"""Model routing: cheap vs reasoning tiers per AI operation."""

from __future__ import annotations

from enum import Enum

from app.core.config import Settings


class TaskTier(str, Enum):
    """Provider model tier."""

    cheap = "cheap"
    reasoning = "reasoning"


# Cheap: normalization, stance, duplicate LLM checks
_CHEAP_OPERATIONS = frozenset(
    {
        "canonicalize_claim",
        "classify_stance",
        "detect_duplicates",
        "summarize_evidence",
        "generate_embedding",
    }
)

# Expensive: contradiction, synthesis, confidence reasoning, verdicts
_REASONING_OPERATIONS = frozenset(
    {
        "analyze_contradictions",
        "generate_confidence_analysis",
        "structured_verdict",
    }
)


def tier_for_operation(operation: str) -> TaskTier:
    """Resolve model tier for a provider method name."""
    if operation in _CHEAP_OPERATIONS:
        return TaskTier.cheap
    if operation in _REASONING_OPERATIONS:
        return TaskTier.reasoning
    return TaskTier.reasoning


def model_for_operation(settings: Settings, operation: str) -> str:
    """Return configured model id for an operation."""
    tier = tier_for_operation(operation)
    if tier == TaskTier.cheap:
        return settings.ai_model_cheap
    return settings.ai_model_reasoning
