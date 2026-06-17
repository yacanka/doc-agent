# Offline Document Agent

Offline Document Agent is a local-first FastAPI application for private document question answering and controlled document updates. It runs on `127.0.0.1`, uses a local GGUF model through `llama-cpp-python`, stores data under `workspace/`, and keeps generated files separate from uploaded originals.

## Project layout

- `setup_online.bat` prepares the Windows virtual environment, downloads wheels, and verifies the GGUF model.
- `run_offline.bat` starts the local UI and API without online package access.
- `config.json` controls host, port, workspace path, model path, and LLM settings.
- `models/` stores the local GGUF model file.
- `wheels/` stores Python wheels downloaded during online setup.
- `workspace/originals/` stores uploaded source files.
- `workspace/outputs/` stores generated documents and validation reports.
- `app/tools/` contains deterministic document parsers and editing tools.

## 1. First online setup with `setup_online.bat`

Run this once on a connected Windows machine before offline use.

1. Install Python 3.10, 3.11, or 3.12 if a supported interpreter is not already available as `py -3` or `python`. Python 3.13+ is not currently supported by the pinned Windows dependency set.
2. Copy or download a trusted GGUF model to the path configured in `config.json`; the default is `models/model.gguf`.
3. Open Command Prompt in the project root.
4. Run:

   ```bat
   setup_online.bat
   ```

During setup, the script prefers Python 3.12, then 3.11, then 3.10; rejects unsupported interpreters; creates `.venv/`; downloads wheels into `wheels/`; installs from that local cache; creates required directories; verifies the configured model; and writes `workspace/setup_complete.json`.

Optional model download:

```bat
set MODEL_URL=https://trusted.example/path/to/model.gguf
setup_online.bat
```

Only use `MODEL_URL` with a trusted HTTPS source. Prefer checksums from the model publisher when available.

## 2. Offline usage with `run_offline.bat`

After setup has completed, move the full project folder to the offline machine if needed. Keep `.venv/`, `wheels/`, `models/`, `config.json`, and `workspace/setup_complete.json` together.

Run:

```bat
run_offline.bat
```

The script refuses to start without `workspace/setup_complete.json`, activates `.venv/`, forces offline package behavior with `PIP_NO_INDEX=1` and `PIP_FIND_LINKS=wheels`, sets model-library offline flags, opens `http://127.0.0.1:8000/docs`, and starts `uvicorn app.main:app`.

Use the API documentation page or local UI to upload a document, ask questions, create a replacement plan, apply approved replacements, and download generated outputs.

## 3. Replacing the GGUF model in `models/`

The default model path is:

```text
models/model.gguf
```

To replace it safely:

1. Stop the application.
2. Obtain a GGUF model from a trusted source.
3. Verify the publisher, license, expected size, and checksum when available.
4. Replace `models/model.gguf` with the new file, or put the file elsewhere under `models/`.
5. If the filename changes, update `model_path` in `config.json`.
6. Re-run `setup_online.bat` on a connected machine if you want the setup marker to reflect the new path.
7. Start offline with `run_offline.bat`.

Model trade-offs:

- Larger models usually improve reasoning but need more RAM and CPU time.
- Smaller quantized models start faster but may produce weaker plans.
- The executor still validates and constrains operations; model quality does not grant extra file permissions.

## 4. Supported file types and operations

| File type | Current API support | Tool capabilities |
| --- | --- | --- |
| DOCX | Upload, question answering, planning, literal text replacement, validation, download | Extract text from paragraphs, tables, headers, and footers; replace literal text while preserving existing package structure where possible. |
| XLSX | Tool-level support | Inspect workbook structure, sample sheet data, update explicit cells, append rows with nearby styling, and copy cell style. |
| PPTX | Tool-level support | Inspect slide summaries, extract slide and notes text, and replace text inside existing runs. |
| PDF | Tool-level read-only support | Extract text with PyMuPDF and fall back to pypdf; write operations are intentionally rejected. |

The public upload endpoint currently accepts DOCX only. XLSX, PPTX, and PDF tools are available in code for controlled extensions, tests, and future API expansion.

## 5. Known limitations

- Only DOCX uploads are exposed through the current web/API flow.
- DOCX replacement is literal text replacement, not semantic rewriting of arbitrary layout regions.
- Text split across complex fields, tracked changes, comments, embedded objects, or unusual XML structures may not always replace as expected.
- PDF editing is not supported; PDFs are read-only for text extraction.
- The local LLM is limited by `context_size`, `max_tokens`, CPU speed, RAM, and model quality.
- The app is designed for one local user at a time, not multi-tenant server deployment.
- Validation confirms expected text changes and parser readability; it is not a legal or visual-perfect proof.

## 6. Why formatting is preserved better than direct AI binary editing

The architecture separates reasoning from execution:

1. The LLM reads extracted text and returns a structured plan.
2. Pydantic validates the plan schema.
3. A deterministic executor runs only approved tools.
4. Tools copy the original document and edit known text locations.
5. Validation checks the generated output after editing.

This avoids asking the AI to rewrite DOCX, XLSX, PPTX, or PDF binaries directly. Office files are structured packages containing XML parts, relationships, metadata, styles, and media. Direct binary editing can corrupt those relationships. Controlled parser-based updates preserve the original package and change only targeted content whenever possible.

## 7. Security and privacy guarantees

- The server rejects non-loopback clients and is intended for `127.0.0.1` or `localhost` use.
- Uploaded filenames are sanitized before storage.
- Upload size is limited by `max_upload_mb` in `config.json`.
- Originals are stored separately from generated outputs.
- Outputs are timestamped instead of overwriting the source document.
- The LLM receives document text, not arbitrary filesystem write access.
- The executor uses an allow-list of approved tools.
- Vague destructive instructions are rejected by the planner.
- Mutating actions are written to the local audit log.

## 8. No-cloud and no-telemetry behavior

The offline runtime is designed to avoid cloud dependencies:

- Model inference uses the local GGUF file configured by `model_path`.
- `run_offline.bat` disables pip index access and points package resolution at local wheels.
- Common Hugging Face and Transformers offline flags are enabled.
- No telemetry client is configured by the application.
- Document originals, outputs, validation reports, and audit logs remain under the local `workspace/` directory.

Important boundary: the application cannot stop unrelated software, browser extensions, endpoint agents, or operating-system services from using the network. For high-assurance use, run on an isolated offline machine or blocked network segment.

## 9. Offline verification checklist

Before handling sensitive documents, verify:

- [ ] `workspace/setup_complete.json` exists.
- [ ] `models/model.gguf` exists, or `config.json` points to the intended GGUF file.
- [ ] `wheels/` contains the downloaded dependency wheels.
- [ ] The machine is disconnected from the network or outbound traffic is blocked.
- [ ] `run_offline.bat` starts without downloading packages.
- [ ] `GET http://127.0.0.1:8000/health` returns `offline_ready: true`.
- [ ] A small test DOCX can be uploaded, edited, downloaded, and opened.
- [ ] The generated validation JSON reports the expected replacements.
- [ ] `workspace/audit.log` records the test mutation.

## 10. Troubleshooting

### Missing model files

Symptoms include `ERROR: GGUF model is missing`, `/health` returning `offline_ready: false`, or LLM failures during questions and planning.

Fix:

1. Check `model_path` in `config.json`.
2. Place a trusted GGUF model at that exact path.
3. Keep the filename extension as `.gguf` for clarity.
4. Re-run `setup_online.bat` on the connected setup machine.
5. Start again with `run_offline.bat`.

### Dependency setup failure

Symptoms include missing Python, failed wheel downloads, or offline installs reporting missing packages.

Fix:

1. Install Python 3.10, 3.11, or 3.12 and confirm `py -3 --version` or `python --version` reports one of those versions.
2. If setup used Python 3.13+ or 3.14, delete `.venv/` so it can be recreated with the supported interpreter.
3. Re-run `setup_online.bat` with internet access.
4. If a package has no compatible wheel, use the same operating system, Python version, and CPU architecture as the offline target.
5. Delete and recreate `.venv/` only after preserving `wheels/` and the model file.
6. Review the exact package named in the pip error and add a compatible wheel to `wheels/` if needed.


### `pydantic-core` metadata or Rust download certificate failure

Symptoms include `Preparing metadata (pyproject.toml) ... error`, `pydantic-core`, `Python reports SOABI: cp314-win_amd64`, or an attempted Rust download that fails with `CERTIFICATE_VERIFY_FAILED`.

Cause:

- The setup is running on Python 3.14. The pinned dependency set expects prebuilt Windows wheels for supported Python versions.
- Because a compatible wheel is not available for Python 3.14, pip falls back to building `pydantic-core` from source. That build path requires Rust and may try to download `rustup-init.exe`, which can fail behind corporate TLS interception or with a missing local certificate chain.

Fix:

1. Install Python 3.12 for Windows from a trusted source.
2. Open a new Command Prompt and verify `py -3.12 --version`.
3. Delete the existing `.venv/` directory created with Python 3.14.
4. Re-run setup with the supported interpreter first on `PATH`, or run `py -3.12 -m venv .venv` before `setup_online.bat`.
5. Do not bypass TLS verification. If your network intercepts TLS, install the organization-approved root certificate instead.

### Unsupported document operations

Symptoms include non-DOCX upload failures, rejected PDF writes, or requests that cannot be safely expressed as a replacement plan.

Fix:

1. Use DOCX for the current web/API workflow.
2. Convert unsupported source documents to DOCX when editing is required.
3. For PDF, use extraction-only behavior or edit the original authoring file instead.
4. Make requests specific: identify exact source text and desired replacement text.
5. Avoid vague destructive commands such as deleting all content.

## API endpoints

- `GET /health` returns service status and non-sensitive configuration.
- `POST /documents` uploads one DOCX file field named `file`.
- `POST /sessions/{session_id}/questions` answers a question using local model inference.
- `POST /sessions/{session_id}/plan` creates a validated replacement plan.
- `POST /sessions/{session_id}/apply` applies replacements and writes validation output.
- `GET /outputs/{filename}` downloads a generated output file.
- `POST /output-folder` opens the local output directory when the OS supports it.
