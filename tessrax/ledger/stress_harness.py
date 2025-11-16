"""Deterministic ledger stress harness emitting synthetic entries."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from tessrax.core.time import canonical_datetime
from tessrax.ledger.merkle import MerkleState


@dataclass(slots=True)
class StressHarnessResult:
    output_path: Path
    entries: int
    merkle_root: str


def generate_stress_ledger(*, output_path: Path, entries: int = 10_000, seed: int = 1337) -> StressHarnessResult:
    rng = random.Random(seed)
    merkle = MerkleState.empty()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for idx in range(entries):
            payload = {"node": idx, "status": "VERIFIED" if idx % 2 == 0 else "LOGGED"}
            payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            entry_hash = hashlib.sha256(f"{idx}:{payload_hash}".encode("utf-8")).hexdigest()
            next_state = merkle.apply_leaf(entry_hash)
            entry = {
                "event_type": "STATE_AUDITED",
                "timestamp": canonical_datetime(),
                "payload": payload,
                "payload_hash": payload_hash,
                "audited_state_hash": f"{idx:064x}",
                "signature": f"{rng.getrandbits(256):064x}",
                "entry_hash": entry_hash,
                "merkle_root": next_state.root(),
            }
            merkle = next_state
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return StressHarnessResult(output_path=output_path, entries=entries, merkle_root=merkle.root())


__all__ = ["StressHarnessResult", "generate_stress_ledger"]
