"""Check links inside archived HTML."""
from __future__ import annotations

import re
import requests
from sqlalchemy.exc import SQLAlchemyError

from backend.models.db import DBNode, SessionLocal

HREF_RE = re.compile(r"href=['\"]([^'\"]+)['\"]", re.IGNORECASE)


def check_links(map_id: int) -> dict:
    """Return broken links for all archived nodes within a map."""
    session = SessionLocal()
    try:
        nodes = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        broken = []
        for node in nodes:
            metadata = node.metadata or {}
            html = metadata.get("archived_html")
            if not html:
                continue
            links = HREF_RE.findall(html)
            for link in links:
                try:
                    response = requests.head(link, timeout=5)
                    if response.status_code >= 400:
                        broken.append({"node": node.id, "url": link})
                except Exception:
                    broken.append({"node": node.id, "url": link})
        return {"broken_links": broken}
    except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Failed to check links for map {map_id}: {exc}") from exc
    finally:
        session.close()
