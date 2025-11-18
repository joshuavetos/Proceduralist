"""Ledger snapshot export and restore utilities."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tessrax.core.errors import DiagnosticError

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
INDEX_PATH = Path("tessrax/ledger/index.db")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")


@dataclass(frozen=True)
class SnapshotMetadata:
    entries: int
    created_at: str
    auditor: str


@dataclass(frozen=True)
class LedgerSnapshot:
    metadata: SnapshotMetadata
    ledger_lines: list[str]
    merkle_state: dict[str, Any]
    index_dump: str


AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


def _read_ledger(ledger_path: Path) -> list[str]:
    if not ledger_path.exists():
        return []
    return [line.rstrip("\n") for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_merkle_state(merkle_state_path: Path) -> dict[str, Any]:
    if not merkle_state_path.exists():
        return {}
    raw = merkle_state_path.read_text(encoding="utf-8")
    return json.loads(raw or "{}")


def _dump_index(index_path: Path) -> str:
    if not index_path.exists():
        return ""
    with sqlite3.connect(index_path) as conn:
        return "\n".join(conn.iterdump())


def export_snapshot(
    *,
    snapshot_path: Path,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    index_path: Path = INDEX_PATH,
) -> LedgerSnapshot:
    ledger_file = Path(ledger_path)
    merkle_file = Path(merkle_state_path)
    index_file = Path(index_path)
    lines = _read_ledger(ledger_file)
    metadata = SnapshotMetadata(
        entries=len(lines),
        created_at=datetime.now(timezone.utc).isoformat(),
        auditor=AUDITOR_IDENTITY,
    )
    snapshot = LedgerSnapshot(
        metadata=metadata,
        ledger_lines=lines,
        merkle_state=_read_merkle_state(merkle_file),
        index_dump=_dump_index(index_file),
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, default=lambda o: o.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def restore_snapshot(
    *,
    snapshot_path: Path,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    index_path: Path = INDEX_PATH,
) -> SnapshotMetadata:
    if not snapshot_path.exists():
        raise DiagnosticError(f"Snapshot missing at {snapshot_path}")
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    metadata_payload = payload["metadata"]
    metadata = SnapshotMetadata(**metadata_payload)
    ledger_lines = payload.get("ledger_lines", [])
    merkle_state = payload.get("merkle_state", {})
    ledger_file = Path(ledger_path)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text("\n".join(ledger_lines) + ("\n" if ledger_lines else ""), encoding="utf-8")
    merkle_file = Path(merkle_state_path)
    merkle_file.parent.mkdir(parents=True, exist_ok=True)
    merkle_file.write_text(json.dumps(merkle_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_file = Path(index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    dump = payload.get("index_dump", "")
    with sqlite3.connect(index_file) as conn:
        conn.executescript("DROP TABLE IF EXISTS ledger_index;")
        if dump.strip():
            conn.executescript(dump)
        conn.commit()
    return metadata


def import_ledger_entries(snapshot_path: Path) -> list[dict[str, Any]]:
    """Load ledger entries from a JSON snapshot file.

    The snapshot must follow the structure produced by :func:`export_snapshot`.
    Each entry in ``ledger_lines`` is parsed as JSON; malformed content raises
    a ``DiagnosticError`` to avoid silently ignoring corrupted data.
    """

    if not snapshot_path.exists():
        raise DiagnosticError(f"Snapshot missing at {snapshot_path}")

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ledger_lines = payload.get("ledger_lines")

    if ledger_lines is None:
        raise DiagnosticError(f"Snapshot at {snapshot_path} is missing 'ledger_lines'")

    entries: list[dict[str, Any]] = []
    for idx, raw_line in enumerate(ledger_lines):
        line = str(raw_line).strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DiagnosticError(
                f"Invalid JSON in ledger_lines[{idx}] for snapshot {snapshot_path}"
            ) from exc

        if not isinstance(entry, dict):
            raise DiagnosticError(
                f"Ledger entry at ledger_lines[{idx}] in {snapshot_path} is not an object"
            )

        entries.append(entry)

    return entries


__all__ = [
    "LedgerSnapshot",
    "SnapshotMetadata",
    "export_snapshot",
    "restore_snapshot",
    "import_ledger_entries",
]
