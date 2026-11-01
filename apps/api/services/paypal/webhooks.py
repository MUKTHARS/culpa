"""PayPal webhook signature verification via /v1/notifications/verify-webhook-signature."""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import urlparse

from core.config import get_settings
from core.errors import PayPalError
from core.ids import parse_iso, utcnow
from core.logging import get_logger
from services.paypal.client import get_paypal

log = get_logger(__name__)
MAX_AGE = timedelta(minutes=10)

REQUIRED_HEADERS = ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig",
                    "paypal-transmission-time")


def verify(headers: dict[str, str], body: bytes) -> bool:
    s = get_settings()
    h = {k.lower(): v for k, v in headers.items()}

    if not (s.paypal_configured and s.paypal_webhook_id):
        allowed = s.allow_unverified_webhooks and not s.is_production
        if allowed:
            log.warning("webhook_unverified_accepted", reason="PAYPAL_WEBHOOK_ID not set")
        return allowed

    if any(not h.get(k) for k in REQUIRED_HEADERS):
        log.warning("webhook_missing_headers")
        return False
    cert_host = urlparse(h["paypal-cert-url"]).hostname or ""
    if not (cert_host == "paypal.com" or cert_host.endswith(".paypal.com")):
        log.warning("webhook_bad_cert_host", host=cert_host)
        return False
    sent = parse_iso(h["paypal-transmission-time"])
    if sent is None or abs(utcnow() - sent) > MAX_AGE:
        log.warning("webhook_stale", transmission_time=h["paypal-transmission-time"])
        return False

    try:
        event = json.loads(body)
        result = get_paypal().request("POST", "/v1/notifications/verify-webhook-signature", json={
            "auth_algo": h["paypal-auth-algo"],
            "cert_url": h["paypal-cert-url"],
            "transmission_id": h["paypal-transmission-id"],
            "transmission_sig": h["paypal-transmission-sig"],
            "transmission_time": h["paypal-transmission-time"],
            "webhook_id": s.paypal_webhook_id,
            "webhook_event": event,
        })
    except (PayPalError, ValueError) as exc:
        log.warning("webhook_verify_call_failed", error=str(exc))
        return False
    return result.get("verification_status") == "SUCCESS"
