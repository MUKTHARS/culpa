# One-time setup on Windows: Python venv + backend deps, web deps, benchmark data.
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\apps\api"

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Some Windows machines block SQLAlchemy's compiled extension (Application Control).
# The pure-Python build behaves identically.
$env:DISABLE_SQLALCHEMY_CEXT = "1"
.\.venv\Scripts\python.exe -m pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy==2.1.6

if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Set-Location "$root\apps\web"
pnpm install
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }

Set-Location $root
& "$root\apps\api\.venv\Scripts\python.exe" bench\generate.py
& "$root\apps\api\.venv\Scripts\python.exe" bench\run.py

Write-Host "Setup complete. Start everything with: powershell -File scripts\dev.ps1"
