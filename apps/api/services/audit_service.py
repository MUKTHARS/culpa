"""Append-only, hash-chained audit log."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import lock_key
from core.ids import iso, utcnow
from core.security import sha256_hex
from models import AuditLog

GENESIS = "0" * 64


def _row_hash(prev_hash: str, case_id: str | None, actor: str, action: str, data: dict, created_at: str) -> str:
    return sha256_hex({"prev": prev_hash, "case_id": case_id, "actor": actor, "action": action, "data": data,
                       "created_at": created_at})


def append(db: Session, *, actor: str, action: str, case_id: str | None = None, data: dict | None = None) -> AuditLog:
    lock_key(db, "audit-chain")
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    now = utcnow()
    data = data or {}
    row = AuditLog(case_id=case_id, actor=actor, action=action, data=data, prev_hash=prev,
                   hash=_row_hash(prev, case_id, actor, action, data, iso(now)), created_at=now)
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """Returns (ok, id of the first broken row)."""
    prev = GENESIS
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        expected = _row_hash(prev, row.case_id, row.actor, row.action, row.data, iso(row.created_at))
        if row.prev_hash != prev or row.hash != expected:
            return False, row.id
        prev = row.hash
    return True, None


def for_case(db: Session, case_id: str) -> list[dict]:
    rows = db.execute(select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.id)).scalars()
    return [{"id": r.id, "actor": r.actor, "action": r.action, "data": r.data, "hash": r.hash,
             "prev_hash": r.prev_hash, "created_at": iso(r.created_at)} for r in rows]
