"""Truth-lock alignment regression test for Ed25519 signing + verification."""
# ruff: noqa: E402

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

pytest.importorskip("sqlalchemy")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.integration
def test_truth_lock_alignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "truth_lock"
    ledger_dir = sandbox / "tessrax" / "ledger"
    infra_dir = sandbox / "tessrax" / "infra"
    signing_keys_dir = infra_dir / "signing_keys"
    ledger_dir.mkdir(parents=True)
    signing_keys_dir.mkdir(parents=True)

    ledger_path = ledger_dir / "ledger.jsonl"
    index_path = ledger_dir / "index.db"
    merkle_state_path = ledger_dir / "merkle_state.json"
    signing_key_path = infra_dir / "signing_key.pem"
    legacy_pub_path = infra_dir / "signing_key.pub"
    db_path = sandbox / "proceduralist.db"

    monkeypatch.setenv("TESSRAX_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TESSRAX_KEY_ID", "truth-lock")
    monkeypatch.setenv("TESSRAX_GOVERNANCE_TOKEN", "truth-lock-governance")

    key_registry = importlib.reload(importlib.import_module("tessrax.infra.key_registry"))
    key_registry.SIGNING_KEYS_DIR = signing_keys_dir
    key_registry.ACTIVE_KEY_PATH = signing_keys_dir / "active_key.json"
    key_registry.ROTATION_STATE_PATH = signing_keys_dir / "rotation_state.json"
    key_registry.ROTATION_RECEIPTS_PATH = signing_keys_dir / "rotation_receipts.json"
    key_registry.LEGACY_PRIVATE_KEY_PATH = signing_key_path
    key_registry.LEGACY_PUBLIC_KEY_PATH = legacy_pub_path

    memory_engine = importlib.reload(importlib.import_module("tessrax.core.memory_engine"))
    ledger_verify = importlib.reload(importlib.import_module("tessrax.ledger.verify_ledger"))
    core_runner = importlib.reload(importlib.import_module("tessrax.core.core_runner"))

    memory_engine.LEDGER_PATH = ledger_path
    memory_engine.INDEX_PATH = index_path
    memory_engine.MERKLE_STATE_PATH = merkle_state_path

    ledger_verify.LEDGER_PATH = ledger_path
    ledger_verify.INDEX_PATH = index_path
    ledger_verify.SIGNING_KEYS_DIR = signing_keys_dir
    ledger_verify.LEGACY_KEY_PATH = legacy_pub_path
    ledger_verify.MERKLE_STATE_PATH = merkle_state_path

    from tessrax.services.proceduralist.database import models

    models.Base.metadata.create_all(core_runner.engine)

    db_session = core_runner.SessionLocal()
    try:
        node = models.StateNode(
            state_hash="abcd" * 16,
            url="https://example.org/state",
            title="Truth Lock",
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        core_runner.process_node(db_session, node)
        db_session.commit()
    finally:
        db_session.close()

    assert ledger_path.exists(), "Ledger should exist after processing a node"
    assert ledger_verify.verify() is True
