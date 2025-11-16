"""High volume load-test generator for receipts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tessrax.ledger.stress_harness import generate_stress_ledger


@dataclass(frozen=True)
class LoadTestSummary:
    output_path: Path
    total_entries: int
    batches: int
    batch_size: int
    merkle_root: str


def generate_high_volume_receipts(
    *,
    output_path: Path,
    batches: int = 5,
    batch_size: int = 2500,
) -> LoadTestSummary:
    if batches <= 0 or batch_size <= 0:
        raise ValueError("batches and batch_size must be positive")
    total_entries = batches * batch_size
    result = generate_stress_ledger(output_path=output_path, entries=total_entries)
    return LoadTestSummary(
        output_path=output_path,
        total_entries=total_entries,
        batches=batches,
        batch_size=batch_size,
        merkle_root=result.merkle_root,
    )


__all__ = ["LoadTestSummary", "generate_high_volume_receipts"]
