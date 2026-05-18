"""Claim relationship graph payloads for React Flow."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

GraphNodeType = Literal["claim", "evidence_cluster"]
GraphEdgeType = Literal["relationship", "evidence_cluster"]


class GraphPosition(BaseModel):
    """Initial layout coordinates (client may re-layout)."""

    x: float
    y: float


class GraphNodeData(BaseModel):
    """Node payload consumed by the frontend."""

    label: str
    slug: str | None = None
    is_focus: bool = False
    stance: str | None = None
    count: int | None = None
    confidence_score: float | None = None


class GraphNode(BaseModel):
    """React Flow node."""

    id: str
    type: GraphNodeType
    position: GraphPosition
    data: GraphNodeData


class GraphEdgeData(BaseModel):
    """Edge metadata for filtering and tooltips."""

    relationship_type: str | None = None
    strength: float | None = None
    explanation: str | None = None


class GraphEdge(BaseModel):
    """React Flow edge."""

    id: str
    source: str
    target: str
    type: GraphEdgeType = "relationship"
    label: str | None = None
    data: GraphEdgeData = Field(default_factory=GraphEdgeData)


class ClaimGraphResponse(BaseModel):
    """Neighborhood graph around a focus claim."""

    focus_claim_id: UUID
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    available_relationship_types: list[str]
    truncated: bool = False
