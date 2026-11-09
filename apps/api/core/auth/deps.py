"""FastAPI dependencies for analyst access and rate limiting."""

from fastapi import Header, Request

from core.config import get_settings
from core.database import SessionLocal
from core.errors import RateLimited, Unauthorized
from core.redis_client import get_redis
from core.security import SlidingWindowLimiter

_limiter: SlidingWindowLimiter | None = None


def limiter() -> SlidingWindowLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter(get_redis())
    return _limiter


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def require_analyst(authorization: str | None = Header(default=None)) -> str:
    """Analyst endpoints need a login session (Authorization: Bearer <token>).

    Local development without an analyst account configured stays open, so the console works out of the box.
    """
    from services import auth_service

    with SessionLocal() as db:
        if not auth_service.login_required(db):
            if get_settings().is_production:
                raise Unauthorized("no analyst account configured; set ANALYST_USERNAME and ANALYST_PASSWORD")
            return "dev-analyst"
        token = bearer_token(authorization)
        user = auth_service.resolve(db, token) if token else None
        if user is None:
            raise Unauthorized("please log in")
        return user.username


def client_ip(request: Request) -> str:
    """The caller's address for rate limiting. Behind the production proxy only the last X-Forwarded-For hop is
    written by infrastructure; anything before it is whatever the client chose to send."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if get_settings().is_production and forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window_s: int = 60):
    def dependency(request: Request) -> None:
        ip = client_ip(request)
        if not limiter().allow(f"culpa:rl:{name}:{ip}", limit, window_s):
            raise RateLimited(f"rate limit exceeded for {name}")

    return dependency
