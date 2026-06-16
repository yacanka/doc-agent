"""File copy helpers for preserving originals and outputs."""
from __future__ import annotations

import shutil
from pathlib import Path


def copy_file(source: Path, destination: Path) -> Path:
    """Copy a file after ensuring the destination directory exists."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination
