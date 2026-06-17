"""SQLite persistence for document sessions, operations, reports, and audit logs."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


def utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class DocumentDatabase:
    """Small SQLite repository for local document processing state."""

    def __init__(self, database_path: Path) -> None:
        """Open a SQLite database path and ensure the schema exists."""
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_session(self, filename: str, original_path: Path, working_path: Path | None = None) -> str:
        """Store a document session and return its generated identifier."""
        session_id = uuid4().hex
        self._execute(
            "INSERT INTO document_sessions VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, filename, str(original_path), None if working_path is None else str(working_path), utc_now(), utc_now()),
        )
        self.add_audit_log(session_id, "session_created", {"filename": filename})
        return session_id

    def add_operation(self, session_id: str, operation_type: str, parameters: dict[str, Any]) -> str:
        """Record an operation request for a document session."""
        operation_id = uuid4().hex
        self._execute(
            "INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?)",
            (operation_id, session_id, operation_type, _json(parameters), "pending", utc_now()),
        )
        return operation_id

    def complete_operation(self, operation_id: str, status: str, output_path: Path | None = None) -> None:
        """Update an operation status and optionally attach an output path."""
        with self._connection() as connection:
            connection.execute("UPDATE operations SET status = ? WHERE id = ?", (status, operation_id))
            if output_path is not None:
                self.add_output(operation_id, output_path, connection)

    def add_output(self, operation_id: str, output_path: Path, connection: sqlite3.Connection | None = None) -> str:
        """Store a generated output path for an operation."""
        output_id = uuid4().hex
        statement = "INSERT INTO output_paths VALUES (?, ?, ?, ?)"
        params = (output_id, operation_id, str(output_path), utc_now())
        self._execute_with_optional_connection(connection, statement, params)
        return output_id

    def add_validation_report(self, operation_id: str, report_path: Path, report: dict[str, Any]) -> str:
        """Persist a validation report path and JSON payload."""
        report_id = uuid4().hex
        self._execute(
            "INSERT INTO validation_reports VALUES (?, ?, ?, ?, ?, ?)",
            (report_id, operation_id, str(report_path), bool(report.get("valid")), bool(report.get("high_risk")), _json(report)),
        )
        return report_id

    def add_audit_log(self, session_id: str | None, event: str, data: dict[str, Any]) -> str:
        """Append an audit log entry for security and traceability."""
        audit_id = uuid4().hex
        self._execute(
            "INSERT INTO audit_log_entries VALUES (?, ?, ?, ?, ?)",
            (audit_id, session_id, event, _json(data), utc_now()),
        )
        return audit_id

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Return one session by identifier or raise KeyError."""
        row = self._fetch_one("SELECT * FROM document_sessions WHERE id = ?", (session_id,))
        if row is None:
            raise KeyError(session_id)
        return dict(row)

    def list_operations(self, session_id: str) -> list[dict[str, Any]]:
        """List operations for a session in creation order."""
        return self._fetch_all("SELECT * FROM operations WHERE session_id = ? ORDER BY created_at", (session_id,))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def _execute(self, statement: str, params: tuple[Any, ...]) -> None:
        with self._connection() as connection:
            connection.execute(statement, params)

    def _fetch_one(self, statement: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        with self._connection() as connection:
            return connection.execute(statement, params).fetchone()

    def _fetch_all(self, statement: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(statement, params).fetchall()
            return [dict(row) for row in rows]

    def _execute_with_optional_connection(self, connection: sqlite3.Connection | None, statement: str, params: tuple[Any, ...]) -> None:
        if connection is None:
            self._execute(statement, params)
        else:
            connection.execute(statement, params)


class SessionStore(DocumentDatabase):
    """Compatibility wrapper for the FastAPI application session API."""

    def __init__(self, workspace_root: Path) -> None:
        """Create a database-backed session store in the workspace root."""
        super().__init__(workspace_root / "document_agent.sqlite3")

    def create_session(self, filename: str, original_path: Path, working_path: Path | None = None) -> dict[str, Any]:
        """Create a session and return the legacy dictionary payload."""
        session_id = super().create_session(filename, original_path, working_path)
        return self.get_session(session_id)

    def update_session(self, session_id: str, **changes: Any) -> dict[str, Any]:
        """Apply supported session field updates and audit extra metadata."""
        fields = {key: value for key, value in changes.items() if key in {"working_path"}}
        if fields:
            self._update_session_fields(session_id, fields)
        extra = {key: value for key, value in changes.items() if key not in fields}
        if extra:
            self.add_audit_log(session_id, "session_metadata_updated", extra)
        return self.get_session(session_id)

    def audit(self, event: str, session_id: str | None, data: dict[str, Any]) -> None:
        """Append a legacy audit event."""
        self.add_audit_log(session_id, event, data)

    def _update_session_fields(self, session_id: str, fields: dict[str, Any]) -> None:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        params = tuple(fields.values()) + (utc_now(), session_id)
        self._execute(f"UPDATE document_sessions SET {assignments}, updated_at = ? WHERE id = ?", params)


_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS document_sessions (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    working_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES document_sessions(id),
    operation_type TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS output_paths (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations(id),
    path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS validation_reports (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations(id),
    report_path TEXT NOT NULL,
    valid INTEGER NOT NULL,
    high_risk INTEGER NOT NULL,
    report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES document_sessions(id),
    event TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)
