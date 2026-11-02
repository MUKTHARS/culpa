"""The plain-language reason for a verdict: a rule code, a title, one or two sentences, and the real-world rule it
follows. It is what the analyst reads first, before the evidence list.
"""

from __future__ import annotations

from engine.types import Evidence

PARTY = {"buyer": "the buyer", "merchant": "the merchant", "agent_provider": "the agent provider"}

# (code, title, reference) per situation.
_RULES = {
    "tampered": ("INT-01", "Evidence was altered after checkout",
                 "Culpa integrity check: the evidence fingerprint must match the one taken at capture"),
    "needs_evidence": ("SNAD-C", "Condition claim needs evidence",
                       "PayPal Significantly Not as Described / Visa 13.3: condition is shown with photos or a return"),
    "processing": ("PROC-01", "Payment-processing dispute",
                   "Visa 12.6 duplicate, 13.6 credit not processed, 13.2 cancelled recurring: settled from transaction records"),
    "F1": ("AGT-01", "The agent broke the signed mandate",
           "The buyer's signed mandate sets hard limits; a purchase outside them is the agent provider's liability"),
    "F2": ("AGT-02", "The agent chose the wrong item",
           "The mandate was clear and the agent's own replay reproduces the mistake"),
    "F3": ("AGT-03", "The instruction was ambiguous",
           "Replay with the buyer's clarification changes the choice, so the instruction caused it; the agent shares it for not asking"),
    "F4": ("SNAD-01", "The item delivered differs from the listing",
           "PayPal Significantly Not as Described / Visa 13.3: compared with the listing captured at purchase"),
    "F4_amount": ("AMT-01", "The buyer was charged more than the listed price",
                  "Visa 12.5 incorrect amount: compared with the listing price at purchase"),
    "F5": ("INR-01", "The item was not delivered",
           "PayPal Item Not Received / Visa 13.1: the seller must show proof of delivery"),
    "F6_not_received": ("INR-F", "Delivered, but the buyer says it never arrived",
                        "PayPal Item Not Received: proof of delivery decides the case for the seller"),
    "F6_changed_mind": ("SNAD-X", "Buyer's remorse",
                        "PayPal Buyer Protection excludes items that were properly described but no longer wanted"),
    "F6_unauthorized": ("UNA-F", "The buyer approved this purchase",
                        "Unauthorized-transaction claims fail when the account holder approved the exact cart"),
    "F6_agent_error": ("AGT-F", "The agent bought what the mandate asked for",
                       "The item fits the signed mandate and the buyer approved the cart, so 'my agent did it' does not hold"),
    "F6_amount": ("AMT-F", "The buyer approved the amount charged",
                  "Visa 12.5 incorrect amount: the charge equals the approved, listed price"),
    "F6": ("SNAD-F", "The item arrived exactly as listed",
           "PayPal Significantly Not as Described: an accurately described item is not covered"),
    "review": ("REV-01", "Not enough evidence to decide",
               "No single cause is proven, so a person decides"),
}

_ACTION = {
    "refund_full": "Refund the buyer in full; {bearer} bears the cost.",
    "refund_partial": "Partial refund to the buyer, shared by the parties at fault.",
    "contest": "Contest the dispute with the fingerprinted evidence.",
    "review": "Held for an analyst.",
}


def explain(*, fault_class: str | None, category: str, flags: list[str], evidence: list[Evidence],
            split: dict[str, float], action: str) -> dict[str, str]:
    if "evidence_tampered" in flags or "mandate_signature_invalid" in flags:
        key = "tampered"
    elif "needs_evidence" in flags and fault_class not in ("F1", "F2", "F4", "F5"):
        key = "needs_evidence"
    elif "processing_dispute" in flags and fault_class is None:
        key = "processing"
    elif fault_class is None:
        key = "review"
    elif fault_class == "F4" and any(e.cite == "order.amount vs snapshot.price" for e in evidence):
        key = "F4_amount"
    elif fault_class == "F6":
        key = {"not_received": "F6_not_received", "changed_mind": "F6_changed_mind", "unauthorized": "F6_unauthorized",
               "incorrect_amount": "F6_amount", "agent_error": "F6_agent_error"}.get(category, "F6")
    else:
        key = fault_class
    code, title, reference = _RULES[key]

    # The finding that decided it, in the evidence's own words.
    cause = next((e.finding for e in evidence if e.primary and e.fault_class == fault_class and e.party), None)
    if key in ("needs_evidence", "processing", "tampered"):
        cause = next((e.finding for e in evidence if not e.party and e.check in ("claim", "integrity")), cause)
    bearers = [PARTY[p] for p, share in split.items() if share > 0]
    outcome = _ACTION[action].format(bearer=" and ".join(bearers) or "the merchant")
    if action == "review" and fault_class:
        outcome = f"Likely {' and '.join(bearers)}, but other findings point elsewhere, so an analyst decides."
    if key == "needs_evidence":
        outcome = "Ask the buyer for photos or a return before deciding."
    if key == "processing":
        outcome = "Check the PayPal transaction history for this payment before deciding."
    summary = " ".join(x for x in (cause, outcome) if x)
    return {"code": code, "title": title, "summary": summary, "reference": reference}
