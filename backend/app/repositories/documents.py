"""Document, chunk, and human-in-the-loop approval repositories."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.documents import ApprovalRequest, Document, DocumentChunk
from backend.app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for ingested documents and prompt-injection quarantine flags."""

    def __init__(self, db: Session) -> None:
        super().__init__(Document, db)

    def get_by_filename(self, filename: str) -> Document | None:
        """Fetch a document by its filename."""
        stmt = select(Document).where(Document.filename == filename)
        return self.db.scalars(stmt).first()

    def get_by_hash(self, content_hash: str) -> Document | None:
        """Fetch a document by its SHA-256 content hash."""
        stmt = select(Document).where(Document.content_hash == content_hash)
        return self.db.scalars(stmt).first()

    def list_flagged_injections(self) -> list[Document]:
        """List all documents flagged as containing prompt injection attempts."""
        stmt = (
            select(Document)
            .where(Document.flagged_injection.is_(True))
            .order_by(Document.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def mark_injection(self, doc_id: str, flagged: bool = True) -> Document | None:
        """Flag or unflag a document for prompt injection."""
        doc = self.get(doc_id)
        if doc is not None:
            doc.flagged_injection = flagged
            return self.update(doc)
        return None

    def list_by_status(self, status: str) -> list[Document]:
        """List documents by ingestion status ('pending', 'indexed', 'failed')."""
        stmt = (
            select(Document)
            .where(Document.status == status)
            .order_by(Document.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for semantic document chunks and vector store references."""

    def __init__(self, db: Session) -> None:
        super().__init__(DocumentChunk, db)

    def create_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Bulk insert semantic chunks belonging to a document."""
        self.db.add_all(chunks)
        self.db.commit()
        return chunks

    def list_by_document(self, document_id: str) -> list[DocumentChunk]:
        """List all chunks associated with a specific document in sequential order."""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.scalars(stmt).all())

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document before re-indexing. Returns deleted count."""
        chunks = self.list_by_document(document_id)
        count = len(chunks)
        for chunk in chunks:
            self.db.delete(chunk)
        if count > 0:
            self.db.commit()
        return count


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    """Repository for Human-in-the-Loop (HITL) approval gates."""

    def __init__(self, db: Session) -> None:
        super().__init__(ApprovalRequest, db)

    def create_request(
        self,
        resource_type: str,
        resource_id: str,
        requester_id: str,
        action: str = "delete",
    ) -> ApprovalRequest:
        """Create a new pending HITL approval request."""
        req = ApprovalRequest(
            id=f"appr-{resource_type}-{resource_id[:8]}-{uuid.uuid4().hex[:6]}",
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            requester_id=requester_id,
            status="pending",
        )
        return self.create(req)

    def list_requests(
        self,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ApprovalRequest]:
        """List approval requests with optional status filtering and pagination."""
        stmt = select(ApprovalRequest)
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        stmt = (
            stmt.order_by(ApprovalRequest.created_at.desc()).offset(skip).limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_pending_for_resource(
        self, resource_type: str, resource_id: str
    ) -> ApprovalRequest | None:
        """Find an active pending approval request for a given resource."""
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.resource_type == resource_type,
                ApprovalRequest.resource_id == resource_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        return self.db.scalars(stmt).first()

    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests awaiting review."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def resolve_request(
        self,
        request_id: str,
        status: str,
        decided_by: str,
    ) -> ApprovalRequest | None:
        """Mark an approval request as approved or rejected with auditor metadata."""
        req = self.get(request_id)
        if req is None:
            return None

        req.status = status
        req.decided_by = decided_by
        return self.update(req)
