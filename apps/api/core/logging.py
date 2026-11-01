"""Structured JSON logging with PII redaction and a per-request correlation id."""

import logging
import re
from contextvars import ContextVar

import structlog

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s-]{8,}\d")
_SENSITIVE_KEYS = {"email", "phone", "address", "address_line_1", "password", "secret", "access_token", "authorization"}


def _redact_value(value):
    if isinstance(value, str):
        return _PHONE.sub("[phone]", _EMAIL.sub("[email]", value))
    if isinstance(value, dict):
        return {k: ("[redacted]" if k.lower() in _SENSITIVE_KEYS else _redact_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def _redact(_, __, event_dict):
    return {k: ("[redacted]" if k.lower() in _SENSITIVE_KEYS else _redact_value(v)) for k, v in event_dict.items()}


def _add_correlation_id(_, __, event_dict):
    event_dict.setdefault("correlation_id", correlation_id.get())
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_correlation_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "culpa"):
    return structlog.get_logger(name)
