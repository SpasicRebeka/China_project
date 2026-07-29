[CmdletBinding()]
param(
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$distRoot = Join-Path $projectRoot 'dist'
$packageName = "hering-windows-source-v$Version"
$stageRoot = Join-Path $distRoot $packageName
$archivePath = "$stageRoot.zip"
$checksumPath = "$archivePath.sha256"

if (-not $stageRoot.StartsWith("$distRoot\", [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Source package staging directory is outside the project dist directory.'
}

foreach ($target in @($stageRoot, $archivePath, $checksumPath)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

$sourceDirectories = @(
    'apps',
    'docs',
    'ops',
    'packages',
    'services',
    'tests'
)
foreach ($directory in $sourceDirectories) {
    $source = Join-Path $projectRoot $directory
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stageRoot $directory) -Recurse
    }
}

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
$stageKnowledgeRoot = Join-Path $stageRoot $knowledgeDirectoryName
New-Item -ItemType Directory -Force -Path $stageKnowledgeRoot | Out-Null
Copy-Item -LiteralPath $knowledgeFile.FullName `
    -Destination (Join-Path $stageKnowledgeRoot 'knowledge_base.json')

$rootFiles = @(
    '.editorconfig',
    '.gitattributes',
    '.gitignore',
    'eslint.config.js',
    'Makefile',
    'package.json',
    'pnpm-lock.yaml',
    'pnpm-workspace.yaml',
    'README.md',
    'tsconfig.base.json'
)
foreach ($file in $rootFiles) {
    $source = Join-Path $projectRoot $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination $stageRoot
    }
}

$excludedDirectoryNames = @(
    'node_modules',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.vite',
    'coverage',
    'playwright-report',
    'test-results'
)
$directoriesToRemove = Get-ChildItem -LiteralPath $stageRoot -Recurse -Directory -Force |
    Where-Object { $_.Name -in $excludedDirectoryNames } |
    Sort-Object FullName -Descending
foreach ($directory in $directoriesToRemove) {
    $resolved = (Resolve-Path -LiteralPath $directory.FullName).Path
    if (-not $resolved.StartsWith("$stageRoot\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove directory outside staging root: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

$generatedStaticDirectories = @(
    (Join-Path $stageRoot 'services\api\static\doctor'),
    (Join-Path $stageRoot 'services\api\static\patient')
)
foreach ($directory in $generatedStaticDirectories) {
    if (Test-Path -LiteralPath $directory) {
        $resolved = (Resolve-Path -LiteralPath $directory).Path
        if (-not $resolved.StartsWith("$stageRoot\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove generated directory outside staging root: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

$generatedFiles = Get-ChildItem -LiteralPath $stageRoot -Recurse -File -Force |
    Where-Object {
        $_.Extension -in @('.pyc', '.pyo') -or
        $_.Name -like '*.tsbuildinfo' -or
        $_.Name -like '*.db' -or
        $_.Name -like '*.db-*' -or
        $_.Name -like '*.log'
    }
foreach ($file in $generatedFiles) {
    $resolved = (Resolve-Path -LiteralPath $file.FullName).Path
    if (-not $resolved.StartsWith("$stageRoot\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove file outside staging root: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Force
}

$buildTime = Get-Date -Format 'yyyy-MM-dd HH:mm:ss K'
@"
Hering Windows source package
Version: $Version
Created: $buildTime

Package scope:
- Application and API source code
- Tests, documentation, deployment scripts, and lock files
- Runtime knowledge_base.json
- Raw medical research files and unreferenced design images are intentionally excluded

Requirements:
- Windows 10/11 x64
- Node.js 22+
- pnpm 10.12.1 via Corepack
- Python 3.12, 3.13, or 3.14 x64

Quick start:
1. corepack enable
2. pnpm install --frozen-lockfile
3. python -m venv .venv
4. .\.venv\Scripts\python.exe -m pip install -r services\api\requirements.lock
5. pnpm build
6. .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir services\api --host 127.0.0.1 --port 8000
7. Open http://127.0.0.1:8000/doctor/
"@ | Set-Content -LiteralPath (Join-Path $stageRoot 'SOURCE_PACKAGE.txt') -Encoding UTF8

Compress-Archive -LiteralPath $stageRoot -DestinationPath $archivePath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($archivePath))" |
    Set-Content -LiteralPath $checksumPath -Encoding ascii

Write-Host "Source package: $archivePath"
Write-Host "SHA256: $hash"
