"""Evidence locator construction, parsing, and collection utilities (P6-1, F5–F8).

Provides:
- Deterministic locator builders and parsers for Document, SQL, and Graph stores
- Canonical Evidence factories and ID generation
- Evidence collection deduplication, ranking, and score filtering
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from backend.app.schemas.common import (
    Citation,
    Evidence,
    EvidenceSource,
    EvidenceSourceType,
    SubQuestion,
)

__all__ = [
    "Citation",
    "Evidence",
    "EvidenceSource",
    "EvidenceSourceType",
    "SubQuestion",
    "build_document_locator",
    "build_graph_locator",
    "build_sql_locator",
    "create_document_evidence",
    "create_evidence",
    "create_graph_evidence",
    "create_sql_evidence",
    "deduplicate_evidence",
    "filter_evidence_by_score",
    "generate_evidence_id",
    "parse_document_locator",
    "parse_graph_locator",
    "parse_locator",
    "parse_sql_locator",
    "sort_evidence_by_score",
    "validate_locator",
]

# Regex patterns for locator parsing
_DOC_LOCATOR_RE = re.compile(
    r"^(?:documents/|doc:)?(?P<id_or_file>[^#]+)(?:#(?P<anchor>.+))?$"
)
_SQL_LOCATOR_RE = re.compile(
    r"^sql:(?P<table>[a-zA-Z0-9_]+)(?::(?P<row_id>[a-zA-Z0-9_\-\.]+))?$"
)
_GRAPH_DIRECTED_OUT_RE = re.compile(
    r"^\((?P<src_label>[^:]+):(?P<src_id>[^)]+)\)-\[:(?P<rel>[^\]]+)\]->\((?P<tgt_label>[^:]+):(?P<tgt_id>[^)]+)\)$"
)
_GRAPH_DIRECTED_IN_RE = re.compile(
    r"^\((?P<src_label>[^:]+):(?P<src_id>[^)]+)\)<-\[:(?P<rel>[^\]]+)\]-\((?P<tgt_label>[^:]+):(?P<tgt_id>[^)]+)\)$"
)


def generate_evidence_id(
    sub_question_id: str,
    source_type: str,
    locator: str,
    content: str,
) -> str:
    """Generate a reproducible, collision-resistant evidence ID (evi_<hash>)."""
    payload = f"{sub_question_id}|{source_type}|{locator}|{content}".encode()
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"evi_{digest}"


# -----------------------------------------------------------------------------
# Document Locator Builders and Parsers
# -----------------------------------------------------------------------------


def build_document_locator(
    filename_or_id: str,
    section: str | None = None,
    chunk_index: int | None = None,
) -> str:
    """Construct canonical document citation locator string.

    Examples:
        - "documents/adr-042-pgbouncer.md#Section-2"
        - "doc:doc-550e8400#chunk-3"
        - "documents/policy-data-retention.md#chunk-1"
    """
    clean_target = filename_or_id.strip()

    # If it's a doc ID (doc:id or uuid)
    if clean_target.startswith("doc:"):
        base = clean_target
    elif clean_target.endswith((".md", ".txt", ".pdf", ".markdown")):
        base = (
            clean_target
            if clean_target.startswith("documents/")
            else f"documents/{clean_target}"
        )
    elif clean_target.startswith("documents/"):
        base = clean_target
    else:
        # Generic identifier
        base = f"doc:{clean_target}"

    if chunk_index is not None:
        return f"{base}#chunk-{chunk_index}"
    elif section is not None:
        clean_section = section.strip()
        return f"{base}#{clean_section}"
    return base


def parse_document_locator(locator: str) -> dict[str, Any]:
    """Parse document locator into constituent components."""
    clean_loc = locator.strip()
    match = _DOC_LOCATOR_RE.match(clean_loc)

    filename: str | None = None
    doc_id: str | None = None
    section: str | None = None
    chunk_index: int | None = None

    if match:
        id_or_file = match.group("id_or_file")
        anchor = match.group("anchor")

        if id_or_file.endswith((".md", ".txt", ".pdf", ".markdown")):
            filename = id_or_file.replace("documents/", "")
        else:
            doc_id = id_or_file.replace("doc:", "")

        if anchor:
            if anchor.startswith("chunk-"):
                try:
                    chunk_index = int(anchor.split("chunk-")[1])
                except ValueError:
                    section = anchor
            else:
                section = anchor

    return {
        "source_type": "document",
        "filename": filename,
        "doc_id": doc_id,
        "section": section,
        "chunk_index": chunk_index,
        "raw_locator": locator,
    }


# -----------------------------------------------------------------------------
# SQL Locator Builders and Parsers
# -----------------------------------------------------------------------------


def build_sql_locator(
    table: str,
    row_id: str | int | None = None,
    query: str | None = None,
) -> str:
    """Construct canonical SQL table and primary key locator string.

    Examples:
        - "sql:customers:cust-acme"
        - "sql:incidents:inc-2031"
        - "sql:services"
    """
    clean_table = table.strip().lower()
    if row_id is not None:
        return f"sql:{clean_table}:{row_id}"
    return f"sql:{clean_table}"


def parse_sql_locator(locator: str) -> dict[str, Any]:
    """Parse SQL locator into table and optional row ID."""
    clean_loc = locator.strip()
    match = _SQL_LOCATOR_RE.match(clean_loc)
    table: str | None = None
    row_id: str | None = None

    if match:
        table = match.group("table")
        row_id = match.group("row_id")

    return {
        "source_type": "sql",
        "table": table,
        "row_id": row_id,
        "raw_locator": locator,
    }


# -----------------------------------------------------------------------------
# Graph Locator Builders and Parsers
# -----------------------------------------------------------------------------


def build_graph_locator(
    source_label: str,
    source_id: str,
    rel_type: str,
    target_label: str,
    target_id: str,
    direction: Literal["out", "in"] = "out",
) -> str:
    """Construct canonical Cypher path locator.

    Examples:
        - "(Service:svc-payments-api)<-[:AFFECTED]-(Incident:inc-2031)"
        - "(Incident:inc-2031)-[:IMPACTED]->(Customer:cust-acme)"
    """
    if direction == "in":
        return (
            f"({source_label}:{source_id})<-[:{rel_type}]-({target_label}:{target_id})"
        )
    return f"({source_label}:{source_id})-[:{rel_type}]->({target_label}:{target_id})"


def parse_graph_locator(locator: str) -> dict[str, Any]:
    """Parse graph traversal locator into node and relationship elements."""
    clean_loc = locator.strip()

    match_out = _GRAPH_DIRECTED_OUT_RE.match(clean_loc)
    if match_out:
        return {
            "source_type": "graph",
            "source_label": match_out.group("src_label"),
            "source_id": match_out.group("src_id"),
            "rel_type": match_out.group("rel"),
            "target_label": match_out.group("tgt_label"),
            "target_id": match_out.group("tgt_id"),
            "direction": "out",
            "raw_locator": locator,
        }

    match_in = _GRAPH_DIRECTED_IN_RE.match(clean_loc)
    if match_in:
        return {
            "source_type": "graph",
            "source_label": match_in.group("src_label"),
            "source_id": match_in.group("src_id"),
            "rel_type": match_in.group("rel"),
            "target_label": match_in.group("tgt_label"),
            "target_id": match_in.group("tgt_id"),
            "direction": "in",
            "raw_locator": locator,
        }

    # Complex / multi-hop path fallback
    return {
        "source_type": "graph",
        "raw_locator": locator,
        "source_label": None,
        "source_id": None,
        "rel_type": None,
        "target_label": None,
        "target_id": None,
        "direction": "multi_hop",
    }


# -----------------------------------------------------------------------------
# Generic Locator Routing and Validation
# -----------------------------------------------------------------------------


def parse_locator(locator: str) -> dict[str, Any]:
    """Dynamically detect source store type and parse citation locator."""
    clean = locator.strip()
    if clean.startswith("sql:"):
        return parse_sql_locator(clean)
    elif clean.startswith("(") or "->" in clean or "<-" in clean:
        return parse_graph_locator(clean)
    else:
        return parse_document_locator(clean)


def validate_locator(locator: str, expected_type: str | None = None) -> bool:
    """Validate that locator is syntactically well-formed for its store type."""
    if not locator or not locator.strip():
        return False

    parsed = parse_locator(locator)
    detected_type = parsed["source_type"]

    if expected_type is not None and detected_type != expected_type:
        return False

    if detected_type == "sql":
        return parsed.get("table") is not None
    elif detected_type == "graph":
        return locator.startswith("(") and locator.endswith(")")
    elif detected_type == "document":
        return bool(parsed.get("filename") or parsed.get("doc_id"))

    return False


# -----------------------------------------------------------------------------
# Evidence Factory and Collection Utilities
# -----------------------------------------------------------------------------


def create_evidence(
    sub_question_id: str,
    source_type: EvidenceSourceType,
    locator: str,
    content: str,
    score: float = 1.0,
    metadata: dict[str, Any] | None = None,
    evidence_id: str | None = None,
) -> Evidence:
    """Factory creating a validated canonical Evidence model."""
    normalized_score = max(0.0, min(1.0, score))
    eid = evidence_id or generate_evidence_id(
        sub_question_id=sub_question_id,
        source_type=source_type,
        locator=locator,
        content=content,
    )
    return Evidence(
        id=eid,
        sub_question_id=sub_question_id,
        source_type=source_type,
        locator=locator,
        content=content,
        score=normalized_score,
        metadata=dict(metadata or {}),
    )


def create_document_evidence(
    sub_question_id: str,
    doc_id_or_filename: str,
    content: str,
    section: str | None = None,
    chunk_index: int | None = None,
    score: float = 1.0,
    metadata: dict[str, Any] | None = None,
    evidence_id: str | None = None,
) -> Evidence:
    """Convenience factory for Document RAG evidence items."""
    loc = build_document_locator(
        filename_or_id=doc_id_or_filename,
        section=section,
        chunk_index=chunk_index,
    )
    meta = dict(metadata or {})
    meta.setdefault("store", "vector")
    return create_evidence(
        sub_question_id=sub_question_id,
        source_type="document",
        locator=loc,
        content=content,
        score=score,
        metadata=meta,
        evidence_id=evidence_id,
    )


def create_sql_evidence(
    sub_question_id: str,
    table: str,
    content: str,
    row_id: str | int | None = None,
    query: str | None = None,
    score: float = 1.0,
    metadata: dict[str, Any] | None = None,
    evidence_id: str | None = None,
) -> Evidence:
    """Convenience factory for Governed SQL retrieval evidence items."""
    loc = build_sql_locator(table=table, row_id=row_id)
    meta = dict(metadata or {})
    meta.setdefault("store", "sql")
    meta.setdefault("table", table)
    if query:
        meta["sql_query"] = query
    if row_id:
        meta["row_id"] = str(row_id)
    return create_evidence(
        sub_question_id=sub_question_id,
        source_type="sql",
        locator=loc,
        content=content,
        score=score,
        metadata=meta,
        evidence_id=evidence_id,
    )


def create_graph_evidence(
    sub_question_id: str,
    locator: str,
    content: str,
    cypher: str | None = None,
    score: float = 1.0,
    metadata: dict[str, Any] | None = None,
    evidence_id: str | None = None,
) -> Evidence:
    """Convenience factory for Typed Graph traversal evidence items."""
    meta = dict(metadata or {})
    meta.setdefault("store", "graph")
    if cypher:
        meta["cypher"] = cypher
    return create_evidence(
        sub_question_id=sub_question_id,
        source_type="graph",
        locator=locator,
        content=content,
        score=score,
        metadata=meta,
        evidence_id=evidence_id,
    )


def deduplicate_evidence(evidence_list: list[Evidence]) -> list[Evidence]:
    """Deduplicate evidence items preserving order and retaining highest scores.

    Deduplication key: `(source_type, locator)` or `id`.
    """
    seen: dict[tuple[str, str], Evidence] = {}
    ordered_keys: list[tuple[str, str]] = []

    for item in evidence_list:
        key = (item.source_type, item.locator)
        if key not in seen:
            seen[key] = item
            ordered_keys.append(key)
        else:
            # Retain the version with higher score
            if item.score > seen[key].score:
                seen[key] = item

    return [seen[k] for k in ordered_keys]


def sort_evidence_by_score(
    evidence_list: list[Evidence],
    descending: bool = True,
) -> list[Evidence]:
    """Sort evidence items by score."""
    return sorted(evidence_list, key=lambda e: e.score, reverse=descending)


def filter_evidence_by_score(
    evidence_list: list[Evidence],
    min_score: float,
) -> list[Evidence]:
    """Filter evidence items retaining those meeting or exceeding min_score."""
    return [e for e in evidence_list if e.score >= min_score]
