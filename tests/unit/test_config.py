"""Unit tests for Settings configuration (P1-1).

Proves: N1 (offline default: no key, no external service),
        N2 (provider-agnostic settings).
"""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings, clear_settings_cache, get_settings


def test_default_settings_offline_n1():
    """Verify N1 requirement: offline defaults with no API keys or external services."""
    clear_settings_cache()
    settings = get_settings()

    assert settings.llm_provider == "fake"
    assert settings.vector_store == "memory"
    assert settings.graph_store == "memory"
    assert settings.max_subquestions == 4
    assert settings.max_corrective_rounds == 1
    assert settings.rate_limit_per_minute == 120
    assert settings.max_upload_mb == 5
    assert settings.use_fakeredis is True
    assert "sqlite" in settings.database_url
    assert settings.jwt_algorithm == "HS256"
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None
    assert settings.gemini_api_key is None


def test_settings_caching():
    """Verify Settings is cached with lru_cache."""
    clear_settings_cache()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_cache_clear(monkeypatch):
    """Verify clear_settings_cache allows picking up new environment variables."""
    clear_settings_cache()
    s1 = get_settings()
    assert s1.max_subquestions == 4

    monkeypatch.setenv("MAX_SUBQUESTIONS", "8")
    clear_settings_cache()
    s2 = get_settings()
    assert s2.max_subquestions == 8

    # Reset
    clear_settings_cache()


def test_settings_env_overrides(monkeypatch):
    """Verify environment variables override default settings cleanly."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("VECTOR_STORE", "qdrant")
    monkeypatch.setenv("GRAPH_STORE", "neo4j")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "60")
    monkeypatch.setenv("MAX_UPLOAD_MB", "10")

    clear_settings_cache()
    settings = get_settings()

    assert settings.llm_provider == "openai"
    assert settings.vector_store == "qdrant"
    assert settings.graph_store == "neo4j"
    assert settings.rate_limit_per_minute == 60
    assert settings.max_upload_mb == 10

    clear_settings_cache()


def test_settings_validation():
    """Verify validation constraints on settings fields."""
    with pytest.raises(ValidationError):
        Settings(max_subquestions=-1)

    with pytest.raises(ValidationError):
        Settings(max_corrective_rounds=-1)

    with pytest.raises(ValidationError):
        Settings(rate_limit_per_minute=0)

    with pytest.raises(ValidationError):
        Settings(max_upload_mb=0)


def test_n2_provider_agnostic_settings():
    """Verify N2 requirement: settings supports arbitrary LLM providers and models."""
    custom_settings = Settings(
        llm_provider="anthropic",
        llm_model="claude-3-5-sonnet",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
    )
    assert custom_settings.llm_provider == "anthropic"
    assert custom_settings.llm_model == "claude-3-5-sonnet"
    assert custom_settings.embedding_provider == "openai"
    assert custom_settings.embedding_model == "text-embedding-3-small"
