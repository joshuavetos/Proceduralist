"""Simple performance scan leveraging archived HTML."""
from __future__ import annotations

import re
from sqlalchemy.exc import SQLAlchemyError

from backend.models.db import DBNode, SessionLocal

SCRIPT_RE = re.compile(r"<script", re.IGNORECASE)


def perf_scan(map_id: int) -> dict:
    """Summarize HTML size and script counts for nodes in a map."""
    session = SessionLocal()
    try:
        nodes = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        results = []
        for node in nodes:
            html = (node.metadata or {}).get("archived_html")
            if not html:
                continue
            size = len(html)
            scripts = len(SCRIPT_RE.findall(html))
            results.append({"node": node.id, "size": size, "scripts": scripts})
        return {"perf": results}
    except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Failed to perform performance scan for map {map_id}: {exc}") from exc
    finally:
        session.close()
