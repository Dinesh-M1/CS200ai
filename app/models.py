"""
Data model.

Document        -- a logical document (e.g. "CT-200 Manual")
DocumentVersion  -- one ingested snapshot of that document (v1, v2, ...)
Node             -- one heading/section within a specific DocumentVersion.
                     `logical_key` is what ties the "same" node across versions
                     together (see app/versioning.py for the matching strategy).
Selection        -- a named, version-pinned set of nodes a user picked for
                     test-case generation.
SelectionNode    -- join table: selection <-> exact (node_id) pin.
                     Because a Node row belongs to exactly one DocumentVersion,
                     pinning to a node_id automatically pins to a version too.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    versions = relationship("DocumentVersion", back_populates="document",
                             order_by="DocumentVersion.version_number")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    document = relationship("Document", back_populates="versions")
    nodes = relationship("Node", back_populates="document_version")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True)
    document_version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)

    heading = Column(String, nullable=False)
    level = Column(Integer, nullable=False)          # markdown heading depth, 1..6
    body = Column(Text, default="")
    content_hash = Column(String, nullable=False)      # sha256 of (heading + body), see parser.py
    order_index = Column(Integer, nullable=False)       # sibling order, for stable listing

    # Used for cross-version matching. Built from the heading path, e.g.
    # "Alarms/Pressure Threshold". Duplicate headings under the same parent
    # get a disambiguating suffix (see parser.py) so two distinct nodes never
    # collide on logical_key within the same version.
    logical_key = Column(String, nullable=False, index=True)

    document_version = relationship("DocumentVersion", back_populates="nodes")
    children = relationship("Node", backref="parent", remote_side=[id])


class Selection(Base):
    __tablename__ = "selections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    node_links = relationship("SelectionNode", back_populates="selection")


class SelectionNode(Base):
    __tablename__ = "selection_nodes"

    id = Column(Integer, primary_key=True)
    selection_id = Column(Integer, ForeignKey("selections.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)

    selection = relationship("Selection", back_populates="node_links")
    node = relationship("Node")