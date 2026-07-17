from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document, DocumentVersion, Node
from app.schemas import NodeOut, NodeSummary
from app.versioning import diff_node_across_versions, get_latest_version

router = APIRouter(tags=["browse"])


def _resolve_version(db: Session, document_name: str, version: int | None) -> DocumentVersion:
    document = db.query(Document).filter(Document.name == document_name).first()
    if document is None:
        raise HTTPException(404, f"document '{document_name}' not found")
    if version is None:
        dv = get_latest_version(db, document.id)
    else:
        dv = (db.query(DocumentVersion)
              .filter(DocumentVersion.document_id == document.id,
                      DocumentVersion.version_number == version).first())
    if dv is None:
        raise HTTPException(404, "version not found")
    return dv


@router.get("/documents/{document_name}/sections", response_model=list[NodeSummary])
def list_top_level_sections(document_name: str, version: int | None = None, db: Session = Depends(get_db)):
    """Top-level sections for a document. `version` defaults to latest."""
    dv = _resolve_version(db, document_name, version)
    nodes = (db.query(Node)
             .filter(Node.document_version_id == dv.id, Node.parent_id.is_(None))
             .order_by(Node.order_index)
             .all())
    return nodes


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(404, "node not found")
    return node


@router.get("/nodes/{node_id}/children", response_model=list[NodeSummary])
def get_node_children(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(404, "node not found")
    children = (db.query(Node)
                .filter(Node.parent_id == node_id)
                .order_by(Node.order_index)
                .all())
    return children


@router.get("/documents/{document_name}/search", response_model=list[NodeOut])
def search_nodes(document_name: str, q: str = Query(..., min_length=1),
                  version: int | None = None, db: Session = Depends(get_db)):
    dv = _resolve_version(db, document_name, version)
    like = f"%{q}%"
    results = (db.query(Node)
               .filter(Node.document_version_id == dv.id)
               .filter((Node.heading.ilike(like)) | (Node.body.ilike(like)))
               .all())
    return results


@router.get("/nodes/{node_id}/diff")
def get_node_diff(node_id: int, to_version: int, db: Session = Depends(get_db)):
    """Has this node changed between its own version and `to_version`?"""
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(404, "node not found")
    dv = db.query(DocumentVersion).filter(DocumentVersion.id == node.document_version_id).first()
    return diff_node_across_versions(
        db, dv.document_id, node.logical_key, dv.version_number, to_version
    )