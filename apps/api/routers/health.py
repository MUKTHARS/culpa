from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core import queue
from core.config import get_settings
from core.database import ping
from core.redis_client import get_redis
from core.resilience import breakers
from services.llm_service import get_llm

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/readyz")
def readyz():
    db_ok = ping()
    body = {"database": db_ok, "redis": get_redis() is not None, "queue_mode": queue.queue_mode()}
    return JSONResponse(body, status_code=200 if db_ok else 503)


@router.get("/system/status")
def system_status():
    s = get_settings()
    llm = get_llm()
    return {
        "env": s.app_env,
        "paypal": {"configured": s.paypal_configured, "env": s.paypal_env,
                   "webhook_verification": bool(s.paypal_webhook_id), "breaker": breakers["paypal"].state},
        "llm": {"configured": s.llm_configured, "judge_model": s.llm_judge_model, "fast_model": s.llm_fast_model,
                "breaker": breakers["claude"].state, "unavailable_reason": llm.unavailable_reason if llm else None},
        "queue": {"mode": queue.queue_mode(), "depth": queue.depth()},
        "auto_settle": s.auto_settle,
        "confidence_threshold": s.confidence_threshold,
        "analyst_login_configured": bool(s.analyst_username and s.analyst_password),
    }
