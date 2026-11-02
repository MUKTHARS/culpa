from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.ids import utcnow


class LLMCache(Base):
    """Memoized language-model outputs keyed by a hash of model + prompt version + inputs."""

    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
