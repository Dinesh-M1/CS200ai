from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Node, Selection, SelectionNode
from app.schemas import SelectionCreate, SelectionOut

router = APIRouter(prefix="/selections", tags=["selection"])


@router.post("", response_model=SelectionOut)
def create_selection(payload: SelectionCreate, db: Session = Depends(get_db)):
    # Validate every node_id actually exists before pinning — a selection
    # that silently references a dangling node_id is worse than one that
    # fails fast at creation time.
    nodes = db.query(Node).filter(Node.id.in_(payload.node_ids)).all()
    found_ids = {n.id for n in nodes}
    missing = set(payload.node_ids) - found_ids
    if missing:
        raise HTTPException(400, f"node_ids not found: {sorted(missing)}")

    selection = Selection(name=payload.name)
    db.add(selection)
    db.commit()
    db.refresh(selection)

    for node_id in payload.node_ids:
        db.add(SelectionNode(selection_id=selection.id, node_id=node_id))
    db.commit()

    return SelectionOut(id=selection.id, name=selection.name, node_ids=payload.node_ids)


@router.get("/{selection_id}", response_model=SelectionOut)
def get_selection(selection_id: int, db: Session = Depends(get_db)):
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if selection is None:
        raise HTTPException(404, "selection not found")
    node_ids = [link.node_id for link in selection.node_links]
    return SelectionOut(id=selection.id, name=selection.name, node_ids=node_ids)