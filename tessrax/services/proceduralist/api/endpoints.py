"""Proceduralist API endpoints for Tessrax services.

This module exposes three FastAPI endpoints that surface ledger-backed
truth data, crawl state metadata, and graph connectivity.  Each endpoint
performs strict input validation, enforces API-key authorization, and
uses dependency-injected SQLAlchemy sessions to avoid connection leaks.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Generator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from tessrax.services.proceduralist.database.models import ActionEdge, StateNode

router = APIRouter()
app = FastAPI(title="Tessrax Proceduralist API", version="1.0.0")
app.include_router(router)

LEDGER_INDEX_PATH = Path("tessrax/ledger/index.db")

POSTGRES_USER = os.getenv("POSTGRES_USER", "tessrax")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "tessrax_state")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")

DB_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"
)
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

API_KEY = os.getenv("TESSRAX_API_KEY")
if not API_KEY:
    raise RuntimeError("TESSRAX_API_KEY not set")

STATE_HASH_PATTERN = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{64})$")


def get_db() -> Generator[Session, None, None]:
    """Provide a scoped SQLAlchemy session via FastAPI dependency injection."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(key: Optional[str]) -> None:
    """Raise ``HTTPException`` when the caller does not provide a valid key."""

    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key.")


def _open_index_connection() -> sqlite3.Connection:
    uri = f"file:{LEDGER_INDEX_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def check_ledger_for_hash(state_hash: str) -> Optional[str]:
    """Return verification status for ``state_hash`` based on ledger events."""

    try:
        with _open_index_connection() as con:
            cur = con.execute(
                "SELECT event_type FROM ledger_index WHERE state_hash = ?",
                (state_hash,),
            )
            rows = cur.fetchall()
    except sqlite3.Error:
        return None

    if not rows:
        return None

    event_types = {row[0] for row in rows}

    if "STATE_AUDITED" in event_types:
        return "VERIFIED"
    if "CONTRADICTION_DETECTED" in event_types:
        return "CONTRADICTION"
    return None


def validate_state_hash(value: str) -> str:
    """Ensure ``value`` matches the expected hexadecimal digest shape."""

    if not STATE_HASH_PATTERN.match(value):
        raise HTTPException(status_code=400, detail="Invalid state_hash format")
    return value


@router.get("/api/v1/truth/{state_hash}")
def truth_query(
    state_hash: str = Depends(validate_state_hash),
    x_api_key: Optional[str] = Header(default=None),
):
    """Return verification status for ``state_hash`` using the ledger index."""

    require_api_key(x_api_key)

    status = check_ledger_for_hash(state_hash)

    if status == "VERIFIED":
        return {"state_hash": state_hash, "is_verified": True}

    if status == "CONTRADICTION":
        return {
            "state_hash": state_hash,
            "is_verified": False,
            "reason": "Contradiction detected",
        }

    return {
        "state_hash": state_hash,
        "is_verified": False,
        "reason": "Not present in ledger",
    }


@router.get("/api/v1/state/{state_hash}")
def get_state_details(
    state_hash: str = Depends(validate_state_hash),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Fetch metadata for a ``StateNode`` and its ledger verification state."""

    require_api_key(x_api_key)

    stmt = select(StateNode).where(StateNode.state_hash == state_hash)
    node = db.execute(stmt).scalars().first()

    if not node:
        raise HTTPException(status_code=404, detail="State not found.")

    status = check_ledger_for_hash(state_hash)

    return {
        "node_id": node.id,
        "url": node.url,
        "title": node.title,
        "is_contradiction": node.is_contradiction,
        "verified_status": status or "UNVERIFIED",
    }


@router.get("/api/v1/graph/children/{state_hash}")
def get_children(
    state_hash: str = Depends(validate_state_hash),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return outgoing edges for a ``StateNode`` identified by ``state_hash``."""

    require_api_key(x_api_key)

    stmt_node = select(StateNode).where(StateNode.state_hash == state_hash)
    node = db.execute(stmt_node).scalars().first()

    if not node:
        raise HTTPException(status_code=404, detail="State not found.")

    stmt_edges = select(ActionEdge).where(ActionEdge.from_node_id == node.id)
    edges = db.execute(stmt_edges).scalars().all()

    return {
        "node_id": node.id,
        "children": [
            {
                "to_node_id": edge.to_node_id,
                "action_label": edge.action_label,
                "is_contradiction": edge.is_contradiction,
            }
            for edge in edges
        ],
    }
