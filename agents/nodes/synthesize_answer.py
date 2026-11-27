"""Cited answer synthesis node for LangGraph research workflow (P9-7, F11, Claude.md §3.1, §5, §7.3, FRD §5.2 FR-11).

Primary Responsibilities:
- Assemble verified evidence into structured, prompt-injection-safe context.
- Wrap external and untrusted evidence in isolated XML delimiters (<untrusted_content>).
- Prompt the LLM gateway (or use deterministic grounded generator in offline/fake mode) to generate Markdown.
- Embed sequential citation tokens [1], [2], ... [n] tied to specific supporting evidence.
- Build canonical Citation array resolving each [n] token to evidence_id, source_type, locator, and snippet.
- Telemetry recording via tracer.node("synthesize_answer") with zero-crash resilience.
- Return partial state dictionary updating: answer, citations, metadata, and current_node.
"""

from __future__ import annotations

import re
from typing import Any

from agents.state import ResearchState
from backend.app.core.llm import get_llm
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Citation, Evidence
from rag.evidence import generate_evidence_id

logger = get_logger("agents.nodes.synthesize_answer")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _normalize_evidence_item(item: Evidence | dict[str, Any]) -> Evidence:
    """Ensure evidence item is a validated Evidence model instance."""
    if isinstance(item, Evidence):
        return item
    d = dict(item)
    if "id" not in d:
        sub_q = str(d.get("sub_question_id", "sq1"))
        src = str(d.get("source_type", "document"))
        loc = str(d.get("locator", "unknown"))
        cnt = str(d.get("content", ""))
        d["id"] = generate_evidence_id(sub_q, src, loc, cnt)
    return Evidence(**d)


def synthesize_answer(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to generate a grounded, cited Markdown research report.

    Args:
        state: ResearchState or dictionary representation containing verified_evidence.

    Returns:
        Partial state dictionary with answer and citations list.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    question = str(_get_field(state, "question", ""))
    entity = _get_field(state, "entity") or "enterprise system"
    raw_verified = (
        _get_field(state, "verified_evidence") or _get_field(state, "evidence") or []
    )
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_synthesis() -> dict[str, Any]:
        evidence_pool: list[Evidence] = []
        for raw_item in raw_verified:
            try:
                evidence_pool.append(_normalize_evidence_item(raw_item))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Skipping unparseable evidence item during synthesis: %s",
                    exc,
                )

        # Build prompt-injection-safe evidence blocks (Claude.md §2, FRD §5.2)
        formatted_blocks: list[str] = []
        for idx, ev in enumerate(evidence_pool, start=1):
            formatted_blocks.append(
                f"[{idx}] Store: {ev.source_type} | Locator: {ev.locator}\n"
                f'<untrusted_content index="{idx}">\n{ev.content.strip()}\n</untrusted_content>'
            )

        context_str = (
            "\n\n".join(formatted_blocks)
            if formatted_blocks
            else "No verified evidence available."
        )

        synthesis_prompt = (
            f"You are the NovaEnterprise Senior Research Analyst. Synthesize an authoritative, grounded Markdown "
            f"answer to the question below using ONLY the verified evidence provided. Cite each claim using bracketed "
            f"numbers like [1], [2] corresponding to the evidence reference indices.\n\n"
            f"Question: {question}\n\n"
            f"Verified Evidence:\n{context_str}\n\n"
            f"Synthesize Answer:"
        )

        llm = get_llm()
        raw_response = ""
        try:
            raw_response = llm.complete(synthesis_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLM completion failed in synthesize_answer for session %s (using deterministic synthesis): %s",
                session_id,
                exc,
            )

        # Verify or deterministically ground synthesis if LLM response is absent or lacks citations
        has_citations = bool(re.search(r"\[\d+\]", raw_response))

        if not raw_response or not has_citations:
            # Deterministic, grounded fallback synthesis
            if evidence_pool:
                sentences: list[str] = [f"Based on enterprise records for {entity}:"]
                for idx, ev in enumerate(evidence_pool[:4], start=1):
                    # Clean snippet for answer text
                    clean_text = ev.content.strip().replace("\n", " ")
                    if len(clean_text) > 120:
                        clean_text = clean_text[:117] + "..."
                    sentences.append(f"{clean_text} [{idx}].")
                answer_text = " ".join(sentences)
            else:
                answer_text = f"Insufficient verified evidence was available to definitively answer '{question}'."
        else:
            answer_text = raw_response

        # Extract citation tokens [n] referenced in the answer text
        referenced_indices = [int(idx) for idx in re.findall(r"\[(\d+)\]", answer_text)]
        # Preserve first occurrence order
        ordered_indices: list[int] = list(dict.fromkeys(referenced_indices))

        citations_list: list[dict[str, Any]] = []

        if evidence_pool:
            for cit_idx in ordered_indices:
                if 1 <= cit_idx <= len(evidence_pool):
                    ev_match = evidence_pool[cit_idx - 1]
                    citation_obj = Citation(
                        citation_id=cit_idx,
                        evidence_id=ev_match.id,
                        source_type=ev_match.source_type,
                        locator=ev_match.locator,
                        snippet=ev_match.content[:200],
                    )
                    citations_list.append(citation_obj.model_dump())

            # If no citations were parsed from text, create mappings for top available evidence items
            if not citations_list and evidence_pool:
                for idx, ev_match in enumerate(evidence_pool[:3], start=1):
                    citation_obj = Citation(
                        citation_id=idx,
                        evidence_id=ev_match.id,
                        source_type=ev_match.source_type,
                        locator=ev_match.locator,
                        snippet=ev_match.content[:200],
                    )
                    citations_list.append(citation_obj.model_dump())
                    if f"[{idx}]" not in answer_text:
                        answer_text += f" [{idx}]"

        logger.info(
            "Synthesized answer for session %s: %d characters, %d citations",
            session_id,
            len(answer_text),
            len(citations_list),
        )

        updated_metadata = {
            **existing_meta,
            "citations_count": len(citations_list),
            "answer_length": len(answer_text),
            "verified_evidence_utilized": len(evidence_pool),
        }

        return {
            "answer": answer_text,
            "citations": citations_list,
            "metadata": updated_metadata,
            "current_node": "synthesize_answer",
        }

    try:
        with tracer.node(session_id, "synthesize_answer"):
            return _execute_synthesis()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in synthesize_answer node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_synthesis()


# Canonical alias for LangGraph registration
synthesize_answer_node = synthesize_answer

__all__ = ["synthesize_answer", "synthesize_answer_node"]
