"""PayPal Orders v2."""

from __future__ import annotations

from services.paypal.client import PayPalClient


def create_order(pp: PayPalClient, *, amount: str, currency: str, item_name: str, custom_id: str, return_url: str,
                 cancel_url: str, idempotency_key: str) -> dict:
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "custom_id": custom_id[:127],
            "description": item_name[:127],
            "amount": {"currency_code": currency, "value": amount,
                       "breakdown": {"item_total": {"currency_code": currency, "value": amount}}},
            "items": [{"name": item_name[:127], "quantity": "1",
                       "unit_amount": {"currency_code": currency, "value": amount}}],
        }],
        "payment_source": {"paypal": {"experience_context": {
            "return_url": return_url, "cancel_url": cancel_url,
            "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
        }}},
    }
    return pp.request("POST", "/v2/checkout/orders", json=payload, idempotency_key=idempotency_key)


def set_custom_id(pp: PayPalClient, order_id: str, custom_id: str) -> None:
    pp.request("PATCH", f"/v2/checkout/orders/{order_id}", json=[{
        "op": "add", "path": "/purchase_units/@reference_id=='default'/custom_id", "value": custom_id[:127],
    }])


def capture_order(pp: PayPalClient, order_id: str, idempotency_key: str) -> dict:
    return pp.request("POST", f"/v2/checkout/orders/{order_id}/capture", json={}, idempotency_key=idempotency_key)


def approve_link(order: dict) -> str | None:
    for link in order.get("links", []):
        if link.get("rel") in ("payer-action", "approve"):
            return link.get("href")
    return None


def capture_id_of(captured: dict) -> str | None:
    try:
        return captured["purchase_units"][0]["payments"]["captures"][0]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def add_tracking(pp: PayPalClient, order_id: str, capture_id: str, tracking_number: str, idempotency_key: str) -> dict:
    return pp.request("POST", f"/v2/checkout/orders/{order_id}/track", json={
        "capture_id": capture_id,
        "tracking_number": tracking_number,
        "carrier": "OTHER",
        "carrier_name_other": "Culpa Demo Carrier",
        "notify_payer": False,
    }, idempotency_key=idempotency_key)
