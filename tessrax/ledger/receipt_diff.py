"""Semantic diff utilities for ledger receipts."""
from __future__ import annotations

from typing import List, Mapping, Any
from tessrax.core.serialization import canonical_serialize  # Added import here


def semantic_diff(left: Mapping[str, object], right: Mapping[str, object]) -> List[tuple[str, object, object]]:
    differences: List[tuple[str, object, object]] = []
    keys = set(left) | set(right)
    for key in sorted(keys):
        l_val = left.get(key)
        r_val = right.get(key)
        if l_val != r_val:
            differences.append((key, l_val, r_val))
    return differences


def calculate_delta_diff(list_a: List[Any], list_b: List[Any]) -> Mapping[str, List[Any]]:
    """Calculates the delta (added, removed, modified) between two lists of ledger entries.

    Entries are compared based on their canonical serialization and assumed to have
    a unique 'id' field for identifying modifications.
    """
    # Canonicalize and index entries from list_a
    a_canonical_map = {
        entry.get('id'): canonical_serialize(entry) for entry in list_a
    }
    a_original_map = {
        entry.get('id'): entry for entry in list_a
    }

    # Canonicalize and index entries from list_b
    b_canonical_map = {
        entry.get('id'): canonical_serialize(entry) for entry in list_b
    }
    b_original_map = {
        entry.get('id'): entry for entry in list_b
    }

    added = []
    removed = []
    modified = []

    # Check for added and modified entries in list_b compared to list_a
    for b_id, b_canonical_entry in b_canonical_map.items():
        if b_id is not None:
            if b_id not in a_canonical_map:
                added.append(b_original_map[b_id])
            elif b_canonical_entry != a_canonical_map[b_id]:
                modified.append(b_original_map[b_id])

    # Check for removed entries in list_a compared to list_b
    for a_id, _ in a_canonical_map.items():
        if a_id is not None:
            if a_id not in b_canonical_map:
                removed.append(a_original_map[a_id])

    return {
        'added': added,
        'removed': removed,
        'modified': modified
    }


__all__ = ["semantic_diff", "calculate_delta_diff"]
