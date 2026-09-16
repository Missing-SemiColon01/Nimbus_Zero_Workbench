# Sandbox Coding Workflow

This backend path supports the README secondary demo:

```text
Requirement -> Coding Model -> Sandbox -> Tests -> Fix -> Verified Code
```

## Local Setup

Create the sandbox image once:

```powershell
docker build -t workbench-sandbox:latest sandbox
```

Start the backend:

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --reload
```

## Direct Sandbox Check

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/sandbox/run `
  -ContentType application/json `
  -Body '{"code":"print(\"hello sandbox\")","timeout_seconds":10}'
```

## Coding Workflow Check

```powershell
$body = @{
  requirement = "Write add(a, b) that returns the sum."
  test_code = "from solution import add`n`ndef test_add():`n    assert add(2, 3) == 5`n"
  max_retries = 1
  timeout_seconds = 10
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/coding/run `
  -ContentType application/json `
  -Body $body
```

## Audit Evidence

Sandbox and coding workflow calls append local JSONL audit events:

```text
data/audit/events.jsonl
```

Recent events are also available at:

```text
GET /api/v1/audit/events?limit=20
```

Audit entries intentionally store execution metadata and results, not the full generated code body.
