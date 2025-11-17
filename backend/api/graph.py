"""Graph retrieval API endpoints backed by the persistent database."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal

router = APIRouter()


def _serialize_node(node: DBNode) -> Dict[str, Any]:
    return {
        "id": node.id,
        "map_id": node.map_id,
        "url": node.url,
        "title": node.title,
        "is_contradiction": node.is_contradiction,
        "contradiction_type": node.contradiction_type,
        "metadata": node.metadata or {},
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


def _serialize_edge(edge: DBEdge) -> Dict[str, Any]:
    return {
        "id": edge.id,
        "map_id": edge.map_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "action_label": edge.action_label,
        "is_contradiction": edge.is_contradiction,
        "contradiction_type": edge.contradiction_type,
        "created_at": edge.created_at,
        "updated_at": edge.updated_at,
    }


@router.get("/api/graph/{map_id}")
async def get_graph(map_id: int) -> Dict[str, List[Dict[str, Any]]]:
    session: Session = SessionLocal()
    try:
        map_record = session.get(DBMap, map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")
        nodes = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        edges = session.query(DBEdge).filter(DBEdge.map_id == map_id).all()
        if not nodes and not edges:
            raise HTTPException(status_code=404, detail="Graph not ready")
        return {"nodes": [_serialize_node(node) for node in nodes], "edges": [_serialize_edge(edge) for edge in edges]}
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
