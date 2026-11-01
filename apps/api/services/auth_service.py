"""Analyst login: one account stored in the database, scrypt password hashes, expiring session tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.ids import as_utc, new_id, utcnow
from core.logging import get_logger
from models import AnalystSession, AnalystUser
from services import audit_service

log = get_logger(__name__)

# scrypt parameters: N=2^14, r=8, p=1 (~16 MB, OWASP minimum). Stored with the hash so they can be raised later.
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
                                dklen=32)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login_required(db: Session) -> bool:
    return db.execute(select(AnalystUser.id).limit(1)).first() is not None


def ensure_seed_user(db: Session) -> None:
    """Create the account from ANALYST_USERNAME / ANALYST_PASSWORD, or update its password if it changed."""
    s = get_settings()
    username, password = s.analyst_username.strip(), s.analyst_password
    if not username or not password:
        return
    user = db.execute(select(AnalystUser).where(AnalystUser.username == username)).scalar_one_or_none()
    if user is None:
        db.add(AnalystUser(id=new_id("usr"), username=username, password_hash=hash_password(password)))
        log.info("analyst_user_created", username=username)
    elif not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
        db.execute(delete(AnalystSession).where(AnalystSession.user_id == user.id))  # old sessions end
        log.info("analyst_password_updated", username=username)
    db.flush()


def login(db: Session, username: str, password: str) -> tuple[str, AnalystUser] | None:
    user = db.execute(select(AnalystUser).where(AnalystUser.username == username.strip())).scalar_one_or_none()
    if user is None:
        verify_password(password, hash_password("timing-equalizer"))  # same work whether or not the user exists
        return None
    if not verify_password(password, user.password_hash):
        audit_service.append(db, actor=f"analyst:{user.username}", action="auth.login_failed")
        return None
    now = utcnow()
    token = secrets.token_urlsafe(32)
    db.add(AnalystSession(token_hash=_token_hash(token), user_id=user.id, created_at=now,
                          expires_at=now + timedelta(hours=get_settings().session_ttl_hours)))
    db.execute(delete(AnalystSession).where(AnalystSession.expires_at < now))  # housekeeping
    user.last_login_at = now
    audit_service.append(db, actor=f"analyst:{user.username}", action="auth.login")
    db.flush()
    return token, user


def resolve(db: Session, token: str) -> AnalystUser | None:
    row = db.get(AnalystSession, _token_hash(token))
    if row is None:
        return None
    if as_utc(row.expires_at) <= utcnow():
        db.delete(row)
        db.commit()
        return None
    return db.get(AnalystUser, row.user_id)


def logout(db: Session, token: str) -> None:
    row = db.get(AnalystSession, _token_hash(token))
    if row is not None:
        db.delete(row)
        db.flush()
