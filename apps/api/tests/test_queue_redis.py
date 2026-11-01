"""Redis Streams transport (with fakeredis): relay publishes outbox ids, a consumer group processes them,
failures retry, and the cache/limiter use Redis."""

import fakeredis
import pytest

import core.redis_client as rc
from core import queue
from core.cache import bump_cases_generation, cache_aside, cases_generation
from core.database import SessionLocal
from core.security import SlidingWindowLimiter
from models import Outbox
from services import outbox_service
from workers import handlers
from workers.runner import Runner


@pytest.fixture
def fake_redis(monkeypatch):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr(rc, "_client", client)
    monkeypatch.setattr(rc, "_checked", True)
    from core.config import get_settings

    monkeypatch.setattr(get_settings(), "queue_mode", "auto")
    yield client
    rc.reset_redis()


def test_redis_mode_relays_and_consumes(fake_redis, monkeypatch):
    seen = []
    monkeypatch.setitem(handlers.HANDLERS, "test.echo", lambda db, payload: seen.append(payload["n"]))
    runner = Runner()
    assert runner.mode == "redis"

    with SessionLocal() as db:
        ids = [outbox_service.add(db, "test.echo", {"n": i}).id for i in range(3)]
        db.commit()

    assert runner.relay_once() >= 3
    assert queue.depth() >= 3
    runner.consume_once(block_ms=10)
    assert sorted(seen) == [0, 1, 2]
    with SessionLocal() as db:
        assert all(db.get(Outbox, i).status == "done" for i in ids)


def test_failed_job_is_retried_then_dead_lettered(fake_redis, monkeypatch):
    def boom(db, payload):
        raise RuntimeError("downstream exploded")

    monkeypatch.setitem(handlers.HANDLERS, "test.boom", boom)
    monkeypatch.setitem(outbox_service.TOPIC_RETRY, "test.boom", (2, 0.0, 0.0))
    runner = Runner()
    with SessionLocal() as db:
        oid = outbox_service.add(db, "test.boom", {}).id
        db.commit()

    for _ in range(2):
        with SessionLocal() as db:  # make the retry due immediately
            row = db.get(Outbox, oid)
            if row.status == "pending":
                row.next_attempt_at = row.created_at
            db.commit()
        runner.relay_once()
        runner.consume_once(block_ms=10)

    with SessionLocal() as db:
        row = db.get(Outbox, oid)
        assert row.status == "dead"
        assert row.attempts == 2
    dead = [d for d in outbox_service.dead_letters(SessionLocal()) if d["outbox_id"] == oid]
    assert dead and "downstream exploded" in dead[0]["error"]


def test_cache_and_limiter_use_redis(fake_redis):
    calls = []
    key = f"culpa:test:{cases_generation()}"
    assert cache_aside(key, 30, lambda: calls.append(1) or {"v": 1}) == {"v": 1}
    assert cache_aside(key, 30, lambda: calls.append(1) or {"v": 2}) == {"v": 1}
    assert calls == [1]
    before = cases_generation()
    bump_cases_generation()
    assert cases_generation() == before + 1

    lim = SlidingWindowLimiter(fake_redis)
    assert all(lim.allow("culpa:rl:t", 2, 60) for _ in range(2))
    assert not lim.allow("culpa:rl:t", 2, 60)
