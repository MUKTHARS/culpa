"""Culpa API: FastAPI app factory, middleware, error mapping and router registration."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.database import SessionLocal, init_db
from core.errors import CulpaError
from core.logging import configure_logging, correlation_id, get_logger
from routers import agent, auth, bench, cases, health, jobs, store, webhooks
from services import auth_service, store_service

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    init_db()
    with SessionLocal() as db:
        seeded = store_service.seed(db)
        auth_service.ensure_seed_user(db)
        db.commit()
    log.info("api_started", seeded_products=seeded, paypal=s.paypal_configured, llm=s.llm_configured)
    worker = None
    if s.run_workers_in_process:
        from workers.runner import start_background

        worker = start_background()
    yield
    if worker is not None:
        worker[1].set()
        worker[0].join(timeout=5)


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Culpa API", version="1.0.0", lifespan=lifespan,
                  docs_url=None if s.is_production else "/docs", redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.web_origin.split(",") if o.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-Id"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex[:16]
        correlation_id.set(cid)
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = cid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        if s.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(CulpaError)
    async def culpa_error(_: Request, exc: CulpaError):
        return JSONResponse({"error": type(exc).__name__, "detail": exc.message}, status_code=exc.status_code)

    for r in (health.router, auth.router, webhooks.router, store.router, agent.router, cases.router, jobs.router, bench.router):
        app.include_router(r)
    return app


app = create_app()
