"""Normalize spreadsheet range/value aliases into explicit cell updates."""
from __future__ import annotations

from typing import Any


def normalize_update_cells_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert range/value model aliases into strict update dictionaries."""
    parameters = dict(payload.get("parameters") or {})
    if "updates" in parameters or not {"range", "values"} <= set(parameters):
        return payload
    normalized = dict(payload)
    normalized["parameters"] = {"updates": range_updates(parameters["range"], parameters["values"])}
    return normalized


def range_updates(range_reference: Any, values: Any) -> dict[str, dict[str, Any]]:
    """Expand an Excel range and values into sheet-coordinate updates."""
    sheet_name, start_cell, end_cell = _split_range(str(range_reference))
    coordinates = _range_coordinates(start_cell, end_cell)
    flattened_values = _flatten_values(values)
    expanded_values = _expanded_values(flattened_values, len(coordinates))
    return {sheet_name: dict(zip(coordinates, expanded_values))}


def _split_range(range_reference: str) -> tuple[str, str, str]:
    sheet_name, cells = range_reference.rsplit("!", maxsplit=1)
    start_cell, end_cell = cells.split(":", maxsplit=1) if ":" in cells else (cells, cells)
    return sheet_name.strip("\"'"), start_cell.upper(), end_cell.upper()


def _range_coordinates(start_cell: str, end_cell: str) -> list[str]:
    start_column, start_row = _cell_parts(start_cell)
    end_column, end_row = _cell_parts(end_cell)
    return [_coordinate(column, row) for row in range(start_row, end_row + 1) for column in range(start_column, end_column + 1)]


def _coordinate(column: int, row: int) -> str:
    return f"{_column_name(column)}{row}"


def _cell_parts(cell_reference: str) -> tuple[int, int]:
    letters = "".join(character for character in cell_reference if character.isalpha())
    digits = "".join(character for character in cell_reference if character.isdigit())
    return _column_number(letters), int(digits)


def _column_number(column_name: str) -> int:
    number = 0
    for character in column_name:
        number = number * 26 + ord(character) - 64
    return number


def _column_name(column_number: int) -> str:
    name = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _flatten_values(values: Any) -> list[Any]:
    if not isinstance(values, list):
        return [values]
    return [item for row in values for item in (row if isinstance(row, list) else [row])]


def _expanded_values(values: list[Any], count: int) -> list[Any]:
    if len(values) == 1:
        return values * count
    if len(values) != count:
        raise ValueError("Range values must contain one value or match the range size")
    return values
