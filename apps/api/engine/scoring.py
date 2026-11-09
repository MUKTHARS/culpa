"""Turn evidence into a fault class, a per-party fault split and a confidence.

Fault follows the cause, not a vote. Only primary evidence (a cause of the problem) decides who is at fault, and
when several causes are present the one the buyer's loss actually comes from wins, in this order:

  F5 nothing delivered      -> merchant      (the buyer received nothing; nothing else matters)
  F4 delivered != listing   -> merchant      (what arrived is not what was sold)
  F1 mandate breach         -> agent provider
  F2 agent reasoning error  -> agent provider
  F3 ambiguous instruction  -> buyer and agent provider share it (the only shared verdict, by design)
  F6 claim contradicts the record -> buyer

The split comes from the winning cause alone. Everything that points elsewhere (another cause, a supporting signal
such as dispute history or the AI judge) only lowers confidence, so a clear case still settles and a muddled one
goes to a person.
"""

from __future__ import annotations

from engine.types import PARTIES, Evidence

CONFIDENCE_CAP_UNCERTAIN = 0.6
STRENGTH_FULL = 0.8
PRECEDENCE = ("F5", "F4", "F1", "F2", "F3", "F6")
CONTRADICTION_PENALTY = 0.05
MAX_CONTRADICTION_PENALTY = 0.15


def _split(items: list[Evidence]) -> dict[str, float]:
    party_w = dict.fromkeys(PARTIES, 0.0)
    for e in items:
        party_w[e.party] += e.weight
    total = sum(party_w.values())
    return {p: round(w / total, 3) for p, w in party_w.items()}


def score(evidence: list[Evidence], flags: list[str]) -> tuple[str | None, dict[str, float], float]:
    faults = [e for e in evidence if e.party and e.fault_class and e.weight > 0]
    if not faults:
        return None, dict.fromkeys(PARTIES, 0.0), 0.0

    causes = [e for e in faults if e.primary]
    if not causes and any(f in flags for f in ("needs_evidence", "processing_dispute")):
        # The records cannot prove this kind of claim, so a side signal must not read as blame.
        return None, dict.fromkeys(PARTIES, 0.0), 0.0
    if causes:
        top = next(c for c in PRECEDENCE if any(e.fault_class == c for e in causes))
        winning = [e for e in causes if e.fault_class == top]
        split = _split(winning)
        strength = sum(e.weight for e in winning)
        decisive = any(e.weight >= 1.0 for e in winning)
        confidence = 1.0 if decisive else min(0.97, strength / STRENGTH_FULL)
        # Evidence for another party (another cause, or a supporting signal) makes the case less clear-cut.
        at_fault = {p for p, share in split.items() if share > 0}
        against = [e for e in faults if e not in winning and e.party not in at_fault]
        agreeing = [e for e in faults if not e.primary and e.party in at_fault]
        if not decisive:  # a broken hard limit is not weakened by anything else
            penalty = min(MAX_CONTRADICTION_PENALTY, CONTRADICTION_PENALTY * len(against))
            confidence = min(0.97, confidence - penalty + 0.02 * len(agreeing))
    else:
        # Only supporting signals and no cause: never enough to move money, so it always goes to a person.
        class_w: dict[str, float] = {}
        for e in faults:
            class_w[e.fault_class] = class_w.get(e.fault_class, 0.0) + e.weight
        top = max(class_w, key=lambda k: (class_w[k], k))
        split = _split([e for e in faults if e.fault_class == top])
        share = class_w[top] / sum(class_w.values())
        confidence = min(CONFIDENCE_CAP_UNCERTAIN, share * min(1.0, class_w[top] / STRENGTH_FULL))

    if any(f in flags for f in ("nondeterministic", "degraded", "replay_unavailable")):
        confidence = min(confidence, CONFIDENCE_CAP_UNCERTAIN)
    return top, split, round(max(0.0, confidence), 3)
