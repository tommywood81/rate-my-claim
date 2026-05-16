"""AI-assisted canonicalization with deterministic normalization."""

from __future__ import annotations

from typing import Any

from app.services.ai.providers.base import BaseAIProvider
from app.services.ingestion.claim_normalization import normalize_claim_text


class CanonicalizationService:
    """Normalize raw text and produce canonical candidate via provider."""

    async def canonicalize(
        self,
        raw_text: str,
        provider: BaseAIProvider,
    ) -> dict[str, Any]:
        """Return normalized + canonical fields or rejection_reason from provider."""
        normalized = normalize_claim_text(raw_text)
        canon = await provider.canonicalize_claim(normalized)
        canonical = str(canon.get("canonical_text") or normalized).strip()
        norm_out = str(canon.get("normalized_text") or canonical).strip()
        return {
            **canon,
            "normalized_text": norm_out,
            "canonical_text": canonical,
        }
