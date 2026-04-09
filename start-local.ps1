# start-local.ps1 — Arranca el sistema en modo local (sin Docker)
# Uso: click derecho -> "Run with PowerShell"  o desde terminal: .\start-local.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  SRE Incident Triage Agent — Local Dev     " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  [!] LLM arranca en modo stub. Configuralo desde la UI:" -ForegroundColor Yellow
Write-Host "      http://localhost:5173 -> Config -> LLM Provider" -ForegroundColor Yellow
Write-Host ""

# ── Configuracion para entorno local (sin Docker, sin Postgres, sin Langfuse) ──
# Nota: LLM_PROVIDER, GEMINI_*, LLM_FALLBACK_PROVIDER y circuit-breaker vars
#       ya no son leidas por el backend (Settings.extra="ignore"). El proveedor
#       LLM se configura desde la UI despues del arranque (Config-from-DB pattern).
$env:LLM_CONFIG_PROVIDER = "memory"

$env:STORAGE_PROVIDER  = "memory"
$env:CONTEXT_PROVIDER  = "static"
$env:ESHOP_CONTEXT_DIR = "$RepoRoot\eshop-context"

$env:TICKET_PROVIDER      = "mock"
$env:NOTIFY_PROVIDER      = "mock"
$env:MOCK_SERVICES_URL    = "http://localhost:9000"
$env:SRE_AGENT_WEBHOOK_URL = "http://localhost:8000/webhooks/resolution"

$env:LANGFUSE_ENABLED = "false"

$env:LOG_LEVEL                    = "INFO"
$env:APP_ENV                      = "development"
$env:MAX_UPLOAD_SIZE_MB           = "5"
$env:GUARDRAILS_LLM_JUDGE_ENABLED = "true"

# ── 1. Arrancar mock-services en ventana separada ──
Write-Host "[1/3] Arrancando mock-services en http://localhost:9000 ..." -ForegroundColor Yellow
$mockDir = "$RepoRoot\services\mock-services"
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host 'MOCK-SERVICES' -ForegroundColor Magenta; cd '$mockDir'; py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 9000"

Write-Host "    Esperando 4 segundos para que mock-services levante..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# ── 2. Arrancar frontend React en ventana separada ──
Write-Host "[2/3] Arrancando frontend React en http://localhost:5173 ..." -ForegroundColor Yellow
$webDir = "$RepoRoot\services\sre-web"
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host 'SRE-WEB (React/Vite)' -ForegroundColor Cyan; cd '$webDir'; npm run dev"

Write-Host "    Esperando 3 segundos para que el frontend compile..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# ── 3. Arrancar sre-agent ──
Write-Host "[3/3] Arrancando sre-agent en http://localhost:8000 ..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  >>> Abre tu navegador en:  http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "  Para detener: presiona Ctrl+C en esta ventana" -ForegroundColor Gray
Write-Host "  Luego cierra la ventana de mock-services y la ventana del frontend" -ForegroundColor Gray
Write-Host ""

Set-Location "$RepoRoot\services\sre-agent"
py -3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
