"""Domain entities for NovaEnterprise enterprise knowledge platform.

Models: Team, Employee, Service, Customer, Incident, Decision (ADR), Project, Ticket.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


class Team(Base):
    """Engineering or operational team entity."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    lead: Mapped[str | None] = mapped_column(String(128), nullable=True)
    slack_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="team", cascade="all, delete-orphan"
    )
    services: Mapped[list["Service"]] = relationship(
        "Service", back_populates="owner_team"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="owner_team"
    )


class Employee(Base):
    """Employee member of an organizational team."""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("teams.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="employees")
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="assignee"
    )


class Service(Base):
    """Microservice or software application component."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="tier-2", nullable=False)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    owner_team_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("teams.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner_team: Mapped["Team | None"] = relationship("Team", back_populates="services")
    incidents: Mapped[list["Incident"]] = relationship(
        "Incident", back_populates="impacted_service"
    )


class Customer(Base):
    """Enterprise client or tenant customer record."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    contract_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Incident(Base):
    """Production or security incident record."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="investigating", nullable=False
    )
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    impacted_service_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("services.id"), nullable=True
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    impacted_service: Mapped["Service | None"] = relationship(
        "Service", back_populates="incidents"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        "Decision", back_populates="incident"
    )


class Decision(Base):
    """Architectural Decision Record (ADR) addressing an incident or policy change."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    consequences: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("incidents.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    incident: Mapped["Incident | None"] = relationship(
        "Incident", back_populates="decisions"
    )


class Project(Base):
    """Internal strategic or platform initiative."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_team_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("teams.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner_team: Mapped["Team | None"] = relationship("Team", back_populates="projects")
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="project", cascade="all, delete-orphan"
    )


class Ticket(Base):
    """Issue, task, or bug ticket tracked within a project."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="P2", nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("projects.id"), nullable=True
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project | None"] = relationship(
        "Project", back_populates="tickets"
    )
    assignee: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="assigned_tickets"
    )
