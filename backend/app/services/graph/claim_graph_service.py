"""Build React Flow graph payloads from claim relationships and evidence clusters."""

from __future__ import annotations

import math
from collections import deque
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimRelationship, RelationshipType
from app.models.evidence import Evidence, EvidenceStance
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.graph_repository import GraphRepository
from app.services.claims.claim_assessment import resolve_public_claim_scores
from app.services.claims.live_claim_sync import get_pending_for_claim
from app.schemas.graph import (
    ClaimGraphResponse,
    GraphEdge,
    GraphEdgeData,
    GraphNode,
    GraphNodeData,
    GraphPosition,
)

MAX_GRAPH_CLAIMS = 48
RELATIONSHIP_TYPES = [t.value for t in RelationshipType]


def layout_nodes(focus_id: UUID, claim_ids: list[UUID]) -> dict[UUID, GraphPosition]:
    """Place focus at center; neighbors on a circle."""
    positions: dict[UUID, GraphPosition] = {}
    positions[focus_id] = GraphPosition(x=0.0, y=0.0)
    others = [cid for cid in claim_ids if cid != focus_id]
    if not others:
        return positions
    radius = 220.0 + min(len(others), 12) * 12.0
    for i, cid in enumerate(others):
        angle = (2.0 * math.pi * i) / len(others)
        positions[cid] = GraphPosition(
            x=radius * math.cos(angle),
            y=radius * math.sin(angle),
        )
    return positions


def _truncate_label(text: str, max_len: int = 72) -> str:
    t = text.strip()
    return t if len(t) <= max_len else f"{t[: max_len - 1]}…"


class ClaimGraphService:
    """Assemble neighborhood graphs for claim detail exploration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._graphs = GraphRepository(session)

    async def build_graph(
        self,
        *,
        focus: Claim,
        relationship_types: list[str] | None = None,
        depth: int = 1,
        include_evidence_clusters: bool = True,
    ) -> ClaimGraphResponse:
        """Return nodes and edges for React Flow."""
        depth = max(1, min(depth, 2))
        type_filter: list[RelationshipType] | None = None
        if relationship_types:
            type_filter = [RelationshipType(t) for t in relationship_types if t in RELATIONSHIP_TYPES]

        visited: set[UUID] = {focus.id}
        frontier: deque[tuple[UUID, int]] = deque([(focus.id, 0)])
        all_edges: list[ClaimRelationship] = []

        while frontier and len(visited) < MAX_GRAPH_CLAIMS:
            current_id, d = frontier.popleft()
            edges = await self._graphs.list_relationships_for_claim(
                current_id, relationship_types=type_filter, limit=100
            )
            for edge in edges:
                all_edges.append(edge)
                neighbor = (
                    edge.target_claim_id
                    if edge.source_claim_id == current_id
                    else edge.source_claim_id
                )
                if neighbor not in visited and len(visited) < MAX_GRAPH_CLAIMS and d < depth:
                    visited.add(neighbor)
                    frontier.append((neighbor, d + 1))

        claim_ids = list(visited)
        if len(claim_ids) > 1:
            internal = await self._graphs.list_relationships_between(claim_ids, limit=500)
            seen_edge_ids = {e.id for e in all_edges}
            for edge in internal:
                if edge.id not in seen_edge_ids:
                    all_edges.append(edge)
                    seen_edge_ids.add(edge.id)

        claims_map = await self._load_claims(claim_ids)
        display_scores = await self._display_scores_for_claims(claims_map)
        positions = layout_nodes(focus.id, claim_ids)

        nodes: list[GraphNode] = []
        for cid in claim_ids:
            claim = claims_map.get(cid)
            if claim is None:
                continue
            conf, _, _ = display_scores.get(
                cid, (float(claim.confidence_score), 0.0, 0.0)
            )
            nodes.append(
                GraphNode(
                    id=str(cid),
                    type="claim",
                    position=positions[cid],
                    data=GraphNodeData(
                        label=_truncate_label(claim.canonical_claim_text),
                        slug=claim.public_slug,
                        is_focus=cid == focus.id,
                        confidence_score=conf,
                    ),
                )
            )

        edges: list[GraphEdge] = []
        for edge in all_edges:
            if edge.source_claim_id not in visited or edge.target_claim_id not in visited:
                continue
            rel_type = (
                edge.relationship_type.value
                if isinstance(edge.relationship_type, RelationshipType)
                else str(edge.relationship_type)
            )
            edges.append(
                GraphEdge(
                    id=str(edge.id),
                    source=str(edge.source_claim_id),
                    target=str(edge.target_claim_id),
                    type="relationship",
                    label=rel_type.replace("_", " "),
                    data=GraphEdgeData(
                        relationship_type=rel_type,
                        strength=edge.strength,
                        explanation=edge.explanation,
                    ),
                )
            )

        truncated = len(visited) >= MAX_GRAPH_CLAIMS

        if include_evidence_clusters:
            cluster_nodes, cluster_edges = await self._evidence_clusters(focus, positions)
            nodes.extend(cluster_nodes)
            edges.extend(cluster_edges)

        return ClaimGraphResponse(
            focus_claim_id=focus.id,
            nodes=nodes,
            edges=edges,
            available_relationship_types=RELATIONSHIP_TYPES,
            truncated=truncated,
        )

    async def _load_claims(self, claim_ids: list[UUID]) -> dict[UUID, Claim]:
        if not claim_ids:
            return {}
        stmt = select(Claim).where(Claim.id.in_(claim_ids), Claim.deleted_at.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r.id: r for r in rows}

    async def _display_scores_for_claims(
        self, claims_map: dict[UUID, Claim]
    ) -> dict[UUID, tuple[float, float, float]]:
        """Public scores for graph nodes (same merge as claim detail API)."""
        ai_repo = AIAnalysisRepository(self._session)
        out: dict[UUID, tuple[float, float, float]] = {}
        for cid, claim in claims_map.items():
            pending = await get_pending_for_claim(self._session, cid)
            pending_rows = (
                await ai_repo.list_for_target("pending_claim", pending.id) if pending else None
            )
            out[cid] = resolve_public_claim_scores(claim, pending_analyses=pending_rows)
        return out

    async def _evidence_clusters(
        self, focus: Claim, positions: dict[UUID, GraphPosition]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Attach stance cluster nodes around the focus claim."""
        stmt = select(Evidence).where(Evidence.claim_id == focus.id)
        items = list((await self._session.execute(stmt)).scalars().all())
        groups: dict[str, list[Evidence]] = {
            EvidenceStance.supports.value: [],
            EvidenceStance.contradicts.value: [],
            EvidenceStance.contextualizes.value: [],
        }
        for ev in items:
            stance = ev.stance.value if isinstance(ev.stance, EvidenceStance) else str(ev.stance)
            if stance in groups:
                groups[stance].append(ev)

        focus_pos = positions.get(focus.id, GraphPosition(x=0.0, y=0.0))
        offsets = {
            EvidenceStance.supports.value: (-160.0, -120.0),
            EvidenceStance.contradicts.value: (160.0, -120.0),
            EvidenceStance.contextualizes.value: (0.0, 160.0),
        }
        labels = {
            EvidenceStance.supports.value: "Supporting",
            EvidenceStance.contradicts.value: "Contradicting",
            EvidenceStance.contextualizes.value: "Contextual",
        }

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        for stance, group in groups.items():
            if not group:
                continue
            node_id = f"cluster-{focus.id}-{stance}"
            ox, oy = offsets[stance]
            nodes.append(
                GraphNode(
                    id=node_id,
                    type="evidence_cluster",
                    position=GraphPosition(x=focus_pos.x + ox, y=focus_pos.y + oy),
                    data=GraphNodeData(
                        label=f"{labels[stance]} evidence",
                        slug=None,
                        is_focus=False,
                        stance=stance,
                        count=len(group),
                    ),
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge-cluster-{focus.id}-{stance}",
                    source=str(focus.id),
                    target=node_id,
                    type="evidence_cluster",
                    label="evidence",
                    data=GraphEdgeData(relationship_type="evidence_cluster"),
                )
            )
        return nodes, edges
