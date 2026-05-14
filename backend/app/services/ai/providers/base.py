"""Abstract AI provider interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAIProvider(ABC):
    """Provider-agnostic surface for embeddings and reasoning."""

    name: str = "base"

    @abstractmethod
    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        """Return embedding vector and resolved model name."""

    @abstractmethod
    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        """Return structured normalization metadata and canonical text."""

    @abstractmethod
    async def summarize_evidence(self, context: str) -> str:
        """Produce a short evidence-grounded summary."""

    @abstractmethod
    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        """Return stance label: supports | contradicts | contextualizes."""

    @abstractmethod
    async def detect_duplicates_llm(self, claim: str, candidates: list[str]) -> list[int]:
        """Return indices of candidates considered likely duplicates."""

    @abstractmethod
    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        """Return narrative contradiction analysis."""

    @abstractmethod
    async def generate_confidence_analysis(self, claim: str, evidence_digest: str) -> dict[str, Any]:
        """Return structured scores and rationale grounded in digest."""

    @abstractmethod
    async def structured_verdict(
        self, claim: str, retrieved_context: str
    ) -> dict[str, Any]:
        """Return JSON-serializable verdict with citations referencing context lines only."""
