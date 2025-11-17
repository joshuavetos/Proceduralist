"""Score computation API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import auditor, clauses
from backend.governance import compute_entropy, compute_integrity, compute_severity
from backend.models.db import DBMap, SessionLocal

router = APIRouter()


@router.post("/api/score/{map_id}")
async def compute_scores(map_id: int) -> dict[str, float]:
    session = SessionLocal()
    try:
        map_record = session.get(DBMap, map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")
    finally:
        session.close()

    severity = compute_severity(map_id)
    entropy = compute_entropy(map_id)
    integrity = compute_integrity(map_id)
    return {"severity": severity, "entropy": entropy, "integrity": integrity}


auditor_metadata = {"auditor": auditor, "clauses": clauses}
