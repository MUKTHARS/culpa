from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from core.auth.deps import bearer_token, rate_limit
from core.database import get_db
from core.errors import Unauthorized
from schemas import LoginRequest
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limit("login", 5))])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login(db, body.username, body.password)
    db.commit()
    if result is None:
        raise Unauthorized("wrong username or password")
    token, user = result
    return {"token": token, "username": user.username}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = bearer_token(authorization)
    if token:
        auth_service.logout(db, token)
        db.commit()
    return {"ok": True}


@router.get("/me")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    required = auth_service.login_required(db)
    token = bearer_token(authorization)
    user = auth_service.resolve(db, token) if token and required else None
    return {"login_required": required, "authenticated": user is not None or not required,
            "username": user.username if user else None}
