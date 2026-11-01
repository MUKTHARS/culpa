"""PayPal webhooks: verify, dedup, store, enqueue, return 200 fast. All slow work happens in workers."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError

from core.auth.deps import rate_limit
from core.database import SessionLocal
from core.logging import get_logger
from models import WebhookEvent
from services import outbox_service
from services.paypal import webhooks as pp_webhooks

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger(__name__)
security_log = get_logger("security")

DISPUTE_EVENTS = {"CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.UPDATED"}


def _process(headers: dict[str, str], body: bytes, ip: str | None) -> dict:
    if not pp_webhooks.verify(headers, body):
        security_log.warning("webhook_signature_failed", ip=ip)
        raise HTTPException(status_code=400, detail="webhook signature verification failed")
    try:
        event = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON") from exc
    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event has no id")

    with SessionLocal() as db:
        row = WebhookEvent(paypal_event_id=event_id, event_type=event.get("event_type", ""), payload=event,
                           verified=True)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            log.info("webhook_duplicate", event_id=event_id)
            return {"ok": True, "duplicate": True}
        if row.event_type in DISPUTE_EVENTS:
            outbox_service.add(db, "dispute.received", {"event_id": event_id})
        db.commit()
    log.info("webhook_stored", event_id=event_id, event_type=event.get("event_type"))
    return {"ok": True}


@router.post("/paypal", dependencies=[Depends(rate_limit("webhook", 600))])
async def paypal_webhook(request: Request):
    body = await request.body()
    ip = request.client.host if request.client else None
    return await run_in_threadpool(_process, dict(request.headers), body, ip)
