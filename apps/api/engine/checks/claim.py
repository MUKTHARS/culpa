"""Check 4: is the buyer's claim consistent with what they approved and what was delivered?"""

from __future__ import annotations

from datetime import timedelta

from core.ids import parse_iso
from engine.agent_policy import relates_to
from engine.attributes import diff, fit
from engine.dsa import count_in_window
from engine.llm import LLMUnavailable
from engine.types import CaseBundle, Evidence

VELOCITY_WINDOW = timedelta(days=30)
VELOCITY_LIMIT = 3


def run(b: CaseBundle, llm=None) -> tuple[list[Evidence], list[str]]:
    flags: list[str] = []
    out: list[Evidence] = []

    req = b.mandate.constraints.required_attributes
    # The item satisfies the mandate only if it fits the required attributes *and* is what the buyer asked for:
    # with no attributes given, socks bought for "shirt" would otherwise count as a perfect fit.
    mandate_ok = all(s == "match" for s in fit(req, b.snapshot.attributes).values()) and relates_to(
        b.mandate.text, b.snapshot.title, b.order.category, b.snapshot.attributes)
    d = b.delivery
    delivered_ok = d.delivered and d.attributes is not None and not diff(b.snapshot.attributes, d.attributes)
    approved = b.order.approved_at is not None

    if approved and mandate_ok and delivered_ok:
        out.append(Evidence(
            check="claim",
            finding="The buyer approved this exact cart, the item satisfies the mandate, and the delivered item "
                    "matches the listing. The claim contradicts the recorded evidence.",
            cite="order.approved_at + mandate fit + delivery", fault_class="F6", party="buyer", weight=0.8))

    now = parse_iso(b.now) if b.now else None
    times = sorted(t for t in (parse_iso(x) for x in b.buyer.recent_dispute_times) if t is not None)
    if now and times:
        n = count_in_window(times, now, VELOCITY_WINDOW)
        if n > VELOCITY_LIMIT:
            out.append(Evidence(check="claim", finding=f"The buyer opened {n} disputes in the last 30 days.",
                                cite="buyer dispute history (sliding window)", fault_class="F6", party="buyer",
                                weight=0.3))

    if b.buyer.ring_size >= 3 and b.buyer.ring_fraud_count >= 2:
        out.append(Evidence(check="claim",
                            finding=f"The buyer shares devices or addresses with {b.buyer.ring_size - 1} other accounts, "
                                    f"{b.buyer.ring_fraud_count} of them with friendly-fraud disputes.",
                            cite="account graph (union-find)", fault_class="F6", party="buyer", weight=0.3))

    if llm is not None and b.claim.text:
        facts = {
            "mandate_text": b.mandate.text,
            "required_attributes": req,
            "listing_at_purchase": {"title": b.snapshot.title, "attributes": b.snapshot.attributes},
            "buyer_approved_cart": approved,
            "delivered": d.delivered,
            "delivered_attributes": d.attributes,
            "tracking": d.tracking,
            "dispute_reason": b.claim.reason,
        }
        try:
            judge = llm.judge_claim(b.claim.text, facts)
            if not judge["consistent_with_evidence"] and judge["confidence"] >= 0.6:
                reasons = "; ".join(judge.get("contradictions", [])[:3]) or "claim contradicts the evidence"
                out.append(Evidence(check="claim", finding=f"Claim judge: {reasons}.", cite="claim vs evidence (LLM judge)",
                                    fault_class="F6", party="buyer", weight=round(0.4 * judge["confidence"], 3)))
            else:
                out.append(Evidence(check="claim",
                                    finding=f"Claim judge: claim is consistent with the evidence ({judge['claim_type']}).",
                                    cite="claim vs evidence (LLM judge)"))
        except LLMUnavailable:
            # The judge only adds evidence; without it the rule-based checks above still decide. No confidence cap.
            flags.append("llm_unavailable")

    if not out:
        out.append(Evidence(check="claim", finding="No contradiction found between the claim and the evidence.",
                            cite="claim"))
    return out, flags
