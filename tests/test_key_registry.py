"""Unit tests for Tessrax multi-key rotation registry (MKRS-001)."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


def _sandbox_registry(tmp_path: Path):
    module = importlib.reload(importlib.import_module("tessrax.infra.key_registry"))
    signing_root = tmp_path / "infra" / "signing_keys"
    signing_root.mkdir(parents=True)
    module.SIGNING_KEYS_DIR = signing_root
    module.ACTIVE_KEY_PATH = signing_root / "active_key.json"
    module.ROTATION_STATE_PATH = signing_root / "rotation_state.json"
    module.LEGACY_PRIVATE_KEY_PATH = signing_root.parent / "signing_key.pem"
    module.LEGACY_PUBLIC_KEY_PATH = signing_root.parent / "signing_key.pub"
    return module


def test_rotation_creates_schedule_and_cross_signatures(tmp_path: Path) -> None:
    os.environ["TESSRAX_KEY_ID"] = "alpha"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "gov-token"
    registry = _sandbox_registry(tmp_path)

    private_path, public_path = registry.rotate_key(reason="initial", governance_token="gov-token")
    assert private_path.exists()
    assert public_path.exists()

    state = registry.rotation_status()
    assert state["active_key"] == "alpha"
    assert state["schedule"]["next_rotation_due"]

    # Second rotation should generate cross-signature receipts and mark legacy windows.
    private_path, public_path = registry.rotate_key(
        reason="rollover",
        governance_token="gov-token",
        new_key_id="bravo",
        force=True,
    )
    assert private_path.name.endswith("bravo.pem")
    assert public_path.name.endswith("bravo.pub")

    state = registry.rotation_status()
    assert state["active_key"] == "bravo"
    bravo_meta = state["keys"]["bravo"]
    assert bravo_meta["status"] == "active"
    assert "cross_signature" in bravo_meta and bravo_meta["cross_signature"]
    assert bravo_meta["cross_signature"]["signed_by_previous"]
    assert bravo_meta["governance_approval"]["token_digest"]

    alpha_meta = state["keys"]["alpha"]
    assert alpha_meta["status"] == "legacy"
    window = alpha_meta["deprecation_window"]
    assert window["start"] < window["end"]

    # Third rotation immediately should respect min interval and fail.
    with pytest.raises(RuntimeError):
        registry.rotate_key(reason="too-fast", governance_token="gov-token", new_key_id="charlie")


def test_governance_token_required(tmp_path: Path) -> None:
    os.environ["TESSRAX_KEY_ID"] = "delta"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "expected"
    registry = _sandbox_registry(tmp_path)

    # Initial rotation allowed because environment token matches.
    registry.rotate_key(reason="bootstrap", governance_token="expected")

    with pytest.raises(PermissionError):
        registry.rotate_key(reason="bad-token", governance_token="wrong")

    key_id, key = registry.load_active_signing_key()
    assert key_id == "delta"
    assert key.verify_key
