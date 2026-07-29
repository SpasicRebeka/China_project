[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [switch]$SkipBuild,
    [switch]$SkipWheelhouse
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$distRoot = Join-Path $projectRoot 'dist'
$releaseName = "hering-windows-x64-v$Version"
$releaseRoot = Join-Path $distRoot $releaseName
$archivePath = "$releaseRoot.zip"
$checksumPath = "$archivePath.sha256"

if (-not $releaseRoot.StartsWith("$distRoot\", [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Release directory is outside the project dist directory.'
}

if (-not $SkipBuild) {
    Push-Location $projectRoot
    try {
        & pnpm build
        if ($LASTEXITCODE -ne 0) {
            throw 'Frontend production build failed.'
        }
    } finally {
        Pop-Location
    }
}

if (Test-Path -LiteralPath $releaseRoot) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
if (Test-Path -LiteralPath $checksumPath) {
    Remove-Item -LiteralPath $checksumPath -Force
}

New-Item -ItemType Directory -Force -Path `
    $releaseRoot, `
    (Join-Path $releaseRoot 'services\api\app'), `
    (Join-Path $releaseRoot 'services\api\static'), `
    (Join-Path $releaseRoot 'data'), `
    (Join-Path $releaseRoot 'logs') | Out-Null

Get-ChildItem -LiteralPath (Join-Path $projectRoot 'services\api\app') -Filter '*.py' -File |
    Copy-Item -Destination (Join-Path $releaseRoot 'services\api\app')
Copy-Item -LiteralPath (Join-Path $projectRoot 'services\api\static\doctor') `
    -Destination (Join-Path $releaseRoot 'services\api\static\doctor') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'services\api\static\patient') `
    -Destination (Join-Path $releaseRoot 'services\api\static\patient') -Recurse
$knowledgeFile = Get-ChildItem -LiteralPath $projectRoot -Directory |
    ForEach-Object {
        $candidate = Join-Path $_.FullName 'knowledge_base.json'
        if (Test-Path -LiteralPath $candidate) {
            Get-Item -LiteralPath $candidate
        }
    } |
    Select-Object -First 1
if (-not $knowledgeFile) {
    throw 'knowledge_base.json was not found in a top-level project directory.'
}
$knowledgeDirectoryName = Split-Path -Leaf $knowledgeFile.DirectoryName
$releaseKnowledgeRoot = Join-Path $releaseRoot $knowledgeDirectoryName
New-Item -ItemType Directory -Force -Path $releaseKnowledgeRoot | Out-Null
Copy-Item -LiteralPath $knowledgeFile.FullName `
    -Destination (Join-Path $releaseKnowledgeRoot 'knowledge_base.json')

$runtimeFiles = @(
    'install.ps1', 'start.ps1', 'stop.ps1', 'status.ps1',
    'install.cmd', 'start.cmd', 'stop.cmd', 'status.cmd',
    'requirements-runtime.lock'
)
foreach ($file in $runtimeFiles) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $releaseRoot
}

Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\Windows-Deployment.md') `
    -Destination (Join-Path $releaseRoot 'DEPLOYMENT.md')

$buildTime = Get-Date -Format 'yyyy-MM-dd HH:mm:ss K'
@"
Hering dual-screen clinical interview system
Version: $Version
Build time: $buildTime
Target: Windows x64 + Python 3.12-3.14
Knowledge base: $knowledgeDirectoryName/knowledge_base.json
"@ | Set-Content -LiteralPath (Join-Path $releaseRoot 'VERSION.txt') -Encoding UTF8

if (-not $SkipWheelhouse) {
    $wheelhouse = Join-Path $releaseRoot 'wheelhouse'
    New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
    $builderPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $builderPython)) {
        throw 'Project .venv was not found; the offline wheelhouse cannot be built.'
    }
    foreach ($pythonTag in @('312', '313', '314')) {
        & $builderPython -m pip download `
            --only-binary=:all: `
            --platform win_amd64 `
            --python-version $pythonTag `
            --implementation cp `
            --abi "cp$pythonTag" `
            --dest $wheelhouse `
            -r (Join-Path $PSScriptRoot 'requirements-runtime.lock')
        if ($LASTEXITCODE -ne 0) {
            throw "Windows x64 CPython $pythonTag offline dependency download failed."
        }
    }
}

Compress-Archive -LiteralPath $releaseRoot -DestinationPath $archivePath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($archivePath))" |
    Set-Content -LiteralPath $checksumPath -Encoding ascii

Write-Host "Release directory: $releaseRoot"
Write-Host "Release archive: $archivePath"
Write-Host "SHA256: $hash"
