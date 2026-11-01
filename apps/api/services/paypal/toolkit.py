"""PayPal Agent Toolkit adapter: the buyer agent creates its order through the official toolkit."""

from __future__ import annotations

import json
from decimal import Decimal

from core.config import get_settings
from core.errors import PayPalFinal, PayPalRetryable
from core.logging import get_logger
from core.resilience import CircuitOpen, breakers

log = get_logger(__name__)


def create_order_via_toolkit(*, item_name: str, amount: str, return_url: str, cancel_url: str) -> dict:
    """Runs the toolkit's `create_order` tool. Returns the raw PayPal order (id, status, links)."""
    from paypal_agent_toolkit.shared.api import PayPalAPI
    from paypal_agent_toolkit.shared.configuration import Context

    s = get_settings()
    breaker = breakers["paypal"]
    try:
        breaker.before_call()
    except CircuitOpen as exc:
        raise PayPalRetryable(str(exc)) from exc

    api = PayPalAPI(client_id=s.paypal_client_id, secret=s.paypal_client_secret,
                    context=Context(sandbox=s.paypal_env != "live", source="CULPA"))
    price = float(Decimal(amount))
    params = {
        "currency_code": "USD",
        "items": [{"name": item_name[:127], "quantity": 1, "item_cost": price, "item_total": price}],
        "return_url": return_url,
        "cancel_url": cancel_url,
    }
    try:
        raw = api.run("create_order", params)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is not None and status < 500:
            breaker.record_success()
            raise PayPalFinal(f"Agent Toolkit create_order failed: {exc}", status=status) from exc
        breaker.record_failure()
        raise PayPalRetryable(f"Agent Toolkit create_order failed: {exc}", status=status) from exc
    breaker.record_success()
    order = json.loads(raw) if isinstance(raw, str) else raw
    log.info("toolkit_order_created", paypal_order_id=order.get("id"))
    return order
