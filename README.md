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

## Quick Start

1. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set your LLM API key

```bash
# PowerShell
$env:LLM_API_KEY="your_key_here"
```

4. Run the API locally

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/api/...

5. Or run the sample ingestion/generation workflow

```bash
python run.py
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
