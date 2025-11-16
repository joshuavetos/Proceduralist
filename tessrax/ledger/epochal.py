"""Epoch management utilities for the Tessrax ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from tessrax.core.errors import EpochError
from tessrax.core.time import canonical_datetime
from tessrax.ledger.merkle import MerkleState

EPOCH_STATE_PATH = Path("tessrax/ledger/epoch_state.json")
SNAPSHOT_PATTERN = "merkle_state-{epoch_id}.json"


class EpochLedgerManager:
    """Assigns canonical epoch IDs to ledger entries and exports snapshots."""

    def __init__(
        self,
        *,
        state_path: Path = EPOCH_STATE_PATH,
        snapshot_dir: Path | None = None,
    ) -> None:
        self.state_path = state_path
        self.snapshot_dir = snapshot_dir or state_path.parent

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"next_epoch": 0, "entries": {}}
        raw = self.state_path.read_bytes()
        if not raw.strip():
            return {"next_epoch": 0, "entries": {}}
        data = json.loads(raw.decode("utf-8"))
        data.setdefault("entries", {})
        data.setdefault("next_epoch", 0)
        return data

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _snapshot_path(self, epoch_id: str) -> Path:
        return self.snapshot_dir / SNAPSHOT_PATTERN.format(epoch_id=epoch_id)

    def record_entry(
        self,
        *,
        entry_hash: str,
        timestamp: str,
        merkle_state: MerkleState,
    ) -> str:
        if len(entry_hash) != 64:
            raise EpochError("entry_hash must be 64 hex chars", details={"entry_hash": entry_hash})
        state = self._load_state()
        entries = state["entries"]
        if entry_hash in entries:
            return entries[entry_hash]["epoch_id"]
        epoch_id = f"EPOCH-{state['next_epoch']:020d}-{entry_hash[:16]}"
        entries[entry_hash] = {
            "epoch_id": epoch_id,
            "timestamp": timestamp,
            "merkle_root": merkle_state.root(),
        }
        state["next_epoch"] = state.get("next_epoch", 0) + 1
        state["updated_at"] = canonical_datetime()
        self._save_state(state)
        snapshot_path = self._snapshot_path(epoch_id)
        snapshot_payload = {
            "epoch_id": epoch_id,
            "merkle_state": merkle_state.to_payload(),
            "exported_at": canonical_datetime(),
        }
        snapshot_path.write_text(json.dumps(snapshot_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return epoch_id

    def get_epoch(self, entry_hash: str) -> str:
        state = self._load_state()
        entries = state.get("entries", {})
        if entry_hash not in entries:
            raise EpochError("Entry hash not found in epoch table", details={"entry_hash": entry_hash})
        return entries[entry_hash]["epoch_id"]


__all__ = ["EpochLedgerManager", "EPOCH_STATE_PATH"]
