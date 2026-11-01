"""Hashing, signing, idempotency keys and the sliding-window rate limiter."""

import hashlib
import hmac
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from decimal import Decimal

from core.config import get_settings

IDEMPOTENCY_NAMESPACE = uuid.UUID("6f1d3c52-8a8e-4c41-9a54-6a0f6c7e2b10")


def _default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"not serializable: {type(obj).__name__}")


def canonical(obj) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, UTF-8. Same data -> same bytes -> same hash."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default).encode()


def sha256_hex(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sign(obj) -> str:
    key = get_settings().mandate_signing_secret.encode()
    return hmac.new(key, canonical(obj), hashlib.sha256).hexdigest()


def verify_signature(obj, signature: str) -> bool:
    return hmac.compare_digest(sign(obj), signature or "")


def idempotency_key(*parts: str) -> str:
    """Deterministic PayPal-Request-Id: the same action on the same case always gets the same key."""
    return str(uuid.uuid5(IDEMPOTENCY_NAMESPACE, ":".join(parts)))


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class SlidingWindowLimiter:
    """Exact sliding-window counter. Redis sorted set when available, in-process deques otherwise."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.time()
        if self.redis is not None:
            try:
                pipe = self.redis.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_s)
                pipe.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
                pipe.zcard(key)
                pipe.expire(key, window_s)
                _, _, count, _ = pipe.execute()
                return count <= limit
            except Exception:
                pass  # Redis down: fall back to the local window
        with self._lock:
            q = self._local[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            q.append(now)
            return len(q) <= limit
