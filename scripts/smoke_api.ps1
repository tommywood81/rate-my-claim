# Quick API smoke test against nginx (default http://localhost:8080)
param([string]$Base = "http://localhost:8080")

$ErrorActionPreference = "Stop"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Get-Json($Uri) {
    $r = Invoke-RestMethod -Uri $Uri -WebSession $session
    if (-not $r.success) { throw "API error at $Uri" }
    return $r.data
}

Write-Host "health..." -ForegroundColor Cyan
Get-Json "$Base/health" | Out-Null

Write-Host "claims list..." -ForegroundColor Cyan
$claims = Get-Json "$Base/api/v1/claims?limit=3"
if ($claims.Count -lt 1) { throw "no claims in DB; run seed" }
$slug = $claims[0].public_slug

Write-Host "claim detail $slug..." -ForegroundColor Cyan
$detail = Get-Json "$Base/api/v1/claims/$slug"
if (-not $detail.evidence_items) { Write-Host "  (no evidence_items on claim; OK for test claims)" }
Get-Json ($Base + '/api/v1/claims/' + $slug + '/graph?depth=1') | Out-Null
Get-Json ($Base + '/api/v1/claims/' + $slug + '/timeline?limit=10') | Out-Null

Write-Host "search..." -ForegroundColor Cyan
Get-Json ($Base + '/api/v1/search/claims?q=exercise&limit=5') | Out-Null

$pwd = $env:SEED_PASSWORD
if (-not $pwd) { $pwd = "SeedDev!ChangeMe123" }

Write-Host "moderator login..." -ForegroundColor Cyan
$login = Invoke-RestMethod -Uri "$Base/api/v1/auth/login" -Method Post -WebSession $session `
    -ContentType "application/json" `
    -Body (@{ username = "seed_moderator"; password = $pwd } | ConvertTo-Json)
if (-not $login.success) { throw "login failed" }

Write-Host "moderation queue..." -ForegroundColor Cyan
$queue = Invoke-RestMethod -Uri "$Base/api/v1/moderation/pending-claims?limit=5" -WebSession $session
if (-not $queue.success) { throw "moderation queue failed" }

Write-Host "metrics..." -ForegroundColor Cyan
$m = Invoke-WebRequest -Uri "$Base/metrics" -UseBasicParsing
if ($m.Content -notmatch "rmc_") { throw "metrics missing rmc_* series" }

Write-Host "OK: API smoke passed" -ForegroundColor Green
