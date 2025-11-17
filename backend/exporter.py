"""Export utilities for serialized map data."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Dict, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBNode, SessionLocal


def _load_map_assets(map_id: int) -> Tuple[DBMap, List[DBNode], List[DBEdge]]:
    if map_id <= 0:
        raise ValueError("Map identifier must be positive")

    session = SessionLocal()
    try:
        map_record = session.get(DBMap, map_id)
        if map_record is None:
            raise ValueError("Map not found")
        nodes = (
            session.query(DBNode)
            .filter(DBNode.map_id == map_id)
            .order_by(DBNode.id.asc())
            .all()
        )
        edges = (
            session.query(DBEdge)
            .filter(DBEdge.map_id == map_id)
            .order_by(DBEdge.id.asc())
            .all()
        )
        return map_record, nodes, edges
    finally:
        session.close()


def export_map_json(map_id: int) -> bytes:
    map_record, nodes, edges = _load_map_assets(map_id)
    payload: Dict[str, Any] = {
        "map": {
            "id": map_record.id,
            "title": map_record.title,
            "start_url": map_record.start_url,
            "status": map_record.status,
            "severity_score": map_record.severity_score,
            "entropy_score": map_record.entropy_score,
            "integrity_score": map_record.integrity_score,
            "created_at": map_record.created_at,
            "updated_at": map_record.updated_at,
        },
        "nodes": [
            {
                "id": node.id,
                "map_id": node.map_id,
                "url": node.url,
                "title": node.title,
                "is_contradiction": node.is_contradiction,
                "contradiction_type": node.contradiction_type,
                "metadata": node.metadata,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
            }
            for node in nodes
        ],
        "edges": [
            {
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
            for edge in edges
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


def _draw_header(pdf: canvas.Canvas, title: str) -> float:
    _, height = letter
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, height - 64, title)
    pdf.setFont("Helvetica", 11)
    y_position = height - 88
    return y_position


def _maybe_new_page(pdf: canvas.Canvas, y_position: float) -> float:
    if y_position < 72:
        pdf.showPage()
        pdf.setFont("Helvetica", 11)
        return letter[1] - 64
    return y_position


def export_map_pdf(map_id: int) -> bytes:
    map_record, nodes, edges = _load_map_assets(map_id)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = _draw_header(pdf, f"Proceduralist Audit Export: {map_record.title}")

    pdf.drawString(72, y, f"Map ID: {map_record.id} | Status: {map_record.status}")
    y -= 16
    pdf.drawString(72, y, f"Start URL: {map_record.start_url}")
    y -= 16
    pdf.drawString(
        72,
        y,
        f"Severity: {map_record.severity_score or 0.0:.2f}  "
        f"Entropy: {map_record.entropy_score or 0.0:.2f}  "
        f"Integrity: {map_record.integrity_score or 0.0:.2f}",
    )
    y -= 24

    contradiction_entries: List[str] = []
    for node in nodes:
        if node.is_contradiction or node.contradiction_type:
            contradiction_entries.append(f"Node {node.id}: {node.contradiction_type or 'contradiction'}")
    for edge in edges:
        if edge.is_contradiction or edge.contradiction_type:
            contradiction_entries.append(f"Edge {edge.id}: {edge.contradiction_type or 'contradiction'}")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(72, y, "Summary")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.drawString(90, y, f"Nodes: {len(nodes)}  Edges: {len(edges)}  Contradictions: {len(contradiction_entries)}")
    y -= 20

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(72, y, "Contradictions")
    y -= 16
    pdf.setFont("Helvetica", 11)
    if contradiction_entries:
        for entry in contradiction_entries:
            y = _maybe_new_page(pdf, y)
            pdf.drawString(90, y, f"- {entry}")
            y -= 14
    else:
        pdf.drawString(90, y, "None detected")
        y -= 14

    pdf.setFont("Helvetica-Bold", 12)
    y = _maybe_new_page(pdf, y - 6)
    pdf.drawString(72, y, "Nodes")
    y -= 16
    pdf.setFont("Helvetica", 11)
    for node in nodes:
        y = _maybe_new_page(pdf, y)
        label = node.title or node.url
        suffix = f" [{node.contradiction_type}]" if node.contradiction_type else ""
        pdf.drawString(90, y, f"#{node.id} {label}{suffix}")
        y -= 14

    pdf.setFont("Helvetica-Bold", 12)
    y = _maybe_new_page(pdf, y - 6)
    pdf.drawString(72, y, "Edges")
    y -= 16
    pdf.setFont("Helvetica", 11)
    if edges:
        for edge in edges:
            y = _maybe_new_page(pdf, y)
            descriptor = f"#{edge.id}: {edge.from_node_id} -> {edge.to_node_id or 'terminal'}"
            suffix = f" [{edge.contradiction_type}]" if edge.contradiction_type else ""
            pdf.drawString(90, y, f"{descriptor}{suffix} ({edge.action_label})")
            y -= 14
    else:
        pdf.drawString(90, y, "No edges recorded")
        y -= 14

    pdf.save()
    return buffer.getvalue()


mock_metadata = {"auditor": auditor, "clauses": clauses}
