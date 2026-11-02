"""GeminiLLM against a fake Gemini client: request shape, parsing, and failure handling."""

import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from engine.llm import GeminiLLM, LLMUnavailable
from engine.types import Candidate

CATALOG = [Candidate(id="buds", title="Pocket Wireless Earbuds", price="79.00", attributes={"color": "Black"})]


def _response(text: str | None, blocked: bool = False):
    candidates = [] if blocked else [SimpleNamespace(finish_reason="STOP")]
    feedback = SimpleNamespace(block_reason="SAFETY" if blocked else None)
    return SimpleNamespace(text=text, candidates=candidates, prompt_feedback=feedback)


def _error(code: int, message: str, status: str = "INVALID_ARGUMENT"):
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": message, "status": status}})


class FakeModels:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _llm(*outcomes) -> tuple[GeminiLLM, FakeModels]:
    models = FakeModels(*outcomes)
    llm = GeminiLLM(api_key="k", judge_model="judge-m", fast_model="fast-m", client=SimpleNamespace(models=models))
    return llm, models


def test_request_uses_json_schema_and_fixed_temperature():
    llm, fake = _llm(_response(json.dumps({"product_id": "buds", "reasoning": "closest match"})))
    assert llm.choose_product("earphones", CATALOG) == ("buds", "closest match")
    call = fake.calls[0]
    assert call["model"] == "fast-m"
    assert call["config"].temperature == 0.0
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema["required"] == ["product_id", "reasoning"]
    assert call["config"].system_instruction


def test_rejected_key_is_remembered_and_later_calls_fail_fast():
    llm, fake = _llm(_error(400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT"))
    with pytest.raises(LLMUnavailable, match="key was rejected"):
        llm.choose_product("earphones", CATALOG, use_cache=False)
    with pytest.raises(LLMUnavailable, match="key was rejected"):
        llm.choose_product("earphones", CATALOG, use_cache=False)
    assert len(fake.calls) == 1


def test_quota_and_busy_errors_are_temporary():
    llm, _ = _llm(_error(429, "You exceeded your current quota", "RESOURCE_EXHAUSTED"),
                  _error(503, "This model is currently experiencing high demand.", "UNAVAILABLE"))
    with pytest.raises(LLMUnavailable, match="quota"):
        llm.clarify("shoes size 9", "I wanted US 9", ["size"])
    with pytest.raises(LLMUnavailable, match="unavailable right now"):
        llm.clarify("shoes size 9", "I wanted US 8", ["size"])
    assert llm.unavailable_reason is None


def test_model_that_rejects_thinking_level_is_retried_without_it():
    judged = {"consistent_with_evidence": False, "claim_type": "not_received", "contradictions": ["delivered"],
              "confidence": 1.4}
    llm, fake = _llm(_error(400, "Thinking level is not supported for this model."), _response(json.dumps(judged)))
    out = llm.judge_claim("It never arrived.", {"delivered": True})
    assert out["confidence"] == 1.0  # clamped
    assert fake.calls[0]["config"].thinking_config is not None
    assert fake.calls[1]["config"].thinking_config is None


def test_blocked_and_out_of_catalog_answers_are_unavailable():
    llm, _ = _llm(_response(None, blocked=True))
    with pytest.raises(LLMUnavailable, match="declined"):
        llm.clarify("shoes size 9", "I wanted US 9", ["size"])
    llm, _ = _llm(_response(json.dumps({"product_id": "not-in-catalog", "reasoning": "x"})))
    with pytest.raises(LLMUnavailable, match="outside the catalog"):
        llm.choose_product("earphones", CATALOG)
