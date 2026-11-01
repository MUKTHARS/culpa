import pytest

from engine.agent_policy import NoMatch, attribute_aware, parse_budget, price_first, relates_to
from engine.llm import LLMUnavailable
from engine.pipeline import analyze
from engine.policy import decide
from engine.types import BuyerSignals, CaseBundle, Integrity, ListingVersion
from tests.factories import CATALOG, UK9, US10, bundle


def test_agent_policies():
    assert attribute_aware("running shoes size 9 under $120", CATALOG)[0] == "uk9"  # cheapest among equal matches
    assert attribute_aware("running shoes size 9 US under $120", CATALOG)[0] == "us9"
    assert attribute_aware("running shoes size UK 9", CATALOG)[0] == "uk9"
    assert price_first("anything", CATALOG)[0] == "us10"
    assert str(parse_budget("shoes under $120.50")) == "120.50"
    assert parse_budget("shoes please") is None


def test_f1_over_budget_is_decisive():
    v = analyze(bundle(amount="200.00", max_amount="150.00"))
    assert v.fault_class == "F1"
    assert v.confidence == 1.0
    assert v.action == "refund_full"
    assert v.liability == {"agent_provider": "200.00"}
    assert "decided_by_rules" in v.flags


def test_f2_explicit_attribute_ignored_by_flawed_agent():
    v = analyze(bundle(chosen=US10, policy="price_first", instruction="running shoes size US 9",
                       claim="Wrong size, I asked for US 9."))
    assert v.fault_class == "F2"
    assert v.split["agent_provider"] == 1.0
    assert v.action == "refund_full"


def test_f3_ambiguous_size_resolved_by_replay():
    v = analyze(bundle(chosen=UK9, required={"size": "9"}, instruction="running shoes size 9",
                       claim="I wanted US 9, they sent UK 9."))
    assert v.fault_class == "F3"
    assert any("clarified instruction" in e.finding for e in v.evidence)
    assert v.split["buyer"] > v.split["agent_provider"] > 0
    assert v.action == "refund_partial"
    assert v.refund_amount is not None


def test_f4_listing_changed_after_purchase():
    snap = ListingVersion(version=1, title="Stride Running Shoe", price="99.00",
                          attributes={"size": "US 9", "color": "Black", "material": "Mesh"},
                          captured_at="2026-10-30T10:00:00Z")
    edited = ListingVersion(version=2, title="Stride Running Shoe", price="99.00",
                            attributes={"size": "US 9", "color": "Black", "material": "Synthetic"},
                            captured_at="2026-10-31T09:00:00Z")
    v = analyze(bundle(delivered_attrs=edited.attributes, history=[snap, edited],
                       claim="The shoes are synthetic, the listing said mesh."))
    assert v.fault_class == "F4"
    assert v.split["merchant"] == 1.0
    assert v.action == "refund_full"
    assert any("edited to v2" in e.finding for e in v.evidence)


def test_f5_never_shipped():
    v = analyze(bundle(delivered=False, shipped=False, reason="ITEM_NOT_RECEIVED", claim="Never arrived."))
    assert v.fault_class == "F5"
    assert v.action == "refund_full"
    assert v.liability == {"merchant": "99.00"}


def test_f6_claim_contradicts_evidence():
    v = analyze(bundle(claim="My AI agent bought the wrong thing, refund me."))
    assert v.fault_class == "F6"
    assert v.action == "contest"


def test_f6_velocity_signal_adds_weight():
    buyer = BuyerSignals(recent_dispute_times=[f"2026-10-{d:02d}T00:00:00Z" for d in (20, 22, 25, 28, 30)])
    v = analyze(bundle(buyer=buyer))
    assert v.fault_class == "F6"
    assert any("disputes in the last 30 days" in e.finding for e in v.evidence)


def test_tampered_evidence_goes_to_review():
    b = bundle()
    b.integrity = Integrity(stored_root="a" * 64, recomputed_root="b" * 64)
    v = analyze(b)
    assert v.action == "review"
    assert "evidence_tampered" in v.flags


def test_nondeterministic_replay_caps_confidence():
    # recorded choice disagrees with what the policy picks on the same inputs
    v = analyze(bundle(chosen=UK9, required={"size": "US 9"}, instruction="running shoes size US 9"))
    assert "nondeterministic" in v.flags
    assert v.confidence <= 0.6
    assert v.action == "review"


def test_bundle_round_trips_through_dict():
    b = bundle()
    assert CaseBundle.from_dict(b.to_dict()) == b


def test_policy_mixed_split_partial_refund():
    action, refund, liability = decide("F3", {"buyer": 0.6, "merchant": 0.0, "agent_provider": 0.4}, 0.9, "100.00")
    assert action == "refund_partial"
    assert refund == "40.00"
    assert liability == {"agent_provider": "40.00", "buyer": "60.00"}
    assert decide("F4", {"buyer": 0, "merchant": 1, "agent_provider": 0}, 0.5, "10.00")[0] == "review"


def test_ambiguity_without_qualifier_in_claim_goes_to_review():
    v = analyze(bundle(chosen=US10, policy="price_first", required={"size": "10"}, instruction="shoes size 10",
                       claim="Not happy with this."))
    assert v.fault_class == "F3"
    assert v.action == "review"


def test_agent_refuses_when_nothing_matches_the_instruction():
    with pytest.raises(NoMatch):
        attribute_aware("shirt", CATALOG)
    assert relates_to("something under $50", "Stride Running Shoe", "shoes/running", {})  # no product words: no limit


def test_unrelated_purchase_is_agent_fault_not_friendly_fraud():
    # "shirt" with no required attributes, and the agent bought shoes: the item "fits" vacuously, but it is not
    # what the buyer asked for. Culpa must blame the agent, never accuse the buyer.
    v = analyze(bundle(instruction="shirt", required={}, claim="I wanted US 9, they sent UK 9."))
    assert v.fault_class == "F2"
    assert v.split["agent_provider"] == 1.0
    assert not any(e.fault_class == "F6" for e in v.evidence)


class NoCreditLLM:
    """Every call fails the way an Anthropic account without credit does."""

    fast_model = "claude-haiku-5-5"

    def _fail(self, *_, **__):
        raise LLMUnavailable("Anthropic account has no credit left")

    choose_product = clarify = judge_claim = _fail


def test_claude_outage_falls_back_to_rule_based_verdicts_without_capping():
    llm = NoCreditLLM()
    f3 = analyze(bundle(chosen=UK9, required={"size": "9"}, instruction="running shoes size 9",
                        claim="I wanted US 9, they sent UK 9."), llm=llm)
    assert f3.fault_class == "F3" and f3.action == "refund_partial"
    assert "llm_unavailable" in f3.flags and not f3.degraded
    f6 = analyze(bundle(claim="It never arrived."), llm=llm)
    assert f6.fault_class == "F6" and f6.action == "contest" and f6.confidence >= 0.8
