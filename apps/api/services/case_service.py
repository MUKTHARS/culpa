"""Cases: create from PayPal disputes or the simulator, build the evidence bundle, run the engine, approve actions."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.cache import bump_cases_generation, cache_aside, cases_generation
from core.config import get_settings
from core.database import lock_key
from core.errors import CulpaError, InvalidState, NotFound
from core.ids import as_utc, iso, new_id, utcnow
from core.logging import get_logger
from core.security import idempotency_key, verify_signature
from engine.dsa import DSU, top_k_review
from engine.pipeline import analyze as run_engine
from engine.types import (
    BuyerSignals,
    Candidate,
    CaseBundle,
    Claim,
    Constraints,
    Delivery,
    Integrity,
    ListingVersion,
    Mandate,
    OrderInfo,
    Trace,
)
from models import AgentTrace, Case, ListingSnapshot, Order, Product, ProductVersion, Settlement
from models import Mandate as MandateRow
from services import audit_service, evidence_service, outbox_service
from services.llm_service import get_llm
from services.paypal import disputes as pp_disputes

log = get_logger(__name__)

REASONS = ("ITEM_NOT_RECEIVED", "ITEM_NOT_AS_DESCRIBED", "UNAUTHORISED", "OTHER")


def _touch(case: Case) -> None:
    case.version += 1
    case.updated_at = utcnow()
    bump_cases_generation()


def create_simulated(db: Session, *, order_id: str, reason: str, claim_text: str, actor: str) -> Case:
    order = db.get(Order, order_id)
    if order is None:
        raise NotFound(f"order {order_id} not found")
    if order.status != "captured":
        raise InvalidState("only captured orders can be disputed")
    if reason not in REASONS:
        raise CulpaError(f"reason must be one of {', '.join(REASONS)}")
    case = Case(id=new_id("case"), merchant_id=order.merchant_id, order_id=order.id, source="simulator", reason=reason,
                claim_text=claim_text.strip(), buyer_id=order.buyer_id, amount=order.amount, currency=order.currency,
                status="open")
    db.add(case)
    db.flush()
    audit_service.append(db, actor=actor, action="case.opened", case_id=case.id,
                         data={"source": "simulator", "order_id": order.id, "reason": reason})
    outbox_service.add(db, "case.analyze", {"case_id": case.id})
    bump_cases_generation()
    return case


def create_from_dispute(db: Session, dispute: dict) -> Case:
    """Idempotent: one case per PayPal dispute id."""
    dispute_id = dispute.get("dispute_id") or dispute.get("id")
    if not dispute_id:
        raise CulpaError("dispute payload has no dispute_id")
    lock_key(db, f"dispute:{dispute_id}")
    existing = db.execute(select(Case).where(Case.paypal_dispute_id == dispute_id)).scalar_one_or_none()
    if existing is not None:
        return existing

    capture_id = pp_disputes.capture_id_of_dispute(dispute)
    order = None
    if capture_id:
        order = db.execute(select(Order).where(Order.capture_id == capture_id)).scalar_one_or_none()
    amount = (dispute.get("dispute_amount") or {}).get("value") or (order.amount if order else "0.00")
    currency = (dispute.get("dispute_amount") or {}).get("currency_code") or (order.currency if order else "USD")
    case = Case(id=new_id("case"), merchant_id=order.merchant_id if order else "", order_id=order.id if order else None,
                paypal_dispute_id=dispute_id, source="paypal", reason=dispute.get("reason", "OTHER"),
                claim_text=pp_disputes.claim_text_of_dispute(dispute), buyer_id=order.buyer_id if order else "",
                amount=str(amount), currency=currency, status="open")
    db.add(case)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.execute(select(Case).where(Case.paypal_dispute_id == dispute_id)).scalar_one()
    audit_service.append(db, actor="paypal", action="case.opened", case_id=case.id,
                         data={"source": "paypal", "dispute_id": dispute_id, "capture_id": capture_id})
    outbox_service.add(db, "case.analyze", {"case_id": case.id})
    bump_cases_generation()
    return case


def _buyer_signals(db: Session, case: Case, order: Order) -> BuyerSignals:
    since = utcnow() - timedelta(days=30)
    times = sorted(iso(as_utc(c.created_at)) for c in db.execute(
        select(Case).where(Case.buyer_id == case.buyer_id, Case.buyer_id != "")).scalars()
        if as_utc(c.created_at) >= since)

    dsu = DSU()
    for buyer_id, device in db.execute(select(Order.buyer_id, Order.buyer_device_hash)).all():
        dsu.find(f"buyer:{buyer_id}")
        if device:
            dsu.union(f"buyer:{buyer_id}", f"device:{device}")
    ring = [m[len("buyer:"):] for m in dsu.members(f"buyer:{order.buyer_id}") if m.startswith("buyer:")]
    fraud_buyers = {c.buyer_id for c in db.execute(
        select(Case).where(Case.fault_class == "F6", Case.buyer_id.in_(ring), Case.buyer_id != order.buyer_id)).scalars()}
    return BuyerSignals(recent_dispute_times=times, ring_size=len(ring), ring_fraud_count=len(fraud_buyers))


def build_bundle(db: Session, case: Case) -> CaseBundle:
    order = db.get(Order, case.order_id) if case.order_id else None
    if order is None:
        raise NotFound("no Culpa evidence recorded for this transaction")
    m = db.get(MandateRow, order.mandate_id)
    t = db.get(AgentTrace, order.trace_id)
    sn = db.get(ListingSnapshot, order.snapshot_id)
    history = db.execute(select(ProductVersion).where(ProductVersion.product_id == order.product_id)
                         .order_by(ProductVersion.captured_at)).scalars()
    mandate_ok = verify_signature(evidence_service.mandate_payload(m), m.signature)
    return CaseBundle(
        case_id=case.id,
        mandate=Mandate(text=m.text, constraints=Constraints(**m.constraints), signature_valid=mandate_ok),
        trace=Trace(policy=t.policy, instruction=t.instruction, candidates=[Candidate(**c) for c in t.candidates],
                    chosen_id=t.chosen_product_id, reasoning=t.reasoning),
        snapshot=ListingVersion(version=sn.product_version, title=sn.title, price=sn.price, attributes=sn.attributes,
                                captured_at=iso(sn.captured_at)),
        order=OrderInfo(amount=order.amount, currency=order.currency, quantity=order.quantity,
                        merchant_id=order.merchant_id, category=order.category, created_at=iso(order.created_at),
                        approved_at=iso(order.approved_at)),
        delivery=Delivery(shipped=order.shipped_at is not None, delivered=order.delivered,
                          tracking=order.tracking_number, attributes=order.delivered_attributes,
                          shipped_at=iso(order.shipped_at)),
        claim=Claim(reason=case.reason, text=case.claim_text),
        listing_history=[ListingVersion(version=v.version, title=v.title, price=v.price, attributes=v.attributes,
                                        captured_at=iso(v.captured_at)) for v in history],
        buyer=_buyer_signals(db, case, order),
        integrity=Integrity(stored_root=order.evidence_root, recomputed_root=evidence_service.recompute_root(m, t, sn)),
        now=iso(utcnow()),
    )


def analyze(db: Session, case_id: str) -> Case:
    lock_key(db, f"case:{case_id}")
    case = db.get(Case, case_id)
    if case is None:
        raise NotFound(f"case {case_id} not found")
    if case.status in ("settling", "settled"):
        return case
    s = get_settings()
    case.status = "analyzing"
    try:
        bundle = build_bundle(db, case)
    except NotFound as exc:
        case.status = "needs_review"
        case.error = exc.message
        case.recommended_action = "review"
        case.analyzed_at = utcnow()
        _touch(case)
        audit_service.append(db, actor="engine", action="case.needs_review", case_id=case.id, data={"error": exc.message})
        return case

    verdict = run_engine(bundle, llm=get_llm(), threshold=s.confidence_threshold)
    v = verdict.to_dict()
    case.verdict = v
    case.fault_class = verdict.fault_class
    case.fault_name = verdict.fault_name
    case.split = verdict.split
    case.confidence = verdict.confidence
    case.recommended_action = verdict.action
    case.refund_amount = verdict.refund_amount
    case.liability = verdict.liability
    case.flags = verdict.flags
    case.error = None
    case.analyzed_at = utcnow()
    case.status = "needs_review" if verdict.action == "review" else "awaiting_approval"
    _touch(case)
    audit_service.append(db, actor="engine", action="case.analyzed", case_id=case.id,
                         data={"fault_class": verdict.fault_class, "split": verdict.split,
                               "confidence": verdict.confidence, "action": verdict.action, "flags": verdict.flags})
    if s.auto_settle and verdict.action != "review":
        approve(db, case.id, actor="auto-policy", action=None)
    return case


def approve(db: Session, case_id: str, *, actor: str, action: str | None) -> Settlement:
    lock_key(db, f"case:{case_id}")
    case = db.get(Case, case_id)
    if case is None:
        raise NotFound(f"case {case_id} not found")
    existing = db.execute(select(Settlement).where(Settlement.case_id == case_id)).scalars().first()
    if existing is not None:
        return existing
    if case.status not in ("awaiting_approval", "needs_review"):
        raise InvalidState(f"case is {case.status}; it cannot be approved")
    chosen = action or case.recommended_action
    if chosen not in ("refund_full", "refund_partial", "contest"):
        raise CulpaError("choose an action: refund_full, refund_partial or contest")
    if chosen == "refund_partial" and not case.refund_amount:
        raise CulpaError("no partial amount was computed for this case")
    amount = {"refund_full": case.amount, "refund_partial": case.refund_amount, "contest": None}[chosen]
    st = Settlement(id=new_id("stl"), case_id=case.id, action=chosen, status="approved",
                    idempotency_key=idempotency_key(case.id, chosen), amount=amount, approved_by=actor)
    db.add(st)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.execute(select(Settlement).where(Settlement.case_id == case_id)).scalars().first()
    case.status = "settling"
    _touch(case)
    audit_service.append(db, actor=actor, action="settlement.approved", case_id=case.id,
                         data={"action": chosen, "amount": amount, "override": bool(action and action != case.recommended_action)})
    outbox_service.add(db, "settlement.requested", {"settlement_id": st.id})
    return st


def reanalyze(db: Session, case_id: str, actor: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFound(f"case {case_id} not found")
    if case.status in ("settling", "settled"):
        raise InvalidState("a settled case cannot be re-analyzed")
    case.status = "open"
    _touch(case)
    audit_service.append(db, actor=actor, action="case.reanalyze_requested", case_id=case.id)
    outbox_service.add(db, "case.analyze", {"case_id": case.id})
    return case


def case_row(c: Case) -> dict:
    return {
        "id": c.id, "source": c.source, "status": c.status, "reason": c.reason, "amount": c.amount,
        "currency": c.currency, "buyer_id": c.buyer_id, "order_id": c.order_id, "paypal_dispute_id": c.paypal_dispute_id,
        "fault_class": c.fault_class, "fault_name": c.fault_name, "split": c.split, "confidence": c.confidence,
        "recommended_action": c.recommended_action, "refund_amount": c.refund_amount, "flags": c.flags or [],
        "created_at": iso(c.created_at), "updated_at": iso(c.updated_at),
    }


def list_cases(db: Session, status: str | None = None, limit: int = 200) -> list[dict]:
    key = f"culpa:cases:list:{cases_generation()}:{status or 'all'}:{limit}"

    def load() -> list[dict]:
        stmt = select(Case).order_by(Case.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Case.status == status)
        return [case_row(c) for c in db.execute(stmt).scalars()]

    return cache_aside(key, 30, load)


def review_queue(db: Session, k: int = 20) -> list[str]:
    rows = db.execute(select(Case).where(Case.status == "needs_review")).scalars()
    return top_k_review([(c.id, float(c.amount or 0), float(c.confidence or 0)) for c in rows], k)


def case_detail(db: Session, case_id: str) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFound(f"case {case_id} not found")
    from services.agent_service import order_dict

    order = db.get(Order, case.order_id) if case.order_id else None
    settlement = db.execute(select(Settlement).where(Settlement.case_id == case.id)).scalars().first()
    mandate = trace = None
    if order is not None:
        m = db.get(MandateRow, order.mandate_id)
        t = db.get(AgentTrace, order.trace_id)
        mandate = {"id": m.id, "text": m.text, "constraints": m.constraints, "hash": m.hash}
        candidate_ids = [c["id"] for c in t.candidates]
        images = {p.id: p.image_url for p in db.execute(select(Product).where(Product.id.in_(candidate_ids))).scalars()}
        trace = {"id": t.id, "policy": t.policy, "model": t.model, "instruction": t.instruction,
                 "chosen_product_id": t.chosen_product_id, "reasoning": t.reasoning, "candidates": t.candidates,
                 "candidate_images": images}
    settlement_events = []
    settlement_dict = None
    if settlement is not None:
        settlement_dict = {"id": settlement.id, "action": settlement.action, "status": settlement.status,
                           "amount": settlement.amount, "simulated": settlement.simulated, "error": settlement.error,
                           "attempts": settlement.attempts, "approved_by": settlement.approved_by,
                           "idempotency_key": settlement.idempotency_key, "paypal_response": settlement.paypal_response,
                           "updated_at": iso(settlement.updated_at)}
        settlement_events.append((iso(settlement.created_at), f"Settlement approved: {settlement.action}"))
        if settlement.status in ("succeeded", "failed_final"):
            settlement_events.append((iso(settlement.updated_at), f"Settlement {settlement.status}"))
    return {
        **case_row(case),
        "claim_text": case.claim_text,
        "error": case.error,
        "liability": case.liability,
        "verdict": case.verdict,
        "order": order_dict(db, order) if order else None,
        "mandate": mandate,
        "trace": trace,
        "settlement": settlement_dict,
        "timeline": evidence_service.timeline(order, case, settlement_events),
        "audit": audit_service.for_case(db, case.id),
    }
