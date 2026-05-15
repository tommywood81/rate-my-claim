"""AI analysis row persistence."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models.ai_analysis import AIAnalysis
from app.repositories.base import RepositoryBase


class AIAnalysisRepository(RepositoryBase):
    """Store isolated model outputs."""

    async def add_analysis(
        self,
        *,
        target_type: str,
        target_id: UUID,
        model_name: str,
        provider: str,
        analysis_type: str,
        generated_text: str,
        structured_payload: dict | None = None,
        confidence: float | None = None,
        prompt_version: str = "v1",
        created_by_job: str | None = None,
    ) -> AIAnalysis:
        """Insert a new analysis row."""
        row = AIAnalysis(
            target_type=target_type,
            target_id=target_id,
            model_name=model_name,
            provider=provider,
            analysis_type=analysis_type,
            generated_text=generated_text,
            structured_payload=json.dumps(structured_payload) if structured_payload else None,
            confidence=confidence,
            prompt_version=prompt_version,
            created_at=datetime.now(tz=UTC),
            created_by_job=created_by_job,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_target(self, target_type: str, target_id: UUID) -> list[AIAnalysis]:
        """Return analyses ordered newest first."""
        stmt = (
            select(AIAnalysis)
            .where(AIAnalysis.target_type == target_type, AIAnalysis.target_id == target_id)
            .order_by(AIAnalysis.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
