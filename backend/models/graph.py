"""Graph data structures with typed contradictions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend import auditor, clauses


CONTRADICTION_TYPE = {
    "disabled_action",
    "error_message",
    "redirect_loop",
    "hidden_prerequisite",
    "broken_link",
    "permission_gate",
    "paywall_gate",
    "captcha_gate",
}


def validate_contradiction(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value not in CONTRADICTION_TYPE:
        raise ValueError(f"Unsupported contradiction type: {value}")
    return value


@dataclass
class StateNode:
    """Represents a node in the audit graph."""

    id: int
    url: str
    title: str = ""
    is_contradiction: bool = False
    contradiction_type: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.contradiction_type = validate_contradiction(self.contradiction_type)


@dataclass
class ActionEdge:
    """Directed edge between nodes."""

    from_node_id: int
    to_node_id: int
    action_label: str
    is_contradiction: bool = False
    contradiction_type: Optional[str] = None

    def __post_init__(self) -> None:
        self.contradiction_type = validate_contradiction(self.contradiction_type)


@dataclass
class Graph:
    nodes: List[StateNode]
    edges: List[ActionEdge]


mock_metadata = {"auditor": auditor, "clauses": clauses}
