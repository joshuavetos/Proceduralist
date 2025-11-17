"""Graph retrieval API endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend import auditor, clauses
from backend.api.audit import map_store

router = APIRouter()


@router.get("/api/graph/{map_id}")
async def get_graph(map_id: int) -> Dict[str, Any]:
    record = map_store.get(map_id)
    if not record:
        raise HTTPException(status_code=404, detail="Map not found")
    if record.temp_graph is None:
        raise HTTPException(status_code=404, detail="Graph not ready")
    return record.temp_graph


auditor_metadata = {"auditor": auditor, "clauses": clauses}
