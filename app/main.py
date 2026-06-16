"""FastAPI entrypoint for the local document agent."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.schemas import ApplyRequest, PlanRequest, QuestionRequest
from app.config import ensure_workspace, load_config, public_config
from app.model.llm import LocalLlm
from app.storage.db import SessionStore
from app.tools.word_tool import assert_docx, extract_text, safe_filename

config = load_config()
ensure_workspace(config)
store = SessionStore(config.workspace_root)
llm = LocalLlm(config)
planner = Planner(llm)
executor = Executor(config.outputs_dir)
app = FastAPI(title="Offline Document Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Return service health and non-sensitive configuration."""
    return {"status": "ok", "config": public_config(config)}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """Upload a single DOCX, extract text, and create a session."""
    try:
        assert_docx(file.filename or "document.docx", file.content_type)
        path = await _save_upload(file)
        session = store.create_session(safe_filename(file.filename or path.name), path)
        text = extract_text(path)
        store.update_session(session["id"], text_preview=text[:1000], text_length=len(text))
        return {"session_id": session["id"], "text_preview": text[:1000], "text_length": len(text)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/sessions/{session_id}/questions")
def answer_question(session_id: str, request: QuestionRequest) -> dict:
    """Answer a question for an uploaded DOCX session."""
    session = _session_or_404(session_id)
    answer = llm.answer(request.question, extract_text(Path(session["original_path"])))
    store.audit("question_answered", session_id, {"question": request.question})
    return {"answer": answer}


@app.post("/sessions/{session_id}/plan")
def plan_operations(session_id: str, request: PlanRequest) -> dict:
    """Create a JSON text replacement plan for a document session."""
    session = _session_or_404(session_id)
    replacements = planner.plan(request.instruction, extract_text(Path(session["original_path"])))
    store.audit("plan_created", session_id, {"replacements": replacements})
    return {"replacements": replacements}


@app.post("/sessions/{session_id}/apply")
def apply_operations(session_id: str, request: ApplyRequest) -> dict:
    """Apply literal replacements and create output plus validation report."""
    session = _session_or_404(session_id)
    result = executor.apply(session, request.replacements)
    store.update_session(session_id, last_output=result["output_path"])
    store.audit("operations_applied", session_id, result)
    return result


async def _save_upload(file: UploadFile) -> Path:
    data = await file.read()
    if len(data) > config.max_upload_mb * 1024 * 1024:
        raise ValueError("Upload exceeds configured maximum size")
    name = f"{uuid4().hex}_{safe_filename(file.filename or 'document.docx')}"
    destination = config.originals_dir / name
    destination.write_bytes(data)
    return destination


def _session_or_404(session_id: str) -> dict:
    try:
        return store.get_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Session not found") from error
