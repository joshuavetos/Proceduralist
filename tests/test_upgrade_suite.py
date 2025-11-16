"""Integration tests covering the Proceduralist upgrade suite."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tessrax.core.memory_engine as core_memory
import tessrax.infra.key_registry as key_registry
import tessrax.ledger.verify_ledger as ledger_module
from tessrax.core.typecheck import run_frozen_payload_typecheck
from tessrax.diagnostics.auto_diag import auto_diagnose
from tessrax.docs.diagram_generator import generate_diagram
from tessrax.governance.policy_registry import PolicyRegistry
from tessrax.governance.token_guard import GovernanceTokenError, GovernanceTokenGuard
from tessrax.ledger.auto_repair import auto_repair, rebuild_index_from_ledger
from tessrax.ledger.compaction import LedgerCompactor, LedgerShardPlanner
from tessrax.ledger.epochal import EpochLedgerManager
from tessrax.ledger.index_backend import IndexEntry, LedgerIndexBackend
from tessrax.ledger.merkle import MerkleAccumulator
from tessrax.ledger.parallel_replay import parallel_replay_root
from tessrax.ledger.receipt_diff import semantic_diff
from tessrax.ledger.stress_harness import generate_stress_ledger
from tessrax.ledger.svg_exporter import export_merkle_svg
from tessrax.governance.explorer import explore
from tessrax.core.memory_engine import write_receipt


def _configure_environment(tmp_path: Path) -> dict:
    sandbox = tmp_path / "tessrax_suite"
    ledger_dir = sandbox / "tessrax" / "ledger"
    ledger_dir.mkdir(parents=True)
    infra_dir = sandbox / "tessrax" / "infra"
    signing_keys_dir = infra_dir / "signing_keys"
    signing_keys_dir.mkdir(parents=True)

    ledger_path = ledger_dir / "ledger.jsonl"
    index_path = ledger_dir / "index.db"
    merkle_path = ledger_dir / "merkle_state.json"
    legacy_priv = infra_dir / "signing_key.pem"
    legacy_pub = infra_dir / "signing_key.pub"

    os.environ["TESSRAX_KEY_ID"] = "suite-key"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "suite-token"

    key_registry.SIGNING_KEYS_DIR = signing_keys_dir
    key_registry.ACTIVE_KEY_PATH = signing_keys_dir / "active_key.json"
    key_registry.ROTATION_STATE_PATH = signing_keys_dir / "rotation_state.json"
    key_registry.ROTATION_RECEIPTS_PATH = signing_keys_dir / "rotation_receipts.json"
    key_registry.LEGACY_PRIVATE_KEY_PATH = legacy_priv
    key_registry.LEGACY_PUBLIC_KEY_PATH = legacy_pub

    core_memory.LEDGER_PATH = ledger_path
    core_memory.INDEX_PATH = index_path
    core_memory.MERKLE_STATE_PATH = merkle_path

    ledger_module.LEDGER_PATH = ledger_path
    ledger_module.INDEX_PATH = index_path
    ledger_module.MERKLE_STATE_PATH = merkle_path
    ledger_module.SIGNING_KEYS_DIR = signing_keys_dir
    ledger_module.LEGACY_KEY_PATH = legacy_pub

    return {
        "ledger_path": ledger_path,
        "index_path": index_path,
        "merkle_path": merkle_path,
        "signing_keys": signing_keys_dir,
        "legacy_pub": legacy_pub,
    }


def _write_sample_receipts(count: int = 3) -> list:
    receipts = []
    for idx in range(count):
        payload = {"node_id": idx, "status": "VERIFIED", "url": f"https://example/{idx}"}
        receipts.append(
            write_receipt(
                event_type="STATE_AUDITED",
                payload=payload,
                audited_state_hash=f"{idx:064x}",
            )
        )
    return receipts


def test_epoch_snapshots_and_auto_tools(tmp_path: Path) -> None:
    env = _configure_environment(tmp_path)
    receipts = _write_sample_receipts(3)
    ledger_path = env["ledger_path"]
    merkle_path = env["merkle_path"]
    index_path = env["index_path"]

    entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    assert len(entries) == len(receipts)
    assert all("epoch_id" in entry for entry in entries)
    assert len({entry["governance_freshness_tag"] for entry in entries}) == len(entries)

    snapshots = list(merkle_path.parent.glob("merkle_state-EPOCH-*.json"))
    assert len(snapshots) == len(receipts)
    manager = EpochLedgerManager(state_path=merkle_path.with_name("epoch_state.json"), snapshot_dir=merkle_path.parent)
    for receipt in receipts:
        assert manager.get_epoch(receipt.entry_hash) == receipt.epoch_id

    observed_root = parallel_replay_root(ledger_path=ledger_path)
    persisted_root = MerkleAccumulator(state_path=merkle_path).state.root()
    assert observed_root == persisted_root

    merkle_path.write_text("{}", encoding="utf-8")
    repair_report = auto_repair(
        ledger_path=ledger_path,
        merkle_state_path=merkle_path,
        index_path=index_path,
    )
    assert repair_report["entries_replayed"] == len(entries)

    compactor = LedgerCompactor(ledger_path=ledger_path, merkle_state_path=merkle_path)
    report = compactor.compact(retain=2, output_path=ledger_path.with_name("compact.jsonl"))
    assert report.retained_entries == 2
    assert report.dropped_entries == len(entries) - 2

    shards = LedgerShardPlanner(ledger_path=ledger_path).shard(max_entries=1, output_dir=ledger_path.parent / "shards")
    assert len(shards) == len(entries)

    svg_path = export_merkle_svg(MerkleAccumulator(state_path=merkle_path).state, ledger_path.parent / "state.svg")
    assert svg_path.exists()

    diag = auto_diagnose(
        ledger_path=ledger_path,
        merkle_state_path=merkle_path,
        index_path=index_path,
        report_path=tmp_path / "diag.json",
    )
    assert diag["diagnosed"] is True

    diagram_path = generate_diagram(tmp_path / "arch.svg")
    assert diagram_path.exists()

    diff = semantic_diff(entries[0], entries[1])
    assert any(field == "payload" for field, *_ in diff)

    summary = explore(ledger_path)
    assert summary.total_entries == len(entries)

    stress = generate_stress_ledger(output_path=tmp_path / "stress.jsonl", entries=25)
    assert stress.entries == 25

    rebuilt = rebuild_index_from_ledger(ledger_path=ledger_path, index_path=index_path)
    assert rebuilt == len(entries)

    conn = sqlite3.connect(index_path)
    count = conn.execute("SELECT COUNT(*) FROM ledger_index").fetchone()[0]
    conn.close()
    assert count == len(entries)


def test_policy_registry_and_typecheck(tmp_path: Path) -> None:
    registry = PolicyRegistry(path=tmp_path / "policy_state.json")
    snap1 = registry.pin("v2.0", reason="upgrade", approver="council")
    snap2 = registry.pin("v2.1", reason="hotfix", approver="council")
    assert snap2.version == "v2.1"
    rolled_back = registry.rollback(reason="stability")
    assert rolled_back.version == snap1.version
    state = json.loads((tmp_path / "policy_state.json").read_text())
    assert state["rollbacks"]
    assert run_frozen_payload_typecheck() is True


def test_multisig_rotation_and_token_guard(tmp_path: Path) -> None:
    env = _configure_environment(tmp_path)
    guard_path = env["merkle_path"].with_name("token_guard.json")
    guard = GovernanceTokenGuard(state_path=guard_path, window_seconds=3600)
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "alpha"
    guard.validate(ledger_counter=0)
    with pytest.raises(GovernanceTokenError):
        guard.validate(ledger_counter=0)

    os.environ["TESSRAX_REQUIRED_APPROVERS"] = "alpha,beta"
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "alpha,beta"
    key_registry.load_active_signing_key()
    key_registry.rotate_key(reason="test rotation", governance_token="alpha,beta", force=True)
    rotation_state = key_registry.rotation_status()
    active_key = rotation_state["active_key"]
    approvals = rotation_state["keys"][active_key]["governance_approval"]["approvals"]
    assert set(approvals) == {"alpha", "beta"}
    receipts_path = key_registry.ROTATION_RECEIPTS_PATH
    assert receipts_path.exists()
    receipts = json.loads(receipts_path.read_text() or "[]")
    assert receipts and "signed_by_new" in receipts[-1]
    os.environ.pop("TESSRAX_REQUIRED_APPROVERS", None)
    os.environ["TESSRAX_GOVERNANCE_TOKEN"] = "suite-token"


def test_cli_diff_and_rocks_backend(tmp_path: Path) -> None:
    env = _configure_environment(tmp_path)
    _write_sample_receipts(2)
    ledger_path = env["ledger_path"]
    entries = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]

    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps(entries[0]), encoding="utf-8")
    modified = dict(entries[0])
    modified["payload_hash"] = "z" * 64
    right.write_text(json.dumps(modified), encoding="utf-8")
    proc = subprocess.run(
        ["python", "-m", "tessrax.cli.tessraxctl", "diff-receipts", str(left), str(right)],
        capture_output=True,
        check=True,
        text=True,
    )
    assert "payload_hash" in proc.stdout

    rocks_backend = LedgerIndexBackend(
        index_path=tmp_path / "rocks.db",
        backend="rocksdb",
        rocks_path=tmp_path / "rocks.json",
    )
    entry = IndexEntry(
        ledger_offset=1,
        event_type="STATE_AUDITED",
        state_hash="a" * 64,
        payload_hash="b" * 64,
        timestamp="2024-01-01T00:00:00Z",
        merkle_root="c" * 64,
        entry_hash="d" * 64,
        previous_entry_hash=None,
    )
    rocks_backend.append(entry)
    rocks_data = (tmp_path / "rocks.json").read_text().splitlines()
    assert rocks_data and "\"entry_hash\"" in rocks_data[-1]
