"""Map listing endpoints for storefront usage."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from backend import auditor, clauses
from backend.models.db import DBMap, SessionLocal

router = APIRouter()


def _serialize_map(record: DBMap) -> Dict[str, Any]:
    return {
        "id": record.id,
        "title": record.title,
        "start_url": record.start_url,
        "status": record.status,
        "severity_score": record.severity_score,
        "entropy_score": record.entropy_score,
        "integrity_score": record.integrity_score,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.get("/api/maps")
async def list_maps(status: str | None = None) -> List[Dict[str, Any]]:
    session: Session = SessionLocal()
    try:
        allowed_status = {"draft", "published", "archived"}
        target_status = "published" if status is None else status
        if target_status not in allowed_status:
            raise HTTPException(status_code=400, detail="Invalid map status filter")

        query = session.query(DBMap).filter(DBMap.status == target_status)
        records = query.order_by(DBMap.id.asc()).all()
        return [_serialize_map(record) for record in records]
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
