[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [ValidateSet('arm64', 'x86_64')]
    [string]$Architecture = 'arm64',
    [ValidateSet('all', '3.12', '3.13', '3.14')]
    [string]$PythonVersion = 'all',
    [switch]$SkipBuild,
    [switch]$SkipWheelhouse
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$distRoot = Join-Path $projectRoot 'dist'
$pythonLabels = if ($PythonVersion -eq 'all') { @('3.14', '3.13', '3.12') } else { @($PythonVersion) }
$pythonTags = $pythonLabels | ForEach-Object { $_.Replace('.', '') }
$pythonName = if ($PythonVersion -eq 'all') { '' } else { "-py$($PythonVersion.Replace('.', ''))" }
$releaseName = "hering-linux-$Architecture$pythonName-v$Version"
$releaseRoot = Join-Path $distRoot $releaseName
$archivePath = "$releaseRoot.tar.gz"
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

foreach ($target in @($releaseRoot, $archivePath, $checksumPath)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

New-Item -ItemType Directory -Force -Path `
    $releaseRoot, `
    (Join-Path $releaseRoot 'services\api\app'), `
    (Join-Path $releaseRoot 'services\api\static'), `
    (Join-Path $releaseRoot 'data'), `
    (Join-Path $releaseRoot 'logs'), `
    (Join-Path $releaseRoot 'ops\kiosk'), `
    (Join-Path $releaseRoot 'ops\systemd') | Out-Null

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
    throw 'knowledge_base.json was not found.'
}
$knowledgeDirectoryName = Split-Path -Leaf $knowledgeFile.DirectoryName
$releaseKnowledgeRoot = Join-Path $releaseRoot $knowledgeDirectoryName
New-Item -ItemType Directory -Force -Path $releaseKnowledgeRoot | Out-Null
Copy-Item -LiteralPath $knowledgeFile.FullName -Destination $releaseKnowledgeRoot

foreach ($file in @('install.sh', 'start.sh', 'stop.sh', 'status.sh', 'requirements-runtime.lock')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $releaseRoot
}
$pythonLabels -join ' ' | Set-Content -LiteralPath (Join-Path $releaseRoot 'SUPPORTED_PYTHON') -Encoding ascii
Copy-Item -LiteralPath (Join-Path $projectRoot 'ops\kiosk\start-kiosk.sh') `
    -Destination (Join-Path $releaseRoot 'ops\kiosk\start-kiosk.sh')
Copy-Item -LiteralPath (Join-Path $projectRoot 'ops\kiosk\kiosk.env.example') `
    -Destination (Join-Path $releaseRoot 'ops\kiosk\kiosk.env.example')
Copy-Item -LiteralPath (Join-Path $projectRoot 'ops\systemd\hering-kiosk.service') `
    -Destination (Join-Path $releaseRoot 'ops\systemd\hering-kiosk.service')
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\Linux-Deployment.md') `
    -Destination (Join-Path $releaseRoot 'DEPLOYMENT.md')

$buildTime = Get-Date -Format 'yyyy-MM-dd HH:mm:ss K'
@"
Hering dual-screen clinical interview system
Version: $Version
Build time: $buildTime
Target: Ubuntu 24.04 $Architecture + Python $($pythonLabels -join ', ')
Knowledge base: $knowledgeDirectoryName/knowledge_base.json
"@ | Set-Content -LiteralPath (Join-Path $releaseRoot 'VERSION.txt') -Encoding UTF8

if (-not $SkipWheelhouse) {
    $wheelhouse = Join-Path $releaseRoot 'wheelhouse'
    New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
    $builderPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $builderPython)) {
        throw 'Project .venv was not found.'
    }
    $platformArguments = if ($Architecture -eq 'arm64') {
        @('--platform', 'manylinux_2_17_aarch64')
    } else {
        @(
            '--platform', 'manylinux_2_28_x86_64',
            '--platform', 'manylinux_2_17_x86_64',
            '--platform', 'manylinux2014_x86_64',
            '--platform', 'manylinux1_x86_64'
        )
    }
    foreach ($pythonTag in $pythonTags) {
        $downloadArguments = @(
            '-m', 'pip', 'download',
            '--only-binary=:all:'
        ) + $platformArguments + @(
            '--python-version', $pythonTag,
            '--implementation', 'cp',
            '--abi', "cp$pythonTag",
            '--dest', $wheelhouse,
            '-r', (Join-Path $PSScriptRoot 'requirements-runtime.lock')
        )
        & $builderPython @downloadArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Linux $Architecture CPython $pythonTag offline dependency download failed."
        }
    }
}

Push-Location $distRoot
try {
    & tar.exe -czf $archivePath $releaseName
    if ($LASTEXITCODE -ne 0) {
        throw 'tar.gz creation failed.'
    }
} finally {
    Pop-Location
}

$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($archivePath))" |
    Set-Content -LiteralPath $checksumPath -Encoding ascii

Write-Host "Release archive: $archivePath"
Write-Host "SHA256: $hash"
