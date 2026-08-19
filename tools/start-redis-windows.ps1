# Downloads (if needed) and starts a portable Redis-for-Windows server.
# No admin/elevation required - runs as a plain foreground process, not a Windows service.
# Use this if Docker Desktop and an installed Redis/Memurai service aren't available.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$redisDir = Join-Path $root "redis-windows"
$version = "5.0.14.1"
$zipUrl = "https://github.com/tporadowski/redis/releases/download/v$version/Redis-x64-$version.zip"

if (-not (Test-Path (Join-Path $redisDir "redis-server.exe"))) {
    Write-Host "Downloading portable Redis $version for Windows..."
    New-Item -ItemType Directory -Force -Path $redisDir | Out-Null
    $zipPath = Join-Path $redisDir "redis.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $redisDir -Force
    Remove-Item $zipPath
}

Write-Host "Starting redis-server on port 6379 (Ctrl+C to stop)..."
& (Join-Path $redisDir "redis-server.exe") (Join-Path $redisDir "redis.windows.conf")
