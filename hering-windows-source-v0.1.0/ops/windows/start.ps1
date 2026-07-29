[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $releaseRoot '.venv\Scripts\python.exe'
$appRoot = Join-Path $releaseRoot 'services\api'
$dataRoot = Join-Path $releaseRoot 'data'
$logRoot = Join-Path $releaseRoot 'logs'
$pidFile = Join-Path $dataRoot 'hering.pid'
$healthUrl = "http://127.0.0.1:$Port/api/health"
$doctorUrl = "http://127.0.0.1:$Port/doctor/"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Runtime is not installed. Run install.cmd first.'
}

New-Item -ItemType Directory -Force -Path $dataRoot, $logRoot | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $existingPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Host "The service is already running. PID: $existingPid"
        if (-not $NoBrowser) {
            Start-Process $doctorUrl
        }
        exit 0
    }
    Remove-Item -LiteralPath $pidFile -Force
}

$occupied = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($occupied) {
    throw "Port $Port is occupied. Try: powershell -ExecutionPolicy Bypass -File .\start.ps1 -Port 8080"
}

$stdoutLog = Join-Path $logRoot 'server.out.log'
$stderrLog = Join-Path $logRoot 'server.err.log'
$arguments = @(
    '-m', 'uvicorn', 'app.main:app',
    '--app-dir', "`"$appRoot`"",
    '--host', '127.0.0.1',
    '--port', $Port.ToString()
)

$server = Start-Process `
    -FilePath $venvPython `
    -ArgumentList $arguments `
    -WorkingDirectory $releaseRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $server.Id -Encoding ascii

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq 'ok') {
            $ready = $true
            break
        }
    } catch {
        if ($server.HasExited) {
            break
        }
    }
}

if (-not $ready) {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw "Service startup failed. Check the log: $stderrLog"
}

Write-Host "Service ready: $doctorUrl" -ForegroundColor Green
Write-Host "PID: $($server.Id)"
Write-Host "Logs: $logRoot"

if (-not $NoBrowser) {
    Start-Process $doctorUrl
}
