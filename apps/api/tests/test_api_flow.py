"""End-to-end through the HTTP API in simulated PayPal mode: agent buys -> capture -> ship -> dispute -> verdict -> settle."""

import pytest


def _buy(client, *, instruction, required, buyer="buyer_alice", max_amount="150"):
    r = client.post("/agent/shop", json={"buyer_id": buyer, "instruction": instruction, "max_amount": max_amount,
                                         "category": "shoes", "required_attributes": required,
                                         "device_id": f"dev-{buyer}"})
    assert r.status_code == 200, r.text
    shop = r.json()
    assert shop["simulated"] is True
    r = client.post("/checkout/capture", json={"token": shop["paypal_order_id"]})
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["status"] == "captured"
    assert len(order["evidence_root"]) == 64
    return shop, order


def _dispute(client, drain, order_id, claim, reason="ITEM_NOT_AS_DESCRIBED"):
    r = client.post("/cases/simulate", json={"order_id": order_id, "reason": reason, "claim_text": claim})
    assert r.status_code == 200, r.text
    case_id = r.json()["id"]
    drain()
    r = client.get(f"/cases/{case_id}")
    assert r.status_code == 200
    return r.json()


def test_health_and_status(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/readyz").status_code == 200
    s = client.get("/system/status").json()
    assert s["paypal"]["configured"] is False
    assert s["queue"]["mode"] == "inline"


def test_products_seeded(client):
    products = client.get("/store/products").json()
    assert {p["id"] for p in products} >= {"p_stride_uk9", "p_stride_us9"}


def test_f3_ambiguous_size_partial_refund(client, drain):
    shop, order = _buy(client, instruction="running shoes size 9 under $120", required={"size": "9"})
    assert shop["product"]["id"] == "p_stride_uk9"
    assert client.post(f"/orders/{order['id']}/ship").status_code == 200
    case = _dispute(client, drain, order["id"], "I wanted US 9, they sent UK 9.")
    assert case["fault_class"] == "F3", case["verdict"]
    assert case["recommended_action"] == "refund_partial"
    assert case["status"] == "awaiting_approval"

    r = client.post(f"/cases/{case['id']}/approve", json={})
    assert r.status_code == 200, r.text
    first = r.json()
    again = client.post(f"/cases/{case['id']}/approve", json={}).json()
    assert again["settlement_id"] == first["settlement_id"]  # idempotent approve
    drain()
    done = client.get(f"/cases/{case['id']}").json()
    assert done["status"] == "settled"
    assert done["settlement"]["simulated"] is True
    assert [a["action"] for a in done["audit"]][:2] == ["case.opened", "case.analyzed"]


def test_f4_listing_edit_after_purchase(client, drain):
    _, order = _buy(client, instruction="running shoes size US 9", required={"size": "US 9"}, buyer="buyer_bob")
    pid = order["product_id"]
    current = client.get(f"/store/products/{pid}").json()
    edited = {**current["attributes"], "material": "Synthetic"}
    assert client.put(f"/store/products/{pid}", json={"attributes": edited}).status_code == 200
    shipped = client.post(f"/orders/{order['id']}/ship").json()
    assert shipped["delivered_attributes"]["material"] == "Synthetic"
    case = _dispute(client, drain, order["id"], "Listing said mesh, I got synthetic.")
    assert case["fault_class"] == "F4"
    assert case["recommended_action"] == "refund_full"
    assert case["liability"] == {"merchant": order["amount"]}
    # restore the listing for other tests
    client.put(f"/store/products/{pid}", json={"attributes": current["attributes"]})


def test_f5_never_shipped(client, drain):
    _, order = _buy(client, instruction="running shoes size US 10", required={"size": "US 10"}, buyer="buyer_cara")
    case = _dispute(client, drain, order["id"], "It never arrived.", reason="ITEM_NOT_RECEIVED")
    assert case["fault_class"] == "F5"


def test_f6_friendly_fraud_contested(client, drain):
    _, order = _buy(client, instruction="running shoes size US 9", required={"size": "US 9"}, buyer="buyer_dan")
    client.post(f"/orders/{order['id']}/ship")
    case = _dispute(client, drain, order["id"], "My AI agent bought the wrong shoes, refund me.")
    assert case["fault_class"] == "F6"
    assert case["recommended_action"] == "contest"
    client.post(f"/cases/{case['id']}/approve", json={})
    drain()
    assert client.get(f"/cases/{case['id']}").json()["status"] == "settled"


def test_cases_list_and_jobs(client):
    cases = client.get("/cases").json()
    assert len(cases) >= 4
    stats = client.get("/jobs/stats").json()
    assert stats["audit_chain_ok"] is True
    assert client.get("/jobs/dead").json() == []


def test_validation_and_errors(client):
    assert client.post("/agent/shop", json={"buyer_id": "x", "instruction": ""}).status_code == 422
    assert client.get("/cases/case_missing").status_code == 404
    r = client.post("/checkout/capture", json={"token": "nope-token"})
    assert r.status_code == 404
    assert r.json()["error"] == "NotFound"


def test_cannot_dispute_uncaptured_order(client):
    r = client.post("/agent/shop", json={"buyer_id": "buyer_eve", "instruction": "cotton tee size L",
                                         "required_attributes": {"size": "L"}})
    order_id = r.json()["order_id"]
    r = client.post("/cases/simulate", json={"order_id": order_id, "reason": "OTHER", "claim_text": "x"})
    assert r.status_code == 409


@pytest.mark.parametrize("bad", ["refund_all", "pay_me"])
def test_approve_rejects_unknown_action(client, bad):
    assert client.post("/cases/whatever/approve", json={"action": bad}).status_code == 422


def test_analyst_sets_a_partial_refund_amount_and_note(client, drain):
    shop, order = _buy(client, instruction="running shoes size 9 under $120", required={"size": "9"}, buyer="buyer_pat")
    assert client.post(f"/orders/{order['id']}/ship").status_code == 200
    case = _dispute(client, drain, order["id"], "I wanted US 9, they sent UK 9.")
    assert case["verdict"]["reason"]["code"] == "AGT-03"  # every verdict explains itself

    too_much = client.post(f"/cases/{case['id']}/approve", json={"action": "refund_partial", "amount": case["amount"]})
    assert too_much.status_code == 400 and "less than" in too_much.json()["detail"]

    r = client.post(f"/cases/{case['id']}/approve",
                    json={"action": "refund_partial", "amount": "40", "note": "Goodwill: buyer keeps the shoes."})
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "40.00"
    audit = client.get(f"/cases/{case['id']}").json()["audit"]
    approved = next(a for a in audit if a["action"] == "settlement.approved")
    assert approved["data"]["note"] == "Goodwill: buyer keeps the shoes."
