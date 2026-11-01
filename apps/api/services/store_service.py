"""Demo merchant store: products, listing versions and fulfillment."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import InvalidState, NotFound, PayPalError
from core.ids import iso, new_id, utcnow
from core.logging import get_logger
from core.security import idempotency_key
from models import Order, Product, ProductVersion
from services import audit_service
from services.paypal import orders as pp_orders
from services.paypal.client import get_paypal

log = get_logger(__name__)
DEMO_MERCHANT = "mrc_demo_store"

DEMO_PRODUCTS = [
    {"id": "p_stride_uk9", "title": "Stride Running Shoe", "category": "shoes/running", "price": "95.00",
     "attributes": {"size": "UK 9", "color": "Black", "material": "Mesh"}},
    {"id": "p_stride_us9", "title": "Stride Running Shoe", "category": "shoes/running", "price": "99.00",
     "attributes": {"size": "US 9", "color": "Black", "material": "Mesh"}},
    {"id": "p_stride_us10", "title": "Stride Running Shoe", "category": "shoes/running", "price": "99.00",
     "attributes": {"size": "US 10", "color": "Black", "material": "Mesh"}},
    {"id": "p_harbor_jacket", "title": "Harbor Leather Jacket", "category": "apparel/jackets", "price": "180.00",
     "attributes": {"size": "M", "color": "Brown", "material": "Leather"}},
    {"id": "p_quiet_headphones", "title": "Quiet Wireless Headphones", "category": "electronics/audio",
     "price": "129.00", "attributes": {"color": "Black", "model": "QW-2"}},
    {"id": "p_everyday_tee", "title": "Everyday Cotton Tee", "category": "apparel/tops", "price": "19.00",
     "attributes": {"size": "L", "color": "White", "material": "Cotton"}},
]


def image_url_for(product_id: str) -> str:
    """Demo product images are static files served by the web app from public/products/."""
    return f"/products/{product_id}.svg"


def product_dict(p: Product) -> dict:
    return {"id": p.id, "merchant_id": p.merchant_id, "title": p.title, "category": p.category, "price": p.price,
            "currency": p.currency, "attributes": p.attributes, "image_url": p.image_url, "version": p.version,
            "updated_at": iso(p.updated_at)}


def seed(db: Session) -> int:
    if db.execute(select(Product.id).limit(1)).first():
        # Databases seeded before images existed: fill in the missing image paths.
        for p in db.execute(select(Product).where(Product.image_url == "")).scalars():
            p.image_url = image_url_for(p.id)
        db.flush()
        return 0
    now = utcnow()
    for spec in DEMO_PRODUCTS:
        db.add(Product(merchant_id=DEMO_MERCHANT, currency="USD", version=1, updated_at=now,
                       image_url=image_url_for(spec["id"]), **spec))
    db.flush()
    for spec in DEMO_PRODUCTS:
        db.add(ProductVersion(product_id=spec["id"], version=1, title=spec["title"], price=spec["price"],
                              attributes=spec["attributes"], captured_at=now))
    db.flush()
    return len(DEMO_PRODUCTS)


def list_products(db: Session) -> list[dict]:
    return [product_dict(p) for p in db.execute(select(Product).order_by(Product.category, Product.id)).scalars()]


def get_product(db: Session, product_id: str) -> Product:
    p = db.get(Product, product_id)
    if p is None:
        raise NotFound(f"product {product_id} not found")
    return p


def update_product(db: Session, product_id: str, *, title: str | None, price: str | None,
                   attributes: dict[str, str] | None, actor: str) -> dict:
    p = get_product(db, product_id)
    before = product_dict(p)
    if title is not None:
        p.title = title
    if price is not None:
        p.price = price
    if attributes is not None:
        p.attributes = {str(k): str(v) for k, v in attributes.items()}
    p.version += 1
    p.updated_at = utcnow()
    db.add(ProductVersion(product_id=p.id, version=p.version, title=p.title, price=p.price,
                          attributes=dict(p.attributes), captured_at=p.updated_at))
    audit_service.append(db, actor=actor, action="listing.updated",
                         data={"product_id": p.id, "before": before["attributes"], "after": p.attributes,
                               "version": p.version})
    db.flush()
    return product_dict(p)


def history(db: Session, product_id: str) -> list[dict]:
    rows = db.execute(select(ProductVersion).where(ProductVersion.product_id == product_id)
                      .order_by(ProductVersion.version)).scalars()
    return [{"version": v.version, "title": v.title, "price": v.price, "attributes": v.attributes,
             "captured_at": iso(v.captured_at)} for v in rows]


def ship(db: Session, order_id: str, actor: str) -> Order:
    """Ship whatever the listing says *now*. If the merchant edited the listing after purchase, the buyer gets the new version."""
    order = db.get(Order, order_id)
    if order is None:
        raise NotFound(f"order {order_id} not found")
    if order.status != "captured":
        raise InvalidState("only captured orders can be shipped")
    if order.shipped_at is not None:
        return order
    product = get_product(db, order.product_id)
    order.shipped_at = utcnow()
    order.delivered = True
    order.delivered_attributes = dict(product.attributes)
    order.tracking_number = "CULPA" + order.id[-10:].upper()
    audit_service.append(db, actor=actor, action="order.shipped",
                         data={"order_id": order.id, "tracking": order.tracking_number,
                               "delivered_attributes": order.delivered_attributes, "listing_version": product.version})
    pp = get_paypal()
    if pp.configured and not order.simulated and order.capture_id:
        try:
            pp_orders.add_tracking(pp, order.paypal_order_id, order.capture_id, order.tracking_number,
                                   idempotency_key("track", order.id))
        except PayPalError as exc:
            log.warning("paypal_tracking_failed", order_id=order.id, error=exc.message)
    db.flush()
    return order


def new_product_id() -> str:
    return new_id("p")
