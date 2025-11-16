"""Merkle integrity regression tests for Tessrax ledger."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tessrax.memory.memory_engine import write_receipt
from tessrax.ledger.merkle import MerkleAccumulator, verify_merkle

import tessrax.core.memory_engine as core_memory
import tessrax.ledger.verify_ledger as ledger_module
import tessrax.aion.verify_local as aion_verify


def _bootstrap_paths(tmp_path: Path) -> None:
    sandbox = tmp_path / "merkle_sandbox"
    ledger_dir = sandbox / "tessrax" / "ledger"
    ledger_dir.mkdir(parents=True)
    infra_dir = sandbox / "tessrax" / "infra"
    signing_keys_dir = infra_dir / "signing_keys"
    signing_keys_dir.mkdir(parents=True)

    ledger_path = ledger_dir / "ledger.jsonl"
    index_path = ledger_dir / "index.db"
    hmac_key_path = infra_dir / "signing_key.pem"
    legacy_pub_path = infra_dir / "signing_key.pub"
    merkle_state_path = ledger_dir / "merkle_state.json"

    os.environ["TESSRAX_KEY_ID"] = "merkle-test-key"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "merkle-gov"

    key_registry = importlib.reload(importlib.import_module("tessrax.infra.key_registry"))
    key_registry.SIGNING_KEYS_DIR = signing_keys_dir
    key_registry.ACTIVE_KEY_PATH = signing_keys_dir / "active_key.json"
    key_registry.ROTATION_STATE_PATH = signing_keys_dir / "rotation_state.json"
    key_registry.LEGACY_PRIVATE_KEY_PATH = hmac_key_path
    key_registry.LEGACY_PUBLIC_KEY_PATH = legacy_pub_path

    core_memory.LEDGER_PATH = ledger_path
    core_memory.INDEX_PATH = index_path
    core_memory.MERKLE_STATE_PATH = merkle_state_path

    ledger_module.LEDGER_PATH = ledger_path
    ledger_module.INDEX_PATH = index_path
    ledger_module.SIGNING_KEYS_DIR = signing_keys_dir
    ledger_module.LEGACY_KEY_PATH = legacy_pub_path
    ledger_module.MERKLE_STATE_PATH = merkle_state_path

    aion_verify.LEDGER_PATH = ledger_path
    aion_verify.INDEX_PATH = index_path
    aion_verify.SIGNING_KEYS_DIR = signing_keys_dir
    aion_verify.LEGACY_KEY_PATH = legacy_pub_path
    aion_verify.LOCAL_MERKLE_STATE_PATH = merkle_state_path


def test_merkle_state_matches_entries(tmp_path: Path) -> None:
    _bootstrap_paths(tmp_path)

    payloads = [
        {"node_id": idx, "status": "VERIFIED", "url": f"https://example.com/{idx}"}
        for idx in range(3)
    ]
    for idx, payload in enumerate(payloads):
        write_receipt(
            event_type="STATE_AUDITED",
            payload=payload,
            audited_state_hash=f"{idx:064x}",
        )

    accumulator = MerkleAccumulator(state_path=core_memory.MERKLE_STATE_PATH)
    assert accumulator.state.entry_count == len(payloads)
    assert verify_merkle(core_memory.LEDGER_PATH, core_memory.MERKLE_STATE_PATH)
