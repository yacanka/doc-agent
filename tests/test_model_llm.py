"""Tests for the local-only llama.cpp adapter."""
from __future__ import annotations

import pytest

from app.config import AppConfig
from app.model.llm import LocalLlm


def test_load_client_fails_clearly_when_model_missing(tmp_path) -> None:
    """Missing GGUF files fail before importing or calling llama.cpp."""
    config = AppConfig(model_path=tmp_path / "missing.gguf")

    with pytest.raises(FileNotFoundError, match="Local GGUF model file not found"):
        LocalLlm(config)._load_client()


def test_complete_uses_configured_generation_limits(tmp_path) -> None:
    """Inference uses local client settings from config.json fields."""
    model = tmp_path / "model.gguf"
    model.write_bytes(b"placeholder")
    llm = LocalLlm(AppConfig(model_path=model, temperature=0.2, max_tokens=32))
    llm._client = RecordingClient()

    assert llm._complete("prompt") == "done"
    assert llm._client.calls == [{"prompt": "prompt", "max_tokens": 32, "temperature": 0.2}]


class RecordingClient:
    """Minimal callable fake for llama_cpp.Llama."""

    def __init__(self) -> None:
        """Initialize call capture."""
        self.calls: list[dict] = []

    def __call__(self, prompt: str, max_tokens: int, temperature: float) -> dict:
        """Record completion arguments and return llama.cpp-like text."""
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})
        return {"choices": [{"text": "done"}]}
