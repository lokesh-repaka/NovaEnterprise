"""Unit tests for offline pytest harness and fake stores (N1).

Proves that tests run fully offline with zero API keys or external services:
- LLM_PROVIDER=fake
- VECTOR_STORE=memory (InMemoryVectorStore)
- GRAPH_STORE=memory (InMemoryGraphStore)
- SQLite in-memory database
- fakeredis client
"""

from sqlalchemy import text


def test_offline_environment_invariants(test_settings):
    """Test that default test settings enforce complete offline isolation (N1)."""
    assert test_settings.llm_provider == "fake"
    assert test_settings.vector_store == "memory"
    assert test_settings.graph_store == "memory"
    assert test_settings.use_fakeredis is True
    assert "sqlite" in test_settings.database_url


def test_fake_llm_deterministic_completions(fake_llm):
    """Test FakeLLM generates deterministic completions without network calls."""
    prompt = "Explain NovaEnterprise hybrid retrieval"
    resp = fake_llm.complete(prompt)
    assert isinstance(resp, str)
    assert len(resp) > 0

    # Verify call history tracking
    assert len(fake_llm.call_history) == 1
    assert fake_llm.call_history[0]["prompt"] == prompt

    # Verify custom response pattern
    fake_llm.set_response("custom_key", "custom answer text")
    assert fake_llm.complete("query with custom_key") == "custom answer text"

    fake_llm.set_response("json_key", {"status": "success"})
    assert fake_llm.complete("query with json_key") == '{"status": "success"}'


def test_fake_llm_deterministic_embeddings(fake_llm):
    """Test FakeLLM produces deterministic normalized embeddings for vector search."""
    text1 = "Payments API incident in APAC"
    text2 = "Payments API incident in APAC"
    text3 = "Database connection pool exhausted"

    emb1 = fake_llm.embed(text1)
    emb2 = fake_llm.embed(text2)
    emb3 = fake_llm.embed(text3)

    assert len(emb1) == fake_llm.embedding_dim
    # Identical texts must produce identical vectors
    assert emb1 == emb2
    # Different texts must produce different vectors
    assert emb1 != emb3

    # Batch embeddings
    batch_res = fake_llm.embed_batch([text1, text3])
    assert len(batch_res) == 2
    assert batch_res[0] == emb1
    assert batch_res[1] == emb3


def test_fake_llm_structured_json(fake_llm):
    """Test FakeLLM structured output generation."""
    schema = {
        "type": "object",
        "properties": {
            "entity": {"type": "string"},
            "complexity": {"type": "string"},
            "retry_count": {"type": "integer"},
            "confidence": {"type": "number"},
            "verified": {"type": "boolean"},
            "tags": {"type": "array"},
            "unsupported": {"type": "unknown_type"},
        },
        "required": ["entity", "complexity"],
    }
    result = fake_llm.generate_structured("Analyze query complexity", schema=schema)
    assert isinstance(result, dict)
    assert result["entity"] == "mock_entity_val"
    assert result["complexity"] == "mock_complexity_val"
    assert result["retry_count"] == 1
    assert result["confidence"] == 1.0
    assert result["verified"] is True
    assert result["tags"] == []
    assert result["unsupported"] is None

    # Custom structured response
    fake_llm.set_response("custom_struct", {"custom_prop": 123})
    assert fake_llm.generate_structured("query with custom_struct") == {
        "custom_prop": 123
    }

    # Default fallback structured object
    fallback = fake_llm.generate_structured("query with no schema")
    assert fallback["entity"] == "Payments API"
    assert fallback["complexity"] == "complex"


def test_in_memory_vector_store(in_memory_vector_store, fake_llm):
    """Test InMemoryVectorStore indexing and cosine similarity retrieval."""
    chunks = [
        {
            "id": "chunk-1",
            "text": "Payments API latency escalated past 500ms due to connection pool limits.",
            "embedding": fake_llm.embed("Payments API latency escalated"),
            "metadata": {"doc_id": "doc-01", "service": "Payments API"},
        },
        {
            "id": "chunk-2",
            "text": "Auth Service migrated to OAuth2 and Keycloak in Q3.",
            "embedding": fake_llm.embed("Auth Service migrated to OAuth2"),
            "metadata": {"doc_id": "doc-02", "service": "Auth Service"},
        },
    ]

    in_memory_vector_store.add_chunks(chunks)
    assert in_memory_vector_store.count() == 2
    assert in_memory_vector_store.get_status_detail() == "memory (2 chunks)"

    # Query with semantic similarity
    query_emb = fake_llm.embed("Payments API latency escalated")
    results = in_memory_vector_store.search(query_vector=query_emb, top_k=1)

    assert len(results) == 1
    assert results[0]["id"] == "chunk-1"
    assert results[0]["score"] >= 0.99  # near 1.0 for identical vector

    # Metadata filter test
    filtered = in_memory_vector_store.search(
        query_vector=query_emb,
        top_k=5,
        filters={"service": "Auth Service"},
    )
    assert len(filtered) == 1
    assert filtered[0]["id"] == "chunk-2"

    # Delete chunk
    assert in_memory_vector_store.delete_chunk("chunk-1") is True
    assert in_memory_vector_store.delete_chunk("chunk-unknown") is False
    assert in_memory_vector_store.count() == 1


def test_in_memory_graph_store(in_memory_graph_store):
    """Test InMemoryGraphStore node insertion, edge traversal, and detail reporting."""
    # Add nodes
    in_memory_graph_store.add_node(
        "cust-01", label="Customer", properties={"name": "Acme Corp"}
    )
    in_memory_graph_store.add_node(
        "srv-01", label="Service", properties={"name": "Payments API"}
    )
    in_memory_graph_store.add_node(
        "inc-01", label="Incident", properties={"name": "INC-8891"}
    )

    # Add edges
    in_memory_graph_store.add_edge(
        source="cust-01",
        target="srv-01",
        rel_type="DEPENDS_ON",
        properties={"tier": "critical"},
    )
    in_memory_graph_store.add_edge(
        source="srv-01",
        target="inc-01",
        rel_type="AFFECTED_BY",
        properties={"severity": "SEV-1"},
    )

    assert in_memory_graph_store.node_count() == 3
    assert in_memory_graph_store.edge_count() == 2
    assert in_memory_graph_store.get_status_detail() == "memory (3 nodes, 2 edges)"
    assert in_memory_graph_store.get_node("cust-01")["label"] == "Customer"

    # Neighbors
    cust_neighbors = in_memory_graph_store.get_neighbors("cust-01")
    assert len(cust_neighbors) == 1
    assert cust_neighbors[0]["neighbor_id"] == "srv-01"
    assert cust_neighbors[0]["direction"] == "out"

    srv_neighbors = in_memory_graph_store.get_neighbors("srv-01")
    assert len(srv_neighbors) == 2

    # 1-hop neighbor expansion
    neighbors = in_memory_graph_store.expand("cust-01", max_depth=1)
    neighbor_ids = {n["id"] for n in neighbors["nodes"]}
    assert "srv-01" in neighbor_ids
    assert "inc-01" not in neighbor_ids

    # 2-hop neighbor expansion
    two_hop = in_memory_graph_store.expand("cust-01", max_depth=2)
    two_hop_ids = {n["id"] for n in two_hop["nodes"]}
    assert "srv-01" in two_hop_ids
    assert "inc-01" in two_hop_ids

    # Expand non-existent node
    assert in_memory_graph_store.expand("unknown") == {"nodes": [], "edges": []}

    # Cypher-like simulated query
    services = in_memory_graph_store.query("MATCH (n:Service)")
    assert len(services) == 1
    assert services[0]["id"] == "srv-01"


def test_fake_redis_fixture(fake_redis):
    """Test fake_redis fixture supports key-value operations in memory."""
    fake_redis.set("rate_limit:user-1", 10)
    assert fake_redis.get("rate_limit:user-1") == b"10"

    fake_redis.incr("rate_limit:user-1")
    assert fake_redis.get("rate_limit:user-1") == b"11"


def test_sqlite_session_fixture(db_session):
    """Test SQLite in-memory database session fixture."""
    db_session.execute(
        text("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT);")
    )
    db_session.execute(text("INSERT INTO test_items (name) VALUES ('Test Item 1');"))
    db_session.commit()

    result = db_session.execute(
        text("SELECT name FROM test_items WHERE id = 1;")
    ).scalar()
    assert result == "Test Item 1"


def test_test_client_fixture(test_client):
    """Test test_client fixture against unprefixed health routes."""
    res = test_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "x-request-id" in res.headers or "X-Request-ID" in res.headers
