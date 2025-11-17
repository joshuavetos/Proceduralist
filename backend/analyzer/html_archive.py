"""Fetch and archive HTML for a given node URL."""
from __future__ import annotations

import requests
from sqlalchemy.exc import SQLAlchemyError

from backend.models.db import DBNode, SessionLocal


def archive_node_html(node_id: int) -> bytes:
    """Fetch the HTML for a node and persist it to metadata."""
    session = SessionLocal()
    try:
        node = session.get(DBNode, node_id)
        if node is None:
            raise ValueError(f"Node not found for id {node_id}")

        response = requests.get(node.url, timeout=10)
        response.raise_for_status()
        html = response.content

        metadata = node.metadata or {}
        metadata["archived_html"] = html.decode("utf-8", errors="ignore")
        node.metadata = metadata
        session.commit()
        return html
    except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
        session.rollback()
        raise RuntimeError(f"Failed to archive HTML for node {node_id}: {exc}") from exc
    finally:
        session.close()
