"""API request and response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Question payload for a document session."""

    question: str = Field(min_length=1, max_length=2000)


class PlanRequest(BaseModel):
    """Natural-language edit instruction payload."""

    instruction: str = Field(min_length=1, max_length=2000)


class ApplyRequest(BaseModel):
    """Literal replacement payload for deterministic DOCX edits."""

    replacements: dict[str, str] = Field(min_length=1)
