# Dev 4 Local Integration

This backend flow is the Dev 4A contract for local integration with the frontend and other modules.

## 1. Upload and ingest a PDF

```bash
curl -F "file=@inspection_report.pdf" \
  -F "document_id=inspection_report_01" \
  http://localhost:8000/api/v1/ingest/upload
```

Use the returned `document_path` when creating a task.

## 2. Run a document task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Find safety-related findings in this inspection report",
    "document_paths": ["data/uploads/inspection_report.pdf"]
  }'
```

Uploaded-document tasks default to `document_understanding` when no explicit task type or capability is provided.

## 3. Run an approved artifact task

Artifact tools require explicit approval.

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Create an approval note for the inspection findings",
    "task_type": "reasoning",
    "approved_tools": ["document.create"]
  }'
```

The task response includes:

- `approval_required`
- `approval_requests`
- `tool_results`
- `artifacts`
- `generated_artifacts`

Use `generated_artifacts[].download_url` for the frontend download action.

## 4. List and download artifacts

```bash
curl http://localhost:8000/api/v1/artifacts
curl -OJ http://localhost:8000/api/v1/artifacts/<filename>/download
```

## 5. Smoke check before demo

Start the backend, then run:

```powershell
.\.venv\Scripts\python.exe scripts\dev4_smoke.py
```

The smoke check verifies:

- `/health`
- `/models`
- `/tools`
- basic `/tasks`
- `/artifacts`

If the basic task fails because Ollama is not running, the API is reachable but model runtime setup still needs attention.
