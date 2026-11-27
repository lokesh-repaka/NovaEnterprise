"""RAG (Retrieval-Augmented Generation) package for NovaEnterprise.

Encapsulates storage protocols, document ingestion, vector storage,
graph storage, and multi-store retrievers (Claude.md §4.2, §8).
"""

from typing import TYPE_CHECKING, Any

from rag.chunker import (
    ParsedChunk,
    SemanticChunker,
    estimate_tokens,
)
from rag.evidence import (
    Citation,
    Evidence,
    EvidenceSource,
    EvidenceSourceType,
    SubQuestion,
    build_document_locator,
    build_graph_locator,
    build_sql_locator,
    create_document_evidence,
    create_evidence,
    create_graph_evidence,
    create_sql_evidence,
    deduplicate_evidence,
    filter_evidence_by_score,
    generate_evidence_id,
    parse_document_locator,
    parse_graph_locator,
    parse_locator,
    parse_sql_locator,
    sort_evidence_by_score,
    validate_locator,
)
from rag.extractor import (
    EntityRelationshipExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from rag.graph_store import (
    GraphEdge,
    GraphExpansion,
    GraphNode,
    GraphRecord,
    GraphStoreService,
    InMemoryGraphStore,
    Neo4jGraphStore,
    get_graph_store,
    reset_graph_store,
)
from rag.parser import (
    DocumentParser,
    ParsedDocument,
    compute_content_hash,
    detect_prompt_injection,
    wrap_untrusted_data,
)
from rag.vector_store import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorChunk,
    VectorSearchResult,
    VectorStoreService,
    get_vector_store,
    reset_vector_store,
)

if TYPE_CHECKING:
    from rag.ingest import (
        CorpusIngestionResult,
        DocumentIngestionResult,
        generate_offline_embedding,
        ingest_corpus,
        ingest_document,
        ingest_file,
    )

_INGEST_EXPORTS = {
    "CorpusIngestionResult",
    "DocumentIngestionResult",
    "generate_offline_embedding",
    "ingest_corpus",
    "ingest_document",
    "ingest_file",
}


def __getattr__(name: str) -> Any:
    if name in _INGEST_EXPORTS:
        import rag.ingest as _ingest

        return getattr(_ingest, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Citation",
    "CorpusIngestionResult",
    "DocumentIngestionResult",
    "DocumentParser",
    "EntityRelationshipExtractor",
    "Evidence",
    "EvidenceSource",
    "EvidenceSourceType",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionResult",
    "GraphEdge",
    "GraphExpansion",
    "GraphNode",
    "GraphRecord",
    "GraphStoreService",
    "InMemoryGraphStore",
    "InMemoryVectorStore",
    "Neo4jGraphStore",
    "ParsedChunk",
    "ParsedDocument",
    "QdrantVectorStore",
    "SemanticChunker",
    "SubQuestion",
    "VectorChunk",
    "VectorSearchResult",
    "VectorStoreService",
    "build_document_locator",
    "build_graph_locator",
    "build_sql_locator",
    "compute_content_hash",
    "create_document_evidence",
    "create_evidence",
    "create_graph_evidence",
    "create_sql_evidence",
    "deduplicate_evidence",
    "detect_prompt_injection",
    "estimate_tokens",
    "filter_evidence_by_score",
    "generate_evidence_id",
    "generate_offline_embedding",
    "get_graph_store",
    "get_vector_store",
    "ingest_corpus",
    "ingest_document",
    "ingest_file",
    "parse_document_locator",
    "parse_graph_locator",
    "parse_locator",
    "parse_sql_locator",
    "reset_graph_store",
    "reset_vector_store",
    "sort_evidence_by_score",
    "validate_locator",
    "wrap_untrusted_data",
]
