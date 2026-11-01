"""Safety nets: pull recent disputes in case a webhook was missed, and re-queue settlements stuck mid-flight."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import PayPalError
from core.ids import as_utc, iso, utcnow
from core.logging import get_logger
from models import Case, Settlement
from services import case_service, outbox_service
from services.paypal import disputes as pp_disputes
from services.paypal.client import get_paypal

log = get_logger(__name__)


def missed_disputes(db: Session, lookback: timedelta = timedelta(days=2)) -> int:
    pp = get_paypal()
    if not pp.configured:
        return 0
    try:
        items = pp_disputes.list_disputes(pp, start_time=iso(utcnow() - lookback))
    except PayPalError as exc:
        log.warning("reconcile_list_failed", error=exc.message)
        return 0
    created = 0
    for item in items:
        dispute_id = item.get("dispute_id")
        if not dispute_id:
            continue
        if db.execute(select(Case.id).where(Case.paypal_dispute_id == dispute_id)).first():
            continue
        try:
            full = pp_disputes.get_dispute(pp, dispute_id)
        except PayPalError:
            full = item
        case_service.create_from_dispute(db, full)
        created += 1
    db.commit()
    return created


def stuck_settlements(db: Session, older_than: timedelta = timedelta(minutes=10)) -> int:
    cutoff = utcnow() - older_than
    rows = db.execute(select(Settlement).where(Settlement.status == "executing")).scalars().all()
    n = 0
    for s in rows:
        if as_utc(s.updated_at) < cutoff:
            outbox_service.add(db, "settlement.requested", {"settlement_id": s.id})
            n += 1
    db.commit()
    return n
