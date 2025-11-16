from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tessrax.ledger.divergence import analyze_root_cause, scan_state_divergence
from tessrax.ledger.load_test import generate_high_volume_receipts
from tessrax.ledger.merkle import MerkleState
from tessrax.ledger.merkle_profiler import profile_replay
from tessrax.ledger.snapshots import export_snapshot, restore_snapshot
from tessrax.ledger.stress_harness import generate_stress_ledger


def _prepare_ledger_environment(tmp_path: Path, entries: int = 4) -> dict[str, Path]:
    ledger_path = tmp_path / "ledger.jsonl"
    generate_stress_ledger(output_path=ledger_path, entries=entries)
    merkle_state = MerkleState.empty()
    parsed_entries = []
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        parsed_entries.append(entry)
        merkle_state = merkle_state.apply_leaf(entry["entry_hash"])
    merkle_path = tmp_path / "merkle_state.json"
    payload = merkle_state.to_payload()
    payload.update(root=merkle_state.root())
    merkle_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path = tmp_path / "index.db"
    with sqlite3.connect(index_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_offset INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        for offset, entry in enumerate(parsed_entries):
            conn.execute(
                "INSERT INTO ledger_index (ledger_offset, event_type, state_hash, payload_hash, timestamp) VALUES (?, ?, ?, ?, ?)",
                (offset, entry["event_type"], entry["audited_state_hash"], entry["payload_hash"], entry["timestamp"]),
            )
        conn.commit()
    return {"ledger": ledger_path, "merkle": merkle_path, "index": index_path}


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    env = _prepare_ledger_environment(tmp_path)
    snapshot_path = tmp_path / "snapshot.json"
    snapshot = export_snapshot(snapshot_path=snapshot_path, ledger_path=env["ledger"], merkle_state_path=env["merkle"], index_path=env["index"])
    assert snapshot.metadata.entries > 0
    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    ledger_restore = restore_dir / "ledger.jsonl"
    merkle_restore = restore_dir / "merkle_state.json"
    index_restore = restore_dir / "index.db"
    restore_snapshot(
        snapshot_path=snapshot_path,
        ledger_path=ledger_restore,
        merkle_state_path=merkle_restore,
        index_path=index_restore,
    )
    assert ledger_restore.exists()
    assert merkle_restore.exists()


def test_divergence_scan_and_root_cause(tmp_path: Path) -> None:
    env = _prepare_ledger_environment(tmp_path)
    report = scan_state_divergence(ledger_path=env["ledger"], index_path=env["index"], merkle_state_path=env["merkle"])
    assert report.root_matches is True
    with sqlite3.connect(env["index"]) as conn:
        conn.execute("DELETE FROM ledger_index WHERE ledger_offset = 0")
        conn.commit()
    drift_report = scan_state_divergence(ledger_path=env["ledger"], index_path=env["index"], merkle_state_path=env["merkle"])
    root_cause = analyze_root_cause(drift_report)
    assert root_cause.classification == "INDEX_DRIFT"


def test_merkle_profile_and_load_test(tmp_path: Path) -> None:
    env = _prepare_ledger_environment(tmp_path)
    profile = profile_replay(ledger_path=env["ledger"], threshold_seconds=5.0)
    assert profile.guard_passed is True
    summary = generate_high_volume_receipts(output_path=tmp_path / "load.jsonl", batches=2, batch_size=6000)
    assert summary.total_entries == 12_000
    assert summary.output_path.exists()
