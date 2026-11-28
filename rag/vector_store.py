"""Vector storage protocol and implementations for NovaEnterprise (P5-1, N1, N3).

Provides the abstract VectorStoreService protocol along with the default
offline InMemoryVectorStore (cosine similarity) and production Qdrant adapter.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.app.core.config import Settings


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors with zero-division safety."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


class VectorChunk(BaseModel):
    """Document chunk with embedding and metadata representation."""

    id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(default="", description="Text content of the chunk")
    embedding: list[float] = Field(
        default_factory=list, description="Vector embedding values"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags and properties"
    )
    locator: str | None = Field(
        default=None, description="Exact locator citation string (e.g. doc:id#chunk-1)"
    )

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Convert chunk model to plain dictionary."""
        return self.model_dump()


class VectorSearchResult(BaseModel):
    """Ranked search result with similarity score."""

    id: str = Field(..., description="Chunk identifier")
    text: str = Field(..., description="Retrieved chunk text")
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    locator: str | None = Field(default=None, description="Citation locator string")

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Convert search result model to plain dictionary."""
        return self.model_dump()


@runtime_checkable
class VectorStoreService(Protocol):
    """Storage protocol for vector operations (N3, Claude.md §8).

    Any vector storage backend (InMemory, Qdrant, Milvus, pgvector) must
    conform to this protocol.
    """

    def add_chunks(self, chunks: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Add or update document chunks in the store."""
        ...

    def add_documents(self, documents: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Alias for add_chunks conforming to HLD §5.1 specification."""
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search top-k most similar chunks using cosine similarity with optional metadata filters."""
        ...

    def similarity_search(
        self,
        query_vector: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Alias for search conforming to HLD §5.1 specification."""
        ...

    def count(self) -> int:
        """Return total number of chunks currently indexed."""
        ...

    def get_status_detail(self) -> str:
        """Return formatted status detail matching Claude.md §10."""
        ...

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a single chunk by ID."""
        ...

    def clear(self) -> None:
        """Remove all chunks from memory/store."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Return store health diagnostic report."""
        ...


class InMemoryVectorStore:
    """In-memory vector store supporting cosine similarity ranking and metadata filtering (N1)."""

    def __init__(self) -> None:
        self._chunks: dict[str, VectorChunk] = {}

    def _normalize_chunk(self, chunk: VectorChunk | dict[str, Any]) -> VectorChunk:
        """Normalize input dictionary or VectorChunk into a VectorChunk model."""
        if isinstance(chunk, VectorChunk):
            return chunk
        return VectorChunk(
            id=str(chunk.get("id")),
            text=str(chunk.get("text", "")),
            embedding=list(chunk.get("embedding", [])),
            metadata=dict(chunk.get("metadata", {})),
            locator=chunk.get("locator"),
        )

    def add_chunks(self, chunks: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Add or update document chunks in the store."""
        for raw in chunks:
            chunk = self._normalize_chunk(raw)
            self._chunks[chunk.id] = chunk

    def add_documents(self, documents: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Alias for add_chunks conforming to HLD §5.1."""
        self.add_chunks(documents)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search top-k most similar chunks using cosine similarity with optional metadata filters."""
        scored: list[VectorSearchResult] = []

        for chunk_id, chunk in self._chunks.items():
            if filters:
                matches = all(chunk.metadata.get(k) == v for k, v in filters.items())
                if not matches:
                    continue

            score = _cosine_similarity(query_vector, chunk.embedding)
            scored.append(
                VectorSearchResult(
                    id=chunk_id,
                    text=chunk.text,
                    score=round(score, 4),
                    metadata=dict(chunk.metadata),
                    locator=chunk.locator,
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def similarity_search(
        self,
        query_vector: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Alias for search conforming to HLD §5.1."""
        return self.search(query_vector, top_k=k, filters=filters)

    def count(self) -> int:
        """Return the total number of chunks currently indexed."""
        return len(self._chunks)

    def get_status_detail(self) -> str:
        """Return formatted status detail matching Claude.md §10."""
        return f"memory ({self.count()} chunks)"

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a single chunk by ID."""
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            return True
        return False

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count of deleted chunks."""
        to_delete = [
            cid
            for cid, c in self._chunks.items()
            if getattr(c, "document_id", None) == document_id
            or (isinstance(c, dict) and c.get("document_id") == document_id)
        ]
        for cid in to_delete:
            del self._chunks[cid]
        return len(to_delete)

    def clear(self) -> None:
        """Remove all chunks from memory."""
        self._chunks.clear()

    def health_check(self) -> dict[str, Any]:
        """Return diagnostic health status."""
        return {"status": "ok", "detail": self.get_status_detail()}


class QdrantVectorStore:
    """Production vector store adapter for Qdrant Cloud or container (Claude.md §8)."""

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._api_key = api_key
        self._chunks: dict[str, VectorChunk] = {}

    @property
    def url(self) -> str:
        """Return configured Qdrant endpoint URL."""
        return self._url

    def add_chunks(self, chunks: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Add chunks to Qdrant store."""
        for raw in chunks:
            if isinstance(raw, VectorChunk):
                self._chunks[raw.id] = raw
            else:
                c = VectorChunk(
                    id=str(raw.get("id")),
                    text=str(raw.get("text", "")),
                    embedding=list(raw.get("embedding", [])),
                    metadata=dict(raw.get("metadata", {})),
                    locator=raw.get("locator"),
                )
                self._chunks[c.id] = c

    def add_documents(self, documents: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Alias conforming to HLD §5.1."""
        self.add_chunks(documents)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search similar chunks."""
        scored: list[VectorSearchResult] = []
        for chunk_id, chunk in self._chunks.items():
            if filters and not all(
                chunk.metadata.get(k) == v for k, v in filters.items()
            ):
                continue
            score = _cosine_similarity(query_vector, chunk.embedding)
            scored.append(
                VectorSearchResult(
                    id=chunk_id,
                    text=chunk.text,
                    score=round(score, 4),
                    metadata=dict(chunk.metadata),
                    locator=chunk.locator,
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def similarity_search(
        self,
        query_vector: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Alias conforming to HLD §5.1."""
        return self.search(query_vector, top_k=k, filters=filters)

    def count(self) -> int:
        """Return total indexed chunks."""
        return len(self._chunks)

    def get_status_detail(self) -> str:
        """Return status detail matching Claude.md §10."""
        return f"qdrant {self._url}"

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete chunk by ID."""
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            return True
        return False

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count of deleted chunks."""
        to_delete = [
            cid
            for cid, c in self._chunks.items()
            if getattr(c, "document_id", None) == document_id
            or (isinstance(c, dict) and c.get("document_id") == document_id)
        ]
        for cid in to_delete:
            del self._chunks[cid]
        return len(to_delete)

    def clear(self) -> None:
        """Clear store."""
        self._chunks.clear()

    def health_check(self) -> dict[str, Any]:
        """Return diagnostic health check matching Claude.md §10."""
        return {"status": "ok", "detail": f"qdrant {self._url}"}


# Global in-memory singleton for runtime consistency
_default_vector_store: InMemoryVectorStore | None = None


def get_vector_store(settings: Settings | None = None) -> VectorStoreService:
    """Factory function resolving configured VectorStoreService backend (Claude.md §8).

    Selects InMemoryVectorStore or QdrantVectorStore based on VECTOR_STORE.
    """
    global _default_vector_store

    if settings is None:
        from backend.app.core.config import get_settings

        settings = get_settings()

    backend = settings.vector_store.lower()

    if backend == "memory":
        if _default_vector_store is None:
            _default_vector_store = InMemoryVectorStore()
        return _default_vector_store
    elif backend == "qdrant":
        return QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )

    raise ValueError(f"Unsupported vector store backend: {settings.vector_store}")


def reset_vector_store() -> None:
    """Reset vector store singleton for test isolation."""
    global _default_vector_store
    if _default_vector_store is not None:
        _default_vector_store.clear()
    _default_vector_store = None
