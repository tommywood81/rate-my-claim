"""Factory for AI providers."""

from app.core.config import get_settings
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.openai_provider import OpenAIProvider


def get_ai_provider(*, budget_scope: str = "unscoped") -> BaseAIProvider:
    """Return configured primary provider (OpenAI for Stage 1).

    ``budget_scope`` groups OpenAI token accounting (per pending job, claim analysis, etc.).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY must be set for AI operations")
    return OpenAIProvider(budget_scope=budget_scope)
