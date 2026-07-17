from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.llm import generate_test_cases
from app.models import Node  # Ensure SQLAlchemy Node is imported  # Core LLM call logic

# Import the standalone functions directly from your store module
from app.store import (
    save_generation,
    get_generation,
    get_generations_by_selection,
    find_existing_generation_for_selection
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/selections/{selection_id}/generate", tags=["Generation"])
def generate_qa_cases(selection_id: int, force_regenerate: bool = False, db: Session = Depends(get_db)):
    """
    Checks if a generation already exists for this selection. If yes (and force_regenerate is False),
    it immediately returns the cached copy. Otherwise, it calls the LLM, parses the structured output,
    and saves the new test cases.
    """
    try:
        # Respect the idempotent policy written in your store's find_existing_generation_for_selection
        if not force_regenerate:
            existing = find_existing_generation_for_selection(selection_id)
            if existing:
                return {
                    "status": "success",
                    "message": "Returned cached generation (idempotent policy). Use force_regenerate=True to bypass.",
                    "generation_id": existing["id"],
                    "test_cases": existing["test_cases"]
                }

        # Call your core LLM logic (passing your database session and your direct save_generation function)
        # Note: Depending on how your app/llm.py is structured, you might need to pass selection_id and db.
        generation_id = generate_test_cases(selection_id)
        
        return {
            "status": "success",
            "generation_id": generation_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/selections/{selection_id}/retrieval", tags=["Retrieval & Staleness"])
def retrieve_and_check_staleness(selection_id: int, db: Session = Depends(get_db)):
    """
    Fetches the generated test cases for this selection and runs a real-time 
    SHA-256 hash check against the active database nodes to identify any content drift.
    """
    try:
        generations = get_generations_by_selection(selection_id)
        if not generations:
            raise HTTPException(status_code=404, detail="No generated test cases found for this selection.")
        
        # Grab the latest generation record
        latest_gen = generations[-1]
        
        # Real-time Staleness Verification
        is_stale = False
        changes_diff = []
        
        # Import check function from versioning module
        from app.versioning import find_node_by_logical_key, get_latest_version
        
        # Find latest document version ID to compare against
        # (Assuming document_id can be inferred from the selection's nodes or you fall back to active checks)
        for snapshot in latest_gen["node_snapshot"]:
            logical_key = snapshot["logical_key"]
            original_hash = snapshot["content_hash"]
            
            # Query the database to find the node's current state
            # We look at the absolute latest nodes in the database to see if their hashes shifted
            current_node = db.query(Node).filter(Node.logical_key == logical_key).order_by(Node.id.desc()).first()
            
            if not current_node:
                is_stale = True
                changes_diff.append({"logical_key": logical_key, "status": "removed_from_document"})
            elif current_node.content_hash != original_hash:
                is_stale = True
                changes_diff.append({
                    "logical_key": logical_key, 
                    "status": "changed",
                    "previous_hash": original_hash,
                    "current_hash": current_node.content_hash
                })
        
        return {
            "selection_id": selection_id,
            "test_cases": latest_gen["test_cases"],
            "is_stale": is_stale,
            "changes_diff": changes_diff,
            "generated_at": latest_gen["created_at"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))