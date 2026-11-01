"""PayPal Payments v2 refunds."""

from __future__ import annotations

from services.paypal.client import PayPalClient


def refund_capture(pp: PayPalClient, capture_id: str, *, amount: str | None, currency: str, note: str,
                   idempotency_key: str) -> dict:
    body: dict = {"note_to_payer": note[:255]}
    if amount is not None:
        body["amount"] = {"value": amount, "currency_code": currency}
    return pp.request("POST", f"/v2/payments/captures/{capture_id}/refund", json=body, idempotency_key=idempotency_key)
