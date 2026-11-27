"""Pydantic v2 schemas for document ingestion and management (P5-4, F13, N7)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Document summary metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Original filename")
    content_hash: str = Field(..., description="SHA-256 content checksum")
    chunk_count: int = Field(..., description="Total semantic chunks indexed")
    flagged_injection: bool = Field(
        ..., description="Whether prompt injection payload was detected"
    )
    status: str = Field(..., description="Ingestion lifecycle status")
    created_at: datetime = Field(..., description="Timestamp of document ingestion")


class DocumentUploadResponse(BaseModel):
    """Response returned upon successful document upload and indexing."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Original filename")
    content_hash: str = Field(..., description="SHA-256 content checksum")
    chunk_count: int = Field(..., description="Total semantic chunks indexed")
    entities_extracted: int = Field(
        ..., description="Count of named entities extracted into knowledge graph"
    )
    flagged_injection: bool = Field(
        ..., description="Whether prompt injection payload was detected"
    )
    status: str = Field(..., description="Ingestion lifecycle status")
    created_at: datetime = Field(..., description="Timestamp of document ingestion")


class DocumentChunkDetail(BaseModel):
    """Semantic chunk detail representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique chunk UUID")
    chunk_index: int = Field(..., description="0-indexed position within document")
    text: str = Field(..., description="Chunk text content")
    embedding_id: str | None = Field(
        default=None, description="Vector store embedding identifier"
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata tags, section hierarchy, and attributes",
    )


class DocumentDetailResponse(BaseModel):
    """Detailed document representation including chunk breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Original filename")
    content_hash: str = Field(..., description="SHA-256 content checksum")
    chunk_count: int = Field(..., description="Total semantic chunks indexed")
    flagged_injection: bool = Field(
        ..., description="Whether prompt injection payload was detected"
    )
    status: str = Field(..., description="Ingestion lifecycle status")
    created_at: datetime = Field(..., description="Timestamp of document ingestion")
    chunks: list[DocumentChunkDetail] = Field(
        default_factory=list, description="Ordered semantic chunks"
    )
