# CT-200 Medical Device QA Test Case Generator

A Python-based project for processing medical device requirement documents and generating QA test cases with the support of large language models.

## Project Overview

This system is designed to transform technical requirement content into structured, testable information. It supports:

- ingestion of Markdown and PDF-based requirement documents
- parsing of document content into a hierarchical section structure
- version-aware tracking of document changes
- selection of relevant sections for test-case generation
- validation of LLM-generated output using structured schemas

The project demonstrates an end-to-end workflow for document understanding, content organization, and automated QA generation.

## Key Features

- Parses requirement documents into a tree of sections and nodes
- Tracks document versions and detects stale or modified content
- Allows users to create selections of relevant sections
- Generates QA test cases using an LLM with validation checks
- Stores generation history locally for traceability
- Exposes the workflow through a FastAPI-based service

## Project Structure

```text
ct200-system/
├── app/
│   ├── db.py
│   ├── llm.py
│   ├── main.py
│   ├── models.py
│   ├── parser.py
│   ├── schemas.py
│   ├── store.py
│   ├── versioning.py
│   └── routers/
├── data/
├── tests/
├── requirements.txt
├── run.py
└── README.md
```

## Main modules and usage

This section describes the main code components, what they do, and how to use them directly (outside the API) for quick experimentation.

- app/main.py
  - The FastAPI application entrypoint. It wires routers, sets up startup/shutdown events, and initializes the SQLite database.
  - Run locally: `uvicorn app.main:app --reload`
  - Intended to be lightweight; most business logic is in the modules described below.

- app/parser.py
  - Responsible for ingesting documents (Markdown, PDF) and converting them into a hierarchical document/section tree.
  - Typical functions: `parse_markdown(path)`, `parse_pdf(path)` (naming may vary; check function names in the file).
  - Example (Python REPL):
    ```python
    from app.parser import parse_markdown
    doc = parse_markdown("data/requirements.md")
    for sec in doc.sections:
        print(sec.title)
    ```

- app/llm.py
  - Encapsulates calls to the LLM service. Reads API key from environment (e.g., `LLM_API_KEY`).
  - Provides helpers to build prompts, call the model, and run schema validation on responses.
  - Example:
    ```python
    from app.llm import LLMClient
    client = LLMClient(api_key=os.getenv("LLM_API_KEY"))
    result = client.generate_tests(prompt_text, schema=True)
    print(result.validated_output)
    ```

- app/store.py
  - Manages persistence for generation outputs and local history (e.g., `generations.json`, SQLite tables).
  - Typical operations: `save_generation(selection_id, output)`, `get_generations(selection_id)`.

- app/versioning.py
  - Tracks document versions and detects changes between ingestions.
  - Use to mark sections as stale or updated when documents change.

- app/db.py / app/models.py / app/schemas.py
  - `db.py` sets up the SQLAlchemy/SQLite connection and session management.
  - `models.py` contains the ORM models for documents, nodes, selections, and generations.
  - `schemas.py` holds Pydantic models used by the API and for validation.

- app/routers/
  - Contains route definitions (ingest, documents, nodes, selections, generate).
  - Check individual routers to see expected request/response shapes.

- run.py
  - A small script that demonstrates the end-to-end ingestion → selection → generation flow.
  - Use it as an example to see how modules interact if you prefer CLI usage over the API.

## Quick Start

1. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set your LLM API key

```bash
# PowerShell
$env:LLM_API_KEY="your_key_here"
# macOS / Linux
export LLM_API_KEY="your_key_here"
```

4. Run the API locally

```bash
uvicorn app.main:app --reload
```

5. run the sample ingestion/generation workflow

```bash
python run.py
```

## Usage examples (API)

Basic curl examples to exercise the main endpoints.

- Ingest a document (multipart form upload):

```bash
curl -X POST "http://localhost:8000/api/ingest" \
  -F "file=@data/requirements.md" \
  -H "Accept: application/json"
```

- List sections of a document:

```bash
curl "http://localhost:8000/api/documents/requirements.md/sections"
```

- Get a node and its children:

```bash
curl "http://localhost:8000/api/nodes/123"
curl "http://localhost:8000/api/nodes/123/children"
```

- Create a selection (example JSON body):

```bash
curl -X POST "http://localhost:8000/api/selections" \
  -H "Content-Type: application/json" \
  -d '{
    "document_name": "requirements.md",
    "selected_node_ids": [12, 45, 78],
    "metadata": {"owner":"qa-team"}
  }'
```

- Generate test cases from a selection:

```bash
curl -X POST "http://localhost:8000/api/selections/<selection_id>/generate"
```

- Retrieve generation history / retrieval results:

```bash
curl "http://localhost:8000/api/selections/<selection_id>/retrieval"
```

## Usage examples (Python client)

Simple Python flow using requests:

```python
import requests

# Ingest
files = {"file": open("data/requirements.md", "rb")}
r = requests.post("http://localhost:8000/api/ingest", files=files)
print(r.json())

# Create a selection (example)
sel = requests.post("http://localhost:8000/api/selections", json={
    "document_name": "requirements.md",
    "selected_node_ids": [1, 2, 3]
}).json()

# Generate
gen = requests.post(f"http://localhost:8000/api/selections/{sel['id']}/generate")
print(gen.json())
```

## Demo Flow

A typical workflow is as follows:

1. Place a requirement document in the data folder.
2. Start the application or run the sample script.
3. Ingest the document and select the relevant section.
4. Generate QA test cases from the chosen content.

This process creates a local database entry and stores generation output for future reference.

## API Endpoints

The current FastAPI app exposes these main routes:

- POST /api/ingest
- GET /api/documents/{document_name}/sections
- GET /api/nodes/{node_id}
- GET /api/nodes/{node_id}/children
- GET /api/documents/{document_name}/search
- GET /api/nodes/{node_id}/diff
- POST /api/selections
- GET /api/selections/{selection_id}
- POST /api/selections/{selection_id}/generate
- GET /api/selections/{selection_id}/retrieval

## Data Files

- SQLite database: ct200.db
- Generation history: generations.json
- Sample documents: data/

## Development

Run tests with:

```bash
python -m pytest tests/ -v
```

## Notes

- The database is created automatically when the application starts.
- Generation outputs are stored locally for traceability.
- If the LLM response is invalid, the system retries and preserves the raw output for debugging.

## License

This project is currently unlicensed. A license may be added before public distribution.
