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
    "CorpusIngestionResult",
    "DocumentIngestionResult",
    "DocumentParser",
    "EntityRelationshipExtractor",
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
    "VectorChunk",
    "VectorSearchResult",
    "VectorStoreService",
    "compute_content_hash",
    "detect_prompt_injection",
    "estimate_tokens",
    "generate_offline_embedding",
    "get_graph_store",
    "get_vector_store",
    "ingest_corpus",
    "ingest_document",
    "ingest_file",
    "reset_graph_store",
    "reset_vector_store",
    "wrap_untrusted_data",
]
