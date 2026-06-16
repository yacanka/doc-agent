"""llama-cpp-python adapter with deterministic local inference."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.model.prompts import planning_prompt, qa_prompt


class LocalLlm:
    """Lazy llama.cpp wrapper for QA and operation planning."""

    def __init__(self, config: AppConfig) -> None:
        """Store configuration and defer model loading until first use."""
        self.config = config
        self._client: Any | None = None

    def answer(self, question: str, document_text: str) -> str:
        """Answer a question from document text using the local model."""
        return self._complete(qa_prompt(question, document_text)).strip()

    def plan(self, instruction: str, document_text: str) -> dict[str, str]:
        """Return literal text replacements planned by the local model."""
        text = self._complete(planning_prompt(instruction, document_text))
        payload = json.loads(_json_object(text))
        replacements = payload.get("replacements", {})
        if not isinstance(replacements, dict):
            raise ValueError("Planner returned invalid replacements")
        return {str(key): str(value) for key, value in replacements.items()}

    def _complete(self, prompt: str) -> str:
        client = self._load_client()
        result = client(prompt, max_tokens=512, temperature=self.config.llm_temperature)
        return result["choices"][0]["text"]

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not Path(self.config.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.config.model_path}")
        from llama_cpp import Llama

        self._client = Llama(model_path=str(self.config.model_path), n_ctx=self.config.llm_context_size)
        return self._client


def _json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Planner did not return JSON")
    return text[start : end + 1]
