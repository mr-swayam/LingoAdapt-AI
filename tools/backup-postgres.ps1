# Backs up the lingoadapt Postgres database to a timestamped, compressed
# custom-format dump (tools/backups/) using pg_dump - restorable with
# tools/restore-postgres.ps1 or `pg_restore` directly.
#
# Usage: .\tools\backup-postgres.ps1 [-Database lingoadapt_dev]

param(
    [string]$Database = "lingoadapt_dev",
    [string]$PgHost = "localhost",
    [string]$PgPort = "5432",
    [string]$PgUser = "lingoadapt"
)

$ErrorActionPreference = "Stop"

function Find-PgDump {
    $onPath = Get-Command pg_dump -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending
    foreach ($dir in $candidates) {
        $exe = Join-Path $dir.FullName "bin\pg_dump.exe"
        if (Test-Path $exe) { return $exe }
    }

    throw "pg_dump not found on PATH or under C:\Program Files\PostgreSQL\*\bin. Install the PostgreSQL client tools."
}

$pgDump = Find-PgDump
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupDir = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $backupDir "$Database-$timestamp.dump"

Write-Host "Backing up '$Database' to $outFile ..."
& $pgDump --host=$PgHost --port=$PgPort --username=$PgUser --format=custom --file=$outFile $Database
if ($LASTEXITCODE -ne 0) { throw "pg_dump exited with code $LASTEXITCODE" }

$size = (Get-Item $outFile).Length
Write-Host "Backup complete: $outFile ($([math]::Round($size / 1KB, 1)) KB)"
