"""Cache layers: an in-process LRU and Redis cache-aside, with stampede protection.

A cache failure never breaks a request: every Redis call falls back to the source of truth.
"""

import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from core.logging import get_logger
from core.redis_client import get_redis

log = get_logger(__name__)
_MISSING = object()


class LRUCache:
    """Bounded LRU with per-entry TTL. OrderedDict gives O(1) move-to-end and pop-oldest."""

    def __init__(self, capacity: int = 1024):
        self.capacity = capacity
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str, default=None):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return default
            expires_at, value = item
            if expires_at and expires_at < time.time():
                del self._data[key]
                return default
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value, ttl_s: float | None = None) -> None:
        with self._lock:
            self._data[key] = ((time.time() + ttl_s) if ttl_s else 0.0, value)
            self._data.move_to_end(key)
            while len(self._data) > self.capacity:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


local_cache = LRUCache(capacity=2048)

CASES_GEN_KEY = "culpa:cases:gen"


def cache_get(key: str):
    r = get_redis()
    if r is None:
        return local_cache.get(key, _MISSING)
    try:
        raw = r.get(key)
        return _MISSING if raw is None else json.loads(raw)
    except Exception as exc:
        log.warning("cache_get_failed", key=key, error=str(exc))
        return _MISSING


def cache_set(key: str, value, ttl_s: int) -> None:
    r = get_redis()
    if r is None:
        local_cache.set(key, value, ttl_s)
        return
    try:
        r.set(key, json.dumps(value, default=str), ex=ttl_s)
    except Exception as exc:
        log.warning("cache_set_failed", key=key, error=str(exc))


def cache_aside(key: str, ttl_s: int, loader: Callable[[], Any]):
    """Read-through with a short lock so only one caller rebuilds a cold key."""
    value = cache_get(key)
    if value is not _MISSING:
        return value
    r = get_redis()
    if r is not None:
        try:
            if not r.set(f"{key}:lock", "1", nx=True, px=3000):
                time.sleep(0.05)
                value = cache_get(key)
                if value is not _MISSING:
                    return value
        except Exception:
            pass
    value = loader()
    cache_set(key, value, ttl_s)
    if r is not None:
        try:
            r.delete(f"{key}:lock")
        except Exception:
            pass
    return value


def cases_generation() -> int:
    r = get_redis()
    if r is None:
        return int(local_cache.get(CASES_GEN_KEY, 0))
    try:
        return int(r.get(CASES_GEN_KEY) or 0)
    except Exception:
        return 0


def bump_cases_generation() -> None:
    """Every case write bumps the generation; cached pages keyed by the old generation go unused."""
    r = get_redis()
    if r is None:
        local_cache.set(CASES_GEN_KEY, int(local_cache.get(CASES_GEN_KEY, 0)) + 1)
        return
    try:
        r.incr(CASES_GEN_KEY)
    except Exception:
        local_cache.clear()
