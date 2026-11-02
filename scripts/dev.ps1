# Start the API (with in-process worker) and the web app in two windows.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File C:\src\culpa\scripts\dev.ps1
# Safe to run again: old Culpa servers are stopped first, so two servers never share a port.
$root = Split-Path -Parent $PSScriptRoot

# Stop previous API servers (uvicorn + its reload workers) and the Next.js dev server.
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'uvicorn main:app' -or
                   ($_.CommandLine -match 'multiprocessing.spawn' -and $_.CommandLine -match 'Python') -or
                   ($_.CommandLine -match 'next' -and $_.CommandLine -match [regex]::Escape("$root\apps\web")) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# --reload-include .env: saving new keys restarts the API, so it never runs with stale credentials.
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$root\apps\api'; .\.venv\Scripts\python.exe -m uvicorn main:app --reload --reload-include .env --port 8000
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$root\apps\web'; pnpm dev
"@

Write-Host "API  http://127.0.0.1:8000/docs"
Write-Host "Web  http://127.0.0.1:3000"
