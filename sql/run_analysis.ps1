<#
.SYNOPSIS  Runs the analytical SQL files in sql/analysis (joins, GROUP BY/HAVING, CASE, subqueries, CTEs, window functions, KPI queries, DDL/DML examples).
.EXAMPLE   powershell -ExecutionPolicy Bypass -File sql\run_analysis.ps1 -File 05_window_functions.sql
.NOTES     Read-only except 07_ddl_dml_examples.sql, which works in a throwaway sandbox schema. Synthetic, sampled-simulation data.
#>
[CmdletBinding()]
param([string]$PgHost = "localhost", [int]$Port = 5432, [string]$User = "postgres", [string]$Database = "irctc_analytics", [string]$PsqlPath = "", [string]$File = "")
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $PsqlPath) { $c = Get-Command psql -ErrorAction SilentlyContinue; if ($c) { $PsqlPath = $c.Source } else { $PsqlPath = (Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" | Sort-Object { [int]($_.Directory.Parent.Name) } -Descending | Select-Object -First 1).FullName } }
$env:PGCLIENTENCODING = "UTF8"
$files = if ($File) { @("sql/analysis/$File") } else { (Get-ChildItem "sql/analysis/*.sql" | Sort-Object Name | ForEach-Object { "sql/analysis/$($_.Name)" }) }
foreach ($f in $files) {
    Write-Host "=== $f ===" -ForegroundColor Cyan
    & $PsqlPath -X -h $PgHost -p $Port -U $User -d $Database -v ON_ERROR_STOP=1 -f $f
    if ($LASTEXITCODE -ne 0) { throw "$f failed (exit code $LASTEXITCODE)" }
}
