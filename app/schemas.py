from typing import Optional
from pydantic import BaseModel, Field, field_validator


class NodeOut(BaseModel):
    id: int
    heading: str
    level: int
    body: str
    content_hash: str
    logical_key: str
    parent_id: Optional[int]
    skipped_level: bool = False

    class Config:
        from_attributes = True


class NodeSummary(BaseModel):
    id: int
    heading: str
    level: int
    logical_key: str

    class Config:
        from_attributes = True


class SelectionCreate(BaseModel):
    name: str
    node_ids: list[int] = Field(..., min_length=1)


class SelectionOut(BaseModel):
    id: int
    name: str
    node_ids: list[int]


class GenerateRequest(BaseModel):
    selection_id: int
    force_regenerate: bool = False


# --- LLM structured-output contract ---
# This is what we require the model's JSON response to conform to.
# Anything that doesn't validate against this triggers the retry/fail policy
# in app/llm.py — we never silently accept a malformed shape.

class TestCaseIdea(BaseModel):
    title: str
    steps: str = Field(..., description="Concrete, executable steps")
    expected_result: str

    @field_validator("title", "steps", "expected_result")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field must not be blank")
        return v


class LLMTestCaseResponse(BaseModel):
    test_cases: list[TestCaseIdea] = Field(..., min_length=3, max_length=5)