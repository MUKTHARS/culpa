"""Turn evidence into a fault class, a per-party fault split and a confidence."""

from __future__ import annotations

from engine.types import PARTIES, Evidence

CONFIDENCE_CAP_UNCERTAIN = 0.6
STRENGTH_FULL = 0.8


def score(evidence: list[Evidence], flags: list[str]) -> tuple[str | None, dict[str, float], float]:
    party_w = dict.fromkeys(PARTIES, 0.0)
    class_w: dict[str, float] = {}
    for e in evidence:
        if e.party and e.fault_class and e.weight > 0:
            party_w[e.party] += e.weight
            class_w[e.fault_class] = class_w.get(e.fault_class, 0.0) + e.weight

    total = sum(party_w.values())
    if total == 0:
        return None, dict.fromkeys(PARTIES, 0.0), 0.0

    split = {p: round(w / total, 3) for p, w in party_w.items()}
    top = max(class_w, key=lambda k: (class_w[k], k))
    share = class_w[top] / sum(class_w.values())
    strength = min(1.0, class_w[top] / STRENGTH_FULL)
    decisive = any(e.weight >= 1.0 and e.fault_class == top for e in evidence)
    confidence = 1.0 if decisive and share == 1.0 else min(0.97, share * strength)

    if any(f in flags for f in ("nondeterministic", "degraded", "replay_unavailable")):
        confidence = min(confidence, CONFIDENCE_CAP_UNCERTAIN)
    return top, split, round(confidence, 3)
