$ErrorActionPreference = "Stop"

Write-Host "=== STARTING E2E INTEGRATION TEST RUNNER ===" -ForegroundColor Cyan

# 1. Start Backend FastAPI
Write-Host "Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$env:PYTHONPATH = "E:\SMART-LEARNING-PRO\backend"
$backendProc = Start-Process -FilePath "E:\SMART-LEARNING-PRO\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -PassThru

# 2. Start Frontend Next.js
Write-Host "Starting Next.js Frontend on http://127.0.0.1:3000..." -ForegroundColor Yellow
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run start" `
    -WorkingDirectory "E:\SMART-LEARNING-PRO\frontend" `
    -PassThru

$exitCode = 1

try {
    # 3. Wait for Backend
    Write-Host "Waiting for Backend health check..." -ForegroundColor Yellow
    $backendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get -TimeoutSec 2
            if ($resp.status -eq "healthy") {
                $backendReady = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $backendReady) {
        throw "FastAPI backend failed to become ready on port 8000!"
    }
    Write-Host "Backend is READY!" -ForegroundColor Green

    # 4. Wait for Frontend
    Write-Host "Waiting for Frontend to respond..." -ForegroundColor Yellow
    $frontendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                $frontendReady = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $frontendReady) {
        throw "Next.js frontend failed to become ready on port 3000!"
    }
    Write-Host "Frontend is READY!" -ForegroundColor Green

    # 5. Run Playwright E2E Tests
    Write-Host "Executing Playwright E2E Test Suite..." -ForegroundColor Cyan
    Push-Location "E:\SMART-LEARNING-PRO\frontend"
    try {
        & npx playwright test
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    Write-Host "Cleaning up server processes..." -ForegroundColor Yellow
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        # Kill cmd and node processes on port 3000
        Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    # Clean up any lingering node or uvicorn
    Get-Process -Name "node", "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -eq $backendProc.Id -or $_.Id -eq $frontendProc.Id
    } | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host "=== E2E TESTS COMPLETED WITH EXIT CODE: $exitCode ===" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })
exit $exitCode
