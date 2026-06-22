"""FastAPI entrypoint for the local document agent."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.excel_rules import plan_excel_operation
from app.agent.schemas import ApplyRequest, DocumentOperation, OperationPlan, PlanRequest, QuestionRequest, ToolName
from app.config import ensure_workspace, load_config, public_config
from app.model.llm import LocalLlm
from app.model.prompts import planning_prompt, qa_prompt
from app.storage.db import SessionStore
from app.tools.document_tool import assert_supported_document, extract_text
from app.tools.word_tool import safe_filename

_TESTCLIENT_HOST = "testclient"

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
    if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost", _TESTCLIENT_HOST}:
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
    """Upload a single DOCX or XLSX, extract text, and create a session."""
    try:
        assert_supported_document(file.filename or "document.docx", file.content_type)
        path = await _save_upload(file)
        session = store.create_session(safe_filename(file.filename or path.name), path)
        text = extract_text(path)
        store.update_session(session["id"], text_preview=text[:1000], text_length=len(text))
        return {"session_id": session["id"], "filename": session["filename"], "text_preview": text[:1000], "text_length": len(text)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/sessions/{session_id}/questions")
def answer_question(session_id: str, request: QuestionRequest) -> dict:
    """Answer a question for an uploaded document session."""
    session = _session_or_404(session_id)
    answer = llm.answer(request.question, extract_text(Path(session["original_path"])))
    store.audit("question_answered", session_id, {"question": request.question})
    return {"answer": answer}


@app.post("/sessions/{session_id}/questions/stream")
def stream_answer_question(session_id: str, request: QuestionRequest) -> StreamingResponse:
    """Stream a document answer as newline-delimited server events."""
    session = _session_or_404(session_id)
    document_text = extract_text(Path(session["original_path"]))
    store.audit("question_stream_started", session_id, {"question": request.question})
    return _event_response(_answer_events(request.question, document_text))


@app.post("/sessions/{session_id}/plan/stream")
def stream_plan_operations(session_id: str, request: PlanRequest) -> StreamingResponse:
    """Stream raw planning tokens and emit parsed replacements at completion."""
    session = _session_or_404(session_id)
    document_text = extract_text(Path(session["original_path"]))
    store.audit("plan_stream_started", session_id, {"instruction": request.instruction})
    return _event_response(_plan_events(session, request.instruction, document_text))


@app.post("/sessions/{session_id}/plan")
def plan_operations(session_id: str, request: PlanRequest) -> dict:
    """Create a validated operation plan for a document session."""
    session = _session_or_404(session_id)
    try:
        plan = _operation_plan(session, request.instruction)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    payload = _plan_payload(plan)
    store.audit("plan_created", session_id, payload)
    return payload


@app.post("/sessions/{session_id}/apply")
def apply_operations(session_id: str, request: ApplyRequest) -> dict:
    """Apply approved replacements or operations and create an output."""
    session = _session_or_404(session_id)
    plan = _apply_plan(request)
    result = executor.apply_plan(session, plan).model_dump()
    store.update_session(session_id, last_output=result["output_path"])
    store.audit("operations_applied", session_id, result)
    result["download_url"] = _download_url(result["output_path"])
    return result


@app.get("/outputs/{filename:path}")
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
    name = f"{uuid4().hex}_{safe_filename(file.filename or 'document')}"
    destination = config.originals_dir / name
    destination.write_bytes(data)
    return destination


def _answer_events(question: str, document_text: str):
    """Yield escaped SSE chunks for browser-visible incremental rendering."""
    yield from _stream_events(qa_prompt(question, document_text))


def _plan_events(session: dict, instruction: str, document_text: str):
    """Yield planning tokens followed by a validated operation plan."""
    chunks = []
    try:
        deterministic_plan = _deterministic_plan(session, instruction)
        if deterministic_plan:
            yield _sse("plan", _plan_payload(deterministic_plan))
            yield _sse("done", {})
            return
        prompt = planning_prompt(instruction, document_text)
        for token in llm.stream_complete(prompt):
            chunks.append(token)
            yield _sse("token", {"text": token})
        plan = planner.parse_response("".join(chunks))
        yield _sse("plan", _plan_payload(plan))
        replacements = _optional_replacements(plan)
        if replacements:
            yield _sse("replacements", {"items": replacements})
        yield _sse("done", {})
    except Exception as error:
        yield _sse("error", {"message": str(error)})


def _stream_events(prompt: str):
    try:
        for token in llm.stream_complete(prompt):
            yield _sse("token", {"text": token})
        yield _sse("done", {})
    except Exception as error:
        yield _sse("error", {"message": str(error)})


def _operation_plan(session: dict, instruction: str) -> OperationPlan:
    deterministic_plan = _deterministic_plan(session, instruction)
    if deterministic_plan:
        return deterministic_plan
    return planner.plan_operations(instruction, extract_text(Path(session["original_path"])))


def _deterministic_plan(session: dict, instruction: str) -> OperationPlan | None:
    source = Path(session["original_path"])
    if source.suffix.lower() != ".xlsx":
        return None
    return plan_excel_operation(instruction)


def _apply_plan(request: ApplyRequest) -> OperationPlan:
    if request.operations:
        return OperationPlan(operations=request.operations)
    return OperationPlan(operations=[_replacement_operation(request.replacements or {})])


def _replacement_operation(replacements: dict[str, str]) -> DocumentOperation:
    return DocumentOperation(
        action="replace_text",
        tool=ToolName.WORD_REPLACE_TEXT,
        parameters={"replacements": replacements},
    )


def _plan_payload(plan: OperationPlan) -> dict:
    operations = [operation.model_dump(mode="json") for operation in plan.operations]
    return {"operations": operations, "replacements": _optional_replacements(plan)}


def _optional_replacements(plan: OperationPlan) -> dict[str, str] | None:
    try:
        return _plan_replacements(plan)
    except ValueError:
        return None

def _plan_replacements(plan) -> dict[str, str]:
    for operation in plan.operations:
        if operation.action == "replace_text":
            return {str(key): str(value) for key, value in operation.parameters["replacements"].items()}
    raise ValueError("No replacement operation was planned")


def _event_response(events) -> StreamingResponse:
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events, media_type="text/event-stream", headers=headers)


def _sse(event: str, payload: dict) -> str:
    """Serialize one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _session_or_404(session_id: str) -> dict:
    try:
        return store.get_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Session not found") from error


def _safe_output_path(filename: str) -> Path:
    requested = Path(filename)
    if requested.is_absolute() or any(part in {"", ".", ".."} for part in requested.parts):
        raise HTTPException(status_code=400, detail="Invalid output path")
    cleaned_parts = [safe_filename(part) for part in requested.parts]
    output_path = config.outputs_dir.joinpath(*cleaned_parts).resolve()
    if config.outputs_dir.resolve() not in output_path.parents:
        raise HTTPException(status_code=400, detail="Invalid output path")
    return output_path


def _download_url(output_path: str) -> str:
    relative_path = Path(output_path).resolve().relative_to(config.outputs_dir.resolve())
    return f"/outputs/{relative_path.as_posix()}"


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


def _patch_testclient_client_address() -> None:
    """Support Starlette TestClient(client=...) on pinned dependency versions."""
    try:
        import fastapi.testclient as fastapi_testclient
    except Exception:
        return
    original = fastapi_testclient.TestClient
    if "client" in original.__init__.__code__.co_varnames:
        return

    class CompatibleTestClient(original):  # type: ignore[misc, valid-type]
        """Backport the client address argument used by local security tests."""

        def __init__(self, app, *args, client=None, **kwargs):
            wrapped_app = _ClientAddressOverride(app, client) if client else app
            super().__init__(wrapped_app, *args, **kwargs)

    fastapi_testclient.TestClient = CompatibleTestClient


class _ClientAddressOverride:
    """ASGI wrapper that overrides request client addresses in tests."""

    def __init__(self, app, client: tuple[str, int]) -> None:
        self.app = app
        self.client = client

    async def __call__(self, scope, receive, send) -> None:
        scoped = dict(scope)
        scoped["client"] = [self.client[0], self.client[1]]
        await self.app(scoped, receive, send)


_patch_testclient_client_address()
