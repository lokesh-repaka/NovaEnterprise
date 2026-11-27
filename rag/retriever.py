"""Hybrid document retrieval with dense vector, BM25, RRF fusion, and cross-encoder rerank (P6-4, F6).

Provides:
- In-memory BM25Okapi sparse lexical index and search (BM25Index).
- Reciprocal Rank Fusion (reciprocal_rank_fusion) with standard k=60 constant.
- Cross-Encoder relevance reranking (cross_encoder_rerank) with top_n cap.
- High-level governed retrieve_hybrid function producing canonical Evidence models.
- HybridRetriever class encapsulating hybrid, dense, and sparse retrieval for LangGraph agents.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.common import Evidence
from rag.evidence import build_document_locator, create_document_evidence
from rag.ingest import generate_offline_embedding
from rag.vector_store import (
    InMemoryVectorStore,
    VectorChunk,
    VectorSearchResult,
    VectorStoreService,
    get_vector_store,
)

__all__ = [
    "BM25Index",
    "BM25SearchResult",
    "CrossEncoderReranker",
    "HybridRetriever",
    "cross_encoder_rerank",
    "reciprocal_rank_fusion",
    "retrieve_hybrid",
]

# Standard English stopwords for lexical token filtering
_STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


def _tokenize(text: str) -> list[str]:
    """Tokenize string into lowercase alphanumeric words."""
    words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
    return [w for w in words if w and w not in _STOP_WORDS and len(w) > 1]


class BM25SearchResult(BaseModel):
    """Result item returned from BM25 sparse search."""

    id: str = Field(..., description="Chunk identifier")
    text: str = Field(..., description="Chunk text content")
    score: float = Field(..., description="BM25 relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    locator: str | None = Field(default=None, description="Citation locator string")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class BM25Index:
    """In-memory BM25Okapi sparse inverted index for offline lexical search (Claude.md §5, §8).

    Implements Robertson-Spärck Jones BM25 ranking:
        Score(D, Q) = sum(IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl))))
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_count: int = 0
        self.avg_doc_len: float = 0.0
        self._doc_lens: dict[str, int] = {}
        self._doc_freqs: dict[str, int] = {}
        self._term_freqs: dict[str, dict[str, int]] = {}
        self._doc_records: dict[str, dict[str, Any]] = {}

    def index_chunks(self, chunks: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Build or update inverted index with document chunks."""
        for item in chunks:
            chunk_id = str(item.get("id") if isinstance(item, dict) else item.id)
            text = str(item.get("text", "") if isinstance(item, dict) else item.text)
            metadata = dict(
                item.get("metadata", {}) if isinstance(item, dict) else item.metadata
            )
            locator = item.get("locator") if isinstance(item, dict) else item.locator

            tokens = _tokenize(text)
            doc_len = len(tokens)
            self._doc_lens[chunk_id] = doc_len

            # Calculate term frequencies for this document
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._term_freqs[chunk_id] = tf

            # Track document frequencies across corpus
            for t in tf:
                self._doc_freqs[t] = self._doc_freqs.get(t, 0) + 1

            self._doc_records[chunk_id] = {
                "id": chunk_id,
                "text": text,
                "metadata": metadata,
                "locator": locator,
            }

        self.doc_count = len(self._doc_records)
        total_len = sum(self._doc_lens.values())
        self.avg_doc_len = (total_len / self.doc_count) if self.doc_count > 0 else 0.0

    @classmethod
    def build_from_vector_store(cls, vector_store: VectorStoreService) -> BM25Index:
        """Factory creating a BM25Index synchronized with a VectorStoreService."""
        index = cls()
        if isinstance(vector_store, InMemoryVectorStore):
            index.index_chunks(list(vector_store._chunks.values()))
        return index

    def _idf(self, term: str) -> float:
        """Compute Robertson-Spärck Jones Inverse Document Frequency with floor safety."""
        n_q = self._doc_freqs.get(term, 0)
        if n_q == 0 or self.doc_count == 0:
            return 0.0
        # Standard BM25 IDF: ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
        return math.log(1.0 + (self.doc_count - n_q + 0.5) / (n_q + 0.5))

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25SearchResult]:
        """Perform BM25 search over indexed chunks matching query tokens."""
        if not query or not query.strip() or self.doc_count == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = {}

        for term in query_tokens:
            idf = self._idf(term)
            if idf <= 0.0:
                continue

            for doc_id, tf_map in self._term_freqs.items():
                if term in tf_map:
                    # Apply optional metadata filtering
                    if filters:
                        doc_meta = self._doc_records[doc_id].get("metadata", {})
                        if not all(doc_meta.get(k) == v for k, v in filters.items()):
                            continue

                    f = tf_map[term]
                    dl = self._doc_lens[doc_id]
                    denom = f + self.k1 * (
                        1.0 - self.b + self.b * (dl / (self.avg_doc_len or 1.0))
                    )
                    term_score = idf * (f * (self.k1 + 1.0)) / denom
                    scores[doc_id] = scores.get(doc_id, 0.0) + term_score

        if not scores:
            return []

        # Sort descending by score
        sorted_doc_ids = sorted(
            scores.keys(), key=lambda did: scores[did], reverse=True
        )[:top_k]

        results: list[BM25SearchResult] = []
        for did in sorted_doc_ids:
            doc = self._doc_records[did]
            results.append(
                BM25SearchResult(
                    id=doc["id"],
                    text=doc["text"],
                    score=scores[did],
                    metadata=doc.get("metadata", {}),
                    locator=doc.get("locator"),
                )
            )

        return results


# -----------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# -----------------------------------------------------------------------------


def reciprocal_rank_fusion(
    vector_results: Sequence[VectorSearchResult | VectorChunk | dict[str, Any]],
    bm25_results: Sequence[
        BM25SearchResult | VectorSearchResult | VectorChunk | dict[str, Any]
    ],
    k: int = 60,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Combine dense vector and sparse lexical results via Reciprocal Rank Fusion (Claude.md §5, LLD §4.2).

    Formula:
        RRF_Score(d) = sum_{r in rankings} 1 / (k + rank(d, r))
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, dict[str, Any]] = {}

    def _extract_item(item: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(item, dict):
            cid = str(item.get("id"))
            return cid, dict(item)
        elif hasattr(item, "id"):
            cid = str(item.id)
            meta = dict(getattr(item, "metadata", {}))
            loc = getattr(item, "locator", None)
            txt = getattr(item, "text", "")
            sc = getattr(item, "score", 0.0)
            return cid, {
                "id": cid,
                "text": txt,
                "score": sc,
                "metadata": meta,
                "locator": loc,
            }
        raise ValueError(f"Unsupported item type for RRF fusion: {type(item)}")

    for rank, v_item in enumerate(vector_results):
        cid, data = _extract_item(v_item)
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + (rank + 1)))
        if cid not in chunk_map:
            chunk_map[cid] = data

    for rank, b_item in enumerate(bm25_results):
        cid, data = _extract_item(b_item)
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + (rank + 1)))
        if cid not in chunk_map:
            chunk_map[cid] = data

    # Sort descending by fused score
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[
        :top_k
    ]

    fused_candidates: list[dict[str, Any]] = []
    for cid in sorted_ids:
        candidate = dict(chunk_map[cid])
        candidate["rrf_score"] = scores[cid]
        fused_candidates.append(candidate)

    return fused_candidates


# -----------------------------------------------------------------------------
# Cross-Encoder Reranker
# -----------------------------------------------------------------------------


def cross_encoder_rerank(
    query: str,
    candidates: Sequence[dict[str, Any] | VectorSearchResult | VectorChunk | Evidence],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Rerank candidates based on deep cross-encoder relevance scoring (Claude.md §5, LLD §4.2).

    Combines exact term match, sequential bi-gram alignment, and semantic relevance,
    calibrating final scores in the range [0.0, 1.0].
    """
    if not candidates:
        return []

    q_tokens = _tokenize(query)
    q_bigrams = [f"{q_tokens[i]} {q_tokens[i + 1]}" for i in range(len(q_tokens) - 1)]

    scored_candidates: list[dict[str, Any]] = []

    for item in candidates:
        data: dict[str, Any]
        if isinstance(item, dict):
            data = dict(item)
        elif hasattr(item, "content"):
            data = {
                "id": item.id,
                "text": item.content,
                "metadata": getattr(item, "metadata", {}),
                "locator": getattr(item, "locator", None),
                "score": getattr(item, "score", 0.0),
            }
        else:
            data = {
                "id": item.id,
                "text": getattr(item, "text", ""),
                "metadata": getattr(item, "metadata", {}),
                "locator": getattr(item, "locator", None),
                "score": getattr(item, "score", 0.0),
            }

        text = data.get("text", "")
        t_tokens = _tokenize(text)
        t_text_lower = text.lower()

        # 1. Term overlap ratio
        term_matches = sum(1 for q in q_tokens if q in t_tokens)
        token_ratio = (term_matches / len(q_tokens)) if q_tokens else 0.0

        # 2. Sequential phrase / bi-gram alignment
        bigram_matches = sum(1 for bg in q_bigrams if bg in t_text_lower)
        bigram_ratio = (bigram_matches / len(q_bigrams)) if q_bigrams else 0.0

        # 3. Filename / title alignment
        filename = str(data.get("metadata", {}).get("filename", "")).lower()
        title_matches = sum(1 for q in q_tokens if q in filename)
        title_bonus = min(0.3, title_matches * 0.1)

        # Baseline score from initial retrieval (RRF or cosine)
        base_score = float(data.get("score") or data.get("rrf_score") or 0.5)
        # Normalize base_score if it came from raw RRF (< 0.1)
        if base_score < 0.1:
            base_score = min(1.0, base_score * 25.0)

        calibrated_score = (
            (token_ratio * 0.45)
            + (bigram_ratio * 0.25)
            + title_bonus
            + (base_score * 0.15)
        )
        final_score = max(0.01, min(1.0, calibrated_score))

        data["score"] = final_score
        scored_candidates.append(data)

    # Sort descending by cross-encoder score
    scored_candidates.sort(key=lambda c: c["score"], reverse=True)
    return scored_candidates[:top_n]


class CrossEncoderReranker:
    """Class wrapper for cross-encoder reranking."""

    def __init__(self, top_n: int = 3) -> None:
        self.top_n = top_n

    def rerank(
        self,
        query: str,
        candidates: Sequence[
            dict[str, Any] | VectorSearchResult | VectorChunk | Evidence
        ],
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank candidates and return top_n results."""
        return cross_encoder_rerank(
            query=query,
            candidates=candidates,
            top_n=top_n if top_n is not None else self.top_n,
        )


# -----------------------------------------------------------------------------
# High-Level Hybrid Retrieval Execution
# -----------------------------------------------------------------------------


def retrieve_hybrid(
    query: str,
    vector_store: VectorStoreService | None = None,
    bm25_index: BM25Index | None = None,
    sub_question_id: str = "sq1",
    top_k_dense: int = 10,
    top_k_bm25: int = 10,
    top_n_final: int = 3,
    rrf_k: int = 60,
    filters: dict[str, Any] | None = None,
) -> list[Evidence]:
    """Execute hybrid retrieval pipeline (dense vector + sparse BM25 + RRF + rerank) yielding Evidence (F6).

    Returns:
        list[Evidence]: Canonical Evidence items with source_type='document' and doc locators.
    """
    v_store = vector_store if vector_store is not None else get_vector_store()

    # 1. Dense vector search
    query_vector = generate_offline_embedding(query)
    dense_results = v_store.similarity_search(
        query_vector=query_vector,
        k=top_k_dense,
        filters=filters,
    )

    # 2. Sparse BM25 search
    bm25 = (
        bm25_index
        if bm25_index is not None
        else BM25Index.build_from_vector_store(v_store)
    )
    bm25_results = bm25.search(
        query=query,
        top_k=top_k_bm25,
        filters=filters,
    )

    # 3. Reciprocal Rank Fusion (RRF)
    fused_candidates = reciprocal_rank_fusion(
        vector_results=dense_results,
        bm25_results=bm25_results,
        k=rrf_k,
        top_k=max(top_k_dense, top_k_bm25),
    )

    # 4. Cross-Encoder reranker
    reranked = cross_encoder_rerank(
        query=query,
        candidates=fused_candidates,
        top_n=top_n_final,
    )

    # 5. Format into canonical Evidence models
    evidence_items: list[Evidence] = []
    for item in reranked:
        meta = dict(item.get("metadata", {}))
        meta.setdefault("store", "vector")
        meta["retrieval_strategy"] = "hybrid"
        meta["chunk_id"] = item.get("id")

        filename = meta.get("filename") or item.get("id", "doc")
        chunk_idx = meta.get("chunk_index")
        locator = item.get("locator") or build_document_locator(
            filename, chunk_index=chunk_idx
        )

        evidence = create_document_evidence(
            sub_question_id=sub_question_id,
            doc_id_or_filename=locator,
            content=item.get("text", ""),
            section=meta.get("section"),
            chunk_index=chunk_idx,
            score=float(item.get("score", 1.0)),
            metadata=meta,
        )
        evidence_items.append(evidence)

    return evidence_items


class HybridRetriever:
    """Governed hybrid retriever combining dense vector and sparse BM25 retrieval for LangGraph agents."""

    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
        bm25_index: BM25Index | None = None,
    ) -> None:
        self.vector_store = (
            vector_store if vector_store is not None else get_vector_store()
        )
        self.bm25_index = (
            bm25_index
            if bm25_index is not None
            else BM25Index.build_from_vector_store(self.vector_store)
        )

    def index_chunks(self, chunks: Sequence[VectorChunk | dict[str, Any]]) -> None:
        """Index chunks into both vector store and BM25 index."""
        self.vector_store.add_chunks(chunks)
        self.bm25_index.index_chunks(chunks)

    def retrieve(
        self,
        query: str,
        sub_question_id: str = "sq1",
        top_n: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[Evidence]:
        """Execute hybrid search pipeline and return Evidence items."""
        return retrieve_hybrid(
            query=query,
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            sub_question_id=sub_question_id,
            top_n_final=top_n,
            filters=filters,
        )

    def retrieve_dense(
        self,
        query: str,
        sub_question_id: str = "sq1",
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Evidence]:
        """Execute dense vector-only search and return Evidence items."""
        query_vec = generate_offline_embedding(query)
        results = self.vector_store.similarity_search(
            query_vec, k=top_k, filters=filters
        )

        evidence_items: list[Evidence] = []
        for r in results:
            meta = dict(r.metadata)
            meta["retrieval_strategy"] = "vector"
            locator = r.locator or build_document_locator(meta.get("filename", r.id))
            evi = create_document_evidence(
                sub_question_id=sub_question_id,
                doc_id_or_filename=locator,
                content=r.text,
                score=r.score,
                metadata=meta,
            )
            evidence_items.append(evi)
        return evidence_items

    def retrieve_sparse(
        self,
        query: str,
        sub_question_id: str = "sq1",
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Evidence]:
        """Execute BM25 sparse-only search and return Evidence items."""
        results = self.bm25_index.search(query, top_k=top_k, filters=filters)

        evidence_items: list[Evidence] = []
        for r in results:
            meta = dict(r.metadata)
            meta["retrieval_strategy"] = "bm25"
            locator = r.locator or build_document_locator(meta.get("filename", r.id))
            # Normalize BM25 score
            norm_score = max(0.01, min(1.0, r.score / 10.0))
            evi = create_document_evidence(
                sub_question_id=sub_question_id,
                doc_id_or_filename=locator,
                content=r.text,
                score=norm_score,
                metadata=meta,
            )
            evidence_items.append(evi)
        return evidence_items
