#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the hue-beatsync server natively on this machine.

.DESCRIPTION
    Audio capture needs the host's sound stack (WASAPI on Windows), which a
    Linux container cannot reach - see server/README.md. This is the way to run
    the server on a Windows machine.

.EXAMPLE
    .\scripts\serve.ps1
    .\scripts\serve.ps1 -Port 9000 -Reload
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not on PATH. Install it from https://docs.astral.sh/uv/ and reopen the shell."
}

$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    # --inexact: the workspace shares one .venv, and a plain sync would
    # prune everything outside this package - the dev tools included.
    uv sync --frozen --inexact --package hue-beatsync-server
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE." }

    $uvArgs = @(
        "run", "--package", "hue-beatsync-server",
        "uvicorn", "server.main:app",
        "--host", $BindHost,
        "--port", $Port
    )
    if ($Reload) { $uvArgs += "--reload" }

    Write-Host "hue-beatsync server on http://$BindHost`:$Port (docs at /docs)" -ForegroundColor Green
    & uv @uvArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
