"""Deterministic governance scoring subsystem.

This module computes severity, entropy, and integrity scores for DBMap
records using only persistent DBNode and DBEdge data.
"""
from __future__ import annotations

from typing import List, Set

from backend import auditor, clauses
from backend.models.db import DBEdge, DBMap, DBMapHistory, DBNode, SessionLocal

severity_map = {
    "disabled_action": 0.4,
    "error_message": 0.6,
    "redirect_loop": 0.7,
    "broken_link": 0.5,
    "permission_gate": 0.8,
    "paywall_gate": 0.9,
    "captcha_gate": 0.3,
}


def _get_map_or_raise(session, map_id: int) -> DBMap:
    map_record = session.get(DBMap, map_id)
    if map_record is None:
        raise ValueError("Map not found")
    return map_record


def compute_severity(map_id: int) -> float:
    """Compute severity_score for a map and persist it on DBMap."""
    session = SessionLocal()
    try:
        map_record = _get_map_or_raise(session, map_id)
        nodes: List[DBNode] = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        edges: List[DBEdge] = session.query(DBEdge).filter(DBEdge.map_id == map_id).all()

        contradiction_types: List[str] = []
        for node in nodes:
            if node.is_contradiction or node.contradiction_type:
                if not node.contradiction_type:
                    raise ValueError("Contradiction node missing contradiction_type")
                contradiction_types.append(node.contradiction_type)
        for edge in edges:
            if edge.is_contradiction or edge.contradiction_type:
                if not edge.contradiction_type:
                    raise ValueError("Contradiction edge missing contradiction_type")
                contradiction_types.append(edge.contradiction_type)

        total_contradictions = len(contradiction_types)
        if total_contradictions == 0:
            severity_score = 0.0
        else:
            total_severity = 0.0
            for contradiction in contradiction_types:
                if contradiction not in severity_map:
                    raise ValueError(f"Unsupported contradiction_type: {contradiction}")
                total_severity += severity_map[contradiction]
            severity_score = total_severity / total_contradictions

        map_record.severity_score = severity_score
        session.commit()
        return severity_score
    finally:
        session.close()


def compute_entropy(map_id: int) -> float:
    """Compute entropy_score for a map and persist it on DBMap."""
    session = SessionLocal()
    try:
        map_record = _get_map_or_raise(session, map_id)
        nodes: List[DBNode] = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        edges: List[DBEdge] = session.query(DBEdge).filter(DBEdge.map_id == map_id).all()

        node_ids: Set[int] = {node.id for node in nodes}
        if not node_ids:
            entropy_score = 0.0
        else:
            visited: Set[int] = set()
            for edge in edges:
                if edge.from_node_id in node_ids:
                    visited.add(edge.from_node_id)
                if edge.to_node_id in node_ids:
                    visited.add(edge.to_node_id)
            entropy_score = len(visited) / len(node_ids)

        map_record.entropy_score = entropy_score
        session.commit()
        return entropy_score
    finally:
        session.close()


def compute_integrity(map_id: int) -> float:
    """Compute integrity_score for a map using stored severity and entropy."""
    session = SessionLocal()
    try:
        map_record = _get_map_or_raise(session, map_id)
        severity_score = map_record.severity_score or 0.0
        entropy_score = map_record.entropy_score or 0.0

        integrity_score = 1.0 - (severity_score * 0.5 + entropy_score * 0.5)
        integrity_score = max(0.0, min(1.0, integrity_score))

        map_record.integrity_score = integrity_score
        session.commit()
        return integrity_score
    finally:
        session.close()


def compute_scores_and_publish(map_id: int) -> dict[str, float]:
    """Compute scores, record history, and auto-publish the map."""

    if map_id <= 0:
        raise ValueError("Map id must be positive")

    severity = compute_severity(map_id)
    entropy = compute_entropy(map_id)
    integrity = compute_integrity(map_id)

    session = SessionLocal()
    try:
        map_record = _get_map_or_raise(session, map_id)

        nodes: List[DBNode] = session.query(DBNode).filter(DBNode.map_id == map_id).all()
        edges: List[DBEdge] = session.query(DBEdge).filter(DBEdge.map_id == map_id).all()

        contradictions = 0
        for node in nodes:
            if node.is_contradiction or node.contradiction_type:
                assert node.contradiction_type, "Contradiction node missing contradiction_type"
                contradictions += 1
        for edge in edges:
            if edge.is_contradiction or edge.contradiction_type:
                assert edge.contradiction_type, "Contradiction edge missing contradiction_type"
                contradictions += 1

        history_entry = DBMapHistory(
            map_id=map_id,
            severity=severity,
            entropy=entropy,
            integrity=integrity,
            contradictions=contradictions,
        )
        session.add(history_entry)

        map_record.status = "published"
        map_record.severity_score = severity
        map_record.entropy_score = entropy
        map_record.integrity_score = integrity

        session.commit()

        return {
            "severity": severity,
            "entropy": entropy,
            "integrity": integrity,
            "contradictions": contradictions,
        }
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
