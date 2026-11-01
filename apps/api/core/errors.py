"""Typed errors raised by services. Routers map them to HTTP status codes."""


class CulpaError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(CulpaError):
    status_code = 404


class Conflict(CulpaError):
    status_code = 409


class InvalidState(CulpaError):
    status_code = 409


class Unauthorized(CulpaError):
    status_code = 401


class RateLimited(CulpaError):
    status_code = 429


class EvidenceTampered(CulpaError):
    status_code = 409


class PayPalError(CulpaError):
    status_code = 502

    def __init__(self, message: str, status: int | None = None, name: str | None = None, debug_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.name = name
        self.debug_id = debug_id


class PayPalRetryable(PayPalError):
    """5xx, timeouts, connection errors, open circuit. Safe to retry with the same idempotency key."""


class PayPalFinal(PayPalError):
    """4xx business errors. Retrying will not help."""


class PayPalNotConfigured(CulpaError):
    status_code = 503
