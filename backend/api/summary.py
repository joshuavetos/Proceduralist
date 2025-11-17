"""Map summary endpoint providing structural and score overview."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal

router = APIRouter()


def _count_contradictions(nodes: list[DBNode], edges: list[DBEdge]) -> int:
    contradictions = 0
    for node in nodes:
        if node.is_contradiction or node.contradiction_type:
            assert node.contradiction_type, "Contradiction node missing contradiction_type"
            contradictions += 1
    for edge in edges:
        if edge.is_contradiction or edge.contradiction_type:
            assert edge.contradiction_type, "Contradiction edge missing contradiction_type"
            contradictions += 1
    return contradictions


@router.get("/api/summary/{map_id}")
async def get_summary(map_id: int) -> dict:
    if map_id <= 0:
        raise HTTPException(status_code=400, detail="Map id must be positive")

    session = SessionLocal()
    try:
        record = session.get(DBMap, map_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        nodes = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        edges = session.query(DBEdge).filter(DBEdge.map_id == map_id).all()

        contradictions = _count_contradictions(nodes, edges)

        return {
            "map_id": record.id,
            "title": record.title,
            "start_url": record.start_url,
            "status": record.status,
            "nodes": len(nodes),
            "edges": len(edges),
            "contradictions": contradictions,
            "severity_score": record.severity_score,
            "entropy_score": record.entropy_score,
            "integrity_score": record.integrity_score,
        }
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
