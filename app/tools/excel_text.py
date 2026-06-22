"""Text extraction and replacement helpers for XLSX workbooks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


def extract_text(path: Path) -> str:
    """Extract visible workbook cell values as deterministic plain text."""
    workbook = load_workbook(path, data_only=False, read_only=True)
    try:
        return "\n".join(_sheet_text(sheet) for sheet in workbook.worksheets)
    finally:
        workbook.close()


def replace_workbook_text(workbook: Any, replacements: dict[str, str]) -> int:
    """Replace literal text in string cells across all worksheets."""
    changed_count = 0
    for sheet in workbook.worksheets:
        changed_count += _replace_sheet_text(sheet, replacements)
    return changed_count


def _sheet_text(sheet: Worksheet) -> str:
    rows = [f"[{sheet.title}]"]
    for values in sheet.iter_rows(values_only=True):
        text_values = [str(value) for value in values if value is not None]
        if text_values:
            rows.append(" | ".join(text_values))
    return "\n".join(rows)


def _replace_sheet_text(sheet: Worksheet, replacements: dict[str, str]) -> int:
    changed_count = 0
    for row in sheet.iter_rows():
        for cell in row:
            changed_count += _replace_cell_text(cell, replacements)
    return changed_count


def _replace_cell_text(cell: Any, replacements: dict[str, str]) -> int:
    if not isinstance(cell.value, str) or cell.value.startswith("="):
        return 0
    updated = _replacement_value(cell.value, replacements)
    if updated == cell.value:
        return 0
    cell.value = updated
    return 1


def _replacement_value(value: str, replacements: dict[str, str]) -> str:
    updated = value
    for source, target in replacements.items():
        updated = updated.replace(str(source), str(target))
    return updated
