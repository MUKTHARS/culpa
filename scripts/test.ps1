# Run every check: backend tests, benchmark, web type-check and production build.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Set-Location "$root\apps\api"
.\.venv\Scripts\python.exe -m pytest
if ($LASTEXITCODE -ne 0) { exit 1 }

Set-Location $root
& "$root\apps\api\.venv\Scripts\python.exe" bench\run.py
if ($LASTEXITCODE -ne 0) { exit 1 }

Set-Location "$root\apps\web"
pnpm typecheck
if ($LASTEXITCODE -ne 0) { exit 1 }
pnpm build
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "All checks passed."
