import json

from core.config import get_settings


def _event(event_id, capture_id, dispute_id="PP-D-1", event_type="CUSTOMER.DISPUTE.CREATED"):
    return {
        "id": event_id,
        "event_type": event_type,
        "resource": {
            "dispute_id": dispute_id,
            "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
            "dispute_amount": {"currency_code": "USD", "value": "99.00"},
            "disputed_transactions": [{"seller_transaction_id": capture_id}],
            "messages": [{"posted_by": "BUYER", "content": "Agent bought the wrong thing"}],
        },
    }


def test_webhook_creates_case_once(client, drain):
    r = client.post("/agent/shop", json={"buyer_id": "buyer_wh", "instruction": "running shoes size US 9",
                                         "required_attributes": {"size": "US 9"}})
    token = r.json()["paypal_order_id"]
    order = client.post("/checkout/capture", json={"token": token}).json()
    client.post(f"/orders/{order['id']}/ship")

    body = json.dumps(_event("WH-1", order["capture_id"]))
    assert client.post("/webhooks/paypal", content=body).json() == {"ok": True}
    dup = client.post("/webhooks/paypal", content=body).json()
    assert dup.get("duplicate") is True
    drain()

    cases = [c for c in client.get("/cases").json() if c["paypal_dispute_id"] == "PP-D-1"]
    assert len(cases) == 1
    assert cases[0]["source"] == "paypal"
    assert cases[0]["fault_class"] == "F6"

    # a second, different event about the same dispute does not create a second case
    client.post("/webhooks/paypal", content=json.dumps(_event("WH-2", order["capture_id"],
                                                              event_type="CUSTOMER.DISPUTE.UPDATED")))
    drain()
    assert len([c for c in client.get("/cases").json() if c["paypal_dispute_id"] == "PP-D-1"]) == 1


def test_webhook_for_unknown_transaction_needs_review(client, drain):
    client.post("/webhooks/paypal", content=json.dumps(_event("WH-3", "UNKNOWN-CAPTURE", dispute_id="PP-D-2")))
    drain()
    case = [c for c in client.get("/cases").json() if c["paypal_dispute_id"] == "PP-D-2"][0]
    assert case["status"] == "needs_review"


def test_webhook_rejected_when_unverified_not_allowed(client):
    s = get_settings()
    s.allow_unverified_webhooks = False
    try:
        r = client.post("/webhooks/paypal", content=json.dumps(_event("WH-4", "X")))
        assert r.status_code == 400
    finally:
        s.allow_unverified_webhooks = True


def test_webhook_bad_json_and_missing_id(client):
    assert client.post("/webhooks/paypal", content=b"not json").status_code == 400
    assert client.post("/webhooks/paypal", content=json.dumps({"event_type": "X"})).status_code == 400
