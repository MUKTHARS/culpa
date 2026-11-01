"""Redis Streams transport for outbox messages.

The outbox table in the database is the source of truth. Streams only carry outbox row ids to
workers, so a Redis outage delays work but never loses it.
"""

from core.config import get_settings
from core.logging import get_logger
from core.redis_client import get_redis

log = get_logger(__name__)

STREAM = "culpa:jobs"
GROUP = "culpa-workers"


def queue_mode() -> str:
    """'redis' when configured and reachable, otherwise 'inline' (the relay runs handlers directly)."""
    mode = get_settings().queue_mode
    if mode == "inline":
        return "inline"
    if get_redis() is not None:
        return "redis"
    if mode == "redis":
        log.warning("queue_redis_requested_but_unavailable")
    return "inline"


def ensure_group() -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def publish(outbox_id: int, topic: str) -> None:
    r = get_redis()
    if r is None:
        raise RuntimeError("redis not available")
    r.xadd(STREAM, {"outbox_id": str(outbox_id), "topic": topic}, maxlen=100_000, approximate=True)


def read(consumer: str, block_ms: int = 1000, count: int = 10) -> list[tuple[str, dict]]:
    r = get_redis()
    if r is None:
        return []
    resp = r.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=count, block=block_ms)
    messages = []
    for _stream, entries in resp or []:
        messages.extend(entries)
    return messages


def claim_stale(consumer: str, idle_ms: int = 60_000) -> list[tuple[str, dict]]:
    """Take over messages a crashed worker never acknowledged."""
    r = get_redis()
    if r is None:
        return []
    try:
        result = r.xautoclaim(STREAM, GROUP, consumer, min_idle_time=idle_ms, start_id="0-0", count=10)
        return list(result[1]) if result else []
    except Exception as exc:
        log.warning("xautoclaim_failed", error=str(exc))
        return []


def ack(message_id: str) -> None:
    r = get_redis()
    if r is not None:
        r.xack(STREAM, GROUP, message_id)


def depth() -> int | None:
    r = get_redis()
    if r is None:
        return None
    try:
        return int(r.xlen(STREAM))
    except Exception:
        return None
