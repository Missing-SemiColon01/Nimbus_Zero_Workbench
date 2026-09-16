# Dev 4B — Local Infrastructure & Runtime Reliability

> **Owner**: Dev 4B (you)  
> **Does NOT own**: Frontend, GCP deployment.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Use the `.venv` already in the repo |
| Docker Desktop | Latest | Required for `docker compose` path |
| Docker Compose | v2+ | Comes with Docker Desktop |
| Ollama | Latest | For the Docker path it runs as a container; for local Python run install it natively |

---

## Option A — Local Python (no Docker)

Use this path for fast iteration and test runs.

### 1. Activate the virtual environment

```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 2. Configure environment

```powershell
# Copy the local-python env template and adjust if needed
Copy-Item .env.local.example .env
```

> `.env.local.example` points `OLLAMA_BASE_URL=http://localhost:11434`.  
> Make sure Ollama is running locally (`ollama serve`).

### 3. Start the API

```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Health check

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
# Expected: { "status": "ok", "sovereign_mode": true }
```

---

## Option B — Docker Compose (full stack)

Use this path to test the full docker networking (api ↔ ollama container).

### 1. Configure environment

The default `.env.example` already points at the ollama *container* hostname:

```
OLLAMA_BASE_URL=http://ollama:11434
SOVEREIGN_MODE=true
```

Copy it:

```bash
cp .env.example .env
```

### 2. Build the API image (required after any dependency change)

```bash
docker compose build api
```

> Always rebuild when `requirements.txt` changes (e.g. adding `openpyxl`, `pytest-asyncio`).

### 3. Start the stack

```bash
docker compose up -d
```

Services started:
- **api** → http://localhost:8000
- **ollama** → internal only (port not exposed to host by default)
- **ui** → http://localhost:3000 (frontend, not owned by Dev 4B)

### 4. Health check

```bash
curl -f http://localhost:8000/api/v1/health
# or
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Expected response:
```json
{ "status": "ok", "sovereign_mode": true }
```

### 5. Verify settings inside the container

```bash
docker compose exec api python -c "
from backend.core.config import get_settings
s = get_settings()
print('data_dir:', s.data_dir)
print('ollama_base_url:', s.ollama_base_url)
print('sovereign_mode:', s.sovereign_mode)
"
```

### 6. Stop the stack

```bash
docker compose down
```

---

## Data directories

The following directories must exist and are created automatically when the API starts:

| Path | Purpose |
|------|---------|
| `data/uploads/` | Uploaded PDFs saved by the ingest endpoint |
| `data/artifacts/` | Generated DOCX / PPTX / PDF / XLSX deliverables |
| `data/tmp/` | Temporary preview PNGs and working files |

They are mounted into Docker via:
```yaml
volumes: ["./data:/app/data"]
```

Files **persist across container restarts** because they live on the host filesystem.

### Manual creation (if needed)

```powershell
New-Item -ItemType Directory -Force data\uploads, data\artifacts, data\tmp
```

---

## Running tests

All tests run without Docker or GPU.

```powershell
# Full suite
.venv\Scripts\python.exe -m pytest tests/ -q

# Dev 3 artifact tests only
.venv\Scripts\python.exe -m pytest tests/test_artifact_generators.py tests/test_artifact_tools.py tests/test_tool_setup.py tests/test_artifact_e2e.py tests/test_artifact_api.py tests/test_spreadsheet.py -q

# Vision + RAG async tests (require pytest-asyncio — already in requirements.txt)
.venv\Scripts\python.exe -m pytest tests/test_vision.py tests/test_rag_tool.py -q
```

**Expected**: `191 passed` (as of Dev 4B Phase 1).

---

## Smoke tests (API running)

```powershell
# 1. Health
Invoke-RestMethod http://localhost:8000/api/v1/health

# 2. Upload a small PDF
$form = @{ file = Get-Item "data/uploads/sample.pdf" }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/ingest/upload -Form $form

# 3. List artifacts
Invoke-RestMethod http://localhost:8000/api/v1/artifacts

# 4. Create a task
$body = @{ request = "Summarise the uploaded document"; task_type = "analysis" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/tasks -Body $body -ContentType "application/json"
```

---

## Gotchas

| Issue | Fix |
|-------|-----|
| `async def functions are not natively supported` in tests | `pytest-asyncio` was missing; now in `requirements.txt` + `asyncio_mode = auto` in `pytest.ini` |
| `OLLAMA_BASE_URL=http://ollama:11434` fails locally | Use `.env.local.example` which sets `http://localhost:11434` |
| Docker image missing new deps (e.g. `openpyxl`) | Run `docker compose build api` after any `requirements.txt` change |
| `data/` subdirs missing | They auto-create on startup; or run the PowerShell `New-Item` command above |
| Tests slow on first run | ONNX model load + quantization warm-up; subsequent runs are faster |

---

## Local Demo Checklist

- [ ] `docker compose build api` — image is current
- [ ] `docker compose up -d` — all services start
- [ ] `curl http://localhost:8000/api/v1/health` → `{"status":"ok","sovereign_mode":true}`
- [ ] `data/uploads`, `data/artifacts`, `data/tmp` exist and are writable
- [ ] `python -m pytest tests/ -q` → **191 passed**
- [ ] Upload a PDF → check file appears in `data/uploads/`
- [ ] Generate an artifact → check file appears in `data/artifacts/`
- [ ] No cloud API credentials required anywhere

