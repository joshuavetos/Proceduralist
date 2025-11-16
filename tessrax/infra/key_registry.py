"""Multi-key rotation registry for Tessrax signing authority (MKRS-001).

This module centralises all key lifecycle management concerns:

* keys are stored under ``tessrax/infra/signing_keys`` with ``.pem`` and
  ``.pub`` material per ``key_id``;
* ``rotation_state.json`` captures the rotation schedule, policy snapshot, and
  per-key deprecation windows; and
* ``active_key.json`` provides the active-key pointer consumed by the memory
  engine when emitting ledger receipts.

Every public helper enforces Tessrax governance clauses (AEP-001/EAC-001/
RVC-001/POST-AUDIT-001) by validating inputs, ensuring deterministic file
layouts, and emitting auditable metadata records.  ``rotate_key`` requires an
explicit governance token so that each rotation event is backed by an approval
record from the governance kernel.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Tuple

from nacl.signing import SigningKey

AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"
SIGNING_KEYS_DIR = Path("tessrax/infra/signing_keys")
LEGACY_PRIVATE_KEY_PATH = Path("tessrax/infra/signing_key.pem")
LEGACY_PUBLIC_KEY_PATH = Path("tessrax/infra/signing_key.pub")
ACTIVE_KEY_PATH = SIGNING_KEYS_DIR / "active_key.json"
ROTATION_STATE_PATH = SIGNING_KEYS_DIR / "rotation_state.json"

DEFAULT_POLICY = {
    "min_hours_between_rotations": 1.0,
    "max_active_age_hours": 720.0,  # 30 days
    "deprecation_window_hours": 720.0,
}


@dataclass(frozen=True)
class RotationState:
    """Runtime representation of the rotation schedule file."""

    active_key: str
    state: Dict[str, Any]


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_bytes()
    if not raw.strip():
        return {}
    return json.loads(raw.decode("utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _private_key_path(key_id: str) -> Path:
    return SIGNING_KEYS_DIR / f"{key_id}.pem"


def _public_key_path(key_id: str) -> Path:
    return SIGNING_KEYS_DIR / f"{key_id}.pub"


def _read_state() -> Dict[str, Any]:
    state = _load_json(ROTATION_STATE_PATH)
    if not state:
        state = {
            "policy": dict(DEFAULT_POLICY),
            "schedule": {"last_rotation": None, "next_rotation_due": None},
            "active_key": None,
            "keys": {},
        }
    return state


def _save_state(state: Dict[str, Any]) -> None:
    _write_json(ROTATION_STATE_PATH, state)


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _persist_material(key_id: str, signing_key: SigningKey) -> Tuple[Path, Path]:
    SIGNING_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private_path = _private_key_path(key_id)
    public_path = _public_key_path(key_id)
    private_path.write_text(signing_key.encode().hex() + "\n", encoding="utf-8")
    os.chmod(private_path, 0o600)
    public_path.write_text(signing_key.verify_key.encode().hex() + "\n", encoding="utf-8")
    return private_path, public_path


def _require_governance(governance_token: str, force: bool) -> None:
    expected = os.getenv("TESSRAX_GOVERNANCE_TOKEN")
    if expected and governance_token != expected and not force:
        raise PermissionError("Governance token mismatch; rotation denied")


def _rotation_policy(state: Dict[str, Any]) -> Dict[str, float]:
    policy = state.get("policy") or {}
    merged = dict(DEFAULT_POLICY)
    for key, value in policy.items():
        if isinstance(value, (int, float)) and value > 0:
            merged[key] = float(value)
    state["policy"] = merged
    return merged


def _record_active_key(key_id: str) -> None:
    active_payload = {"key_id": key_id, "updated_at": _utcnow().isoformat()}
    _write_json(ACTIVE_KEY_PATH, active_payload)


def _promote_new_key(
    state: Dict[str, Any],
    new_key_id: str,
    signing_key: SigningKey,
    reason: str,
    governance_token: str,
    *,
    previous_key_id: str | None,
    force: bool,
) -> Tuple[Path, Path]:
    policy = _rotation_policy(state)
    now = _utcnow()
    schedule = state.setdefault("schedule", {})
    last_rotation = schedule.get("last_rotation")
    if last_rotation and not force:
        last_dt = datetime.fromisoformat(last_rotation)
        delta = now - last_dt
        minimum = timedelta(hours=policy["min_hours_between_rotations"])
        if delta < minimum:
            raise RuntimeError("Rotation requested before minimum interval elapsed")

    max_age = timedelta(hours=policy["max_active_age_hours"])
    schedule["last_rotation"] = now.isoformat()
    schedule["next_rotation_due"] = (now + max_age).isoformat()

    cross_record: Dict[str, Any] | None = None
    if previous_key_id:
        prev_path = _private_key_path(previous_key_id)
        if not prev_path.exists():
            raise FileNotFoundError(f"Previous key material missing for '{previous_key_id}'")
        prev_hex = prev_path.read_text(encoding="utf-8").strip()
        try:
            prev_key = SigningKey(bytes.fromhex(prev_hex))
        except ValueError as exc:  # pragma: no cover - protects manual edits
            raise RuntimeError("Previous signing key is not valid hex") from exc
        cross_payload = {
            "event": "KEY_ROTATION",
            "previous_key_id": previous_key_id,
            "new_key_id": new_key_id,
            "timestamp": now.isoformat(),
            "reason": reason,
            "auditor": AUDITOR_IDENTITY,
        }
        canonical = _canonical_json(cross_payload).encode("utf-8")
        cross_record = {
            "payload": cross_payload,
            "signed_by_previous": prev_key.sign(canonical).signature.hex(),
            "signed_by_new": signing_key.sign(canonical).signature.hex(),
        }
        previous_meta = state.setdefault("keys", {}).setdefault(previous_key_id, {})
        previous_meta.update(
            {
                "status": "legacy",
                "last_active": now.isoformat(),
                "deprecation_window": {
                    "start": now.isoformat(),
                    "end": (now + timedelta(hours=policy["deprecation_window_hours"])).isoformat(),
                },
            }
        )

    private_path, public_path = _persist_material(new_key_id, signing_key)
    state.setdefault("keys", {})[new_key_id] = {
        "status": "active",
        "created_at": now.isoformat(),
        "activated_at": now.isoformat(),
        "policy_snapshot": policy,
        "deprecation_window": {
            "start": now.isoformat(),
            "end": (now + timedelta(hours=policy["deprecation_window_hours"])).isoformat(),
        },
        "cross_signature": cross_record,
        "governance_approval": {
            "approver": os.getenv("TESSRAX_ROTATION_APPROVER", AUDITOR_IDENTITY),
            "token_digest": _hash_token(governance_token),
            "issued_at": now.isoformat(),
        },
        "reason": reason,
    }

    state["active_key"] = new_key_id
    _record_active_key(new_key_id)
    LEGACY_PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_PRIVATE_KEY_PATH.write_text(signing_key.encode().hex() + "\n", encoding="utf-8")
    os.chmod(LEGACY_PRIVATE_KEY_PATH, 0o600)
    LEGACY_PUBLIC_KEY_PATH.write_text(signing_key.verify_key.encode().hex() + "\n", encoding="utf-8")

    return private_path, public_path


def rotate_key(
    *,
    reason: str,
    governance_token: str,
    new_key_id: str | None = None,
    force: bool = False,
) -> Tuple[Path, Path]:
    """Rotate to a freshly generated key under governance approval."""

    if not reason or not reason.strip():
        raise ValueError("Rotation reason must be a non-empty string")
    if not governance_token:
        raise ValueError("Governance token is required for rotation")

    state = _read_state()
    _require_governance(governance_token, force)

    previous_key = state.get("active_key")
    key_id = new_key_id or os.getenv("TESSRAX_KEY_ID", "legacy")
    if key_id in (state.get("keys") or {}) and not force:
        raise FileExistsError(f"Key '{key_id}' already exists; pass force=True to overwrite")

    signing_key = SigningKey.generate()
    private_path, public_path = _promote_new_key(
        state,
        key_id,
        signing_key,
        reason,
        governance_token,
        previous_key_id=previous_key,
        force=force,
    )
    _save_state(state)
    return private_path, public_path


def _bootstrap_if_needed() -> RotationState:
    state = _read_state()
    active_key = state.get("active_key")
    if active_key:
        return RotationState(active_key=active_key, state=state)

    if LEGACY_PRIVATE_KEY_PATH.exists():
        raw = LEGACY_PRIVATE_KEY_PATH.read_text(encoding="utf-8").strip()
        try:
            signing_key = SigningKey(bytes.fromhex(raw))
        except ValueError as exc:  # pragma: no cover - guard corrupted file
            raise RuntimeError("Legacy signing key is not valid hex") from exc
    else:
        signing_key = SigningKey.generate()

    key_id = os.getenv("TESSRAX_KEY_ID", "legacy")
    governance_token = os.getenv("TESSRAX_GOVERNANCE_TOKEN", "bootstrap")
    private_path, public_path = _promote_new_key(
        state,
        key_id,
        signing_key,
        reason="bootstrap", 
        governance_token=governance_token,
        previous_key_id=None,
        force=True,
    )
    _save_state(state)
    # ensure on-disk compatibility even if bootstrap reused existing files
    if not LEGACY_PRIVATE_KEY_PATH.exists():
        LEGACY_PRIVATE_KEY_PATH.write_text(signing_key.encode().hex() + "\n", encoding="utf-8")
        os.chmod(LEGACY_PRIVATE_KEY_PATH, 0o600)
    if not LEGACY_PUBLIC_KEY_PATH.exists():
        LEGACY_PUBLIC_KEY_PATH.write_text(signing_key.verify_key.encode().hex() + "\n", encoding="utf-8")
    return RotationState(active_key=key_id, state=state)


def load_active_signing_key() -> Tuple[str, SigningKey]:
    """Return the active ``(key_id, SigningKey)`` tuple, bootstrapping if needed."""

    rotation_state = _bootstrap_if_needed()
    key_id = rotation_state.active_key
    private_path = _private_key_path(key_id)
    if not private_path.exists():
        raise FileNotFoundError(f"Active key material missing at {private_path}")
    raw = private_path.read_text(encoding="utf-8").strip()
    if len(raw) != 64:
        raise RuntimeError("Stored key material must be 32-byte hex seed")
    signing_key = SigningKey(bytes.fromhex(raw))
    return key_id, signing_key


def get_active_key_id() -> str:
    """Return the currently active key identifier."""

    rotation_state = _bootstrap_if_needed()
    return rotation_state.active_key


def rotation_status() -> Dict[str, Any]:
    """Expose the rotation state for observability endpoints/tests."""

    return _read_state()


__all__ = [
    "rotate_key",
    "load_active_signing_key",
    "get_active_key_id",
    "rotation_status",
    "SIGNING_KEYS_DIR",
    "LEGACY_PRIVATE_KEY_PATH",
    "LEGACY_PUBLIC_KEY_PATH",
    "ACTIVE_KEY_PATH",
    "ROTATION_STATE_PATH",
]
