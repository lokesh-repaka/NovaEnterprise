"""In-memory mock stores for offline Vector and Graph RAG operations (N1, N3).

Re-exports InMemoryVectorStore and InMemoryGraphStore from rag domain package
to preserve backwards compatibility with test fixtures.
"""

from rag.graph_store import InMemoryGraphStore
from rag.vector_store import (
    InMemoryVectorStore,
    _cosine_similarity,
)

__all__ = [
    "InMemoryGraphStore",
    "InMemoryVectorStore",
    "_cosine_similarity",
]
