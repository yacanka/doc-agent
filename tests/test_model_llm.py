"""Tests for the local-only GPT4All adapter."""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from app.config import AppConfig
from app.model.llm import LocalLlm, make_stop_callback


def test_load_client_fails_clearly_when_model_missing(tmp_path) -> None:
    """Missing GGUF files fail before importing or calling GPT4All."""
    config = AppConfig(model_path=tmp_path / "missing.gguf")

    with pytest.raises(FileNotFoundError, match="Local GGUF model file not found"):
        LocalLlm(config)._load_client()


def test_complete_uses_chat_session_streaming_and_generation_limits(tmp_path) -> None:
    """Inference uses chat_session, streaming, and controlled decoding settings."""
    model = tmp_path / "model.gguf"
    model.write_bytes(b"placeholder")
    llm = LocalLlm(AppConfig(model_path=model, temperature=0.2, max_tokens=32))
    llm._client = RecordingClient(["do", "ne"])

    assert llm._complete("prompt") == "done"
    assert llm._client.system_messages == [
        "You are a Turkish-speaking helpful assistant.\nAnswer the user's question directly.\nDo not add unnecessary detail.\nStop when the answer is complete."
    ]
    assert llm._client.calls == [
        {
            "prompt": "prompt",
            "max_tokens": 32,
            "temp": 0.2,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "repeat_last_n": 128,
            "streaming": True,
            "callback_provided": True,
        }
    ]


def test_stream_complete_hides_stop_texts(tmp_path) -> None:
    """Streaming output never exposes known chat-template sentinels."""
    model = tmp_path / "model.gguf"
    model.write_bytes(b"placeholder")
    llm = LocalLlm(AppConfig(model_path=model))
    llm._client = RecordingClient(["Merhaba", "<|im_end|>", "ignored"])

    assert list(llm.stream_complete("prompt")) == ["Merhaba"]


def test_stream_complete_hides_split_stop_texts(tmp_path) -> None:
    """Streaming output buffers sentinel prefixes until they are safe."""
    model = tmp_path / "model.gguf"
    model.write_bytes(b"placeholder")
    llm = LocalLlm(AppConfig(model_path=model))
    llm._client = RecordingClient(["Merhaba", "<|im", "_end|>", "ignored"])

    assert list(llm.stream_complete("prompt")) == ["Merhaba"]


def test_stop_callback_stops_on_known_sentinel() -> None:
    """Manual callback asks GPT4All to stop when sentinel text appears."""
    callback = make_stop_callback()

    assert callback(1, "Merhaba") is True
    assert callback(2, "<|im_end|>") is False


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
            "device": "cpu",
            "n_threads": 2,
            "n_ctx": 2048,
            "verbose": False,
        }
    ]


class RecordingClient:
    """Minimal fake for gpt4all.GPT4All."""

    def __init__(self, tokens: list[str]) -> None:
        """Initialize call capture."""
        self.calls: list[dict] = []
        self.tokens = tokens
        self.system_messages: list[str] = []

    @contextmanager
    def chat_session(self, system_message: str):
        """Record system prompt and emulate GPT4All chat session."""
        self.system_messages.append(system_message)
        yield

    def generate(self, prompt: str, **kwargs):
        """Record completion arguments and return GPT4All-like tokens."""
        self.calls.append({"prompt": prompt, "callback_provided": bool(kwargs.pop("callback")), **kwargs})
        yield from self.tokens
