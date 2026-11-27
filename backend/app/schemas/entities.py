"""Pydantic v2 schemas for domain browse entities (P4-2).

Codifies response data models for Customers, Incidents, Services, and Teams
in strict accordance with docs/API_CONTRACT.md and Claude.md §12.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CustomerResponse(BaseModel):
    """Customer entity representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique customer ID (e.g. cust-acme)")
    name: str = Field(..., description="Customer enterprise name")
    tier: str = Field(..., description="Subscription or criticality tier (enterprise, standard, smb)")
    contract_value: Decimal = Field(..., description="Annual contract value")
    industry: str | None = Field(default=None, description="Industry sector")
    created_at: datetime = Field(..., description="Timestamp of record creation")


class ServiceResponse(BaseModel):
    """Microservice or software application component representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique service ID (e.g. svc-payments-api)")
    name: str = Field(..., description="Service name")
    tier: str = Field(..., description="Service criticality tier (tier-1, tier-2)")
    port: int | None = Field(default=None, description="Internal network port")
    repo_url: str | None = Field(default=None, description="Version control repository URL")
    owner_team_id: str | None = Field(default=None, description="Owner team identifier")
    created_at: datetime = Field(..., description="Timestamp of record creation")


class EmployeeResponse(BaseModel):
    """Employee team member representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique employee identifier")
    name: str = Field(..., description="Employee full name")
    email: str = Field(..., description="Corporate email address")
    role: str | None = Field(default=None, description="Job title / role")
    team_id: str = Field(..., description="Assigned team identifier")
    created_at: datetime = Field(..., description="Timestamp of record creation")


class DecisionSummary(BaseModel):
    """Compact summary of an Architectural Decision Record (ADR)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ADR identifier (e.g. adr-012)")
    title: str = Field(..., description="ADR title")
    status: str = Field(..., description="Decision status (proposed, accepted, superseded)")
    decided_at: datetime | None = Field(default=None, description="Date decision was ratified")


class DecisionResponse(BaseModel):
    """Architectural Decision Record (ADR) representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ADR identifier (e.g. adr-012)")
    title: str = Field(..., description="ADR title")
    status: str = Field(..., description="Decision status (proposed, accepted, superseded, rejected)")
    context: str | None = Field(default=None, description="Problem context and background")
    decision: str | None = Field(default=None, description="Chosen technical architecture decision")
    consequences: str | None = Field(default=None, description="Pros, cons, and operational consequences")
    incident_id: str | None = Field(default=None, description="Associated incident ID if applicable")
    decided_at: datetime | None = Field(default=None, description="Timestamp decision was ratified")
    created_at: datetime = Field(..., description="Timestamp record created")


class ProjectSummary(BaseModel):
    """Compact summary of an internal engineering initiative."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Project identifier (e.g. prj-pci-dss)")
    name: str = Field(..., description="Project initiative name")
    status: str = Field(..., description="Project status (active, completed)")


class ProjectResponse(BaseModel):
    """Internal strategic or platform initiative representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Project identifier (e.g. prj-pci-dss)")
    name: str = Field(..., description="Project name")
    description: str | None = Field(default=None, description="Project goals and scope")
    owner_team_id: str | None = Field(default=None, description="Owning engineering team ID")
    status: str = Field(..., description="Project status (active, completed, archived)")
    created_at: datetime = Field(..., description="Timestamp record created")


class TicketResponse(BaseModel):
    """Issue or task ticket representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Ticket identifier (e.g. tkt-101)")
    title: str = Field(..., description="Ticket summary")
    status: str = Field(..., description="Ticket status (open, in_progress, resolved, closed)")
    priority: str = Field(..., description="Ticket priority (P0, P1, P2, P3)")
    project_id: str | None = Field(default=None, description="Associated project ID")
    assignee_id: str | None = Field(default=None, description="Assigned employee ID")
    created_at: datetime = Field(..., description="Timestamp record created")


class ProjectDetailResponse(ProjectResponse):
    """Project detail representation with tracked tickets."""

    tickets: list[TicketResponse] = Field(default_factory=list, description="Tickets tracked within this project")


class TeamResponse(BaseModel):
    """Engineering or operational team representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique team identifier (e.g. team-payments-platform)")
    name: str = Field(..., description="Team name")
    lead: str | None = Field(default=None, description="Engineering lead name")
    slack_channel: str | None = Field(default=None, description="Team communication channel")
    description: str | None = Field(default=None, description="Team mission and ownership description")
    created_at: datetime = Field(..., description="Timestamp of record creation")


class TeamDetailResponse(TeamResponse):
    """Detailed team representation with members, owned services, and active projects."""

    employees: list[EmployeeResponse] = Field(default_factory=list, description="Team members")
    services: list[ServiceResponse] = Field(default_factory=list, description="Services owned by this team")
    projects: list[ProjectSummary] = Field(default_factory=list, description="Projects owned by this team")


class IncidentResponse(BaseModel):
    """Production or security incident record representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Incident tracking ID (e.g. inc-2031)")
    title: str = Field(..., description="Incident title or summary")
    severity: str = Field(..., description="Severity level (SEV1, SEV2, SEV3)")
    status: str = Field(..., description="Operational status (investigating, mitigated, resolved)")
    root_cause: str | None = Field(default=None, description="Postmortem identified root cause")
    impacted_service_id: str | None = Field(default=None, description="Impacted service ID")
    occurred_at: datetime | None = Field(default=None, description="Timestamp incident started")
    resolved_at: datetime | None = Field(default=None, description="Timestamp incident resolved")
    created_at: datetime = Field(..., description="Timestamp record created")


class IncidentDetailResponse(IncidentResponse):
    """Detailed incident record with impacted service and associated decisions."""

    impacted_service: ServiceResponse | None = Field(default=None, description="Impacted microservice details")
    decisions: list[DecisionSummary] = Field(default_factory=list, description="Associated ADR decisions")
