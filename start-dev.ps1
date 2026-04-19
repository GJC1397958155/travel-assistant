param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Protect-PowerShellLiteral {
    param([string]$Value)

    return "'" + $Value.Replace("'", "''") + "'"
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Join-Path $projectRoot 'Travel Planning Assistant'

if (-not (Test-Path -LiteralPath $frontendRoot)) {
    throw "Frontend directory not found: $frontendRoot"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python was not found in PATH.'
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm was not found in PATH.'
}

$nodeModulesPath = Join-Path $frontendRoot 'node_modules'
if (-not (Test-Path -LiteralPath $nodeModulesPath)) {
    throw 'Frontend dependencies are missing. Run npm install in Travel Planning Assistant first.'
}

$frontendEnvPath = Join-Path $frontendRoot '.env'
if (-not (Test-Path -LiteralPath $frontendEnvPath)) {
    Write-Warning "Frontend .env not found. The app will use the default backend URL http://localhost:$BackendPort"
}

$quotedProjectRoot = Protect-PowerShellLiteral $projectRoot
$quotedFrontendRoot = Protect-PowerShellLiteral $frontendRoot

$backendCommand = @(
    "Set-Location -LiteralPath $quotedProjectRoot",
    "python -m uvicorn rag.api.main:app --reload --host 0.0.0.0 --port $BackendPort"
) -join '; '

$frontendCommand = @(
    "Set-Location -LiteralPath $quotedFrontendRoot",
    "npm run dev -- --host 0.0.0.0 --port $FrontendPort"
) -join '; '

if ($DryRun) {
    Write-Host 'Backend command:'
    Write-Host $backendCommand
    Write-Host ''
    Write-Host 'Frontend command:'
    Write-Host $frontendCommand
    exit 0
}

Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoExit',
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $backendCommand
) | Out-Null

Start-Sleep -Milliseconds 500

Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoExit',
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $frontendCommand
) | Out-Null

Write-Host "Backend window started: http://localhost:$BackendPort"
Write-Host "Frontend window started: http://localhost:$FrontendPort"
Write-Host 'Close each window to stop its server.'
