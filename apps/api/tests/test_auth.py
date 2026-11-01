"""Analyst login: DB-backed account, hashed password, expiring sessions. The account is removed after each test,
so the rest of the suite keeps running in open local-dev mode."""

from datetime import timedelta

import pytest
from sqlalchemy import delete

from core.auth import deps
from core.config import get_settings
from core.database import SessionLocal
from core.ids import utcnow
from core.security import SlidingWindowLimiter
from models import AnalystSession, AnalystUser
from services import auth_service


@pytest.fixture
def account(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "analyst_username", "analyst")
    monkeypatch.setattr(s, "analyst_password", "correct horse battery")
    monkeypatch.setattr(deps, "_limiter", SlidingWindowLimiter(None))
    with SessionLocal() as db:
        auth_service.ensure_seed_user(db)
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(AnalystSession))
        db.execute(delete(AnalystUser))
        db.commit()


def _login(client, password="correct horse battery"):
    return client.post("/auth/login", json={"username": "analyst", "password": password})


def test_password_hashing():
    h = auth_service.hash_password("s3cret")
    assert h.startswith("scrypt$") and "s3cret" not in h
    assert auth_service.verify_password("s3cret", h)
    assert not auth_service.verify_password("wrong", h)
    assert not auth_service.verify_password("s3cret", "garbage")


def test_console_open_without_account(client):
    assert client.get("/cases").status_code == 200
    assert client.get("/auth/me").json() == {"login_required": False, "authenticated": True, "username": None}


def test_login_flow(client, account):
    assert client.get("/cases").status_code == 401
    assert _login(client, "wrong").status_code == 401

    r = _login(client)
    assert r.status_code == 200
    token = r.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/cases", headers=auth).status_code == 200
    assert client.get("/auth/me", headers=auth).json()["username"] == "analyst"
    assert client.get("/cases", headers={"Authorization": "Bearer not-a-token"}).status_code == 401

    with SessionLocal() as db:  # the raw token is never stored
        stored = [s.token_hash for s in db.query(AnalystSession).all()]
    assert token not in stored and len(stored) == 1

    client.post("/auth/logout", headers=auth)
    assert client.get("/cases", headers=auth).status_code == 401


def test_expired_session_rejected(client, account):
    token = _login(client).json()["token"]
    with SessionLocal() as db:
        for s in db.query(AnalystSession).all():
            s.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get("/cases", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_password_change_ends_sessions(client, account, monkeypatch):
    token = _login(client).json()["token"]
    monkeypatch.setattr(get_settings(), "analyst_password", "a new password")
    with SessionLocal() as db:
        auth_service.ensure_seed_user(db)
        db.commit()
    assert client.get("/cases", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _login(client, "a new password").status_code == 200


def test_login_rate_limited(client, account):
    codes = [_login(client, "wrong").status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
