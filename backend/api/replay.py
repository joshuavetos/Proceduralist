"""Deterministic replay endpoint for stored graphs."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal

router = APIRouter()


class ReplayRequest(BaseModel):
    start_node: int
    max_steps: int


@router.post("/api/replay/{map_id}")
async def replay(map_id: int, request: ReplayRequest) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        map_record = session.get(DBMap, map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        current_node = session.get(DBNode, request.start_node)
        if current_node is None or current_node.map_id != map_id:
            raise HTTPException(status_code=404, detail="Start node not found for map")

        visited_nodes: List[int] = [current_node.id]
        visited_edges: List[int] = []
        visited_set = {current_node.id}
        loop_detected = False
        stopped_reason = ""

        if current_node.is_contradiction or current_node.contradiction_type:
            stopped_reason = "contradiction_node"
        else:
            for _ in range(request.max_steps):
                outgoing_edges = (
                    session.query(DBEdge)
                    .filter(DBEdge.map_id == map_id, DBEdge.from_node_id == current_node.id)
                    .order_by(DBEdge.action_label.asc(), DBEdge.to_node_id.asc())
                    .all()
                )
                if not outgoing_edges:
                    stopped_reason = "missing_edges"
                    break

                selected_edge = outgoing_edges[0]
                visited_edges.append(selected_edge.id)

                if selected_edge.is_contradiction or selected_edge.contradiction_type:
                    stopped_reason = "contradiction_edge"
                    break
                if selected_edge.to_node_id is None:
                    stopped_reason = "missing_edges"
                    break

                next_node = session.get(DBNode, selected_edge.to_node_id)
                if next_node is None:
                    stopped_reason = "missing_edges"
                    break

                if next_node.id in visited_set:
                    loop_detected = True
                    visited_nodes.append(next_node.id)
                    stopped_reason = "loop_detected"
                    current_node = next_node
                    break

                visited_nodes.append(next_node.id)
                visited_set.add(next_node.id)
                current_node = next_node
            else:
                stopped_reason = "max_steps"

        response: Dict[str, Any] = {
            "visited_nodes": visited_nodes,
            "visited_edges": visited_edges,
            "stopped_reason": stopped_reason,
            "loop_detected": loop_detected,
            "final_node": current_node.id,
        }
        return response
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
