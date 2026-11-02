"""Buyer-agent decision policies. The live agent and the replay check call the same functions.

- attribute_aware: deterministic heuristic, matches instruction words to product title and attributes.
- price_first:     a deliberately flawed agent that ignores attributes and buys the cheapest item
                   (used by the benchmark to model agent reasoning errors).
- llm:             the language model picks the product (needs an LLM client).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from engine.attributes import tokens
from engine.types import Candidate

_BUDGET = re.compile(r"(?:under|below|max(?:imum)?|less than|up to|<=?)\s*\$?\s*(\d+(?:\.\d{1,2})?)", re.I)
# Words that say nothing about which product is wanted.
_NOT_PRODUCT_WORDS = {"under", "below", "max", "maximum", "less", "than", "up", "to", "for", "with", "and", "or", "in",
                      "i", "me", "my", "want", "need", "buy", "get", "find", "please", "some", "new", "pair", "usd",
                      "something", "anything", "item", "thing", "stuff", "good", "nice", "cheap"}


class PolicyUnavailable(Exception):
    pass


class NoMatch(PolicyUnavailable):
    """Nothing in the catalog relates to the instruction: a careful agent asks instead of buying something."""


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


# Everyday names for the same product ("earphones" for earbuds or headphones). Applied to both sides of a comparison.
_SYNONYMS = {
    "earphone": {"earbud", "headphone"}, "earbud": {"earphone", "headphone"}, "headphone": {"earphone", "earbud"},
    "headset": {"headphone"}, "sneaker": {"shoe"}, "trainer": {"shoe"}, "coat": {"jacket"}, "shirt": {"tee"},
    "backpack": {"pack"}, "bag": {"pack"}, "pan": {"skillet"}, "blanket": {"throw"},
    "tshirt": {"tee", "shirt"}, "teeshirt": {"tee", "shirt"}, "jumper": {"sweater"}, "pullover": {"sweater"},
    "sweatshirt": {"sweater"}, "boot": {"shoe"}, "frying": {"skillet"},
}


def product_terms(text: str) -> set[str]:
    """Words that can identify a product: no budget words, no bare numbers ("9" alone could be any size), and no
    single letters (the "t" of "t shirt", the size "M")."""
    terms = {_stem(t) for t in tokens(text)
             if t not in _NOT_PRODUCT_WORDS and not t.replace(".", "").isdigit() and len(t) > 1}
    for t in list(terms):
        terms |= _SYNONYMS.get(t, set())
    terms |= {name for name, same in _SYNONYMS.items() if same & terms}  # "pack" also answers to "backpack"
    return terms


def relates_to(instruction: str, title: str, category: str, attributes: dict[str, str]) -> bool:
    """Is the item the kind of thing asked for ("shirt" vs socks: no)?

    The kind comes from the product's name and category; attributes say which variant, so "white t shirt" never
    matches white earbuds. Only a request made of attribute words alone ("something black") is matched on them.
    An instruction with no product words at all ("under $50") constrains nothing, so any item relates to it.
    """
    wanted = product_terms(instruction)
    if not wanted:
        return True
    if wanted & product_terms(f"{title} {category}"):
        return True
    return wanted <= product_terms(" ".join(attributes.values()))


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


def matched_terms(instruction: str, c: Candidate) -> list[str]:
    """The words of the request a product matches, for showing why it ranked where it did."""
    return sorted(set(tokens(instruction)) & _words(c))


def rank(instruction: str, candidates: list[Candidate]) -> list[Candidate]:
    """Search results in the agent's own order: only items of the kind asked for, within any budget in the text;
    closest product name first ("headphones": headphones before earbuds), then exact word matches, then price."""
    want = set(tokens(instruction))
    asked = product_terms(instruction)
    pool = [c for c in _affordable(instruction, candidates) if relates_to(instruction, c.title, c.category, c.attributes)]
    return sorted(pool, key=lambda c: (-len(asked & product_terms(c.title)), -len(want & _words(c)), Decimal(c.price), c.id))


def attribute_aware(instruction: str, candidates: list[Candidate]) -> tuple[str, str]:
    if not candidates:
        raise ValueError("no candidates")
    ranked = rank(instruction, candidates)
    if not ranked:
        raise NoMatch(f"nothing in the catalog matches {instruction!r}")
    best = ranked[0]
    matched = matched_terms(instruction, best)
    return best.id, f"Best match on {', '.join(matched) or 'no shared terms'}; cheapest among equal matches."


def price_first(instruction: str, candidates: list[Candidate]) -> tuple[str, str]:
    if not candidates:
        raise ValueError("no candidates")
    pool = _affordable(instruction, candidates)
    best = min(pool, key=lambda c: (Decimal(c.price), c.id))
    return best.id, "Cheapest item within budget."


POLICIES = {"attribute_aware": attribute_aware, "price_first": price_first}


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
