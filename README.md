# Offline Document Agent

Local-first FastAPI service for DOCX upload, text extraction, llama.cpp-backed question answering, JSON replacement planning, safe DOCX text replacement, output validation, and audit logging.

## Project structure

- `app/main.py` starts the FastAPI app and exposes document/session endpoints.
- `app/config.py` loads `config.json` and creates workspace directories.
- `app/model/` contains prompts and the `llama-cpp-python` adapter.
- `app/agent/` contains planning, execution, and API schemas.
- `app/tools/` contains DOCX, validation, backup, and placeholder document tools.
- `app/storage/db.py` stores sessions and audit logs as local JSON/JSONL.
- `models/` stores local GGUF models.
- `wheels/` can hold offline Python wheels.
- `workspace/` contains originals, working files, and generated outputs.

## Setup

Run `setup_online.bat` on a connected Windows machine, copy any required wheels and a GGUF model into `models/model.gguf`, then run `run_offline.bat`.

## API

- `GET /health`
- `POST /documents` with one DOCX file field named `file`
- `POST /sessions/{session_id}/questions`
- `POST /sessions/{session_id}/plan`
- `POST /sessions/{session_id}/apply`

## Security notes

Uploads are limited by `max_upload_mb`, filenames are sanitized, only DOCX files are accepted, originals are preserved, generated documents are timestamped, and every mutating action is audit logged.
