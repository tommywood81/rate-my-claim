"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent


def _env_files() -> tuple[str, ...]:
    """Load .env from cwd, backend/, then repo root (later files override earlier)."""
    paths: list[Path] = []
    for candidate in (Path.cwd() / ".env", _BACKEND_DIR / ".env", _REPO_ROOT / ".env"):
        if candidate.is_file() and candidate not in paths:
            paths.append(candidate)
    return tuple(str(p) for p in paths) if paths else (".env",)


class Settings(BaseSettings):
    """Runtime configuration for the API and workers."""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Rate My Claim API"
    debug: bool = False
    secret_key: str = Field(..., min_length=32, description="Signing key for JWT and CSRF")
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    database_url: PostgresDsn = Field(
        ...,
        alias="DATABASE_URL",
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host/db",
    )
    database_sync_url: PostgresDsn | None = Field(
        default=None,
        alias="DATABASE_SYNC_URL",
        description="Sync URL for Alembic/Celery, e.g. postgresql+psycopg2://...",
    )

    redis_url: RedisDsn = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND"
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_organization: str | None = Field(default=None, alias="OPENAI_ORG_ID")

    openai_enforce_token_budgets: bool = Field(
        default=True,
        alias="OPENAI_ENFORCE_TOKEN_BUDGETS",
        description="When true, enforce daily and per-scope token caps (dev safety).",
    )
    openai_max_tokens_per_day: int = Field(
        default=200_000,
        ge=0,
        alias="OPENAI_MAX_TOKENS_PER_DAY",
        description="Max OpenAI total_tokens per UTC day (0 = no daily cap).",
    )
    openai_max_tokens_per_claim_scope: int = Field(
        default=80_000,
        ge=0,
        alias="OPENAI_MAX_TOKENS_PER_CLAIM_SCOPE",
        description="Max total_tokens per logical scope (e.g. one enrichment job). 0 = no cap.",
    )

    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_version: str = "v1"

    ai_model_cheap: str = "gpt-4o-mini"
    ai_model_reasoning: str = "gpt-4o-mini"

    ai_provider: Literal["openai", "ollama"] = Field(
        default="openai",
        alias="AI_PROVIDER",
        description="Primary AI backend: openai or ollama.",
    )
    ai_cache_enabled: bool = Field(default=True, alias="AI_CACHE_ENABLED")
    ai_cache_ttl_seconds: int = Field(default=86400, ge=60, alias="AI_CACHE_TTL_SECONDS")
    ai_retry_max_attempts: int = Field(default=3, ge=1, le=8, alias="AI_RETRY_MAX_ATTEMPTS")
    ai_retry_base_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        alias="AI_RETRY_BASE_DELAY_SECONDS",
    )
    ai_track_cost_usd: bool = Field(
        default=True,
        alias="AI_TRACK_COST_USD",
        description="Accumulate estimated OpenAI spend in Redis (dev observability).",
    )

    ollama_base_url: str | None = Field(default=None, alias="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="llama3.2", alias="OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")

    cors_origins: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
    auth_login_rate_limit: str = Field(default="10/minute", alias="AUTH_LOGIN_RATE_LIMIT")
    auth_register_rate_limit: str = Field(default="5/minute", alias="AUTH_REGISTER_RATE_LIMIT")
    auth_forgot_password_rate_limit: str = Field(
        default="5/minute",
        alias="AUTH_FORGOT_PASSWORD_RATE_LIMIT",
    )
    auth_brute_force_max_attempts: int = Field(default=5, ge=1, alias="AUTH_BRUTE_FORCE_MAX_ATTEMPTS")
    auth_brute_force_lockout_seconds: int = Field(
        default=900,
        ge=60,
        alias="AUTH_BRUTE_FORCE_LOCKOUT_SECONDS",
    )
    auth_password_reset_expire_minutes: int = Field(
        default=60,
        ge=5,
        alias="AUTH_PASSWORD_RESET_EXPIRE_MINUTES",
    )
    auth_email_verify_expire_hours: int = Field(
        default=48,
        ge=1,
        alias="AUTH_EMAIL_VERIFY_EXPIRE_HOURS",
    )
    auth_expose_dev_tokens: bool = Field(
        default=False,
        alias="AUTH_EXPOSE_DEV_TOKENS",
        description="Return reset/verify tokens in API meta (development only).",
    )
    csrf_cookie_name: str = "rmc_csrf"
    access_cookie_name: str = "rmc_access"
    refresh_cookie_name: str = "rmc_refresh"

    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")

    public_app_url: str = Field(default="http://localhost:8080", alias="PUBLIC_APP_URL")

    duplicate_vector_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    hybrid_semantic_weight: float = 0.35
    hybrid_fts_weight: float = 0.25
    hybrid_evidence_weight: float = 0.15
    hybrid_confidence_weight: float = 0.10
    hybrid_freshness_weight: float = 0.10
    hybrid_relationship_weight: float = 0.05

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Return sync SQLAlchemy URL for workers and migrations."""
        if self.database_sync_url is not None:
            return str(self.database_sync_url)
        url = str(self.database_url)
        return url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()  # type: ignore[call-arg]
