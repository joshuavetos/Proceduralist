"""Unified analysis endpoints for archived crawl artifacts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.analyzer.a11y import a11y_scan
from backend.analyzer.html_archive import archive_node_html
from backend.analyzer.link_checker import check_links
from backend.analyzer.perf import perf_scan
from backend.models.db import DBMap, SessionLocal

router = APIRouter()


@router.post("/api/analyze/archive/{node_id}")
async def archive(node_id: int) -> dict:
    try:
        html = archive_node_html(node_id)
        return {"bytes": len(html)}
    except Exception as exc:  # pragma: no cover - translate to HTTP errors
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/analyze/full/{map_id}")
async def analyze_map(map_id: int) -> dict:
    session = SessionLocal()
    try:
        if session.get(DBMap, map_id) is None:
            raise HTTPException(status_code=404, detail="Map not found")
    finally:
        session.close()

    return {
        "links": check_links(map_id),
        "a11y": a11y_scan(map_id),
        "perf": perf_scan(map_id),
    }
