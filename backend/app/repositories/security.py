"""User identity and append-only audit log repositories."""

from typing import NoReturn

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.security import AuditLog, User
from backend.app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User identity and RBAC profile management."""

    def __init__(self, db: Session) -> None:
        super().__init__(User, db)

    def get_by_username(self, username: str) -> User | None:
        """Fetch user by unique username."""
        stmt = select(User).where(User.username == username)
        return self.db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        """Fetch user by unique email address."""
        stmt = select(User).where(User.email == email)
        return self.db.scalars(stmt).first()

    def list_by_role(self, role: str) -> list[User]:
        """List all users matching a specified role ('admin', 'analyst', 'viewer')."""
        stmt = select(User).where(User.role == role).order_by(User.username.asc())
        return list(self.db.scalars(stmt).all())


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for strictly append-only, immutable audit trail logging.

    In accordance with Enterprise Security Compliance and CLAUDE.md §18,
    audit records must NEVER be updated or deleted once committed.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(AuditLog, db)

    def record_log(
        self,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Append an immutable audit entry."""
        log = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )
        return self.create(log)

    def list_logs(
        self,
        resource_type: str | None = None,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit events with optional filtering by resource or user."""
        stmt = select(AuditLog)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_logs(
        self,
        resource_type: str | None = None,
        user_id: str | None = None,
    ) -> int:
        """Count audit events matching optional filters."""
        stmt = select(func.count()).select_from(AuditLog)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        return int(self.db.scalar(stmt) or 0)

    # Immutable Invariant Enforcements:
    def update(self, entity: AuditLog) -> NoReturn:
        """Prohibit modifying audit log records."""
        raise PermissionError("Audit logs are strictly append-only and immutable.")

    def delete(self, entity: AuditLog) -> NoReturn:
        """Prohibit deleting audit log records."""
        raise PermissionError("Audit logs are strictly append-only and immutable.")

    def delete_by_id(self, id: str | int) -> NoReturn:
        """Prohibit deleting audit log records by ID."""
        raise PermissionError("Audit logs are strictly append-only and immutable.")
