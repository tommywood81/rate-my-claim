"""Enrichment pipeline YAML config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.enrichment_pipeline_config import (
    EnrichmentPipelineConfig,
    clear_enrichment_pipeline_config_cache,
    load_enrichment_pipeline_config,
)


def test_default_config_values() -> None:
    cfg = EnrichmentPipelineConfig()
    assert cfg.ai.use_combined_assessment is True
    assert cfg.crawl.parallel_fetches >= 1
    assert cfg.retrieval.evidence_line_limit == 10


def test_load_repo_yaml() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "enrichment_pipeline.yaml"
    cfg = load_enrichment_pipeline_config(path)
    assert cfg.crawl.skip_chunk_embeddings_on_hot_path is True
    assert cfg.retrieval.min_similarity == 0.72


def test_env_override_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "pipeline.yaml"
    custom.write_text(
        "crawl:\n  parallel_fetches: 2\nai:\n  use_combined_assessment: false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENRICHMENT_PIPELINE_CONFIG", str(custom))
    clear_enrichment_pipeline_config_cache()
    cfg = load_enrichment_pipeline_config()
    assert cfg.crawl.parallel_fetches == 2
    assert cfg.ai.use_combined_assessment is False
    clear_enrichment_pipeline_config_cache()
