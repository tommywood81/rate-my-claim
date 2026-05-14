"""Claim-related API DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateClaimRequest(BaseModel):
    """Submit a new empirical claim for enrichment."""

    raw_claim_text: str = Field(min_length=10, max_length=8000)
    source_urls: list[str] = Field(default_factory=list, max_length=20)


class PendingClaimResponse(BaseModel):
    """Pipeline state for a submitted claim."""

    id: UUID
    raw_claim_text: str
    processing_status: str
    canonical_candidate_text: str | None
    ai_summary: str | None
    duplicate_candidate_ids: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimListItemResponse(BaseModel):
    """Summary row for browse and discovery."""

    id: UUID
    public_slug: str
    canonical_claim_text: str
    status: str
    confidence_score: float
    evidence_count: int
    discovery_score: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    """Evidence card for claim detail."""

    id: UUID
    title: str
    url: str | None
    publisher: str | None
    stance: str
    credibility_score: float
    summary: str | None
    retrieval_timestamp: datetime | None

    model_config = {"from_attributes": True}


class AIAnalysisResponse(BaseModel):
    """Isolated AI output for display."""

    id: UUID
    analysis_type: str
    model_name: str
    provider: str
    generated_text: str
    structured_payload: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimDetailResponse(BaseModel):
    """Full public claim payload."""

    id: UUID
    public_slug: str
    canonical_claim_text: str
    status: str
    confidence_score: float
    controversy_score: float
    evidence_score: float
    freshness_score: float
    evidence_count: int
    discovery_score: int
    aliases: list[str]
    evidence_supporting: list[EvidenceResponse]
    evidence_contradicting: list[EvidenceResponse]
    evidence_contextual: list[EvidenceResponse]
    ai_analyses: list[AIAnalysisResponse]
    related_slugs: list[str]

    model_config = {"from_attributes": True}


class VoteRequest(BaseModel):
    """Discovery vote body."""

    value: int = Field(ge=-1, le=1, description="1 upvote, -1 downvote, 0 remove vote")


class ModerationActionRequest(BaseModel):
    """Moderator action on pending or approved claims."""

    action_type: str
    target_type: str = Field(description="pending_claim or claim")
    target_id: UUID
    explanation: str | None = Field(default=None, max_length=8000)
    payload: dict | None = None
