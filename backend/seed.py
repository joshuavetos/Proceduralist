"""Seed data for Proceduralist demo graphs."""
from __future__ import annotations

from backend import auditor, clauses
from backend.models.db import DBEdge, DBNode, SessionLocal
from backend.models.graph import ActionEdge, Graph, StateNode
from backend.models.map import MapRepository


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


def seed_maps(repository: MapRepository) -> None:
    demo = repository.create(title="Demo Audit", start_url="https://example.com")
    graph = build_seed_graph()
    session = SessionLocal()
    try:
        session.query(DBEdge).filter(DBEdge.map_id == demo.id).delete()
        session.query(DBNode).filter(DBNode.map_id == demo.id).delete()
        session.commit()

        graph_id_lookup = {}
        for node in graph.nodes:
            db_node = DBNode(
                map_id=demo.id or 0,
                url=node.url,
                title=node.title,
                is_contradiction=node.is_contradiction,
                contradiction_type=node.contradiction_type,
                metadata=node.metadata,
            )
            session.add(db_node)
            session.flush()
            assert db_node.id is not None, "Seed node must have id"
            graph_id_lookup[node.id] = db_node.id

        for edge in graph.edges:
            from_node_id = graph_id_lookup.get(edge.from_node_id, edge.from_node_id)
            to_node_id = graph_id_lookup.get(edge.to_node_id, edge.to_node_id)
            db_edge = DBEdge(
                map_id=demo.id or 0,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                action_label=edge.action_label,
                is_contradiction=edge.is_contradiction,
                contradiction_type=edge.contradiction_type,
            )
            session.add(db_edge)
        session.commit()
        repository.update_status(demo.id or 1, "published")
    finally:
        session.close()


auditor_metadata = {"auditor": auditor, "clauses": clauses}
