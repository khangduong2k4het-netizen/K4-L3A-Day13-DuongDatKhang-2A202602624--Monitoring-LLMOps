param(
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'),
    [ValidateRange(1, 100)][int]$Concurrency = 5
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$apiProcess = $null
$previousLogPath = $env:LOG_PATH
$previousEncoding = $env:PYTHONIOENCODING
Push-Location $repoRoot
try {
    # Fail before archiving anything if the interpreter cannot run.
    & $Python -c 'import uvicorn, httpx, fastapi, structlog, dotenv'
    if ($LASTEXITCODE -ne 0) { throw 'Python/dependencies unavailable. Repair the environment first.' }

    # Do not stop an unrelated process or rotate a log while an API is writing it.
    $probe = [Net.Sockets.TcpClient]::new()
    try {
        $portInUse = $false
        try { $probe.Connect('127.0.0.1', 8000); $portInUse = $true } catch {}
    } finally { $probe.Dispose() }
    if ($portInUse) { throw 'Port 8000 is in use. Stop the existing API (Ctrl+C), then rerun this script.' }

    $runId = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
    $archiveDir = Join-Path $repoRoot "data/log-runs/$runId"
    New-Item -ItemType Directory -Path $archiveDir | Out-Null
    $activeLog = Join-Path $repoRoot 'data/logs.jsonl'
    $env:PYTHONIOENCODING = 'utf-8'
    if (Test-Path -LiteralPath $activeLog) {
        Write-Host "`n=== BASELINE: OLD LOGS (not the final result) ==="
        & $Python scripts/validate_logs.py | Tee-Object -FilePath (Join-Path $archiveDir 'baseline-validator.txt')
        if ($LASTEXITCODE -ne 0) {
            'Baseline validator could not evaluate the old log; see its output.' |
                Add-Content -LiteralPath (Join-Path $archiveDir 'baseline-validator.txt')
        }
        # Both resolved paths are inside the repository data directory; preserve the old file.
        Move-Item -LiteralPath $activeLog -Destination (Join-Path $archiveDir 'baseline.jsonl')
    } else {
        'No previous data/logs.jsonl exists. No baseline was measured.' |
            Set-Content -LiteralPath (Join-Path $archiveDir 'baseline-validator.txt')
    }

    # Override a custom .env LOG_PATH so the API and validator use the same file.
    $env:LOG_PATH = $activeLog
    $apiProcess = Start-Process -FilePath $Python -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--env-file', '.env',
        '--host', '127.0.0.1', '--port', '8000'
    ) -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $archiveDir 'api-stdout.txt') `
        -RedirectStandardError (Join-Path $archiveDir 'api-stderr.txt')

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($apiProcess.HasExited) { throw "API exited. Inspect $archiveDir/api-stderr.txt" }
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1
            if ($health.ok) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'API did not become ready.' }

    Write-Host "`n=== NEW WORKLOAD: generating fresh logs ==="
    & $Python scripts/load_test.py --concurrency $Concurrency |
        Tee-Object -FilePath (Join-Path $archiveDir 'load-test.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Load test failed.' }
    # load_test.py currently prints request errors without a nonzero exit code.
    $loadOutput = Get-Content -LiteralPath (Join-Path $archiveDir 'load-test.txt')
    if (-not ($loadOutput -match '^\[200\]') -or ($loadOutput -match '^(Error:|\[(?!200\])\d+\])')) {
        throw 'Workload contains failed requests; inspect load-test.txt before accepting the result.'
    }

    Write-Host "`n=== FINAL SCORECARD: FRESH data/logs.jsonl ==="
    & $Python scripts/validate_logs.py |
        Tee-Object -FilePath (Join-Path $archiveDir 'current-validator.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Log validation failed.' }
    Write-Host "Results: $archiveDir"
    Write-Host 'Use current-validator.txt as the final result; baseline-validator.txt contains the old score.'
    Write-Host 'Review the FINAL score above (minimum 80/100) and PII leaks (must be 0).'
    Write-Host 'Fresh logs remain in data/logs.jsonl. The temporary API will now stop.'
} finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id
    }
    $env:LOG_PATH = $previousLogPath
    $env:PYTHONIOENCODING = $previousEncoding
    Pop-Location
}
