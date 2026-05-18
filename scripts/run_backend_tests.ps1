# Run backend pytest inside Docker (unit + integration).
# Usage: .\scripts\run_backend_tests.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Unit tests..."
docker compose exec -T backend python -m pytest tests/ -q `
  --ignore=tests/test_phase2_pgvector_integration.py `
  --ignore=tests/test_phase3_auth.py `
  --ignore=tests/test_phase4_ingestion.py `
  --ignore=tests/test_phase6_evidence.py `
  --ignore=tests/test_anonymous_submit.py `
  --ignore=tests/test_claim_ai_analysis_flow.py `
  -m "not integration" 2>$null
if ($LASTEXITCODE -ne 0) {
    docker compose exec -T backend python -m pytest tests/test_health.py tests/test_phase5_ai_provider.py tests/test_phase7_search.py tests/test_phase9_graph_timeline.py tests/test_phase10_observability.py tests/test_phase11_unit_services.py tests/test_phase11_celery.py tests/test_phase11_migrations.py -q
}

Write-Host "Integration tests (RUN_PG_INTEGRATION=1)..."
docker compose exec -T -e RUN_PG_INTEGRATION=1 backend python -m pytest tests/ -q
