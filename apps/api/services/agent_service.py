"""The buyer agent: signed mandate -> product choice -> listing snapshot -> PayPal order (Agent Toolkit) -> capture."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import CulpaError, NotFound, PayPalError
from core.ids import iso, new_id, utcnow
from core.logging import get_logger
from core.security import idempotency_key, sha256_hex, sign
from engine.agent_policy import attribute_aware
from engine.dsa import Trie
from engine.llm import LLMUnavailable
from engine.types import Candidate
from models import AgentTrace, ListingSnapshot, Mandate, Order, Product
from services import audit_service, evidence_service
from services.llm_service import get_llm
from services.paypal import orders as pp_orders
from services.paypal.client import get_paypal
from services.paypal.toolkit import create_order_via_toolkit

log = get_logger(__name__)


def _candidates(db: Session, category: str | None, max_amount: Decimal | None) -> list[Candidate]:
    trie = None
    if category:
        trie = Trie()
        trie.insert(category)
    out = []
    for p in db.execute(select(Product).order_by(Product.id)).scalars():
        if trie and not trie.allows(p.category):
            continue
        if max_amount is not None and Decimal(p.price) > max_amount:
            continue
        out.append(Candidate(id=p.id, title=p.title, price=p.price, category=p.category, merchant_id=p.merchant_id,
                             attributes=dict(p.attributes)))
    return out


def shop(db: Session, *, buyer_id: str, instruction: str, max_amount: str | None, category: str | None,
         required_attributes: dict[str, str], device_id: str | None) -> dict:
    s = get_settings()
    instruction = instruction.strip()
    if not instruction:
        raise CulpaError("instruction is required")
    cap: Decimal | None = None
    if max_amount:
        try:
            cap = Decimal(max_amount)
        except InvalidOperation as exc:
            raise CulpaError("max_amount must be a number") from exc

    now = utcnow()
    constraints = {
        "max_amount": str(cap) if cap is not None else None,
        "currency": "USD",
        "max_quantity": 1,
        "allowed_merchants": None,
        "allowed_categories": [category] if category else None,
        "expires_at": iso(now + timedelta(hours=24)),
        "required_attributes": {k.strip().lower(): v.strip() for k, v in required_attributes.items()
                                if k.strip() and v.strip()},
    }
    mandate = Mandate(id=new_id("mdt"), buyer_id=buyer_id, text=instruction, constraints=constraints,
                      signature="", hash="", created_at=now, expires_at=now + timedelta(hours=24))
    payload = evidence_service.mandate_payload(mandate)
    mandate.hash = sha256_hex(payload)
    mandate.signature = sign(payload)
    db.add(mandate)
    db.flush()  # no ORM relationships: flush in foreign-key order explicitly

    candidates = _candidates(db, category, cap)
    if not candidates:
        raise CulpaError("no product in the store fits the mandate's category and budget")

    policy, model = "attribute_aware", ""
    llm = get_llm()
    if llm is not None:
        try:
            chosen_id, reasoning = llm.choose_product(instruction, candidates)
            policy, model = "llm", llm.fast_model
        except LLMUnavailable as exc:
            log.warning("agent_llm_unavailable_fallback", error=str(exc))
            chosen_id, reasoning = attribute_aware(instruction, candidates)
    else:
        chosen_id, reasoning = attribute_aware(instruction, candidates)

    trace = AgentTrace(id=new_id("trc"), mandate_id=mandate.id, policy=policy, model=model, instruction=instruction,
                       candidates=[c.__dict__ for c in candidates], chosen_product_id=chosen_id, reasoning=reasoning,
                       hash="", created_at=utcnow())
    trace.hash = sha256_hex(evidence_service.trace_payload(trace))
    db.add(trace)
    db.flush()

    product = db.get(Product, chosen_id)
    if product is None:
        raise NotFound(f"product {chosen_id} vanished")
    snapshot = ListingSnapshot(id=new_id("snp"), product_id=product.id, product_version=product.version,
                               title=product.title, price=product.price, attributes=dict(product.attributes),
                               hash="", captured_at=utcnow())
    snapshot.hash = sha256_hex(evidence_service.snapshot_payload(snapshot))
    db.add(snapshot)
    db.flush()

    order_id = new_id("ord")
    pp = get_paypal()
    simulated = not pp.configured
    item_name = f"{product.title} ({', '.join(f'{k} {v}' for k, v in product.attributes.items())})"
    if simulated:
        paypal_order_id = "SIM-" + order_id[4:].upper()
        approve_url = f"{s.public_web_url}/checkout/return?token={paypal_order_id}"
    else:
        created = create_order_via_toolkit(
            item_name=item_name, amount=product.price,
            return_url=f"{s.public_web_url}/checkout/return",
            cancel_url=f"{s.public_web_url}/agent?cancelled=1",
        )
        paypal_order_id = created["id"]
        approve_url = pp_orders.approve_link(created) or ""
        try:
            pp_orders.set_custom_id(pp, paypal_order_id, order_id)
        except PayPalError as exc:
            log.warning("paypal_custom_id_patch_failed", error=exc.message)

    order = Order(id=order_id, merchant_id=product.merchant_id, buyer_id=buyer_id,
                  buyer_device_hash=sha256_hex(device_id) if device_id else "", paypal_order_id=paypal_order_id,
                  simulated=simulated, status="created", amount=product.price, currency=product.currency,
                  quantity=1, category=product.category, product_id=product.id, mandate_id=mandate.id,
                  trace_id=trace.id, snapshot_id=snapshot.id, approve_url=approve_url, created_at=utcnow())
    db.add(order)
    audit_service.append(db, actor=f"agent:{policy}", action="agent.order_created",
                         data={"order_id": order.id, "paypal_order_id": paypal_order_id, "product_id": product.id,
                               "simulated": simulated})
    db.flush()
    return {
        "order_id": order.id,
        "paypal_order_id": paypal_order_id,
        "approve_url": approve_url,
        "simulated": simulated,
        "policy": policy,
        "reasoning": reasoning,
        "product": {"id": product.id, "title": product.title, "price": product.price,
                    "attributes": product.attributes, "image_url": product.image_url},
        "mandate": {"id": mandate.id, "hash": mandate.hash, "constraints": constraints},
        "candidates": len(candidates),
    }


def capture(db: Session, paypal_order_id: str) -> dict:
    order = db.execute(select(Order).where(Order.paypal_order_id == paypal_order_id)).scalar_one_or_none()
    if order is None:
        raise NotFound("unknown order token")
    if order.status != "captured":
        if order.simulated:
            order.capture_id = "SIMCAP-" + order.id[4:].upper()
        else:
            captured = pp_orders.capture_order(get_paypal(), paypal_order_id, idempotency_key("capture", order.id))
            order.capture_id = pp_orders.capture_id_of(captured)
        order.status = "captured"
        order.approved_at = utcnow()
        m = db.get(Mandate, order.mandate_id)
        t = db.get(AgentTrace, order.trace_id)
        sn = db.get(ListingSnapshot, order.snapshot_id)
        order.evidence = evidence_service.fingerprint(order, m, t, sn)
        order.evidence_root = order.evidence["root"]
        audit_service.append(db, actor="buyer", action="order.captured",
                             data={"order_id": order.id, "capture_id": order.capture_id,
                                   "evidence_root": order.evidence_root})
        db.flush()
    return order_dict(db, order)


def order_dict(db: Session, order: Order) -> dict:
    product = db.get(Product, order.product_id)
    snapshot = db.get(ListingSnapshot, order.snapshot_id)
    return {
        "id": order.id, "paypal_order_id": order.paypal_order_id, "capture_id": order.capture_id,
        "simulated": order.simulated, "status": order.status, "amount": order.amount, "currency": order.currency,
        "buyer_id": order.buyer_id, "merchant_id": order.merchant_id, "product_id": order.product_id,
        "product_title": product.title if product else "",
        "product_image_url": product.image_url if product else "",
        "snapshot_attributes": snapshot.attributes if snapshot else {},
        "current_attributes": product.attributes if product else {},
        "evidence": order.evidence, "evidence_root": order.evidence_root,
        "created_at": iso(order.created_at), "approved_at": iso(order.approved_at), "shipped_at": iso(order.shipped_at),
        "delivered": order.delivered, "delivered_attributes": order.delivered_attributes,
        "tracking_number": order.tracking_number, "approve_url": order.approve_url,
    }


def list_orders(db: Session, limit: int = 200) -> list[dict]:
    rows = db.execute(select(Order).order_by(Order.created_at.desc()).limit(limit)).scalars()
    return [order_dict(db, o) for o in rows]
