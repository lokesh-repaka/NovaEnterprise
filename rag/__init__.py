"""RAG (Retrieval-Augmented Generation) package for NovaEnterprise.

Encapsulates storage protocols, document ingestion, vector storage,
graph storage, and multi-store retrievers (Claude.md §4.2, §8).
"""

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
    "GraphEdge",
    "GraphExpansion",
    "GraphNode",
    "GraphRecord",
    "GraphStoreService",
    "InMemoryGraphStore",
    "InMemoryVectorStore",
    "Neo4jGraphStore",
    "QdrantVectorStore",
    "VectorChunk",
    "VectorSearchResult",
    "VectorStoreService",
    "get_graph_store",
    "get_vector_store",
    "reset_graph_store",
    "reset_vector_store",
]
