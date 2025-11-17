"""Audit lifecycle API endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.exc import SQLAlchemyError

from auditor import crawler
from backend import auditor, clauses
from backend.models.db import DBEdge, DBNode, SessionLocal
from backend.models.map import MapRepository
from backend.queue import get_queue

router = APIRouter()

map_repository = MapRepository()


class AuditStartRequest(BaseModel):
    title: str
    start_url: HttpUrl


class AuditStartResponse(BaseModel):
    id: int
    status: str


def _persist_graph(map_id: int, graph: Mapping[str, List[Dict[str, object]]]) -> None:
    session = SessionLocal()
    try:
        # Clear any prior crawl results for determinism.
        session.query(DBEdge).filter(DBEdge.map_id == map_id).delete()
        session.query(DBNode).filter(DBNode.map_id == map_id).delete()
        session.commit()

        node_lookup: Dict[str, int] = {}
        for node in graph.get("nodes", []):
            url = str(node.get("url") or node.get("id") or "")
            assert url, "Node url must be present"
            db_node = DBNode(
                map_id=map_id,
                url=url,
                title=str(node.get("title") or ""),
                is_contradiction=bool(node.get("is_contradiction", False)),
                contradiction_type=node.get("contradiction_type"),
                metadata=node.get("metadata") or {"actions": node.get("actions", [])},
            )
            session.add(db_node)
            session.flush()
            assert db_node.id is not None, "Node id must be assigned"
            node_lookup[url] = db_node.id

        for edge in graph.get("edges", []):
            source_url = str(edge.get("source") or edge.get("from") or "")
            target_url = str(edge.get("target") or edge.get("to") or "")
            if not source_url:
                raise ValueError("Edge source must be present")
            from_node_id = node_lookup.get(source_url)
            if from_node_id is None:
                placeholder_node = DBNode(map_id=map_id, url=source_url, title=source_url)
                session.add(placeholder_node)
                session.flush()
                from_node_id = placeholder_node.id
                node_lookup[source_url] = from_node_id or 0
            to_node_id = node_lookup.get(target_url)
            if target_url and to_node_id is None:
                placeholder_target = DBNode(map_id=map_id, url=target_url, title=target_url)
                session.add(placeholder_target)
                session.flush()
                to_node_id = placeholder_target.id
                node_lookup[target_url] = to_node_id or 0
            db_edge = DBEdge(
                map_id=map_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                action_label=str(edge.get("action_label") or edge.get("label") or "navigate"),
                is_contradiction=bool(edge.get("is_contradiction", False)),
                contradiction_type=edge.get("contradiction_type"),
            )
            session.add(db_edge)
        session.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive runtime guard
        session.rollback()
        raise RuntimeError(f"Failed to persist graph for map {map_id}: {exc}") from exc
    finally:
        session.close()


async def run_audit_task(map_id: int, start_url: str) -> Dict[str, Any]:
    record = map_repository.get(map_id)
    if not record:
        raise HTTPException(status_code=404, detail="Map not found")
    map_repository.update_status(map_id, "running")
    graph = crawler.crawl(start_url)
    _persist_graph(map_id, graph)
    map_repository.update_status(map_id, "published")
    return {"id": map_id, "start_url": start_url, "status": "published"}


@router.post("/api/audit/start", response_model=AuditStartResponse)
async def start_audit(request: AuditStartRequest) -> AuditStartResponse:
    new_map = map_repository.create(title=request.title, start_url=str(request.start_url))
    map_repository.update_status(new_map.id or 0, "queued")
    queue = get_queue()
    job_result = queue.enqueue(run_audit_task, new_map.id, new_map.start_url)
    final_status = new_map.status
    if hasattr(job_result, "get_id"):
        final_status = map_repository.get(new_map.id or 0).status  # type: ignore[assignment]
    return AuditStartResponse(id=new_map.id or 0, status=final_status)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
