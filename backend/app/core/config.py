"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API and workers."""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_version: str = "v1"

    ai_model_cheap: str = "gpt-4o-mini"
    ai_model_reasoning: str = "gpt-4o-mini"

    ollama_base_url: str | None = Field(default=None, alias="OLLAMA_BASE_URL")

    cors_origins: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
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
