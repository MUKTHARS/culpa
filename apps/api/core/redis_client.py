"""One shared Redis connection, or None when Redis is not configured or not reachable."""

import threading

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)
_lock = threading.Lock()
_client = None
_checked = False


def get_redis():
    global _client, _checked
    if _checked:
        return _client
    with _lock:
        if _checked:
            return _client
        url = get_settings().redis_url
        if url:
            try:
                import redis

                client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
                client.ping()
                _client = client
                log.info("redis_connected")
            except Exception as exc:
                log.warning("redis_unavailable", error=str(exc))
                _client = None
        _checked = True
        return _client


def reset_redis() -> None:
    global _client, _checked
    with _lock:
        _client, _checked = None, False
