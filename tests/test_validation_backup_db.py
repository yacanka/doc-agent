from pathlib import Path

import pytest

pytest.importorskip("docx")
from docx import Document

from app.storage.db import DocumentDatabase, SessionStore
from app.tools.backup_tool import (
    copy_to_timestamped_output,
    create_working_copy,
    restore_output_as_working,
    store_original,
)
from app.tools.validation_tool import result_to_dict, validate_output_file


def _docx(path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def test_backup_workflow_preserves_original_and_restores_output(tmp_path: Path) -> None:
    upload = tmp_path / "upload.docx"
    _docx(upload, "original")

    original = store_original(upload, tmp_path / "workspace", "session-1")
    working = create_working_copy(original, tmp_path / "workspace", "session-1")
    output = copy_to_timestamped_output(working, tmp_path / "workspace", "session-1")
    restored = restore_output_as_working(output, tmp_path / "workspace", "session-1")

    assert original.read_bytes() == upload.read_bytes()
    assert working.read_bytes() == upload.read_bytes()
    assert output.parent == tmp_path / "workspace" / "outputs" / "session-1"
    assert restored.read_bytes() == output.read_bytes()
    with pytest.raises(FileExistsError):
        store_original(upload, tmp_path / "workspace", "session-1")


def test_validation_writes_report_and_tracks_package_changes(tmp_path: Path) -> None:
    original = tmp_path / "original.docx"
    output = tmp_path / "output.docx"
    _docx(original, "Hello Alice")
    _docx(output, "Hello Bob")

    result = validate_output_file(original, output, tmp_path / "workspace")
    report = Path(result.report_path)

    assert result.valid is True
    assert result.parser == "python-docx"
    assert "word/document.xml" in result.changed_entries
    assert report.parent == tmp_path / "workspace" / "outputs"
    assert result_to_dict(result)["report_path"] == str(report)


def test_document_database_records_session_operation_report_and_audit(tmp_path: Path) -> None:
    database = DocumentDatabase(tmp_path / "workspace" / "state.sqlite3")
    session_id = database.create_session("source.docx", tmp_path / "source.docx")
    operation_id = database.add_operation(session_id, "replace_text", {"Alice": "Bob"})

    database.complete_operation(operation_id, "completed", tmp_path / "out.docx")
    report_id = database.add_validation_report(operation_id, tmp_path / "report.json", {"valid": True, "high_risk": False})
    audit_id = database.add_audit_log(session_id, "checked", {"ok": True})

    assert database.get_session(session_id)["filename"] == "source.docx"
    assert database.list_operations(session_id)[0]["status"] == "completed"
    assert report_id
    assert audit_id


def test_session_store_keeps_legacy_api_shape(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "workspace")
    session = store.create_session("source.docx", tmp_path / "source.docx")

    updated = store.update_session(session["id"], text_length=10)
    store.audit("event", session["id"], {"ok": True})

    assert updated["id"] == session["id"]
    assert store.get_session(session["id"])["filename"] == "source.docx"
