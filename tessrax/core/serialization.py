"""Canonical serialisation utilities for Tessrax (TESST-compliant).

All helpers enforce deterministic encoding guarantees so that ledger payloads
can be hashed, signed, and replayed across cold environments.  Nested mappings
are normalised recursively to satisfy Deterministic Serialisation v2 and the
Governance Kernel clauses (AEP-001, RVC-001, EAC-001).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from typing import Any, cast


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Return deterministic JSON for ``payload`` (AEP-001 compliant)."""

    materialized = _materialize_for_json(payload)
    return json.dumps(
        materialized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _normalize_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Float values must be finite for canonical normalisation")
    decimal_value = Decimal(str(value)).normalize()
    if decimal_value == 0:
        return 0.0
    return float(decimal_value)


def _normalize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    iso = value.isoformat(timespec="microseconds")
    return iso.replace("+00:00", "Z")


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(value[key])
            for key in sorted(value, key=lambda candidate: str(candidate))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, float):
        return _normalize_float(value)
    if isinstance(value, Decimal):
        as_float = float(value)
        if not math.isfinite(as_float):
            raise ValueError("Decimal values must be finite")
        return _normalize_float(as_float)
    return value


def normalize_payload(payload: Mapping[str, Any]) -> dict:
    """Recursively sort nested mappings for zero-drift hashing (RVC-001)."""

    if not isinstance(payload, Mapping):  # pragma: no cover - guard rail
        raise TypeError("Payload must be a mapping for canonical normalisation")
    return _normalize(payload)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen_mapping = {key: _freeze_value(val) for key, val in value.items()}
        return FrozenPayload(frozen_mapping)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def snapshot_payload(payload: Mapping[str, Any]) -> "FrozenPayload":
    """Return an immutable payload snapshot (DLK-001 + EAC-001)."""

    normalized = normalize_payload(payload)
    frozen = _freeze_value(normalized)
    if not isinstance(frozen, FrozenPayload):  # pragma: no cover - defensive
        raise TypeError("Snapshot generation must return a FrozenPayload mapping")
    return cast(FrozenPayload, frozen)


@dataclass(frozen=True)
class FrozenPayload(Mapping[str, Any]):
    """Read-only mapping for ledger payloads (DLK-001 hardened)."""

    _data: dict[str, Any]
    __tessrax_normalized__: bool = True

    def __getitem__(self, key: str) -> Any:  # pragma: no cover - passthrough
        return self._data[key]

    def __iter__(self):  # pragma: no cover - passthrough
        return iter(self._data)

    def __len__(self) -> int:  # pragma: no cover - passthrough
        return len(self._data)

    def items(self):  # pragma: no cover - passthrough
        return self._data.items()

    def keys(self):  # pragma: no cover - passthrough
        return self._data.keys()

    def values(self):  # pragma: no cover - passthrough
        return self._data.values()


def _materialize_for_json(value: Any) -> Any:
    if isinstance(value, FrozenPayload):
        return {key: _materialize_for_json(val) for key, val in value.items()}
    if isinstance(value, Mapping):
        return {str(key): _materialize_for_json(val) for key, val in value.items()}
    if isinstance(value, tuple):
        return [_materialize_for_json(item) for item in value]
    if isinstance(value, list):
        return [_materialize_for_json(item) for item in value]
    return value


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash ``payload`` after canonical normalisation (TESST verified)."""

    if getattr(payload, "__tessrax_normalized__", False):
        canonical_payload = payload
    else:
        canonical_payload = normalize_payload(payload)
    return hashlib.sha256(canonical_json(canonical_payload).encode("utf-8")).hexdigest()


__all__ = [
    "FrozenPayload",
    "canonical_json",
    "canonical_payload_hash",
    "normalize_payload",
    "snapshot_payload",
]
