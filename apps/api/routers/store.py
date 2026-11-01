from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth.deps import require_analyst
from core.database import get_db
from schemas import ProductUpdate
from services import store_service

router = APIRouter(prefix="/store", tags=["store"])


@router.get("/products")
def products(db: Session = Depends(get_db)):
    return store_service.list_products(db)


@router.get("/products/{product_id}")
def product(product_id: str, db: Session = Depends(get_db)):
    return store_service.product_dict(store_service.get_product(db, product_id))


@router.get("/products/{product_id}/history")
def product_history(product_id: str, db: Session = Depends(get_db)):
    store_service.get_product(db, product_id)
    return store_service.history(db, product_id)


@router.put("/products/{product_id}")
def update_product(product_id: str, body: ProductUpdate, db: Session = Depends(get_db),
                   actor: str = Depends(require_analyst)):
    result = store_service.update_product(db, product_id, title=body.title, price=body.price,
                                          attributes=body.attributes, actor=f"merchant:{actor}")
    db.commit()
    return result
