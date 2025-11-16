"""Cold-start integration test for Tessrax OS primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tessrax.memory.memory_engine import write_receipt
from tessrax.governance.governance_kernel import classify_clean
from tessrax.ledger.verify_ledger import verify as verify_ledger
from tessrax.aion.verify_local import verify_local_ledger

import tessrax.core.memory_engine as core_memory
import tessrax.ledger.verify_ledger as ledger_module
import tessrax.aion.verify_local as aion_verify


@dataclass
class DummyNode:
    id: int
    state_hash: str
    url: str
    title: str


def test_cold_start(tmp_path: Path) -> None:
    sandbox = tmp_path / "tessrax_sandbox"
    ledger_dir = sandbox / "tessrax" / "ledger"
    ledger_dir.mkdir(parents=True)
    infra_dir = sandbox / "tessrax" / "infra"
    signing_keys_dir = infra_dir / "signing_keys"
    signing_keys_dir.mkdir(parents=True)

    ledger_path = ledger_dir / "ledger.jsonl"
    index_path = ledger_dir / "index.db"
    hmac_key_path = infra_dir / "signing_key.pem"
    legacy_pub_path = infra_dir / "signing_key.pub"

    key_id = "test-key"
    core_memory.LEDGER_PATH = ledger_path
    core_memory.INDEX_PATH = index_path
    core_memory.SIGNING_KEY_PATH = hmac_key_path
    core_memory.SIGNING_KEYS_DIR = signing_keys_dir
    core_memory.LEGACY_PUBLIC_KEY_PATH = legacy_pub_path
    core_memory.SIGNING_KEY_ID = key_id

    ledger_module.LEDGER_PATH = ledger_path
    ledger_module.INDEX_PATH = index_path
    ledger_module.SIGNING_KEYS_DIR = signing_keys_dir
    ledger_module.LEGACY_KEY_PATH = legacy_pub_path

    aion_verify.LEDGER_PATH = ledger_path
    aion_verify.INDEX_PATH = index_path
    aion_verify.SIGNING_KEYS_DIR = signing_keys_dir
    aion_verify.LEGACY_KEY_PATH = legacy_pub_path

    payloads = [
        {"node_id": 1, "status": "VERIFIED", "url": "http://example.com"},
        {"node_id": 2, "status": "VERIFIED", "url": "http://example.com/login"},
        {"node_id": 3, "status": "VERIFIED", "url": "http://example.com/cart"},
    ]

    for idx, payload in enumerate(payloads):
        write_receipt(
            event_type="STATE_AUDITED",
            payload=payload,
            audited_state_hash=f"{idx:064x}",
        )

    assert verify_ledger() is True
    receipts = verify_local_ledger()
    assert len(receipts) == 3

    nodes = [
        DummyNode(id=1, state_hash="a" * 64, url="http://example.com", title="Home"),
        DummyNode(id=2, state_hash="b" * 64, url="http://example.com/login", title="Login"),
    ]
    decisions = [classify_clean(node, recurrence_count=idx) for idx, node in enumerate(nodes)]
    assert all(decision.decision == "VERIFIED" for decision in decisions)
    assert all(decision.category == "CLEAN" for decision in decisions)
    assert all(decision.policy_code.startswith("POL#CLEAN") for decision in decisions)
    assert all(isinstance(decision.tags, tuple) and decision.tags for decision in decisions)
    assert len(verify_local_ledger()) == 3
