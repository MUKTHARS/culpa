"""Check 1: hard mandate constraints. No AI. A breach is decisive (F1, confidence 1.0)."""

from __future__ import annotations

from decimal import Decimal

from core.ids import parse_iso
from engine.dsa import Trie
from engine.types import CaseBundle, Evidence


def _breach(finding: str, cite: str) -> Evidence:
    return Evidence(check="rules", finding=finding, cite=cite, fault_class="F1", party="agent_provider", weight=1.0)


def run(b: CaseBundle) -> list[Evidence]:
    c = b.mandate.constraints
    o = b.order
    out: list[Evidence] = []

    amount = Decimal(o.amount)
    if c.max_amount is not None and amount > Decimal(c.max_amount):
        out.append(_breach(f"Order total {o.currency} {amount} exceeds the mandate cap of {c.currency} {c.max_amount}.",
                           "mandate.constraints.max_amount vs order.amount"))
    if c.currency and o.currency != c.currency:
        out.append(_breach(f"Order currency {o.currency} differs from the mandate currency {c.currency}.",
                           "mandate.constraints.currency"))
    if c.max_quantity is not None and o.quantity > c.max_quantity:
        out.append(_breach(f"Quantity {o.quantity} exceeds the mandate limit of {c.max_quantity}.",
                           "mandate.constraints.max_quantity"))
    if c.allowed_merchants and o.merchant_id not in c.allowed_merchants:
        out.append(_breach(f"Merchant {o.merchant_id} is not on the mandate allowlist.",
                           "mandate.constraints.allowed_merchants"))
    if c.allowed_categories:
        trie = Trie()
        for cat in c.allowed_categories:
            trie.insert(cat)
        if not trie.allows(o.category):
            out.append(_breach(f"Category '{o.category}' is outside the mandate categories "
                               f"{', '.join(c.allowed_categories)}.", "mandate.constraints.allowed_categories"))
    if c.expires_at and o.created_at:
        expires, created = parse_iso(c.expires_at), parse_iso(o.created_at)
        if expires and created and created > expires:
            out.append(_breach(f"Order placed at {o.created_at}, after the mandate expired at {c.expires_at}.",
                               "mandate.constraints.expires_at"))
    if not out:
        out.append(Evidence(check="rules", finding="Order is within every hard limit of the signed mandate.",
                            cite="mandate.constraints"))
    return out
