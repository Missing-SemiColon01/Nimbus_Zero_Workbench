# One-command local startup script for Windows PowerShell
# Starts the backend API locally with reload enabled.

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Sovereign AI Workbench - Local API Startup" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Ensure required data directories exist
$dataDirs = @("data/uploads", "data/artifacts", "data/tmp", "data/tmp/artifact-previews")
foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Green
    }
}

# 2. Check for .env file; copy from .env.local.example if missing
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.local.example") {
        Copy-Item ".env.local.example" ".env"
        Write-Host "Created .env from .env.local.example (Local Python configuration)" -ForegroundColor Yellow
    }
}

# 3. Locate Python inside virtual environment
$pythonBin = ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonBin)) {
    Write-Host "Virtual environment not found at .venv. Falling back to system python..." -ForegroundColor Yellow
    $pythonBin = "python"
}

Write-Host "Starting Sovereign AI Workbench API at http://localhost:8000 ..." -ForegroundColor Green
& $pythonBin -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

