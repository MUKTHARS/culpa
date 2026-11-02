"""What kind of dispute this is, in the categories payment networks use.

The category comes from the dispute reason code (PayPal's, or the simulator's) first and the buyer's own words
second. It decides which questions the records can answer: a "never arrived" claim can be checked against the
delivery record; a "it arrived broken" claim cannot, so Culpa asks for evidence instead of guessing.

Categories and their real-world counterparts:
  not_received          PayPal Item Not Received, Visa 13.1, Mastercard 4855
  not_as_described      PayPal Significantly Not as Described, Visa 13.3, Mastercard 4853
  condition             damaged, defective, counterfeit, used or incomplete (Visa 13.3 / 13.4 counterfeit)
  unauthorized          PayPal Unauthorized Transaction, Visa 10.4, Mastercard 4837
  agent_error           "my agent bought the wrong thing" (agent purchases; no network code yet)
  changed_mind          buyer's remorse: excluded from PayPal Buyer Protection
  duplicate             Visa 12.6.1, Mastercard 4834 (processing error)
  incorrect_amount      Visa 12.5, Mastercard 4831 (processing error)
  credit_not_processed  Visa 13.6, Mastercard 4860 (refund promised, not received)
  canceled_recurring    Visa 13.2, Mastercard 4841 (subscription charged after cancelling)
  other                 anything else
"""

from __future__ import annotations

import re

CONDITION = "condition"
PROCESSING = ("duplicate", "incorrect_amount", "credit_not_processed", "canceled_recurring")

# PayPal Disputes API reasons, card-network style codes and the simulator's reasons.
_REASONS = {
    "ITEM_NOT_RECEIVED": "not_received",
    "MERCHANDISE_OR_SERVICE_NOT_RECEIVED": "not_received",
    "ITEM_NOT_AS_DESCRIBED": "not_as_described",
    "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED": "not_as_described",
    "UNAUTHORISED": "unauthorized",
    "UNAUTHORIZED": "unauthorized",
    "DUPLICATE_TRANSACTION": "duplicate",
    "INCORRECT_AMOUNT": "incorrect_amount",
    "CREDIT_NOT_PROCESSED": "credit_not_processed",
    "CANCELED_RECURRING_BILLING": "canceled_recurring",
    "PAYMENT_BY_OTHER_MEANS": "duplicate",
}

# Words override a generic reason: "not as described" + "it arrived broken" is a condition claim.
_WORDS: list[tuple[str, str]] = [
    ("duplicate", r"\b(charged twice|double charged|duplicate charge|two charges|billed twice)\b"),
    ("credit_not_processed", r"\b(refund (was )?(never|not) (received|processed|issued)|promised (a )?refund|never got my refund|returned it)\b"),
    ("canceled_recurring", r"\b(cancell?ed (my )?(subscription|membership|plan)|still (being )?charged after cancell?ing)\b"),
    ("incorrect_amount", r"\b(charged (more|too much|extra)|wrong amount|price was different|overcharged|higher than (the )?(listed|advertised))\b"),
    (CONDITION, r"\b(broken|damaged|defective|faulty|doesn'?t work|does not work|not working|cracked|scratched|torn|dented|"
                r"stopped working|counterfeit|fake|knock-?off|not genuine|used|second-?hand|missing (parts|pieces|accessories)|incomplete)\b"),
    ("changed_mind", r"\b(changed my mind|don'?t want it|do not want it|no longer (want|need)|found it cheaper|ordered by mistake)\b"),
    ("agent_error", r"\b(my (ai )?agent|the agent|the bot|assistant) (bought|ordered|picked|chose|purchased)\b"),
    ("unauthorized", r"\b(never authori[sz]ed|didn'?t authori[sz]e|not authori[sz]ed|unauthori[sz]ed|didn'?t make this purchase|someone else)\b"),
    ("not_received", r"\b(never arrived|not (been )?received|never received|didn'?t (receive|arrive|get)|never got|not delivered|lost in (the )?(mail|post|transit))\b"),
]


def classify(reason: str, text: str) -> str:
    words = (text or "").lower()
    for category, pattern in _WORDS:
        if re.search(pattern, words):
            return category
    return _REASONS.get((reason or "").upper(), "other")
