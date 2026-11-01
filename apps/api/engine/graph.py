"""Merkle tree over evidence hashes: one root per order, and inclusion proofs for single items."""

from __future__ import annotations

import hashlib


def _h(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    """Recursive pairwise hashing. An odd level duplicates its last node."""
    if not leaves:
        return _h("")
    if len(leaves) == 1:
        return leaves[0]
    level = leaves if len(leaves) % 2 == 0 else [*leaves, leaves[-1]]
    parents = [_h(a + b) for a, b in zip(level[::2], level[1::2], strict=True)]
    return merkle_root(parents)


def merkle_proof(leaves: list[str], index: int) -> list[tuple[str, str]]:
    """Sibling hashes from leaf to root: [(side, hash)], side 'L' or 'R' is the sibling's position."""
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    proof: list[tuple[str, str]] = []
    level = list(leaves)
    i = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling = i ^ 1
        proof.append(("L" if sibling < i else "R", level[sibling]))
        level = [_h(a + b) for a, b in zip(level[::2], level[1::2], strict=True)]
        i //= 2
    return proof


def verify_proof(leaf: str, proof: list[tuple[str, str]], root: str) -> bool:
    node = leaf
    for side, sibling in proof:
        node = _h(sibling + node) if side == "L" else _h(node + sibling)
    return node == root
