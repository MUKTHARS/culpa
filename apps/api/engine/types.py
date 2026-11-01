"""Engine input and output types. Plain dataclasses that round-trip through JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

FAULT_CLASSES = ("F1", "F2", "F3", "F4", "F5", "F6")
FAULT_NAMES = {
    "F1": "Mandate breach by agent",
    "F2": "Agent reasoning error",
    "F3": "Ambiguous instruction",
    "F4": "Merchant misrepresentation",
    "F5": "Fulfillment failure",
    "F6": "Friendly fraud",
}
PARTIES = ("buyer", "merchant", "agent_provider")


@dataclass
class Constraints:
    max_amount: str | None = None
    currency: str = "USD"
    max_quantity: int | None = None
    allowed_merchants: list[str] | None = None
    allowed_categories: list[str] | None = None
    expires_at: str | None = None
    required_attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Mandate:
    text: str
    constraints: Constraints
    signature_valid: bool = True


@dataclass
class Candidate:
    id: str
    title: str
    price: str
    category: str = ""
    merchant_id: str = ""
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Trace:
    policy: str
    instruction: str
    candidates: list[Candidate]
    chosen_id: str
    reasoning: str = ""


@dataclass
class ListingVersion:
    version: int
    title: str
    price: str
    attributes: dict[str, str]
    captured_at: str


@dataclass
class OrderInfo:
    amount: str
    currency: str = "USD"
    quantity: int = 1
    merchant_id: str = ""
    category: str = ""
    created_at: str | None = None
    approved_at: str | None = None


@dataclass
class Delivery:
    shipped: bool = False
    delivered: bool = False
    tracking: str | None = None
    attributes: dict[str, str] | None = None
    shipped_at: str | None = None


@dataclass
class Claim:
    reason: str = ""
    text: str = ""


@dataclass
class BuyerSignals:
    recent_dispute_times: list[str] = field(default_factory=list)
    ring_size: int = 1
    ring_fraud_count: int = 0


@dataclass
class Integrity:
    stored_root: str | None = None
    recomputed_root: str | None = None


@dataclass
class CaseBundle:
    case_id: str
    mandate: Mandate
    trace: Trace
    snapshot: ListingVersion
    order: OrderInfo
    delivery: Delivery
    claim: Claim
    listing_history: list[ListingVersion] = field(default_factory=list)
    buyer: BuyerSignals = field(default_factory=BuyerSignals)
    integrity: Integrity = field(default_factory=Integrity)
    now: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> CaseBundle:
        m = d["mandate"]
        t = d["trace"]
        return CaseBundle(
            case_id=d["case_id"],
            mandate=Mandate(text=m["text"], constraints=Constraints(**m["constraints"]),
                            signature_valid=m.get("signature_valid", True)),
            trace=Trace(policy=t["policy"], instruction=t["instruction"],
                        candidates=[Candidate(**c) for c in t["candidates"]],
                        chosen_id=t["chosen_id"], reasoning=t.get("reasoning", "")),
            snapshot=ListingVersion(**d["snapshot"]),
            order=OrderInfo(**d["order"]),
            delivery=Delivery(**d["delivery"]),
            claim=Claim(**d["claim"]),
            listing_history=[ListingVersion(**v) for v in d.get("listing_history", [])],
            buyer=BuyerSignals(**d.get("buyer", {})),
            integrity=Integrity(**d.get("integrity", {})),
            now=d.get("now"),
        )


@dataclass
class Evidence:
    check: str
    finding: str
    cite: str
    fault_class: str | None = None
    party: str | None = None
    weight: float = 0.0


@dataclass
class Verdict:
    fault_class: str | None
    fault_name: str | None
    split: dict[str, float]
    confidence: float
    action: str
    refund_amount: str | None
    liability: dict[str, str]
    evidence: list[Evidence]
    flags: list[str]
    check_order: list[list[str]]
    degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
