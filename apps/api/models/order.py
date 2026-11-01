from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.ids import utcnow


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(40), index=True)
    buyer_id: Mapped[str] = mapped_column(String(80), index=True)
    buyer_device_hash: Mapped[str] = mapped_column(String(64), default="")
    paypal_order_id: Mapped[str] = mapped_column(String(64), unique=True)
    capture_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="created")  # created | captured | cancelled
    amount: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(120), default="")
    product_id: Mapped[str] = mapped_column(String(40))
    mandate_id: Mapped[str] = mapped_column(ForeignKey("mandates.id"))
    trace_id: Mapped[str] = mapped_column(ForeignKey("agent_traces.id"))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("listing_snapshots.id"))
    approve_url: Mapped[str] = mapped_column(String(500), default="")
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_root: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
