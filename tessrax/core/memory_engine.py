"""Tessrax Memory Engine v2.0.0 (Merkle-hardened).

Responsibilities:
* canonical JSON serialisation with recursive normalisation;
* Ed25519 signing via a managed key registry;
* atomic append-only writes guarded by jittered file locks;
* mirrored writes to the ledger index database with integrity annotations;
* Merkle-root maintenance + previous-entry hash chaining; and
* runtime verification of caller input per Tessrax RVC-001.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from nacl.signing import SigningKey

from tessrax.core.serialization import (
    canonical_json,
    canonical_payload_hash,
    snapshot_payload,
)
from tessrax.core.time import canonical_datetime
from tessrax.core.typecheck import is_frozen_payload
from tessrax.infra import key_registry
from tessrax.governance.token_guard import GovernanceTokenGuard
from tessrax.ledger.epochal import EpochLedgerManager
from tessrax.ledger.index_backend import IndexEntry, LedgerIndexBackend
from tessrax.ledger.merkle import MerkleAccumulator

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"
CANONICAL_EVENT_TYPES: tuple[str, ...] = ("STATE_AUDITED", "CONTRADICTION_DETECTED")


@dataclass(slots=True)
class Receipt:
    """Simple representation of a signed ledger entry."""

    event_type: str
    timestamp: str
    payload: Mapping[str, Any]
    payload_hash: str
    audited_state_hash: str
    signature: str
    ledger_offset: int
    previous_entry_hash: str | None
    entry_hash: str
    merkle_root: str
    epoch_id: str
    governance_freshness_tag: str


def _load_active_key() -> tuple[str, SigningKey]:
    """Retrieve the active (key_id, SigningKey) pair from the registry."""

    key_id, signing_key = key_registry.load_active_signing_key()
    return key_id, signing_key


@contextmanager
def _acquire_mutex(handle) -> None:
    delay = 0.01
    max_delay = 0.5
    attempts = 0
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            jitter = random.uniform(0.0, delay)
            time.sleep(delay + jitter)
            attempts += 1
            delay = min(delay * 2, max_delay)
            if attempts > 10:
                raise TimeoutError("Unable to obtain ledger lock within backoff window")
        else:
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            break


def _append_to_ledger(entry: Mapping[str, Any]) -> int:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = canonical_json(entry) + "\n"
    with open(LEDGER_PATH, "a+", encoding="utf-8") as handle:
        with _acquire_mutex(handle):
            handle.seek(0, os.SEEK_END)
            offset = handle.tell()
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    return offset


def _verify_inputs(event_type: str, payload: Mapping[str, Any], audited_state_hash: str) -> None:
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")
    if event_type not in CANONICAL_EVENT_TYPES:
        raise ValueError(
            f"event_type must be one of {CANONICAL_EVENT_TYPES}, received {event_type!r}"
        )
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    if not isinstance(audited_state_hash, str) or len(audited_state_hash) < 8:
        raise ValueError("audited_state_hash must be a non-empty hash string")


def write_receipt(event_type: str, payload: Mapping[str, Any], audited_state_hash: str) -> Receipt:
    _verify_inputs(event_type, payload, audited_state_hash)
    index_backend = LedgerIndexBackend(index_path=INDEX_PATH)
    index_backend.ensure_schema()

    timestamp = canonical_datetime()
    normalized_payload = snapshot_payload(payload)
    if not is_frozen_payload(normalized_payload):  # pragma: no cover - defensive
        raise TypeError("snapshot_payload must return FrozenPayload")
    payload_hash = canonical_payload_hash(normalized_payload)
    token_guard = GovernanceTokenGuard(
        state_path=MERKLE_STATE_PATH.with_name("governance_token_state.json")
    )
    merkle_accumulator = MerkleAccumulator(state_path=MERKLE_STATE_PATH)
    freshness_tag = token_guard.validate(
        ledger_counter=merkle_accumulator.state.entry_count
    )
    key_id, signing_key = _load_active_key()
    canonical_event = {
        "event_type": event_type,
        "timestamp": timestamp,
        "payload": normalized_payload,
        "payload_hash": payload_hash,
        "audited_state_hash": audited_state_hash,
        "auditor": AUDITOR_IDENTITY,
        "key_id": key_id,
    }

    canonical_str = canonical_json(canonical_event)
    signature = signing_key.sign(canonical_str.encode("utf-8")).signature.hex()
    previous_entry_hash = merkle_accumulator.state.last_leaf_hash
    ledger_body = {
        **canonical_event,
        "signature": signature,
        "previous_entry_hash": previous_entry_hash,
        "governance_freshness_tag": freshness_tag,
    }
    entry_hash = hashlib.sha256(canonical_json(ledger_body).encode("utf-8")).hexdigest()
    merkle_update = merkle_accumulator.prepare_update(entry_hash)
    epoch_manager = EpochLedgerManager(
        state_path=MERKLE_STATE_PATH.with_name("epoch_state.json"),
        snapshot_dir=MERKLE_STATE_PATH.parent,
    )
    epoch_id = epoch_manager.record_entry(
        entry_hash=entry_hash,
        timestamp=timestamp,
        merkle_state=merkle_update.new_state,
    )
    ledger_entry = {
        **ledger_body,
        "entry_hash": entry_hash,
        "merkle_root": merkle_update.new_root,
        "epoch_id": epoch_id,
    }
    offset = _append_to_ledger(ledger_entry)
    index_backend.append(
        IndexEntry(
            ledger_offset=offset,
            event_type=event_type,
            state_hash=audited_state_hash,
            payload_hash=payload_hash,
            timestamp=timestamp,
            merkle_root=merkle_update.new_root,
            entry_hash=entry_hash,
            previous_entry_hash=previous_entry_hash,
        )
    )
    merkle_accumulator.commit(merkle_update)

    return Receipt(
        event_type=event_type,
        timestamp=timestamp,
        payload=canonical_event["payload"],
        payload_hash=payload_hash,
        audited_state_hash=audited_state_hash,
        signature=signature,
        ledger_offset=offset,
        previous_entry_hash=previous_entry_hash,
        entry_hash=entry_hash,
        merkle_root=merkle_update.new_root,
        epoch_id=epoch_id,
        governance_freshness_tag=freshness_tag,
    )


__all__ = [
    "Receipt",
    "write_receipt",
    "CANONICAL_EVENT_TYPES",
]
