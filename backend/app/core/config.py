"""Configuration module for NovaEnterprise.

Provides centralized, cached runtime settings via Pydantic Settings.
Guarantees offline operation by default (N1) with provider-agnostic extensibility (N2).
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime settings for the NovaEnterprise platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata
    app_name: str = "NovaEnterprise"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8001

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"

    # Core AI / Model settings (N1: defaults to fake, N2: provider-agnostic)
    llm_provider: str = Field(
        default="fake",
        description="LLM provider name: fake, openai, anthropic, gemini, etc.",
    )
    llm_model: str = Field(
        default="fake-model", description="Default model name for the selected provider"
    )
    embedding_provider: str = Field(
        default="fake", description="Embedding provider: fake, openai, etc."
    )
    embedding_model: str = Field(
        default="fake-embeddings", description="Embedding model identifier"
    )

    # API keys for external providers (optional; N1: None by default)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    cohere_api_key: str | None = None
    mistral_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Storage protocols & selections (N1: memory stores by default)
    vector_store: str = Field(
        default="memory", description="Vector store backend: memory or qdrant"
    )
    graph_store: str = Field(
        default="memory", description="Graph store backend: memory or neo4j"
    )

    # Agent graph execution bounds (Claude.md §7.3, §10.1)
    max_subquestions: int = Field(
        default=4, description="Maximum sub-questions during decomposition (default: 4)"
    )
    max_corrective_rounds: int = Field(
        default=1, description="Maximum corrective retrieval loops (default: 1)"
    )

    # Rate limits & Guardrails (N6, N7)
    rate_limit_per_minute: int = Field(
        default=120, description="Requests per minute allowed per client"
    )
    max_upload_mb: int = Field(
        default=5, description="Maximum upload file size in megabytes"
    )

    # Persistence & Caching
    database_url: str = Field(
        default="sqlite:///./data/enterprise.db",
        description="SQLAlchemy database connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    use_fakeredis: bool = Field(
        default=True,
        description="Whether to use in-memory fakeredis for local/offline execution",
    )

    # Security & Identity (Phase 3 / Claude.md §2, §9)
    jwt_secret_key: str = Field(
        default="nova-enterprise-development-jwt-secret-do-not-use-in-production",
        description="JWT secret key for token signing",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_service_role_key: str | None = None

    # External store connection configurations
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "enterprise_chunks"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Paths and CORS
    sample_data_dir: str = "sample_data"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("max_subquestions")
    @classmethod
    def validate_max_subquestions(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_subquestions must be a positive integer")
        return v

    @field_validator("max_corrective_rounds")
    @classmethod
    def validate_max_corrective_rounds(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_corrective_rounds must be a non-negative integer")
        return v

    @field_validator("rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("rate_limit_per_minute must be greater than zero")
        return v

    @field_validator("max_upload_mb")
    @classmethod
    def validate_max_upload_mb(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_upload_mb must be greater than zero")
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings.

    Settings is cached with @lru_cache: restart the server after editing .env.
    """
    return Settings()


def clear_settings_cache() -> None:
    """Clear the cached settings instance (primarily for tests)."""
    get_settings.cache_clear()
