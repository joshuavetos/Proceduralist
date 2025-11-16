"""Ledger compaction and sharding utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List

from tessrax.core.errors import LedgerRepairError
from tessrax.core.time import canonical_datetime
from tessrax.ledger.merkle import MerkleAccumulator, MerkleState, compute_entry_hash

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")


@dataclass(slots=True)
class CompactionReport:
    retained_entries: int
    dropped_entries: int
    new_merkle_root: str
    old_merkle_root: str
    output_path: Path


class LedgerCompactor:
    def __init__(
        self,
        *,
        ledger_path: Path = LEDGER_PATH,
        merkle_state_path: Path = MERKLE_STATE_PATH,
    ) -> None:
        self.ledger_path = ledger_path
        self.merkle_state_path = merkle_state_path

    def _read_entries(self) -> List[dict]:
        if not self.ledger_path.exists():
            return []
        entries: List[dict] = []
        with self.ledger_path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                stripped = raw.strip()
                if stripped:
                    entries.append(json.loads(stripped))
        return entries

    def compact(self, *, retain: int, output_path: Path | None = None) -> CompactionReport:
        entries = self._read_entries()
        if not entries:
            raise LedgerRepairError("Ledger is empty; nothing to compact")
        retain = max(retain, 1)
        retained = entries[-retain:]
        output = output_path or self.ledger_path.with_name("ledger_compacted.jsonl")
        with output.open("w", encoding="utf-8") as handle:
            for entry in retained:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        accumulator = MerkleAccumulator(state_path=self.merkle_state_path)
        accumulator.state = MerkleState.empty()
        for entry in retained:
            accumulator.state = accumulator.state.apply_leaf(entry["entry_hash"])
        accumulator._persist_state()  # type: ignore[attr-defined]
        old_root = entries[-1]["merkle_root"]
        report = CompactionReport(
            retained_entries=len(retained),
            dropped_entries=len(entries) - len(retained),
            new_merkle_root=accumulator.state.root(),
            old_merkle_root=old_root,
            output_path=output,
        )
        serialized_report = asdict(report)
        serialized_report["output_path"] = str(serialized_report["output_path"])
        rollover = {
            "generated_at": canonical_datetime(),
            "report": serialized_report,
        }
        output.with_suffix(".rollover.json").write_text(
            json.dumps(rollover, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report


class LedgerShardPlanner:
    def __init__(self, *, ledger_path: Path = LEDGER_PATH) -> None:
        self.ledger_path = ledger_path

    def shard(self, *, max_entries: int, output_dir: Path | None = None) -> list[Path]:
        if max_entries <= 0:
            raise LedgerRepairError("max_entries must be positive")
        entries = []
        if self.ledger_path.exists():
            with self.ledger_path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    stripped = raw.strip()
                    if stripped:
                        entries.append(json.loads(stripped))
        if not entries:
            return []
        output = output_dir or self.ledger_path.parent
        output.mkdir(parents=True, exist_ok=True)
        shards: list[Path] = []
        previous_root = None
        for start in range(0, len(entries), max_entries):
            chunk = entries[start : start + max_entries]
            shard_path = output / f"ledger-shard-{start:08d}-{start + len(chunk):08d}.jsonl"
            accumulator = MerkleState.empty()
            with shard_path.open("w", encoding="utf-8") as handle:
                for entry in chunk:
                    accumulator = accumulator.apply_leaf(entry["entry_hash"])
                    entry = dict(entry)
                    entry["shard_previous_root"] = previous_root
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
            previous_root = accumulator.root()
            shards.append(shard_path)
        return shards


def read_entry_stream(path: Path = LEDGER_PATH) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped:
                entry = json.loads(stripped)
                compute_entry_hash(entry)
                yield entry


__all__ = [
    "CompactionReport",
    "LedgerCompactor",
    "LedgerShardPlanner",
    "read_entry_stream",
]
