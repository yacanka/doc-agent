"""FastAPI entrypoint for the local document agent."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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
ui_dir = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")


@app.middleware("http")
async def enforce_localhost_only(request: Request, call_next):
    """Reject non-loopback clients to keep the local document agent private."""
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
        return JSONResponse({"detail": "Localhost access only"}, status_code=403)
    return await call_next(request)


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    """Redirect browser users to the local single-page UI."""
    return RedirectResponse(url="/ui/index.html")


@app.get("/health")
def health() -> dict:
    """Return service health and non-sensitive configuration."""
    return {"status": "ok", "config": public_config(config), "offline_ready": _offline_ready()}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """Upload a single DOCX, extract text, and create a session."""
    try:
        assert_docx(file.filename or "document.docx", file.content_type)
        path = await _save_upload(file)
        session = store.create_session(safe_filename(file.filename or path.name), path)
        text = extract_text(path)
        store.update_session(session["id"], text_preview=text[:1000], text_length=len(text))
        return {"session_id": session["id"], "filename": session["filename"], "text_preview": text[:1000], "text_length": len(text)}
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
    result["download_url"] = _download_url(result["output_path"])
    return result


@app.get("/outputs/{filename}")
def download_output(filename: str) -> FileResponse:
    """Download a generated output file from the controlled outputs directory."""
    output_path = _safe_output_path(filename)
    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(output_path, filename=output_path.name)


@app.post("/output-folder")
def open_output_folder() -> dict:
    """Open the local output folder when the operating system supports it."""
    if not _can_open_folder():
        return {"supported": False, "message": "Opening folders is not supported here"}
    _open_folder(config.outputs_dir)
    return {"supported": True, "path": str(config.outputs_dir)}


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


def _safe_output_path(filename: str) -> Path:
    cleaned_name = safe_filename(Path(filename).name)
    output_path = (config.outputs_dir / cleaned_name).resolve()
    if config.outputs_dir.resolve() not in output_path.parents:
        raise HTTPException(status_code=400, detail="Invalid output path")
    return output_path


def _download_url(output_path: str) -> str:
    return f"/outputs/{Path(output_path).name}"


def _offline_ready() -> bool:
    return config.model_path.exists() and config.workspace_root.exists()


def _can_open_folder() -> bool:
    return sys.platform.startswith(("darwin", "win")) or bool(os.environ.get("DISPLAY"))


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
