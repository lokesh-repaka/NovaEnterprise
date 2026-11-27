"""Canonical Evidence, Citation, and SubQuestion contracts (Claude.md §5, API_CONTRACT.md §2).

Provides the unified Evidence shape shared across all three retrieval paths
(Hybrid/Vector Document RAG, Governed SQL, and Typed Graph Traversals).
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceSource(str, Enum):
    """Enumeration of canonical evidence retrieval sources."""

    DOCUMENT = "document"
    SQL = "sql"
    GRAPH = "graph"


# Canonical string literal type
EvidenceSourceType = Literal["document", "sql", "graph"]


class Evidence(BaseModel):
    """Canonical evidence item produced by all three retrieval paths (Claude.md §5).

    Every retriever (Document hybrid, SQL allowlist, Graph traversal) returns
    this exact shape, differing only in `source_type` and `locator`.
    """

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str = Field(..., description="Unique evidence identifier (e.g. evi_<hash>)")
    sub_question_id: str = Field(
        ...,
        description="ID of the decomposed sub-question that triggered this retrieval",
    )
    source_type: EvidenceSourceType = Field(
        ..., description="Retrieval source store type: 'document', 'sql', or 'graph'"
    )
    locator: str = Field(
        ...,
        description="Exact citation locator (document filename/chunk, SQL table/row ID, or Cypher graph path)",
    )
    content: str = Field(
        ..., description="Plaintext content snippet or serialized record data"
    )
    score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relevance or confidence score normalized between 0.0 and 1.0",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Store-specific provenance data (store, table, chunk_id, sql_query, cypher, etc.)",
    )

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence item to dictionary representation."""
        return self.model_dump()


class Citation(BaseModel):
    """Verified citation marker linking a synthesized answer claim to evidence (F11, F12)."""

    model_config = ConfigDict(from_attributes=True)

    citation_id: int = Field(
        ..., description="Sequential citation marker integer index (e.g. 1 for [1])"
    )
    evidence_id: str = Field(
        ..., description="ID of the resolved Evidence object supporting the claim"
    )
    source_type: EvidenceSourceType = Field(
        ..., description="Source store type: 'document', 'sql', or 'graph'"
    )
    locator: str = Field(
        ..., description="Exact citation locator of the supporting evidence"
    )
    snippet: str = Field(
        ..., description="Brief claim-supporting quotation or extracted text snippet"
    )


class SubQuestion(BaseModel):
    """Decomposed research sub-question allocated to a specific retrieval strategy (F4, F5)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique sub-question identifier (e.g. sq1, sq2)")
    question: str = Field(..., description="Decomposed sub-question query prompt")
    strategy: str = Field(
        ...,
        description="Allocated retrieval strategy ('vector', 'hybrid', 'sql', 'graph')",
    )
    status: Literal["pending", "answered", "failed"] = Field(
        default="pending", description="Sub-question execution lifecycle status"
    )
