"""Run the checks in dependency order and produce a verdict."""

from __future__ import annotations

from engine.checks import claim, listing, replay, rules
from engine.dsa import topo_layers
from engine.claim_types import classify
from engine.policy import decide
from engine.reasons import explain
from engine.scoring import score
from engine.types import FAULT_NAMES, PARTIES, CaseBundle, Evidence, Verdict

# rules runs alone first so a hard breach can stop the analysis; replay and claim are independent of
# each other and form one layer that could run in parallel.
CHECK_DEPS: dict[str, list[str]] = {
    "rules": [],
    "listing": ["rules"],
    "replay": ["listing"],
    "claim": ["listing"],
}


def analyze(b: CaseBundle, llm=None, threshold: float = 0.8, use_replay: bool = True) -> Verdict:
    layers = topo_layers(CHECK_DEPS)
    flags: list[str] = []

    if b.integrity.stored_root and b.integrity.recomputed_root and b.integrity.stored_root != b.integrity.recomputed_root:
        flags.append("evidence_tampered")
    if not b.mandate.signature_valid:
        flags.append("mandate_signature_invalid")
    if flags:
        ev = [Evidence(check="integrity",
                       finding="Evidence fingerprint does not match the root recorded at checkout"
                       if "evidence_tampered" in flags else "Mandate signature is invalid",
                       cite="order.evidence_root")]
        split = dict.fromkeys(PARTIES, 0.0)
        return Verdict(fault_class=None, fault_name=None, split=split, confidence=0.0,
                       action="review", refund_amount=None, liability={}, evidence=ev, flags=flags,
                       check_order=layers, claim_category=classify(b.claim.reason, b.claim.text),
                       reason=explain(fault_class=None, category="other", flags=flags, evidence=ev, split=split,
                                      action="review"))

    evidence: list[Evidence] = []
    ran: list[list[str]] = []
    for layer in layers:
        done: list[str] = []
        for name in layer:
            if name == "rules":
                evidence += rules.run(b)
            elif name == "listing":
                evidence += listing.run(b)
            elif name == "replay":
                if not use_replay:
                    continue
                ev, fl = replay.run(b, llm)
                evidence += ev
                flags += fl
            elif name == "claim":
                ev, fl = claim.run(b, llm)
                evidence += ev
                flags += fl
            done.append(name)
        ran.append(done)
        if any(e.check == "rules" and e.weight >= 1.0 for e in evidence):
            flags.append("decided_by_rules")
            break

    flags = sorted(set(flags))
    fault_class, split, confidence = score(evidence, flags)
    action, refund_amount, liability = decide(fault_class, split, confidence, b.order.amount, threshold)
    category = classify(b.claim.reason, b.claim.text)
    return Verdict(
        fault_class=fault_class,
        fault_name=FAULT_NAMES.get(fault_class) if fault_class else None,
        split=split,
        confidence=confidence,
        action=action,
        refund_amount=refund_amount,
        liability=liability,
        evidence=evidence,
        flags=flags,
        check_order=ran,
        degraded="degraded" in flags,
        claim_category=category,
        reason=explain(fault_class=fault_class, category=category, flags=flags, evidence=evidence, split=split,
                       action=action),
    )
