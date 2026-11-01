"""PayPal Customer Disputes v1."""

from __future__ import annotations

import json

from services.paypal.client import PayPalClient


def get_dispute(pp: PayPalClient, dispute_id: str) -> dict:
    return pp.request("GET", f"/v1/customer/disputes/{dispute_id}")


def list_disputes(pp: PayPalClient, start_time: str | None = None, page_size: int = 50) -> list[dict]:
    params: dict = {"page_size": page_size}
    if start_time:
        params["start_time"] = start_time
    return pp.request("GET", "/v1/customer/disputes", params=params).get("items", [])


def accept_claim(pp: PayPalClient, dispute_id: str, note: str, idempotency_key: str) -> dict:
    return pp.request("POST", f"/v1/customer/disputes/{dispute_id}/accept-claim",
                      json={"note": note[:2000], "accept_claim_type": "REFUND"}, idempotency_key=idempotency_key)


def make_refund_offer(pp: PayPalClient, dispute_id: str, amount: str, currency: str, note: str,
                      idempotency_key: str) -> dict:
    return pp.request("POST", f"/v1/customer/disputes/{dispute_id}/make-offer", json={
        "note": note[:2000],
        "offer_amount": {"currency_code": currency, "value": amount},
        "offer_type": "REFUND",
    }, idempotency_key=idempotency_key)


def provide_evidence(pp: PayPalClient, dispute_id: str, notes: str, idempotency_key: str) -> dict:
    payload = {"evidences": [{"evidence_type": "OTHER", "notes": notes[:2000]}]}
    files = {"input": (None, json.dumps(payload), "application/json")}
    return pp.request("POST", f"/v1/customer/disputes/{dispute_id}/provide-evidence", files=files,
                      idempotency_key=idempotency_key)


def capture_id_of_dispute(dispute: dict) -> str | None:
    for tx in dispute.get("disputed_transactions", []) or []:
        if tx.get("seller_transaction_id"):
            return tx["seller_transaction_id"]
    return None


def claim_text_of_dispute(dispute: dict) -> str:
    parts = []
    for msg in dispute.get("messages", []) or []:
        if msg.get("posted_by") == "BUYER" and msg.get("content"):
            parts.append(msg["content"])
    info = dispute.get("extensions", {}).get("merchandize_dispute_properties", {}) or {}
    if info.get("issue_type"):
        parts.append(f"Issue type: {info['issue_type']}")
    return "\n".join(parts)
