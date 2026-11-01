"""Time-sortable unique ids and UTC time helpers."""

from datetime import UTC, datetime

import ulid


def new_id(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new()).lower()}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC so comparisons never mix aware and naive."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime | None) -> str | None:
    dt = as_utc(dt)
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
