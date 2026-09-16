# One-command reset script for local workbench data.
# Cleans generated artifacts, preview thumbnails, and temporary files without deleting git-tracked code.

$ErrorActionPreference = "SilentlyContinue"

Write-Host "=============================================" -ForegroundColor Yellow
Write-Host " Sovereign AI Workbench - Local Data Reset" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Yellow

$dirsToClean = @("data/uploads", "data/artifacts", "data/tmp/artifact-previews")

foreach ($dir in $dirsToClean) {
    if (Test-Path $dir) {
        Get-ChildItem -Path $dir -File | Remove-Item -Force
        Write-Host "Cleaned files in: $dir" -ForegroundColor Green
    } else {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Ensured directory: $dir" -ForegroundColor Cyan
    }
}

Write-Host "Local workbench data reset successfully." -ForegroundColor Green

