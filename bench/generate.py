"""Generate AgentDispute-150: 25 labeled agent-purchase disputes per fault class (F1-F6), ~20% hard.

Each case is built from a known cause, so its label is true by construction:
  F1 the order breaks a hard mandate limit      F4 the merchant changed the item after purchase
  F2 a flawed agent ignores an explicit attribute F5 the item was never delivered
  F3 the instruction was ambiguous               F6 everything matches; the claim is false

Usage: python bench/generate.py   (writes bench/data/agentdispute-150.jsonl)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps" / "api"))

from engine.agent_policy import attribute_aware, price_first  # noqa: E402
from engine.types import (  # noqa: E402
    BuyerSignals,
    Candidate,
    CaseBundle,
    Claim,
    Constraints,
    Delivery,
    ListingVersion,
    Mandate,
    OrderInfo,
    Trace,
)

SEED = 2026
PER_CLASS = 25
HARD_SHARE = 0.2
NOW = "2026-11-02T12:00:00Z"


def _c(i, title, price, category, **attrs) -> Candidate:
    return Candidate(id=f"p{i}", title=title, price=f"{price:.2f}", category=category, merchant_id="m_bench",
                     attributes=attrs)


def family(rng: random.Random, kind: str) -> tuple[list[Candidate], str]:
    """A small catalog plus the attribute that matters for this family."""
    base = rng.randint(40, 160)
    if kind == "shoes":
        return [
            _c(1, "Stride Running Shoe", base, "shoes/running", size="UK 9", color="Black"),
            _c(2, "Stride Running Shoe", base + 4, "shoes/running", size="US 9", color="Black"),
            _c(3, "Stride Running Shoe", base + 4, "shoes/running", size="US 10", color="Black"),
            _c(4, "Stride Running Shoe", base + 6, "shoes/running", size="EU 42", color="Black"),
        ], "size"
    if kind == "jacket":
        return [
            _c(1, "Harbor Jacket", base, "apparel/jackets", color="Navy Blue", material="Leather"),
            _c(2, "Harbor Jacket", base + 9, "apparel/jackets", color="Sky Blue", material="Leather"),
            _c(3, "Harbor Jacket", base + 9, "apparel/jackets", color="Black", material="Leather"),
        ], "color"
    if kind == "headphones":
        return [
            _c(1, "Quiet Headphones", base, "electronics/audio", color="White", model="QW-2"),
            _c(2, "Quiet Headphones", base + 15, "electronics/audio", color="Black", model="QW-2"),
            _c(3, "Quiet Headphones Pro", base + 40, "electronics/audio", color="Black", model="QW-3"),
        ], "color"
    return [
        _c(1, "Everyday Tee", base // 4 + 9, "apparel/tops", size="S", color="White"),
        _c(2, "Everyday Tee", base // 4 + 11, "apparel/tops", size="M", color="White"),
        _c(3, "Everyday Tee", base // 4 + 11, "apparel/tops", size="L", color="White"),
    ], "size"


def _snap(c: Candidate, version=1, at="2026-10-25T10:00:00Z") -> ListingVersion:
    return ListingVersion(version=version, title=c.title, price=c.price, attributes=dict(c.attributes), captured_at=at)


def _bundle(case_id, *, mandate_text, required, candidates, chosen, policy="attribute_aware", max_amount=None,
            delivery=None, claim, reason="ITEM_NOT_AS_DESCRIBED", history=None, buyer=None, constraints_extra=None,
            amount=None, created_at="2026-10-25T10:00:05Z") -> CaseBundle:
    snap = _snap(chosen)
    cons = Constraints(max_amount=max_amount or "500.00", required_attributes=required, **(constraints_extra or {}))
    return CaseBundle(
        case_id=case_id,
        mandate=Mandate(text=mandate_text, constraints=cons),
        trace=Trace(policy=policy, instruction=mandate_text, candidates=candidates, chosen_id=chosen.id),
        snapshot=snap,
        order=OrderInfo(amount=amount or chosen.price, merchant_id=chosen.merchant_id, category=chosen.category,
                        created_at=created_at, approved_at="2026-10-25T10:01:00Z"),
        delivery=delivery or Delivery(shipped=True, delivered=True, tracking="TRK" + case_id[-4:],
                                      attributes=dict(chosen.attributes), shipped_at="2026-10-26T09:00:00Z"),
        claim=Claim(reason=reason, text=claim),
        listing_history=history or [snap],
        buyer=buyer or BuyerSignals(),
        now=NOW,
    )


def _pick(candidates, text, policy="attribute_aware"):
    fn = attribute_aware if policy == "attribute_aware" else price_first
    cid, _ = fn(text, candidates)
    return next(c for c in candidates if c.id == cid)


def _instruction(chosen: Candidate, key: str, value: str) -> str:
    noun = chosen.title.lower()
    return f"{noun} {key} {value}"


def gen_f1(rng, i, hard):
    kind = rng.choice(["shoes", "jacket", "headphones", "tee"])
    cands, key = family(rng, kind)
    target = rng.choice(cands)
    text = _instruction(target, key, target.attributes[key])
    chosen = _pick(cands, text)
    variant = rng.choice(["budget", "budget", "expired", "category"])
    extra, created, max_amount = {}, "2026-10-25T10:00:05Z", None
    if variant == "budget":
        max_amount = f"{float(chosen.price) - rng.randint(3, 25):.2f}"
    elif variant == "expired":
        extra = {"expires_at": "2026-10-24T00:00:00Z"}
    else:
        extra = {"allowed_categories": ["groceries"]}
    claim = rng.choice(["I never approved spending that much.", "This purchase was outside what I allowed.",
                        "My limit was lower than this."]) if not hard else rng.choice(
        ["The item looks fine but I want my money back.", "Package arrived, not what I expected."])
    return _bundle(f"F1-{i:03d}", mandate_text=text, required={key: chosen.attributes[key]}, candidates=cands,
                   chosen=chosen, max_amount=max_amount, constraints_extra=extra, claim=claim, created_at=created,
                   reason="UNAUTHORISED" if not hard else "ITEM_NOT_AS_DESCRIBED")


def gen_f2(rng, i, hard):
    kind = rng.choice(["shoes", "jacket", "headphones", "tee"])
    cands, key = family(rng, kind)
    cheapest = min(cands, key=lambda c: float(c.price))
    wanted = rng.choice([c for c in cands if c.attributes[key] != cheapest.attributes[key]])
    text = _instruction(wanted, key, wanted.attributes[key])
    chosen = _pick(cands, text, "price_first")
    claim = (f"I asked for {key} {wanted.attributes[key]} and got {chosen.attributes[key]}." if not hard else
             rng.choice(["I changed my mind about this order.", "Please refund, the seller is unresponsive."]))
    b = _bundle(f"F2-{i:03d}", mandate_text=text, required={key: wanted.attributes[key]}, candidates=cands,
                chosen=chosen, policy="price_first", claim=claim)
    if hard and i % 2:
        # A non-reproducible agent: the recorded choice is not what the agent picks on replay.
        # Culpa cannot prove the cause and should escalate rather than guess.
        other = next(c for c in cands if c.id != chosen.id and c.attributes[key] != wanted.attributes[key]) \
            if any(c.id != chosen.id and c.attributes[key] != wanted.attributes[key] for c in cands) else None
        if other is not None:
            b.trace.chosen_id = other.id
            b.snapshot = _snap(other)
            b.listing_history = [b.snapshot]
            b.order.amount = other.price
            b.delivery.attributes = dict(other.attributes)
    return b


def gen_f3(rng, i, hard):
    kind = rng.choice(["shoes", "jacket"])
    cands, key = family(rng, kind)
    if kind == "shoes":
        partial, wanted_value = "9", "US 9"
    else:
        partial, wanted_value = "blue", "Sky Blue"
    text = f"{cands[0].title.lower()} {key} {partial}"
    chosen = _pick(cands, text)
    noise = rng.choice(["", " Very disappointed.", " The agent should have checked."]) if hard else ""
    claim = f"I wanted {wanted_value}, they sent {chosen.attributes[key]}.{noise}"
    return _bundle(f"F3-{i:03d}", mandate_text=text, required={key: partial}, candidates=cands, chosen=chosen,
                   claim=claim)


def gen_f4(rng, i, hard):
    kind = rng.choice(["shoes", "jacket", "headphones", "tee"])
    cands, key = family(rng, kind)
    target = rng.choice(cands)
    text = _instruction(target, key, target.attributes[key])
    chosen = _pick(cands, text)
    snap = _snap(chosen)
    changed = dict(chosen.attributes)
    if "material" in changed:
        changed["material"] = "Synthetic"
    elif kind == "headphones":
        changed["model"] = "QW-1"
    else:
        changed["color"] = rng.choice(["Grey", "Red", "Green"])
    if hard and key in changed:
        v = changed[key].split()
        changed[key] = " ".join(reversed(v))  # formatting noise on the key attribute; the real change is elsewhere
    v2 = ListingVersion(version=2, title=chosen.title, price=chosen.price, attributes=changed,
                        captured_at="2026-10-25T18:00:00Z")
    claim = ("The item is different from the listing." if not hard else
             rng.choice(["My AI agent bought the wrong thing.", "I think the agent messed up this order."]))
    # Some hard cases have no record of what was delivered: the evidence is insufficient by design.
    delivered_attrs = None if hard and i % 2 else changed
    return _bundle(f"F4-{i:03d}", mandate_text=text, required={key: chosen.attributes[key]}, candidates=cands,
                   chosen=chosen, history=[snap, v2],
                   delivery=Delivery(shipped=True, delivered=True, tracking=f"TRKF4{i}", attributes=delivered_attrs,
                                     shipped_at="2026-10-26T09:00:00Z"), claim=claim)


def gen_f5(rng, i, hard):
    kind = rng.choice(["shoes", "jacket", "headphones", "tee"])
    cands, key = family(rng, kind)
    target = rng.choice(cands)
    text = _instruction(target, key, target.attributes[key])
    chosen = _pick(cands, text)
    if hard:
        delivery = Delivery(shipped=True, delivered=False, tracking=f"TRKF5{i}", attributes=None,
                            shipped_at="2026-10-26T09:00:00Z")
        claim = rng.choice(["The agent ordered something I never got.", "Wrong item? I can't even find it."])
    else:
        delivery = Delivery(shipped=False, delivered=False)
        claim = rng.choice(["It never arrived.", "Package not received after two weeks.", "Nothing was delivered."])
    return _bundle(f"F5-{i:03d}", mandate_text=text, required={key: chosen.attributes[key]}, candidates=cands,
                   chosen=chosen, delivery=delivery, claim=claim, reason="ITEM_NOT_RECEIVED")


def gen_f6(rng, i, hard):
    kind = rng.choice(["shoes", "jacket", "headphones", "tee"])
    cands, key = family(rng, kind)
    target = rng.choice(cands)
    text = _instruction(target, key, target.attributes[key])
    chosen = _pick(cands, text)
    claim = rng.choice([
        "My AI agent bought the wrong item, I want a refund.",
        "The item is not as described at all.",
        "The listing said something different, this is a scam.",
        "Wrong size, the bot made a mistake.",
    ])
    buyer = None
    if hard:
        buyer = BuyerSignals(recent_dispute_times=[f"2026-10-{d:02d}T08:00:00Z" for d in (5, 11, 19, 27, 30)])
        claim = rng.choice(["It never arrived.", "I never authorized this purchase."])
    return _bundle(f"F6-{i:03d}", mandate_text=text, required={key: chosen.attributes[key]}, candidates=cands,
                   chosen=chosen, claim=claim, buyer=buyer)


GENERATORS = {"F1": gen_f1, "F2": gen_f2, "F3": gen_f3, "F4": gen_f4, "F5": gen_f5, "F6": gen_f6}


def generate() -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for label, gen in GENERATORS.items():
        n_hard = round(PER_CLASS * HARD_SHARE)
        for i in range(PER_CLASS):
            hard = i >= PER_CLASS - n_hard
            b = gen(rng, i, hard)
            rows.append({"id": b.case_id, "label": label, "hard": hard, "bundle": b.to_dict()})
    return rows


def main() -> None:
    rows = generate()
    out = ROOT / "data" / "agentdispute-150.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} cases to {out}")


if __name__ == "__main__":
    main()
