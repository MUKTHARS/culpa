"""Execute an approved settlement on PayPal. The state machine and idempotency key make retries safe."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import InvalidState, NotFound, PayPalFinal, PayPalNotConfigured, PayPalRetryable
from core.ids import as_utc, utcnow
from core.logging import get_logger
from core.cache import bump_cases_generation
from models import Case, Order, Settlement
from models.case import SETTLEMENT_TRANSITIONS
from services import audit_service, case_service
from services.paypal import disputes as pp_disputes
from services.paypal import refunds as pp_refunds
from services.paypal.client import get_paypal

log = get_logger(__name__)

# How long a worker owns an 'executing' settlement; after this it is presumed crashed and may be retried.
EXECUTING_LEASE = timedelta(minutes=5)
# Autonomous settlement never runs below this confidence, whatever the configured threshold says.
MIN_AUTONOMOUS_CONFIDENCE = Decimal("0.80")
AUTO_ACTOR = "auto-policy"
QUEUED = "QUEUED_FOR_PAYPAL"
HELD_FOR_HUMAN_REVIEW = "HELD_FOR_HUMAN_REVIEW"
AUTONOMY_OFF = "AUTONOMY_OFF"
DISPUTE_CAN_BE_ANSWERED = ("OPEN", "WAITING_FOR_SELLER_RESPONSE")
CAPTURE_STATE = {"REFUNDED": "already refunded in full", "PARTIALLY_REFUNDED": "already partly refunded"}


def _transition(s: Settlement, to: str) -> None:
    if to not in SETTLEMENT_TRANSITIONS.get(s.status, set()):
        raise InvalidState(f"settlement {s.id}: {s.status} -> {to} is not allowed")
    s.status = to
    s.updated_at = utcnow()


def _contest_notes(case: Case) -> str:
    v = case.verdict or {}
    lines = [f"Culpa fault attribution: {case.fault_class} {case.fault_name or ''} "
             f"(confidence {case.confidence}). Evidence fingerprinted at checkout."]
    for e in v.get("evidence", []):
        if e.get("party"):
            lines.append(f"- {e['finding']} [{e['cite']}]")
    return "\n".join(lines)


def _preflight(pp, s: Settlement, case: Case, order: Order) -> None:
    """Re-read PayPal before any money action; Culpa's own records are never enough.

    On a retry the earlier attempt may itself have refunded it, so a changed state is not an error: the POST below
    reuses the same idempotency key and PayPal returns the original result.
    """
    is_retry = s.attempts > 1
    if case.paypal_dispute_id:
        status = pp_disputes.get_dispute(pp, case.paypal_dispute_id).get("status")
        if status not in DISPUTE_CAN_BE_ANSWERED and not is_retry:
            raise PayPalFinal(f"The PayPal dispute is {status} and can no longer be answered. No money moved.")
        return
    if s.action == "contest":
        return
    if not order.capture_id:
        raise PayPalFinal("order has no capture id to refund")
    capture = pp_refunds.get_capture(pp, order.capture_id)
    status = capture.get("status")
    if status != "COMPLETED" and not is_retry:
        state = CAPTURE_STATE.get(status, f"in state {status}")
        raise PayPalFinal(f"This payment is {state} on PayPal, so Culpa did not refund it. No money moved.")
    paid = (capture.get("amount") or {}).get("value")
    if paid is not None and s.amount is not None and Decimal(s.amount) > Decimal(paid):
        raise PayPalFinal(f"Refund of {s.amount} is more than the {paid} PayPal captured. No money moved.")


def _perform(s: Settlement, case: Case, order: Order | None) -> tuple[dict, bool]:
    """Returns (response, simulated)."""
    pp = get_paypal()
    real = pp.configured and order is not None and not order.simulated
    if not real:
        return {"simulated": True, "action": s.action, "amount": s.amount,
                "note": "PayPal not configured or simulated order; no money moved."}, True
    _preflight(pp, s, case, order)

    note = f"Culpa case {case.id}: {case.fault_name or 'dispute'}"
    if s.action == "refund_full":
        if case.paypal_dispute_id:
            return pp_disputes.accept_claim(pp, case.paypal_dispute_id, note, s.idempotency_key), False
        if not order.capture_id:
            raise PayPalFinal("order has no capture id to refund")
        return pp_refunds.refund_capture(pp, order.capture_id, amount=None, currency=order.currency, note=note,
                                         idempotency_key=s.idempotency_key), False
    if s.action == "refund_partial":
        if case.paypal_dispute_id:
            return pp_disputes.make_refund_offer(pp, case.paypal_dispute_id, s.amount, order.currency, note,
                                                 s.idempotency_key), False
        if not order.capture_id:
            raise PayPalFinal("order has no capture id to refund")
        return pp_refunds.refund_capture(pp, order.capture_id, amount=s.amount, currency=order.currency, note=note,
                                         idempotency_key=s.idempotency_key), False
    if s.action == "contest":
        if not case.paypal_dispute_id:
            return {"note": "Simulator case: there is no PayPal dispute to contest; claim denied in Culpa."}, True
        return pp_disputes.provide_evidence(pp, case.paypal_dispute_id, _contest_notes(case), s.idempotency_key), False
    raise PayPalFinal(f"unknown settlement action {s.action}")


def _claim(db: Session, s: Settlement) -> bool:
    """Atomically move to 'executing' and commit, before the PayPal call. Only one worker can win.

    A database lock cannot do this: it would have to be held across the network call. A crash leaves a visible
    'executing' row, which becomes claimable again once its lease runs out; the retry reuses the idempotency key.
    """
    if s.status == "executing":
        if as_utc(s.updated_at) > utcnow() - EXECUTING_LEASE:
            return False
    elif "executing" not in SETTLEMENT_TRANSITIONS.get(s.status, set()):
        raise InvalidState(f"settlement {s.id}: {s.status} -> executing is not allowed")
    won = db.execute(update(Settlement)
                     .where(Settlement.id == s.id, Settlement.status == s.status, Settlement.attempts == s.attempts)
                     .values(status="executing", attempts=s.attempts + 1, updated_at=utcnow())).rowcount == 1
    db.commit()
    db.refresh(s)
    return won


def execute(db: Session, settlement_id: str) -> Settlement:
    s = db.get(Settlement, settlement_id)
    if s is None:
        raise NotFound(f"settlement {settlement_id} not found")
    if s.status in ("succeeded", "failed_final"):
        return s
    case = db.get(Case, s.case_id)
    order = db.get(Order, case.order_id) if case.order_id else None

    if not _claim(db, s):
        return s  # another worker is executing it right now

    try:
        response, simulated = _perform(s, case, order)
    except PayPalRetryable as exc:
        _transition(s, "failed_retryable")
        s.error = exc.message
        audit_service.append(db, actor="settlement", action="settlement.retrying", case_id=case.id,
                             data={"error": exc.message, "attempt": s.attempts, "paypal_debug_id": exc.debug_id})
        db.commit()
        bump_cases_generation()
        raise
    except (PayPalFinal, PayPalNotConfigured) as exc:
        _transition(s, "failed_final")
        s.error = exc.message
        case.status = "settle_failed"
        case.version += 1
        audit_service.append(db, actor="settlement", action="settlement.failed", case_id=case.id,
                             data={"error": exc.message, "paypal_debug_id": getattr(exc, "debug_id", None)})
        db.commit()
        bump_cases_generation()
        return s

    _transition(s, "succeeded")
    s.paypal_response = response
    s.simulated = simulated
    s.error = None
    # A partial refund on a real PayPal dispute is an offer: the money moves only if the buyer accepts it.
    offer = s.action == "refund_partial" and bool(case.paypal_dispute_id) and not simulated
    case.status = "offer_sent" if offer else "settled"
    case.version += 1
    case.updated_at = utcnow()
    audit_service.append(db, actor="settlement", action="settlement.succeeded", case_id=case.id,
                         data={"action": s.action, "amount": s.amount, "simulated": simulated})
    db.commit()
    bump_cases_generation()
    return s


def retries_exhausted(db: Session, settlement_id: str, error: str) -> None:
    """The job was dead-lettered. Surface it on the case; the settlement stays retryable so Jobs > Replay still works."""
    s = db.get(Settlement, settlement_id)
    if s is None or s.status in ("succeeded", "failed_final"):
        return
    case = db.get(Case, s.case_id)
    case.status = "settle_failed"
    case.version += 1
    case.updated_at = utcnow()
    s.error = error[:2000]
    audit_service.append(db, actor="settlement", action="settlement.dead_lettered", case_id=case.id,
                         data={"error": error[:500], "attempts": s.attempts})
    bump_cases_generation()


def _hold_reason(db: Session, case: Case) -> str | None:
    """A confident verdict that automation still must not act on, or None."""
    others = case.order_id and db.execute(select(Settlement).join(Case, Case.id == Settlement.case_id).where(
        Case.order_id == case.order_id, Settlement.case_id != case.id, Settlement.status != "failed_final")).first()
    if others:
        return "already_settled"  # this order has been settled, or is being settled, under another case
    category = (case.verdict or {}).get("claim_category")
    if case.fault_class == "F5" and category != "not_received":
        return "claim_contradicts_delivery"  # the buyer describes an item the records say never arrived
    return None


def execute_autonomous_paypal_resolution(db: Session, case: Case) -> str:
    """Settle a fresh verdict with no analyst, or hold it for one. Called in the verdict's own transaction.

    Only queues the work: the outbox job and execute() still own every PayPal call, so an autonomous settlement has
    the same idempotency key, state machine, retries and dead-lettering as an analyst's.
    """
    settings = get_settings()
    if not settings.auto_settle:
        return AUTONOMY_OFF
    threshold = max(MIN_AUTONOMOUS_CONFIDENCE, Decimal(str(settings.confidence_threshold)))
    confident = case.confidence is not None and Decimal(str(case.confidence)) >= threshold
    hold = _hold_reason(db, case) if confident else None
    if hold is not None:
        case.flags = sorted({*(case.flags or []), hold})
        case.status = "needs_review"
        audit_service.append(db, actor=AUTO_ACTOR, action="settlement.held_for_human", case_id=case.id,
                             data={"confidence": case.confidence, "label": HELD_FOR_HUMAN_REVIEW, "reason": hold})
        return HELD_FOR_HUMAN_REVIEW
    if not confident or case.recommended_action not in ("refund_full", "refund_partial", "contest"):
        if case.status == "needs_review":
            audit_service.append(db, actor=AUTO_ACTOR, action="settlement.held_for_human", case_id=case.id,
                                 data={"confidence": case.confidence, "label": HELD_FOR_HUMAN_REVIEW})
        return HELD_FOR_HUMAN_REVIEW
    if case.status == "awaiting_approval":
        case_service.approve(db, case.id, actor=AUTO_ACTOR, action=None)
    return QUEUED
