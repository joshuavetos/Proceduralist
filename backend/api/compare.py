"""Map comparison endpoint for contradictions and structure."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal

router = APIRouter()


class CompareRequest(BaseModel):
    map_a: int
    map_b: int


@router.post("/api/compare")
async def compare_maps(req: CompareRequest) -> dict:
    if req.map_a <= 0 or req.map_b <= 0:
        raise HTTPException(status_code=400, detail="Map ids must be positive")

    session = SessionLocal()
    try:
        map_a = session.get(DBMap, req.map_a)
        map_b = session.get(DBMap, req.map_b)
        if map_a is None or map_b is None:
            raise HTTPException(status_code=404, detail="One or both maps not found")

        nodes_a = session.query(DBNode).filter(DBNode.map_id == req.map_a).all()
        nodes_b = session.query(DBNode).filter(DBNode.map_id == req.map_b).all()
        edges_a = session.query(DBEdge).filter(DBEdge.map_id == req.map_a).all()
        edges_b = session.query(DBEdge).filter(DBEdge.map_id == req.map_b).all()

        def contradictions(nodes: list[DBNode], edges: list[DBEdge]) -> set[tuple[str, int, str | None]]:
            contradictions_set: set[tuple[str, int, str | None]] = set()
            for node in nodes:
                if node.is_contradiction or node.contradiction_type:
                    assert node.contradiction_type, "Contradiction node missing contradiction_type"
                    contradictions_set.add(("node", node.id, node.contradiction_type))
            for edge in edges:
                if edge.is_contradiction or edge.contradiction_type:
                    assert edge.contradiction_type, "Contradiction edge missing contradiction_type"
                    contradictions_set.add(("edge", edge.id, edge.contradiction_type))
            return contradictions_set

        contradictions_a = contradictions(nodes_a, edges_a)
        contradictions_b = contradictions(nodes_b, edges_b)

        return {
            "new_contradictions": list(contradictions_b - contradictions_a),
            "resolved_contradictions": list(contradictions_a - contradictions_b),
            "score_delta": {
                "severity": (map_b.severity_score or 0.0) - (map_a.severity_score or 0.0),
                "entropy": (map_b.entropy_score or 0.0) - (map_a.entropy_score or 0.0),
                "integrity": (map_b.integrity_score or 0.0) - (map_a.integrity_score or 0.0),
            },
            "node_delta": len(nodes_b) - len(nodes_a),
            "edge_delta": len(edges_b) - len(edges_a),
        }
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
