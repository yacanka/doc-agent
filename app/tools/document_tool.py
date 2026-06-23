"""Shared document type validation and text extraction helpers."""
from __future__ import annotations

from pathlib import Path

from app.tools.excel_tool import assert_xlsx, extract_text as extract_xlsx_text
from app.tools.word_tool import assert_docx, extract_text as extract_docx_text


def assert_supported_document(filename: str, content_type: str | None) -> None:
    """Validate uploads for the editable Office formats supported by the app."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        assert_docx(filename, content_type)
        return
    if suffix == ".xlsx":
        assert_xlsx(filename, content_type)
        return
    raise ValueError("Only DOCX and XLSX uploads are supported")


def extract_text(path: Path) -> str:
    """Extract plain text from a supported uploaded document."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".xlsx":
        return extract_xlsx_text(path)
    raise ValueError(f"Unsupported document type: {suffix}")
