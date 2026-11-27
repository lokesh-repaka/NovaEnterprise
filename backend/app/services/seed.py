"""Sample data seeding service and fiscal calendar resolution (P2-4).

Loads curated NovaEnterprise domain data from sample_data/ into PostgreSQL/SQLite,
populates the incident-customer graph associations, and provides deterministic
fiscal quarter date boundary resolution.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

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


def get_sample_data_dir(sample_data_dir: Path | str | None = None) -> Path:
    """Resolve the path to the sample_data directory."""
    if sample_data_dir is not None:
        p = Path(sample_data_dir)
        if p.exists():
            return p
    # Default: search from this file up to the project root
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / "sample_data"
        if candidate.exists() and candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate sample_data directory in project root.")


def load_json_data(file_name: str, sample_data_dir: Path | str | None = None) -> Any:
    """Load JSON data from sample_data/<file_name>."""
    base_dir = get_sample_data_dir(sample_data_dir)
    file_path = base_dir / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"Sample data file not found: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def get_fiscal_calendar(sample_data_dir: Path | str | None = None) -> dict[str, Any]:
    """Retrieve the enterprise fiscal calendar definition from organizational memory."""
    org_memory = load_json_data("organizational_memory.json", sample_data_dir)
    calendar: dict[str, Any] = org_memory.get("fiscal_calendar", {})
    return calendar


def resolve_fiscal_quarter(
    time_phrase: str,
    sample_data_dir: Path | str | None = None,
) -> tuple[datetime, datetime, str]:
    """Resolve a natural language time phrase into exact UTC fiscal quarter boundaries.

    Supports 'last quarter', 'previous quarter', 'current quarter', 'this quarter',
    or explicit quarter identifiers (e.g., '2026-Q1', '2026-Q2', 'Q1', 'Q2').
    """
    calendar = get_fiscal_calendar(sample_data_dir)
    quarters: dict[str, Any] = calendar.get("quarters", {})
    normalized = time_phrase.strip().lower()

    target_quarter_key: str | None = None

    if normalized in ("last quarter", "previous quarter"):
        target_quarter_key = calendar.get("last_quarter")
    elif normalized in ("current quarter", "this quarter"):
        target_quarter_key = calendar.get("current_quarter")
    else:
        # Check direct or prefix matches against known quarters
        for q_key in quarters:
            if (
                normalized == q_key.lower()
                or normalized == q_key.split("-")[-1].lower()
            ):
                target_quarter_key = q_key
                break

    if not target_quarter_key or target_quarter_key not in quarters:
        raise ValueError(f"Could not resolve fiscal quarter for phrase '{time_phrase}'")

    q_info = quarters[target_quarter_key]
    # Parse ISO dates with UTC timezone
    start_str = q_info["start_date"].replace("Z", "+00:00")
    end_str = q_info["end_date"].replace("Z", "+00:00")

    start_dt = datetime.fromisoformat(start_str)
    end_dt = datetime.fromisoformat(end_str)

    return start_dt, end_dt, target_quarter_key


def load_all_documents(
    sample_data_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Scan and load all markdown documents from sample_data/documents/.

    Tags untrusted documents containing prompt injection payloads.
    """
    base_dir = get_sample_data_dir(sample_data_dir)
    doc_dir = base_dir / "documents"
    if not doc_dir.exists():
        raise FileNotFoundError(f"Documents directory not found at {doc_dir}")

    docs: list[dict[str, Any]] = []
    for path in sorted(doc_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        filename = path.name

        # Detect deliberate prompt injection patterns
        is_injection = (
            "<system>" in content or "IGNORE ALL PREVIOUS INSTRUCTIONS" in content
        )
        is_untrusted = is_injection or "vendor-note" in filename.lower()

        docs.append(
            {
                "filename": filename,
                "path": str(path.relative_to(base_dir.parent)),
                "title": path.stem.replace("-", " ").title(),
                "content": content,
                "is_untrusted": is_untrusted,
                "flagged_injection": is_injection,
            }
        )
    return docs


def seed_database(
    db: Session, sample_data_dir: Path | str | None = None
) -> dict[str, int]:
    """Seed the relational database with all canonical entities and associations.

    This function is strictly idempotent: executing multiple times produces identical state
    without unique constraint violations or duplicate associations.
    """
    # 1. Teams
    teams_data = load_json_data("teams.json", sample_data_dir)
    for item in teams_data:
        existing_team = db.get(Team, item["id"])
        if existing_team is None:
            team = Team(
                id=item["id"],
                name=item["name"],
                lead=item.get("lead"),
                slack_channel=item.get("slack_channel"),
                description=item.get("description"),
            )
            db.add(team)
        else:
            existing_team.name = item["name"]
            existing_team.lead = item.get("lead")
            existing_team.slack_channel = item.get("slack_channel")
            existing_team.description = item.get("description")
    db.flush()

    # 2. Employees
    employees_data = load_json_data("employees.json", sample_data_dir)
    for item in employees_data:
        existing_emp = db.get(Employee, item["id"])
        if existing_emp is None:
            emp = Employee(
                id=item["id"],
                name=item["name"],
                email=item["email"],
                role=item.get("role"),
                team_id=item["team_id"],
            )
            db.add(emp)
        else:
            existing_emp.name = item["name"]
            existing_emp.email = item["email"]
            existing_emp.role = item.get("role")
            existing_emp.team_id = item["team_id"]
    db.flush()

    # 3. Services
    services_data = load_json_data("services.json", sample_data_dir)
    for item in services_data:
        existing_svc = db.get(Service, item["id"])
        if existing_svc is None:
            svc = Service(
                id=item["id"],
                name=item["name"],
                tier=item.get("tier", "tier-2"),
                port=item.get("port"),
                repo_url=item.get("repo_url"),
                owner_team_id=item.get("owner_team_id"),
            )
            db.add(svc)
        else:
            existing_svc.name = item["name"]
            existing_svc.tier = item.get("tier", "tier-2")
            existing_svc.port = item.get("port")
            existing_svc.repo_url = item.get("repo_url")
            existing_svc.owner_team_id = item.get("owner_team_id")
    db.flush()

    # 4. Customers
    customers_data = load_json_data("customers.json", sample_data_dir)
    for item in customers_data:
        existing_cust = db.get(Customer, item["id"])
        contract_val = Decimal(str(item.get("contract_value", "0.00")))
        if existing_cust is None:
            cust = Customer(
                id=item["id"],
                name=item["name"],
                tier=item.get("tier", "standard"),
                contract_value=contract_val,
                industry=item.get("industry"),
            )
            db.add(cust)
        else:
            existing_cust.name = item["name"]
            existing_cust.tier = item.get("tier", "standard")
            existing_cust.contract_value = contract_val
            existing_cust.industry = item.get("industry")
    db.flush()

    # 5. Incidents & Customer Associations
    incidents_data = load_json_data("incidents.json", sample_data_dir)
    for item in incidents_data:
        occurred_dt = None
        if item.get("occurred_at"):
            occurred_dt = datetime.fromisoformat(
                item["occurred_at"].replace("Z", "+00:00")
            )
        resolved_dt = None
        if item.get("resolved_at"):
            resolved_dt = datetime.fromisoformat(
                item["resolved_at"].replace("Z", "+00:00")
            )

        existing_inc = db.get(Incident, item["id"])
        if existing_inc is None:
            inc = Incident(
                id=item["id"],
                title=item["title"],
                severity=item["severity"],
                status=item.get("status", "investigating"),
                root_cause=item.get("root_cause"),
                impacted_service_id=item.get("impacted_service_id"),
                occurred_at=occurred_dt,
                resolved_at=resolved_dt,
            )
            db.add(inc)
        else:
            existing_inc.title = item["title"]
            existing_inc.severity = item["severity"]
            existing_inc.status = item.get("status", "investigating")
            existing_inc.root_cause = item.get("root_cause")
            existing_inc.impacted_service_id = item.get("impacted_service_id")
            existing_inc.occurred_at = occurred_dt
            existing_inc.resolved_at = resolved_dt
    db.flush()

    # 6. Decisions (ADR)
    decisions_data = load_json_data("decisions.json", sample_data_dir)
    for item in decisions_data:
        decided_dt = None
        if item.get("decided_at"):
            decided_dt = datetime.fromisoformat(
                item["decided_at"].replace("Z", "+00:00")
            )

        existing_dec = db.get(Decision, item["id"])
        if existing_dec is None:
            dec = Decision(
                id=item["id"],
                title=item["title"],
                status=item.get("status", "proposed"),
                context=item.get("context"),
                decision=item.get("decision"),
                consequences=item.get("consequences"),
                incident_id=item.get("incident_id"),
                decided_at=decided_dt,
            )
            db.add(dec)
        else:
            existing_dec.title = item["title"]
            existing_dec.status = item.get("status", "proposed")
            existing_dec.context = item.get("context")
            existing_dec.decision = item.get("decision")
            existing_dec.consequences = item.get("consequences")
            existing_dec.incident_id = item.get("incident_id")
            existing_dec.decided_at = decided_dt
    db.flush()

    # 7. Projects
    projects_data = load_json_data("projects.json", sample_data_dir)
    for item in projects_data:
        existing_proj = db.get(Project, item["id"])
        if existing_proj is None:
            proj = Project(
                id=item["id"],
                name=item["name"],
                description=item.get("description"),
                owner_team_id=item.get("owner_team_id"),
                status=item.get("status", "active"),
            )
            db.add(proj)
        else:
            existing_proj.name = item["name"]
            existing_proj.description = item.get("description")
            existing_proj.owner_team_id = item.get("owner_team_id")
            existing_proj.status = item.get("status", "active")
    db.flush()

    # 8. Tickets
    tickets_data = load_json_data("tickets.json", sample_data_dir)
    for item in tickets_data:
        existing_ticket = db.get(Ticket, item["id"])
        if existing_ticket is None:
            ticket = Ticket(
                id=item["id"],
                title=item["title"],
                status=item.get("status", "open"),
                priority=item.get("priority", "P2"),
                project_id=item.get("project_id"),
                assignee_id=item.get("assignee_id"),
            )
            db.add(ticket)
        else:
            existing_ticket.title = item["title"]
            existing_ticket.status = item.get("status", "open")
            existing_ticket.priority = item.get("priority", "P2")
            existing_ticket.project_id = item.get("project_id")
            existing_ticket.assignee_id = item.get("assignee_id")
    db.commit()

    return {
        "teams": len(teams_data),
        "employees": len(employees_data),
        "services": len(services_data),
        "customers": len(customers_data),
        "incidents": len(incidents_data),
        "decisions": len(decisions_data),
        "projects": len(projects_data),
        "tickets": len(tickets_data),
    }
