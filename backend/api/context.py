"""Context retrieval endpoints for nodes within a stored graph."""
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


def _serialize_edge(edge: DBEdge, target_node: DBNode | None) -> Dict[str, Any]:
    return {
        "id": edge.id,
        "map_id": edge.map_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "action_label": edge.action_label,
        "is_contradiction": edge.is_contradiction,
        "contradiction_type": edge.contradiction_type,
        "target_url": target_node.url if target_node else None,
        "created_at": edge.created_at,
        "updated_at": edge.updated_at,
    }


@router.get("/api/context/{map_id}/{node_id}")
async def get_context(map_id: int, node_id: int) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        map_record = session.get(DBMap, map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")
        current_node = (
            session.query(DBNode).filter(DBNode.map_id == map_id, DBNode.id == node_id).first()
        )
        if current_node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        edges = (
            session.query(DBEdge)
            .filter(DBEdge.map_id == map_id, DBEdge.from_node_id == node_id)
            .all()
        )
        target_nodes: Dict[int, DBNode] = {}
        for edge in edges:
            if edge.to_node_id:
                target_node = session.get(DBNode, edge.to_node_id)
                if target_node:
                    target_nodes[edge.id] = target_node

        actions: List[Dict[str, Any]] = []
        contradictions: List[Dict[str, Any]] = []
        next_states: List[Dict[str, Any]] = []

        if current_node.is_contradiction or current_node.contradiction_type:
            contradictions.append(
                {
                    "source": "node",
                    "node_id": current_node.id,
                    "contradiction_type": current_node.contradiction_type,
                }
            )

        for edge in edges:
            target_node = target_nodes.get(edge.id)
            edge_payload = _serialize_edge(edge, target_node)
            next_states.append(edge_payload)
            actions.append(
                {
                    "action_label": edge.action_label,
                    "to_node_id": edge.to_node_id,
                    "is_contradiction": edge.is_contradiction,
                    "contradiction_type": edge.contradiction_type,
                    "target_url": target_node.url if target_node else None,
                }
            )
            if edge.is_contradiction or edge.contradiction_type:
                contradictions.append(
                    {
                        "source": "edge",
                        "edge_id": edge.id,
                        "from_node_id": edge.from_node_id,
                        "to_node_id": edge.to_node_id,
                        "contradiction_type": edge.contradiction_type,
                    }
                )

        return {
            "current_node": _serialize_node(current_node),
            "actions": actions,
            "contradictions": contradictions,
            "last_audited_timestamp": current_node.updated_at,
            "next_states": next_states,
        }
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
