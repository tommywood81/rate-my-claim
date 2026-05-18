"""Factory for configured, instrumented AI providers."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.ai.instrumented_provider import InstrumentedAIProvider
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.registry import create_provider


def get_ai_provider(*, budget_scope: str = "unscoped") -> BaseAIProvider:
    """Return the configured provider with cache, retry, and audit layers.

    ``budget_scope`` groups OpenAI token/cost accounting (per pending job, claim, etc.).
  """
    settings = get_settings()
    inner = create_provider(settings.ai_provider, budget_scope=budget_scope)
    return InstrumentedAIProvider(inner, scope_key=budget_scope, settings=settings)
