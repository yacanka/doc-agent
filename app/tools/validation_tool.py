"""Validation report generation for document operations."""
from __future__ import annotations

import json
from pathlib import Path

from app.storage.db import utc_now
from app.tools.word_tool import extract_text


def validate_replacements(path: Path, replacements: dict[str, str], changed_count: int) -> dict:
    """Validate a DOCX after replacement operations."""
    text = extract_text(path)
    missing = [value for value in replacements.values() if value not in text]
    leftovers = [key for key in replacements if key in text]
    return {
        "created_at": utc_now(),
        "document": str(path),
        "changed_count": changed_count,
        "missing_replacements": missing,
        "leftover_sources": leftovers,
        "valid": not missing and not leftovers and changed_count > 0,
    }


def write_report(report: dict, output_path: Path) -> Path:
    """Write a validation report next to the generated document."""
    report_path = output_path.with_suffix(output_path.suffix + ".validation.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
