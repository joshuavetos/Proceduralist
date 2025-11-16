"""Merkle accumulator utilities for Tessrax ledgers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from tessrax.core.serialization import canonical_json

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"
EMPTY_ROOT = hashlib.sha256(b"TESSRAX|MERKLE|EMPTY").hexdigest()


class MerkleVerificationError(RuntimeError):
    """Raised when Merkle chain validation fails."""


def _hash_leaf(leaf_hash: str) -> str:
    return hashlib.sha256(f"leaf:{leaf_hash}".encode("utf-8")).hexdigest()


def _hash_node(left: str, right: str) -> str:
    return hashlib.sha256(f"node:{left}:{right}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MerkleState:
    entry_count: int
    peaks: list[str]
    last_leaf_hash: str | None

    @classmethod
    def empty(cls) -> "MerkleState":
        return cls(entry_count=0, peaks=[], last_leaf_hash=None)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "MerkleState":
        entry_count = int(payload.get("entry_count", 0))
        peaks = [str(value) for value in payload.get("peaks", [])]
        last_leaf_hash = payload.get("last_leaf_hash")
        if last_leaf_hash is not None:
            last_leaf_hash = str(last_leaf_hash)
        return cls(entry_count=entry_count, peaks=peaks, last_leaf_hash=last_leaf_hash)

    def to_payload(self) -> dict:
        return {
            "entry_count": self.entry_count,
            "peaks": list(self.peaks),
            "last_leaf_hash": self.last_leaf_hash,
        }

    def root(self) -> str:
        if not self.peaks:
            return EMPTY_ROOT
        accumulator = self.peaks[0]
        for peak in self.peaks[1:]:
            accumulator = _hash_node(accumulator, peak)
        return accumulator

    def apply_leaf(self, leaf_hash: str) -> "MerkleState":
        if not isinstance(leaf_hash, str) or len(leaf_hash) != 64:
            raise ValueError("leaf_hash must be a 64-character hex string")
        node = _hash_leaf(leaf_hash)
        peaks = list(self.peaks)
        counter = self.entry_count
        while counter & 1 and peaks:
            left = peaks.pop()
            node = _hash_node(left, node)
            counter >>= 1
        peaks.append(node)
        return MerkleState(
            entry_count=self.entry_count + 1,
            peaks=peaks,
            last_leaf_hash=leaf_hash,
        )


@dataclass(frozen=True)
class MerkleUpdate:
    new_state: MerkleState
    previous_leaf_hash: str | None
    new_root: str


class MerkleAccumulator:
    """Persistent Merkle accumulator backed by ``MERKLE_STATE_PATH``."""

    def __init__(self, state_path: Path | str = MERKLE_STATE_PATH):
        self.state_path = Path(state_path)
        self.state = self._load_state()

    def _load_state(self) -> MerkleState:
        if not self.state_path.exists():
            return MerkleState.empty()
        raw = self.state_path.read_bytes()
        if not raw.strip():
            return MerkleState.empty()
        payload = json.loads(raw.decode("utf-8"))
        return MerkleState.from_payload(payload)

    def prepare_update(self, leaf_hash: str) -> MerkleUpdate:
        new_state = self.state.apply_leaf(leaf_hash)
        return MerkleUpdate(
            new_state=new_state,
            previous_leaf_hash=self.state.last_leaf_hash,
            new_root=new_state.root(),
        )

    def commit(self, update: MerkleUpdate) -> str:
        self.state = update.new_state
        self._persist_state()
        return self.state.root()

    def _persist_state(self) -> None:
        payload = self.state.to_payload()
        payload.update(
            auditor=AUDITOR_IDENTITY,
            updated_at=datetime.now(timezone.utc).isoformat(),
            root=self.state.root(),
        )
        canonical = canonical_json(payload)
        payload["integrity"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _entry_body(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    body_keys = [
        "event_type",
        "timestamp",
        "payload",
        "payload_hash",
        "audited_state_hash",
        "auditor",
        "key_id",
        "signature",
        "previous_entry_hash",
    ]
    return {key: entry[key] for key in body_keys if key in entry}


def compute_entry_hash(entry: Mapping[str, Any]) -> str:
    """Reconstruct the canonical entry hash from a ledger record."""

    body = _entry_body(entry)
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def verify_merkle(
    ledger_path: Path | str = LEDGER_PATH,
    state_path: Path | str = MERKLE_STATE_PATH,
) -> bool:
    ledger_file = Path(ledger_path)
    if not ledger_file.exists():
        raise MerkleVerificationError(f"Ledger not found at {ledger_file}")

    state = MerkleState.empty()
    previous_hash: str | None = None
    with ledger_file.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - corruption path
                raise MerkleVerificationError(
                    f"Ledger line {line_no}: invalid JSON {exc.msg}"
                ) from exc
            for field in ("entry_hash", "merkle_root"):
                if field not in entry:
                    raise MerkleVerificationError(
                        f"Ledger line {line_no}: missing field '{field}'"
                    )
            body_hash = compute_entry_hash(entry)
            if body_hash != entry["entry_hash"]:
                raise MerkleVerificationError(
                    f"Ledger line {line_no}: entry_hash mismatch"
                )
            if entry.get("previous_entry_hash") != previous_hash:
                raise MerkleVerificationError(
                    f"Ledger line {line_no}: previous_entry_hash mismatch"
                )
            state = state.apply_leaf(entry["entry_hash"])
            if state.root() != entry["merkle_root"]:
                raise MerkleVerificationError(
                    f"Ledger line {line_no}: merkle_root mismatch"
                )
            previous_hash = entry["entry_hash"]

    persisted = MerkleAccumulator(state_path=state_path)
    if (
        persisted.state.entry_count != state.entry_count
        or persisted.state.root() != state.root()
    ):
        raise MerkleVerificationError("Persisted Merkle state diverges from ledger replay")

    return True


__all__ = [
    "MerkleAccumulator",
    "MerkleState",
    "MerkleVerificationError",
    "compute_entry_hash",
    "verify_merkle",
    "MERKLE_STATE_PATH",
]
