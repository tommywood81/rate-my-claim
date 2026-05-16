"""OpenAI-backed provider implementation."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.token_budget import budget_chat_call, budget_embedding_call

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """Production OpenAI client with explicit model routing."""

    name = "openai"

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        *,
        budget_scope: str = "unscoped",
    ) -> None:
        """Initialize client from settings when not injected."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIProvider")
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._settings = settings
        self._budget_scope = budget_scope

    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        """Create a single embedding vector."""
        model = self._settings.embedding_model
        text_in = text[:8000]

        async def call() -> Any:
            return await self._client.embeddings.create(model=model, input=text_in)

        response = await budget_embedding_call(
            settings=self._settings,
            scope_key=self._budget_scope,
            text=text_in,
            call=call,
        )
        vec = list(response.data[0].embedding)
        return vec, model

    async def _chat_json(self, system: str, user: str, *, model: str) -> dict[str, Any]:
        """Parse JSON object from chat completion."""

        async def call() -> Any:
            return await self._client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )

        completion = await budget_chat_call(
            settings=self._settings,
            scope_key=self._budget_scope,
            system=system,
            user=user,
            completion_reserve=3072,
            call=call,
        )
        content = completion.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("openai_json_parse_failed", extra={"content": content[:200]})
            return {}

    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        """Normalize claim text into declarative empirical form."""
        system = (
            "You normalize empirical claims for a research database. "
            "Output strict JSON keys: canonical_text (string), "
            "normalized_text (string), domain_guess (string or null), "
            "rejection_reason (string or null if acceptable). "
            "Reject vague, ideological, or non-falsifiable claims with rejection_reason."
        )
        return await self._chat_json(system, raw_text, model=self._settings.ai_model_cheap)

    async def summarize_evidence(self, context: str) -> str:
        """Summarize only what is explicitly present in context."""
        system = "Summarize retrieved evidence in <=120 words. Do not invent sources."
        user = context[:12000]

        async def call() -> Any:
            return await self._client.chat.completions.create(
                model=self._settings.ai_model_cheap,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

        completion = await budget_chat_call(
            settings=self._settings,
            scope_key=self._budget_scope,
            system=system,
            user=user,
            completion_reserve=512,
            call=call,
        )
        return (completion.choices[0].message.content or "").strip()

    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        """Classify stance using cheap model."""
        system = (
            'Classify relationship of excerpt to claim. '
            'JSON: {"stance":"supports|contradicts|contextualizes"}'
        )
        data = await self._chat_json(
            system,
            f"Claim: {claim}\nExcerpt: {evidence_excerpt}",
            model=self._settings.ai_model_cheap,
        )
        stance = str(data.get("stance", "contextualizes")).lower()
        if stance not in {"supports", "contradicts", "contextualizes"}:
            return "contextualizes"
        return stance

    async def detect_duplicates_llm(self, claim: str, candidates: list[str]) -> list[int]:
        """Ask model which candidates are duplicates; conservative."""
        if not candidates:
            return []
        numbered = "\n".join(f"{i}: {c}" for i, c in enumerate(candidates))
        system = (
            "Given a claim and numbered candidate claims, return JSON "
            '{"duplicate_indices":[int,...]} only for near-duplicate meaning, else empty.'
        )
        data = await self._chat_json(
            system,
            f"Claim:\n{claim}\nCandidates:\n{numbered}",
            model=self._settings.ai_model_cheap,
        )
        raw = data.get("duplicate_indices", [])
        out: list[int] = []
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, int) and 0 <= x < len(candidates):
                    out.append(x)
        return out

    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        """Narrative contradiction scan."""
        system = (
            "Identify tensions or contradictions across evidence blocks. "
            "If none, say so. Max 200 words. Ground only in provided blocks."
        )
        user = f"Claim: {claim}\nBlocks:\n{evidence_blocks[:14000]}"

        async def call() -> Any:
            return await self._client.chat.completions.create(
                model=self._settings.ai_model_reasoning,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

        completion = await budget_chat_call(
            settings=self._settings,
            scope_key=self._budget_scope,
            system=system,
            user=user,
            completion_reserve=1024,
            call=call,
        )
        return (completion.choices[0].message.content or "").strip()

    async def generate_confidence_analysis(
        self,
        claim: str,
        evidence_digest: str,
    ) -> dict[str, Any]:
        """Return component scores in [0,1]."""
        system = (
            "Score evidence support strength (not absolute truth). "
            "JSON keys: aggregate (0-1), evidence_quality, source_credibility, "
            "evidence_consistency, freshness, rationale (string)."
        )
        return await self._chat_json(
            system,
            f"Claim: {claim}\nDigest:\n{evidence_digest[:12000]}",
            model=self._settings.ai_model_reasoning,
        )

    async def structured_verdict(self, claim: str, retrieved_context: str) -> dict[str, Any]:
        """Structured verdict referencing CONTEXT_LINE numbers only."""
        system = (
            "You assist a moderation queue. Using ONLY numbered lines in CONTEXT, "
            "produce JSON: {"
            '"verdict_summary": string, '
            '"citations": [{"context_line": int, "note": string}], '
            '"confidence_hint": number, '
            '"controversy_hint": number '
            "}. Never invent URLs or studies not present in CONTEXT."
        )
        return await self._chat_json(
            system,
            f"CLAIM:\n{claim}\n\nCONTEXT:\n{retrieved_context[:16000]}",
            model=self._settings.ai_model_reasoning,
        )
