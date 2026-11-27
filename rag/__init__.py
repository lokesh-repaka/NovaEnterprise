"""RAG (Retrieval-Augmented Generation) package for NovaEnterprise.

Encapsulates storage protocols, document ingestion, vector storage,
graph storage, and multi-store retrievers (Claude.md §4.2, §8).
"""

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

__all__ = [
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
    "get_graph_store",
    "get_vector_store",
    "reset_graph_store",
    "reset_vector_store",
    "wrap_untrusted_data",
]
