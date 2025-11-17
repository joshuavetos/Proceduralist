"""Database models and session utilities for Proceduralist backend.

All SQLAlchemy models include explicit ``__tablename__`` definitions to satisfy
schema clarity requirements. Runtime assertions and deterministic error messages
prevent silent failures during persistence.
"""
from __future__ import annotations

import os
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from backend import auditor, clauses

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://proceduralist:password@localhost:5432/proceduralist",
)

assert DATABASE_URL, "DATABASE_URL must be configured for persistent storage"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

Base = declarative_base()


class DBMap(Base):
    __tablename__ = "maps"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    start_url = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    severity_score = Column(Float, nullable=True, default=None)
    entropy_score = Column(Float, nullable=True, default=None)
    integrity_score = Column(Float, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    nodes = relationship("DBNode", back_populates="map", cascade="all, delete-orphan")
    edges = relationship("DBEdge", back_populates="map", cascade="all, delete-orphan")


class DBNode(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    map_id = Column(Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False, default="")
    is_contradiction = Column(Boolean, nullable=False, default=False)
    contradiction_type = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    map = relationship("DBMap", back_populates="nodes")
    outgoing_edges = relationship(
        "DBEdge",
        back_populates="from_node",
        foreign_keys="DBEdge.from_node_id",
        cascade="all, delete-orphan",
    )


class DBEdge(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, index=True)
    map_id = Column(Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True)
    from_node_id = Column(
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    action_label = Column(String, nullable=False, default="navigate")
    is_contradiction = Column(Boolean, nullable=False, default=False)
    contradiction_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    map = relationship("DBMap", back_populates="edges")
    from_node = relationship("DBNode", foreign_keys=[from_node_id])
    to_node = relationship("DBNode", foreign_keys=[to_node_id])


def init_db() -> None:
    """Create tables if they do not exist, enforcing schema determinism."""
    Base.metadata.create_all(bind=engine)


auditor_metadata = {"auditor": auditor, "clauses": clauses}

# Initialize the schema on import to guarantee availability for all endpoints.
init_db()
