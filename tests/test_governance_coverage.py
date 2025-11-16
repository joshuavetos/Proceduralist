from __future__ import annotations

import importlib
import os
from pathlib import Path

from tessrax.governance import coverage
from tessrax.ledger.stress_harness import generate_stress_ledger


def _sandbox_registry(tmp_path: Path):
    module = importlib.reload(importlib.import_module("tessrax.infra.key_registry"))
    signing_root = tmp_path / "infra" / "signing_keys"
    signing_root.mkdir(parents=True)
    module.SIGNING_KEYS_DIR = signing_root
    module.ACTIVE_KEY_PATH = signing_root / "active_key.json"
    module.ROTATION_STATE_PATH = signing_root / "rotation_state.json"
    module.ROTATION_RECEIPTS_PATH = signing_root / "rotation_receipts.json"
    module.LEGACY_PRIVATE_KEY_PATH = signing_root.parent / "signing_key.pem"
    module.LEGACY_PUBLIC_KEY_PATH = signing_root.parent / "signing_key.pub"
    return module


def test_contradiction_stress_and_replay(tmp_path: Path) -> None:
    index_path = tmp_path / "index.db"
    result = coverage.contradiction_stress_harness(total_nodes=7, index_path=index_path)
    assert result.nodes_checked == 7
    assert result.contradictions_found >= 2
    assert result.ledger_index_ready is True

    ledger_path = tmp_path / "ledger.jsonl"
    generate_stress_ledger(output_path=ledger_path, entries=4)
    replay_report = coverage.governance_replay_simulator(ledger_path=ledger_path)
    assert replay_report.entry_count == 4
    assert len(replay_report.merkle_root) == 64


def test_receipt_normalizer() -> None:
    receipt = {"timestamp": "2024-01-01T00:00:00Z", "payload": {"b": 2, "a": 1}}
    normalized = coverage.audit_receipt_normalizer(receipt)
    assert normalized.size_bytes > 10
    assert normalized.canonical_hash == coverage.audit_receipt_normalizer(receipt).canonical_hash


def test_multisig_rotation_verifier(tmp_path: Path) -> None:
    registry = _sandbox_registry(tmp_path)
    os.environ["TESSRAX_KEY_ID"] = "suite"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "alpha,beta"
    os.environ["TESSRAX_REQUIRED_APPROVERS"] = "alpha,beta"
    registry.rotate_key(reason="bootstrap", governance_token="alpha,beta", force=True)
    registry.rotate_key(reason="rollover", governance_token="alpha,beta", new_key_id="suite-next", force=True)
    report = coverage.multisig_rotation_verifier(rotation_state_path=registry.ROTATION_STATE_PATH)
    assert report.quorum_satisfied is True
    assert set(report.approvals_present) == {"alpha", "beta"}
    assert report.latest_receipt_hash is not None
    os.environ.pop("TESSRAX_REQUIRED_APPROVERS", None)
