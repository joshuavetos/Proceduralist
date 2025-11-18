"""Ledger replay engine for deterministic state verification."""
from __future__ import annotations
from typing import List, Any
from tessrax.core.merkle import MerkleTree
from tessrax.core.serialization import canonical_serialize  # Import for deterministic sorting


class LedgerReplayEngine:
    """Replays ledger events to deterministically verify state and consistency."""
    def __init__(self, ledger_entries: List[Any]) -> None:
        if not ledger_entries:
            raise ValueError("Ledger entries cannot be empty for replay engine construction.")
        # Sort the ledger_entries deterministically by their canonical serialization
        # This ensures that even if the input list order changes, the Merkle tree will be built consistently.
        sorted_entries = sorted(ledger_entries, key=lambda entry: canonical_serialize(entry))
        self._merkle_tree = MerkleTree(sorted_entries)

    def get_merkle_root(self) -> str:
        """Returns the Merkle root hash of the replayed ledger."""
        return self._merkle_tree.root_hash


__all__ = ["LedgerReplayEngine"]
