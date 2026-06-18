"""Tests for the local-only GPT4All adapter."""
from __future__ import annotations

import pytest

from app.config import AppConfig
from app.model.llm import LocalLlm


def test_load_client_fails_clearly_when_model_missing(tmp_path) -> None:
    """Missing GGUF files fail before importing or calling GPT4All."""
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
    assert llm._client.calls == [{"prompt": "prompt", "max_tokens": 32, "temp": 0.2}]


def test_load_client_initializes_gpt4all_without_download(tmp_path, monkeypatch) -> None:
    """GPT4All is initialized from the local model directory only."""
    model = tmp_path / "model.gguf"
    model.write_bytes(b"placeholder")
    calls = []

    class FakeGPT4All:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr("app.model.llm._gpt4all_class", lambda: FakeGPT4All)

    client = LocalLlm(AppConfig(model_path=model, context_size=2048, threads=2))._load_client()

    assert isinstance(client, FakeGPT4All)
    assert calls == [
        {
            "model_name": "model.gguf",
            "model_path": str(tmp_path),
            "allow_download": False,
            "n_threads": 2,
            "n_ctx": 2048,
            "device": "cpu",
            "verbose": False,
        }
    ]


class RecordingClient:
    """Minimal fake for gpt4all.GPT4All."""

    def __init__(self) -> None:
        """Initialize call capture."""
        self.calls: list[dict] = []

    def generate(self, prompt: str, max_tokens: int, temp: float) -> str:
        """Record completion arguments and return GPT4All-like text."""
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens, "temp": temp})
        return "done"
