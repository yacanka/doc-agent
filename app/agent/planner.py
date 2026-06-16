"""Operation planning service."""
from __future__ import annotations

from app.model.llm import LocalLlm


class Planner:
    """Create JSON replacement plans from document instructions."""

    def __init__(self, llm: LocalLlm) -> None:
        """Initialize with the local language model."""
        self.llm = llm

    def plan(self, instruction: str, document_text: str) -> dict[str, str]:
        """Plan safe literal replacements for a document."""
        replacements = self.llm.plan(instruction, document_text)
        if not replacements:
            raise ValueError("No replacements were planned")
        return replacements
