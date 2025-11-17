"""Seed data for Proceduralist demo graphs."""
from __future__ import annotations

from backend import auditor, clauses
from backend.models.graph import ActionEdge, Graph, StateNode
from backend.models.map import Map, MapStore


def build_seed_graph() -> Graph:
    nodes = [
        StateNode(id=1, url="https://example.com", title="Home"),
        StateNode(
            id=2,
            url="https://example.com/disabled",
            title="Disabled CTA",
            is_contradiction=True,
            contradiction_type="disabled_action",
        ),
        StateNode(
            id=3,
            url="https://example.com/error",
            title="Server Error",
            is_contradiction=True,
            contradiction_type="error_message",
        ),
    ]
    edges = [
        ActionEdge(from_node_id=1, to_node_id=2, action_label="CTA"),
        ActionEdge(
            from_node_id=1,
            to_node_id=3,
            action_label="Submit",
            is_contradiction=True,
            contradiction_type="error_message",
        ),
    ]
    return Graph(nodes=nodes, edges=edges)


def seed_maps(store: MapStore) -> Map:
    demo = store.create(title="Demo Audit", start_url="https://example.com")
    store.update_status(demo.id or 1, "published")
    return demo


auditor_metadata = {"auditor": auditor, "clauses": clauses}
