"""Check 3: replay the agent's decision to separate an ambiguous instruction (F3) from an agent error (F2)."""

from __future__ import annotations

from engine.agent_policy import PolicyUnavailable, relates_to, run_policy
from engine.attributes import fit, tokens
from engine.llm import LLMUnavailable
from engine.types import Candidate, CaseBundle, Evidence


def heuristic_clarify(instruction: str, claim_text: str, keys: list[str], chosen_attrs: dict[str, str],
                      candidates: list[Candidate]) -> str:
    """Add qualifiers the buyer names in the claim that the chosen item lacked and the catalog offers.

    "I wanted US 9, they sent UK 9" + chosen size "UK 9" + catalog sizes {UK 9, US 9} -> adds "us".
    """
    claim_words = set(tokens(claim_text))
    have = set(tokens(instruction))
    extra: list[str] = []
    for key in keys:
        offered = set()
        for c in candidates:
            offered |= set(tokens(c.attributes.get(key, "")))
        chosen_words = set(tokens(chosen_attrs.get(key, "")))
        extra.extend(sorted((claim_words & offered) - chosen_words - have - set(extra)))
    return f"{instruction} {' '.join(extra)}".strip() if extra else instruction


def run(b: CaseBundle, llm=None) -> tuple[list[Evidence], list[str]]:
    flags: list[str] = []
    t = b.trace
    if not relates_to(t.instruction, b.snapshot.title, b.order.category, b.snapshot.attributes):
        return [Evidence(check="replay",
                         finding=f"The buyer asked for '{t.instruction}' and the agent bought '{b.snapshot.title}', which "
                                 "has nothing in common with the request. A careful agent would have asked instead.",
                         cite="trace.instruction vs snapshot", fault_class="F2", party="agent_provider",
                         weight=0.85)], flags

    req = b.mandate.constraints.required_attributes
    status = fit(req, b.snapshot.attributes)
    values = set(status.values())

    if not req or values <= {"match"}:
        return [Evidence(check="replay", finding="The agent's choice satisfies every attribute in the mandate.",
                         cite="mandate.required_attributes vs snapshot")], flags

    try:
        original_id, _ = run_policy(t.policy, t.instruction, t.candidates, llm, use_cache=False)
    except (PolicyUnavailable, LLMUnavailable) as exc:
        flags.append("replay_unavailable")
        return [Evidence(check="replay", finding=f"Replay could not run: {exc}.", cite="trace.policy")], flags

    if original_id != t.chosen_id:
        flags.append("nondeterministic")
        return [Evidence(check="replay",
                         finding=f"Replay picked {original_id}, not the recorded {t.chosen_id}; the agent is not "
                                 "reproducible on the same inputs.",
                         cite="trace", fault_class="F2", party="agent_provider", weight=0.3)], flags

    bad = sorted(k for k, s in status.items() if s in ("mismatch", "missing"))
    if bad:
        detail = "; ".join(f"{k} required '{req[k]}', listing says '{b.snapshot.attributes.get(k, 'missing')}'"
                           for k in bad)
        return [Evidence(check="replay",
                         finding=f"The mandate was explicit and the agent still chose a non-matching item ({detail}). "
                                 "Replay on the same inputs reproduces the choice.",
                         cite="trace + mandate.required_attributes", fault_class="F2", party="agent_provider",
                         weight=0.85)], flags

    ambiguous = sorted(k for k, s in status.items() if s == "ambiguous")
    clarified = t.instruction
    if llm is not None:
        try:
            clarified = llm.clarify(t.instruction, b.claim.text, ambiguous)
        except LLMUnavailable:
            # Falls back to the heuristic clarifier below, which the benchmark measures. No confidence cap.
            flags.append("llm_unavailable")
    if clarified == t.instruction:
        clarified = heuristic_clarify(t.instruction, b.claim.text, ambiguous, b.snapshot.attributes, t.candidates)

    if clarified == t.instruction:
        return [
            Evidence(check="replay", finding=f"The instruction was ambiguous for {', '.join(ambiguous)} and the "
                                             "claim adds no qualifier to resolve it.",
                     cite="trace.instruction", fault_class="F3", party="buyer", weight=0.3),
            Evidence(check="replay", finding="The agent did not ask the buyer to resolve the ambiguity.",
                     cite="trace.instruction", fault_class="F3", party="agent_provider", weight=0.2),
        ], flags

    try:
        clarified_id, _ = run_policy(t.policy, clarified, t.candidates, llm)
    except (PolicyUnavailable, LLMUnavailable) as exc:
        flags.append("replay_unavailable")
        return [Evidence(check="replay", finding=f"Clarified replay could not run: {exc}.", cite="trace")], flags

    if clarified_id != t.chosen_id:
        return [
            Evidence(check="replay",
                     finding=f"Ambiguous {', '.join(ambiguous)}: with the clarified instruction '{clarified}' the agent "
                             f"picks {clarified_id} instead of {t.chosen_id}. The instruction caused the error.",
                     cite="trace replay (original vs clarified)", fault_class="F3", party="buyer", weight=0.5),
            Evidence(check="replay", finding="The agent bought on an ambiguous attribute without confirming it.",
                     cite="trace replay", fault_class="F3", party="agent_provider", weight=0.33),
        ], flags

    return [Evidence(check="replay",
                     finding=f"Even with the clarified instruction '{clarified}' the agent picks the same item; "
                             "the agent ignores the qualifier.",
                     cite="trace replay (original vs clarified)", fault_class="F2", party="agent_provider",
                     weight=0.7)], flags
