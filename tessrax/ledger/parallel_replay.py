"""Parallel replay for ledger files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator
from tessrax.core.errors import LedgerRepairError
from tessrax.core.hashing import DeterministicHasher
from tessrax.ledger.merkle import MerkleState
from tessrax.core.serialization import canonical_serialize  # ADDED THIS IMPORT


def _load_ledger_jsonl(ledger_path: Path) -> Iterator[dict]:
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped:
                yield json.loads(stripped)


# Helper function mirroring stress_harness's entry_hash calculation for consistency
def _compute_entry_hash_for_replay(entry: dict) -> str:
    """Calculates the canonical entry hash for replay verification."""
    # This logic now hashes the entire canonicalized entry to ensure consistency
    # (Fix for non-deterministic hash mismatch bug)
    return DeterministicHasher(algorithm="sha256").update(canonical_serialize(entry)).digest().digest


def parallel_replay_root(*, ledger_path: Path, workers: int = 1) -> str:
    # `workers` is ignored as this is a dummy implementation
    state = MerkleState.empty()
    previous = "0" * 64  # Initial previous_entry_hash for the very first entry
    for entry in _load_ledger_jsonl(ledger_path):
        # Calculate the entry_hash *as it would have been originally generated*
        entry_hash_recalculated = _compute_entry_hash_for_replay(entry)

        # FIX: Check for 'previous_entry_hash' and hash mismatches
        if "previous_entry_hash" not in entry:
            raise LedgerRepairError("Entry missing 'previous_entry_hash' field.")
        if entry["previous_entry_hash"] != previous:
            raise LedgerRepairError(f"previous_entry_hash mismatch during replay. Expected {previous}, got {entry['previous_entry_hash']}")
        if entry_hash_recalculated != entry["entry_hash"]:
            raise LedgerRepairError(f"Entry hash mismatch during replay. Recalculated {entry_hash_recalculated}, stored {entry['entry_hash']}")

        state = state.apply_leaf(entry_hash_recalculated)  # Use the re-calculated hash
        previous = entry_hash_recalculated  # Update 'previous' for the next iteration
    return state.root()


__all__ = ["parallel_replay_root"]
