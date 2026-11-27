"""Document ingestion pipeline for NovaEnterprise (P5-4, F13, N1, N3, N7, N8).

Orchestrates multi-format document parsing, semantic chunking, entity and
relationship extraction, offline embedding generation, vector indexing,
graph knowledge modeling, and relational persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.logging import get_logger
from backend.app.models.documents import Document, DocumentChunk
from backend.app.repositories.documents import (
    DocumentChunkRepository,
    DocumentRepository,
)
from rag.chunker import ParsedChunk, SemanticChunker
from rag.extractor import EntityRelationshipExtractor, ExtractionResult
from rag.graph_store import GraphStoreService, get_graph_store
from rag.parser import DocumentParser, ParsedDocument
from rag.vector_store import VectorChunk, VectorStoreService, get_vector_store

logger = get_logger("rag.ingest")

# Supported file extensions for corpus ingestion (N7)
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}


def generate_offline_embedding(text: str, dim: int = 384) -> list[float]:
    """Generate a deterministic, unit-normalized embedding vector offline (N1, N2).

    Uses word-level SHA-256 seed hashing to produce a reproducible pseudo-random vector
    normalized via L2 norm, compatible with cosine similarity vector search
    without any external network or provider calls.
    """
    import re

    words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
    if not words:
        words = [text.strip()] if text.strip() else ["empty"]

    accum: list[float] = [0.0] * dim
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        seed_ints = list(digest)
        for i in range(dim):
            byte_val = seed_ints[i % len(seed_ints)]
            val = (byte_val ^ ((i * 31) & 0xFF)) / 128.0 - 1.0
            accum[i] += val

    norm = math.sqrt(sum(x * x for x in accum))
    if norm == 0.0:
        norm = 1.0
    return [round(x / norm, 6) for x in accum]


class DocumentIngestionResult(BaseModel):
    """Result summary of a single ingested document."""

    document_id: str = Field(..., description="Unique document UUID")
    filename: str = Field(..., description="Original filename")
    content_hash: str = Field(..., description="SHA-256 content checksum")
    chunk_count: int = Field(..., description="Number of semantic chunks indexed")
    entities_extracted: int = Field(
        ..., description="Number of named entities extracted"
    )
    relationships_extracted: int = Field(
        ..., description="Number of relationships extracted"
    )
    flagged_injection: bool = Field(
        ..., description="Whether prompt injection was detected"
    )
    status: str = Field(default="indexed", description="Ingestion lifecycle status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of ingestion",
    )


class CorpusIngestionResult(BaseModel):
    """Aggregated result summary of full corpus ingestion."""

    total_documents: int = Field(..., description="Total documents processed")
    total_chunks: int = Field(..., description="Total semantic chunks indexed")
    total_entities: int = Field(..., description="Total entities extracted")
    total_relationships: int = Field(..., description="Total relationships extracted")
    flagged_documents: int = Field(
        ..., description="Total documents flagged for injection"
    )
    documents: list[DocumentIngestionResult] = Field(
        default_factory=list, description="Detailed per-document ingestion records"
    )


def ingest_document(
    data: bytes | str,
    filename: str,
    db: Session | None = None,
    vector_store: VectorStoreService | None = None,
    graph_store: GraphStoreService | None = None,
    doc_id: str | None = None,
    settings: Settings | None = None,
) -> DocumentIngestionResult:
    """Ingest a single document into vector store, graph store, and relational database.

    Pipeline stages:
    1. Multi-format parsing, injection detection, and content hashing
    2. Semantic sliding-window chunking and hierarchical citation locators
    3. Named entity and relationship extraction
    4. Offline embedding vector generation and vector store indexing
    5. Knowledge graph node and edge indexing
    6. Relational database persistence (idempotent / deduplicated by content_hash)
    """
    if settings is None:
        settings = get_settings()

    # 1. Parse document
    parser = DocumentParser()
    parsed_doc: ParsedDocument = parser.parse(
        data=data, filename=filename, doc_id=doc_id
    )

    # 2. Chunk document
    chunker = SemanticChunker()
    chunks: list[ParsedChunk] = chunker.chunk(parsed_doc)

    # 3. Extract entities and relationships
    extractor = EntityRelationshipExtractor()
    extraction: ExtractionResult = extractor.extract_from_chunks(
        chunks=chunks,
        doc_id=parsed_doc.id,
        doc_title=parsed_doc.title,
    )

    # 4. Index chunks into Vector Store
    if vector_store is None:
        vector_store = get_vector_store(settings)

    vector_chunks: list[VectorChunk] = []
    for chunk in chunks:
        embedding = generate_offline_embedding(chunk.text)
        v_chunk = chunk.to_vector_chunk(embedding=embedding)
        vector_chunks.append(v_chunk)

    if vector_chunks:
        vector_store.add_chunks(vector_chunks)

    # 5. Index into Knowledge Graph Store
    if graph_store is None:
        graph_store = get_graph_store(settings)

    # Add Document node
    doc_props = {
        "title": parsed_doc.title,
        "filename": parsed_doc.filename,
        "doc_type": parsed_doc.doc_type,
        "content_hash": parsed_doc.content_hash,
        "flagged_injection": parsed_doc.flagged_injection,
    }
    graph_store.add_node(parsed_doc.id, label="Document", properties=doc_props)

    # Add extracted entity nodes and MENTIONS edges from document
    for ent in extraction.entities:
        node = ent.to_graph_node()
        graph_store.add_node(node.id, label=node.label, properties=node.properties)
        mentions_props: dict[str, Any] = {}
        if ent.source_locator:
            mentions_props["locator"] = ent.source_locator
        graph_store.add_edge(
            source=parsed_doc.id,
            target=ent.id,
            rel_type="MENTIONS",
            properties=mentions_props,
        )

    # Add cross-entity extracted relationships
    for rel in extraction.relationships:
        edge = rel.to_graph_edge()
        graph_store.add_edge(
            source=edge.source,
            target=edge.target,
            rel_type=edge.type,
            properties=edge.properties,
        )

    # 6. Relational Database Persistence (if DB session provided)
    target_doc_id = parsed_doc.id
    doc_status = "indexed"
    created_timestamp = datetime.now(timezone.utc)

    if db is not None:
        doc_repo = DocumentRepository(db)
        chunk_repo = DocumentChunkRepository(db)

        # Check for existing document by content hash
        existing_doc = doc_repo.get_by_hash(parsed_doc.content_hash)
        if existing_doc is not None:
            target_doc_id = existing_doc.id
            existing_doc.filename = filename
            existing_doc.chunk_count = len(chunks)
            existing_doc.flagged_injection = parsed_doc.flagged_injection
            existing_doc.status = doc_status
            doc_repo.update(existing_doc)

            # Prune old chunks before re-inserting
            chunk_repo.delete_by_document(target_doc_id)
            created_timestamp = existing_doc.created_at
        else:
            # Check by doc_id as fallback
            existing_by_id = doc_repo.get(parsed_doc.id)
            if existing_by_id is not None:
                existing_by_id.filename = filename
                existing_by_id.content_hash = parsed_doc.content_hash
                existing_by_id.chunk_count = len(chunks)
                existing_by_id.flagged_injection = parsed_doc.flagged_injection
                existing_by_id.status = doc_status
                doc_repo.update(existing_by_id)
                chunk_repo.delete_by_document(target_doc_id)
                created_timestamp = existing_by_id.created_at
            else:
                new_doc = Document(
                    id=parsed_doc.id,
                    filename=filename,
                    content_hash=parsed_doc.content_hash,
                    chunk_count=len(chunks),
                    flagged_injection=parsed_doc.flagged_injection,
                    status=doc_status,
                    created_at=created_timestamp,
                )
                doc_repo.create(new_doc)

        # Bulk insert semantic chunks
        db_chunks = [
            DocumentChunk(
                id=chunk.id,
                document_id=target_doc_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding_id=chunk.id,
                metadata_json=chunk.metadata,
                created_at=created_timestamp,
            )
            for chunk in chunks
        ]
        if db_chunks:
            chunk_repo.create_chunks(db_chunks)

    logger.info(
        "Ingested document '%s' (id=%s): %d chunks, %d entities, %d relationships (flagged=%s)",
        filename,
        target_doc_id,
        len(chunks),
        len(extraction.entities),
        len(extraction.relationships),
        parsed_doc.flagged_injection,
    )

    return DocumentIngestionResult(
        document_id=target_doc_id,
        filename=filename,
        content_hash=parsed_doc.content_hash,
        chunk_count=len(chunks),
        entities_extracted=len(extraction.entities),
        relationships_extracted=len(extraction.relationships),
        flagged_injection=parsed_doc.flagged_injection,
        status=doc_status,
        created_at=created_timestamp,
    )


def ingest_file(
    file_path: str | Path,
    db: Session | None = None,
    vector_store: VectorStoreService | None = None,
    graph_store: GraphStoreService | None = None,
    settings: Settings | None = None,
) -> DocumentIngestionResult:
    """Read a local document file and execute the ingestion pipeline."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Document file not found at '{path}'")

    data = path.read_bytes()
    return ingest_document(
        data=data,
        filename=path.name,
        db=db,
        vector_store=vector_store,
        graph_store=graph_store,
        settings=settings,
    )


def ingest_corpus(
    documents_dir: str | Path = "sample_data/documents",
    db: Session | None = None,
    vector_store: VectorStoreService | None = None,
    graph_store: GraphStoreService | None = None,
    settings: Settings | None = None,
) -> CorpusIngestionResult:
    """Ingest all eligible documents from a directory into all storage subsystems."""
    corpus_path = Path(documents_dir)
    if not corpus_path.is_dir():
        raise NotADirectoryError(f"Corpus directory not found at '{corpus_path}'")

    if settings is None:
        settings = get_settings()

    # Discover and sort files deterministically
    candidate_files = [
        f
        for f in corpus_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    candidate_files.sort(key=lambda p: p.name)

    logger.info(
        "Starting corpus ingestion from '%s' (%d files found)",
        corpus_path,
        len(candidate_files),
    )

    doc_results: list[DocumentIngestionResult] = []
    total_chunks = 0
    total_entities = 0
    total_relationships = 0
    flagged_docs = 0

    # Ensure DB session if none provided
    if db is None:
        engine = get_engine(settings.database_url)
        init_db(engine)
        session_factory = get_session_factory(engine)
        with session_factory() as session:
            for file_path in candidate_files:
                res = ingest_file(
                    file_path=file_path,
                    db=session,
                    vector_store=vector_store,
                    graph_store=graph_store,
                    settings=settings,
                )
                doc_results.append(res)
                total_chunks += res.chunk_count
                total_entities += res.entities_extracted
                total_relationships += res.relationships_extracted
                if res.flagged_injection:
                    flagged_docs += 1
    else:
        for file_path in candidate_files:
            res = ingest_file(
                file_path=file_path,
                db=db,
                vector_store=vector_store,
                graph_store=graph_store,
                settings=settings,
            )
            doc_results.append(res)
            total_chunks += res.chunk_count
            total_entities += res.entities_extracted
            total_relationships += res.relationships_extracted
            if res.flagged_injection:
                flagged_docs += 1

    logger.info(
        "Corpus ingestion complete: %d docs, %d chunks, %d entities, %d relationships (%d flagged)",
        len(doc_results),
        total_chunks,
        total_entities,
        total_relationships,
        flagged_docs,
    )

    return CorpusIngestionResult(
        total_documents=len(doc_results),
        total_chunks=total_chunks,
        total_entities=total_entities,
        total_relationships=total_relationships,
        flagged_documents=flagged_docs,
        documents=doc_results,
    )


def main() -> None:
    """CLI entrypoint for running ingestion via `python -m rag.ingest`."""
    parser = argparse.ArgumentParser(
        description="NovaEnterprise Document Ingestion CLI"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="sample_data/documents",
        help="Path to documents corpus directory (default: sample_data/documents)",
    )
    args = parser.parse_args()

    print("=== NovaEnterprise Document Ingestion ===")
    print(f"Indexing corpus from: {args.dir}")

    try:
        result = ingest_corpus(documents_dir=args.dir)
        print("\n=== Ingestion Summary ===")
        print(f"Total Documents:     {result.total_documents}")
        print(f"Total Chunks:        {result.total_chunks}")
        print(f"Entities Extracted:  {result.total_entities}")
        print(f"Rels Extracted:      {result.total_relationships}")
        print(f"Flagged Injections:  {result.flagged_documents}")
        print("Status: SUCCESS\n")
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"\n[ERROR] Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
