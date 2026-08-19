# Restores a Postgres custom-format dump produced by backup-postgres.ps1
# into a target database (created if it doesn't already exist). Existing
# data in the target database is NOT dropped first - pg_restore is run
# with --clean --if-exists so it drops/recreates each object it's about to
# restore, but an unrelated table left over from something else would
# survive. For a true from-scratch restore drill, restore into a fresh
# database name.
#
# Usage: .\tools\restore-postgres.ps1 -DumpFile .\tools\backups\lingoadapt_dev-20260101-000000.dump [-Database lingoadapt_dev]

param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
    [string]$Database = "lingoadapt_dev",
    [string]$PgHost = "localhost",
    [string]$PgPort = "5432",
    [string]$PgUser = "lingoadapt"
)

$ErrorActionPreference = "Stop"

function Find-PgTool([string]$Name) {
    $onPath = Get-Command $Name -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending
    foreach ($dir in $candidates) {
        $exe = Join-Path $dir.FullName "bin\$Name.exe"
        if (Test-Path $exe) { return $exe }
    }

    throw "$Name not found on PATH or under C:\Program Files\PostgreSQL\*\bin."
}

if (-not (Test-Path $DumpFile)) {
    throw "Dump file not found: $DumpFile"
}

$pgRestore = Find-PgTool "pg_restore"
$createdb = Find-PgTool "createdb"

& $createdb --host=$PgHost --port=$PgPort --username=$PgUser $Database 2>$null
# createdb fails harmlessly if the database already exists - that's fine,
# pg_restore --clean below handles restoring into an existing database.

Write-Host "Restoring $DumpFile into '$Database' ..."
& $pgRestore --host=$PgHost --port=$PgPort --username=$PgUser --dbname=$Database --clean --if-exists --no-owner $DumpFile
if ($LASTEXITCODE -ne 0) { throw "pg_restore exited with code $LASTEXITCODE" }

Write-Host "Restore complete."
