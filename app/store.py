"""
Store for LLM-generated test cases.

Uses a local JSON file instead of MongoDB. Justification (per the
assignment's "well-justified JSON store" allowance): a 2-3 day assignment
doesn't need a separate DB server to prove the storage design is sound —
what matters is that generations are (a) linked to the exact node content
they came from, in a way that (b) survives re-versioning. A flat JSON store
with those two properties demonstrates the same design as Mongo would;
swapping the backend later is a small, isolated change (this module is the
only place that would need to change).

Each generation record stores a `node_snapshot`: the logical_key + the
content_hash of every node it was generated from, AT GENERATION TIME. This
is what makes staleness detection possible later — we're not storing a
foreign key to a live Node row (which would just follow the node into its
current, possibly-changed state), we're storing a fact about the past.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STORE_PATH = Path(os.environ.get("GENERATION_STORE_PATH", "./generations.json"))


def _load() -> dict:
    if not STORE_PATH.exists():
        return {}
    with open(STORE_PATH, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def save_generation(selection_id: int, node_snapshot: list[dict], test_cases: list[dict],
                     status: str = "ok") -> str:
    """node_snapshot: [{"node_id": int, "logical_key": str, "content_hash": str}, ...]"""
    data = _load()
    gen_id = str(uuid.uuid4())
    data[gen_id] = {
        "id": gen_id,
        "selection_id": selection_id,
        "node_snapshot": node_snapshot,
        "test_cases": test_cases,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(data)
    return gen_id


def get_generation(gen_id: str) -> Optional[dict]:
    return _load().get(gen_id)


def get_generations_by_selection(selection_id: int) -> list[dict]:
    return [g for g in _load().values() if g["selection_id"] == selection_id]


def get_generations_by_node(node_id: int) -> list[dict]:
    out = []
    for g in _load().values():
        if any(s["node_id"] == node_id for s in g["node_snapshot"]):
            out.append(g)
    return out


def find_existing_generation_for_selection(selection_id: int) -> Optional[dict]:
    """Backs the idempotent-duplicate-submission policy: if a generation
    already exists for this selection, callers should return it instead of
    calling the LLM again, unless force_regenerate=True."""
    existing = get_generations_by_selection(selection_id)
    return existing[-1] if existing else None