"""Operation planning service with strict LLM response validation."""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agent.schemas import OperationPlan, RiskLevel, ToolName
from app.model.llm import LocalLlm
from app.model.prompts import planning_prompt

_DESTRUCTIVE_TERMS = ("delete", "remove", "erase", "wipe", "drop", "destroy", "clear")
_VAGUE_TARGETS = ("all", "everything", "content", "document", "file", "it", "this")


class Planner:
    """Create and validate safe document operation plans."""

    def __init__(self, llm: LocalLlm) -> None:
        """Initialize with the local language model."""
        self.llm = llm

    def plan(self, instruction: str, document_text: str) -> dict[str, str]:
        """Plan safe literal replacements for legacy callers."""
        plan = self.plan_operations(instruction, document_text)
        return _replacements_from_plan(plan)

    def plan_operations(self, instruction: str, document_text: str) -> OperationPlan:
        """Return a validated operation plan for a natural-language instruction."""
        _reject_vague_destructive_instruction(instruction)
        response = self._planning_response(instruction, document_text)
        return self.parse_response(response)

    def _planning_response(self, instruction: str, document_text: str) -> str | dict[str, Any]:
        """Get the rawest available planning response from the LLM adapter."""
        if hasattr(self.llm, "complete"):
            return self.llm.complete(planning_prompt(instruction, document_text))
        return self.llm.plan(instruction, document_text)

    def parse_response(self, response: str | dict[str, Any]) -> OperationPlan:
        """Parse and validate an LLM response as an operation plan."""
        payload = _decode_response(response)
        if "replacements" in payload and "operations" not in payload:
            payload = _legacy_replacement_payload(payload)
        try:
            return OperationPlan.model_validate(payload)
        except ValidationError as error:
            raise ValueError(f"Invalid operation plan: {error}") from error


def _decode_response(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError("Planner response must be valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("Planner response must be a JSON object")
    return payload


def _legacy_replacement_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "operations": [{"action": "replace_text", "tool": ToolName.WORD_REPLACE_TEXT, "parameters": payload}],
        "risk": RiskLevel.LOW,
    }


def _replacements_from_plan(plan: OperationPlan) -> dict[str, str]:
    for operation in plan.operations:
        if operation.action == "replace_text":
            replacements = operation.parameters["replacements"]
            return {str(key): str(value) for key, value in replacements.items()}
    raise ValueError("No replacement operation was planned")


def _reject_vague_destructive_instruction(instruction: str) -> None:
    words = instruction.lower().replace(".", " ").replace(",", " ").split()
    if not any(term in words for term in _DESTRUCTIVE_TERMS):
        return
    if any(target in words for target in _VAGUE_TARGETS):
        raise ValueError("Vague destructive requests are not supported")
