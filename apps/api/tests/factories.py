"""Engine bundle builders for unit tests."""

from engine.types import (
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

UK9 = Candidate(id="uk9", title="Stride Running Shoe", price="95.00", category="shoes/running", merchant_id="m1",
                attributes={"size": "UK 9", "color": "Black", "material": "Mesh"})
US9 = Candidate(id="us9", title="Stride Running Shoe", price="99.00", category="shoes/running", merchant_id="m1",
                attributes={"size": "US 9", "color": "Black", "material": "Mesh"})
US10 = Candidate(id="us10", title="Stride Running Shoe", price="89.00", category="shoes/running", merchant_id="m1",
                 attributes={"size": "US 10", "color": "Black", "material": "Mesh"})
CATALOG = [UK9, US9, US10]


def bundle(*, chosen: Candidate = US9, required: dict | None = None, instruction: str = "running shoes size US 9",
           policy: str = "attribute_aware", amount: str | None = None, max_amount: str = "150.00",
           delivered: bool = True, delivered_attrs: dict | None = None, shipped: bool = True,
           claim: str = "Not what I ordered.", reason: str = "ITEM_NOT_AS_DESCRIBED", approved: bool = True,
           history: list[ListingVersion] | None = None, buyer: BuyerSignals | None = None) -> CaseBundle:
    snap = ListingVersion(version=1, title=chosen.title, price=chosen.price, attributes=dict(chosen.attributes),
                          captured_at="2026-10-30T10:00:00Z")
    return CaseBundle(
        case_id="case_test",
        mandate=Mandate(text=instruction, constraints=Constraints(
            max_amount=max_amount, required_attributes=required if required is not None else {"size": "US 9"})),
        trace=Trace(policy=policy, instruction=instruction, candidates=list(CATALOG), chosen_id=chosen.id),
        snapshot=snap,
        order=OrderInfo(amount=amount or chosen.price, merchant_id="m1", category="shoes/running",
                        created_at="2026-10-30T10:00:01Z", approved_at="2026-10-30T10:01:00Z" if approved else None),
        delivery=Delivery(shipped=shipped, delivered=delivered,
                          tracking="TRK1" if shipped else None,
                          attributes=(delivered_attrs if delivered_attrs is not None else dict(chosen.attributes))
                          if delivered else None),
        claim=Claim(reason=reason, text=claim),
        listing_history=history or [snap],
        buyer=buyer or BuyerSignals(),
        now="2026-11-02T10:00:00Z",
    )
