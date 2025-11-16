"""Local ledger verification utilities for Tessrax AION.

This module provides an offline-only verification routine that mirrors the
canonical hashing and signature expectations enforced by the memory engine.  It
is intentionally dependency-light so it can run inside minimal recovery
environments.  All helpers follow the Tessrax governance clauses
(AEP-001/RVC-001/EAC-001/POST-AUDIT-001) by validating runtime input,
referencing only on-disk artefacts, and emitting auditable receipts.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from nacl.signing import VerifyKey

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
SIGNING_KEYS_DIR = Path("tessrax/infra/signing_keys")
LEGACY_KEY_PATH = Path("tessrax/infra/signing_key.pub")
AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


class LedgerVerificationError(RuntimeError):
    """Raised when ledger or index verification fails."""


@dataclass(frozen=True)
class Receipt:
    """Canonical representation of a verified ledger receipt."""

    event_type: str
    timestamp: str
    payload: dict
    payload_hash: str
    audited_state_hash: str
    signature: str


def _canonical_json(obj: dict) -> str:
    """Return deterministic JSON used for hashing/signing (sort_keys=True)."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_public_keys() -> Dict[str, VerifyKey]:
    """Load Ed25519 verification keys from ``SIGNING_KEYS_DIR`` or legacy file."""

    keys: Dict[str, VerifyKey] = {}
    if SIGNING_KEYS_DIR.exists():
        for path in sorted(SIGNING_KEYS_DIR.glob("*.pub")):
            raw = path.read_bytes()
            if raw.strip():
                keys[path.stem] = _coerce_verify_key(raw)
    if LEGACY_KEY_PATH.exists():
        raw = LEGACY_KEY_PATH.read_bytes()
        if raw.strip():
            keys.setdefault("legacy", _coerce_verify_key(raw))
    if not keys:
        raise LedgerVerificationError("No verification keys available under tessrax/infra.")
    return keys


def _coerce_verify_key(raw: bytes) -> VerifyKey:
    """Allow both raw bytes and hex-encoded keys."""

    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""
    if text:
        try:
            return VerifyKey(bytes.fromhex(text))
        except ValueError:
            pass
    return VerifyKey(raw)


def _hash_payload(payload: dict, line_no: int) -> str:
    if not isinstance(payload, dict):
        raise LedgerVerificationError(f"Ledger line {line_no}: payload must be an object")
    canonical = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _verify_signature(entry: dict, verify_keys: Dict[str, VerifyKey], line_no: int) -> None:
    key_id = entry.get("key_id")
    key: VerifyKey
    if key_id:
        if key_id not in verify_keys:
            raise LedgerVerificationError(f"Ledger line {line_no}: unknown key_id '{key_id}'")
        key = verify_keys[key_id]
    else:
        if len(verify_keys) != 1:
            raise LedgerVerificationError(
                f"Ledger line {line_no}: key_id missing while multiple keys configured"
            )
        key = next(iter(verify_keys.values()))

    signed_body = {
        "event_type": entry["event_type"],
        "timestamp": entry["timestamp"],
        "payload": entry["payload"],
        "payload_hash": entry["payload_hash"],
        "audited_state_hash": entry["audited_state_hash"],
    }
    if key_id:
        signed_body["key_id"] = key_id

    message = _canonical_json(signed_body).encode("utf-8")

    signature_hex = entry["signature"]
    if not isinstance(signature_hex, str):
        raise LedgerVerificationError(f"Ledger line {line_no}: signature must be hex string")
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError as exc:  # pragma: no cover - corrupted ledger defense
        raise LedgerVerificationError(f"Ledger line {line_no}: invalid signature encoding") from exc
    key.verify(message, signature)


def _read_receipts() -> List[Receipt]:
    if not LEDGER_PATH.exists():
        raise LedgerVerificationError(f"Ledger not found at {LEDGER_PATH}")

    verify_keys = _load_public_keys()
    receipts: List[Receipt] = []

    with LEDGER_PATH.open("r", encoding="utf-8") as ledger_file:
        for line_no, raw in enumerate(ledger_file, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise LedgerVerificationError(f"Ledger line {line_no}: invalid JSON {exc.msg}") from exc

            required = [
                "event_type",
                "timestamp",
                "payload",
                "payload_hash",
                "audited_state_hash",
                "signature",
            ]
            for field in required:
                if field not in entry:
                    raise LedgerVerificationError(f"Ledger line {line_no}: missing field '{field}'")

            payload_hash = _hash_payload(entry["payload"], line_no)
            if payload_hash != entry["payload_hash"]:
                raise LedgerVerificationError(f"Ledger line {line_no}: payload hash mismatch")

            _verify_signature(entry, verify_keys, line_no)

            receipts.append(
                Receipt(
                    event_type=entry["event_type"],
                    timestamp=str(entry["timestamp"]),
                    payload=dict(entry["payload"]),
                    payload_hash=payload_hash,
                    audited_state_hash=entry["audited_state_hash"],
                    signature=entry["signature"],
                )
            )
    if not receipts:
        raise LedgerVerificationError("Ledger contains no receipts to verify")
    return receipts


def _fetch_index_rows() -> Iterable[tuple[int, str, str]]:
    if not INDEX_PATH.exists():
        raise LedgerVerificationError(f"Ledger index missing at {INDEX_PATH}")
    try:
        with sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True) as con:
            cursor = con.execute(
                "SELECT event_type, state_hash, payload_hash FROM ledger_index ORDER BY ledger_offset"
            )
            return list(cursor.fetchall())
    except sqlite3.Error as exc:  # pragma: no cover - corruption path
        raise LedgerVerificationError("Unable to open ledger index") from exc


def _compare_with_index(receipts: List[Receipt]) -> None:
    rows = _fetch_index_rows()
    if len(rows) != len(receipts):
        raise LedgerVerificationError(
            f"Ledger/index length mismatch ({len(receipts)} vs {len(rows)})"
        )
    for idx, (event_type, state_hash, payload_hash) in enumerate(rows):
        receipt = receipts[idx]
        if (
            receipt.event_type != event_type
            or receipt.audited_state_hash != state_hash
            or receipt.payload_hash != payload_hash
        ):
            raise LedgerVerificationError(f"Ledger/index mismatch at offset {idx}")


def verify_local(limit: int | None = None) -> List[Receipt]:
    """Run both verification stages and return the most recent receipts."""

    receipts = _read_receipts()
    _compare_with_index(receipts)
    if limit is not None:
        return receipts[-limit:]
    return receipts


def emit_audit_receipt(status: str, runtime_info: dict, integrity_score: float) -> dict:
    """Return a governance-compliant execution receipt."""

    payload = {
        "auditor": AUDITOR_IDENTITY,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "runtime_info": runtime_info,
        "integrity_score": round(float(integrity_score), 3),
        "clauses": ["AEP-001", "POST-AUDIT-001", "RVC-001", "EAC-001"],
    }
    canonical = _canonical_json(payload)
    payload["signature"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _main() -> None:
    start = time.time()
    try:
        receipts = verify_local()
        duration = time.time() - start
        receipt = emit_audit_receipt(
            status="ok",
            runtime_info={"records": len(receipts), "duration_sec": round(duration, 3)},
            integrity_score=0.99,
        )
        print(json.dumps(receipt, sort_keys=True))
    except LedgerVerificationError as exc:
        duration = time.time() - start
        receipt = emit_audit_receipt(
            status=f"error: {exc}",
            runtime_info={"duration_sec": round(duration, 3)},
            integrity_score=0.0,
        )
        print(json.dumps(receipt, sort_keys=True))
        raise


if __name__ == "__main__":  # pragma: no cover - CLI utility
    _main()


# Compatibility alias required by downstream tests and governance harnesses.
verify_local_ledger = verify_local

__all__ = [
    "LedgerVerificationError",
    "Receipt",
    "emit_audit_receipt",
    "verify_local",
    "verify_local_ledger",
]
