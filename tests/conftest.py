"""Root pytest configuration and offline test harness fixtures for NovaEnterprise (N1).

Guarantees 100% offline test execution without external network calls,
third-party API credentials, or container services.
"""

import os
from collections.abc import Generator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings, clear_settings_cache, get_settings
from backend.app.main import create_app
from tests.mocks.fake_llm import FakeLLM
from tests.mocks.fake_stores import InMemoryGraphStore, InMemoryVectorStore


@pytest.fixture(autouse=True, scope="session")
def enforce_offline_environment() -> Generator[None, None, None]:
    """Session fixture enforcing pure offline environment variables (N1)."""
    original_env = os.environ.copy()

    # Enforce offline defaults as defined in Claude.md §3.2 & GEMINI.md §3
    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["VECTOR_STORE"] = "memory"
    os.environ["GRAPH_STORE"] = "memory"
    os.environ["USE_FAKEREDIS"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    clear_settings_cache()

    yield

    # Restore environment after test session completes
    os.environ.clear()
    os.environ.update(original_env)
    clear_settings_cache()


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing clean, isolated offline settings."""
    clear_settings_cache()
    return get_settings()


@pytest.fixture
def fake_llm() -> Generator[FakeLLM, None, None]:
    """Fixture providing a fresh FakeLLM instance."""
    llm = FakeLLM()
    yield llm
    llm.reset()


@pytest.fixture
def in_memory_vector_store() -> Generator[InMemoryVectorStore, None, None]:
    """Fixture providing a clean in-memory vector store."""
    store = InMemoryVectorStore()
    yield store
    store.clear()


@pytest.fixture
def in_memory_graph_store() -> Generator[InMemoryGraphStore, None, None]:
    """Fixture providing a clean in-memory graph store."""
    store = InMemoryGraphStore()
    yield store
    store.clear()


@pytest.fixture
def fake_redis() -> Generator[fakeredis.FakeRedis, None, None]:
    """Fixture providing an isolated in-memory fakeredis client."""
    client = fakeredis.FakeRedis()
    yield client
    client.flushall()


@pytest.fixture
def db_engine():
    """Fixture providing an in-memory SQLite SQLAlchemy engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Fixture providing an active SQLAlchemy database session with automatic teardown."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Fixture providing a FastAPI TestClient configured for the test app."""
    app = create_app()
    with TestClient(app) as client:
        yield client
