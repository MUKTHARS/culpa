from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.ids import utcnow

# Case lifecycle: open -> analyzing -> awaiting_approval | needs_review -> settling -> settled | offer_sent | settle_failed
CASE_STATUSES = ("open", "analyzing", "awaiting_approval", "needs_review", "settling", "settled", "offer_sent", "settle_failed")

# Settlement state machine. No other transitions are allowed.
SETTLEMENT_TRANSITIONS = {
    "approved": {"executing"},
    "executing": {"succeeded", "failed_retryable", "failed_final"},
    "failed_retryable": {"executing"},
    "succeeded": set(),
    "failed_final": set(),
}


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    paypal_dispute_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # paypal | simulator
    reason: Mapped[str] = mapped_column(String(60), default="")
    claim_text: Mapped[str] = mapped_column(Text, default="")
    buyer_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    amount: Mapped[str] = mapped_column(String(20), default="0.00")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    fault_class: Mapped[str | None] = mapped_column(String(4), nullable=True)
    fault_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    split: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    refund_amount: Mapped[str | None] = mapped_column(String(20), nullable=True)
    liability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("case_id", "action"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="approved")
    idempotency_key: Mapped[str] = mapped_column(String(64))
    amount: Mapped[str | None] = mapped_column(String(20), nullable=True)
    simulated: Mapped[bool] = mapped_column(default=False)
    paypal_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    approved_by: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
