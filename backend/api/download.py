"""Download endpoints for map exports."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from backend import auditor, clauses
from backend.exporter import export_map_json, export_map_pdf

router = APIRouter()


@router.get("/api/store/download/{map_id}")
async def download_map(map_id: int, format: str = Query(..., pattern="^(json|pdf)$")) -> Response:
    if format == "json":
        try:
            payload = export_map_json(map_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="map-{map_id}.json"'},
        )

    if format == "pdf":
        try:
            payload = export_map_pdf(map_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=payload,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="map-{map_id}.pdf"'},
        )

    raise HTTPException(status_code=400, detail="Unsupported export format")


auditor_metadata = {"auditor": auditor, "clauses": clauses}
