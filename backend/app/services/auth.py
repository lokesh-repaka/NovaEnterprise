"""Authentication and demo identity service (P3-2).

Manages predefined demo users across the role hierarchy (admin, analyst, viewer),
handles password verification, seeds demo user accounts, and issues JWT tokens.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import (
    Role,
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.security import User
from backend.app.repositories.security import UserRepository
from backend.app.schemas.auth import DemoUser, TokenResponse

# Canonical demo password for development and offline evaluation environments
DEMO_PASSWORD = "demo_password"

# Predefined demo accounts covering the three RBAC tiers (Claude.md §2)
CANONICAL_DEMO_USERS: list[dict[str, Any]] = [
    {
        "id": "usr-admin-01",
        "username": "admin",
        "email": "admin@novaenterprise.io",
        "role": Role.ADMIN,
        "name": "Sarah Connor",
        "description": "Full administrative control: document deletion approval, system reindexing, and RBAC governance.",
    },
    {
        "id": "usr-analyst-01",
        "username": "analyst",
        "email": "analyst@novaenterprise.io",
        "role": Role.ANALYST,
        "name": "Alex Mercer",
        "description": "Lead risk analyst: initiate multi-agent research sessions, upload documents, query graph, and access memory.",
    },
    {
        "id": "usr-viewer-01",
        "username": "viewer",
        "email": "viewer@novaenterprise.io",
        "role": Role.VIEWER,
        "name": "Taylor Reed",
        "description": "Read-only access: inspect dashboards, browse customers, view incidents, and review completed research.",
    },
]


def get_demo_users() -> list[DemoUser]:
    """Retrieve the list of predefined demo users and their roles."""
    return [DemoUser.model_validate(user) for user in CANONICAL_DEMO_USERS]


def get_demo_user_by_role(role: Role | str) -> DemoUser | None:
    """Retrieve demo user metadata matching a specified role."""
    target_role = role.value if isinstance(role, Role) else str(role).lower()
    for user_data in CANONICAL_DEMO_USERS:
        user_role = (
            user_data["role"].value
            if isinstance(user_data["role"], Role)
            else str(user_data["role"]).lower()
        )
        if user_role == target_role:
            return DemoUser.model_validate(user_data)
    return None


def seed_demo_users(db: Session) -> list[User]:
    """Ensure all canonical demo users exist in the database with hashed passwords.

    Idempotent operation: creates missing demo accounts or updates their password hashes.
    """
    repo = UserRepository(db)
    seeded_users: list[User] = []
    hashed_pwd = get_password_hash(DEMO_PASSWORD)

    for data in CANONICAL_DEMO_USERS:
        existing = repo.get_by_username(data["username"]) or repo.get_by_email(
            data["email"]
        )
        role_str = (
            data["role"].value
            if isinstance(data["role"], Role)
            else str(data["role"]).lower()
        )

        if existing is None:
            user = User(
                id=data["id"],
                username=data["username"],
                email=data["email"],
                role=role_str,
                hashed_password=hashed_pwd,
            )
            created = repo.create(user)
            seeded_users.append(created)
        else:
            existing.role = role_str
            existing.hashed_password = hashed_pwd
            repo.update(existing)
            seeded_users.append(existing)

    return seeded_users


def authenticate_user(
    db: Session,
    username_or_email: str,
    password: str,
) -> User | None:
    """Validate user credentials against the database.

    If users have not yet been seeded into the database, automatically seeds
    canonical demo accounts to guarantee seamless developer experience.
    """
    repo = UserRepository(db)
    user = repo.get_by_username(username_or_email)
    if user is None:
        user = repo.get_by_email(username_or_email)

    # Auto-seed fallback for demo accounts if DB is empty
    if user is None:
        for demo in CANONICAL_DEMO_USERS:
            if (
                username_or_email == demo["username"]
                or username_or_email == demo["email"]
            ):
                seed_demo_users(db)
                user = repo.get_by_username(demo["username"])
                break

    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def issue_token_for_user(
    user_id: str,
    username: str,
    email: str,
    role: str | Role,
) -> TokenResponse:
    """Issue a signed JWT access token and return the formatted TokenResponse."""
    settings = get_settings()
    role_str = role.value if isinstance(role, Role) else str(role).lower()

    token_data = {
        "sub": user_id,
        "username": username,
        "email": email,
        "role": role_str,
        "is_active": True,
    }

    access_token = create_access_token(token_data)
    expires_in = settings.access_token_expire_minutes * 60

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        role=role_str,
        user_id=user_id,
        email=email,
        username=username,
    )
