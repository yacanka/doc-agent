"""Backup and working-copy management for uploaded documents."""
from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def copy_file(source: Path, destination: Path) -> Path:
    """Copy a file after ensuring the destination directory exists."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def store_original(upload_path: Path, workspace_root: Path, session_id: str) -> Path:
    """Copy an uploaded original into workspace/originals without overwriting it."""
    destination = _session_path(workspace_root, "originals", session_id, upload_path.name)
    if destination.exists():
        raise FileExistsError(f"Original already exists: {destination}")
    return copy_file(upload_path, destination)


def create_working_copy(original_path: Path, workspace_root: Path, session_id: str) -> Path:
    """Create or replace the current working copy from an immutable original."""
    destination = _session_path(workspace_root, "working", session_id, original_path.name)
    return copy_file(original_path, destination)


def create_output_path(workspace_root: Path, session_id: str, filename: str) -> Path:
    """Return a unique timestamped output path under workspace/outputs."""
    output_dir = workspace_root / "outputs" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return _unique_path(output_dir / f"{_timestamp()}_{_safe_filename(filename)}")


def copy_to_timestamped_output(source: Path, workspace_root: Path, session_id: str) -> Path:
    """Copy a document to a timestamped output path and return that path."""
    destination = create_output_path(workspace_root, session_id, source.name)
    return copy_file(source, destination)


def restore_output_as_working(output_path: Path, workspace_root: Path, session_id: str) -> Path:
    """Undo by restoring a previous output as the current working copy."""
    _ensure_inside(output_path, workspace_root / "outputs")
    destination = _session_path(workspace_root, "working", session_id, output_path.name)
    return copy_file(output_path, destination)


def _session_path(workspace_root: Path, area: str, session_id: str, filename: str) -> Path:
    directory = workspace_root / area / session_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory / _safe_filename(filename)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not allocate unique output path for {path}")


def _ensure_inside(path: Path, root: Path) -> None:
    path.resolve().relative_to(root.resolve())


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "document"
    return _SAFE_NAME.sub("_", name)
