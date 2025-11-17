"""History retrieval endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from backend import auditor, clauses
from backend.models.db import DBMapHistory, SessionLocal

router = APIRouter()


@router.get("/api/history/{map_id}")
async def get_history(map_id: int) -> list[dict]:
    session = SessionLocal()
    try:
        records = (
            session.query(DBMapHistory)
            .filter(DBMapHistory.map_id == map_id)
            .order_by(DBMapHistory.timestamp.asc())
            .all()
        )
        return [
            {
                "timestamp": r.timestamp,
                "severity": r.severity,
                "entropy": r.entropy,
                "integrity": r.integrity,
                "contradictions": r.contradictions,
            }
            for r in records
        ]
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
