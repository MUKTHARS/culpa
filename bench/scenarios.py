"""Dispute scenarios modelled on real-world dispute rules, with the outcome each rule expects.

42 situations drawn from PayPal Buyer Protection (Item Not Received, Significantly Not as Described, unauthorized
transactions and its exclusions), Visa / Mastercard reason codes (13.1, 13.3, 13.6, 13.2, 12.5, 12.6 and 10.4 /
4837, 4853, 4855) and the agent-purchase cases the industry is still debating, each run on three product families:
126 cases. Every case states the expected fault, who pays, and the action.

Usage: python bench/scenarios.py   (prints a summary and writes bench/scenarios.md)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps" / "api"))

from engine.agent_policy import attribute_aware, price_first  # noqa: E402
from engine.pipeline import analyze  # noqa: E402
from engine.types import (  # noqa: E402
    BuyerSignals,
    Candidate,
    CaseBundle,
    Claim,
    Constraints,
    Delivery,
    Integrity,
    ListingVersion,
    Mandate,
    OrderInfo,
    Trace,
)

NOW = "2026-11-02T12:00:00Z"


@dataclass
class Family:
    name: str
    category: str
    key: str
    candidates: list[Candidate]
    wanted: Candidate  # what an explicit instruction asks for
    other: Candidate  # a different variant (the "wrong" one)
    partial: str  # an ambiguous value ("9", "blue", "qw")
    clarified: str  # what the buyer meant by it
    noun: str


def _c(i: str, title: str, price: str, category: str, **attrs) -> Candidate:
    return Candidate(id=i, title=title, price=price, category=category, merchant_id="m_store", attributes=attrs)


SHOES = [_c("uk9", "Stride Running Shoe", "95.00", "shoes/running", size="UK 9", color="Black"),
         _c("us9", "Stride Running Shoe", "99.00", "shoes/running", size="US 9", color="Black"),
         _c("us10", "Stride Running Shoe", "89.00", "shoes/running", size="US 10", color="Black")]
JACKETS = [_c("navy", "Harbor Jacket", "140.00", "apparel/jackets", color="Navy Blue", material="Leather"),
           _c("sky", "Harbor Jacket", "149.00", "apparel/jackets", color="Sky Blue", material="Leather"),
           _c("black", "Harbor Jacket", "135.00", "apparel/jackets", color="Black", material="Leather")]
AUDIO = [_c("qw2", "Quiet Headphones", "129.00", "electronics/audio", color="Black", model="QW-2"),
         _c("qw3", "Quiet Headphones Pro", "169.00", "electronics/audio", color="Black", model="QW-3"),
         _c("qw2w", "Quiet Headphones", "119.00", "electronics/audio", color="White", model="QW-2")]

FAMILIES = [
    Family("shoes", "shoes/running", "size", SHOES, SHOES[1], SHOES[0], "9", "US 9", "running shoes"),
    Family("jacket", "apparel/jackets", "color", JACKETS, JACKETS[1], JACKETS[0], "blue", "Sky Blue", "harbor jacket"),
    Family("headphones", "electronics/audio", "model", AUDIO, AUDIO[1], AUDIO[0], "qw", "QW-3", "quiet headphones"),
]


def bundle(f: Family, *, chosen: Candidate | None = None, instruction: str | None = None,
           required: dict | None = None, policy: str = "attribute_aware", shipped: bool = True,
           delivered: bool = True, delivered_attrs: dict | None = None, changed_listing: dict | None = None,
           claim: str = "Not what I ordered.", reason: str = "ITEM_NOT_AS_DESCRIBED", amount: str | None = None,
           cons: dict | None = None, buyer: BuyerSignals | None = None, integrity: Integrity | None = None,
           signature_valid: bool = True, created_at: str = "2026-10-25T10:00:05Z") -> CaseBundle:
    chosen = chosen or f.wanted
    instruction = instruction or f"{f.noun} {f.key} {f.wanted.attributes[f.key]}"
    required = {f.key: f.wanted.attributes[f.key]} if required is None else required
    snap = ListingVersion(1, chosen.title, chosen.price, dict(chosen.attributes), "2026-10-25T10:00:00Z")
    history = [snap]
    if changed_listing:
        history.append(ListingVersion(2, chosen.title, chosen.price, {**chosen.attributes, **changed_listing},
                                      "2026-10-25T18:00:00Z"))
    constraints = Constraints(**{"max_amount": "500.00", "required_attributes": required, **(cons or {})})
    return CaseBundle(
        case_id="scenario",
        mandate=Mandate(text=instruction, constraints=constraints, signature_valid=signature_valid),
        trace=Trace(policy=policy, instruction=instruction, candidates=list(f.candidates), chosen_id=chosen.id),
        snapshot=snap,
        order=OrderInfo(amount=amount or chosen.price, merchant_id=chosen.merchant_id, category=chosen.category,
                        created_at=created_at, approved_at="2026-10-25T10:01:00Z"),
        delivery=Delivery(shipped=shipped, delivered=delivered and shipped,
                          tracking="TRK123" if shipped else None,
                          attributes=(delivered_attrs if delivered_attrs is not None else dict(chosen.attributes))
                          if delivered and shipped else None,
                          shipped_at="2026-10-26T09:00:00Z" if shipped else None),
        claim=Claim(reason=reason, text=claim),
        listing_history=history,
        buyer=buyer or BuyerSignals(),
        integrity=integrity or Integrity(),
        now=NOW,
    )


REPEAT_DISPUTER = BuyerSignals(recent_dispute_times=[f"2026-10-{d:02d}T08:00:00Z" for d in (3, 9, 15, 22, 29)])
FRAUD_RING = BuyerSignals(ring_size=4, ring_fraud_count=3)


def _changed(f: Family) -> dict:
    return {f.key: f.other.attributes[f.key]}


def _price_first_pick(f: Family) -> Candidate:
    cid, _ = price_first(f"{f.noun} {f.key} {f.wanted.attributes[f.key]}", f.candidates)
    return next(c for c in f.candidates if c.id == cid)


def _unreproducible_pick(f: Family) -> Candidate:
    """A recorded choice the agent's own replay would not make (neither the wanted item nor the agent's pick)."""
    replayed = _price_first_pick(f)
    return next(c for c in f.candidates if c.id not in (f.wanted.id, replayed.id))


def _ambiguous_pick(f: Family) -> Candidate:
    cid, _ = attribute_aware(f"{f.noun} {f.key} {f.partial}", f.candidates)
    return next(c for c in f.candidates if c.id == cid)


@dataclass
class Situation:
    title: str
    rule: str  # the real-world rule it follows
    build: Callable[[Family], CaseBundle]
    fault: str | None  # expected fault class (None = no fault proven)
    bearer: str | None  # merchant | agent_provider | buyer | split | None (nobody pays yet)
    action: str


S = Situation
SITUATIONS: list[Situation] = [
    # Item not received: PayPal INR, Visa 13.1, Mastercard 4855
    S("Never shipped; buyer says it never arrived", "PayPal INR / Visa 13.1",
      lambda f: bundle(f, shipped=False, claim="It never arrived.", reason="ITEM_NOT_RECEIVED"), "F5", "merchant", "refund_full"),
    S("Shipped with tracking but no proof of delivery", "PayPal INR: seller must show delivery",
      lambda f: bundle(f, delivered=False, claim="Package not received.", reason="ITEM_NOT_RECEIVED"), "F5", "merchant", "refund_full"),
    S("Delivery confirmed; buyer says it never arrived", "PayPal INR: proof of delivery wins for the seller",
      lambda f: bundle(f, claim="It never arrived.", reason="ITEM_NOT_RECEIVED"), "F6", "buyer", "contest"),
    S("Delivery confirmed; buyer says lost in transit", "Visa 13.1: delivery scan defeats the claim",
      lambda f: bundle(f, claim="It got lost in the mail.", reason="ITEM_NOT_RECEIVED"), "F6", "buyer", "contest"),
    S("Never shipped; buyer files 'not as described'", "PayPal INR: nothing delivered",
      lambda f: bundle(f, shipped=False, claim="The colour is wrong."), "F5", "merchant", "refund_full"),
    S("Never shipped; buyer is a repeat disputer", "Visa 13.1: history does not excuse non-delivery",
      lambda f: bundle(f, shipped=False, claim="Never got it.", reason="ITEM_NOT_RECEIVED", buyer=REPEAT_DISPUTER),
      "F5", "merchant", "refund_full"),
    # Significantly not as described: PayPal SNAD, Visa 13.3, Mastercard 4853
    S("Listing edited after purchase; edited version shipped", "PayPal SNAD / Visa 13.3",
      lambda f: bundle(f, changed_listing=_changed(f), delivered_attrs={**f.wanted.attributes, **_changed(f)}),
      "F4", "merchant", "refund_full"),
    S("Merchant shipped a different variant", "PayPal SNAD: a different item",
      lambda f: bundle(f, delivered_attrs=dict(f.other.attributes), claim="I got the wrong one."), "F4", "merchant", "refund_full"),
    S("Delivered exactly as listed; buyer says not as described", "PayPal SNAD: accurately described is not covered",
      lambda f: bundle(f, claim="This is not what was described."), "F6", "buyer", "contest"),
    S("Delivered exactly as listed; buyer says wrong variant", "Visa 13.3: listing at purchase matches delivery",
      lambda f: bundle(f, claim="Wrong one, I wanted something else."), "F6", "buyer", "contest"),
    S("Wrong variant shipped; buyer is a repeat disputer", "PayPal SNAD: history does not excuse a wrong item",
      lambda f: bundle(f, delivered_attrs=dict(f.other.attributes), buyer=REPEAT_DISPUTER), "F4", "merchant", "refund_full"),
    S("Delivered as listed; buyer linked to a fraud ring", "Friendly-fraud pattern",
      lambda f: bundle(f, claim="Not as described.", buyer=FRAUD_RING), "F6", "buyer", "contest"),
    # Condition claims: records cannot prove condition, so ask for evidence
    S("Arrived broken", "PayPal SNAD / Visa 13.3 defective: needs photos",
      lambda f: bundle(f, claim="It arrived broken."), None, None, "review"),
    S("Buyer says it is counterfeit", "Visa 13.4 counterfeit: needs examination",
      lambda f: bundle(f, claim="This is a fake, not genuine."), None, None, "review"),
    S("Missing parts", "PayPal SNAD: missing parts need evidence",
      lambda f: bundle(f, claim="It came with missing parts."), None, None, "review"),
    S("Stopped working after a day", "Visa 13.3 defective",
      lambda f: bundle(f, claim="It stopped working after one day."), None, None, "review"),
    S("Sold as new, arrived used", "PayPal SNAD: condition misrepresented",
      lambda f: bundle(f, claim="This item is used, not new."), None, None, "review"),
    S("Says it arrived damaged, but it was never shipped", "PayPal INR: nothing was delivered",
      lambda f: bundle(f, shipped=False, claim="It arrived damaged."), "F5", "merchant", "refund_full"),
    # The agent and its mandate
    S("Agent spent over the mandate cap", "Signed mandate: hard spending limit",
      lambda f: bundle(f, cons={"max_amount": "50.00"}), "F1", "agent_provider", "refund_full"),
    S("Agent bought after the mandate expired", "Signed mandate: expiry",
      lambda f: bundle(f, cons={"expires_at": "2026-10-24T00:00:00Z"}), "F1", "agent_provider", "refund_full"),
    S("Agent bought outside the allowed category", "Signed mandate: category allowlist",
      lambda f: bundle(f, cons={"allowed_categories": ["groceries"]}), "F1", "agent_provider", "refund_full"),
    S("Agent bought from a merchant not on the allowlist", "Signed mandate: merchant allowlist",
      lambda f: bundle(f, cons={"allowed_merchants": ["m_other"]}), "F1", "agent_provider", "refund_full"),
    S("Agent bought in the wrong currency", "Signed mandate: currency",
      lambda f: bundle(f, cons={"currency": "EUR"}), "F1", "agent_provider", "refund_full"),
    S("Agent ignored an explicit attribute", "Mandate clear; replay reproduces the error",
      lambda f: bundle(f, chosen=_price_first_pick(f), policy="price_first",
                       claim=f"I asked for {f.wanted.attributes[f.key]}."), "F2", "agent_provider", "refund_full"),
    S("Agent bought a product of the wrong kind", "Item unrelated to the instruction",
      lambda f: bundle(f, instruction="portable speaker", required={}, claim="I asked for a speaker."),
      "F2", "agent_provider", "refund_full"),
    S("Ambiguous instruction; buyer's claim clarifies it", "Replay with clarification changes the choice",
      lambda f: bundle(f, chosen=_ambiguous_pick(f), instruction=f"{f.noun} {f.key} {f.partial}",
                       required={f.key: f.partial}, claim=f"I wanted {f.clarified}, not this."),
      "F3", "split", "refund_partial"),
    S("Ambiguous instruction; claim adds nothing", "Cause not provable: analyst decides",
      lambda f: bundle(f, chosen=_ambiguous_pick(f), instruction=f"{f.noun} {f.key} {f.partial}",
                       required={f.key: f.partial}, claim="Not what I wanted."), "F3", None, "review"),
    S("Mandate breach and never shipped", "Hard limit breached first: agent liable",
      lambda f: bundle(f, cons={"max_amount": "50.00"}, shipped=False, reason="ITEM_NOT_RECEIVED",
                       claim="Never arrived."), "F1", "agent_provider", "refund_full"),
    S("'My agent bought the wrong thing', but it fits the mandate", "Agent liability needs an agent error",
      lambda f: bundle(f, claim="My AI agent bought the wrong item."), "F6", "buyer", "contest"),
    S("Agent cannot be reproduced on replay", "Cause not provable: analyst decides",
      lambda f: bundle(f, chosen=_unreproducible_pick(f), policy="price_first", claim="Wrong one."), "F2", None, "review"),
    # Unauthorized: PayPal unauthorized transaction, Visa 10.4, Mastercard 4837
    S("Says unauthorized, but approved the exact cart", "Approval by the account holder",
      lambda f: bundle(f, claim="I never authorized this purchase.", reason="UNAUTHORISED"), "F6", "buyer", "contest"),
    S("Says unauthorized; the agent broke the cap", "Mandate breach is the agent's",
      lambda f: bundle(f, claim="I never authorized this.", reason="UNAUTHORISED", cons={"max_amount": "50.00"}),
      "F1", "agent_provider", "refund_full"),
    S("Says unauthorized; evidence altered", "Integrity failure: analyst decides",
      lambda f: bundle(f, claim="Not authorized.", reason="UNAUTHORISED", integrity=Integrity("a" * 64, "b" * 64)),
      None, None, "review"),
    # Buyer's remorse: excluded from PayPal Buyer Protection
    S("Changed their mind after delivery", "PayPal Buyer Protection exclusion",
      lambda f: bundle(f, claim="I changed my mind, I don't want it."), "F6", "buyer", "contest"),
    S("Found it cheaper elsewhere", "PayPal Buyer Protection exclusion",
      lambda f: bundle(f, claim="I found it cheaper elsewhere, refund me."), "F6", "buyer", "contest"),
    # Processing errors: settled from transaction records
    S("Charged twice", "Visa 12.6.1 duplicate processing",
      lambda f: bundle(f, claim="I was charged twice for this.", reason="OTHER"), None, None, "review"),
    S("Refund promised but never received", "Visa 13.6 credit not processed",
      lambda f: bundle(f, claim="I returned it but my refund was never processed.", reason="OTHER"), None, None, "review"),
    S("Charged after cancelling a subscription", "Visa 13.2 cancelled recurring",
      lambda f: bundle(f, claim="I cancelled my subscription and was still charged.", reason="OTHER"), None, None, "review"),
    S("Charged more than the listed price", "Visa 12.5 incorrect amount",
      lambda f: bundle(f, amount=f"{float(f.wanted.price) + 20:.2f}", claim="I was charged more than the listed price."),
      "F4", "merchant", "refund_full"),
    S("Says the amount was wrong, but it matches the listing", "Visa 12.5: charge equals approved price",
      lambda f: bundle(f, claim="Wrong amount charged.", reason="OTHER"), "F6", "buyer", "contest"),
    # Integrity
    S("Mandate signature does not verify", "Integrity failure: analyst decides",
      lambda f: bundle(f, signature_valid=False), None, None, "review"),
    S("Delivered as listed; claim is 'it never arrived' from a repeat disputer", "Proof of delivery + dispute history",
      lambda f: bundle(f, claim="Never arrived.", reason="ITEM_NOT_RECEIVED", buyer=REPEAT_DISPUTER), "F6", "buyer", "contest"),
]


def bearer(action: str, split: dict[str, float]) -> str | None:
    if action == "review":
        return None
    if action == "refund_partial":
        return "split"
    return max(split, key=split.get) if any(split.values()) else None


def run() -> list[dict]:
    rows = []
    for i, sit in enumerate(SITUATIONS, 1):
        for f in FAMILIES:
            v = analyze(sit.build(f))
            got = {"fault": v.fault_class, "bearer": bearer(v.action, v.split), "action": v.action}
            want = {"fault": sit.fault, "bearer": sit.bearer, "action": sit.action}
            single = sum(1 for s in v.split.values() if s > 0)
            honest_split = v.fault_class == "F3" or single <= 1  # one party at fault, except a shared ambiguity
            rows.append({"id": f"S{i:02d}-{f.name}", "title": sit.title, "rule": sit.rule, "want": want, "got": got,
                         "reason": v.reason.get("code", ""), "confidence": v.confidence,
                         "passed": got == want and honest_split})
    return rows


def write_markdown(rows: list[dict], path: Path) -> None:
    passed = sum(r["passed"] for r in rows)
    lines = ["# Dispute scenarios", "",
             f"{len(rows)} cases ({len(SITUATIONS)} real-world situations x {len(FAMILIES)} product families). "
             f"Passed: {passed}/{len(rows)}. Generated by `python bench/scenarios.py`.", "",
             "| Case | Situation | Real-world rule | Expected | Culpa | Reason | OK |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    fmt = lambda d: f"{d['fault'] or 'no fault'} / {d['bearer'] or 'nobody yet'} / {d['action']}"  # noqa: E731
    for r in rows:
        lines.append(f"| {r['id']} | {r['title']} | {r['rule']} | {fmt(r['want'])} | {fmt(r['got'])} | "
                     f"{r['reason']} | {'yes' if r['passed'] else '**no**'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = run()
    write_markdown(rows, ROOT / "scenarios.md")
    failed = [r for r in rows if not r["passed"]]
    print(f"{len(rows) - len(failed)}/{len(rows)} scenarios pass")
    for r in failed:
        print(f"  FAIL {r['id']}: {r['title']} | want {r['want']} | got {r['got']} | {r['reason']} conf {r['confidence']}")


if __name__ == "__main__":
    main()
