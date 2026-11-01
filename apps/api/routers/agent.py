from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth.deps import rate_limit, require_analyst
from core.database import get_db
from schemas import CaptureRequest, ShopRequest
from services import agent_service, store_service

router = APIRouter(tags=["agent"])


@router.post("/agent/shop", dependencies=[Depends(rate_limit("agent_shop", 20))])
def shop(body: ShopRequest, db: Session = Depends(get_db)):
    result = agent_service.shop(db, buyer_id=body.buyer_id, instruction=body.instruction, max_amount=body.max_amount,
                                category=body.category, required_attributes=body.required_attributes,
                                device_id=body.device_id)
    db.commit()
    return result


@router.post("/checkout/capture", dependencies=[Depends(rate_limit("capture", 30))])
def capture(body: CaptureRequest, db: Session = Depends(get_db)):
    result = agent_service.capture(db, body.token)
    db.commit()
    return result


@router.get("/orders")
def orders(db: Session = Depends(get_db), _: str = Depends(require_analyst)):
    return agent_service.list_orders(db)


@router.post("/orders/{order_id}/ship")
def ship(order_id: str, db: Session = Depends(get_db), actor: str = Depends(require_analyst)):
    order = store_service.ship(db, order_id, actor=f"merchant:{actor}")
    db.commit()
    return agent_service.order_dict(db, order)
