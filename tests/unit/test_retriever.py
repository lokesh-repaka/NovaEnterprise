"""Unit and integration tests for Hybrid Document RAG (P6-4, F6, Claude.md §5, §8).

Validates:
- BM25Okapi sparse lexical scoring and ranking
- Reciprocal Rank Fusion (RRF) with k=60
- Cross-Encoder relevance reranking with top_n cap
- Hybrid retriever producing canonical Evidence models with document locators
- Dense-only and sparse-only fallback paths
- Ingested corpus retrieval integration
"""

from pathlib import Path

import pytest

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.schemas.common import Evidence
from rag.ingest import generate_offline_embedding
from rag.retriever import (
    BM25Index,
    HybridRetriever,
    cross_encoder_rerank,
    reciprocal_rank_fusion,
    retrieve_hybrid,
)
from rag.vector_store import InMemoryVectorStore, VectorChunk


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite session with initialized schema."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        yield session


@pytest.fixture
def sample_chunks() -> list[VectorChunk]:
    """Create a curated set of sample document chunks for hybrid retrieval tests."""
    chunks = [
        VectorChunk(
            id="chunk-inc2031-1",
            text="INC-2031 Postmortem: Payments API experienced thread pool starvation and database connection pool exhaustion under sudden traffic surge.",
            embedding=generate_offline_embedding(
                "Payments API connection pool exhaustion"
            ),
            metadata={
                "filename": "documents/postmortem-inc-2031-payments-api-outage.md",
                "chunk_index": 0,
                "doc_type": "postmortem",
            },
            locator="documents/postmortem-inc-2031-payments-api-outage.md#chunk-0",
        ),
        VectorChunk(
            id="chunk-adr042-1",
            text="ADR-042: Adopt PgBouncer as a transaction-mode connection pooler sidecar for Payments API and all tier-1 services to prevent database thread starvation.",
            embedding=generate_offline_embedding(
                "PgBouncer connection pooling sidecar Payments API"
            ),
            metadata={
                "filename": "documents/adr-042-pgbouncer-connection-pooling.md",
                "chunk_index": 0,
                "doc_type": "adr",
            },
            locator="documents/adr-042-pgbouncer-connection-pooling.md#chunk-0",
        ),
        VectorChunk(
            id="chunk-policy-1",
            text="Corporate Data Retention Policy: All customer transaction logs must be retained for seven years in compliance with SOC2 and financial regulations.",
            embedding=generate_offline_embedding(
                "Data retention policy transaction logs compliance"
            ),
            metadata={
                "filename": "documents/policy-data-retention.md",
                "chunk_index": 0,
                "doc_type": "policy",
            },
            locator="documents/policy-data-retention.md#chunk-0",
        ),
        VectorChunk(
            id="chunk-runbook-1",
            text="SRE Runbook: Restarting Redis cache cluster and draining message queues during high memory backpressure alerts.",
            embedding=generate_offline_embedding(
                "SRE Runbook restarting Redis cache cluster memory pressure"
            ),
            metadata={
                "filename": "documents/runbook-redis-recovery.md",
                "chunk_index": 0,
                "doc_type": "runbook",
            },
            locator="documents/runbook-redis-recovery.md#chunk-0",
        ),
    ]
    return chunks


def test_bm25_tokenization_and_scoring(sample_chunks: list[VectorChunk]) -> None:
    """Verify BM25 index tokenizes text and scores keyword relevance."""
    index = BM25Index()
    index.index_chunks(sample_chunks)

    assert index.doc_count == 4
    assert index.avg_doc_len > 0

    # Query matching chunk 0 (Payments API thread pool exhaustion)
    results = index.search("thread pool starvation exhaustion", top_k=2)
    assert len(results) == 2
    assert results[0].id == "chunk-inc2031-1"
    assert results[0].score > 0

    # Query matching chunk 1 (PgBouncer sidecar)
    results_adr = index.search("PgBouncer transaction-mode sidecar", top_k=2)
    assert len(results_adr) >= 1
    assert results_adr[0].id == "chunk-adr042-1"


def test_bm25_empty_and_non_matching_query(sample_chunks: list[VectorChunk]) -> None:
    """Verify BM25 returns empty results for empty or completely disjoint queries."""
    index = BM25Index()
    index.index_chunks(sample_chunks)

    # Empty query
    assert index.search("", top_k=5) == []
    assert index.search("   ", top_k=5) == []

    # Non-matching terms
    res = index.search("astronomy telescope galaxies", top_k=5)
    assert len(res) == 0


def test_reciprocal_rank_fusion_algorithm() -> None:
    """Verify Reciprocal Rank Fusion (RRF) computes correct scores and preserves ranking."""
    # List A: d1 at rank 0, d2 at rank 1, d3 at rank 2
    # List B: d2 at rank 0, d1 at rank 1, d4 at rank 2
    list_a = [
        {"id": "doc-1", "text": "Doc 1"},
        {"id": "doc-2", "text": "Doc 2"},
        {"id": "doc-3", "text": "Doc 3"},
    ]
    list_b = [
        {"id": "doc-2", "text": "Doc 2"},
        {"id": "doc-1", "text": "Doc 1"},
        {"id": "doc-4", "text": "Doc 4"},
    ]

    fused = reciprocal_rank_fusion(
        vector_results=list_a,
        bm25_results=list_b,
        k=60,
        top_k=5,
    )

    assert len(fused) == 4
    # Both doc-1 and doc-2 appear at ranks 0 and 1 in the two lists:
    # RRF score = 1/(60+1) + 1/(60+2) = 1/61 + 1/62 ≈ 0.01639 + 0.01613 ≈ 0.03252
    top_two_ids = {fused[0]["id"], fused[1]["id"]}
    assert top_two_ids == {"doc-1", "doc-2"}

    # doc-3 and doc-4 only appear once at rank 2:
    # RRF score = 1/(60+3) = 1/63 ≈ 0.01587
    remaining_ids = {fused[2]["id"], fused[3]["id"]}
    assert remaining_ids == {"doc-3", "doc-4"}


def test_cross_encoder_rerank_scoring() -> None:
    """Verify cross_encoder_rerank computes relevance and respects top_n limit."""
    candidates = [
        {"id": "c1", "text": "Weather forecast for sunny California.", "score": 0.5},
        {
            "id": "c2",
            "text": "PgBouncer deployment sidecar for connection pool exhaustion on Payments API.",
            "score": 0.5,
        },
        {
            "id": "c3",
            "text": "Database index tuning for postgres query optimization.",
            "score": 0.5,
        },
        {"id": "c4", "text": "Random unrelated text about gardening.", "score": 0.5},
    ]

    query = "How does PgBouncer prevent connection pool exhaustion on Payments API?"
    reranked = cross_encoder_rerank(query=query, candidates=candidates, top_n=2)

    assert len(reranked) == 2
    assert reranked[0]["id"] == "c2"
    assert reranked[0]["score"] > reranked[1]["score"]


def test_retrieve_hybrid_returns_canonical_evidence(
    sample_chunks: list[VectorChunk],
) -> None:
    """Verify retrieve_hybrid executes full pipeline and produces valid Evidence models (F6)."""
    vector_store = InMemoryVectorStore()
    vector_store.add_chunks(sample_chunks)

    bm25 = BM25Index()
    bm25.index_chunks(sample_chunks)

    query = (
        "What caused the Payments API connection pool outage and what ADR solved it?"
    )
    evidence_items = retrieve_hybrid(
        query=query,
        vector_store=vector_store,
        bm25_index=bm25,
        sub_question_id="sq_hybrid_1",
        top_k_dense=5,
        top_k_bm25=5,
        top_n_final=3,
    )

    assert isinstance(evidence_items, list)
    assert 1 <= len(evidence_items) <= 3

    for item in evidence_items:
        assert isinstance(item, Evidence)
        assert item.source_type == "document"
        assert item.sub_question_id == "sq_hybrid_1"
        assert 0.0 <= item.score <= 1.0
        assert item.metadata["store"] == "vector"
        assert item.metadata["retrieval_strategy"] == "hybrid"
        assert item.locator.startswith("documents/") or item.locator.startswith("doc:")
        assert "#chunk-" in item.locator

    # The top retrieved chunk should be either INC-2031 or ADR-042
    top_content = evidence_items[0].content
    assert (
        "Payments API" in top_content
        or "PgBouncer" in top_content
        or "connection pool" in top_content
    )


def test_hybrid_retriever_class_interface(sample_chunks: list[VectorChunk]) -> None:
    """Verify HybridRetriever class encapsulates hybrid, dense, and sparse search."""
    vector_store = InMemoryVectorStore()
    vector_store.add_chunks(sample_chunks)

    retriever = HybridRetriever(vector_store=vector_store)
    # Automatically indexes chunks from vector_store if bm25_index not explicitly provided
    retriever.index_chunks(sample_chunks)

    # 1. Hybrid search
    res_hybrid = retriever.retrieve(
        query="PgBouncer connection pooler sidecar",
        sub_question_id="sq_h1",
        top_n=2,
    )
    assert len(res_hybrid) <= 2
    assert all(e.source_type == "document" for e in res_hybrid)
    assert any("adr-042" in e.locator for e in res_hybrid)

    # 2. Dense-only search
    res_dense = retriever.retrieve_dense(
        query="Redis cache recovery runbook",
        sub_question_id="sq_dense",
        top_k=1,
    )
    assert len(res_dense) == 1
    assert "runbook-redis" in res_dense[0].locator

    # 3. Sparse-only search
    res_sparse = retriever.retrieve_sparse(
        query="SOC2 compliance data retention",
        sub_question_id="sq_sparse",
        top_k=1,
    )
    assert len(res_sparse) == 1
    assert "policy-data-retention" in res_sparse[0].locator


def test_hybrid_retrieval_with_ingested_corpus(db_session) -> None:
    """Verify hybrid retrieval over documents ingested via ingest_corpus (F6, F13)."""
    from rag.ingest import ingest_corpus
    from rag.vector_store import InMemoryVectorStore

    v_store = InMemoryVectorStore()
    sample_dir = Path(__file__).resolve().parents[2] / "sample_data" / "documents"

    # Ingest corpus
    res = ingest_corpus(
        documents_dir=sample_dir,
        db=db_session,
        vector_store=v_store,
    )
    assert res.total_documents > 0
    assert res.total_chunks > 0

    retriever = HybridRetriever(vector_store=v_store)
    # Automatically indexes all ingested vector chunks into BM25
    retriever.index_chunks(list(v_store._chunks.values()))

    evidence = retriever.retrieve(
        query="Payments API outage caused by database connection pool exhaustion and PgBouncer solution",
        sub_question_id="sq_canonical",
        top_n=3,
    )

    assert len(evidence) == 3
    assert all(isinstance(e, Evidence) for e in evidence)
    assert all(e.source_type == "document" for e in evidence)
    locators = [e.locator for e in evidence]
    # Canonical question documents must be retrieved
    assert any("inc-2031" in loc or "adr-042" in loc for loc in locators)
