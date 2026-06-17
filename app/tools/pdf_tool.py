"""Read-only PDF text extraction utilities."""
from __future__ import annotations

from pathlib import Path


def extract_text(path: Path) -> str:
    """Extract PDF text using PyMuPDF first and pypdf as a fallback."""
    try:
        return _extract_with_pymupdf(path)
    except Exception:
        return _extract_with_pypdf(path)


def reject_write_operation(*_: object, **__: object) -> None:
    """Reject PDF write operations until safe editing is implemented."""
    raise NotImplementedError("PDF write operations are not supported in this read-only version")


def update_pdf(*args: object, **kwargs: object) -> None:
    """Reject attempts to update PDF content."""
    reject_write_operation(*args, **kwargs)


def _extract_with_pymupdf(path: Path) -> str:
    import fitz

    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def _extract_with_pypdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
