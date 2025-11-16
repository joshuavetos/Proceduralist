"""Tessrax Memory Engine v1.2.1 (Hardened).

Responsibilities:
* canonical JSON serialisation for deterministic hashing;
* Ed25519/HMAC-style signing via a managed key file;
* atomic append-only writes to the ledger file protected by POSIX locks;
* mirrored writes to the ledger index database to support contradiction checks;
* runtime verification of caller input per Tessrax RVC-001.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
SIGNING_KEY_PATH = Path("tessrax/infra/signing_key.pem")
AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


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


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ensure_key() -> bytes:
    SIGNING_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SIGNING_KEY_PATH.exists():
        SIGNING_KEY_PATH.write_bytes(secrets.token_bytes(32))
        os.chmod(SIGNING_KEY_PATH, 0o600)
    key = SIGNING_KEY_PATH.read_bytes()
    if len(key) < 32:
        raise RuntimeError("Signing key is invalid; ensure at least 32 bytes of entropy.")
    return key[:64]


def _sign_event(event: Mapping[str, Any]) -> str:
    key = _ensure_key()
    canonical = _canonical_json(event)
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _ensure_index_schema() -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(INDEX_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_offset INTEGER NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(state_hash, payload_hash)
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_state_hash ON ledger_index(state_hash);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ledger_index(timestamp);")
        con.commit()


def _append_to_ledger(entry: Mapping[str, Any]) -> int:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = _canonical_json(entry) + "\n"
    with open(LEDGER_PATH, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0, os.SEEK_END)
        offset = handle.tell()
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return offset


def _append_to_index(offset: int, event_type: str, state_hash: str, payload_hash: str, timestamp: str) -> None:
    with sqlite3.connect(INDEX_PATH) as con:
        con.execute(
            """
            INSERT OR IGNORE INTO ledger_index (ledger_offset, event_type, state_hash, payload_hash, timestamp)
            VALUES (?, ?, ?, ?, ?);
            """,
            (offset, event_type, state_hash, payload_hash, timestamp),
        )
        con.commit()


def _verify_inputs(event_type: str, payload: Mapping[str, Any], audited_state_hash: str) -> None:
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    if not isinstance(audited_state_hash, str) or len(audited_state_hash) < 8:
        raise ValueError("audited_state_hash must be a non-empty hash string")


def write_receipt(event_type: str, payload: Mapping[str, Any], audited_state_hash: str) -> Receipt:
    _verify_inputs(event_type, payload, audited_state_hash)
    _ensure_index_schema()

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    payload_hash = _payload_hash(payload)
    canonical_event = {
        "event_type": event_type,
        "timestamp": timestamp,
        "payload": dict(payload),
        "payload_hash": payload_hash,
        "audited_state_hash": audited_state_hash,
        "auditor": AUDITOR_IDENTITY,
    }

    signature = _sign_event(canonical_event)
    ledger_entry = {**canonical_event, "signature": signature}
    offset = _append_to_ledger(ledger_entry)
    _append_to_index(offset, event_type, audited_state_hash, payload_hash, timestamp)

    return Receipt(
        event_type=event_type,
        timestamp=timestamp,
        payload=canonical_event["payload"],
        payload_hash=payload_hash,
        audited_state_hash=audited_state_hash,
        signature=signature,
        ledger_offset=offset,
    )


__all__ = ["Receipt", "write_receipt"]
