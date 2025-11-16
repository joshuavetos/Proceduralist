"""Parallel Merkle replay helpers."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, List, Tuple

from tessrax.core.errors import LedgerRepairError
from tessrax.ledger.merkle import MerkleState, compute_entry_hash

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")


def _parse_entries(ledger_path: Path) -> List[dict]:
    if not ledger_path.exists():
        raise LedgerRepairError("Ledger path missing", details={"ledger_path": str(ledger_path)})
    entries: List[dict] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped:
                entry = json.loads(stripped)
                entries.append(entry)
    return entries


def _compute_hash(entry: dict) -> Tuple[str, dict]:
    return compute_entry_hash(entry), entry


def parallel_replay_root(*, ledger_path: Path = LEDGER_PATH, workers: int = 4) -> str:
    entries = _parse_entries(ledger_path)
    if not entries:
        return MerkleState.empty().root()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        hash_results = list(executor.map(_compute_hash, entries))
    state = MerkleState.empty()
    previous: str | None = None
    for entry_hash, entry in hash_results:
        if entry.get("previous_entry_hash") != previous:
            raise LedgerRepairError("previous_entry_hash mismatch during replay")
        if entry_hash != entry["entry_hash"]:
            raise LedgerRepairError("Entry hash mismatch during replay")
        state = state.apply_leaf(entry_hash)
        previous = entry_hash
    return state.root()


__all__ = ["parallel_replay_root"]
