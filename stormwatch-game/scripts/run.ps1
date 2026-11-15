$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$python = Join-Path $backendPath '.venv\Scripts\python.exe'
$nodeCommand = (Get-Command node -ErrorAction Stop).Source
$viteEntry = Join-Path $frontendPath 'node_modules\vite\bin\vite.js'
$logRoot = Join-Path $env:TEMP 'stormwatch-logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$backendOut = Join-Path $logRoot 'backend.log'
$backendErr = Join-Path $logRoot 'backend-error.log'
$frontendOut = Join-Path $logRoot 'frontend.log'
$frontendErr = Join-Path $logRoot 'frontend-error.log'

function Test-BackendReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.service -eq 'stormwatch-simulation'
    }
    catch { return $false }
}

function Test-FrontendReady {
    try {
        $page = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 2
        return $page.StatusCode -eq 200
    }
    catch { return $false }
}

function Test-PortListening([int]$port) {
    $probe = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $probe.BeginConnect('127.0.0.1', $port, $null, $null)
        return $connect.AsyncWaitHandle.WaitOne(250) -and $probe.Connected
    }
    finally { $probe.Dispose() }
}

$backendReady = Test-BackendReady
$frontendReady = Test-FrontendReady
if (-not $backendReady -and (Test-PortListening 8000)) {
    throw 'Port 8000 is occupied by a service that did not identify itself as the STORMWATCH backend.'
}
if (-not $frontendReady -and (Test-PortListening 5173)) {
    throw 'Port 5173 is occupied by a service that did not return the STORMWATCH frontend.'
}
if (-not $backendReady -and -not (Test-Path $python)) { throw 'Backend virtual environment is missing. Run .\scripts\setup.ps1 first.' }
if (-not $frontendReady -and -not (Test-Path $viteEntry)) { throw 'Frontend dependencies are missing. Run .\scripts\setup.ps1 first.' }

$backendProcess = $null
$frontendProcess = $null
try {
    if (-not $backendReady) {
        $backendProcess = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendPath -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
    }
    if (-not $frontendReady) {
        $frontendArgs = @('"' + $viteEntry + '"','--host','127.0.0.1','--port','5173','--strictPort')
        $frontendProcess = Start-Process -FilePath $nodeCommand -ArgumentList $frontendArgs -WorkingDirectory $frontendPath -PassThru -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($backendProcess -and $backendProcess.HasExited) { throw "Backend stopped during startup. See $backendErr" }
        if ($frontendProcess -and $frontendProcess.HasExited) { throw "Frontend stopped during startup. See $frontendErr" }
        if ((Test-BackendReady) -and (Test-FrontendReady)) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Services did not become ready. Logs: $logRoot" }

    Write-Host 'STORMWATCH is running locally.'
    Write-Host 'Game:    http://127.0.0.1:5173'
    Write-Host 'Backend: http://127.0.0.1:8000'
    if ($backendProcess -or $frontendProcess) {
        Write-Host "Logs:    $logRoot"
        Write-Host 'Press Ctrl+C here to stop services started by this script. Existing services are left running.'
        while ($true) {
            if ($backendProcess -and $backendProcess.HasExited) { throw "Backend exited. See $backendErr" }
            if ($frontendProcess -and $frontendProcess.HasExited) { throw "Frontend exited. See $frontendErr" }
            Start-Sleep -Seconds 1
        }
    }
    else {
        Write-Host 'Both services were already running; no duplicate processes were started.'
    }
}
finally {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
