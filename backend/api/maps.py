"""Map listing endpoints for storefront usage."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal

router = APIRouter()


class CreateMapRequest(BaseModel):
    title: str = Field(..., min_length=1)
    start_url: str = Field(..., min_length=1)
    status: Optional[str] = Field(default="draft")
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


class UpdateMapRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    start_url: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


class AddNodeRequest(BaseModel):
    url: str = Field(..., min_length=1)
    title: str = Field(default="")
    is_contradiction: bool = False
    contradiction_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AddEdgeRequest(BaseModel):
    from_node_id: int
    to_node_id: Optional[int] = None
    action_label: str = Field(default="navigate", min_length=1)
    is_contradiction: bool = False
    contradiction_type: Optional[str] = None


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


@router.post("/api/maps/create")
async def create_map(payload: CreateMapRequest) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        allowed_status = {"draft", "published", "archived"}
        status = payload.status if payload.status is not None else "draft"
        if status not in allowed_status:
            raise HTTPException(status_code=400, detail="Invalid map status")

        record = DBMap(
            title=payload.title,
            start_url=payload.start_url,
            status=status,
            description=payload.description,
            tags=payload.tags,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _serialize_map(record)
    finally:
        session.close()


@router.post("/api/maps/{map_id}/add_node")
async def add_node(map_id: int, payload: AddNodeRequest) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        map_record = session.query(DBMap).filter(DBMap.id == map_id).first()
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        node = DBNode(
            map_id=map_id,
            url=payload.url,
            title=payload.title,
            is_contradiction=payload.is_contradiction,
            contradiction_type=payload.contradiction_type,
            metadata=payload.metadata,
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        return {
            "id": node.id,
            "map_id": node.map_id,
            "url": node.url,
            "title": node.title,
            "is_contradiction": node.is_contradiction,
            "contradiction_type": node.contradiction_type,
            "metadata": node.metadata,
        }
    finally:
        session.close()


@router.post("/api/maps/{map_id}/add_edge")
async def add_edge(map_id: int, payload: AddEdgeRequest) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        map_record = session.query(DBMap).filter(DBMap.id == map_id).first()
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        from_node = session.query(DBNode).filter(DBNode.id == payload.from_node_id, DBNode.map_id == map_id).first()
        if from_node is None:
            raise HTTPException(status_code=400, detail="from_node_id does not belong to map")

        if payload.to_node_id is not None:
            to_node = session.query(DBNode).filter(DBNode.id == payload.to_node_id, DBNode.map_id == map_id).first()
            if to_node is None:
                raise HTTPException(status_code=400, detail="to_node_id does not belong to map")

        edge = DBEdge(
            map_id=map_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            action_label=payload.action_label,
            is_contradiction=payload.is_contradiction,
            contradiction_type=payload.contradiction_type,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return {
            "id": edge.id,
            "map_id": edge.map_id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "action_label": edge.action_label,
            "is_contradiction": edge.is_contradiction,
            "contradiction_type": edge.contradiction_type,
        }
    finally:
        session.close()


@router.patch("/api/maps/{map_id}")
async def update_map(map_id: int, payload: UpdateMapRequest) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        record = session.query(DBMap).filter(DBMap.id == map_id).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        if payload.title is not None:
            record.title = payload.title
        if payload.start_url is not None:
            record.start_url = payload.start_url
        if payload.description is not None:
            record.description = payload.description
        if payload.tags is not None:
            record.tags = payload.tags

        session.commit()
        session.refresh(record)
        return _serialize_map(record)
    finally:
        session.close()


@router.patch("/api/maps/{map_id}/status")
async def update_map_status(map_id: int, status: str) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        allowed_status = {"draft", "published", "archived"}
        if status not in allowed_status:
            raise HTTPException(status_code=400, detail="Invalid map status")

        record = session.query(DBMap).filter(DBMap.id == map_id).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        record.status = status
        session.commit()
        session.refresh(record)
        return _serialize_map(record)
    finally:
        session.close()


@router.delete("/api/maps/{map_id}")
async def delete_map(map_id: int) -> Dict[str, str]:
    session: Session = SessionLocal()
    try:
        record = session.query(DBMap).filter(DBMap.id == map_id).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Map not found")

        session.delete(record)
        session.commit()
        return {"detail": "Map deleted"}
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
