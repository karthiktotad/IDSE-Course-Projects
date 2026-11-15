$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'

function Get-CommandPath([string]$name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $command) { throw "Required command '$name' was not found. Install Python 3.11+ and Node.js 20+ then retry." }
    return $command.Source
}

$python = Get-CommandPath 'python'
$node = Get-CommandPath 'node'
$npm = Get-CommandPath 'npm'
$pythonVersionCodeText = (& $python -c 'import sys; print(sys.version_info[0] * 100 + sys.version_info[1])').Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersionCodeText -notmatch '^\d+$') {
    throw "Could not read the Python version from '$python'."
}
$pythonVersionCode = [int]$pythonVersionCodeText
$pythonMajor = [math]::Floor($pythonVersionCode / 100)
$pythonMinor = $pythonVersionCode % 100
$pythonVersion = "$pythonMajor.$pythonMinor"
if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 11)) {
    throw "Python 3.11 or newer is required; found $pythonVersion."
}
$nodeVersion = (& $node --version).Trim().TrimStart('v')
$nodeMajor = [int]($nodeVersion.Split('.')[0])
if ($nodeMajor -lt 20) { throw "Node.js 20 or newer is required; found $nodeVersion." }

$venvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating the backend virtual environment...'
    & $python -m venv (Join-Path $backendPath '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create backend virtual environment.' }
}
Write-Host 'Installing backend dependencies...'
& $venvPython -m pip install -r (Join-Path $backendPath 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

Write-Host 'Installing frontend dependencies...'
Push-Location $frontendPath
try {
    if (Test-Path (Join-Path $frontendPath 'node_modules\vite\bin\vite.js')) {
        Write-Host 'Frontend node_modules already exists; leaving it intact.'
    }
    elseif (-not (Test-Path (Join-Path $frontendPath 'node_modules')) -and (Test-Path (Join-Path $frontendPath 'package-lock.json'))) {
        & $npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    else {
        & $npm install
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
}
finally { Pop-Location }

Write-Host "Setup complete. Python $pythonVersion and Node.js $nodeVersion are ready."
Write-Host 'Start the game with: .\scripts\run.ps1'
