"""Domain entity repositories for NovaEnterprise relational models."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.domain import (
    Customer,
    Decision,
    Employee,
    Incident,
    Project,
    Service,
    Team,
    Ticket,
)
from backend.app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    """Repository for Team entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Team, db)

    def get_by_name(self, name: str) -> Team | None:
        """Fetch a team by its unique name."""
        stmt = select(Team).where(Team.name == name)
        return self.db.scalars(stmt).first()

    def get_with_relations(self, team_id: str) -> Team | None:
        """Fetch a team with employees, services, and projects eagerly loaded."""
        stmt = (
            select(Team)
            .where(Team.id == team_id)
            .options(
                selectinload(Team.employees),
                selectinload(Team.services),
                selectinload(Team.projects),
            )
        )
        return self.db.scalars(stmt).first()


class EmployeeRepository(BaseRepository[Employee]):
    """Repository for Employee entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Employee, db)

    def get_by_email(self, email: str) -> Employee | None:
        """Fetch an employee by unique email address."""
        stmt = select(Employee).where(Employee.email == email)
        return self.db.scalars(stmt).first()

    def list_by_team(self, team_id: str) -> list[Employee]:
        """List all employees belonging to a specific team."""
        stmt = (
            select(Employee)
            .where(Employee.team_id == team_id)
            .order_by(Employee.name.asc())
        )
        return list(self.db.scalars(stmt).all())


class ServiceRepository(BaseRepository[Service]):
    """Repository for Service entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Service, db)

    def get_by_name(self, name: str) -> Service | None:
        """Fetch a service by its unique name."""
        stmt = select(Service).where(Service.name == name)
        return self.db.scalars(stmt).first()

    def list_by_tier(self, tier: str) -> list[Service]:
        """List services filtered by criticality tier (e.g., 'tier-1', 'tier-2')."""
        stmt = select(Service).where(Service.tier == tier).order_by(Service.name.asc())
        return list(self.db.scalars(stmt).all())

    def list_by_team(self, team_id: str) -> list[Service]:
        """List all services owned by a specific team."""
        stmt = (
            select(Service)
            .where(Service.owner_team_id == team_id)
            .order_by(Service.name.asc())
        )
        return list(self.db.scalars(stmt).all())


class CustomerRepository(BaseRepository[Customer]):
    """Repository for Customer entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Customer, db)

    def get_by_name(self, name: str) -> Customer | None:
        """Fetch a customer by unique name."""
        stmt = select(Customer).where(Customer.name == name)
        return self.db.scalars(stmt).first()

    def list_by_tier(self, tier: str) -> list[Customer]:
        """List customers filtered by tier (e.g. enterprise, standard, smb)."""
        stmt = (
            select(Customer).where(Customer.tier == tier).order_by(Customer.name.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_industry(self, industry: str) -> list[Customer]:
        """List customers in a specific industry sector."""
        stmt = (
            select(Customer)
            .where(Customer.industry == industry)
            .order_by(Customer.name.asc())
        )
        return list(self.db.scalars(stmt).all())


class IncidentRepository(BaseRepository[Incident]):
    """Repository for Incident records and service associations."""

    def __init__(self, db: Session) -> None:
        super().__init__(Incident, db)

    def get_by_title(self, title: str) -> Incident | None:
        """Fetch an incident by its title."""
        stmt = select(Incident).where(Incident.title == title)
        return self.db.scalars(stmt).first()

    def list_by_service(self, service_id: str) -> list[Incident]:
        """List all incidents affecting a specific service."""
        stmt = (
            select(Incident)
            .where(Incident.impacted_service_id == service_id)
            .order_by(Incident.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_severity(self, severity: str) -> list[Incident]:
        """List incidents matching a severity rating (SEV1, SEV2, SEV3)."""
        stmt = (
            select(Incident)
            .where(Incident.severity == severity)
            .order_by(Incident.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_status(self, status: str) -> list[Incident]:
        """List incidents by status ('investigating', 'identified', 'resolved')."""
        stmt = (
            select(Incident)
            .where(Incident.status == status)
            .order_by(Incident.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Incident]:
        """List incidents that occurred within a given UTC datetime window."""
        stmt = (
            select(Incident)
            .where(Incident.occurred_at >= start_date, Incident.occurred_at <= end_date)
            .order_by(Incident.occurred_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_with_relations(self, incident_id: str) -> Incident | None:
        """Fetch an incident with its impacted service and decisions eagerly loaded."""
        stmt = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(
                selectinload(Incident.impacted_service),
                selectinload(Incident.decisions),
            )
        )
        return self.db.scalars(stmt).first()


class DecisionRepository(BaseRepository[Decision]):
    """Repository for Architectural Decision Records (ADR)."""

    def __init__(self, db: Session) -> None:
        super().__init__(Decision, db)

    def get_by_title(self, title: str) -> Decision | None:
        """Fetch an ADR by its title."""
        stmt = select(Decision).where(Decision.title == title)
        return self.db.scalars(stmt).first()

    def list_by_incident(self, incident_id: str) -> list[Decision]:
        """List decisions taken in response to a specific incident."""
        stmt = (
            select(Decision)
            .where(Decision.incident_id == incident_id)
            .order_by(Decision.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_status(self, status: str) -> list[Decision]:
        """List decisions matching status ('proposed', 'accepted', 'approved', 'deprecated')."""
        stmt = (
            select(Decision)
            .where(Decision.status == status)
            .order_by(Decision.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Project, db)

    def list_by_team(self, team_id: str) -> list[Project]:
        """List projects owned by a team."""
        stmt = (
            select(Project)
            .where(Project.owner_team_id == team_id)
            .order_by(Project.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_status(self, status: str) -> list[Project]:
        """List projects by current status ('active', 'completed', 'archived')."""
        stmt = (
            select(Project)
            .where(Project.status == status)
            .order_by(Project.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())


class TicketRepository(BaseRepository[Ticket]):
    """Repository for Ticket entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(Ticket, db)

    def list_by_project(self, project_id: str) -> list[Ticket]:
        """List tickets linked to a project."""
        stmt = (
            select(Ticket)
            .where(Ticket.project_id == project_id)
            .order_by(Ticket.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_assignee(self, assignee_id: str) -> list[Ticket]:
        """List tickets assigned to an employee."""
        stmt = (
            select(Ticket)
            .where(Ticket.assignee_id == assignee_id)
            .order_by(Ticket.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_status(self, status: str) -> list[Ticket]:
        """List tickets by status ('open', 'in_progress', 'resolved', 'closed')."""
        stmt = (
            select(Ticket)
            .where(Ticket.status == status)
            .order_by(Ticket.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_priority(self, priority: str) -> list[Ticket]:
        """List tickets by priority ('P0', 'P1', 'P2', 'P3')."""
        stmt = (
            select(Ticket)
            .where(Ticket.priority == priority)
            .order_by(Ticket.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())
