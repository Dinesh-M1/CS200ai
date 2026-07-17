"""
Document re-ingestion and cross-version node matching.

MATCHING STRATEGY (the thing the assignment wants justified):
We match nodes across versions by `logical_key` — the heading path from
root, e.g. "Alarms/Pressure Threshold", with "#2"-style suffixes for
duplicate sibling headings (see parser.py).

Why this over hash-based or fuzzy matching:
- Hash-based matching (match nodes with identical content_hash) fails the
  MOMENT the body text changes at all — which is exactly the case we most
  need to detect and track, not lose.
- Fuzzy title matching (e.g. string similarity on heading text) is the most
  "clever" option but the least defensible: it can silently merge two
  genuinely different sections that happen to have similar names, which is
  worse than failing to match at all.
- Path-based matching is simple, deterministic, and its failure mode is
  legible: it breaks exactly when someone renames a heading. That's a
  known, nameable limitation rather than a silent one.

KNOWN FAILURE MODE (be ready to state this in the interview):
If a heading is renamed AND its body is edited in the same re-ingestion,
this strategy sees it as "node deleted, new node added" rather than "node
changed" — because the logical_key (which is heading-path-based) no longer
matches anything in the previous version. A production system would want a
secondary pass: for any node that appears "new" in v2, check if there's a
node that "disappeared" from v1 with high body-text similarity, and offer
that as a suggested rename-match for human confirmation. We're not building
that here — flagging it is the point.
"""
from sqlalchemy.orm import Session

from app.models import Document, DocumentVersion, Node
from app.parser import parse_markdown_tree, flatten, RawNode


def get_or_create_document(db: Session, name: str) -> Document:
    doc = db.query(Document).filter(Document.name == name).first()
    if doc is None:
        doc = Document(name=name)
        db.add(doc)
        db.commit()
        db.refresh(doc)
    return doc


def ingest_document(db: Session, document_name: str, markdown_text: str) -> DocumentVersion:
    """Parse `markdown_text` and store it as the next version of
    `document_name`. Does NOT touch or delete prior versions."""
    document = get_or_create_document(db, document_name)

    last_version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    next_version_number = 1 if last_version is None else last_version.version_number + 1

    doc_version = DocumentVersion(document_id=document.id, version_number=next_version_number)
    db.add(doc_version)
    db.commit()
    db.refresh(doc_version)

    root = parse_markdown_tree(markdown_text)
    raw_to_db: dict[int, Node] = {}  # id(RawNode) -> persisted Node

    def persist(raw: RawNode, parent_db_id):
        if raw.heading == "_root":
            for c in raw.children:
                persist(c, None)
            return
        db_node = Node(
            document_version_id=doc_version.id,
            parent_id=parent_db_id,
            heading=raw.heading,
            level=raw.level,
            body=raw.body,
            content_hash=raw.content_hash,
            order_index=raw.order_index,
            logical_key=raw.logical_key,
        )
        db.add(db_node)
        db.flush()  # get db_node.id without committing, so children can reference it
        raw_to_db[id(raw)] = db_node
        for c in raw.children:
            persist(c, db_node.id)

    persist(root, None)
    db.commit()
    db.refresh(doc_version)
    return doc_version


def find_node_by_logical_key(db: Session, document_version_id: int, logical_key: str) -> Node | None:
    return (
        db.query(Node)
        .filter(Node.document_version_id == document_version_id, Node.logical_key == logical_key)
        .first()
    )


def get_latest_version(db: Session, document_id: int) -> DocumentVersion | None:
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )


def diff_node_across_versions(db: Session, document_id: int, logical_key: str,
                               from_version_number: int, to_version_number: int) -> dict:
    """Lightweight diff summary for a single logical node between two versions."""
    from_dv = (db.query(DocumentVersion)
               .filter(DocumentVersion.document_id == document_id,
                       DocumentVersion.version_number == from_version_number).first())
    to_dv = (db.query(DocumentVersion)
             .filter(DocumentVersion.document_id == document_id,
                     DocumentVersion.version_number == to_version_number).first())
    if from_dv is None or to_dv is None:
        return {"error": "one or both versions not found"}

    from_node = find_node_by_logical_key(db, from_dv.id, logical_key)
    to_node = find_node_by_logical_key(db, to_dv.id, logical_key)

    if from_node is None and to_node is None:
        return {"status": "not_found_in_either_version"}
    if from_node is None:
        return {"status": "added_in_target_version", "logical_key": logical_key}
    if to_node is None:
        return {"status": "removed_in_target_version", "logical_key": logical_key}
    if from_node.content_hash == to_node.content_hash:
        return {"status": "unchanged", "logical_key": logical_key}
    return {
        "status": "changed",
        "logical_key": logical_key,
        "from_hash": from_node.content_hash,
        "to_hash": to_node.content_hash,
        # Deliberately NOT attempting a semantic diff (word-level, etc.) —
        # out of scope. This tells you THAT it changed, not how much it
        # matters. See staleness note in app/store.py.
    }