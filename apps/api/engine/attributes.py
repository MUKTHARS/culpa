"""Attribute normalization and comparison: tolerant of formatting noise, strict about meaning."""

from __future__ import annotations

import re
from functools import lru_cache

from engine.dsa import edit_distance

_PUNCT = re.compile(r"[^a-z0-9.]+")
_FILLER = {"size", "color", "colour", "the", "a", "an", "of"}


@lru_cache(maxsize=4096)
def tokens(value: str) -> tuple[str, ...]:
    raw = _PUNCT.sub(" ", str(value).lower()).split()
    return tuple(sorted({t.strip(".") for t in raw if t.strip(".") and t not in _FILLER}))


@lru_cache(maxsize=4096)
def compare(required: str, actual: str) -> str:
    """'match' | 'ambiguous' | 'mismatch'.

    match:     same tokens, or a one-character typo in a word of 5+ letters ("blakc" vs "black").
               Never for values with digits: "9" vs "8" is a different size, not a typo.
    ambiguous: every required token is present but actual adds a qualifier ("9" vs "UK 9").
    mismatch:  anything else.
    """
    rt, at = tokens(required), tokens(actual)
    if not rt:
        return "match"
    if rt == at:
        return "match"
    joined_r, joined_a = " ".join(rt), " ".join(at)
    typo_safe = len(joined_r) >= 5 and not any(c.isdigit() for c in joined_r + joined_a)
    if typo_safe and len(rt) == len(at) and edit_distance(joined_r, joined_a) <= max(1, len(joined_r) // 10):
        return "match"
    if set(rt) < set(at):
        return "ambiguous"
    return "mismatch"


def fit(required: dict[str, str], actual: dict[str, str]) -> dict[str, str]:
    """Per required attribute: match / ambiguous / mismatch / missing."""
    lowered = {k.lower(): v for k, v in actual.items()}
    out: dict[str, str] = {}
    for key, want in required.items():
        have = lowered.get(key.lower())
        out[key] = "missing" if have is None else compare(want, have)
    return out


def diff(before: dict[str, str], after: dict[str, str]) -> dict[str, tuple[str | None, str | None]]:
    """Keys whose meaning changed between two attribute maps (formatting-only changes are ignored)."""
    b = {k.lower(): v for k, v in before.items()}
    a = {k.lower(): v for k, v in after.items()}
    changed: dict[str, tuple[str | None, str | None]] = {}
    for key in sorted(set(b) | set(a)):
        old, new = b.get(key), a.get(key)
        if old is None or new is None:
            if old != new:
                changed[key] = (old, new)
        elif compare(old, new) != "match":
            changed[key] = (old, new)
    return changed
