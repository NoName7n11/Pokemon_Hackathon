param(
    [string]$Python = "python",
    [string]$Environment = ".venv-plan1"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EnvironmentPath = Join-Path $RepoRoot $Environment

if (-not (Test-Path -LiteralPath $EnvironmentPath)) {
    & $Python -m venv $EnvironmentPath
}

$EnvironmentPython = Join-Path $EnvironmentPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $EnvironmentPython)) {
    throw "Plan 1 virtual environment was not created at $EnvironmentPath"
}

& $EnvironmentPython (Join-Path $PSScriptRoot "verify_environment.py")
& $EnvironmentPython -m unittest discover -s (Join-Path $RepoRoot "plan_1\tests") -v

Write-Output "Plan 1 environment ready: $EnvironmentPath"
