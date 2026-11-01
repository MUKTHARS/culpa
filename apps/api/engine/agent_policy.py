"""Buyer-agent decision policies. The live agent and the replay check call the same functions.

- attribute_aware: deterministic heuristic, matches instruction words to product title and attributes.
- price_first:     a deliberately flawed agent that ignores attributes and buys the cheapest item
                   (used by the benchmark to model agent reasoning errors).
- llm:             Claude picks the product (needs an LLM client).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from engine.attributes import tokens
from engine.types import Candidate

_BUDGET = re.compile(r"(?:under|below|max(?:imum)?|less than|up to|<=?)\s*\$?\s*(\d+(?:\.\d{1,2})?)", re.I)


def parse_budget(instruction: str) -> Decimal | None:
    m = _BUDGET.search(instruction)
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except InvalidOperation:
        return None


def _affordable(instruction: str, candidates: list[Candidate]) -> list[Candidate]:
    budget = parse_budget(instruction)
    if budget is None:
        return list(candidates)
    pool = [c for c in candidates if Decimal(c.price) <= budget]
    return pool or list(candidates)


def _words(c: Candidate) -> set[str]:
    return set(tokens(" ".join([c.title, c.category, *c.attributes.values()])))


def attribute_aware(instruction: str, candidates: list[Candidate]) -> tuple[str, str]:
    if not candidates:
        raise ValueError("no candidates")
    want = set(tokens(instruction))
    pool = _affordable(instruction, candidates)
    ranked = sorted(pool, key=lambda c: (-len(want & _words(c)), Decimal(c.price), c.id))
    best = ranked[0]
    matched = sorted(want & _words(best))
    return best.id, f"Best match on {', '.join(matched) or 'no shared terms'}; cheapest among equal matches."


def price_first(instruction: str, candidates: list[Candidate]) -> tuple[str, str]:
    if not candidates:
        raise ValueError("no candidates")
    pool = _affordable(instruction, candidates)
    best = min(pool, key=lambda c: (Decimal(c.price), c.id))
    return best.id, "Cheapest item within budget."


POLICIES = {"attribute_aware": attribute_aware, "price_first": price_first}


class PolicyUnavailable(Exception):
    pass


def run_policy(policy: str, instruction: str, candidates: list[Candidate], llm=None,
               use_cache: bool = True) -> tuple[str, str]:
    if policy == "llm":
        if llm is None:
            raise PolicyUnavailable("llm policy needs an LLM client")
        return llm.choose_product(instruction, candidates, use_cache=use_cache)
    fn = POLICIES.get(policy)
    if fn is None:
        raise PolicyUnavailable(f"unknown agent policy {policy!r}")
    return fn(instruction, candidates)
