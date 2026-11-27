"""LangGraph research state schema for NovaEnterprise (P9-1, Claude.md §7.3, FRD §5.2).

Defines ResearchState, the shared execution context passed through all 13 workflow nodes.
Supports:
- Strict Pydantic v2 validation with default field values
- Dual attribute and dict-like subscripting (state["key"] / state.key)
- TypedDict mirror ResearchStateDict for pure TypedDict LangGraph annotations
- Mutation helpers for evidence accumulation, strategy recording, and non-fatal error tracking
"""

from __future__ import annotations

from collections.abc import KeysView
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from rag.evidence import Evidence


class ResearchStateDict(TypedDict, total=False):
    """TypedDict definition of ResearchState for LangGraph StateGraph typing."""

    session_id: str
    question: str
    user_id: str | None
    complexity: str | None
    intent: str | None
    entity: str | None
    time_range: dict[str, str]
    sub_questions: list[dict[str, Any]]
    evidence: list[Evidence | dict[str, Any]]
    verified_evidence: list[Evidence | dict[str, Any]]
    missing_facets: list[str]
    needs_retry: bool
    corrective_rounds: int
    verification_ratio: float
    answer: str
    citations: list[dict[str, Any]]
    errors: list[str]
    status: Literal["running", "completed", "failed"]
    strategies_used: list[str]
    current_node: str | None
    metadata: dict[str, Any]
    execution_time_seconds: float | None
    created_at: datetime
    updated_at: datetime


class ResearchState(BaseModel):
    """Complete LangGraph workflow state container for enterprise research execution (FRD §5.2)."""

    session_id: str = Field(..., description="Unique research execution identifier")
    question: str = Field(..., description="Original user natural language question")
    user_id: str | None = Field(
        default="demo-user", description="Analyst identity requesting research"
    )
    complexity: Literal["simple", "moderate", "complex"] | str | None = Field(
        default=None, description="Assessed question complexity tier"
    )
    intent: str | None = Field(default=None, description="Extracted query intent")
    entity: str | None = Field(
        default=None, description="Primary extracted enterprise entity"
    )
    time_range: dict[str, str] = Field(
        default_factory=dict, description="Resolved start and end ISO dates"
    )
    sub_questions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Decomposed sub-questions with assigned retrieval strategies",
    )
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Aggregated evidence records retrieved across all stores",
    )
    verified_evidence: list[Evidence] = Field(
        default_factory=list,
        description="Sub-set of evidence claims confirmed during verification",
    )
    missing_facets: list[str] = Field(
        default_factory=list,
        description="Sub-questions or aspects lacking adequate evidence",
    )
    needs_retry: bool = Field(
        default=False,
        description="Flag indicating whether corrective retrieval is required",
    )
    corrective_rounds: int = Field(
        default=0, description="Counter tracking corrective iterations (max 1)"
    )
    verification_ratio: float = Field(
        default=0.0,
        description="Proportion of claims successfully verified against evidence",
    )
    answer: str = Field(
        default="",
        description="Synthesized Markdown answer text with embedded [n] citation markers",
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array of citation mappings linking [n] tokens to evidence locators",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal subsystem or store degradation messages",
    )
    status: Literal["running", "completed", "failed"] | str = Field(
        default="running", description="Overall workflow execution state"
    )
    strategies_used: list[str] = Field(
        default_factory=list,
        description="Unique retrieval strategies executed (vector, sql, graph, hybrid)",
    )
    current_node: str | None = Field(
        default=None, description="Most recently entered or active workflow node"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution context tags"
    )
    execution_time_seconds: float | None = Field(
        default=None, description="Total wall-clock execution duration in seconds"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Workflow kickoff timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last state mutation timestamp",
    )

    # =====================================================================
    # Dict-like Access for LangGraph Node Interoperability
    # =====================================================================

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like subscript access (e.g. state['question'])."""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-like assignment (e.g. state['complexity'] = 'complex')."""
        setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)

    def get(self, key: str, default: Any = None) -> Any:
        """Safe dict-style get method."""
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        """Check if attribute or field exists in model."""
        return hasattr(self, key) and key in self.__class__.model_fields

    def keys(self) -> KeysView[str]:
        """Return all model field names."""
        return self.__class__.model_fields.keys()

    def values(self) -> list[Any]:
        """Return all model field values."""
        return [getattr(self, k) for k in self.__class__.model_fields]

    def items(self) -> list[tuple[str, Any]]:
        """Return all (field_name, field_value) pairs."""
        return [(k, getattr(self, k)) for k in self.__class__.model_fields]

    # =====================================================================
    # State Mutation Helpers
    # =====================================================================

    def add_evidence(self, item: Evidence | dict[str, Any]) -> None:
        """Add an evidence item, converting dict to Evidence if needed."""
        if isinstance(item, Evidence):
            self.evidence.append(item)
        elif isinstance(item, dict):
            self.evidence.append(Evidence.model_validate(item))
        self.updated_at = datetime.now(timezone.utc)

    def add_strategy(self, strategy: str) -> None:
        """Record a retrieval strategy used, avoiding duplicates."""
        if strategy not in self.strategies_used:
            self.strategies_used.append(strategy)
            self.updated_at = datetime.now(timezone.utc)

    def add_error(self, error_message: str) -> None:
        """Record a non-fatal subsystem error or store degradation."""
        self.errors.append(error_message)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to a plain dictionary."""
        return self.model_dump()
