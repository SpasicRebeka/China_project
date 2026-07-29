[CmdletBinding()]
param(
    [switch]$Online
)

$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $releaseRoot '.venv\Scripts\python.exe'
$requirements = Join-Path $releaseRoot 'requirements-runtime.lock'
$wheelhouse = Join-Path $releaseRoot 'wheelhouse'
function Test-SupportedPython {
    param(
        [string]$FilePath,
        [string[]]$PrefixArguments = @()
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        return $false
    }

    try {
        $checkCode = 'import sys; supported = (3, 12) <= sys.version_info[:2] <= (3, 14); raise SystemExit(0 if supported and sys.maxsize > 2**32 else 1)'
        & $FilePath @PrefixArguments -c $checkCode *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-SupportedPython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($minorVersion in @('3.14', '3.13', '3.12')) {
            $launcherArguments = @("-$minorVersion")
            if (Test-SupportedPython -FilePath $launcher.Source -PrefixArguments $launcherArguments) {
                return [pscustomobject]@{
                    FilePath = $launcher.Source
                    PrefixArguments = $launcherArguments
                }
            }
        }
    }

    $candidates = @()
    if ($env:LocalAppData) {
        foreach ($folder in @('Python314', 'Python313', 'Python312')) {
            $candidates += Join-Path $env:LocalAppData "Programs\Python\$folder\python.exe"
        }
    }
    if ($env:ProgramFiles) {
        foreach ($folder in @('Python314', 'Python313', 'Python312')) {
            $candidates += Join-Path $env:ProgramFiles "$folder\python.exe"
        }
    }
    $candidates += @(
        'C:\Python314\python.exe',
        'C:\Python313\python.exe',
        'C:\Python312\python.exe'
    )

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\python.exe') {
        $candidates += $pythonCommand.Source
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-SupportedPython -FilePath $candidate) {
            return [pscustomobject]@{
                FilePath = $candidate
                PrefixArguments = @()
            }
        }
    }

    return $null
}

function Install-SupportedPythonWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }

    Write-Host ''
    Write-Host '64-bit Python 3.12, 3.13, or 3.14 is not installed.' -ForegroundColor Yellow
    $answer = Read-Host 'Install Python 3.12 for the current user with winget now? [y/N]'
    if ($answer.Trim().ToLowerInvariant() -notin @('y', 'yes')) {
        return $false
    }

    & $winget.Source install `
        --id Python.Python.3.12 `
        --exact `
        --scope user `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install Python 3.12 (exit code $LASTEXITCODE)."
    }

    return $true
}

function Invoke-SupportedPython {
    param(
        [pscustomobject]$Runtime,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $prefix = @($Runtime.PrefixArguments)
    & $Runtime.FilePath @prefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

Write-Host 'Checking for 64-bit Python 3.12, 3.13, or 3.14...'
$pythonRuntime = Resolve-SupportedPython

if (-not $pythonRuntime -and (Install-SupportedPythonWithWinget)) {
    $pythonRuntime = Resolve-SupportedPython
}

if (-not $pythonRuntime) {
    throw @'
64-bit Python 3.12, 3.13, or 3.14 is required but was not found.
Install one from https://www.python.org/downloads/ and enable "Add python.exe to PATH",
then run install.cmd again.
'@
}

Write-Host "Using Python: $($pythonRuntime.FilePath) $($pythonRuntime.PrefixArguments -join ' ')"
Invoke-SupportedPython -Runtime $pythonRuntime -Arguments @('-c', 'import sys; print(sys.version)')

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Creating the isolated runtime...'
    Invoke-SupportedPython -Runtime $pythonRuntime -Arguments @('-m', 'venv', (Join-Path $releaseRoot '.venv'))
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "Virtual environment creation failed: $venvPython was not created."
}

if (-not $Online -and (Test-Path -LiteralPath $wheelhouse)) {
    Write-Host 'Installing runtime dependencies from the offline wheelhouse...'
    & $venvPython -m pip install --no-index --find-links $wheelhouse -r $requirements
} else {
    Write-Host 'Installing runtime dependencies from the Python package index...'
    & $venvPython -m pip install -r $requirements
}
if ($LASTEXITCODE -ne 0) {
    throw "Runtime dependency installation failed with exit code $LASTEXITCODE."
}

& $venvPython -c "import fastapi, pydantic, uvicorn; print('Runtime dependency check passed')"
if ($LASTEXITCODE -ne 0) {
    throw 'Runtime dependency check failed.'
}

Write-Host ''
Write-Host 'Installation complete. Double-click start.cmd to launch.' -ForegroundColor Green
