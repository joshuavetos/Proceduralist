"""Semantic diff utilities for ledger receipts."""
from __future__ import annotations

from typing import List, Mapping


def semantic_diff(left: Mapping[str, object], right: Mapping[str, object]) -> List[tuple[str, object, object]]:
    differences: List[tuple[str, object, object]] = []
    keys = set(left) | set(right)
    for key in sorted(keys):
        l_val = left.get(key)
        r_val = right.get(key)
        if l_val != r_val:
            differences.append((key, l_val, r_val))
    return differences


__all__ = ["semantic_diff"]
