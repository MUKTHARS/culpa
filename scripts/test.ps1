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
# Separate output folder: building into .next would break a dev server that is running at the same time.
# Next.js rewrites tsconfig.json and next-env.d.ts to point at that folder, so put both back afterwards.
$keep = @{}
foreach ($f in "tsconfig.json", "next-env.d.ts") { $keep[$f] = [IO.File]::ReadAllText("$root\apps\web\$f") }
$env:NEXT_DIST_DIR = ".next-build"
pnpm build
$code = $LASTEXITCODE
Remove-Item Env:NEXT_DIST_DIR
foreach ($f in $keep.Keys) { [IO.File]::WriteAllText("$root\apps\web\$f", $keep[$f]) }
if ($code -ne 0) { exit 1 }

Write-Host "All checks passed."
