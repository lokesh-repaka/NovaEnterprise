"""Unit tests for document parsing and semantic chunking (P5-2, F13, N8).

Validates multi-format parsing (.md, .txt, .pdf), SHA-256 content hashing,
prompt injection detection, semantic boundary splitting, markdown header
preservation, and locator generation across enterprise documents.
"""

import io
from pathlib import Path

import pytest

from rag.chunker import (
    ParsedChunk,
    SemanticChunker,
)
from rag.parser import (
    DocumentParser,
    ParsedDocument,
)
from rag.vector_store import VectorChunk


class TestDocumentParser:
    """Tests for multi-format document parsing and injection detection."""

    def test_markdown_parsing_and_metadata_extraction(self) -> None:
        """Verify markdown parsing extracts title, metadata attributes, and content hash."""
        sample_md = """# Incident Postmortem: INC-2031 Payments API Latency Spike

**Incident Reference:** INC-2031
**Severity:** SEV1
**Target Service:** Payments API (`svc-payments-api`)
**Owning Team:** Payments Platform (`team-payments`)

---

## Executive Summary

On May 14, 2026, the Payments API experienced a critical degradation lasting 150 minutes.
"""
        parser = DocumentParser()
        doc = parser.parse_text(
            content=sample_md,
            filename="postmortem-inc-2031-payments-api-outage.md",
            doc_id="doc-inc-2031",
        )

        assert isinstance(doc, ParsedDocument)
        assert doc.id == "doc-inc-2031"
        assert doc.filename == "postmortem-inc-2031-payments-api-outage.md"
        assert doc.title == "Incident Postmortem: INC-2031 Payments API Latency Spike"
        assert doc.doc_type == "postmortem"
        assert doc.metadata.get("severity") == "SEV1"
        assert doc.metadata.get("incident_reference") == "INC-2031"
        assert doc.content_hash is not None
        assert len(doc.content_hash) == 64  # SHA-256
        assert doc.flagged_injection is False

    def test_plain_text_parsing(self) -> None:
        """Verify plain text file parsing."""
        raw_text = "System maintenance alert for identity cluster.\nScheduled window: 02:00 UTC."
        parser = DocumentParser()
        doc = parser.parse_text(
            content=raw_text,
            filename="maintenance-notice.txt",
        )
        assert doc.doc_type == "text"
        assert doc.filename == "maintenance-notice.txt"
        assert "System maintenance alert" in doc.text
        assert doc.flagged_injection is False

    def test_pdf_parsing_in_memory(self) -> None:
        """Verify PDF document parsing extracting text and page metadata."""
        import pypdf

        # Generate a minimal valid PDF in-memory using pypdf
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        stream = io.BytesIO()
        writer.write(stream)
        pdf_bytes = stream.getvalue()

        parser = DocumentParser()
        doc = parser.parse_bytes(
            data=pdf_bytes,
            filename="sample-doc.pdf",
        )
        assert doc.filename == "sample-doc.pdf"
        assert doc.doc_type == "pdf"
        assert doc.content_hash is not None

    def test_unsupported_file_extension_raises(self) -> None:
        """Verify unsupported extensions raise descriptive ValueError."""
        parser = DocumentParser()
        with pytest.raises(ValueError, match="Unsupported file type"):
            parser.parse_bytes(b"MZ...", filename="malicious.exe")

    def test_prompt_injection_detection_and_quarantine(self) -> None:
        """Verify deliberate prompt injection payload is quarantined and flagged (F13, N8)."""
        parser = DocumentParser()
        vendor_note_path = Path("sample_data/documents/vendor-note-processor-update.md")
        assert vendor_note_path.exists(), "Sample vendor note document must exist"

        doc = parser.parse_file(vendor_note_path)

        assert doc.flagged_injection is True
        assert doc.metadata.get("flagged_injection") is True
        assert doc.metadata.get("sanitized") is True
        # Verify untrusted wrapper envelope is applied
        assert "<untrusted_document_data>" in doc.text
        assert "</untrusted_document_data>" in doc.text

    def test_clean_document_not_flagged(self) -> None:
        """Verify legitimate engineering postmortem is not falsely flagged."""
        parser = DocumentParser()
        postmortem_path = Path(
            "sample_data/documents/postmortem-inc-2031-payments-api-outage.md"
        )
        assert postmortem_path.exists()

        doc = parser.parse_file(postmortem_path)
        assert doc.flagged_injection is False
        assert doc.metadata.get("flagged_injection") is False


class TestSemanticChunker:
    """Tests for hierarchical semantic chunking and locator generation."""

    def test_chunking_with_header_preservation(self) -> None:
        """Verify chunker preserves header context and hierarchical paths."""
        text = """# Incident Postmortem: INC-2031

## Executive Summary
Payments API suffered connection saturation. Three customers were affected.

## Technical Root Cause Analysis
PgBouncer was missing. HPA autoscaled to 12 pods. Server connection limit of 200 was breached.

## Permanent Corrective Decisions
Adopted PgBouncer in transaction pooling mode under ADR-042.
"""
        chunker = SemanticChunker(chunk_size=150, chunk_overlap=30)
        chunks = chunker.chunk_document(
            text=text,
            doc_id="postmortem-inc-2031",
            metadata={"doc_type": "postmortem", "service": "payments-api"},
        )

        assert len(chunks) >= 3
        # Verify each chunk has hierarchical section information
        sections = [c.section_title for c in chunks if c.section_title]
        assert "Executive Summary" in sections
        assert "Technical Root Cause Analysis" in sections
        assert "Permanent Corrective Decisions" in sections

        # Verify citation locator format
        for i, c in enumerate(chunks):
            assert c.locator == f"doc:postmortem-inc-2031#chunk-{i}"
            assert c.doc_id == "postmortem-inc-2031"
            assert c.chunk_index == i

    def test_sliding_window_overlap(self) -> None:
        """Verify chunks enforce sliding-window overlap on long sections."""
        long_section = (
            "# Large Policy Document\n\n## Section 1\n"
            + "This is a detailed enterprise paragraph describing authorization policies in depth. "
            * 25
        )
        chunker = SemanticChunker(chunk_size=200, chunk_overlap=50)
        chunks = chunker.chunk_document(long_section, doc_id="policy-01")

        assert len(chunks) > 1
        # Check that adjacent chunks have overlapping words
        chunk0_words = set(chunks[0].text.split()[-10:])
        chunk1_words = set(chunks[1].text.split()[:20])
        assert len(chunk0_words & chunk1_words) > 0

    def test_vector_chunk_conversion(self) -> None:
        """Verify ParsedChunk converts seamlessly into VectorChunk."""
        chunk = ParsedChunk(
            id="chk-001",
            doc_id="doc-123",
            chunk_index=0,
            text="Enterprise document chunk text",
            section_title="Architecture",
            locator="doc:doc-123#chunk-0",
            metadata={"doc_type": "adr", "service": "billing"},
        )

        v_chunk = chunk.to_vector_chunk(embedding=[0.1, 0.2, 0.3])
        assert isinstance(v_chunk, VectorChunk)
        assert v_chunk.id == "chk-001"
        assert v_chunk.text == "Enterprise document chunk text"
        assert v_chunk.embedding == [0.1, 0.2, 0.3]
        assert v_chunk.locator == "doc:doc-123#chunk-0"
        assert v_chunk.metadata["section_title"] == "Architecture"
        assert v_chunk.metadata["doc_id"] == "doc-123"


class TestSampleDataIngestCorpus:
    """Integration test verifying parser and chunker across the entire 15 sample documents."""

    def test_all_15_sample_documents_parse_and_chunk(self) -> None:
        """Verify all 15 documents in sample_data/documents/ are parsed and chunked."""
        docs_dir = Path("sample_data/documents")
        assert docs_dir.exists() and docs_dir.is_dir()

        doc_files = sorted(docs_dir.glob("*.md"))
        assert len(doc_files) == 15, (
            f"Expected 15 sample documents, found {len(doc_files)}"
        )

        parser = DocumentParser()
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=64)

        total_chunks = 0
        flagged_count = 0

        for file_path in doc_files:
            parsed = parser.parse_file(file_path)
            assert parsed.content_hash, (
                f"Document {file_path.name} missing content hash"
            )
            assert parsed.title, f"Document {file_path.name} missing extracted title"

            if parsed.flagged_injection:
                flagged_count += 1
                assert file_path.name == "vendor-note-processor-update.md"

            chunks = chunker.chunk_document(
                text=parsed.text,
                doc_id=parsed.id,
                metadata=parsed.metadata,
            )
            assert len(chunks) >= 1, f"Document {file_path.name} generated 0 chunks"
            total_chunks += len(chunks)

        # Only the hostile vendor note must be flagged
        assert flagged_count == 1
        # Chunk count should be around ~70 chunks (Claude.md §6)
        assert 50 <= total_chunks <= 100, f"Expected ~70 chunks, got {total_chunks}"
