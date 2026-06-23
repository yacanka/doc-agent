"""Regression tests for browser-provided Excel upload metadata."""

import pytest

from app.tools.excel_tool import assert_xlsx


@pytest.mark.parametrize(
    "content_type",
    [
        None,
        "",
        "application/octet-stream",
        "application/zip",
        "application/x-zip-compressed",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=binary",
    ],
)
def test_assert_xlsx_accepts_browser_excel_content_types(content_type: str | None) -> None:
    assert_xlsx("report.xlsx", content_type)


def test_assert_xlsx_rejects_legacy_xls_extension() -> None:
    with pytest.raises(ValueError, match="Only XLSX"):
        assert_xlsx("report.xls", "application/vnd.ms-excel")
