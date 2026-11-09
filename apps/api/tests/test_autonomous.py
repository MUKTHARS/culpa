"""Autonomous settlement and the reliability guarantees it depends on, since no analyst is watching."""

from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from core.cache import local_cache
from core.auth import deps
from core.config import Settings, get_settings
from core.database import SessionLocal
from core.errors import PayPalFinal, PayPalRetryable
from core.ids import utcnow
from core.resilience import CircuitBreaker
from models import Case, DeadLetter, Outbox, Settlement
from services import outbox_service, settlement_service
from services.paypal import client as pp_client
from services.paypal.client import TOKEN_KEY, PayPalClient
from tests.test_api_flow import _buy, _dispute
from workers import runner as runner_module


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    deps.limiter()._local.clear()
    yield
    deps.limiter()._local.clear()  # later test files make their own purchases


@pytest.fixture
def autonomous(monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_settle", True)


def _open_breaker():
    breaker = CircuitBreaker("test", threshold=1, cooldown_s=0.0)
    breaker.record_failure()
    assert breaker.state == "half_open"
    return breaker


def _pp(handler, breaker):
    local_cache.delete(TOKEN_KEY)
    return PayPalClient(settings=Settings(paypal_client_id="id", paypal_client_secret="s", paypal_env="sandbox"),
                        transport=httpx.MockTransport(handler), breaker=breaker, sleep=lambda _: None)


def test_failed_token_call_does_not_wedge_the_half_open_breaker():
    breaker = _open_breaker()
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json={"access_token": "t", "expires_in": 3600})

    pp = _pp(handler, breaker)
    with pytest.raises(PayPalRetryable):
        pp.request("GET", "/x", attempts=1)
    assert not breaker._half_open_trial
    breaker.before_call()  # a later trial is allowed


def test_expired_token_releases_the_half_open_trial():
    breaker = _open_breaker()

    def handler(req):
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(401, json={})

    with pytest.raises(PayPalRetryable):
        _pp(handler, breaker).request("GET", "/x", attempts=1)
    assert not breaker._half_open_trial


class FakePayPal:
    configured = True

    def __init__(self, outcome=None):
        self.outcome = outcome or {"id": "PP-1"}
        self.calls = []  # money-moving POSTs only
        self.capture = {"status": "COMPLETED", "amount": {"value": "20.00"}}
        self.dispute_status = "OPEN"

    def request(self, method, path, **kw):
        if method == "GET":
            return {"status": self.dispute_status} if "/disputes/" in path else self.capture
        self.calls.append((path, kw.get("idempotency_key")))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def paypal(monkeypatch):
    def install(outcome=None):
        fake = FakePayPal(outcome)
        monkeypatch.setattr(pp_client, "_client", fake)
        return fake

    return install


def _settlement(case_status="settling", status="approved", action="refund_full", dispute=None, amount="10.00"):
    from core.ids import new_id
    from models import AgentTrace, ListingSnapshot, Mandate, Order

    with SessionLocal() as db:
        now = utcnow()
        m = Mandate(id=new_id("mdt"), buyer_id="b", text="t", constraints={}, signature="", hash="", created_at=now)
        db.add(m)
        db.flush()
        t = AgentTrace(id=new_id("trc"), mandate_id=m.id, policy="p", instruction="t", candidates=[], chosen_product_id="x",
                       hash="", created_at=now)
        sn = ListingSnapshot(id=new_id("snp"), product_id="x", product_version=1, title="t", price="10.00", attributes={},
                             hash="", captured_at=now)
        db.add_all([t, sn])
        db.flush()
        o = Order(id=new_id("ord"), merchant_id="m", buyer_id="b", paypal_order_id=new_id("pp"), capture_id="CAP", amount="20.00",
                  simulated=False, status="captured", product_id="x", mandate_id=m.id, trace_id=t.id, snapshot_id=sn.id)
        db.add(o)
        db.flush()
        c = Case(id=new_id("case"), order_id=o.id, source="paypal", status=case_status, amount="20.00", paypal_dispute_id=dispute)
        db.add(c)
        db.flush()
        s = Settlement(id=new_id("stl"), case_id=c.id, action=action, status=status, idempotency_key=new_id("k"), amount=amount)
        db.add(s)
        db.commit()
        return s.id, c.id


def test_a_settlement_being_executed_is_not_executed_again(paypal):
    fake = paypal()
    sid, _ = _settlement(status="executing")
    with SessionLocal() as db:
        db.get(Settlement, sid).updated_at = utcnow()
        db.commit()
        settlement_service.execute(db, sid)
    assert fake.calls == []


def test_a_crashed_execution_is_retried_with_the_same_key_after_its_lease(paypal):
    fake = paypal()
    sid, cid = _settlement(status="executing")
    with SessionLocal() as db:
        s = db.get(Settlement, sid)
        s.updated_at = utcnow() - timedelta(minutes=6)
        key = s.idempotency_key
        db.commit()
        settlement_service.execute(db, sid)
        assert db.get(Settlement, sid).status == "succeeded"
    assert [c[1] for c in fake.calls] == [key]


def test_partial_refund_on_a_real_dispute_is_an_offer_not_settled(paypal):
    fake = paypal()
    sid, cid = _settlement(action="refund_partial", dispute="PP-D-" + utcnow().isoformat())
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
        assert db.get(Case, cid).status == "offer_sent"
    assert fake.calls[0][0].endswith("/make-offer")


def test_exhausted_retries_fail_the_case_and_replay_recovers_it(paypal, monkeypatch):
    fake = paypal(PayPalRetryable("PayPal down"))
    monkeypatch.setitem(outbox_service.TOPIC_RETRY, "settlement.requested", (1, 0.0, 0.0))
    sid, cid = _settlement()
    with SessionLocal() as db:
        oid = outbox_service.add(db, "settlement.requested", {"settlement_id": sid}).id
        db.commit()
    runner_module._run_job(oid)
    with SessionLocal() as db:
        assert db.get(Outbox, oid).status == "dead"
        assert db.get(Case, cid).status == "settle_failed"
        assert db.get(Settlement, sid).status == "failed_retryable"
        dead_id = db.query(DeadLetter).filter_by(outbox_id=oid).one().id
        new_oid = outbox_service.replay_dead(db, dead_id).id
        db.commit()
    fake.outcome = {"id": "PP-2"}
    runner_module._run_job(new_oid)
    with SessionLocal() as db:
        assert db.get(Case, cid).status == "settled"


def test_paypal_rejection_goes_to_settle_failed(paypal):
    paypal(PayPalFinal("DISPUTE_RESOLVED"))
    sid, cid = _settlement()
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
        assert db.get(Case, cid).status == "settle_failed"


def test_confident_verdict_settles_with_no_analyst(client, drain, autonomous):
    _, order = _buy(client, instruction="running shoes size 9 under $120", required={"size": "9"}, buyer="buyer_auto1")
    client.post(f"/orders/{order['id']}/ship")
    case = _dispute(client, drain, order["id"], "I wanted US 9, they sent UK 9.")
    assert case["confidence"] >= 0.8 and case["status"] == "settled"
    assert case["settlement"]["approved_by"] == "auto-policy" and case["settlement"]["action"] == "refund_partial"
    assert case["resolution_strategy"] == "autonomous" and case["paypal_result"] == "simulated"
    row = next(r for r in client.get("/cases").json() if r["id"] == case["id"])
    assert row["paypal_result"] == "simulated"


def test_low_confidence_is_held_for_a_human(autonomous):
    with SessionLocal() as db:
        case = SimpleNamespace(confidence=0.79, recommended_action="refund_full", status="awaiting_approval", id="x", order_id=None, verdict=None, fault_class=None)
        assert settlement_service.execute_autonomous_paypal_resolution(db, case) == "HELD_FOR_HUMAN_REVIEW"
        unsafe = SimpleNamespace(confidence=0.95, recommended_action="review", status="awaiting_approval", id="x", order_id=None, verdict=None, fault_class=None)
        assert settlement_service.execute_autonomous_paypal_resolution(db, unsafe) == "HELD_FOR_HUMAN_REVIEW"


def test_autonomy_cannot_be_lowered_below_the_floor(autonomous, monkeypatch):
    monkeypatch.setattr(get_settings(), "confidence_threshold", 0.5)
    with SessionLocal() as db:
        case = SimpleNamespace(confidence=0.7, recommended_action="contest", status="awaiting_approval", id="x", order_id=None, verdict=None, fault_class=None)
        assert settlement_service.execute_autonomous_paypal_resolution(db, case) == "HELD_FOR_HUMAN_REVIEW"


def test_autonomy_off_changes_nothing(client, drain):
    _, order = _buy(client, instruction="running shoes size 9 under $120", required={"size": "9"}, buyer="buyer_auto2")
    client.post(f"/orders/{order['id']}/ship")
    case = _dispute(client, drain, order["id"], "I wanted US 9, they sent UK 9.")
    assert case["status"] == "awaiting_approval" and case["settlement"] is None
    assert case["resolution_strategy"] == "human"


def test_rate_limit_ignores_a_forged_forwarded_address(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    req = SimpleNamespace(headers={"x-forwarded-for": "6.6.6.6, 9.9.9.9"}, client=SimpleNamespace(host="10.0.0.1"))
    assert deps.client_ip(req) == "9.9.9.9"
    monkeypatch.setattr(get_settings(), "app_env", "development")
    assert deps.client_ip(req) == "10.0.0.1"


# --- PayPal is re-read before money moves ---

@pytest.mark.parametrize("state", ["REFUNDED", "PARTIALLY_REFUNDED", "PENDING", "DECLINED"])
def test_no_refund_unless_paypal_says_the_payment_is_intact(paypal, state):
    fake = paypal()
    fake.capture["status"] = state
    sid, cid = _settlement()
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
        assert db.get(Case, cid).status == "settle_failed"
        assert "No money moved" in db.get(Settlement, sid).error
    assert fake.calls == []


def test_refund_larger_than_the_capture_is_refused(paypal):
    fake = paypal()
    fake.capture["amount"]["value"] = "5.00"
    sid, _ = _settlement(action="refund_partial", amount="10.00")
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
    assert fake.calls == []


def test_retry_after_a_crash_reuses_the_key_even_though_the_capture_is_now_refunded(paypal):
    fake = paypal()
    fake.capture["status"] = "REFUNDED"  # our own first attempt did this before the crash
    sid, cid = _settlement(status="failed_retryable")
    with SessionLocal() as db:
        db.get(Settlement, sid).attempts = 1
        db.commit()
        settlement_service.execute(db, sid)
        assert db.get(Case, cid).status == "settled"
    assert len(fake.calls) == 1


@pytest.mark.parametrize("state", ["RESOLVED", "UNDER_REVIEW", "WAITING_FOR_BUYER_RESPONSE"])
def test_a_closed_paypal_dispute_is_not_answered(paypal, state):
    fake = paypal()
    fake.dispute_status = state
    sid, _ = _settlement(dispute=f"D-{state}-{utcnow().timestamp()}")
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
    assert fake.calls == []


# --- what automation does with realistic disputes, through the real API and engine ---

def _order(client, buyer, ship=True):
    _, order = _buy(client, instruction="running shoes size US 9", required={"size": "US 9"}, buyer=buyer)
    if ship:
        assert client.post(f"/orders/{order['id']}/ship").status_code == 200
    return order


def _expect(case, status, action, by="auto-policy"):
    assert case["status"] == status, case["verdict"]["reason"]
    assert (case["settlement"] or {}).get("action") == action
    if action:
        assert case["settlement"]["approved_by"] == by


def test_never_shipped_and_never_arrived_is_refunded(client, drain, autonomous):
    order = _order(client, "rw_inr", ship=False)
    _expect(_dispute(client, drain, order["id"], "It never arrived.", reason="ITEM_NOT_RECEIVED"), "settled", "refund_full")


@pytest.mark.parametrize("claim", ["I expected size US 9, but received UK 9.", "My AI agent bought the wrong item.",
                                   "The item is scratched."])
def test_buyer_describes_an_item_that_was_never_delivered_is_held(client, drain, autonomous, claim):
    order = _order(client, f"rw_hold_{abs(hash(claim))}", ship=False)
    case = _dispute(client, drain, order["id"], claim)
    _expect(case, "needs_review", None)
    assert case["resolution_strategy"] == "human"


@pytest.mark.parametrize("claim,reason", [
    ("My AI agent bought the wrong item, I want a refund.", "ITEM_NOT_AS_DESCRIBED"),
    ("It never arrived.", "ITEM_NOT_RECEIVED"),
    ("I changed my mind about this order.", "OTHER"),
])
def test_claims_the_record_contradicts_are_contested_without_refund(client, drain, autonomous, claim, reason):
    order = _order(client, f"rw_f6_{abs(hash(claim))}")
    case = _dispute(client, drain, order["id"], claim, reason=reason)
    _expect(case, "settled", "contest")
    assert case["settlement"]["amount"] is None


@pytest.mark.parametrize("claim", ["It arrived broken.", "This is a counterfeit.", "The box was missing parts.",
                                   "I was charged twice.", "My refund was never processed."])
def test_claims_records_cannot_prove_wait_for_a_person(client, drain, autonomous, claim):
    order = _order(client, f"rw_ev_{abs(hash(claim))}")
    case = _dispute(client, drain, order["id"], claim, reason="OTHER")
    _expect(case, "needs_review", None)
    assert case["resolution_strategy"] == "human" and case["split"]["buyer"] == 0


def test_listing_changed_before_shipping_refunds_from_the_merchant(client, drain, autonomous):
    order = _order(client, "rw_f4", ship=False)
    pid = order["product_id"]
    original = next(p for p in client.get("/store/products").json() if p["id"] == pid)["attributes"]
    client.put(f"/store/products/{pid}", json={"attributes": {**original, "material": "Synthetic"}})
    client.post(f"/orders/{order['id']}/ship")
    case = _dispute(client, drain, order["id"], "The listing said mesh, I received synthetic.")
    client.put(f"/store/products/{pid}", json={"attributes": original})
    _expect(case, "settled", "refund_full")
    assert case["split"]["merchant"] == 1.0


def test_an_order_can_only_be_disputed_once(client, drain, autonomous):
    order = _order(client, "rw_once", ship=False)
    _dispute(client, drain, order["id"], "It never arrived.", reason="ITEM_NOT_RECEIVED")
    again = client.post("/cases/simulate", json={"order_id": order["id"], "reason": "ITEM_NOT_RECEIVED", "claim_text": "Again."})
    assert again.status_code == 409
    assert next(o for o in client.get("/orders").json() if o["id"] == order["id"])["case_id"]


def test_paypal_dispute_on_an_order_settled_under_another_case_is_held(client, drain, autonomous):
    order = _order(client, "rw_second", ship=False)
    first = _dispute(client, drain, order["id"], "It never arrived.", reason="ITEM_NOT_RECEIVED")
    with SessionLocal() as db:  # a real PayPal dispute arrives later for the same payment
        from services import case_service
        real = case_service.create_from_dispute(db, {"dispute_id": "PP-AFTER-" + first["id"], "reason": "ITEM_NOT_RECEIVED"})
        real.order_id, real.buyer_id = order["id"], order["buyer_id"]
        db.commit()
    drain()
    second = client.get(f"/cases/{real.id}").json()
    assert second["status"] == "needs_review" and second["settlement"] is None and "already_settled" in second["flags"]


def test_payment_refunded_before_this_case_reads_as_done_not_failed(client, paypal):
    fake = paypal()
    fake.capture["status"] = "REFUNDED"
    sid, cid = _settlement()
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
    case = client.get(f"/cases/{cid}").json()
    assert case["status"] == "already_refunded" and case["paypal_result"] == "already_refunded"
    assert case["settlement"]["error"] is None and fake.calls == []


def test_paypal_refusal_is_explained_and_still_counts_as_failed(client, paypal):
    paypal(PayPalFinal("PayPal UNPROCESSABLE_ENTITY: REFUND_NOT_ALLOWED (Capture cannot be refunded.)"))
    sid, cid = _settlement()
    with SessionLocal() as db:
        settlement_service.execute(db, sid)
    case = client.get(f"/cases/{cid}").json()
    assert case["status"] == "settle_failed" and case["paypal_result"] == "failed"
    assert "No money moved" in case["settlement"]["error"]
