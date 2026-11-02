"""Check 2: did the merchant deliver what the listing promised at purchase time?"""

from __future__ import annotations

from core.ids import parse_iso
from engine.attributes import diff
from engine.dsa import version_at
from engine.types import CaseBundle, Evidence


def run(b: CaseBundle) -> list[Evidence]:
    d = b.delivery
    out: list[Evidence] = []

    if not d.delivered:
        if not d.shipped and not d.tracking:
            out.append(Evidence(check="listing", finding="No shipment and no tracking number were ever recorded.",
                                cite="delivery", fault_class="F5", party="merchant", weight=0.9))
        else:
            out.append(Evidence(check="listing",
                                finding=f"Shipped (tracking {d.tracking or 'n/a'}) but delivery was never confirmed. "
                                        "Without proof of delivery, a not-received claim goes to the buyer.",
                                cite="delivery.tracking", fault_class="F5", party="merchant", weight=0.7))
        return out

    if d.attributes is None:
        out.append(Evidence(check="listing", finding="Delivered, but no description of the delivered item was recorded.",
                            cite="delivery.attributes"))
        return out

    changed = diff(b.snapshot.attributes, d.attributes)
    if not changed:
        out.append(Evidence(check="listing", finding="Delivered item matches the listing captured at purchase.",
                            cite=f"snapshot v{b.snapshot.version} vs delivery"))
        return out

    parts = [f"{k}: listed '{old}', delivered '{new}'" for k, (old, new) in changed.items()]
    cite = f"snapshot v{b.snapshot.version} vs delivery"

    history = sorted(b.listing_history, key=lambda v: v.captured_at)
    later = [v for v in history if v.version > b.snapshot.version and diff(b.snapshot.attributes, v.attributes)]
    if later:
        first = later[0]
        parts.append(f"listing was edited to v{first.version} at {first.captured_at}, after purchase")
        cite += f"; listing v{first.version}"

    if b.order.created_at and history:
        times = [parse_iso(v.captured_at) for v in history]
        idx = version_at(times, parse_iso(b.order.created_at))
        if idx >= 0 and history[idx].version != b.snapshot.version:
            parts.append(f"note: listing v{history[idx].version} was live at order time, snapshot is v{b.snapshot.version}")

    out.append(Evidence(check="listing", finding="Delivered item differs from the listing: " + "; ".join(parts) + ".",
                        cite=cite, fault_class="F4", party="merchant", weight=0.9))
    return out
