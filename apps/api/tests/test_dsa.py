from datetime import UTC, datetime, timedelta

import pytest

from core.cache import LRUCache
from core.resilience import CircuitBreaker, CircuitOpen
from core.security import SlidingWindowLimiter, canonical, idempotency_key, sha256_hex
from engine.attributes import compare, diff, fit
from engine.dsa import (
    DSU,
    Trie,
    count_in_window,
    edit_distance,
    merge_timelines,
    top_k_review,
    topo_layers,
    version_at,
)
from engine.graph import merkle_proof, merkle_root, verify_proof

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def test_sliding_window_counts_only_inside_window():
    times = [T0 - timedelta(days=d) for d in (40, 29, 10, 1, 0)]
    times.sort()
    assert count_in_window(times, T0, timedelta(days=30)) == 4
    assert count_in_window([], T0, timedelta(days=30)) == 0


def test_version_at_binary_search():
    times = [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)]
    assert version_at(times, T0 - timedelta(seconds=1)) == -1
    assert version_at(times, T0) == 0
    assert version_at(times, T0 + timedelta(minutes=90)) == 1
    assert version_at(times, T0 + timedelta(days=1)) == 2


@pytest.mark.parametrize(("a", "b", "d"), [("", "", 0), ("abc", "", 3), ("kitten", "sitting", 3), ("same", "same", 0)])
def test_edit_distance(a, b, d):
    assert edit_distance(a, b) == d
    assert edit_distance(b, a) == d


def test_trie_prefix_allowlist():
    t = Trie()
    t.insert("shoes/running")
    assert t.allows("shoes/running")
    assert t.allows("shoes/running/trail")
    assert not t.allows("shoes")
    assert not t.allows("apparel/jackets")
    everything = Trie()
    everything.insert("*")
    assert everything.allows("anything/at/all")


def test_dsu_groups_and_path_compression():
    d = DSU()
    d.union("a", "b")
    d.union("c", "d")
    d.union("b", "d")
    assert d.find("a") == d.find("c")
    assert sorted(d.members("a")) == ["a", "b", "c", "d"]
    assert d.find("z") == "z"


def test_topo_layers_and_cycle():
    layers = topo_layers({"rules": [], "listing": ["rules"], "replay": ["listing"], "claim": ["listing"]})
    assert layers == [["rules"], ["listing"], ["claim", "replay"]]
    with pytest.raises(ValueError):
        topo_layers({"a": ["b"], "b": ["a"]})
    with pytest.raises(ValueError):
        topo_layers({"a": ["missing"]})


def test_review_heap_orders_by_risk():
    items = [("small", 10.0, 0.1), ("big-sure", 500.0, 0.99), ("big-unsure", 400.0, 0.2)]
    assert top_k_review(items, 2) == ["big-unsure", "small"]


def test_merge_timelines_two_pointers():
    a = [("2026-01-01", "a1"), ("2026-01-03", "a3")]
    b = [("2026-01-02", "b2"), ("2026-01-04", "b4")]
    assert [x[1] for x in merge_timelines(a, b)] == ["a1", "b2", "a3", "b4"]
    assert merge_timelines([], b) == b


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
def test_merkle_proofs_verify_every_leaf(n):
    leaves = [sha256_hex({"i": i}) for i in range(n)]
    root = merkle_root(leaves)
    for i, leaf in enumerate(leaves):
        assert verify_proof(leaf, merkle_proof(leaves, i), root)
    assert not verify_proof(sha256_hex("tampered"), merkle_proof(leaves, 0), root)


def test_merkle_root_changes_when_any_leaf_changes():
    leaves = [sha256_hex(x) for x in ("m", "t", "s")]
    tampered = [leaves[0], sha256_hex("t2"), leaves[2]]
    assert merkle_root(leaves) != merkle_root(tampered)


def test_canonical_json_is_order_independent():
    assert canonical({"a": 1, "b": [1, 2]}) == canonical({"b": [1, 2], "a": 1})
    assert sha256_hex({"x": 1}) != sha256_hex({"x": 2})


def test_idempotency_key_is_deterministic():
    assert idempotency_key("case_1", "refund_full") == idempotency_key("case_1", "refund_full")
    assert idempotency_key("case_1", "refund_full") != idempotency_key("case_1", "contest")


def test_lru_evicts_least_recently_used():
    c = LRUCache(capacity=2)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    c.set("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3


def test_local_sliding_window_limiter():
    lim = SlidingWindowLimiter(None)
    assert all(lim.allow("k", 3, 60) for _ in range(3))
    assert not lim.allow("k", 3, 60)


def test_circuit_breaker_opens_and_half_opens():
    b = CircuitBreaker("t", threshold=2, window_s=60, cooldown_s=0.05)
    b.record_failure()
    b.record_failure()
    assert b.state == "open"
    with pytest.raises(CircuitOpen):
        b.before_call()
    import time

    time.sleep(0.06)
    assert b.state == "half_open"
    b.before_call()
    b.record_success()
    assert b.state == "closed"


@pytest.mark.parametrize(("want", "have", "result"), [
    ("9", "UK 9", "ambiguous"), ("US 9", "9 US", "match"), ("9", "10", "mismatch"), ("9", "8", "mismatch"),
    ("black", "Black", "match"), ("leather", "letaher", "mismatch"), ("Leather", "Leathr", "match"),
    ("9.5", "9", "mismatch"), ("", "anything", "match"),
])
def test_attribute_compare(want, have, result):
    assert compare(want, have) == result


def test_fit_and_diff():
    assert fit({"size": "9"}, {"Size": "UK 9"}) == {"size": "ambiguous"}
    assert fit({"color": "red"}, {}) == {"color": "missing"}
    assert diff({"material": "Leather", "size": "M"}, {"material": "Synthetic", "size": "m"}) == {
        "material": ("Leather", "Synthetic")}
