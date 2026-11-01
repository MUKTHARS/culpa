"""Evidence fingerprints: hashes of the mandate, agent trace and listing snapshot, rolled into a Merkle root."""

from __future__ import annotations

from core.ids import iso, utcnow
from core.security import sha256_hex
from engine.dsa import merge_timelines
from engine.graph import merkle_proof, merkle_root
from models import AgentTrace, Case, ListingSnapshot, Mandate, Order


def mandate_payload(m: Mandate) -> dict:
    return {"buyer_id": m.buyer_id, "text": m.text, "constraints": m.constraints, "created_at": iso(m.created_at)}


def trace_payload(t: AgentTrace) -> dict:
    return {"mandate_id": t.mandate_id, "policy": t.policy, "model": t.model, "instruction": t.instruction,
            "candidates": t.candidates, "chosen_product_id": t.chosen_product_id, "reasoning": t.reasoning,
            "created_at": iso(t.created_at)}


def snapshot_payload(s: ListingSnapshot) -> dict:
    return {"product_id": s.product_id, "product_version": s.product_version, "title": s.title, "price": s.price,
            "attributes": s.attributes, "captured_at": iso(s.captured_at)}


def leaves(m: Mandate, t: AgentTrace, s: ListingSnapshot) -> list[str]:
    return [sha256_hex(mandate_payload(m)), sha256_hex(trace_payload(t)), sha256_hex(snapshot_payload(s))]


def fingerprint(order: Order, m: Mandate, t: AgentTrace, s: ListingSnapshot) -> dict:
    lv = leaves(m, t, s)
    root = merkle_root(lv)
    return {
        "evidence_id": order.id,
        "mandate_hash": lv[0],
        "trace_hash": lv[1],
        "snapshot_hash": lv[2],
        "root": root,
        "proofs": {name: merkle_proof(lv, i) for i, name in enumerate(("mandate", "trace", "snapshot"))},
        "captured_at": iso(utcnow()),
    }


def recompute_root(m: Mandate, t: AgentTrace, s: ListingSnapshot) -> str:
    return merkle_root(leaves(m, t, s))


def timeline(order: Order | None, case: Case | None, settlement_events: list[tuple[str, str]]) -> list[dict]:
    order_events: list[tuple[str, str]] = []
    if order is not None:
        for when, label in ((order.created_at, "Agent created the PayPal order"),
                            (order.approved_at, "Buyer approved; payment captured; evidence fingerprinted"),
                            (order.shipped_at, f"Shipped (tracking {order.tracking_number})")):
            if when is not None:
                order_events.append((iso(when), label))
    case_events: list[tuple[str, str]] = []
    if case is not None:
        case_events.append((iso(case.created_at), f"Dispute opened ({case.source}): {case.reason}"))
        if case.analyzed_at is not None:
            case_events.append((iso(case.analyzed_at), f"Culpa verdict: {case.fault_class or 'undetermined'}"))
    merged = merge_timelines(sorted(order_events), sorted(case_events))
    merged = merge_timelines(merged, sorted(settlement_events))
    return [{"at": at, "event": label} for at, label in merged]
