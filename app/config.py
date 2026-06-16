"""Application configuration and workspace bootstrap."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class AppConfig(BaseModel):
    """Validated local runtime settings loaded from config.json."""

    host: str = "127.0.0.1"
    port: int = 8000
    model_path: Path = Path("models/model.gguf")
    workspace_root: Path = Path("workspace")
    max_upload_mb: int = Field(default=25, gt=0, le=200)
    context_size: int = Field(
        default=4096, gt=512, validation_alias=AliasChoices("context_size", "llm_context_size")
    )
    threads: int = Field(default=4, gt=0)
    temperature: float = Field(
        default=0.1, ge=0.0, le=1.0, validation_alias=AliasChoices("temperature", "llm_temperature")
    )
    max_tokens: int = Field(default=512, gt=0)

    @property
    def originals_dir(self) -> Path:
        """Return the immutable upload directory."""
        return self.workspace_root / "originals"

    @property
    def working_dir(self) -> Path:
        """Return the session working directory."""
        return self.workspace_root / "working"

    @property
    def outputs_dir(self) -> Path:
        """Return the generated outputs directory."""
        return self.workspace_root / "outputs"

    @property
    def audit_log_path(self) -> Path:
        """Return the JSONL audit log path."""
        return self.workspace_root / "audit.log"


def load_config(path: str | Path = "config.json") -> AppConfig:
    """Load local configuration from JSON, falling back to safe defaults."""
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig(**data)


def ensure_workspace(config: AppConfig) -> None:
    """Create workspace directories required by the application."""
    directories = [config.originals_dir, config.working_dir, config.outputs_dir]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    config.audit_log_path.parent.mkdir(parents=True, exist_ok=True)


def public_config(config: AppConfig) -> dict[str, Any]:
    """Return non-sensitive configuration values for health endpoints."""
    return {
        "host": config.host,
        "port": config.port,
        "workspace_root": str(config.workspace_root),
        "model_path": str(config.model_path),
    }
