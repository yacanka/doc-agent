"""Lightweight JSONL persistence for sessions and audit events."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """Persist sessions and audit events without a server dependency."""

    def __init__(self, workspace_root: Path) -> None:
        """Initialize paths and in-memory session index."""
        self.workspace_root = workspace_root
        self.sessions_path = workspace_root / "sessions.json"
        self.audit_path = workspace_root / "audit.log"
        self.sessions = self._load_sessions()

    def create_session(self, filename: str, original_path: Path) -> dict[str, Any]:
        """Create and persist a new upload session."""
        session = {
            "id": uuid4().hex,
            "filename": filename,
            "original_path": str(original_path),
            "created_at": utc_now(),
            "events": [],
        }
        self.sessions[session["id"]] = session
        self.save()
        self.audit("session_created", session["id"], {"filename": filename})
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Return a session by identifier or raise KeyError."""
        return self.sessions[session_id]

    def update_session(self, session_id: str, **changes: Any) -> dict[str, Any]:
        """Apply changes to a session and persist them."""
        session = self.get_session(session_id)
        session.update(changes)
        self.save()
        return session

    def audit(self, event: str, session_id: str | None, data: dict[str, Any]) -> None:
        """Append one immutable audit event as JSONL."""
        record = {"time": utc_now(), "event": event, "session_id": session_id, "data": data}
        with self.audit_path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def save(self) -> None:
        """Persist all sessions atomically enough for local single-user usage."""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.sessions_path.write_text(json.dumps(self.sessions, indent=2), encoding="utf-8")

    def _load_sessions(self) -> dict[str, Any]:
        if not self.sessions_path.exists():
            return {}
        return json.loads(self.sessions_path.read_text(encoding="utf-8"))
