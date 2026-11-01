"""Data structures and algorithms used by the engine and services. Each one is unit-tested."""

from __future__ import annotations

import heapq
from bisect import bisect_right
from collections import deque
from collections.abc import Sequence
from datetime import datetime, timedelta


def count_in_window(times: Sequence[datetime], now: datetime, window: timedelta) -> int:
    """Sliding window over sorted timestamps: events in (now - window, now]. O(log n) via binary search."""
    lo = bisect_right(times, now - window)
    hi = bisect_right(times, now)
    return hi - lo


def version_at(times: Sequence[datetime], t: datetime) -> int:
    """Index of the last version captured at or before t, or -1. `times` must be sorted ascending."""
    return bisect_right(times, t) - 1


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, iterative two-row DP: O(m*n) time, O(min(m, n)) memory."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Trie:
    """Prefix tree over '/'-separated category paths. 'shoes' allows 'shoes/running/trail'."""

    __slots__ = ("children", "terminal")

    def __init__(self):
        self.children: dict[str, Trie] = {}
        self.terminal = False

    def insert(self, path: str) -> None:
        node = self
        for part in _path_parts(path):
            node = node.children.setdefault(part, Trie())
        node.terminal = True

    def allows(self, path: str) -> bool:
        node = self
        if node.terminal:
            return True
        for part in _path_parts(path):
            node = node.children.get(part)
            if node is None:
                return False
            if node.terminal:
                return True
        return False


def _path_parts(path: str) -> list[str]:
    return [p for p in path.strip().lower().split("/") if p and p != "*"]


class DSU:
    """Union-find with path compression and union by size."""

    def __init__(self):
        self.parent: dict[str, str] = {}
        self.size: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1
            return x
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> str:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return ra

    def members(self, x: str) -> list[str]:
        root = self.find(x)
        return [k for k in list(self.parent) if self.find(k) == root]


def review_priority(amount: float, confidence: float) -> float:
    """Riskiest money first: amount x uncertainty."""
    return amount * (1.0 - confidence)


def top_k_review(items: list[tuple[str, float, float]], k: int) -> list[str]:
    """items = (case_id, amount, confidence). Max-heap via negated priority; O(n log k)."""
    heap: list[tuple[float, str]] = []
    for case_id, amount, confidence in items:
        entry = (review_priority(amount, confidence), case_id)
        if len(heap) < k:
            heapq.heappush(heap, entry)
        elif entry > heap[0]:
            heapq.heapreplace(heap, entry)
    return [cid for _, cid in sorted(heap, reverse=True)]


def merge_timelines(a: list[tuple[str, str]], b: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Two-pointer merge of two (iso_time, label) lists already sorted by time."""
    i = j = 0
    out: list[tuple[str, str]] = []
    while i < len(a) and j < len(b):
        if a[i][0] <= b[j][0]:
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    out.extend(a[i:])
    out.extend(b[j:])
    return out


def topo_layers(deps: dict[str, list[str]]) -> list[list[str]]:
    """Kahn's algorithm. Each layer only depends on earlier layers, so a layer can run in parallel."""
    indeg = {k: 0 for k in deps}
    children: dict[str, list[str]] = {k: [] for k in deps}
    for node, parents in deps.items():
        for p in parents:
            if p not in deps:
                raise ValueError(f"unknown dependency {p!r} of {node!r}")
            indeg[node] += 1
            children[p].append(node)
    layer = deque(sorted(k for k, d in indeg.items() if d == 0))
    layers: list[list[str]] = []
    seen = 0
    while layer:
        current = list(layer)
        layers.append(current)
        seen += len(current)
        nxt: list[str] = []
        for node in current:
            for c in children[node]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    nxt.append(c)
        layer = deque(sorted(nxt))
    if seen != len(deps):
        raise ValueError("cycle in dependency graph")
    return layers
