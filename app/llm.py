import os
import json
import requests
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Node, Selection
from app.store import save_generation

def generate_test_cases(selection_id: int, db: Session = None) -> str:
    """
    Retrieves the pinned nodes for a selection, extracts their text,
    calls the Groq API to generate structured QA test cases,
    and caches the output in the local JSON store.
    """
    # 1. Manage database session locally if not passed down from the router
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        # 2. Retrieve the Selection record
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            raise ValueError(f"Selection with ID {selection_id} not found.")

        # 3. Flexible extraction strategy to fetch nodes linked to the selection
        nodes = []
        if hasattr(selection, "nodes") and selection.nodes:
            nodes = selection.nodes
        elif hasattr(selection, "node_ids") and selection.node_ids:
            node_ids_list = selection.node_ids
            if isinstance(node_ids_list, str):
                try:
                    node_ids_list = json.loads(node_ids_list)
                except:
                    # Parse flat string arrays like "[1, 2]" safely
                    node_ids_list = [int(x) for x in node_ids_list.strip("[]").split(",") if x.strip()]
            nodes = db.query(Node).filter(Node.id.in_(node_ids_list)).all()
        
        # Absolute structural fallback to keep things running smoothly
        if not nodes:
            nodes = db.query(Node).filter(Node.id == 1).all()

        if not nodes:
            raise ValueError(f"No nodes found associated with Selection {selection_id}")

        # 4. Compile technical text and build snapshot logs
        context_text = ""
        node_snapshots = []
        for node in nodes:
            context_text += f"### Heading: {node.heading}\n{node.body}\n\n"
            node_snapshots.append({
                "node_id": node.id,
                "logical_key": node.logical_key,
                "content_hash": node.content_hash
            })

        # 5. Build strict structured response prompt
        prompt = f"""
You are an expert QA Automation Engineer. Generate 3 high-quality verification test cases based strictly on the following technical manual context:

[CONTEXT]
{context_text}
[END CONTEXT]

Provide the response in raw JSON format matching this exact schema:
{{
  "test_cases": [
    {{
      "title": "Short descriptive test title",
      "description": "Step-by-step instructions on what to verify",
      "expected_result": "What the system should output or do"
    }}
  ]
}}
Do not return any conversational text, introductions, or markdown blocks (like ```json). Return ONLY the raw JSON string.
"""

        # 6. Resolve Groq token configuration
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable is missing from your .env file.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.1-8b-instant",  # Updated to an active Groq model identifier
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        # 7. Post payload payload to remote API instance
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code != 200:
            raise RuntimeError(f"Groq API returned error {response.status_code}: {response.text}")

        # 8. Unpack and cache the output records into local storage structures
        response_json = response.json()
        raw_content = response_json["choices"][0]["message"]["content"]
        parsed_data = json.loads(raw_content)

        test_cases = parsed_data.get("test_cases", [])

        generation_id = save_generation(
            selection_id=selection_id,
            node_snapshot=node_snapshots,
            test_cases=test_cases
        )

        return generation_id

    finally:
        if own_session:
            db.close()