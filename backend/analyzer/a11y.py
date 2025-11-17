"""Basic accessibility checks against archived HTML."""
from __future__ import annotations

import re
from sqlalchemy.exc import SQLAlchemyError

from backend.models.db import DBNode, SessionLocal

IMG_RE = re.compile(r"<img[^>]+>", re.IGNORECASE)
ALT_RE = re.compile(r"alt=['\"]([^'\"]*)['\"]", re.IGNORECASE)


def a11y_scan(map_id: int) -> dict:
    """Detect missing alt text on images for all nodes in a map."""
    session = SessionLocal()
    try:
        nodes = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        errors = []
        for node in nodes:
            html = (node.metadata or {}).get("archived_html")
            if not html:
                continue
            for img in IMG_RE.findall(html):
                if not ALT_RE.search(img):
                    errors.append({"node": node.id, "issue": "missing_alt_text"})
        return {"a11y_issues": errors}
    except SQLAlchemyError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Failed to perform accessibility scan for map {map_id}: {exc}") from exc
    finally:
        session.close()
