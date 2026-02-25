param(
    [switch]$Run,
    [string]$Host = "127.0.0.1",
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDir = Join-Path $rootDir "venv"
$envFile = Join-Path $rootDir ".env"
$envExample = Join-Path $rootDir ".env.example"
$requirements = Join-Path $rootDir "requirements.txt"

Write-Host "[1/4] Preparing virtual environment" -ForegroundColor Cyan
if (-not (Test-Path $venvDir)) {
    py -m venv $venvDir
}

$pythonExe = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}

Write-Host "[2/4] Installing dependencies" -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r $requirements

Write-Host "[3/4] Preparing environment file" -ForegroundColor Cyan
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "Created .env from .env.example. Update secrets before production use." -ForegroundColor Yellow
}

Write-Host "[4/4] Setup complete" -ForegroundColor Green

if ($Run) {
    Write-Host "Starting API on $Host`:$Port" -ForegroundColor Cyan
    Set-Location $rootDir
    & $pythonExe -m uvicorn main:app --host $Host --port $Port
} else {
    Write-Host "Run API manually:" -ForegroundColor Green
    Write-Host "  .\venv\Scripts\python.exe -m uvicorn main:app --host $Host --port $Port"
}
