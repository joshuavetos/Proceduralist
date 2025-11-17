"""Operational queue status endpoints for monitoring crawl progress."""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter
from sqlalchemy import func

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal
from backend.queue import get_queue

router = APIRouter()


def _safe_queue_depth(queue: object) -> int:
    if hasattr(queue, "count"):
        try:
            count_val = getattr(queue, "count")
            if callable(count_val):
                return int(count_val())
            return int(count_val)
        except Exception:
            return 0
    if hasattr(queue, "__len__"):
        try:
            return int(len(queue))
        except Exception:
            return 0
    return 0


def _progress(status: str, nodes: int, edges: int) -> float:
    stage_progress = {
        "draft": 0.05,
        "queued": 0.15,
        "running": 0.55,
        "published": 1.0,
        "failed": 1.0,
        "archived": 1.0,
    }
    base = stage_progress.get(status, 0.0)
    momentum = min(0.35, (nodes + edges) * 0.01)
    return round(min(1.0, base + momentum), 3)


def _contradiction_count(session: SessionLocal, map_id: int) -> int:
    node_contradictions = (
        session.query(func.count(DBNode.id))
        .filter(DBNode.map_id == map_id)
        .filter((DBNode.is_contradiction.is_(True)) | (DBNode.contradiction_type.isnot(None)))
        .scalar()
        or 0
    )
    edge_contradictions = (
        session.query(func.count(DBEdge.id))
        .filter(DBEdge.map_id == map_id)
        .filter((DBEdge.is_contradiction.is_(True)) | (DBEdge.contradiction_type.isnot(None)))
        .scalar()
        or 0
    )
    return int(node_contradictions + edge_contradictions)


@router.get("/api/queue/status")
async def get_queue_status() -> Dict[str, object]:
    queue = get_queue()
    queue_depth = _safe_queue_depth(queue)
    session = SessionLocal()
    try:
        status_totals: Dict[str, int] = {}
        for status in ["draft", "queued", "running", "published", "archived", "failed"]:
            status_totals[status] = (
                session.query(func.count(DBMap.id)).filter(DBMap.status == status).scalar() or 0
            )

        recent_maps: List[Dict[str, object]] = []
        records = session.query(DBMap).order_by(DBMap.created_at.desc()).limit(12).all()
        for record in records:
            nodes = session.query(func.count(DBNode.id)).filter(DBNode.map_id == record.id).scalar() or 0
            edges = session.query(func.count(DBEdge.id)).filter(DBEdge.map_id == record.id).scalar() or 0
            contradictions = _contradiction_count(session, record.id)
            recent_maps.append(
                {
                    "id": record.id,
                    "title": record.title,
                    "status": record.status,
                    "nodes": int(nodes),
                    "edges": int(edges),
                    "contradictions": contradictions,
                    "progress": _progress(record.status, int(nodes), int(edges)),
                    "start_url": record.start_url,
                }
            )

        return {
            "queue_depth": queue_depth,
            "status_totals": status_totals,
            "recent_maps": recent_maps,
        }
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
