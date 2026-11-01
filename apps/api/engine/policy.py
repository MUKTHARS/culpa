"""Settlement policy. Code, not the model, decides what happens to money."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SHARE_THRESHOLD = 0.7

ACTIONS = ("refund_full", "refund_partial", "contest", "review")


def _money(x: Decimal) -> str:
    return str(x.quantize(CENT, rounding=ROUND_HALF_UP))


def decide(fault_class: str | None, split: dict[str, float], confidence: float, amount: str,
           threshold: float = 0.8) -> tuple[str, str | None, dict[str, str]]:
    """Returns (action, refund_amount, liability per party)."""
    if fault_class is None or confidence < threshold:
        return "review", None, {}

    total = Decimal(amount)
    merchant = Decimal(str(split.get("merchant", 0.0)))
    agent = Decimal(str(split.get("agent_provider", 0.0)))
    buyer = Decimal(str(split.get("buyer", 0.0)))

    if buyer >= Decimal(str(SHARE_THRESHOLD)):
        return "contest", None, {"buyer": _money(total)}
    if merchant >= Decimal(str(SHARE_THRESHOLD)):
        return "refund_full", _money(total), {"merchant": _money(total)}
    if agent >= Decimal(str(SHARE_THRESHOLD)):
        return "refund_full", _money(total), {"agent_provider": _money(total)}

    refund = (total * (merchant + agent)).quantize(CENT, rounding=ROUND_HALF_UP)
    if refund <= 0:
        return "contest", None, {"buyer": _money(total)}
    liability = {p: _money(total * s) for p, s in (("merchant", merchant), ("agent_provider", agent), ("buyer", buyer))
                 if s > 0}
    return "refund_partial", _money(refund), liability
