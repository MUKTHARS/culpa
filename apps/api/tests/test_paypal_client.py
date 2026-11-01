"""PayPal client behaviour against a mock transport: token caching, idempotent retries, error mapping, breaker."""

import httpx
import pytest

from core.cache import local_cache
from core.config import Settings
from core.errors import PayPalFinal, PayPalRetryable
from core.resilience import CircuitBreaker
from services.paypal import refunds
from services.paypal.client import TOKEN_KEY, PayPalClient


def _settings():
    return Settings(paypal_client_id="id", paypal_client_secret="secret", paypal_env="sandbox")


def _client(handler, breaker=None):
    local_cache.delete(TOKEN_KEY)
    return PayPalClient(settings=_settings(), transport=httpx.MockTransport(handler),
                        breaker=breaker or CircuitBreaker("test-paypal"), sleep=lambda _: None)


def test_retry_reuses_idempotency_key_then_succeeds():
    seen = []

    def handler(req: httpx.Request):
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        seen.append(req.headers.get("PayPal-Request-Id"))
        if len(seen) < 3:
            return httpx.Response(503, json={"name": "SERVICE_UNAVAILABLE"})
        return httpx.Response(201, json={"id": "REFUND-1", "status": "COMPLETED"})

    pp = _client(handler)
    out = refunds.refund_capture(pp, "CAP-1", amount="10.00", currency="USD", note="n", idempotency_key="key-1")
    assert out["id"] == "REFUND-1"
    assert seen == ["key-1", "key-1", "key-1"]


def test_business_error_is_final_with_debug_id():
    def handler(req: httpx.Request):
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(422, headers={"PayPal-Debug-Id": "dbg123"},
                              json={"name": "UNPROCESSABLE_ENTITY", "message": "nope",
                                    "details": [{"issue": "CAPTURE_FULLY_REFUNDED"}]})

    with pytest.raises(PayPalFinal) as exc:
        _client(handler).request("POST", "/v2/payments/captures/C/refund", json={})
    assert exc.value.debug_id == "dbg123"
    assert "CAPTURE_FULLY_REFUNDED" in exc.value.message


def test_expired_token_is_refreshed():
    tokens = iter(["old", "new"])
    calls = []

    def handler(req: httpx.Request):
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        calls.append(req.headers["Authorization"])
        if req.headers["Authorization"] == "Bearer old":
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": True})

    assert _client(handler).request("GET", "/v1/customer/disputes/D") == {"ok": True}
    assert calls == ["Bearer old", "Bearer new"]


def test_breaker_opens_after_repeated_failures():
    breaker = CircuitBreaker("t", threshold=2, window_s=60, cooldown_s=60)

    def handler(req: httpx.Request):
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(500)

    pp = _client(handler, breaker)
    with pytest.raises(PayPalRetryable):
        pp.request("GET", "/x", attempts=2)
    assert breaker.state == "open"
    with pytest.raises(PayPalRetryable, match="circuit is open"):
        pp.request("GET", "/x", attempts=1)
