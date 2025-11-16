"""Tessrax Memory Engine v1.2.1 (Hardened).

Responsibilities:
* canonical JSON serialisation for deterministic hashing;
* Ed25519 signing via a managed key file;
* atomic append-only writes to the ledger file protected by POSIX locks;
* mirrored writes to the ledger index database to support contradiction checks;
* runtime verification of caller input per Tessrax RVC-001.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from nacl.signing import SigningKey

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
SIGNING_KEY_PATH = Path("tessrax/infra/signing_key.pem")
SIGNING_KEYS_DIR = Path("tessrax/infra/signing_keys")
LEGACY_PUBLIC_KEY_PATH = Path("tessrax/infra/signing_key.pub")
SIGNING_KEY_ID = os.getenv("TESSRAX_KEY_ID", "legacy")
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


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Return deterministic JSON used for hashing/signing (sort_keys=True)."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Compute the canonical SHA-256 digest for ``payload``."""

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _ensure_key() -> SigningKey:
    """Load or create the Ed25519 signing key (seed stored as hex)."""

    SIGNING_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)

    key_bytes: bytes
    if not SIGNING_KEY_PATH.exists():
        signing_key = SigningKey.generate()
        SIGNING_KEY_PATH.write_text(signing_key.encode().hex(), encoding="utf-8")
        os.chmod(SIGNING_KEY_PATH, 0o600)
        _sync_public_material(signing_key)
        return signing_key

    raw_contents = SIGNING_KEY_PATH.read_bytes().strip()
    key_hex: str | None = None
    try:
        key_hex = raw_contents.decode("utf-8").strip()
    except UnicodeDecodeError:
        key_hex = None

    if key_hex:
        try:
            key_bytes = bytes.fromhex(key_hex)
        except ValueError as exc:  # pragma: no cover - invalid manual edits
            raise RuntimeError("Signing key file is not valid hexadecimal.") from exc
    else:
        key_bytes = raw_contents

    if len(key_bytes) != 32:
        raise RuntimeError("Signing key must be exactly 32 bytes of entropy.")

    # Persist as canonical hex to avoid legacy binary encodings.
    SIGNING_KEY_PATH.write_text(key_bytes.hex(), encoding="utf-8")

    signing_key = SigningKey(key_bytes)
    _sync_public_material(signing_key)
    return signing_key


def _sync_public_material(signing_key: SigningKey) -> None:
    """Write the verify key material for both legacy and keyed locations."""

    SIGNING_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_PUBLIC_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    verify_key_hex = signing_key.verify_key.encode().hex() + "\n"
    (SIGNING_KEYS_DIR / f"{SIGNING_KEY_ID}.pub").write_text(verify_key_hex, encoding="utf-8")
    LEGACY_PUBLIC_KEY_PATH.write_text(verify_key_hex, encoding="utf-8")


def _sign_event(canonical: str) -> str:
    """Sign the canonical JSON payload with Ed25519 and return the signature hex."""

    signing_key = _ensure_key()
    signed = signing_key.sign(canonical.encode("utf-8"))
    return signed.signature.hex()


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
    serialized = canonical_json(entry) + "\n"
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
    _ensure_index_schema()

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    payload_hash = canonical_payload_hash(payload)
    canonical_event = {
        "event_type": event_type,
        "timestamp": timestamp,
        "payload": dict(payload),
        "payload_hash": payload_hash,
        "audited_state_hash": audited_state_hash,
        "auditor": AUDITOR_IDENTITY,
        "key_id": SIGNING_KEY_ID,
    }

    canonical_str = canonical_json(canonical_event)
    signature = _sign_event(canonical_str)
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


__all__ = [
    "Receipt",
    "write_receipt",
    "canonical_json",
    "canonical_payload_hash",
    "CANONICAL_EVENT_TYPES",
]
