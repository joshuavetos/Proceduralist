"""Ledger corruption auto-repair utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Any, Optional, Dict
from dataclasses import dataclass
import sys

from tessrax.core.errors import LedgerRepairError, DiagnosticError
from tessrax.core.time import canonical_datetime
from tessrax.ledger.index_backend import IndexEntry, LedgerIndexBackend
from tessrax.ledger.merkle import MerkleAccumulator, MerkleState
from tessrax.ledger.parallel_replay import parallel_replay_root
from tessrax.ledger.snapshots import import_ledger_entries
from tessrax.ledger.divergence import DivergenceDetector, DivergenceDetectionReport
from tessrax.core.ledger_replay import LedgerReplayEngine
from tessrax.core.serialization import canonical_serialize

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
INDEX_PATH = Path("tessrax/ledger/index.db")


@dataclass(frozen=True)
class DivergenceReport:
    ledger_entries: int
    index_entries: int
    merkle_entries: int
    root_matches: bool
    differences: dict[str, int]


@dataclass(frozen=True)
class RootCauseAnalysis:
    classification: str
    details: str


def _load_raw_entries_from_file(ledger_path: Path) -> List[dict]:
    """Loads ledger entries as raw dicts from ledger.jsonl, skipping malformed lines."""
    if not ledger_path.exists():
        return []
    entries: List[dict] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped:
                try:
                    entries.append(json.loads(stripped))
                except json.JSONDecodeError:
                    print(f"Warning: Skipping malformed JSON line in ledger: {stripped}", file=sys.stderr)
    return entries


def rebuild_index_from_ledger(
    *,
    ledger_path: Path = LEDGER_PATH,
    index_path: Path = INDEX_PATH,
) -> int:
    backend = LedgerIndexBackend(index_path=index_path)
    backend.ensure_schema()
    entries = _load_raw_entries_from_file(ledger_path)  # Use the updated loader
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


def repair_ledger_data(
    *,
    ledger_path: Path = LEDGER_PATH,
    trusted_snapshot_path: Path,
) -> Dict[str, Any]:
    """Repairs the ledger.jsonl file from a trusted snapshot if divergence is detected."""
    report = {
        "ledger_repaired": False,
        "divergence_detected": False,
        "divergence_report": None,
        "original_entry_count": 0,
        "repaired_entry_count": 0,
    }
    current_entries = _load_raw_entries_from_file(ledger_path)
    report["original_entry_count"] = len(current_entries)
    if not trusted_snapshot_path.exists():
        raise DiagnosticError(f"Trusted snapshot missing at {trusted_snapshot_path}")

    trusted_entries = import_ledger_entries(trusted_snapshot_path)
    # Use DivergenceDetector to compare trusted vs. current ledger entries
    detector = DivergenceDetector(trusted_entries, current_entries)
    divergence_detection_result = detector.detect_divergence()

    # Store the divergence report
    report["divergence_report"] = {
        "roots_match": divergence_detection_result.roots_match,
        "root_a": divergence_detection_result.root_a,  # Trusted root
        "root_b": divergence_detection_result.root_b,  # Current root
        "detailed_diff": divergence_detection_result.detailed_diff
    }

    # Check for any divergence
    if not divergence_detection_result.roots_match or \
       divergence_detection_result.detailed_diff['added'] or \
       divergence_detection_result.detailed_diff['removed'] or \
       divergence_detection_result.detailed_diff['modified']:

        print(f"Detected divergence in ledger data. Repairing '{ledger_path}' from '{trusted_snapshot_path}'.")
        report["divergence_detected"] = True

        # Overwrite corrupted ledger with trusted entries
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("w", encoding="utf-8") as handle:
            for entry in trusted_entries:
                # FIX: Corrected to use double-escaped newline in triple-quoted string
                handle.write(canonical_serialize(entry).decode("utf-8") + "\n")
        report["ledger_repaired"] = True
        report["repaired_entry_count"] = len(trusted_entries)
        print(f"Ledger '{ledger_path}' successfully repaired. {len(trusted_entries)} entries restored.")
    else:
        print(f"No significant divergence detected in ledger data compared to '{trusted_snapshot_path}'. No ledger repair performed.")
        report["repaired_entry_count"] = len(current_entries)  # No change in count
    return report


def auto_repair(
    *,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    index_path: Path = INDEX_PATH,
    trusted_snapshot_path: Optional[Path] = None,  # New argument
) -> dict:
    report = {
        "repaired_at": canonical_datetime(),
        "ledger_entries_after_repair": 0,
        "entries_replayed": 0,
        "index_entries_rebuilt": 0,
        "merkle_root_rebuilt": False,
        "merkle_root": None,
        "ledger_data_repair_report": None,  # New field for ledger data repair summary
    }

    if trusted_snapshot_path:
        ledger_data_repair_summary = repair_ledger_data(
            ledger_path=ledger_path,
            trusted_snapshot_path=trusted_snapshot_path
        )
        report["ledger_data_repair_report"] = ledger_data_repair_summary
        entries_to_process = _load_raw_entries_from_file(ledger_path)  # Reload the potentially repaired ledger
    else:
        entries_to_process = _load_raw_entries_from_file(ledger_path)

    if not entries_to_process:
        raise LedgerRepairError("No entries found in ledger to process; auto-repair aborted.")

    report["ledger_entries_after_repair"] = len(entries_to_process)
    report["entries_replayed"] = len(entries_to_process)

    # Replay ledger to get observed_root from the (potentially repaired) ledger
    # Using parallel_replay_root as it's the original method for MerkleAccumulator compatibility
    observed_root = parallel_replay_root(ledger_path=ledger_path)
    report["merkle_root"] = observed_root

    persisted_state = MerkleAccumulator(state_path=merkle_state_path)

    if persisted_state.state.root() != observed_root:
        print(f"Merkle state divergence detected. Rebuilding Merkle state from ledger. Old root: {persisted_state.state.root()}, New root: {observed_root}")
        temp_merkle_state = MerkleState.empty()
        for entry in entries_to_process:
            if "entry_hash" not in entry:
                raise LedgerRepairError("Ledger entries processed by MerkleAccumulator must contain 'entry_hash'.")
            temp_merkle_state = temp_merkle_state.apply_leaf(entry["entry_hash"])
        persisted_state.state = temp_merkle_state
        persisted_state._persist_state()  # type: ignore[attr-defined]
        report["merkle_root_rebuilt"] = True
    else:
        print("Merkle state is consistent with ledger.")

    rebuilt_index_count = rebuild_index_from_ledger(ledger_path=ledger_path, index_path=index_path)
    report["index_entries_rebuilt"] = rebuilt_index_count
    print("Index rebuilt from ledger.")

    (ledger_path.with_suffix(".repair.json")).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["auto_repair", "rebuild_index_from_ledger", "repair_ledger_data"]
