"""Streamlit dashboard for Tessrax OS v1.2."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import streamlit as st
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased, sessionmaker

from tessrax.services.proceduralist.database.models import ActionEdge, StateNode

POSTGRES_USER = os.getenv("POSTGRES_USER", "tessrax")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "tessrax_state")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
DEFAULT_DB_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
DB_URL = os.getenv("TESSRAX_DB_URL", DEFAULT_DB_URL)

LEDGER_INDEX_PATH = Path(os.getenv("LEDGER_INDEX_PATH", "tessrax/ledger/index.db"))
LEDGER_PATH = Path(os.getenv("LEDGER_PATH", "tessrax/ledger/ledger.jsonl"))


@st.cache_resource(show_spinner=False)
def _session_factory(url: str = DB_URL) -> sessionmaker:
    engine = create_engine(url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


SessionLocal = _session_factory()


@dataclass(slots=True)
class GraphContext:
    node: StateNode
    children: List[Dict[str, str]]
    parents: List[Dict[str, str]]


def _with_session(operation: Callable[[Session], Dict[str, int] | List[Dict[str, str]] | GraphContext | None], default):
    try:
        with SessionLocal() as session:
            return operation(session)
    except SQLAlchemyError as exc:
        st.warning(f"Database unavailable: {exc}")
        return default


def _sanitize_db_url(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    prefix, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    user = creds.split(":", 1)[0]
    return f"{prefix}://{user}:***@{host}"


def _fetch_state_summary(session: Session) -> Dict[str, int]:
    total_states = session.execute(select(func.count(StateNode.id))).scalar() or 0
    total_edges = session.execute(select(func.count(ActionEdge.id))).scalar() or 0
    contradictions = (
        session.execute(select(func.count(StateNode.id)).where(StateNode.is_contradiction.is_(True))).scalar()
        or 0
    )
    return {
        "states": int(total_states),
        "edges": int(total_edges),
        "contradictions": int(contradictions),
    }


def _fetch_recent_contradictions(session: Session) -> List[Dict[str, str]]:
    stmt = (
        select(StateNode)
        .where(StateNode.is_contradiction.is_(True))
        .order_by(StateNode.updated_at.desc())
        .limit(12)
    )
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "state_hash": node.state_hash,
            "title": node.title or "(untitled)",
            "url": node.url,
            "updated_at": node.updated_at.isoformat() if node.updated_at else "",
        }
        for node in rows
    ]


def _count_receipts() -> int:
    if not LEDGER_INDEX_PATH.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{LEDGER_INDEX_PATH}?mode=ro", uri=True) as con:
            cur = con.execute("SELECT COUNT(*) FROM ledger_index")
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def _load_recent_events(limit: int = 20) -> List[Dict[str, str]]:
    if not LEDGER_INDEX_PATH.exists():
        return []
    try:
        with sqlite3.connect(f"file:{LEDGER_INDEX_PATH}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                """
                SELECT ledger_offset, event_type, state_hash, payload_hash, timestamp
                FROM ledger_index
                ORDER BY ledger_offset DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
    except sqlite3.Error:
        return []

    return [
        {
            "offset": row["ledger_offset"],
            "event_type": row["event_type"],
            "state_hash": row["state_hash"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def _fetch_graph_context(session: Session, state_hash: str) -> Optional[GraphContext]:
    node = (
        session.execute(select(StateNode).where(StateNode.state_hash == state_hash)).scalars().first()
    )
    if not node:
        return None

    ChildNode = aliased(StateNode)
    ParentNode = aliased(StateNode)

    child_stmt = (
        select(ActionEdge, ChildNode)
        .join(ChildNode, ActionEdge.to_node_id == ChildNode.id)
        .where(ActionEdge.from_node_id == node.id)
    )
    parent_stmt = (
        select(ActionEdge, ParentNode)
        .join(ParentNode, ActionEdge.from_node_id == ParentNode.id)
        .where(ActionEdge.to_node_id == node.id)
    )

    children = [
        {
            "state_hash": child.state_hash,
            "title": child.title or "(untitled)",
            "action": edge.action_label or "", 
            "is_contradiction": "Yes" if edge.is_contradiction else "No",
        }
        for edge, child in session.execute(child_stmt).all()
    ]

    parents = [
        {
            "state_hash": parent.state_hash,
            "title": parent.title or "(untitled)",
            "action": edge.action_label or "",
            "is_contradiction": "Yes" if edge.is_contradiction else "No",
        }
        for edge, parent in session.execute(parent_stmt).all()
    ]

    return GraphContext(node=node, children=children, parents=parents)


def _graphviz_for_context(context: GraphContext) -> str:
    def _label(title: str, suffix: str) -> str:
        safe_title = (title or "(untitled)").replace("\"", "'")
        return f"{suffix}: {safe_title}"[:60]

    lines = ["digraph StateGraph {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fontname="Helvetica"];']
    base_id = "node0"
    base_color = "#0a9396" if context.node.is_contradiction else "#1d3557"
    base_label = _label(context.node.title or context.node.url, "State")
    lines.append(
        f'"{base_id}" [label="{base_label}\\n{context.node.state_hash[:10]}" '
        f'fillcolor="#e0fbfc" color="{base_color}"];'
    )

    for idx, child in enumerate(context.children):
        child_id = f"child{idx}"
        color = "#d00000" if child["is_contradiction"] == "Yes" else "#457b9d"
        child_label = _label(child["title"], "Child")
        lines.append(
            f'"{child_id}" [label="{child_label}\\n{child["state_hash"][:10]}" '
            f'fillcolor="#f1faee" color="{color}"];'
        )
        edge_label = child["action"] or "edge"
        lines.append(f'"{base_id}" -> "{child_id}" [label="{edge_label}" fontsize=10];')

    for idx, parent in enumerate(context.parents):
        parent_id = f"parent{idx}"
        color = "#e85d04" if parent["is_contradiction"] == "Yes" else "#588157"
        parent_label = _label(parent["title"], "Parent")
        lines.append(
            f'"{parent_id}" [label="{parent_label}\\n{parent["state_hash"][:10]}" '
            f'fillcolor="#fff3b0" color="{color}"];'
        )
        edge_label = parent["action"] or "edge"
        lines.append(f'"{parent_id}" -> "{base_id}" [label="{edge_label}" fontsize=10];')

    lines.append("}")
    return "\n".join(lines)


st.set_page_config(page_title="Tessrax Dashboard", layout="wide")
st.title("Tessrax OS v1.2 Observatory")
st.caption("Realtime view of the state graph, ledger receipts, and contradictions.")

summary = _with_session(_fetch_state_summary, {"states": 0, "edges": 0, "contradictions": 0})
receipts = _count_receipts()

col1, col2, col3, col4 = st.columns(4)
col1.metric("State Nodes", summary["states"])
col2.metric("Action Edges", summary["edges"])
col3.metric("Contradictions", summary["contradictions"])
col4.metric("Ledger Receipts", receipts)

st.divider()

contradictions = _with_session(_fetch_recent_contradictions, [])
st.subheader("Recent Contradictions")
if contradictions:
    st.table(contradictions)
else:
    st.info("No contradictions recorded yet.")

st.subheader("Recent Ledger Events")
recent_events = _load_recent_events()
if recent_events:
    st.table(recent_events)
else:
    if LEDGER_INDEX_PATH.exists():
        st.info("Ledger index is present but no events were found.")
    else:
        st.warning(f"Ledger index missing at {LEDGER_INDEX_PATH}.")

st.divider()

st.subheader("State Graph Explorer")
state_hash_input = st.text_input("Lookup state hash", placeholder="Enter hex digest", max_chars=64)
query_hash = state_hash_input.strip()
if query_hash:
    context = _with_session(lambda s: _fetch_graph_context(s, query_hash), None)
    if context:
        st.success(
            f"State {context.node.state_hash} — URL: {context.node.url} | Contradiction: {context.node.is_contradiction}",
        )
        dot = _graphviz_for_context(context)
        st.graphviz_chart(dot)
        detail_cols = st.columns(2)
        with detail_cols[0]:
            st.markdown("**Outgoing Edges**")
            st.table(context.children or [{"info": "No outgoing edges"}])
        with detail_cols[1]:
            st.markdown("**Incoming Edges**")
            st.table(context.parents or [{"info": "No incoming edges"}])
    else:
        st.warning("State hash not found in database.")
else:
    st.caption("Provide a state hash to inspect neighboring nodes.")

with st.sidebar:
    st.header("Data Sources")
    st.write(f"Postgres URL: {_sanitize_db_url(DB_URL)}")
    ledger_status = "available" if LEDGER_PATH.exists() else "missing"
    index_status = "available" if LEDGER_INDEX_PATH.exists() else "missing"
    st.write(f"Ledger file: {LEDGER_PATH} ({ledger_status})")
    st.write(f"Ledger index: {LEDGER_INDEX_PATH} ({index_status})")
