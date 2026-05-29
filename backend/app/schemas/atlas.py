"""Claim embedding atlas (3D semantic space) API DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClaimAtlasPointResponse(BaseModel):
    """One claim in projected embedding space."""

    id: UUID
    public_slug: str
    label: str
    status: str
    confidence_score: float
    controversy_score: float
    evidence_score: float
    freshness_score: float
    evidence_count: int
    truth_label: str = Field(description="supported, refuted, or unclear")
    x: float
    y: float
    z: float


class ClaimAtlasResponse(BaseModel):
    """3D map of indexed claims derived from stored embeddings."""

    points: list[ClaimAtlasPointResponse]
    method: str = Field(description="Projection method, e.g. pca_3d")
    embedding_dimensions: int
    total_indexed: int
    projected_count: int
    computed_at: datetime
    note: str = Field(
        default=(
            "Positions are a 3D PCA projection of semantic embeddings — nearby points "
            "tend to discuss similar topics. This is a similarity map, not a literal "
            "coordinate system."
        )
    )
