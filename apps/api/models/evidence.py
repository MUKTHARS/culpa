"""Evidence captured at checkout. Rows are written once and fingerprinted; they are never updated."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.ids import utcnow


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    buyer_id: Mapped[str] = mapped_column(String(80), index=True)
    text: Mapped[str] = mapped_column(Text)
    constraints: Mapped[dict] = mapped_column(JSON)
    signature: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(ForeignKey("mandates.id"), index=True)
    policy: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(60), default="")
    instruction: Mapped[str] = mapped_column(Text)
    candidates: Mapped[list] = mapped_column(JSON)
    chosen_product_id: Mapped[str] = mapped_column(String(40))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(40), index=True)
    product_version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[str] = mapped_column(String(20))
    attributes: Mapped[dict] = mapped_column(JSON)
    hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
