"""Audit lifecycle API endpoints."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from backend import auditor, clauses
from backend.models.map import MapStore
from backend.queue import get_queue
from backend.seed import build_seed_graph

router = APIRouter()

map_store = MapStore()


class AuditStartRequest(BaseModel):
    title: str
    start_url: HttpUrl


class AuditStartResponse(BaseModel):
    id: int
    status: str


async def run_audit_task(map_id: int, start_url: str) -> Dict[str, Any]:
    record = map_store.get(map_id)
    if not record:
        raise HTTPException(status_code=404, detail="Map not found")
    map_store.update_status(map_id, "running")
    # placeholder deterministic audit run
    map_store.update_status(map_id, "published")
    return {"id": map_id, "start_url": start_url, "status": "published"}


@router.post("/api/audit/start", response_model=AuditStartResponse)
async def start_audit(request: AuditStartRequest) -> AuditStartResponse:
    new_map = map_store.create(title=request.title, start_url=str(request.start_url))
    map_store.update_status(new_map.id or 0, "queued")
    queue = get_queue()
    job_result = queue.enqueue(run_audit_task, new_map.id, new_map.start_url)
    final_status = new_map.status
    if hasattr(job_result, "get_id"):
        final_status = map_store.get(new_map.id or 0).status  # type: ignore[assignment]
    return AuditStartResponse(id=new_map.id or 0, status=final_status)


@router.get("/api/graph/{map_id}")
async def get_graph(map_id: int) -> Dict[str, Any]:
    record = map_store.get(map_id)
    if not record:
        raise HTTPException(status_code=404, detail="Map not found")
    graph = build_seed_graph()
    payload = asdict(graph)
    return payload


auditor_metadata = {"auditor": auditor, "clauses": clauses}
