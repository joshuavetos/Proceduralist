"""Ledger verification tool for Tessrax Proceduralist.

The verifier enforces:
* strict JSONL parsing with canonical hashing and Ed25519 signatures,
* monotonic timestamps,
* per-entry key rotation via ``key_id`` lookups,
* ledger/index parity checks (offset alignment + payload hashes), and
* validated state-hash/event semantics.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from nacl.signing import VerifyKey

from tessrax.core.errors import TessraxError
from tessrax.core.memory_engine import CANONICAL_EVENT_TYPES
from tessrax.core.models import ReceiptPayloadModel
from tessrax.core.serialization import canonical_json, canonical_payload_hash
from tessrax.ledger.epochal import EpochLedgerManager, EpochError
from tessrax.ledger.merkle import MerkleAccumulator, MerkleState, compute_entry_hash

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
SIGNING_KEYS_DIR = Path("tessrax/infra/signing_keys")
LEGACY_KEY_PATH = Path("tessrax/infra/signing_key.pub")

STATE_HASH_PATTERN = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{64})$")


@dataclass(frozen=True)
class LedgerRecord:
    """In-memory representation of a ledger entry."""

    offset: int
    event_type: str
    audited_state_hash: str
    payload_hash: str
    entry_hash: str
    merkle_root: str
    previous_entry_hash: str | None


class LedgerVerificationError(TessraxError):
    """Raised when the verifier encounters integrity issues."""

    def __init__(self, message: str):
        super().__init__(code="LEDGER_VERIFY", message=message, details=None)


def _load_verify_keys() -> Dict[str, VerifyKey]:
    keys: Dict[str, VerifyKey] = {}

    if SIGNING_KEYS_DIR.exists():
        for key_path in SIGNING_KEYS_DIR.glob("*.pub"):
            raw = key_path.read_bytes()
            if raw.strip():
                keys[key_path.stem] = _coerce_verify_key(raw)

    if not keys and LEGACY_KEY_PATH.exists():
        raw = LEGACY_KEY_PATH.read_bytes()
        if raw.strip():
            keys["legacy"] = _coerce_verify_key(raw)

    if not keys:
        raise LedgerVerificationError("No Ed25519 verification keys found.")

    return keys


def _safe_json_load(line: str, line_no: int) -> dict:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise LedgerVerificationError(
            f"Corrupted JSON at line {line_no}: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise LedgerVerificationError(f"Ledger line {line_no} is not a JSON object")

    return data


def _validate_state_hash(value: str, line_no: int) -> None:
    if not isinstance(value, str) or not STATE_HASH_PATTERN.match(value):
        raise LedgerVerificationError(
            f"Invalid audited_state_hash at line {line_no}: {value!r}"
        )


def _validate_event_type(event_type: str, line_no: int) -> None:
    if event_type not in CANONICAL_EVENT_TYPES:
        raise LedgerVerificationError(
            f"Unknown event_type at line {line_no}: {event_type!r}"
        )


def _coerce_verify_key(raw: bytes) -> VerifyKey:
    """Support canonical, double-hex, and raw encodings for verify keys."""

    text: str | None
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = None

    if text:
        try:
            candidate = bytes.fromhex(text)
        except ValueError:
            candidate = None
        else:
            if len(candidate) == 32:
                return VerifyKey(candidate)
            if len(candidate) == 64:
                try:
                    nested_text = candidate.decode("ascii").strip()
                except UnicodeDecodeError:
                    nested_text = ""
                if nested_text:
                    try:
                        nested_candidate = bytes.fromhex(nested_text)
                    except ValueError:
                        nested_candidate = None
                    else:
                        if len(nested_candidate) == 32:
                            return VerifyKey(nested_candidate)

    compact_raw = raw.strip()
    if len(compact_raw) != 32:
        raise LedgerVerificationError("Verification key material is not 32 bytes.")
    return VerifyKey(compact_raw)


def _verify_signature(record: dict, verify_keys: Dict[str, VerifyKey], line_no: int) -> None:
    key_id = record.get("key_id")
    if not isinstance(key_id, str):
        if len(verify_keys) == 1:
            # Older ledgers emitted receipts without key identifiers because only
            # a single signing key existed.  Fall back to that lone key so that
            # the verifier can still replay those ledgers.
            key_id = next(iter(verify_keys))
        else:
            raise LedgerVerificationError(
                f"Missing key_id at line {line_no} while multiple verification keys are configured"
            )

    if key_id not in verify_keys:
        raise LedgerVerificationError(
            f"Unknown key_id '{key_id}' at line {line_no}"
        )

    signed_body = {
        "event_type": record["event_type"],
        "timestamp": record["timestamp"],
        "payload": record["payload"],
        "payload_hash": record["payload_hash"],
        "audited_state_hash": record["audited_state_hash"],
        "key_id": key_id,
    }
    if "auditor" in record:
        signed_body["auditor"] = record["auditor"]

    message = canonical_json(signed_body).encode()

    signature_hex = record.get("signature")
    if not isinstance(signature_hex, str):
        raise LedgerVerificationError(f"Missing signature at line {line_no}")

    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError as exc:
        raise LedgerVerificationError(
            f"Invalid signature encoding at line {line_no}"
        ) from exc

    verify_keys[key_id].verify(message, signature)


def _hash_payload(payload: dict, line_no: int) -> str:
    if not isinstance(payload, dict):
        raise LedgerVerificationError(f"Payload at line {line_no} must be an object")

    return canonical_payload_hash(payload)


def _read_ledger() -> tuple[List[LedgerRecord], MerkleState]:
    records: List[LedgerRecord] = []
    prev_ts: float | None = None
    verify_keys: Dict[str, VerifyKey] | None = None
    merkle_state = MerkleState.empty()
    prev_entry_hash: str | None = None
    epoch_manager = EpochLedgerManager()

    if not LEDGER_PATH.exists() or LEDGER_PATH.stat().st_size == 0:
        return records, merkle_state

    with LEDGER_PATH.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue

            entry = _safe_json_load(stripped, line_no)
            required_fields = [
                "event_type",
                "timestamp",
                "payload",
                "payload_hash",
                "audited_state_hash",
                "signature",
                "epoch_id",
                "governance_freshness_tag",
            ]
            merkle_fields = ["entry_hash", "merkle_root"]
            for field in required_fields:
                if field not in entry:
                    raise LedgerVerificationError(
                        f"Missing field '{field}' at line {line_no}"
                    )
            for field in merkle_fields:
                if field not in entry:
                    raise LedgerVerificationError(
                        f"Missing field '{field}' at line {line_no}"
                    )

            ReceiptPayloadModel.model_validate(entry)

            event_type = entry["event_type"]
            if not isinstance(event_type, str):
                raise LedgerVerificationError(
                    f"event_type at line {line_no} must be a string"
                )
            _validate_event_type(event_type, line_no)
            _validate_state_hash(entry["audited_state_hash"], line_no)

            timestamp_value = entry["timestamp"]
            if isinstance(timestamp_value, (int, float)):
                timestamp = float(timestamp_value)
            elif isinstance(timestamp_value, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_value).timestamp()
                except ValueError as exc:
                    raise LedgerVerificationError(
                        f"Timestamp at line {line_no} must be ISO-8601 or numeric"
                    ) from exc
            else:
                raise LedgerVerificationError(
                    f"Timestamp at line {line_no} must be ISO-8601 or numeric"
                )

            payload_hash = _hash_payload(entry["payload"], line_no)
            payload_hash_field = entry["payload_hash"]
            if not isinstance(payload_hash_field, str):
                raise LedgerVerificationError(
                    f"payload_hash at line {line_no} must be a string"
                )
            if payload_hash != payload_hash_field:
                raise LedgerVerificationError(
                    f"Payload hash mismatch at line {line_no}"
                )

            if prev_ts is not None and timestamp < prev_ts:
                raise LedgerVerificationError(
                    f"Timestamp regression at line {line_no}"
                )
            prev_ts = timestamp

            if verify_keys is None:
                verify_keys = _load_verify_keys()
            _verify_signature(entry, verify_keys, line_no)

            entry_hash = entry["entry_hash"]
            if not isinstance(entry_hash, str):
                raise LedgerVerificationError(
                    f"entry_hash at line {line_no} must be a string"
                )
            computed_entry_hash = compute_entry_hash(entry)
            if computed_entry_hash != entry_hash:
                raise LedgerVerificationError(
                    f"Entry hash mismatch at line {line_no}"
                )
            if entry.get("previous_entry_hash") != prev_entry_hash:
                raise LedgerVerificationError(
                    f"previous_entry_hash mismatch at line {line_no}"
                )
            merkle_state = merkle_state.apply_leaf(entry_hash)
            merkle_root = entry["merkle_root"]
            if merkle_root != merkle_state.root():
                raise LedgerVerificationError(
                    f"merkle_root mismatch at line {line_no}"
                )
            epoch_id = entry.get("epoch_id")
            if not isinstance(epoch_id, str):
                raise LedgerVerificationError(
                    f"epoch_id at line {line_no} must be a string"
                )
            try:
                recorded_epoch = epoch_manager.get_epoch(entry_hash)
            except EpochError:
                recorded_epoch = None
            if recorded_epoch and recorded_epoch != epoch_id:
                raise LedgerVerificationError(
                    f"epoch_id mismatch at line {line_no}"
                )
            prev_entry_hash = entry_hash

            offset = len(records)
            records.append(
                LedgerRecord(
                    offset=offset,
                    event_type=event_type,
                    audited_state_hash=entry["audited_state_hash"],
                    payload_hash=payload_hash,
                    entry_hash=entry_hash,
                    merkle_root=merkle_root,
                    previous_entry_hash=entry.get("previous_entry_hash"),
                )
            )
    return records, merkle_state


def _fetch_index_rows() -> List[Tuple[int, str, str, str, str | None, str, str | None]]:
    if not INDEX_PATH.exists() or INDEX_PATH.stat().st_size == 0:
        return []

    try:
        with sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True) as con:
            cur = con.execute(
                "SELECT ledger_offset, event_type, state_hash, payload_hash, "
                "merkle_root, entry_hash, previous_entry_hash "
                "FROM ledger_index ORDER BY ledger_offset"
            )
            return cur.fetchall()
    except sqlite3.Error as exc:
        raise LedgerVerificationError("Failed to read ledger index") from exc


def _compare_index(records: List[LedgerRecord]) -> None:
    index_rows = _fetch_index_rows()

    if len(index_rows) != len(records):
        raise LedgerVerificationError(
            f"Index/ledger length mismatch ({len(index_rows)} vs {len(records)})"
        )

    prev_offset = -1
    for expected_offset, row in enumerate(index_rows):
        (
            ledger_offset,
            event_type,
            state_hash,
            payload_hash,
            merkle_root,
            entry_hash,
            previous_entry_hash,
        ) = row
        if not isinstance(ledger_offset, int):
            raise LedgerVerificationError(
                f"Index row {expected_offset} has non-integer ledger_offset"
            )
        if ledger_offset < prev_offset:
            raise LedgerVerificationError(
                f"Ledger offsets must be monotonically increasing (row {expected_offset})"
            )
        prev_offset = ledger_offset

        record = records[expected_offset]
        if (
            record.event_type != event_type
            or record.audited_state_hash != state_hash
            or record.payload_hash != payload_hash
            or record.entry_hash != entry_hash
            or record.merkle_root != merkle_root
            or (record.previous_entry_hash or None) != previous_entry_hash
        ):
            raise LedgerVerificationError(
                f"Index mismatch at offset {expected_offset}"
            )


def _verify_merkle_state(observed: MerkleState) -> None:
    persisted = MerkleAccumulator(state_path=MERKLE_STATE_PATH)
    if persisted.state.entry_count != observed.entry_count:
        raise LedgerVerificationError("Merkle entry count mismatch")
    if persisted.state.root() != observed.root():
        raise LedgerVerificationError("Merkle root mismatch")


def verify_ledger() -> bool:
    try:
        print("[VERIFY] Stage 1 — Validating ledger entries...")
        records, merkle_state = _read_ledger()
        if not records:
            print("[VERIFY] Stage 1 SUCCESS (no entries present).")
        else:
            print("[VERIFY] Stage 1 SUCCESS.")

        print("[VERIFY] Stage 2 — Checking index consistency...")
        _compare_index(records)
        print("[VERIFY] Stage 2 SUCCESS.")

        print("[VERIFY] Stage 3 — Validating Merkle accumulator...")
        _verify_merkle_state(merkle_state)
        print("[VERIFY] Stage 3 SUCCESS.")
    except LedgerVerificationError as exc:
        print(f"[FAIL] {exc}")
        return False

    print("[VERIFY] FINAL VERDICT — SUCCESS.")
    return True


if __name__ == "__main__":
    verify_ledger()


# Provide backwards compatibility for historical import paths.
verify = verify_ledger

__all__ = [
    "LedgerRecord",
    "LedgerVerificationError",
    "verify_ledger",
    "verify",
]
