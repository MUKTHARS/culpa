"""Builds the engine's Claude client with a memo cache backed by an in-process LRU and the llm_cache table."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from core.cache import LRUCache
from core.config import get_settings
from core.database import SessionLocal
from core.logging import get_logger
from core.resilience import breakers
from engine.llm import ClaudeLLM
from models import LLMCache

log = get_logger(__name__)


class DBMemo:
    def __init__(self):
        self.lru = LRUCache(capacity=1024)

    def get(self, key: str) -> dict | None:
        hit = self.lru.get(key)
        if hit is not None:
            return hit
        with SessionLocal() as db:
            row = db.get(LLMCache, key)
            if row is None:
                return None
            self.lru.set(key, row.value)
            return row.value

    def set(self, key: str, value: dict) -> None:
        self.lru.set(key, value)
        with SessionLocal() as db:
            try:
                row = db.get(LLMCache, key)
                if row is None:
                    db.add(LLMCache(key=key, value=value))
                else:
                    row.value = value
                db.commit()
            except IntegrityError:
                db.rollback()
            except Exception as exc:
                db.rollback()
                log.warning("llm_cache_write_failed", error=str(exc))


_llm: ClaudeLLM | None = None


def get_llm() -> ClaudeLLM | None:
    global _llm
    s = get_settings()
    if not s.llm_configured:
        return None
    if _llm is None:
        _llm = ClaudeLLM(api_key=s.anthropic_api_key, judge_model=s.llm_judge_model, fast_model=s.llm_fast_model,
                         timeout_s=s.llm_timeout_s, memo=DBMemo(), breaker=breakers["claude"])
    return _llm
