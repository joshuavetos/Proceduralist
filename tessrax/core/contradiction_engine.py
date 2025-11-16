"""Tessrax Contradiction Engine v1.2.1 (Hardened).

This module isolates the logic that discovers contradiction states that have
not yet been written to the immutable ledger.  The implementation fulfils the
Tessrax governance requirements by ensuring that:

* the ledger index is canonicalised and initialised on cold start;
* every filesystem dependency is created deterministically (AEP-001);
* runtime verification guards validate the provided database/session object;
* persistent locking is unnecessary here because the underlying ledger index
  uses SQLite, which already serialises concurrent reads.

The module is intentionally dependency-light so it can operate during cold
start even when optional infrastructure such as SQLAlchemy is unavailable.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import sqlite3
from pathlib import Path
from typing import Iterable, List, Protocol, Sequence

INDEX_PATH = Path("tessrax/ledger/index.db")
INDEX_TABLE = "ledger_index"


class SupportsExecute(Protocol):
    """Subset of sqlalchemy Session used by the engine."""

    def execute(self, statement): ...  # pragma: no cover - interface contract


@dataclasses.dataclass(slots=True)
class ContradictionNode:
    """Fallback record used when ORM models are unavailable."""

    id: int
    state_hash: str
    url: str | None = None
    title: str | None = None
    is_contradiction: bool = False
    is_deleted: bool = False


@dataclasses.dataclass(slots=True)
class ContradictionEdge:
    """Fallback edge record linking to contradiction states."""

    to_node_id: int
    is_contradiction: bool = False


class RepositoryAdapter(Protocol):
    """Repository abstraction that returns contradiction nodes and edges."""

    def contradiction_nodes(self) -> Iterable[ContradictionNode]: ...

    def contradiction_edges(self) -> Iterable[ContradictionEdge]: ...


class _SQLAlchemyAdapter:
    """Concrete adapter that lazily imports ORM models when available."""

    def __init__(self, session: SupportsExecute) -> None:
        _validate_session(session)
        self._session = session
        self._models = _load_models()

    def contradiction_nodes(self) -> Iterable[ContradictionNode]:
        select = _sqlalchemy_select()
        StateNode = self._models["StateNode"]
        stmt = select(StateNode).where(
            StateNode.is_contradiction.is_(True),
            StateNode.is_deleted.is_(False),
        )
        return list(self._session.execute(stmt).scalars())

    def contradiction_edges(self) -> Iterable[ContradictionEdge]:
        select = _sqlalchemy_select()
        ActionEdge = self._models["ActionEdge"]
        stmt = select(ActionEdge).where(ActionEdge.is_contradiction.is_(True))
        return list(self._session.execute(stmt).scalars())


class _IterableAdapter:
    """Adapter that works with plain iterables for cold-start scenarios."""

    def __init__(self, nodes: Iterable[ContradictionNode], edges: Iterable[ContradictionEdge]):
        self._nodes = list(nodes)
        self._edges = list(edges)

    def contradiction_nodes(self) -> Iterable[ContradictionNode]:
        return list(self._nodes)

    def contradiction_edges(self) -> Iterable[ContradictionEdge]:
        return list(self._edges)


def _ensure_index_schema() -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(INDEX_PATH) as con:
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {INDEX_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_offset INTEGER NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{INDEX_TABLE}_state_hash ON {INDEX_TABLE}(state_hash);"
        )
        con.commit()


def _load_models() -> dict:
    module = importlib.import_module("tessrax.services.proceduralist.database.models")
    try:
        return {"StateNode": module.StateNode, "ActionEdge": module.ActionEdge}
    except AttributeError as exc:  # pragma: no cover - defensive runtime guard
        raise RuntimeError(
            "The database models are undefined. Define StateNode and ActionEdge before using the SQLAlchemy adapter."
        ) from exc


def _validate_session(session: object) -> None:
    if not hasattr(session, "execute"):
        raise TypeError("session must expose an execute() method compatible with SQLAlchemy")


def _state_processed(state_hash: str) -> bool:
    if not state_hash:
        return False
    with sqlite3.connect(INDEX_PATH) as con:
        cur = con.execute(
            f"SELECT COUNT(1) FROM {INDEX_TABLE} WHERE state_hash = ?",
            (state_hash,),
        )
        return (cur.fetchone() or (0,))[0] > 0


def _adapter_from(source, edges=None) -> RepositoryAdapter:
    if hasattr(source, "execute"):
        return _SQLAlchemyAdapter(source)  # type: ignore[arg-type]

    if hasattr(source, "contradiction_nodes") and hasattr(source, "contradiction_edges"):
        return source  # type: ignore[return-value]

    if isinstance(source, Iterable):
        nodes = list(source)
        edges_iter = edges or []
        return _IterableAdapter(nodes, edges_iter)

    raise TypeError(
        "Unsupported source for find_contradictions. Provide a SQLAlchemy session or iterables of nodes and edges."
    )


def find_contradictions(source, *, edges: Sequence[ContradictionEdge] | None = None) -> List[ContradictionNode]:
    """Return contradiction nodes that are not yet represented in the ledger index."""

    _ensure_index_schema()
    adapter = _adapter_from(source, edges)
    results: List[ContradictionNode] = []
    seen_ids: set[int] = set()
    nodes = [n for n in adapter.contradiction_nodes() if n]
    edges_data = list(adapter.contradiction_edges())

    for node in nodes:
        if not node.is_deleted and node.is_contradiction and not _state_processed(node.state_hash):
            results.append(node)
            seen_ids.add(getattr(node, "id", 0))

    for edge in edges_data:
        if not edge.is_contradiction:
            continue
        target_id = getattr(edge, "to_node_id", None)
        if target_id in seen_ids or target_id is None:
            continue
        for node in nodes:
            if getattr(node, "id", None) == target_id and not _state_processed(node.state_hash):
                results.append(node)
                seen_ids.add(target_id)
                break

    return results


def _sqlalchemy_select():
    spec = importlib.util.find_spec("sqlalchemy")
    if spec is None:  # pragma: no cover - executed only when dependency missing
        raise RuntimeError(
            "SQLAlchemy is not installed. Install it or pass iterables of nodes/edges to find_contradictions."
        )
    sqlalchemy_module = importlib.import_module("sqlalchemy")
    return getattr(sqlalchemy_module, "select")


__all__ = [
    "ContradictionNode",
    "ContradictionEdge",
    "find_contradictions",
]
