# CT-200 Medical Device QA Test Case Generator

A robust system for automatically generating QA test cases from medical device requirement documents using LLM-powered generation with structured output validation.

## Project Overview

CT-200 System is an intelligent document processing and test case generation platform that:

- **Ingests** medical device requirement documents in markdown format
- **Parses** documents into hierarchical tree structures with intelligent handling of document irregularities
- **Tracks** document versions and maintains cross-version compatibility
- **Generates** QA test cases using LLM with strict validation and retry mechanisms
- **Stores** all test case generations with timestamps and status tracking
- **Validates** all LLM output against strict Pydantic schemas

## Key Features

### Document Management
- **Hierarchical Parsing**: Converts markdown documents into structured node trees
- **Version Control**: Maintains multiple document versions with proper linking
- **Logical Key Matching**: Intelligent cross-version node matching using heading paths
- **Edge Case Handling**: 
  - Duplicate headings under same parent (disambiguated with #2, #3 suffixes)
  - Skipped heading levels (automatically attached to nearest valid ancestor)
  - Empty sections (preserved as valid nodes)
  - Preamble content before first heading

### LLM Integration
- **Structured Output**: Enforces JSON schema compliance from LLM responses
- **Validation Pipeline**: Two-stage validation with Pydantic models
- **Retry Logic**: Single retry with explicit error feedback before failure
- **Error Handling**: Captures and stores raw output on validation failure
- **Flexible Provider Support**: Currently uses Groq's OpenAI-compatible endpoint (easily swappable)

### Data Storage
- **SQLite Database**: Persistent storage of documents, versions, nodes, and selections
- **JSON Generation Store**: Local file-based storage of test case generations with snapshots
- **Staleness Detection**: Content hashing enables detection of modified nodes

## Project Structure

```
ct200-system/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── db.py                    # SQLite engine and session setup
│   ├── models.py                # SQLAlchemy ORM models
│   ├── schemas.py               # Pydantic validation schemas
│   ├── parser.py                # Markdown to tree parser
│   ├── versioning.py            # Document versioning and matching
│   ├── llm.py                   # LLM integration with retry logic
│   ├── store.py                 # Test case generation storage
│   └── routers/
│       ├── browse.py            # Document browsing endpoints
│       └── selection.py          # Selection management endpoints
├── data/                         # Document storage
├── tests/                        # Test suite
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── .gitignore                    # Git ignore patterns
```

## Core Components

### 1. **Database Models** (`models.py`)
- `Document`: Logical document entity (e.g., "CT-200 Manual")
- `DocumentVersion`: Versioned snapshot of a document
- `Node`: Individual sections/headings within a document version
- `Selection`: Named collection of nodes for test case generation
- `SelectionNode`: Join table linking selections to nodes

### 2. **Parser** (`parser.py`)
Converts markdown into a tree structure with:
- Smart heading-level handling
- Duplicate heading disambiguation
- Skipped level detection
- Content hashing for change detection

### 3. **Versioning** (`versioning.py`)
- Cross-version node matching via logical keys
- Document re-ingestion without version deletion
- Staleness detection for modified content

### 4. **LLM Integration** (`llm.py`)
- Template-based prompt construction
- JSON extraction with markdown fence handling
- Single-retry validation with error feedback
- Graceful failure with raw output preservation

### 5. **Storage** (`store.py`)
- Local JSON file storage for test case generations
- Node snapshots for staleness detection
- Status tracking (ok, failed, etc.)
- Query methods for finding generations by selection or node

## Installation

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or navigate to the project directory**:
   ```bash
   cd ct200-system
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```bash
   # LLM API Configuration
   LLM_API_KEY=your_groq_api_key_here
   
   # (Optional) Custom generation store path
   GENERATION_STORE_PATH=./generations.json
   ```

5. **Initialize the database**:
   ```bash
   python -c "from app.db import init_db; init_db()"
   ```

## Usage

### 1. Import and Initialize Database
```python
from app.db import SessionLocal, init_db
from app.versioning import ingest_document, get_or_create_document

# Initialize database tables
init_db()

# Get database session
db = SessionLocal()
```

### 2. Ingest a Document
```python
# Read your markdown file
with open("data/ct200_manual.md", "r") as f:
    markdown_text = f.read()

# Ingest as new version
doc_version = ingest_document(db, "CT-200 Manual", markdown_text)
print(f"Ingested version {doc_version.version_number}")
```

### 3. Query Nodes
```python
from app.models import Node

# Get all nodes from a version
nodes = db.query(Node).filter(
    Node.document_version_id == doc_version.id
).all()

for node in nodes:
    print(f"{node.heading} (level {node.level}): {node.logical_key}")
```

### 4. Create a Selection
```python
from app.models import Selection, SelectionNode

selection = Selection(name="CT-200 Alarms Section")
db.add(selection)
db.commit()

# Add nodes to selection
for node_id in [1, 2, 3]:  # Example node IDs
    link = SelectionNode(selection_id=selection.id, node_id=node_id)
    db.add(link)
db.commit()
```

### 5. Generate Test Cases
```python
from app.llm import generate_test_cases
from app.store import save_generation

# Get selected nodes' content
selection_nodes = db.query(SelectionNode).filter(
    SelectionNode.selection_id == selection.id
).all()

node_ids = [sn.node_id for sn in selection_nodes]
nodes = db.query(Node).filter(Node.id.in_(node_ids)).all()

# Combine content
combined_text = "\n\n".join(
    f"# {node.heading}\n{node.body}" for node in nodes
)

try:
    # Generate test cases
    test_cases = generate_test_cases(combined_text)
    
    # Store generation with node snapshot
    node_snapshot = [
        {
            "node_id": node.id,
            "logical_key": node.logical_key,
            "content_hash": node.content_hash
        }
        for node in nodes
    ]
    
    gen_id = save_generation(
        selection_id=selection.id,
        node_snapshot=node_snapshot,
        test_cases=test_cases,
        status="ok"
    )
    print(f"Generated test cases (ID: {gen_id})")
    
except Exception as e:
    gen_id = save_generation(
        selection_id=selection.id,
        node_snapshot=node_snapshot,
        test_cases=[],
        status=f"failed: {str(e)}"
    )
    print(f"Generation failed (ID: {gen_id})")
```

### 6. Retrieve Generations
```python
from app.store import get_generation, get_generations_by_selection, find_existing_generation_for_selection

# Get all generations for a selection
gens = get_generations_by_selection(selection_id=1)

# Check for existing generation (idempotent checking)
existing = find_existing_generation_for_selection(selection_id=1)
if existing:
    print(f"Found existing generation: {existing['id']}")

# Get specific generation
gen = get_generation(gen_id)
print(f"Status: {gen['status']}")
print(f"Test Cases: {len(gen['test_cases'])}")
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for LLM provider (Groq) | Required |
| `GENERATION_STORE_PATH` | Path to JSON store for generations | `./generations.json` |

### Database

- **Type**: SQLite (no server setup required)
- **File**: `ct200.db` (created automatically in project root)
- **Connection String**: `sqlite:///./ct200.db`

## API Endpoints (Planned)

The routers directory contains two planned endpoint groups:

### Browse Endpoints (`routers/browse.py`)
- GET `/documents` - List all documents
- GET `/documents/{id}/versions` - List versions of a document
- GET `/versions/{id}/nodes` - Browse nodes in a version
- GET `/nodes/{id}` - Get node details

### Selection Endpoints (`routers/selection.py`)
- POST `/selections` - Create a new selection
- GET `/selections/{id}` - Get selection details
- POST `/selections/{id}/generate` - Generate test cases
- GET `/generations/{id}` - Get generation results

## Development

### Running Tests
```bash
# From the project root
python -m pytest tests/ -v
```

### Common Tasks

**Create tables from scratch**:
```bash
python -c "from app.db import init_db; init_db()"
```

**View database**:
```bash
# Using sqlite3 command line
sqlite3 ct200.db

# Inside SQLite:
.tables
SELECT name FROM sqlite_master WHERE type='table';
```

**Clear database** (WARNING: deletes all data):
```bash
rm ct200.db
python -c "from app.db import init_db; init_db()"
```

## Design Decisions

### Why SQLite?
A 2-3 day assignment doesn't require a separate database server. SQLite demonstrates the storage design is sound while eliminating deployment complexity.

### Why JSON for Generations?
Generations are immutable snapshots with their exact source nodes. A flat JSON store avoids foreign key complexity while preserving the design that could swap to MongoDB later (only `store.py` would change).

### Why Path-Based Node Matching?
- **Not hash-based**: Fails when body text changes (the change we most want to detect)
- **Not fuzzy-matching**: Can silently merge genuinely different sections
- **Path-based**: Simple, deterministic, with clear failure modes (breaks only on heading rename)

### Why Single Retry for LLM?
One malformed response is often transient (extra prose, trailing comma). A second consecutive failure after explicit correction is likely a real capability problem. More retries waste tokens.

## Troubleshooting

### "LLM_API_KEY not set"
Set the environment variable:
```bash
# On Windows (PowerShell)
$env:LLM_API_KEY="your_key"

# On Windows (cmd)
set LLM_API_KEY=your_key

# On macOS/Linux
export LLM_API_KEY="your_key"
```

### Database locked error
Close all other connections to `ct200.db` (check other Python processes, sqlite3 shells, etc.)

### LLMGenerationError - failed validation twice
The LLM is unable to produce valid JSON after a retry. Check:
- API key validity
- Rate limiting (add delays between requests)
- Model availability (confirm Groq endpoint is up)
- The raw output is stored for debugging

### Duplicate logical keys
This should not happen. If it does, check:
- Node creation order in parser
- Document parsing for duplicate heading detection

## Future Enhancements

1. **FastAPI Server**: Full REST API implementation for routers
2. **Fuzzy Matching Secondary Pass**: For renamed nodes with similar body text
3. **MongoDB Backend**: Swap `store.py` to use MongoDB for scalability
4. **Web UI**: Dashboard for document browsing and selection management
5. **Batch Processing**: Queue system for large document ingestions
6. **Metrics**: Track generation success rates and LLM performance

## License

[Add your license here]

## Support

For issues or questions:
1. Check `ct200.db` for data consistency
2. Review `generations.json` for generation history
3. Check `.env` file for missing configuration
4. Run tests: `python -m pytest tests/ -v`
