"""Four-scope memory schemas for NovaEnterprise (P8-1, F15, N8, N9, Claude.md §7.4).

Defines strongly-typed Pydantic models for the 4 discrete memory scopes:
1. Working Memory (in-node / active execution run transient context)
2. Episodic Memory (session-level multi-turn conversation & research history)
3. Semantic Memory (user / analyst-specific knowledge & preference memory)
4. Organizational Memory (enterprise constants, fiscal calendar, SLAs, ownership)

Also provides the consolidated FourScopeMemoryContext snapshot model for agent prompt context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from backend.app.core.upload_validator import scrub_secrets


class MemoryScope(str, Enum):
    """The four discrete, non-intermingled memory scopes (F15)."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    ORGANIZATIONAL = "organizational"


class MemoryItem(BaseModel):
    """Generic memory item container across all scopes."""

    id: str = Field(
        default_factory=lambda: f"mem_{uuid4().hex[:12]}",
        description="Unique memory record identifier",
    )
    scope: MemoryScope = Field(..., description="Target memory scope")
    key: str = Field(..., description="Lookup key or semantic topic")
    content: Any = Field(..., description="Memory content payload")
    user_id: str | None = Field(
        default=None, description="Analyst identity for user-scoped memory"
    )
    session_id: str | None = Field(
        default=None, description="Research session identity for session-scoped memory"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata tags"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC record timestamp",
    )
    ttl_seconds: int | None = Field(
        default=None, description="Optional time-to-live expiration in seconds"
    )

    @model_validator(mode="after")
    def sanitize_secrets(self) -> MemoryItem:
        """Automatically scrub secrets from string content (N8, N9)."""
        if isinstance(self.content, str):
            scrub_res = scrub_secrets(self.content)
            self.content = scrub_res.scrubbed_text
        elif isinstance(self.content, dict):
            clean_dict: dict[str, Any] = {}
            for k, v in self.content.items():
                if isinstance(v, str):
                    clean_dict[k] = scrub_secrets(v).scrubbed_text
                else:
                    clean_dict[k] = v
            self.content = clean_dict
        return self


# =====================================================================
# 1. Working Memory Scope (Ephemeral In-Run Context)
# =====================================================================


class WorkingMemoryState(BaseModel):
    """Transient working memory scoped to the active execution run / StateGraph invocation."""

    session_id: str = Field(
        default="", description="Parent research session identifier"
    )
    current_sub_question_index: int = Field(
        default=0, description="Active sub-question ordinal index"
    )
    active_sub_question: str | None = Field(
        default=None, description="Natural language text of current sub-question"
    )
    findings: list[str] = Field(
        default_factory=list, description="Intermediate conclusions and findings"
    )
    scratchpad: dict[str, Any] = Field(
        default_factory=dict, description="Ephemeral hypothesis and node annotations"
    )
    last_node: str | None = Field(
        default=None, description="Most recently completed workflow node"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last working state mutation",
    )

    def set_active_sub_question(
        self, sub_question: str, index: int | None = None
    ) -> None:
        """Set current active sub-question focus."""
        self.active_sub_question = sub_question
        if index is not None:
            self.current_sub_question_index = index
        self.updated_at = datetime.now(timezone.utc)

    def add_finding(self, finding: str) -> None:
        """Append an intermediate finding with secret scrubbing."""
        sanitized = scrub_secrets(finding).scrubbed_text
        self.findings.append(sanitized)
        self.updated_at = datetime.now(timezone.utc)

    def update_scratchpad(self, key: str, value: Any) -> None:
        """Record a scratchpad hypothesis or temporary flag."""
        if isinstance(value, str):
            value = scrub_secrets(value).scrubbed_text
        self.scratchpad[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def clear_run_state(self) -> None:
        """Reset in-run transient state."""
        self.active_sub_question = None
        self.current_sub_question_index = 0
        self.findings = []
        self.scratchpad = {}
        self.last_node = None
        self.updated_at = datetime.now(timezone.utc)


# =====================================================================
# 2. Episodic Memory Scope (Session Multi-Turn History)
# =====================================================================


class EpisodicMemoryEntry(BaseModel):
    """Session-level conversation turn and interaction context (stored in Redis with TTL)."""

    id: str = Field(
        default_factory=lambda: f"epi_{uuid4().hex[:12]}",
        description="Unique episodic interaction ID",
    )
    session_id: str = Field(..., description="Correlated research session ID")
    turn_index: int = Field(default=0, description="Sequential turn number")
    user_id: str | None = Field(
        default=None, description="Analyst submitting the question"
    )
    question: str = Field(..., description="Natural language question asked")
    answer: str = Field(..., description="Synthesized answer produced")
    complexity: str | None = Field(
        default=None, description="Assessed query complexity (simple or complex)"
    )
    citations: list[str] = Field(
        default_factory=list, description="List of locator citation strings used"
    )
    feedback: str | None = Field(
        default=None, description="User feedback or rating on turn"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Session execution metadata"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of interaction turn",
    )
    ttl_seconds: int | None = Field(
        default=86400, description="Session retention TTL (24 hours default)"
    )

    @model_validator(mode="after")
    def sanitize_entry(self) -> EpisodicMemoryEntry:
        """Ensure question, answer, and feedback do not leak secrets."""
        self.question = scrub_secrets(self.question).scrubbed_text
        self.answer = scrub_secrets(self.answer).scrubbed_text
        if self.feedback:
            self.feedback = scrub_secrets(self.feedback).scrubbed_text
        return self


# =====================================================================
# 3. Semantic Memory Scope (Analyst Profile & Persistent Learnings)
# =====================================================================


class SemanticMemoryEntry(BaseModel):
    """Long-term analyst-specific preferences, terminology, and domain insights."""

    id: str = Field(
        default_factory=lambda: f"sem_{uuid4().hex[:12]}",
        description="Unique semantic memory ID",
    )
    user_id: str = Field(..., description="Analyst owner identifier")
    key: str = Field(..., description="Semantic concept or preference key")
    content: str = Field(..., description="Recorded domain insight or preference")
    category: str = Field(
        default="preference",
        description="Category: preference, knowledge, rule, glossary",
    )
    confidence: float = Field(
        default=1.0, description="Confidence score from 0.0 to 1.0"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Associated context tags"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )

    @model_validator(mode="after")
    def sanitize_content(self) -> SemanticMemoryEntry:
        """Sanitize secrets from semantic memory content."""
        self.content = scrub_secrets(self.content).scrubbed_text
        return self


# =====================================================================
# 4. Organizational Memory Scope (Enterprise Ground Truth & Constants)
# =====================================================================


class CompanyInfo(BaseModel):
    """Basic corporate identity information."""

    name: str = Field(default="NovaEnterprise Inc.")
    domain: str = Field(default="nova.io")
    headquarters: str = Field(default="San Francisco, CA")
    default_currency: str = Field(default="USD")


class FiscalQuarter(BaseModel):
    """Single quarter definition in corporate fiscal calendar."""

    name: str = Field(..., description="Human-readable quarter name")
    start_date: str = Field(..., description="ISO-8601 start date")
    end_date: str = Field(..., description="ISO-8601 end date")
    status: str = Field(
        default="closed", description="Quarter state: closed, active, future"
    )


class FiscalCalendar(BaseModel):
    """Corporate fiscal calendar with quarter resolution."""

    fiscal_year: int = Field(default=2026)
    fiscal_year_start: str = Field(default="2026-01-01")
    fiscal_year_end: str = Field(default="2026-12-31")
    current_quarter: str = Field(default="2026-Q3")
    last_quarter: str = Field(default="2026-Q2")
    quarters: dict[str, FiscalQuarter] = Field(default_factory=dict)

    def resolve_quarter(self, identifier: str) -> FiscalQuarter | None:
        """Resolve a quarter by code (e.g. '2026-Q2') or relative alias (e.g. 'last_quarter')."""
        normalized = identifier.strip().lower().replace(" ", "_")
        if normalized in {"last_quarter", "lastquarter", "previous_quarter"}:
            target_key = self.last_quarter
        elif normalized in {"current_quarter", "currentquarter", "this_quarter"}:
            target_key = self.current_quarter
        else:
            target_key = identifier.strip().upper()

        return self.quarters.get(target_key)


class ServiceTier(BaseModel):
    """Service level agreement tier specification."""

    description: str = Field(..., description="Tier service description")
    availability_sla: float = Field(..., description="Target uptime percentage")
    max_downtime_quarter_min: float = Field(
        ..., description="Maximum allowed quarterly downtime in minutes"
    )
    sev1_response_sla_min: int = Field(
        ..., description="Sev1 response SLA limit in minutes"
    )


class OrganizationalMemory(BaseModel):
    """Enterprise-wide shared facts and constants (curated ground truth)."""

    company_info: CompanyInfo = Field(default_factory=CompanyInfo)
    fiscal_calendar: FiscalCalendar = Field(default_factory=FiscalCalendar)
    service_tiers: dict[str, ServiceTier] = Field(default_factory=dict)
    service_ownership: dict[str, str] = Field(
        default_factory=dict, description="service_id to team_id map"
    )
    custom_facts: dict[str, Any] = Field(
        default_factory=dict, description="Additional enterprise constants"
    )

    def get_service_owner(self, service_id: str) -> str | None:
        """Retrieve team ID owning a specific service."""
        return self.service_ownership.get(service_id)

    def get_service_tier(self, tier_id: str) -> ServiceTier | None:
        """Retrieve SLA specifications for a service tier."""
        return self.service_tiers.get(tier_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrganizationalMemory:
        """Construct OrganizationalMemory instance from dictionary payload."""
        company_info = CompanyInfo(**data.get("company_info", {}))

        raw_calendar = data.get("fiscal_calendar", {})
        raw_quarters = raw_calendar.get("quarters", {})
        quarters_map = {
            q_id: FiscalQuarter(**q_data) for q_id, q_data in raw_quarters.items()
        }
        fiscal_calendar = FiscalCalendar(
            fiscal_year=raw_calendar.get("fiscal_year", 2026),
            fiscal_year_start=raw_calendar.get("fiscal_year_start", "2026-01-01"),
            fiscal_year_end=raw_calendar.get("fiscal_year_end", "2026-12-31"),
            current_quarter=raw_calendar.get("current_quarter", "2026-Q3"),
            last_quarter=raw_calendar.get("last_quarter", "2026-Q2"),
            quarters=quarters_map,
        )

        raw_tiers = data.get("service_tiers", {})
        service_tiers = {
            tier_id: ServiceTier(**t_data) for tier_id, t_data in raw_tiers.items()
        }

        service_ownership = dict(data.get("service_ownership", {}))

        return cls(
            company_info=company_info,
            fiscal_calendar=fiscal_calendar,
            service_tiers=service_tiers,
            service_ownership=service_ownership,
        )

    @classmethod
    def from_file(cls, file_path: Path | str) -> OrganizationalMemory:
        """Load and parse organizational memory from JSON file."""
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# =====================================================================
# 5. FourScopeMemoryContext Unified Snapshot
# =====================================================================


class FourScopeMemoryContext(BaseModel):
    """Consolidated snapshot of all 4 memory scopes prepared for agent execution."""

    session_id: str = Field(..., description="Target research session ID")
    user_id: str | None = Field(
        default=None, description="Analyst identity requesting research"
    )
    working: WorkingMemoryState = Field(default_factory=WorkingMemoryState)
    episodic: list[EpisodicMemoryEntry] = Field(default_factory=list)
    semantic: list[SemanticMemoryEntry] = Field(default_factory=list)
    organizational: OrganizationalMemory | None = Field(default=None)

    def to_prompt_context(self) -> str:
        """Format the 4 memory scopes into a clean, injection-safe markdown context for LLMs."""
        sections: list[str] = ["## Memory Context (Four Scopes)"]

        # 1. Working Memory
        sections.append("### Working Memory (Current Execution)")
        if self.working.active_sub_question:
            sections.append(
                f"- Active Sub-Question ({self.working.current_sub_question_index}): {self.working.active_sub_question}"
            )
        if self.working.findings:
            sections.append("- Accumulated Findings:")
            for finding in self.working.findings:
                sections.append(f"  * {finding}")
        if self.working.scratchpad:
            sections.append(f"- Scratchpad: {json.dumps(self.working.scratchpad)}")
        if (
            not self.working.active_sub_question
            and not self.working.findings
            and not self.working.scratchpad
        ):
            sections.append("- (Empty working memory)")

        # 2. Episodic Memory
        sections.append("\n### Episodic Memory (Session Context)")
        if self.episodic:
            for epi_entry in self.episodic:
                sections.append(
                    f"- Turn {epi_entry.turn_index}: Q: {epi_entry.question}"
                )
                sections.append(f"  A: {epi_entry.answer}")
                if epi_entry.citations:
                    sections.append(
                        f"  Citations: {', '.join(epi_entry.citations[:5])}"
                    )
        else:
            sections.append("- (No previous session turns)")

        # 3. Semantic Memory
        sections.append("\n### Semantic Memory (Analyst Profile)")
        if self.semantic:
            for sem_entry in self.semantic:
                sections.append(
                    f"- [{sem_entry.category.upper()}] {sem_entry.key}: {sem_entry.content}"
                )
        else:
            sections.append("- (No user profile entries)")

        # 4. Organizational Memory
        sections.append("\n### Organizational Memory")
        if self.organizational:
            org = self.organizational
            sections.append(
                f"- Company: {org.company_info.name} ({org.company_info.domain})"
            )
            sections.append(
                f"- Fiscal Calendar: Year {org.fiscal_calendar.fiscal_year}, "
                f"Current Quarter: {org.fiscal_calendar.current_quarter}, "
                f"Last Quarter: {org.fiscal_calendar.last_quarter}"
            )
            if org.service_ownership:
                sample_services = list(org.service_ownership.items())[:4]
                summary = ", ".join(f"{s}->{t}" for s, t in sample_services)
                sections.append(f"- Service Ownership: {summary}")
        else:
            sections.append("- (Organizational memory not loaded)")

        return "\n".join(sections)
