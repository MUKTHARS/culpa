"""Transactional outbox: add messages inside a business transaction; workers claim, run, retry or dead-letter them."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from core.database import is_postgres
from core.ids import iso, utcnow
from core.resilience import backoff_delay
from models import DeadLetter, Outbox

TOPIC_RETRY = {
    # topic: (max attempts, base backoff seconds, cap seconds)
    "dispute.received": (5, 2.0, 32.0),
    "case.analyze": (5, 2.0, 32.0),
    "settlement.requested": (8, 5.0, 600.0),
}
DEFAULT_RETRY = (5, 2.0, 60.0)
STALE_DISPATCH = timedelta(minutes=5)


def add(db: Session, topic: str, payload: dict) -> Outbox:
    row = Outbox(topic=topic, payload=payload, status="pending", next_attempt_at=utcnow())
    db.add(row)
    db.flush()
    return row


def claim_due(db: Session, limit: int = 20) -> list[Outbox]:
    """Pending rows that are due, plus rows dispatched long ago whose worker never finished them."""
    now = utcnow()
    stmt = (
        select(Outbox)
        .where(or_(
            (Outbox.status == "pending") & (Outbox.next_attempt_at <= now),
            (Outbox.status == "dispatched") & (Outbox.dispatched_at <= now - STALE_DISPATCH),
        ))
        .order_by(Outbox.id)
        .limit(limit)
    )
    if is_postgres():
        stmt = stmt.with_for_update(skip_locked=True)
    return list(db.execute(stmt).scalars())


def mark_dispatched(db: Session, row: Outbox) -> None:
    row.status = "dispatched"
    row.dispatched_at = utcnow()


def mark_done(db: Session, row: Outbox) -> None:
    row.status = "done"
    row.done_at = utcnow()
    row.last_error = None


def fail(db: Session, row: Outbox, error: str) -> bool:
    """Record a failure. Returns True when the message was dead-lettered."""
    max_attempts, base, cap = TOPIC_RETRY.get(row.topic, DEFAULT_RETRY)
    row.attempts += 1
    row.last_error = error[:4000]
    if row.attempts >= max_attempts:
        row.status = "dead"
        db.add(DeadLetter(outbox_id=row.id, topic=row.topic, payload=row.payload, error=row.last_error,
                          attempts=row.attempts))
        return True
    row.status = "pending"
    row.next_attempt_at = utcnow() + timedelta(seconds=max(1.0, backoff_delay(row.attempts, base, cap)))
    return False


def replay_dead(db: Session, dead_id: int) -> Outbox | None:
    dead = db.get(DeadLetter, dead_id)
    if dead is None or dead.replayed_at is not None:
        return None
    dead.replayed_at = utcnow()
    return add(db, dead.topic, dead.payload)


def stats(db: Session) -> dict:
    rows = db.execute(select(Outbox.status, Outbox.id)).all()
    counts: dict[str, int] = {}
    for status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    dead_open = db.execute(select(DeadLetter).where(DeadLetter.replayed_at.is_(None))).scalars().all()
    return {"outbox": counts, "dead_letters_open": len(dead_open)}


def dead_letters(db: Session) -> list[dict]:
    rows = db.execute(select(DeadLetter).order_by(DeadLetter.id.desc()).limit(200)).scalars()
    return [{"id": d.id, "outbox_id": d.outbox_id, "topic": d.topic, "payload": d.payload, "error": d.error,
             "attempts": d.attempts, "created_at": iso(d.created_at), "replayed_at": iso(d.replayed_at)} for d in rows]


def reset_stuck_dispatched(db: Session) -> int:
    """Used on startup in inline mode: anything left 'dispatched' by a previous process goes back to pending."""
    result = db.execute(update(Outbox).where(Outbox.status == "dispatched").values(status="pending"))
    return result.rowcount or 0
