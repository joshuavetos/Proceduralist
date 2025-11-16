"""Merkle replay profiler and timing guard."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from tessrax.core.errors import DiagnosticError
from tessrax.ledger.parallel_replay import parallel_replay_root


@dataclass(frozen=True)
class MerkleReplayProfile:
    ledger_path: Path
    merkle_root: str
    elapsed_seconds: float
    threshold_seconds: float
    guard_passed: bool


def profile_replay(*, ledger_path: Path, threshold_seconds: float = 1.0) -> MerkleReplayProfile:
    ledger_file = Path(ledger_path)
    if not ledger_file.exists():
        raise DiagnosticError(f"Ledger missing at {ledger_file}")
    start = time.perf_counter()
    root = parallel_replay_root(ledger_path=ledger_file)
    elapsed = time.perf_counter() - start
    guard_passed = elapsed <= threshold_seconds
    return MerkleReplayProfile(
        ledger_path=ledger_file,
        merkle_root=root,
        elapsed_seconds=elapsed,
        threshold_seconds=threshold_seconds,
        guard_passed=guard_passed,
    )


__all__ = ["MerkleReplayProfile", "profile_replay"]
