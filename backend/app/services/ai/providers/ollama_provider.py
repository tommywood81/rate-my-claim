"""Ollama-compatible local inference provider (optional)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.ai.providers.base import BaseAIProvider


class OllamaProvider(BaseAIProvider):
    """Minimal Ollama HTTP integration for future local models."""

    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        """Resolve base URL from settings."""
        self._settings = get_settings()
        self._base = (
            base_url or self._settings.ollama_base_url or "http://127.0.0.1:11434"
        ).rstrip("/")

    async def _embed(self, text: str) -> tuple[list[float], str]:
        """Call Ollama embeddings API."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self._base}/api/embeddings",
                json={"model": self._settings.ollama_embed_model, "prompt": text[:8000]},
            )
            r.raise_for_status()
            data = r.json()
            return list(data["embedding"]), str(data.get("model", "nomic-embed-text"))

    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        """Return embedding from Ollama."""
        return await self._embed(text)

    async def _chat(self, prompt: str, operation: str) -> str:
        """Run generate endpoint (operation name used for cache keys upstream)."""
        _ = operation
        model = self._settings.ollama_chat_model
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                f"{self._base}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return str(r.json().get("response", ""))

    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        """Return JSON parsed from model output."""
        text = await self._chat(
            f"Return JSON with keys canonical_text, normalized_text, domain_guess, rejection_reason. Input: {raw_text}",
            "canonicalize_claim",
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"canonical_text": raw_text, "normalized_text": raw_text.strip()}

    async def summarize_evidence(self, context: str) -> str:
        """Short summary."""
        return await self._chat(
            f"Summarize in <=120 words:\n{context[:12000]}",
            "summarize_evidence",
        )

    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        """Stance classification."""
        out = await self._chat(
            f'JSON stance supports|contradicts|contextualizes only. Claim:{claim} Excerpt:{evidence_excerpt}',
            "classify_stance",
        )
        try:
            data = json.loads(out)
            s = str(data.get("stance", "contextualizes")).lower()
            return s if s in {"supports", "contradicts", "contextualizes"} else "contextualizes"
        except json.JSONDecodeError:
            return "contextualizes"

    async def detect_duplicates(self, claim: str, candidates: list[str]) -> list[int]:
        """Duplicate indices."""
        out = await self._chat(
            f"JSON duplicate_indices for claim vs candidates: {claim} | {candidates}",
            "detect_duplicates",
        )
        try:
            data = json.loads(out)
            return [int(x) for x in data.get("duplicate_indices", []) if isinstance(x, int)]
        except (json.JSONDecodeError, ValueError):
            return []

    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        """Contradiction narrative."""
        return await self._chat(
            f"Contradictions? Claim:{claim}\n{evidence_blocks[:8000]}",
            "analyze_contradictions",
        )

    async def generate_confidence_analysis(self, claim: str, evidence_digest: str) -> dict[str, Any]:
        """Scores JSON."""
        out = await self._chat(
            f"JSON aggregate evidence_quality source_credibility evidence_consistency freshness rationale. "
            f"Claim:{claim} Digest:{evidence_digest[:8000]}",
            "generate_confidence_analysis",
        )
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"aggregate": 0.5, "rationale": "parse_error"}

    async def structured_verdict(self, claim: str, retrieved_context: str) -> dict[str, Any]:
        """Verdict JSON."""
        out = await self._chat(
            f"JSON verdict_summary citations context_line note confidence_hint controversy_hint. "
            f"Claim:{claim}\nContext:{retrieved_context[:8000]}",
            "structured_verdict",
        )
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"verdict_summary": out[:500], "citations": []}
