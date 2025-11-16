"""Index backend abstraction with write-ahead logging and feature-flagged storage."""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from tessrax.core.errors import LedgerRepairError
from tessrax.core.time import canonical_datetime

LEDGER_INDEX_PATH = Path("tessrax/ledger/index.db")
WAL_PATH = LEDGER_INDEX_PATH.with_suffix(".wal.jsonl")
ROCKS_EMULATION_PATH = Path("tessrax/ledger/rocksdb_index.json")


@dataclass(slots=True)
class IndexEntry:
    ledger_offset: int
    event_type: str
    state_hash: str
    payload_hash: str
    timestamp: str
    merkle_root: str
    entry_hash: str
    previous_entry_hash: str | None


class IndexWriteAheadLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or WAL_PATH

    def append(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")

    def drain(self) -> list[dict]:
        if not self.path.exists():
            return []
        entries = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.path.write_text("", encoding="utf-8")
        return entries


class JsonKeyValueIndex:
    """Simple RocksDB emulation storing entries as JSON for deterministic tests."""

    def __init__(self, path: Path = ROCKS_EMULATION_PATH) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8")
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def _save(self, entries: Iterable[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def append(self, entry: Mapping[str, object]) -> None:
        entries = self._load()
        entries.append(dict(entry))
        self._save(entries)

    def rebuild(self, entries: Iterable[Mapping[str, object]]) -> None:
        self._save(entries)


class LedgerIndexBackend:
    def __init__(
        self,
        *,
        index_path: Path = LEDGER_INDEX_PATH,
        backend: str | None = None,
        rocks_path: Path | None = None,
    ) -> None:
        self.index_path = index_path
        self.backend = (backend or os.getenv("TESSRAX_INDEX_BACKEND", "sqlite")).lower()
        self.wal = IndexWriteAheadLog(index_path.with_suffix(".wal.jsonl"))
        self.rocks_path = rocks_path or ROCKS_EMULATION_PATH
        if self.backend not in {"sqlite", "rocksdb"}:
            raise LedgerRepairError("Unknown index backend", details={"backend": self.backend})

    def ensure_schema(self) -> None:
        if self.backend == "rocksdb":
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.index_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ledger_offset INTEGER NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    merkle_root TEXT,
                    entry_hash TEXT,
                    previous_entry_hash TEXT
                );
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_state_hash ON ledger_index(state_hash);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ledger_index(timestamp);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_entry_hash ON ledger_index(entry_hash);")
            con.commit()

    @staticmethod
    def _entry_to_payload(entry: IndexEntry) -> dict:
        return {
            "ledger_offset": entry.ledger_offset,
            "event_type": entry.event_type,
            "state_hash": entry.state_hash,
            "payload_hash": entry.payload_hash,
            "timestamp": entry.timestamp,
            "merkle_root": entry.merkle_root,
            "entry_hash": entry.entry_hash,
            "previous_entry_hash": entry.previous_entry_hash,
        }

    def _insert_sqlite(self, entry: IndexEntry) -> None:
        with sqlite3.connect(self.index_path) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO ledger_index (
                    ledger_offset, event_type, state_hash, payload_hash,
                    timestamp, merkle_root, entry_hash, previous_entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.ledger_offset,
                    entry.event_type,
                    entry.state_hash,
                    entry.payload_hash,
                    entry.timestamp,
                    entry.merkle_root,
                    entry.entry_hash,
                    entry.previous_entry_hash,
                ),
            )
            con.commit()

    def append(self, entry: IndexEntry) -> None:
        payload = self._entry_to_payload(entry) | {"written_at": canonical_datetime()}
        self.wal.append(payload)
        if self.backend == "sqlite":
            self._insert_sqlite(entry)
        else:
            JsonKeyValueIndex(self.rocks_path).append(payload)
        self.wal.drain()

    def rebuild(self, entries: Iterable[IndexEntry]) -> None:
        if self.backend == "sqlite":
            if self.index_path.exists():
                self.index_path.unlink()
            self.ensure_schema()
            for entry in entries:
                self._insert_sqlite(entry)
        else:
            JsonKeyValueIndex(self.rocks_path).rebuild(
                self._entry_to_payload(entry) for entry in entries
            )
        self.wal.drain()


__all__ = [
    "IndexEntry",
    "IndexWriteAheadLog",
    "JsonKeyValueIndex",
    "LedgerIndexBackend",
]
