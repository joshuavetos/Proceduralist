"""State divergence scanner for ledger, index, and Merkle state."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Dict

from tessrax.core.errors import DiagnosticError
from tessrax.core.ledger_replay import LedgerReplayEngine  # New import
from tessrax.ledger.receipt_diff import calculate_delta_diff  # New import
from tessrax.ledger.merkle import MerkleAccumulator  # Existing import
from tessrax.ledger.parallel_replay import parallel_replay_root  # Existing import

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


def _count_ledger_entries(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _count_index_entries(path: Path) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_offset INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        return conn.execute("SELECT COUNT(*) FROM ledger_index").fetchone()[0]


def _merkle_entries(path: Path) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    return int(payload.get("entry_count", 0))


def scan_state_divergence(
    *,
    ledger_path: Path = LEDGER_PATH,
    index_path: Path = INDEX_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
) -> DivergenceReport:
    ledger_file = Path(ledger_path)
    index_file = Path(index_path)
    merkle_file = Path(merkle_state_path)
    ledger_entries = _count_ledger_entries(ledger_file)
    index_entries = _count_index_entries(index_file)
    merkle_entries = _merkle_entries(merkle_file)
    if ledger_entries == 0:
        raise DiagnosticError("Ledger has no entries; divergence scan is meaningless")
    replay_root = parallel_replay_root(ledger_path=ledger_file)
    merkle_root = MerkleAccumulator(state_path=merkle_file).state.root()
    root_matches = replay_root == merkle_root
    differences = {
        "ledger_vs_index": ledger_entries - index_entries,
        "ledger_vs_merkle": ledger_entries - merkle_entries,
        "index_vs_merkle": index_entries - merkle_entries,
    }
    return DivergenceReport(
        ledger_entries=ledger_entries,
        index_entries=index_entries,
        merkle_entries=merkle_entries,
        root_matches=root_matches,
        differences=differences,
    )


def analyze_root_cause(report: DivergenceReport) -> RootCauseAnalysis:
    if report.root_matches and all(delta == 0 for delta in report.differences.values()):
        return RootCauseAnalysis(classification="NONE", details="No divergence detected")
    if report.differences["ledger_vs_index"] != 0:
        return RootCauseAnalysis(
            classification="INDEX_DRIFT",
            details="Ledger entries do not match index entries",
        )
    if report.differences["ledger_vs_merkle"] != 0:
        return RootCauseAnalysis(
            classification="MERKLE_DRIFT",
            details="Ledger entry count differs from Merkle state",
        )
    return RootCauseAnalysis(classification="UNKNOWN", details="Unable to isolate root cause")


@dataclass(frozen=True)
class DivergenceDetectionReport:
    roots_match: bool
    root_a: str
    root_b: str
    detailed_diff: Dict[str, List[Any]]


class DivergenceDetector:
    """Detects and reports divergences between two sets of ledger entries."""
    def __init__(self, primary_entries: List[Any], secondary_entries: List[Any]) -> None:
        self.primary_entries = primary_entries
        self.secondary_entries = secondary_entries

    def detect_divergence(self) -> DivergenceDetectionReport:
        # Calculate Merkle roots for both sets of entries
        replay_engine_a = LedgerReplayEngine(self.primary_entries)
        root_a = replay_engine_a.get_merkle_root()
        replay_engine_b = LedgerReplayEngine(self.secondary_entries)
        root_b = replay_engine_b.get_merkle_root()
        roots_match = (root_a == root_b)
        detailed_diff = {
            'added': [],
            'removed': [],
            'modified': []
        }
        if not roots_match:
            # If roots differ, calculate a detailed delta diff
            detailed_diff = calculate_delta_diff(self.primary_entries, self.secondary_entries)
        return DivergenceDetectionReport(
            roots_match=roots_match,
            root_a=root_a,
            root_b=root_b,
            detailed_diff=detailed_diff
        )


__all__ = [
    "DivergenceReport",
    "RootCauseAnalysis",
    "analyze_root_cause",
    "scan_state_divergence",
    "DivergenceDetector",  # New export
    "DivergenceDetectionReport"  # New export
]
