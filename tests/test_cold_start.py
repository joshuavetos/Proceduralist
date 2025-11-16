"""Cold-start integration test for Tessrax OS primitives."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from nacl.signing import SigningKey

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


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _rewrite_ledger_for_ed25519(
    ledger_path: Path, signing_key: SigningKey, key_id: str
) -> None:
    records: List[dict] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            entry = json.loads(raw)
            ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
            signed_body = {
                "event_type": entry["event_type"],
                "timestamp": ts,
                "payload": entry["payload"],
                "payload_hash": entry["payload_hash"],
                "audited_state_hash": entry["audited_state_hash"],
                "key_id": key_id,
            }
            signature = signing_key.sign(_canonical(signed_body).encode("utf-8")).signature.hex()
            entry.update({"timestamp": ts, "key_id": key_id, "signature": signature})
            records.append(entry)
    with ledger_path.open("w", encoding="utf-8") as handle:
        for entry in records:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _normalize_index_offsets(index_path: Path) -> None:
    if not index_path.exists():
        return
    with sqlite3.connect(index_path) as con:
        rows = con.execute(
            "SELECT rowid FROM ledger_index ORDER BY ledger_offset"
        ).fetchall()
        for idx, (rowid,) in enumerate(rows):
            con.execute("UPDATE ledger_index SET ledger_offset = ? WHERE rowid = ?", (idx, rowid))
        con.commit()


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

    core_memory.LEDGER_PATH = ledger_path
    core_memory.INDEX_PATH = index_path
    core_memory.SIGNING_KEY_PATH = hmac_key_path

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

    key_id = "test-key"
    signing_key = SigningKey.generate()
    pub_bytes = signing_key.verify_key.encode()
    (signing_keys_dir / f"{key_id}.pub").write_bytes(pub_bytes)
    legacy_pub_path.write_bytes(pub_bytes)
    _rewrite_ledger_for_ed25519(ledger_path, signing_key, key_id)
    _normalize_index_offsets(index_path)

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
