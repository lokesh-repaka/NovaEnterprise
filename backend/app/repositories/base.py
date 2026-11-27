"""Generic base repository for NovaEnterprise SQLAlchemy models."""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Standard generic CRUD repository encapsulating SQLAlchemy session operations."""

    def __init__(self, model_cls: type[ModelT], db: Session) -> None:
        self.model_cls = model_cls
        self.db = db

    def get(self, id: str | int) -> ModelT | None:
        """Fetch a single record by its primary key ID."""
        return self.db.get(self.model_cls, id)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        descending: bool = False,
    ) -> list[ModelT]:
        """Fetch a paginated list of records with optional ordering."""
        stmt = select(self.model_cls)
        if order_by is not None:
            stmt = stmt.order_by(order_by.desc() if descending else order_by.asc())
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count(self) -> int:
        """Count total records for this entity."""
        stmt = select(func.count()).select_from(self.model_cls)
        return int(self.db.scalar(stmt) or 0)

    def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity and refresh its attributes."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelT) -> ModelT:
        """Commit updates to an existing attached or merged entity."""
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        """Delete an existing entity from the database."""
        self.db.delete(entity)
        self.db.commit()

    def delete_by_id(self, id: str | int) -> bool:
        """Find an entity by ID and delete it if present. Returns True if found & deleted."""
        entity = self.get(id)
        if entity is not None:
            self.delete(entity)
            return True
        return False

    def save(self, entity: ModelT) -> ModelT:
        """Flush changes without a full commit (useful inside nested transactions)."""
        self.db.add(entity)
        self.db.flush()
        return entity
