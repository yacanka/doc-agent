"""Tests for strict model prompt contracts."""
from __future__ import annotations

from app.model.prompts import planning_prompt, qa_prompt


def test_qa_prompt_requires_question_mode() -> None:
    """Question prompts require the plain-text question response mode."""
    prompt = qa_prompt("What is due?", "Payment is due Friday.")

    assert "Required mode: question" in prompt
    assert "exactly one mode" in prompt
    assert "I do not know" in prompt


def test_planning_prompt_requires_apply_request_json() -> None:
    """Operation prompts require strict ApplyRequest-compatible JSON."""
    prompt = planning_prompt("Replace Friday with Monday", "Payment is due Friday.")

    assert "Required mode: operation" in prompt
    assert "app.agent.schemas.ApplyRequest" in prompt
    assert '{"replacements":{"existing document text":"replacement text"}}' in prompt
