"""Semantic and hierarchical document chunking for NovaEnterprise (P5-2, F13, N3).

Splits parsed documents along markdown headings and structural boundaries,
maintains section header hierarchies, and generates exact citation locators.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from rag.vector_store import VectorChunk


def estimate_tokens(text: str) -> int:
    """Estimate token count deterministically and 100% offline (N1).

    Uses a fast word/punctuation tokenizer that approximates BPE token lengths
    without requiring external network downloads or live tokenizer endpoints.
    """
    if not text:
        return 0
    # Words + punctuation tokens
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return len(tokens)


class ParsedChunk(BaseModel):
    """Semantic document chunk carrying structural metadata and citation locator."""

    id: str = Field(..., description="Unique chunk identifier")
    doc_id: str = Field(..., description="Parent document identifier")
    chunk_index: int = Field(..., description="0-indexed position within parent document")
    text: str = Field(..., description="Chunk text content")
    section_title: str | None = Field(
        default=None, description="Immediate heading under which chunk occurs"
    )
    section_hierarchy: list[str] = Field(
        default_factory=list,
        description="Hierarchical heading path (e.g. ['H1 Title', 'H2 Subtitle'])",
    )
    locator: str = Field(
        ..., description="Canonical citation locator (e.g. doc:id#chunk-0)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Inherited and chunk-specific metadata"
    )
    token_count: int = Field(default=0, description="Estimated token count")

    def to_vector_chunk(self, embedding: list[float] | None = None) -> VectorChunk:
        """Convert parsed chunk into VectorChunk model for VectorStoreService ingestion."""
        combined_meta = dict(self.metadata)
        combined_meta["doc_id"] = self.doc_id
        combined_meta["chunk_index"] = self.chunk_index
        if self.section_title:
            combined_meta["section_title"] = self.section_title
        if self.section_hierarchy:
            combined_meta["section_hierarchy"] = list(self.section_hierarchy)

        return VectorChunk(
            id=self.id,
            text=self.text,
            embedding=list(embedding or []),
            metadata=combined_meta,
            locator=self.locator,
        )


class SemanticChunker:
    """Hierarchical and sliding-window document chunker (PRD §OQ-1)."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        """Initialize chunker with token targets and overlap parameters."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_into_sections(self, text: str) -> list[tuple[list[str], str]]:
        """Split markdown text into sections by heading levels (#, ##, ###).

        Returns a list of tuples: (hierarchy_path, section_body_text).
        """
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        if not matches:
            # No headings found, treat entire text as single section
            return [([], text.strip())]

        sections: list[tuple[list[str], str]] = []
        heading_stack: list[tuple[int, str]] = []

        # Content before first heading
        first_start = matches[0].start()
        preamble = text[:first_start].strip()
        if preamble:
            sections.append(([], preamble))

        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()

            # Update heading stack
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

            current_hierarchy = [h[1] for h in heading_stack]

            # Content between current heading and next heading
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            if body:
                sections.append((current_hierarchy, body))
            elif i == len(matches) - 1:
                # Terminal section with only header
                sections.append((current_hierarchy, title))

        return sections

    def _split_section_text(self, text: str) -> list[str]:
        """Split a long text block using paragraphs and sliding-window overlap."""
        tokens = re.findall(r"\w+|[^\w\s]", text)
        if len(tokens) <= self.chunk_size:
            return [text]

        # Break text into word/whitespace tokens for reconstructed chunks
        words = text.split()
        if not words:
            return [text]

        chunks: list[str] = []
        step = max(1, self.chunk_size - self.chunk_overlap)

        idx = 0
        while idx < len(words):
            chunk_words = words[idx : idx + self.chunk_size]
            chunk_str = " ".join(chunk_words).strip()
            if chunk_str:
                chunks.append(chunk_str)
            idx += step

        return chunks

    def chunk_document(
        self,
        text: str,
        doc_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[ParsedChunk]:
        """Chunk a document into semantic chunks preserving markdown hierarchy and locators."""
        doc_meta = dict(metadata or {})
        sections = self._split_into_sections(text)

        chunks: list[ParsedChunk] = []
        chunk_idx = 0

        for hierarchy, section_text in sections:
            section_title = hierarchy[-1] if hierarchy else None
            section_chunks = self._split_section_text(section_text)

            for sub_text in section_chunks:
                clean_text = sub_text.strip()
                if not clean_text:
                    continue

                locator = f"doc:{doc_id}#chunk-{chunk_idx}"
                chunk_id = f"{doc_id}_chunk_{chunk_idx}"
                token_count = estimate_tokens(clean_text)

                chunk = ParsedChunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    chunk_index=chunk_idx,
                    text=clean_text,
                    section_title=section_title,
                    section_hierarchy=list(hierarchy),
                    locator=locator,
                    metadata=dict(doc_meta),
                    token_count=token_count,
                )
                chunks.append(chunk)
                chunk_idx += 1

        return chunks
