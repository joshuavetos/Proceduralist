"""Canonical serialisation utilities for Tessrax (TESST-compliant).

All helpers enforce deterministic encoding guarantees so that ledger payloads
can be hashed, signed, and replayed across cold environments.  Nested mappings
are normalised recursively to satisfy Deterministic Serialisation v2.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Return deterministic JSON for ``payload`` using UTF-8 + sorted keys."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    return value


def normalize_payload(payload: Mapping[str, Any]) -> dict:
    """Recursively sort nested mappings for zero-drift hashing."""

    if not isinstance(payload, Mapping):  # pragma: no cover - guard rail
        raise TypeError("Payload must be a mapping for canonical normalisation")
    return _normalize(payload)


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash ``payload`` after canonical normalisation."""

    normalized = normalize_payload(payload)
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


__all__ = ["canonical_json", "canonical_payload_hash", "normalize_payload"]
