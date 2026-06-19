"""GPT4All adapter with deterministic local inference."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

from app.config import AppConfig
from app.model.prompts import planning_prompt, qa_prompt

SYSTEM_PROMPT = """
You are a Turkish-speaking helpful assistant.
Answer the user's question directly.
Do not add unnecessary detail.
Stop when the answer is complete.
""".strip()

STOP_TEXTS = ("<|im_end|>", "<|endoftext|>", "\n<|im_start|>user", "\nUser:", "\nKullanıcı:")


class StopCallback(Protocol):
    """GPT4All callback signature used to stop unsafe generations."""

    def __call__(self, token_id: int, token: str) -> bool:
        """Return False when generation should stop."""


class LocalLlm:
    """Lazy GPT4All wrapper for local-only QA and operation planning."""

    def __init__(self, config: AppConfig) -> None:
        """Store configuration and defer model loading until first use."""
        self.config = config
        self._client: Any | None = None

    def answer(self, question: str, document_text: str) -> str:
        """Answer a document question using only the local GGUF model."""
        return self._complete(qa_prompt(question, document_text)).strip()

    def plan(self, instruction: str, document_text: str) -> dict[str, str]:
        """Return literal text replacements planned by the local GGUF model."""
        payload = json.loads(_json_object(self._complete(planning_prompt(instruction, document_text))))
        replacements = payload.get("replacements", {})
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError("Planner returned invalid replacements JSON")
        return {str(key): str(value) for key, value in replacements.items()}

    def complete(self, prompt: str) -> str:
        """Return raw model text for a trusted server-built prompt."""
        return self._complete(prompt)

    def stream_complete(self, prompt: str) -> Iterator[str]:
        """Yield cleaned model tokens from a GPT4All chat session."""
        yield from self._stream_complete(prompt)

    def _complete(self, prompt: str) -> str:
        return "".join(self._stream_complete(prompt))

    def _stream_complete(self, prompt: str) -> Iterator[str]:
        client = self._load_client()
        callback = make_stop_callback()
        with client.chat_session(system_message=SYSTEM_PROMPT):
            stream = client.generate(prompt, streaming=True, callback=callback, **self._generation_options())
            yield from _visible_tokens(stream)

    def _generation_options(self) -> dict[str, float | int]:
        return {
            "max_tokens": self.config.max_tokens,
            "temp": self.config.temperature,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "repeat_last_n": 128,
        }

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        model_path = Path(self.config.model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"Local GGUF model file not found: {model_path}")
        self._client = _new_gpt4all_client(model_path, self.config)
        return self._client


def make_stop_callback() -> StopCallback:
    """Create a GPT4All callback that stops on known chat-template sentinels."""
    buffer = ""

    def callback(token_id: int, token: str) -> bool:
        nonlocal buffer
        buffer += token
        return not any(stop_text in buffer for stop_text in STOP_TEXTS)

    return callback


def _visible_tokens(stream: Iterator[str]) -> Iterator[str]:
    buffer = ""
    for token in stream:
        buffer += token
        stop_index = _first_stop_index(buffer)
        if stop_index >= 0:
            yield from _non_empty(buffer[:stop_index])
            return
        visible, buffer = _split_visible_buffer(buffer)
        yield from _non_empty(visible)
    yield from _non_empty(buffer)


def _first_stop_index(text: str) -> int:
    indexes = [text.find(stop_text) for stop_text in STOP_TEXTS if stop_text in text]
    return min(indexes) if indexes else -1


def _split_visible_buffer(buffer: str) -> tuple[str, str]:
    hold_length = max(_stop_prefix_length(buffer, stop_text) for stop_text in STOP_TEXTS)
    if hold_length == 0:
        return buffer, ""
    return buffer[:-hold_length], buffer[-hold_length:]


def _stop_prefix_length(buffer: str, stop_text: str) -> int:
    max_length = min(len(buffer), len(stop_text) - 1)
    for length in range(max_length, 0, -1):
        if buffer.endswith(stop_text[:length]):
            return length
    return 0


def _non_empty(text: str) -> Iterator[str]:
    if text:
        yield text


def _new_gpt4all_client(model_path: Path, config: AppConfig) -> Any:
    return _gpt4all_class()(
        model_name=model_path.name,
        model_path=str(model_path.parent),
        allow_download=False,
        device="cpu",
        n_threads=config.threads,
        n_ctx=config.context_size,
        verbose=False,
    )


def _json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Planner did not return JSON")
    return text[start : end + 1]


def _gpt4all_class() -> Any:
    """Return the GPT4All class only when model loading is required."""
    from gpt4all import GPT4All

    return GPT4All
