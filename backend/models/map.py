"""Map data model and in-memory store.

This module follows the governance clauses for determinism and includes
assertions to prevent silent failures when creating or updating Map
records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

from backend import auditor, clauses


@dataclass
class Map:
    """Represents an audit map with minimal lifecycle fields."""

    title: str
    start_url: str
    status: str = "draft"
    id: Optional[int] = field(default=None)

    def __post_init__(self) -> None:
        assert self.title, "Map.title must be non-empty"
        assert self.start_url, "Map.start_url must be non-empty"
        assert self.status in {"draft", "queued", "running", "published", "failed"}, (
            "Map.status must be a valid lifecycle state"
        )


class MapStore:
    """Thread-safe in-memory repository for ``Map`` instances."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._data: Dict[int, Map] = {}
        self._next_id = 1

    def create(self, title: str, start_url: str) -> Map:
        with self._lock:
            new_map = Map(title=title, start_url=start_url, status="draft", id=self._next_id)
            self._data[self._next_id] = new_map
            self._next_id += 1
        return new_map

    def update_status(self, map_id: int, status: str) -> Map:
        assert status in {"draft", "queued", "running", "published", "failed"}, (
            "Map.status must be a valid lifecycle state"
        )
        with self._lock:
            if map_id not in self._data:
                raise KeyError(f"Map {map_id} not found")
            record = self._data[map_id]
            record.status = status
            self._data[map_id] = record
            return record

    def get(self, map_id: int) -> Optional[Map]:
        with self._lock:
            return self._data.get(map_id)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
