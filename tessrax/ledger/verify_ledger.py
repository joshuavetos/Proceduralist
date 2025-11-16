"""Ledger verification tool for Tessrax Proceduralist.

The verifier enforces:
* strict JSONL parsing with canonical hashing and Ed25519 signatures,
* monotonic timestamps,
* per-entry key rotation via ``key_id`` lookups,
* ledger/index parity checks (offset alignment + payload hashes), and
* validated state-hash/event semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from nacl.signing import VerifyKey

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
SIGNING_KEYS_DIR = Path("tessrax/infra/signing_keys")
LEGACY_KEY_PATH = Path("tessrax/infra/signing_key.pub")

STATE_HASH_PATTERN = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{64})$")
CANONICAL_EVENTS = {"STATE_AUDITED", "CONTRADICTION_DETECTED"}


@dataclass(frozen=True)
class LedgerRecord:
    """In-memory representation of a ledger entry."""

    offset: int
    event_type: str
    audited_state_hash: str
    payload_hash: str


class LedgerVerificationError(RuntimeError):
    """Raised when the verifier encounters integrity issues."""


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _load_verify_keys() -> Dict[str, VerifyKey]:
    keys: Dict[str, VerifyKey] = {}

    if SIGNING_KEYS_DIR.exists():
        for key_path in SIGNING_KEYS_DIR.glob("*.pub"):
            keys[key_path.stem] = VerifyKey(key_path.read_bytes())

    if not keys and LEGACY_KEY_PATH.exists():
        keys["legacy"] = VerifyKey(LEGACY_KEY_PATH.read_bytes())

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
    if event_type not in CANONICAL_EVENTS:
        raise LedgerVerificationError(
            f"Unknown event_type at line {line_no}: {event_type!r}"
        )


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

    message = _canonical_json(
        {
            "event_type": record["event_type"],
            "timestamp": record["timestamp"],
            "payload": record["payload"],
            "payload_hash": record["payload_hash"],
            "audited_state_hash": record["audited_state_hash"],
            "key_id": key_id,
        }
    ).encode()

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

    canonical = _canonical_json(payload).encode()
    return hashlib.sha256(canonical).hexdigest()


def _read_ledger() -> List[LedgerRecord]:
    verify_keys = _load_verify_keys()
    records: List[LedgerRecord] = []
    prev_ts = None

    if not LEDGER_PATH.exists():
        raise LedgerVerificationError(f"Ledger file missing: {LEDGER_PATH}")

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
            ]
            for field in required_fields:
                if field not in entry:
                    raise LedgerVerificationError(
                        f"Missing field '{field}' at line {line_no}"
                    )

            event_type = entry["event_type"]
            if not isinstance(event_type, str):
                raise LedgerVerificationError(
                    f"event_type at line {line_no} must be a string"
                )
            _validate_event_type(event_type, line_no)
            _validate_state_hash(entry["audited_state_hash"], line_no)

            timestamp = entry["timestamp"]
            if not isinstance(timestamp, (int, float)):
                raise LedgerVerificationError(
                    f"Timestamp at line {line_no} must be numeric"
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

            _verify_signature(entry, verify_keys, line_no)

            offset = len(records)
            records.append(
                LedgerRecord(
                    offset=offset,
                    event_type=event_type,
                    audited_state_hash=entry["audited_state_hash"],
                    payload_hash=payload_hash,
                )
            )
    return records


def _fetch_index_rows() -> List[Tuple[int, str, str, str]]:
    if not INDEX_PATH.exists():
        raise LedgerVerificationError(f"Ledger index missing: {INDEX_PATH}")

    try:
        with sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True) as con:
            cur = con.execute(
                "SELECT ledger_offset, event_type, state_hash, payload_hash "
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

    for expected_offset, row in enumerate(index_rows):
        ledger_offset, event_type, state_hash, payload_hash = row
        if ledger_offset != expected_offset:
            raise LedgerVerificationError(
                f"Non-contiguous ledger_offset detected at index row {expected_offset}"
            )

        record = records[expected_offset]
        if (
            record.event_type != event_type
            or record.audited_state_hash != state_hash
            or record.payload_hash != payload_hash
        ):
            raise LedgerVerificationError(
                f"Index mismatch at offset {expected_offset}"
            )


def verify_ledger() -> bool:
    try:
        print("[VERIFY] Stage 1 — Validating ledger entries...")
        records = _read_ledger()
        print("[VERIFY] Stage 1 SUCCESS.")

        print("[VERIFY] Stage 2 — Checking index consistency...")
        _compare_index(records)
        print("[VERIFY] Stage 2 SUCCESS.")
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
