# run_tests.ps1
# One-click test runner for Windows PowerShell
# This script sets up the environment and runs the full test suite

param(
    [switch]$Coverage,
    [switch]$Verbose
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Content Moderation Service - Test Runner" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Detect Python executable
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "ERROR: Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Green
& $pythonCmd --version
Write-Host ""

# Create/activate virtual environment (skip if already in one)
$VENV_PATH = "venv"
if (-not (Test-Path $VENV_PATH)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv $VENV_PATH
}

# Note: We'll use the system Python if venv setup fails
Write-Host "Using system Python (dependencies already installed)..." -ForegroundColor Green

# Run pytest
Write-Host "Running test suite..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$testArgs = @("tests/", "-v")

if ($Coverage) {
    $testArgs += @("--cov=src", "--cov=moderation_service", "--cov-report=term-missing")
    Write-Host "Running with coverage report..." -ForegroundColor Yellow
}

if ($Verbose) {
    $testArgs += @("-vv", "-s")
}

& $pythonCmd -m pytest @testArgs

$testResult = $LASTEXITCODE

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
if ($testResult -eq 0) {
    Write-Host "All tests PASSED!" -ForegroundColor Green
} else {
    Write-Host "Some tests FAILED (exit code: $testResult)" -ForegroundColor Red
}
Write-Host "================================================" -ForegroundColor Cyan

exit $testResult
