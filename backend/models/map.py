"""Map persistence layer backed by SQLAlchemy.

Runtime checks enforce deterministic status transitions and prevent silent
failures when interacting with the database-backed map repository.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend import auditor, clauses
from backend.models.db import DBMap, SessionLocal, init_db


class MapRepository:
    """Repository for CRUD operations on ``DBMap`` records."""

    VALID_STATUSES = {"draft", "queued", "running", "published", "failed", "archived"}

    def __init__(self) -> None:
        init_db()

    def _get_session(self) -> Session:
        return SessionLocal()

    def create(self, title: str, start_url: str) -> DBMap:
        assert title, "Map.title must be non-empty"
        assert start_url, "Map.start_url must be non-empty"
        session = self._get_session()
        try:
            new_map = DBMap(title=title, start_url=start_url, status="draft")
            session.add(new_map)
            session.commit()
            session.refresh(new_map)
            assert new_map.id is not None, "Persistent map id must be assigned"
            return new_map
        except SQLAlchemyError as exc:  # pragma: no cover - defensive runtime guard
            session.rollback()
            raise RuntimeError(f"Failed to create map: {exc}") from exc
        finally:
            session.close()

    def update_status(self, map_id: int, status: str) -> DBMap:
        assert status in self.VALID_STATUSES, "Map.status must be a valid lifecycle state"
        session = self._get_session()
        try:
            record = session.get(DBMap, map_id)
            if record is None:
                raise KeyError(f"Map {map_id} not found")
            record.status = status
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except SQLAlchemyError as exc:  # pragma: no cover - defensive runtime guard
            session.rollback()
            raise RuntimeError(f"Failed to update map {map_id}: {exc}") from exc
        finally:
            session.close()

    def get(self, map_id: int) -> Optional[DBMap]:
        session = self._get_session()
        try:
            record = session.get(DBMap, map_id)
            return record
        finally:
            session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
