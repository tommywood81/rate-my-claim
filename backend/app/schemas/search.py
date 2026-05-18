"""Search API DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SearchScoreBreakdown(BaseModel):
    """Normalized hybrid ranking components."""

    semantic_similarity: float
    text_relevance: float
    evidence_quality: float
    confidence_score: float
    freshness_score: float
    relationship_density: float
    final_score: float


class ClaimSearchHitResponse(BaseModel):
    """Claim search result with relevance metadata."""

    id: UUID
    public_slug: str
    canonical_claim_text: str
    status: str
    confidence_score: float
    evidence_count: int
    discovery_score: int
    updated_at: datetime
    scores: SearchScoreBreakdown
