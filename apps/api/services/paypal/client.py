"""PayPal REST client: cached OAuth token, idempotent POSTs, retries with backoff, and a circuit breaker."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from core.cache import local_cache
from core.config import Settings, get_settings
from core.errors import PayPalFinal, PayPalNotConfigured, PayPalRetryable
from core.logging import get_logger
from core.resilience import CircuitBreaker, CircuitOpen, breakers, retry

log = get_logger(__name__)
TOKEN_KEY = "paypal:token"


class PayPalClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None,
                 breaker: CircuitBreaker | None = None, sleep: Callable[[float], None] = time.sleep):
        self.settings = settings or get_settings()
        self.breaker = breaker or breakers["paypal"]
        self.sleep = sleep
        self.http = httpx.Client(base_url=self.settings.paypal_base_url, transport=transport,
                                 timeout=httpx.Timeout(10.0, connect=5.0))

    @property
    def configured(self) -> bool:
        return self.settings.paypal_configured

    def _token(self) -> str:
        cached = local_cache.get(TOKEN_KEY)
        if cached:
            return cached
        try:
            resp = self.http.post("/v1/oauth2/token", data={"grant_type": "client_credentials"},
                                  auth=(self.settings.paypal_client_id, self.settings.paypal_client_secret),
                                  headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise PayPalRetryable(f"token request failed: {exc}") from exc
        if resp.status_code >= 500:
            raise PayPalRetryable(f"token request failed: HTTP {resp.status_code}", status=resp.status_code)
        if resp.status_code >= 400:
            raise PayPalFinal("PayPal rejected the client credentials (check PAYPAL_CLIENT_ID / SECRET)",
                              status=resp.status_code)
        data = resp.json()
        local_cache.set(TOKEN_KEY, data["access_token"], max(60, int(data.get("expires_in", 3600)) - 60))
        return data["access_token"]

    def request(self, method: str, path: str, *, json: dict | list | None = None, files: dict | None = None,
                params: dict | None = None, idempotency_key: str | None = None, attempts: int = 3) -> dict[str, Any]:
        if not self.configured:
            raise PayPalNotConfigured("PayPal credentials are not configured")

        def once() -> dict[str, Any]:
            try:
                self.breaker.before_call()
            except CircuitOpen as exc:
                raise PayPalRetryable(str(exc)) from exc
            try:
                token = self._token()
            except (PayPalRetryable, PayPalFinal):
                self.breaker.record_failure()  # otherwise a half-open trial would stay open forever
                raise
            headers = {"Authorization": f"Bearer {token}", "Prefer": "return=representation"}
            if idempotency_key:
                headers["PayPal-Request-Id"] = idempotency_key
            try:
                resp = self.http.request(method, path, json=json, files=files, params=params, headers=headers)
            except httpx.HTTPError as exc:
                self.breaker.record_failure()
                raise PayPalRetryable(f"{method} {path} failed: {exc}") from exc

            debug_id = resp.headers.get("PayPal-Debug-Id")
            if resp.status_code == 401:
                local_cache.delete(TOKEN_KEY)
                self.breaker.release_trial()  # an expired token says nothing about PayPal's health
                raise PayPalRetryable("access token rejected; refreshing", status=401, debug_id=debug_id)
            if resp.status_code == 429 or resp.status_code >= 500:
                self.breaker.record_failure()
                raise PayPalRetryable(f"{method} {path}: HTTP {resp.status_code}", status=resp.status_code,
                                      debug_id=debug_id)
            self.breaker.record_success()
            body: dict[str, Any] = {}
            if resp.content:
                try:
                    body = resp.json()
                except ValueError:
                    body = {"raw": resp.text}
            if resp.status_code >= 400:
                name = body.get("name") or "UNKNOWN_ERROR"
                detail = "; ".join(d.get("issue", "") + (f" ({d.get('description')})" if d.get("description") else "")
                                   for d in body.get("details", []) if isinstance(d, dict))
                msg = f"PayPal {name}: {body.get('message', '')} {detail}".strip()
                log.warning("paypal_error", path=path, status=resp.status_code, name=name, paypal_debug_id=debug_id)
                raise PayPalFinal(msg, status=resp.status_code, name=name, debug_id=debug_id)
            log.info("paypal_ok", method=method, path=path, status=resp.status_code, paypal_debug_id=debug_id)
            return body

        return retry(once, attempts=attempts, retry_on=(PayPalRetryable,), sleep=self.sleep)


_client: PayPalClient | None = None


def get_paypal() -> PayPalClient:
    global _client
    if _client is None:
        _client = PayPalClient()
    return _client


def set_paypal(client: PayPalClient | None) -> None:
    """Tests swap in a client with a mock transport."""
    global _client
    _client = client
