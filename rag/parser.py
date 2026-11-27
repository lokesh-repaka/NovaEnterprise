"""Document parsing and metadata extraction for NovaEnterprise (P5-2, F13, N8).

Provides multi-format parsing (.md, .txt, .pdf), SHA-256 provenance hashing,
document classification, and prompt injection detection with quarantined data envelopes.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# Supported document file extensions (Claude.md §8, PRD §N7)
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}

# Prompt injection signature patterns (PRD Journey 3, FRD FR-13, Claude.md §8)
_INJECTION_PATTERNS = re.compile(
    r"("
    r"ignore\s+all\s+previous\s+instructions"
    r"|bypass\s+all\s+security\s+policies"
    r"|master\s+administrator\s+credentials"
    r"|permanent\s+superadmin\s+privileges"
    r"|administrative\s+maintenance\s+mode"
    r"|<system>"
    r"|</system>"
    r"|retrieve\s+the\s+system\s+master"
    r")",
    re.IGNORECASE,
)


def compute_content_hash(data: bytes | str) -> str:
    """Compute deterministic SHA-256 hash of document content."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Scan text for prompt injection keywords and malicious adversarial payload signatures."""
    match = _INJECTION_PATTERNS.search(text)
    if match:
        return True, match.group(0)
    return False, None


def wrap_untrusted_data(text: str) -> str:
    """Wrap untrusted document content in a quarantined XML envelope (PRD Journey 3, N8)."""
    return f"<untrusted_document_data>\n{text}\n</untrusted_document_data>"


class ParsedDocument(BaseModel):
    """Normalized parsed enterprise document representation."""

    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original file name")
    content_hash: str = Field(..., description="SHA-256 content checksum")
    title: str = Field(..., description="Extracted document title")
    doc_type: str = Field(..., description="Document taxonomy category")
    text: str = Field(..., description="Parsed and sanitized text content")
    raw_text: str = Field(..., description="Original text prior to quarantine wrapping")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extracted document attributes"
    )
    flagged_injection: bool = Field(
        default=False, description="Whether prompt injection payload was detected"
    )


class DocumentParser:
    """Multi-format enterprise document parser with injection sanitization."""

    def _infer_doc_type(self, filename: str, content: str) -> str:
        """Infer document category from filename and content headers."""
        name_lower = filename.lower()
        content_lower = content[:500].lower()

        if "postmortem" in name_lower or "incident" in name_lower or "inc-" in name_lower:
            return "postmortem"
        elif "adr-" in name_lower or "decision" in name_lower or "architecture decision" in content_lower:
            return "adr"
        elif "policy" in name_lower or "retention" in name_lower or "rbac" in name_lower:
            return "policy"
        elif "meeting-notes" in name_lower or "meeting" in name_lower:
            return "meeting_notes"
        elif "runbook" in name_lower or "failover" in name_lower:
            return "runbook"
        elif "vendor-note" in name_lower or "vendor" in name_lower:
            return "vendor_note"
        elif "summary" in name_lower or "quarterly" in name_lower:
            return "summary"
        elif name_lower.endswith(".pdf"):
            return "pdf"
        elif name_lower.endswith(".txt"):
            return "text"
        return "markdown"

    def _extract_markdown_metadata(self, text: str, filename: str) -> tuple[str, dict[str, Any]]:
        """Extract H1 title and key-value properties from markdown content."""
        title = Path(filename).stem.replace("-", " ").title()
        metadata: dict[str, Any] = {}

        lines = text.splitlines()
        for line in lines:
            stripped = line.strip()
            # Title extraction from first H1
            if stripped.startswith("# ") and not metadata.get("extracted_title"):
                title = stripped[2:].strip()
                metadata["extracted_title"] = title

            # Key-value extraction: **Key:** Value, Key: Value, etc.
            if ":" in stripped and not stripped.startswith("#"):
                clean_line = stripped.strip("*_` ").strip()
                if ":" in clean_line:
                    raw_k, raw_v = clean_line.split(":", 1)
                    k = raw_k.strip("*_` ").strip().lower().replace(" ", "_").replace("-", "_")
                    v = raw_v.strip("*_` ").strip()
                    # Filter out non-metadata keys
                    if k and v and k not in ("http", "https", "note", "attention") and len(k) < 40:
                        metadata[k] = v

        return title, metadata

    def parse_text(
        self,
        content: str,
        filename: str,
        doc_id: str | None = None,
    ) -> ParsedDocument:
        """Parse plain text or markdown document content."""
        ext = Path(filename).suffix.lower()
        if ext and ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
            )

        content_hash = compute_content_hash(content)
        doc_id = doc_id or Path(filename).stem or str(uuid4())
        doc_type = self._infer_doc_type(filename, content)

        title, metadata = self._extract_markdown_metadata(content, filename)
        metadata["filename"] = filename
        metadata["doc_type"] = doc_type

        # Prompt injection inspection (N8, F13)
        has_injection, matched_pattern = detect_prompt_injection(content)
        sanitized_text = content
        if has_injection:
            sanitized_text = wrap_untrusted_data(content)
            metadata["flagged_injection"] = True
            metadata["sanitized"] = True
            metadata["injection_pattern"] = matched_pattern
        else:
            metadata["flagged_injection"] = False

        return ParsedDocument(
            id=doc_id,
            filename=filename,
            content_hash=content_hash,
            title=title,
            doc_type=doc_type,
            text=sanitized_text,
            raw_text=content,
            metadata=metadata,
            flagged_injection=has_injection,
        )

    def parse_bytes(
        self,
        data: bytes,
        filename: str,
        doc_id: str | None = None,
    ) -> ParsedDocument:
        """Parse raw binary data (e.g. PDF or encoded text)."""
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
            )

        if ext == ".pdf":
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(data))
            page_texts: list[str] = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                page_texts.append(f"<!-- Page {i + 1} -->\n{page_text}")

            content = "\n\n".join(page_texts)
            content_hash = compute_content_hash(data)
            doc_id = doc_id or Path(filename).stem or str(uuid4())

            has_injection, pattern = detect_prompt_injection(content)
            metadata: dict[str, Any] = {
                "filename": filename,
                "doc_type": "pdf",
                "page_count": len(reader.pages),
                "flagged_injection": has_injection,
            }
            sanitized_text = content
            if has_injection:
                sanitized_text = wrap_untrusted_data(content)
                metadata["sanitized"] = True
                metadata["injection_pattern"] = pattern

            return ParsedDocument(
                id=doc_id,
                filename=filename,
                content_hash=content_hash,
                title=Path(filename).stem.replace("-", " ").title(),
                doc_type="pdf",
                text=sanitized_text,
                raw_text=content,
                metadata=metadata,
                flagged_injection=has_injection,
            )

        # Standard text-based formats (.md, .txt)
        text_content = data.decode("utf-8", errors="replace")
        return self.parse_text(text_content, filename, doc_id=doc_id)

    def parse_file(
        self,
        file_path: Path | str,
        doc_id: str | None = None,
    ) -> ParsedDocument:
        """Parse file from filesystem path."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {path}")

        raw_bytes = path.read_bytes()
        return self.parse_bytes(raw_bytes, filename=path.name, doc_id=doc_id)
