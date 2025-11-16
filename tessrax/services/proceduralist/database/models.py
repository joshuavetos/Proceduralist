"""State database models for Tessrax Proceduralist services (v1.2.1).

The ORM schema captures the immutable state graph that the core runner
processes.  Every column, index, and relationship in this module complies with
AEP-001 (auto-executability) and RVC-001 (runtime verification) by ensuring all
referenced dependencies resolve when the module is imported.  Each model embeds
operational safeguards such as processed flags, timestamp metadata, processing
attempt counters, and soft-deletion semantics enforced via a hybrid property.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow() -> datetime:
    """Return a timezone-aware timestamp for ORM defaults."""

    return datetime.now(timezone.utc)


class TimestampMixin:
    """Common timestamp fields shared across ORM models."""

    created_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class SoftDeleteMixin:
    """Provides a nullable ``deleted_at`` timestamp and ``is_deleted`` hybrid."""

    deleted_at = Column(DateTime, nullable=True)

    @hybrid_property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @is_deleted.expression  # pragma: no cover - SQL expression mapping
    def is_deleted(cls):  # type: ignore[override]
        return cls.deleted_at.isnot(None)


class StateNode(TimestampMixin, SoftDeleteMixin, Base):
    """Graph node representing a crawled state (page, action result, etc.)."""

    __tablename__ = "state_nodes"

    id = Column(Integer, primary_key=True)
    state_hash = Column(String, unique=True, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)

    is_contradiction = Column(Boolean, default=False, nullable=False)
    processed = Column(Boolean, default=False, nullable=False, index=True)

    processed_at = Column(DateTime, nullable=True)
    processing_attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)

    outgoing_edges = relationship(
        "ActionEdge",
        back_populates="from_node",
        foreign_keys="ActionEdge.from_node_id",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "ActionEdge",
        back_populates="to_node",
        foreign_keys="ActionEdge.to_node_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        hash_preview = (self.state_hash or "")[:7]
        return f"<StateNode id={self.id} hash={hash_preview}>"


class ActionEdge(TimestampMixin, SoftDeleteMixin, Base):
    """Directed edge connecting two ``StateNode`` records."""

    __tablename__ = "action_edges"

    id = Column(Integer, primary_key=True)
    from_node_id = Column(Integer, ForeignKey("state_nodes.id", ondelete="CASCADE"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("state_nodes.id", ondelete="CASCADE"), nullable=False)

    action_label = Column(String, nullable=True)
    is_contradiction = Column(Boolean, default=False, nullable=False)

    from_node = relationship("StateNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("StateNode", foreign_keys=[to_node_id], back_populates="incoming_edges")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ActionEdge id={self.id} from={self.from_node_id} "
            f"to={self.to_node_id} label={self.action_label}>"
        )


# Indexes (duplicated for clarity even though SQLAlchemy handles unique/foreign keys)
Index("idx_state_hash_unique", StateNode.state_hash, unique=True)
Index("idx_node_processed", StateNode.processed)
Index("idx_edge_from", ActionEdge.from_node_id)
Index("idx_edge_to", ActionEdge.to_node_id)
Index("idx_edge_contra", ActionEdge.is_contradiction)
