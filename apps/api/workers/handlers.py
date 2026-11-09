"""Job handlers, one per outbox topic. Each must be idempotent: delivery is at-least-once."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.cache import bump_cases_generation
from core.errors import PayPalError
from core.logging import get_logger
from models import WebhookEvent
from services import case_service, settlement_service
from services.paypal import disputes as pp_disputes
from services.paypal.client import get_paypal

log = get_logger(__name__)


def dispute_received(db: Session, payload: dict) -> None:
    event = db.execute(select(WebhookEvent).where(WebhookEvent.paypal_event_id == payload["event_id"])).scalar_one()
    resource = event.payload.get("resource", {}) or {}
    dispute_id = resource.get("dispute_id") or resource.get("id")
    dispute = resource
    pp = get_paypal()
    if dispute_id and pp.configured:
        try:
            dispute = pp_disputes.get_dispute(pp, dispute_id)
        except PayPalError as exc:
            log.warning("dispute_fetch_failed_using_webhook_resource", dispute_id=dispute_id, error=exc.message)
    case_service.create_from_dispute(db, dispute)


def case_analyze(db: Session, payload: dict) -> None:
    case = case_service.analyze(db, payload["case_id"])
    # Same transaction as the verdict: the settlement job is committed with it or not at all.
    settlement_service.execute_autonomous_paypal_resolution(db, case)
    db.commit()
    bump_cases_generation()  # after the commit, so the grid can't cache the old state under the new generation


def settlement_requested(db: Session, payload: dict) -> None:
    settlement_service.execute(db, payload["settlement_id"])


def settlement_dead_lettered(db: Session, payload: dict, error: str) -> None:
    settlement_service.retries_exhausted(db, payload["settlement_id"], error)


# Run in the same transaction that dead-letters the job.
ON_DEAD_LETTER: dict[str, Callable[[Session, dict, str], None]] = {
    "settlement.requested": settlement_dead_lettered,
}

HANDLERS: dict[str, Callable[[Session, dict], None]] = {
    "dispute.received": dispute_received,
    "case.analyze": case_analyze,
    "settlement.requested": settlement_requested,
}
