"""Provider registry — swap OpenAI and Ollama without changing call sites."""

from __future__ import annotations

from typing import Literal

from app.core.config import Settings, get_settings
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.ollama_provider import OllamaProvider
from app.services.ai.providers.openai_provider import OpenAIProvider

ProviderName = Literal["openai", "ollama"]


def create_provider(
    name: ProviderName | str,
    *,
    budget_scope: str = "unscoped",
    settings: Settings | None = None,
) -> BaseAIProvider:
    """Instantiate a concrete provider by name."""
    cfg = settings or get_settings()
    normalized = str(name).lower().strip()
    if normalized == "openai":
        if not cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY must be set when AI_PROVIDER=openai")
        return OpenAIProvider(budget_scope=budget_scope)
    if normalized == "ollama":
        return OllamaProvider()
    raise ValueError(f"unknown_ai_provider:{normalized}")


def list_providers() -> list[str]:
    """Registered provider identifiers."""
    return ["openai", "ollama"]
