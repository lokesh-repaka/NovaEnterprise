"""Unit tests for ResearchState schema and provider-agnostic Fake LLM provider (P9-1, N1, N2).

Validates:
- ResearchState model fields, defaults, dict-like subscripting, and mutation helpers (Claude.md §7.3, FRD §5.2)
- State serialization and round-trip deserialization with Evidence models
- Provider-agnostic get_llm() and get_embedding_model() resolving 8 providers (N2)
- FakeLLMClient deterministic completions, structured output generation, and normalized embeddings (N1)
- Custom response registration and offline reproducibility
"""

from datetime import datetime

import pytest

from agents.state import ResearchState, ResearchStateDict
from backend.app.core.llm import (
    BaseLLMClient,
    FakeLLMClient,
    LLMProvider,
    get_embedding_model,
    get_llm,
    reset_llm_cache,
)
from rag.evidence import Evidence

# =====================================================================
# 1. ResearchState Schema Tests
# =====================================================================


def test_research_state_defaults_and_fields() -> None:
    """FRD §5.2: Verify default values and field shapes of ResearchState."""
    session_id = "sess_state_001"
    question = "Which customers were impacted by the Payments API outage last quarter?"

    state = ResearchState(session_id=session_id, question=question)

    assert state.session_id == session_id
    assert state.question == question
    assert state.user_id == "demo-user"
    assert state.complexity is None
    assert state.intent is None
    assert state.entity is None
    assert state.time_range == {}
    assert state.sub_questions == []
    assert state.evidence == []
    assert state.verified_evidence == []
    assert state.missing_facets == []
    assert state.needs_retry is False
    assert state.corrective_rounds == 0
    assert state.verification_ratio == 0.0
    assert state.answer == ""
    assert state.citations == []
    assert state.errors == []
    assert state.status == "running"
    assert state.strategies_used == []
    assert state.current_node is None
    assert isinstance(state.created_at, datetime)
    assert isinstance(state.updated_at, datetime)


def test_research_state_dict_like_access_and_mutation() -> None:
    """Claude.md §7.3: Verify ResearchState supports both attribute and dict-like access."""
    state = ResearchState(session_id="sess_dict_01", question="What caused INC-2031?")

    # Dict-like read
    assert state["session_id"] == "sess_dict_01"
    assert state["question"] == "What caused INC-2031?"
    assert state.get("complexity") is None
    assert state.get("nonexistent", "fallback") == "fallback"
    assert "question" in state
    assert "nonexistent" not in state

    # Dict-like write
    state["complexity"] = "complex"
    assert state.complexity == "complex"
    assert state["complexity"] == "complex"

    state["intent"] = "root_cause_analysis"
    assert state.intent == "root_cause_analysis"

    # Keys, values, items
    keys = list(state.keys())
    assert "session_id" in keys
    assert "complexity" in keys
    assert "intent" in keys


def test_research_state_helper_methods() -> None:
    """Verify state mutation helpers: add_evidence, add_error, add_strategy."""
    state = ResearchState(session_id="sess_helpers", question="Check Payments API")

    # Add evidence
    evidence = Evidence(
        id="evi_test_101",
        sub_question_id="sq1",
        source_type="graph",
        locator="(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)",
        content="Payments API was affected by INC-2031",
        score=0.98,
    )
    state.add_evidence(evidence)
    assert len(state.evidence) == 1
    assert state.evidence[0].id == "evi_test_101"

    # Add evidence as dict
    state.add_evidence(
        {
            "id": "evi_test_102",
            "sub_question_id": "sq2",
            "source_type": "sql",
            "locator": "sql:incidents#row-2031",
            "content": "INC-2031 duration was 42 minutes",
            "score": 1.0,
        }
    )
    assert len(state.evidence) == 2

    # Add strategy
    state.add_strategy("graph")
    state.add_strategy("sql")
    state.add_strategy("graph")  # Deduplication
    assert state.strategies_used == ["graph", "sql"]

    # Add error
    state.add_error("Neo4j transient connection timeout on sub-question sq3")
    assert len(state.errors) == 1
    assert "Neo4j transient connection timeout" in state.errors[0]


def test_research_state_serialization_round_trip() -> None:
    """Verify ResearchState serializes to JSON and deserializes cleanly without data loss."""
    state = ResearchState(
        session_id="sess_serial",
        question="Which customers were impacted by the Payments API outage?",
        complexity="complex",
        entity="Payments API",
        time_range={
            "start_date": "2026-04-01T00:00:00Z",
            "end_date": "2026-06-30T23:59:59Z",
        },
        sub_questions=[
            {"id": "sq1", "text": "What incidents occurred?", "strategy": "sql"}
        ],
        evidence=[
            Evidence(
                id="evi_01",
                sub_question_id="sq1",
                source_type="sql",
                locator="sql:incidents#row-2031",
                content="INC-2031 SEV1 outage",
            )
        ],
        strategies_used=["sql"],
    )

    dumped = state.model_dump()
    assert dumped["session_id"] == "sess_serial"
    assert dumped["complexity"] == "complex"
    assert len(dumped["evidence"]) == 1

    json_str = state.model_dump_json()
    restored = ResearchState.model_validate_json(json_str)

    assert restored.session_id == state.session_id
    assert restored.entity == state.entity
    assert restored.sub_questions == state.sub_questions
    assert len(restored.evidence) == 1
    assert restored.evidence[0].id == "evi_01"


def test_research_state_dict_typed_dict() -> None:
    """Verify ResearchStateDict TypedDict works with LangGraph annotations."""
    dict_payload: ResearchStateDict = {
        "session_id": "sess_typed_01",
        "question": "Sample question text",
        "complexity": "simple",
    }
    assert dict_payload["session_id"] == "sess_typed_01"
    assert dict_payload["complexity"] == "simple"


# =====================================================================
# 2. Fake LLM Provider & Client Tests
# =====================================================================


def test_fake_llm_client_protocol_conformance() -> None:
    """N2: Verify FakeLLMClient conforms to BaseLLMClient interface."""
    client = FakeLLMClient()
    assert isinstance(client, BaseLLMClient)


def test_fake_llm_client_completions() -> None:
    """N1: Verify FakeLLMClient produces deterministic completions offline."""
    client = FakeLLMClient()
    resp = client.complete("Summarize the root cause of INC-2031")
    assert isinstance(resp, str)
    assert len(resp) > 0
    assert len(client.call_history) == 1
    assert client.call_history[0]["type"] == "complete"


def test_fake_llm_client_custom_response_overrides() -> None:
    """Verify custom pattern responses override default synthesized outputs."""
    client = FakeLLMClient()
    client.set_response(
        "classify_intent", {"intent": "incident_investigation", "confidence": 0.99}
    )

    structured = client.generate_structured("Please classify_intent for INC-2031")
    assert structured["intent"] == "incident_investigation"
    assert structured["confidence"] == 0.99

    client.set_response("greeting_prompt", "Hello from Fake LLM!")
    text = client.complete("This is a greeting_prompt")
    assert text == "Hello from Fake LLM!"


def test_fake_llm_client_canonical_scenario_generation() -> None:
    """Verify built-in responses for the canonical enterprise research query."""
    client = FakeLLMClient()
    canonical_prompt = (
        "Which customers were impacted by the Payments API outage last quarter?"
    )

    # Query analysis
    analysis = client.generate_structured(f"analyze_query: {canonical_prompt}")
    assert analysis["entity"] == "Payments API"
    assert "time_range" in analysis

    # Decomposition
    decomp = client.generate_structured(f"decompose_query: {canonical_prompt}")
    assert "sub_questions" in decomp
    assert len(decomp["sub_questions"]) >= 1


def test_fake_llm_client_embeddings_and_normalization() -> None:
    """Verify deterministic, unit-normalized vector embeddings (L2 norm == 1.0)."""
    client = FakeLLMClient(embedding_dim=384)
    vec1 = client.embed("Payments API postmortem incident report")
    assert len(vec1) == 384

    # Norm must equal ~1.0
    norm = sum(x * x for x in vec1)
    assert pytest.approx(norm, rel=1e-3) == 1.0

    # Batch embedding
    batch = client.embed_batch(["text one", "text two"])
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert len(batch[1]) == 384


# =====================================================================
# 3. Provider-Agnostic LLM Gateway Factory (get_llm & get_embedding_model)
# =====================================================================


def test_get_llm_resolves_default_fake_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N1, N2: Verify get_llm() returns FakeLLMClient when LLM_PROVIDER=fake."""
    reset_llm_cache()
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    client = get_llm()
    assert isinstance(client, FakeLLMClient)
    assert client.provider == LLMProvider.FAKE


def test_get_embedding_model_resolves_default_fake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N1, N2: Verify get_embedding_model() returns FakeLLMClient embedding service."""
    reset_llm_cache()
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    embedder = get_embedding_model()
    vec = embedder.embed("Enterprise search query")
    assert len(vec) == 384


def test_llm_providers_enum_covers_all_eight_providers() -> None:
    """N2: Verify all 8 platform providers are defined in LLMProvider enum."""
    expected_providers = {
        "fake",
        "openai",
        "anthropic",
        "google",
        "groq",
        "cohere",
        "mistral",
        "ollama",
    }
    actual_providers = {p.value for p in LLMProvider}
    assert expected_providers == actual_providers


def test_get_llm_unsupported_provider_raises_informative_error() -> None:
    """Verify requesting an invalid provider raises ValueError with supported providers."""
    reset_llm_cache()
    with pytest.raises(ValueError, match="Unsupported LLM provider 'unsupported_ai'"):
        get_llm(provider="unsupported_ai")


def test_get_llm_cloud_provider_missing_credentials_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify attempting to instantiate a live cloud provider without API keys raises clean error."""
    reset_llm_cache()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="API key not configured"):
        get_llm(provider="openai")
