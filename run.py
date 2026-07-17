"""Simple helper to ingest the CT-200 markdown and generate one test-case batch."""
from pathlib import Path

from app import __init__  # noqa: F401
from app.db import SessionLocal, init_db
from app.models import Node, Selection, SelectionNode
from app.store import get_generation
from app.versioning import ingest_document
from app.llm import generate_test_cases
from pypdf import PdfReader


def convert_pdf_to_markdown(pdf_path: Path, markdown_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    content = "\n\n".join(page.strip() for page in pages if page.strip())
    if not content:
        raise RuntimeError(f"Unable to extract text from PDF: {pdf_path}")

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Converted PDF to markdown: {markdown_path}")


def main():
    init_db()

    db = SessionLocal()

    markdown_path = Path("data/ct200_manual.md")
    pdf_path = Path("data/ct200_manual.pdf")

    if not markdown_path.exists():
        if pdf_path.exists():
            convert_pdf_to_markdown(pdf_path, markdown_path)
        else:
            raise SystemExit(
                f"Missing input: either {markdown_path} or {pdf_path} must exist."
            )

    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    doc_version = ingest_document(db, "CT-200 Manual", markdown_text)
    print(f"Ingested document version: {doc_version.version_number}")

    node = db.query(Node).first()
    if node is None:
        raise SystemExit("No nodes found after ingestion. Check the markdown file content.")

    selection = db.query(Selection).filter(Selection.name == "auto-generated-selection").first()
    if selection is None:
        selection = Selection(name="auto-generated-selection")
        db.add(selection)
        db.commit()
        db.refresh(selection)
        print(f"Created selection: {selection.id}")
    else:
        print(f"Using existing selection: {selection.id}")

    existing_link = db.query(SelectionNode).filter(
        SelectionNode.selection_id == selection.id,
        SelectionNode.node_id == node.id,
    ).first()
    if existing_link is None:
        db.add(SelectionNode(selection_id=selection.id, node_id=node.id))
        db.commit()
        print(f"Linked node {node.id} to selection {selection.id}")

    print(f"Generating test cases for node: {node.heading}")
    generation_id = generate_test_cases(selection.id, db=db)
    generation = get_generation(generation_id)
    print(f"Generated {len(generation['test_cases'])} test cases")
    print(f"Saved generation: {generation_id}")


if __name__ == "__main__":
    main()
