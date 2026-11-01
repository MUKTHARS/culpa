"""Execute an approved settlement on PayPal. The state machine and idempotency key make retries safe."""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.database import lock_key
from core.errors import InvalidState, NotFound, PayPalFinal, PayPalNotConfigured, PayPalRetryable
from core.ids import utcnow
from core.logging import get_logger
from core.cache import bump_cases_generation
from models import Case, Order, Settlement
from models.case import SETTLEMENT_TRANSITIONS
from services import audit_service
from services.paypal import disputes as pp_disputes
from services.paypal import refunds as pp_refunds
from services.paypal.client import get_paypal

log = get_logger(__name__)


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


def _perform(s: Settlement, case: Case, order: Order | None) -> tuple[dict, bool]:
    """Returns (response, simulated)."""
    pp = get_paypal()
    real = pp.configured and order is not None and not order.simulated
    if not real:
        return {"simulated": True, "action": s.action, "amount": s.amount,
                "note": "PayPal not configured or simulated order; no money moved."}, True

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


def execute(db: Session, settlement_id: str) -> Settlement:
    lock_key(db, f"settlement:{settlement_id}")
    s = db.get(Settlement, settlement_id)
    if s is None:
        raise NotFound(f"settlement {settlement_id} not found")
    if s.status in ("succeeded", "failed_final"):
        return s
    case = db.get(Case, s.case_id)
    order = db.get(Order, case.order_id) if case.order_id else None

    if s.status != "executing":  # 'executing' means a previous attempt crashed: retry with the same key
        _transition(s, "executing")
    s.attempts += 1
    db.commit()  # written before the PayPal call, so a crash leaves a visible 'executing' row

    try:
        response, simulated = _perform(s, case, order)
    except PayPalRetryable as exc:
        _transition(s, "failed_retryable")
        s.error = exc.message
        audit_service.append(db, actor="settlement", action="settlement.retrying", case_id=case.id,
                             data={"error": exc.message, "attempt": s.attempts, "paypal_debug_id": exc.debug_id})
        db.commit()
        raise
    except (PayPalFinal, PayPalNotConfigured) as exc:
        _transition(s, "failed_final")
        s.error = exc.message
        case.status = "settle_failed"
        case.version += 1
        audit_service.append(db, actor="settlement", action="settlement.failed", case_id=case.id,
                             data={"error": exc.message, "paypal_debug_id": getattr(exc, "debug_id", None)})
        bump_cases_generation()
        db.commit()
        return s

    _transition(s, "succeeded")
    s.paypal_response = response
    s.simulated = simulated
    s.error = None
    case.status = "settled"
    case.version += 1
    case.updated_at = utcnow()
    audit_service.append(db, actor="settlement", action="settlement.succeeded", case_id=case.id,
                         data={"action": s.action, "amount": s.amount, "simulated": simulated})
    bump_cases_generation()
    db.commit()
    return s
