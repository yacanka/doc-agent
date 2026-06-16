from pathlib import Path

from docx import Document

from app.tools.validation_tool import validate_replacements
from app.tools.word_tool import extract_text, replace_text, safe_filename


def _docx(path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def test_safe_filename_removes_paths_and_symbols() -> None:
    assert safe_filename("../bad name!.docx") == "bad_name_.docx"


def test_extract_and_replace_docx_text(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "output.docx"
    _docx(source, "Hello Alice")

    count = replace_text(source, output, {"Alice": "Bob"})

    assert count == 1
    assert "Hello Bob" in extract_text(output)
    assert validate_replacements(output, {"Alice": "Bob"}, count)["valid"] is True
