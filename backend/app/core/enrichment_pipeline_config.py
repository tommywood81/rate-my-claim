"""YAML-tunable enrichment pipeline hyperparameters (non-secret)."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = _BACKEND_DIR / "config" / "enrichment_pipeline.yaml"


class RetrievalStageConfig(BaseModel):
    """Prompt context limits for assessment (legacy neighbor keys kept for compatibility)."""

    borrow_from_similar_claims: bool = False
    min_similarity: float = Field(default=0.72, ge=0.0, le=1.0)
    similar_claim_search_limit: int = Field(default=12, ge=1, le=50)
    max_similar_claims: int = Field(default=6, ge=1, le=30)
    evidence_line_limit: int = Field(default=10, ge=1, le=50)
    excerpt_max_chars: int = Field(default=500, ge=80, le=4000)
    context_max_chars: int = Field(default=6000, ge=500, le=32000)
    digest_line_limit: int = Field(default=10, ge=1, le=50)


class SourceDiscoveryConfig(BaseModel):
    """One-shot reputable web source fetch during enrichment (no neighbor borrow)."""

    enabled: bool = True
    max_sources: int = Field(default=3, ge=0, le=10)
    excerpt_max_chars: int = Field(default=320, ge=80, le=2000)
    min_publisher_credibility: float = Field(default=0.70, ge=0.0, le=1.0)
    min_excerpt_keyword_overlap: int = Field(
        default=1,
        ge=0,
        le=8,
        description="Min claim keywords that must appear in saved excerpt (0 = disabled)",
    )
    max_urls_per_domain: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Allow multiple pages from same allowlisted domain (e.g. Wikipedia)",
    )
    max_candidate_fetches: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Max allowlisted URLs to fetch while filling max_sources",
    )
    search_result_limit: int = Field(default=20, ge=3, le=40)
    fetch_timeout_seconds: float = Field(default=10.0, ge=2.0, le=60.0)
    allowlist_config_path: str = Field(
        default="config/reputable_sources.yaml",
        description="Relative to backend root unless absolute",
    )


class CrawlStageConfig(BaseModel):
    """URL fetch parallelism, timeouts, and hot-path embedding policy."""

    max_url_jobs: int = Field(default=6, ge=0, le=30)
    parallel_fetches: int = Field(default=4, ge=1, le=16)
    per_url_timeout_seconds: float = Field(default=8.0, ge=1.0, le=120.0)
    total_crawl_budget_seconds: float = Field(default=25.0, ge=2.0, le=300.0)
    http_timeout_seconds: float = Field(default=10.0, ge=2.0, le=120.0)
    max_extracted_chars: int = Field(default=18000, ge=1000, le=200000)
    artifact_excerpt_chars: int = Field(default=2500, ge=200, le=20000)
    embed_document_on_hot_path: bool = True
    skip_chunk_embeddings_on_hot_path: bool = True
    max_chunks_to_embed: int = Field(default=2, ge=0, le=50)


class AIStageConfig(BaseModel):
    """Model call strategy for assessment (latency vs quality)."""

    use_combined_assessment: bool = True
    skip_evidence_summary_call: bool = True
    use_provisional_verdict_without_corpus: bool = False
    prompt_claim_max_chars: int = Field(default=8000, ge=500, le=32000)


class TruthResolutionConfig(BaseModel):
    """
    When to show public truth as inconclusive (~1% target).

    Most claims resolve to supported/refuted from model scores; only narrow middling
    or high-controversy bands stay inconclusive.
    """

    supported_aggregate_min: float = Field(default=0.55, ge=0.0, le=1.0)
    refuted_aggregate_max: float = Field(default=0.45, ge=0.0, le=1.0)
    inconclusive_aggregate_low: float = Field(default=0.47, ge=0.0, le=1.0)
    inconclusive_aggregate_high: float = Field(default=0.53, ge=0.0, le=1.0)
    high_controversy_for_inconclusive: float = Field(default=0.72, ge=0.0, le=1.0)
    contested_aggregate_low: float = Field(default=0.42, ge=0.0, le=1.0)
    contested_aggregate_high: float = Field(default=0.58, ge=0.0, le=1.0)
    weak_evidence_inconclusive_below: float = Field(
        default=0.25,
        ge=0.0,
        le=0.5,
        description="supported/refuted with aggregate below this become inconclusive",
    )


class EnrichmentPipelineConfig(BaseModel):
    """Full enrichment pipeline tuning document."""

    retrieval: RetrievalStageConfig = Field(default_factory=RetrievalStageConfig)
    sources: SourceDiscoveryConfig = Field(default_factory=SourceDiscoveryConfig)
    crawl: CrawlStageConfig = Field(default_factory=CrawlStageConfig)
    ai: AIStageConfig = Field(default_factory=AIStageConfig)
    truth: TruthResolutionConfig = Field(default_factory=TruthResolutionConfig)


def _resolve_config_path() -> Path:
    raw = os.environ.get("ENRICHMENT_PIPELINE_CONFIG", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_CONFIG_PATH


def load_enrichment_pipeline_config(path: Path | None = None) -> EnrichmentPipelineConfig:
    """Load and validate pipeline YAML; missing file yields defaults."""
    cfg_path = path or _resolve_config_path()
    if not cfg_path.is_file():
        logger.warning(
            "enrichment_pipeline_config_missing",
            extra={"path": str(cfg_path), "using": "defaults"},
        )
        return EnrichmentPipelineConfig()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if raw is None:
        return EnrichmentPipelineConfig()
    if not isinstance(raw, dict):
        raise ValueError(f"enrichment pipeline config must be a mapping: {cfg_path}")
    return EnrichmentPipelineConfig.model_validate(raw)


@lru_cache
def get_enrichment_pipeline_config() -> EnrichmentPipelineConfig:
    """Process-wide cached pipeline config (restart workers after YAML edits)."""
    cfg = load_enrichment_pipeline_config()
    logger.info(
        "enrichment_pipeline_config_loaded",
        extra={
            "path": str(_resolve_config_path()),
            "combined_assessment": cfg.ai.use_combined_assessment,
            "parallel_fetches": cfg.crawl.parallel_fetches,
            "evidence_line_limit": cfg.retrieval.evidence_line_limit,
        },
    )
    return cfg


def clear_enrichment_pipeline_config_cache() -> None:
    """Clear cached config (tests)."""
    get_enrichment_pipeline_config.cache_clear()
