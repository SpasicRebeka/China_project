[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $releaseRoot 'data\hering.pid'
$appRoot = Join-Path $releaseRoot 'services\api'

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'No running service was found.'
    exit 0
}

$serverPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid" -ErrorAction SilentlyContinue

if (-not $process) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host 'The service was already stopped. Stale state was removed.'
    exit 0
}

if ($process.CommandLine -notlike "*$appRoot*") {
    throw "PID $serverPid does not match this installation. Stop was cancelled."
}

Stop-Process -Id $serverPid
Remove-Item -LiteralPath $pidFile -Force
Write-Host 'Service stopped.' -ForegroundColor Green
