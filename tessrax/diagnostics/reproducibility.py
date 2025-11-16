"""End-to-end reproducibility auditor."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from tessrax.core.errors import DiagnosticError
from tessrax.core.hashing import HashResult, hash_paths

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
REQUIREMENTS_PATH = Path("requirements.txt")


@dataclass(frozen=True)
class ReproducibilityReport:
    ledger_hash: HashResult
    merkle_hash: HashResult
    requirements_hash: HashResult
    consistent: bool


def _hash_file(path: Path) -> HashResult:
    if not path.exists():
        raise DiagnosticError(f"Required artifact missing: {path}")
    return hash_paths([path])


def audit_reproducibility(
    *,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    requirements_path: Path = REQUIREMENTS_PATH,
) -> ReproducibilityReport:
    ledger_result = _hash_file(Path(ledger_path))
    merkle_result = _hash_file(Path(merkle_state_path))
    requirements_result = _hash_file(Path(requirements_path))
    consistent = len({ledger_result.digest, merkle_result.digest, requirements_result.digest}) == 3
    return ReproducibilityReport(
        ledger_hash=ledger_result,
        merkle_hash=merkle_result,
        requirements_hash=requirements_result,
        consistent=consistent,
    )


def reproducibility_guard(*, reference_hashes: Sequence[str], ledger_path: Path = LEDGER_PATH) -> bool:
    ledger_result = _hash_file(Path(ledger_path))
    if ledger_result.digest not in reference_hashes:
        raise DiagnosticError("Ledger hash drift detected")
    return True


__all__ = ["ReproducibilityReport", "audit_reproducibility", "reproducibility_guard"]
