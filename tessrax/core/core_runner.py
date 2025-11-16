"""Tessrax Core Runner v1.2.1 (Metabolic Spine).

This module orchestrates the Detect → Classify → Record loop for state nodes
persisted in the Proceduralist database.  The implementation follows the
Tessrax governance mandates by providing:

* processed flags guarded via atomic compare-and-swap operations (AEP-001);
* deterministic Postgres connectivity with runtime validation (RVC-001);
* per-node crash isolation so a single failure cannot halt the runner;
* contradiction detection based on both node and edge assertions;
* soft-delete enforcement with a dead-letter queue for repeated failures;
* memory-engine receipts signed with SHA-256 integrity digests.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import time
from datetime import datetime
from typing import Iterable

from sqlalchemy import create_engine, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from tessrax.core.governance_kernel import classify_clean, classify_contradiction
from tessrax.core.memory_engine import write_receipt
from tessrax.services.proceduralist.database.models import ActionEdge, StateNode

POSTGRES_USER = os.getenv("TESSRAX_DB_USER", "tessrax")
POSTGRES_PASSWORD = os.getenv("TESSRAX_DB_PASSWORD", "password")
POSTGRES_DB = os.getenv("TESSRAX_DB_NAME", "tessrax_state")
POSTGRES_HOST = os.getenv("TESSRAX_DB_HOST", "postgres")
POSTGRES_PORT = os.getenv("TESSRAX_DB_PORT", "5432")

DB_URL = os.getenv(
    "TESSRAX_DB_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

SHUTDOWN = False
MAX_ATTEMPTS = int(os.getenv("TESSRAX_MAX_ATTEMPTS", "3"))
POLL_INTERVAL_SECONDS = float(os.getenv("TESSRAX_POLL_INTERVAL", "1"))
IDLE_SLEEP_SECONDS = float(os.getenv("TESSRAX_IDLE_SLEEP", "2"))


def _signal_handler(sig, frame):
    del sig, frame
    global SHUTDOWN
    SHUTDOWN = True
    print("[CORE] Shutdown signal received. Draining loop...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def _integrity_digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_claim(db: Session, node: StateNode) -> bool:
    stmt = (
        update(StateNode)
        .where(StateNode.id == node.id, StateNode.processed.is_(False))
        .values(processed=True, processed_at=datetime.utcnow())
    )
    result = db.execute(stmt)
    db.commit()
    claimed = result.rowcount == 1
    if claimed:
        node.processed = True
        node.processed_at = datetime.utcnow()
    return claimed


def _release_claim(db: Session, node: StateNode) -> None:
    db.execute(
        update(StateNode)
        .where(StateNode.id == node.id)
        .values(processed=False, processed_at=None)
    )
    db.commit()
    node.processed = False
    node.processed_at = None


def get_unprocessed_nodes(db: Session) -> Iterable[StateNode]:
    stmt = select(StateNode).where(
        StateNode.processed.is_(False),
        StateNode.deleted_at.is_(None),
    )
    return db.execute(stmt).scalars().all()


def _has_contradictory_edge(db: Session, node: StateNode) -> bool:
    stmt = (
        select(ActionEdge.id)
        .where(
            ActionEdge.deleted_at.is_(None),
            ActionEdge.is_contradiction.is_(True),
            or_(ActionEdge.from_node_id == node.id, ActionEdge.to_node_id == node.id),
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _record_governance_event(decision) -> None:
    if not getattr(decision, "state_hash", None):
        raise ValueError(
            f"[CORE] GovernanceDecision missing state_hash (node_id={decision.node_id})"
        )

    decision_type = decision.decision
    if decision_type == "VERIFIED":
        event_type = "STATE_AUDITED"
    elif decision_type in {"LOGGED", "ESCALATE", "DEFER"}:
        event_type = "CONTRADICTION_DETECTED"
    else:
        raise ValueError(f"Unsupported governance decision type: {decision_type}")

    payload = {
        "event_type": event_type,
        "decision": decision_type,
        "severity": decision.severity,
        "policy_code": decision.policy_code,
        "rationale": decision.rationale.summary,
        "category": decision.category,
        "tags": list(decision.tags),
        "node_id": decision.node_id,
        "state_hash": decision.state_hash,
        "recurrence_count": decision.recurrence_count,
        "first_seen": decision.first_seen,
        "last_seen": decision.last_seen,
        "confidence": decision.confidence,
    }
    payload["integrity_hash"] = _integrity_digest(payload)
    write_receipt(event_type=event_type, payload=payload, audited_state_hash=decision.state_hash)


def _dead_letter(db: Session, node: StateNode, error_msg: str) -> None:
    node.deleted_at = datetime.utcnow()
    node.last_error = error_msg
    node.processed = True
    node.processed_at = datetime.utcnow()
    db.commit()
    print(f"[CORE] Node {node.id} moved to DEAD LETTER QUEUE.")


def process_node(db: Session, node: StateNode) -> None:
    if node.deleted_at is not None:
        return

    if (node.processing_attempts or 0) >= MAX_ATTEMPTS:
        _dead_letter(db, node, node.last_error or "Exceeded max attempts")
        return

    if not _atomic_claim(db, node):
        return

    try:
        if node.is_contradiction:
            decision = classify_contradiction(node)
            _record_governance_event(decision)
        else:
            if _has_contradictory_edge(db, node):
                node.is_contradiction = True
                db.commit()
                decision = classify_contradiction(node)
            else:
                decision = classify_clean(node)
            _record_governance_event(decision)

        node.processing_attempts = 0
        node.last_error = None
        db.commit()

    except Exception as exc:  # pragma: no cover - defensive runtime guard
        print(f"[CORE] ERROR processing node {node.id}: {exc}")
        node.processing_attempts = (node.processing_attempts or 0) + 1
        node.last_error = str(exc)
        if node.processing_attempts >= MAX_ATTEMPTS:
            _dead_letter(db, node, node.last_error)
        else:
            db.commit()
            _release_claim(db, node)
        raise


def run_loop() -> None:
    print("[CORE] Tessrax OS v1.2.1 Core Runner online.")

    while not SHUTDOWN:
        db = SessionLocal()
        try:
            nodes = get_unprocessed_nodes(db)
            if not nodes:
                print("[CORE] No pending nodes.")
                time.sleep(IDLE_SLEEP_SECONDS)
            else:
                for node in nodes:
                    try:
                        process_node(db, node)
                    except Exception:
                        continue
        finally:
            db.close()

        time.sleep(POLL_INTERVAL_SECONDS)

    print("[CORE] Shutdown complete.")


if __name__ == "__main__":
    run_loop()
