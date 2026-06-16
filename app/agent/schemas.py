"""API and agent operation schemas."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionRequest(BaseModel):
    """Question payload for a document session."""

    question: str = Field(min_length=1, max_length=2000)


class PlanRequest(BaseModel):
    """Natural-language edit instruction payload."""

    instruction: str = Field(min_length=1, max_length=2000)


class ApplyRequest(BaseModel):
    """Literal replacement payload for deterministic DOCX edits."""

    replacements: dict[str, str] = Field(min_length=1)


class ChatMode(StrEnum):
    """Supported conversational modes for document sessions."""

    QUESTION = "question"
    PLAN = "plan"
    EXECUTE = "execute"


class RiskLevel(StrEnum):
    """Risk classification for a planned document operation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class ToolName(StrEnum):
    """Approved Python tool entry points exposed to the executor."""

    WORD_REPLACE_TEXT = "word.replace_text"
    VALIDATE_REPLACEMENTS = "validation.validate_replacements"


class DocumentOperation(BaseModel):
    """Validated operation requested by the planner."""

    action: Literal["replace_text", "validate_replacements"]
    tool: ToolName
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk: RiskLevel = RiskLevel.LOW

    @model_validator(mode="after")
    def validate_operation_contract(self) -> "DocumentOperation":
        """Ensure the action, tool, and parameters form an approved contract."""
        if self.action == "replace_text":
            self._validate_replace_text()
        if self.action == "validate_replacements" and self.tool != ToolName.VALIDATE_REPLACEMENTS:
            raise ValueError("Validation actions must use the validation tool")
        if self.risk == RiskLevel.DESTRUCTIVE:
            raise ValueError("Destructive document operations are not supported")
        return self

    def _validate_replace_text(self) -> None:
        if self.tool != ToolName.WORD_REPLACE_TEXT:
            raise ValueError("Replacement actions must use the Word replacement tool")
        replacements = self.parameters.get("replacements")
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError("Replacement actions require non-empty replacements")
        if any(not str(source).strip() for source in replacements):
            raise ValueError("Replacement sources must be explicit")


class OperationPlan(BaseModel):
    """Structured, validated plan produced from an LLM response."""

    mode: ChatMode = ChatMode.PLAN
    operations: list[DocumentOperation] = Field(min_length=1)
    summary: str = Field(default="", max_length=500)
    risk: RiskLevel = RiskLevel.LOW

    @field_validator("risk")
    @classmethod
    def reject_destructive_plan(cls, value: RiskLevel) -> RiskLevel:
        """Reject plans globally marked as destructive."""
        if value == RiskLevel.DESTRUCTIVE:
            raise ValueError("Destructive plans are not supported")
        return value


class ExecutionResult(BaseModel):
    """Result returned after approved Python tools execute a plan."""

    output_path: str
    report_path: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)
    changed_count: int = Field(ge=0)
    operations_executed: int = Field(ge=0)
