[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$healthUrl = "http://127.0.0.1:$Port/api/health"
$knowledgeUrl = "http://127.0.0.1:$Port/api/v1/knowledge-graph"

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
    $knowledge = Invoke-RestMethod -Uri $knowledgeUrl -TimeoutSec 3
    Write-Host 'Service status: ready' -ForegroundColor Green
    Write-Host "Application version: $($health.version)"
    Write-Host "Knowledge base version: $($knowledge.kb_version)"
    Write-Host "Chief complaint count: $($knowledge.symptoms.Count)"
    Write-Host "Doctor UI: http://127.0.0.1:$Port/doctor/"
} catch {
    Write-Host 'Service status: stopped or unavailable' -ForegroundColor Red
    exit 1
}
