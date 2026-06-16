"""Safe DOCX operations."""
from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(filename: str) -> str:
    """Return a path-safe filename for local storage."""
    name = Path(filename).name.strip() or "document.docx"
    return _SAFE_NAME.sub("_", name)


def assert_docx(filename: str, content_type: str | None) -> None:
    """Validate that an upload is a DOCX file."""
    valid_type = content_type in {None, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if not filename.lower().endswith(".docx") or not valid_type:
        raise ValueError("Only DOCX uploads are supported")


def extract_text(path: Path) -> str:
    """Extract paragraph and table text from a DOCX file."""
    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        parts.extend(cell.text for row in table.rows for cell in row.cells)
    return "\n".join(part for part in parts if part)


def replace_text(source: Path, destination: Path, replacements: dict[str, str]) -> int:
    """Copy a DOCX and replace text inside paragraph runs safely."""
    shutil.copy2(source, destination)
    document = Document(destination)
    count = _replace_paragraphs(document.paragraphs, replacements)
    for table in document.tables:
        for row in table.rows:
            count += _replace_cells(row.cells, replacements)
    document.save(destination)
    return count


def timestamped_output(outputs_dir: Path, session_id: str, filename: str) -> Path:
    """Build a unique timestamped output path for a session."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return outputs_dir / session_id / f"{stamp}_{safe_filename(filename)}"


def _replace_cells(cells: list, replacements: dict[str, str]) -> int:
    count = 0
    for cell in cells:
        count += _replace_paragraphs(cell.paragraphs, replacements)
    return count


def _replace_paragraphs(paragraphs: list, replacements: dict[str, str]) -> int:
    count = 0
    for paragraph in paragraphs:
        for run in paragraph.runs:
            for old_text, new_text in replacements.items():
                if old_text in run.text:
                    occurrences = run.text.count(old_text)
                    run.text = run.text.replace(old_text, new_text)
                    count += occurrences
    return count
