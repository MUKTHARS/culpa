"""Circuit breaker and retry with exponential backoff + full jitter."""

import random
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    """closed -> open after `threshold` failures inside `window_s` -> half-open after `cooldown_s` -> closed on success."""

    def __init__(self, name: str, threshold: int = 5, window_s: float = 60.0, cooldown_s: float = 30.0):
        self.name = name
        self.threshold = threshold
        self.window_s = window_s
        self.cooldown_s = cooldown_s
        self._failures: deque[float] = deque()
        self._opened_at: float | None = None
        self._half_open_trial = False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state_locked(time.time())

    def _state_locked(self, now: float) -> str:
        if self._opened_at is None:
            return "closed"
        if now - self._opened_at >= self.cooldown_s:
            return "half_open"
        return "open"

    def before_call(self) -> None:
        with self._lock:
            state = self._state_locked(time.time())
            if state == "open":
                raise CircuitOpen(f"{self.name} circuit is open")
            if state == "half_open":
                if self._half_open_trial:
                    raise CircuitOpen(f"{self.name} circuit is half-open; trial call in flight")
                self._half_open_trial = True

    def release_trial(self) -> None:
        """The half-open trial ended without telling us anything about the service: let the next call try."""
        with self._lock:
            self._half_open_trial = False

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()
            self._opened_at = None
            self._half_open_trial = False

    def record_failure(self) -> None:
        with self._lock:
            now = time.time()
            if self._state_locked(now) == "half_open":
                self._opened_at = now
                self._half_open_trial = False
                return
            self._failures.append(now)
            while self._failures and self._failures[0] < now - self.window_s:
                self._failures.popleft()
            if len(self._failures) >= self.threshold:
                self._opened_at = now


def backoff_delay(attempt: int, base_s: float = 0.5, cap_s: float = 30.0) -> float:
    """Full jitter: uniform(0, min(cap, base * 2^attempt))."""
    return random.uniform(0, min(cap_s, base_s * (2**attempt)))


def retry(fn: Callable[[], T], *, attempts: int, retry_on: tuple[type[BaseException], ...], base_s: float = 0.5,
          cap_s: float = 8.0, sleep: Callable[[float], None] = time.sleep) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            last = exc
            if attempt == attempts - 1:
                break
            sleep(backoff_delay(attempt, base_s, cap_s))
    assert last is not None
    raise last


breakers: dict[str, CircuitBreaker] = {
    "paypal": CircuitBreaker("paypal"),
    "llm": CircuitBreaker("llm", threshold=5, window_s=60, cooldown_s=60),
}
