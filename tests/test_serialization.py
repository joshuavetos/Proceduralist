"""Regression tests for canonical serialization rules (AEP-001 compliant)."""
from __future__ import annotations

from datetime import datetime, timezone
import math

import pytest

from tessrax.core.serialization import (
    FrozenPayload,
    canonical_payload_hash,
    normalize_payload,
    snapshot_payload,
)


def test_normalize_payload_handles_floats_and_datetimes() -> None:
    payload = {
        "ts": datetime(2025, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc),
        "nested": {"value": -0.0, "list": [1, 2.0, 3.1415926535]},
    }

    normalized = normalize_payload(payload)
    assert normalized["nested"]["value"] == 0.0
    assert normalized["ts"].endswith("Z")
    assert "T03:04:05.123456Z" in normalized["ts"]


def test_normalize_payload_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError):
        normalize_payload({"value": math.inf})


def test_snapshot_payload_is_immutable_and_hashable() -> None:
    payload = {"alpha": {"beta": 1}, "gamma": [1, 2]}
    frozen = snapshot_payload(payload)
    assert isinstance(frozen, FrozenPayload)

    payload["alpha"]["beta"] = 99
    payload["gamma"].append(3)

    assert frozen["alpha"]["beta"] == 1
    assert frozen["gamma"] == (1, 2)

    with pytest.raises(TypeError):  # type: ignore[misc]
        frozen["alpha"] = "mutate"  # type: ignore[index]

    digest = canonical_payload_hash(frozen)
    assert isinstance(digest, str)
    assert len(digest) == 64
