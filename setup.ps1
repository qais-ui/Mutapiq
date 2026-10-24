# Mutabiq one-command setup for Windows (PowerShell).   Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# Needs: Python 3.11+ and Ollama (https://ollama.com/download) installed first.
param([string]$Py = "python", [string]$Ollama = "ollama")
$ErrorActionPreference = "Stop"

Write-Host "1/6 Python environment" -ForegroundColor Cyan
$pyver = & $Py -c "import sys; print(sys.version_info >= (3,11))"
if ($pyver -ne "True") { Write-Host "Python 3.11 or newer is needed. Install it from python.org, then run again." -ForegroundColor Red; exit 1 }
if (-not (Test-Path .venv\Scripts\python.exe)) { & $Py -m venv .venv }
if ($LASTEXITCODE -ne 0) { Write-Host "Could not create the Python environment." -ForegroundColor Red; exit 1 }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
# WeasyPrint needs GTK on Windows; skip it — the app offers HTML download (Print -> Save as PDF) instead.
Get-Content requirements.txt | Where-Object { $_ -notmatch "^weasyprint" } | Set-Content .req-win.txt
& .\.venv\Scripts\python.exe -m pip install -r .req-win.txt -q
if ($LASTEXITCODE -ne 0) { Write-Host "Package install failed. Check your internet and run START_MUTABIQ.bat again." -ForegroundColor Red; Remove-Item .venv -Recurse -Force; exit 1 }
Remove-Item .req-win.txt
& .\.venv\Scripts\python.exe -m playwright install chromium

Write-Host "2/6 Open-weight models (Apache-2.0 / MIT)" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
$up = $true
try { & $Ollama list *> $null; if ($LASTEXITCODE -ne 0) { $up = $false } } catch { $up = $false }
if (-not $up) { Start-Process $Ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep -Seconds 8 }
& $Ollama pull qwen2.5:7b-instruct
if ($LASTEXITCODE -ne 0) { Write-Host "Model download failed. Check your internet and run START_MUTABIQ.bat again." -ForegroundColor Red; exit 1 }
& $Ollama pull bge-m3

Write-Host "3/6 Official law texts" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\get_laws.py

Write-Host "4/6 Cloud IP ranges" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\update_cloud_ranges.py
if ($LASTEXITCODE -ne 0) { Write-Host "  (skipped - cloud region detection will be less precise)" -ForegroundColor Yellow }

Write-Host "5/6 Search index" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m core.rag ingest

Write-Host "6/6 Database + demo engagement" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\seed.py

Write-Host "`nSetup done." -ForegroundColor Green
