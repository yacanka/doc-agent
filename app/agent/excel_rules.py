"""Deterministic Excel operation planning rules for explicit user instructions."""
from __future__ import annotations

import re
from typing import Any

from app.agent.schemas import DocumentOperation, OperationPlan, ToolName

_CELL = r"(?P<cell>\$?[A-Z]{1,3}\$?\d{1,7})"
_SHEET_VALUE = r"[A-Za-z0-9 _.-]{1,64}"
_SET_PATTERNS = (
    re.compile(rf"(?:set|update|change)\s+(?:(?P<sheet1>{_SHEET_VALUE})!)?{_CELL}\s+(?:to|as)\s+(?P<value>.+)", re.I),
    re.compile(rf"(?:set|update|change)\s+(?P<sheet>{_SHEET_VALUE})\s+{_CELL}\s+(?:to|as)\s+(?P<value>.+)", re.I),
)
_REPLACE_PATTERN = re.compile(r"replace\s+['\"]?(?P<old>.+?)['\"]?\s+with\s+['\"]?(?P<new>.+?)['\"]?$", re.I)
_APPEND_PATTERN = re.compile(rf"append\s+row\s+(?:to|into)\s+(?P<sheet>{_SHEET_VALUE})\s*:\s*(?P<values>.+)", re.I)


def plan_excel_operation(instruction: str) -> OperationPlan | None:
    """Return a deterministic Excel plan when the instruction is explicit."""
    operation = _cell_update(instruction) or _append_row(instruction) or _text_replacement(instruction)
    if not operation:
        return None
    return OperationPlan(operations=[operation], summary="Deterministic Excel operation")


def _cell_update(instruction: str) -> DocumentOperation | None:
    for pattern in _SET_PATTERNS:
        match = pattern.search(instruction.strip())
        if match:
            return _update_operation(_sheet_name(match), match.group("cell"), match.group("value"))
    return None


def _update_operation(sheet_name: str, cell_reference: str, value: str) -> DocumentOperation:
    updates = {sheet_name: {_clean_cell(cell_reference): _clean_value(value)}}
    return DocumentOperation(action="update_cells", tool=ToolName.EXCEL_UPDATE_CELLS, parameters={"updates": updates})


def _append_row(instruction: str) -> DocumentOperation | None:
    match = _APPEND_PATTERN.search(instruction.strip())
    if not match:
        return None
    rows = [[_clean_value(value) for value in match.group("values").split(",")]]
    return DocumentOperation(
        action="append_rows",
        tool=ToolName.EXCEL_APPEND_ROWS,
        parameters={"sheet_name": _sheet_name(match), "rows": rows},
    )


def _text_replacement(instruction: str) -> DocumentOperation | None:
    match = _REPLACE_PATTERN.search(instruction.strip())
    if not match:
        return None
    replacements = {_clean_value(match.group("old")): _clean_value(match.group("new"))}
    return DocumentOperation(action="replace_text", tool=ToolName.EXCEL_REPLACE_TEXT, parameters={"replacements": replacements})


def _sheet_name(match: re.Match[str]) -> str:
    return _clean_value(match.groupdict().get("sheet") or match.groupdict().get("sheet1") or "Sheet")


def _clean_cell(cell_reference: str) -> str:
    return cell_reference.replace("$", "").upper()


def _clean_value(value: Any) -> str:
    return str(value).strip().strip("'\"")
