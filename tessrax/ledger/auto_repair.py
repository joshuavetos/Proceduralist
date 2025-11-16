"""Ledger corruption auto-repair utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from tessrax.core.errors import LedgerRepairError
from tessrax.core.time import canonical_datetime
from tessrax.ledger.index_backend import IndexEntry, LedgerIndexBackend
from tessrax.ledger.merkle import MerkleAccumulator, MerkleState
from tessrax.ledger.parallel_replay import parallel_replay_root

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
INDEX_PATH = Path("tessrax/ledger/index.db")


def _load_entries(ledger_path: Path) -> List[dict]:
    if not ledger_path.exists():
        return []
    entries: List[dict] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def rebuild_index_from_ledger(
    *,
    ledger_path: Path = LEDGER_PATH,
    index_path: Path = INDEX_PATH,
) -> int:
    backend = LedgerIndexBackend(index_path=index_path)
    backend.ensure_schema()
    entries = _load_entries(ledger_path)
    backend.rebuild(
        IndexEntry(
            ledger_offset=idx,
            event_type=entry["event_type"],
            state_hash=entry["audited_state_hash"],
            payload_hash=entry["payload_hash"],
            timestamp=entry["timestamp"],
            merkle_root=entry["merkle_root"],
            entry_hash=entry["entry_hash"],
            previous_entry_hash=entry.get("previous_entry_hash"),
        )
        for idx, entry in enumerate(entries)
    )
    return len(entries)


def auto_repair(
    *,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    index_path: Path = INDEX_PATH,
) -> dict:
    entries = _load_entries(ledger_path)
    if not entries:
        raise LedgerRepairError("Ledger empty; nothing to repair")
    observed_root = parallel_replay_root(ledger_path=ledger_path)
    persisted_state = MerkleAccumulator(state_path=merkle_state_path)
    if persisted_state.state.root() != observed_root:
        persisted_state.state = MerkleState.empty()
        for entry in entries:
            persisted_state.state = persisted_state.state.apply_leaf(entry["entry_hash"])
        persisted_state._persist_state()  # type: ignore[attr-defined]
    rebuilt = rebuild_index_from_ledger(ledger_path=ledger_path, index_path=index_path)
    report = {
        "repaired_at": canonical_datetime(),
        "entries_replayed": len(entries),
        "index_entries": rebuilt,
        "merkle_root": observed_root,
    }
    (ledger_path.with_suffix(".repair.json")).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["auto_repair", "rebuild_index_from_ledger"]
