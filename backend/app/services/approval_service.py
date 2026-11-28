"""Governance approval workflow and destructive action service (P11-2, F17, Claude.md §12, §18.1).

Coordinates:
- Intercepting destructive deletion requests from non-admin roles (analysts) and queuing approval requests.
- Executing direct or approved document deletions across SQL database and Vector store.
- Listing, inspecting, and deciding on pending administrative approval gates.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.db import get_session_factory
from backend.app.core.logging import get_logger
from backend.app.models.documents import ApprovalRequest
from backend.app.repositories.documents import (
    ApprovalRequestRepository,
    DocumentChunkRepository,
    DocumentRepository,
)
from rag.vector_store import VectorStoreService, get_vector_store

logger = get_logger("services.approvals")


class ApprovalService:
    """Service managing administrative approval gates and safe destructive operations."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        vector_store: VectorStoreService | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._vector_store = vector_store or get_vector_store()

    def request_document_deletion(
        self, document_id: str, requester_id: str
    ) -> ApprovalRequest:
        """Queue a document deletion request for administrative approval (F17).

        Raises KeyError if the target document does not exist.
        """
        with self._session_factory() as db:
            doc_repo = DocumentRepository(db)
            doc = doc_repo.get(document_id)
            if doc is None:
                raise KeyError(f"Document with ID '{document_id}' not found")

            approval_repo = ApprovalRequestRepository(db)
            existing = approval_repo.get_pending_for_resource(
                resource_type="document", resource_id=document_id
            )
            if existing is not None:
                logger.info(
                    "Reusing existing pending approval request %s for document %s",
                    existing.id,
                    document_id,
                )
                return existing

            req = approval_repo.create_request(
                resource_type="document",
                resource_id=document_id,
                requester_id=requester_id,
                action="delete",
            )
            logger.info(
                "Created approval request %s: user '%s' requested deletion of document '%s'",
                req.id,
                requester_id,
                document_id,
            )
            return req

    def execute_document_deletion(
        self, document_id: str, admin_id: str
    ) -> dict[str, Any]:
        """Directly or approved execution of document deletion across SQL and Vector stores (F17).

        Raises KeyError if the target document does not exist.
        """
        with self._session_factory() as db:
            doc_repo = DocumentRepository(db)
            doc = doc_repo.get(document_id)
            if doc is None:
                raise KeyError(f"Document with ID '{document_id}' not found")

            # 1. Prune semantic chunks from database
            chunk_repo = DocumentChunkRepository(db)
            db_chunks_pruned = chunk_repo.delete_by_document(document_id)

            # 2. Delete document record
            doc_repo.delete(doc)

            # 3. Prune chunks from vector store
            vec_pruned = 0
            if hasattr(self._vector_store, "delete_document"):
                vec_pruned = int(self._vector_store.delete_document(document_id))

            # 4. Resolve any pending approval request for this document
            approval_repo = ApprovalRequestRepository(db)
            pending_req = approval_repo.get_pending_for_resource(
                resource_type="document", resource_id=document_id
            )
            if pending_req is not None:
                approval_repo.resolve_request(
                    request_id=pending_req.id,
                    status="approved",
                    decided_by=admin_id,
                )

            logger.info(
                "Document %s deleted by %s: %d DB chunks pruned, %d vector chunks pruned",
                document_id,
                admin_id,
                db_chunks_pruned,
                vec_pruned,
            )

            return {
                "deleted_document_id": document_id,
                "pruned_chunks": db_chunks_pruned or vec_pruned,
            }

    def list_approvals(
        self,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ApprovalRequest]:
        """List approval requests, optionally filtered by status, with pagination."""
        with self._session_factory() as db:
            repo = ApprovalRequestRepository(db)
            return repo.list_requests(status=status, skip=skip, limit=limit)

    def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        """Retrieve single approval request by ID."""
        with self._session_factory() as db:
            repo = ApprovalRequestRepository(db)
            return repo.get(approval_id)

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        reason: str | None = None,
    ) -> tuple[ApprovalRequest, dict[str, Any]]:
        """Resolve a pending approval gate with an admin decision (approved/rejected).

        Raises:
            KeyError: if approval request does not exist.
            ValueError: if approval request is not pending.
        """
        with self._session_factory() as db:
            repo = ApprovalRequestRepository(db)
            req = repo.get(approval_id)
            if req is None:
                raise KeyError(f"Approval request '{approval_id}' not found")

            if req.status != "pending":
                raise ValueError(
                    f"Approval request '{approval_id}' has already been resolved with status '{req.status}'"
                )

            norm_decision = decision.lower()
            if norm_decision == "rejected":
                updated = repo.resolve_request(
                    request_id=approval_id,
                    status="rejected",
                    decided_by=decided_by,
                )
                assert updated is not None
                logger.info(
                    "Approval request %s rejected by admin %s (reason: %s)",
                    approval_id,
                    decided_by,
                    reason,
                )
                return updated, {
                    "message": f"Deletion request was rejected by administrator {decided_by}",
                    "reason": reason,
                }

            elif norm_decision == "approved":
                execution_result: dict[str, Any] = {}
                # Execute the approved destructive action
                if req.resource_type == "document" and req.action == "delete":
                    doc_repo = DocumentRepository(db)
                    doc = doc_repo.get(req.resource_id)
                    if doc is not None:
                        chunk_repo = DocumentChunkRepository(db)
                        pruned_count = chunk_repo.delete_by_document(req.resource_id)
                        doc_repo.delete(doc)
                        if hasattr(self._vector_store, "delete_document"):
                            self._vector_store.delete_document(req.resource_id)
                        execution_result = {
                            "deleted_document_id": req.resource_id,
                            "pruned_chunks": pruned_count,
                        }
                    else:
                        execution_result = {
                            "deleted_document_id": req.resource_id,
                            "pruned_chunks": 0,
                            "note": "Document already removed",
                        }

                updated = repo.resolve_request(
                    request_id=approval_id,
                    status="approved",
                    decided_by=decided_by,
                )
                assert updated is not None
                logger.info(
                    "Approval request %s approved and executed by admin %s",
                    approval_id,
                    decided_by,
                )
                return updated, execution_result

            else:
                raise ValueError(f"Invalid approval decision: '{decision}'")


# Singleton instance
_approval_service_instance: ApprovalService | None = None


def get_approval_service(
    session_factory: sessionmaker[Session] | None = None,
    vector_store: VectorStoreService | None = None,
) -> ApprovalService:
    """Retrieve or initialize the ApprovalService singleton."""
    global _approval_service_instance
    if _approval_service_instance is None or session_factory is not None:
        _approval_service_instance = ApprovalService(
            session_factory=session_factory,
            vector_store=vector_store,
        )
    return _approval_service_instance


def reset_approval_service() -> None:
    """Reset the ApprovalService singleton (used between test fixtures)."""
    global _approval_service_instance
    _approval_service_instance = None


__all__ = [
    "ApprovalService",
    "get_approval_service",
    "reset_approval_service",
]
