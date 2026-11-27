"""Document ingestion and management API endpoints (P5-4, F13, N7, N8).

Provides:
- POST /api/v1/documents/upload: Upload, validate, parse, chunk, extract, and index documents (analyst+)
- POST /api/v1/documents: Alias for upload (analyst+)
- GET /api/v1/documents: List indexed documents with pagination and status filtering (viewer+)
- GET /api/v1/documents/{id}: Retrieve document metadata and semantic chunks (viewer+)
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.db import get_db
from backend.app.core.logging import get_logger
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.documents import Document, DocumentChunk
from backend.app.schemas.documents import (
    DocumentChunkDetail,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from rag.graph_store import get_graph_store
from rag.ingest import ingest_document
from rag.vector_store import get_vector_store

logger = get_logger("api.documents")

router = APIRouter(prefix="/documents", tags=["Documents"])

from backend.app.core.upload_validator import validate_upload


async def _process_document_upload(
    file: UploadFile,
    db: Session,
    settings: Settings,
    current_user: AuthenticatedUser,
) -> DocumentUploadResponse:
    """Validate upload payload and execute end-to-end ingestion pipeline."""
    filename = file.filename or "uploaded_document.txt"

    # 1. Enforce validation (extension, size, empty file) and scrub secrets (N7, N8, BRD §242)
    content = await file.read()
    validation = validate_upload(
        file_data=content,
        filename=filename,
        max_mb=settings.max_upload_mb,
        scrub=True,
    )
    if not validation.is_valid:
        raise HTTPException(
            status_code=validation.status_code,
            detail=validation.error_detail,
        )

    logger.info(
        "User '%s' (role=%s) uploading document '%s' (%d bytes, %d secrets scrubbed)",
        current_user.id,
        current_user.role,
        filename,
        len(content),
        validation.secrets_scrubbed_count,
    )

    # 2. Ingest into stores and relational DB (F13, N8)
    vector_store = get_vector_store(settings)
    graph_store = get_graph_store(settings)

    result = ingest_document(
        data=validation.content_bytes,
        filename=filename,
        db=db,
        vector_store=vector_store,
        graph_store=graph_store,
        settings=settings,
    )

    return DocumentUploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
        entities_extracted=result.entities_extracted,
        flagged_injection=result.flagged_injection,
        status=result.status,
        created_at=result.created_at,
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest enterprise document",
    description="Upload a markdown, text, or PDF document for parsing, chunking, and indexing. Requires analyst or admin role.",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file (.md, .txt, .pdf)")],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("analyst"))],
) -> DocumentUploadResponse:
    """Endpoint for uploading documents to the RAG knowledge index."""
    return await _process_document_upload(
        file=file,
        db=db,
        settings=settings,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest enterprise document (alias)",
    description="Alias for POST /api/v1/documents/upload. Requires analyst or admin role.",
)
async def upload_document_alias(
    file: Annotated[UploadFile, File(description="Document file (.md, .txt, .pdf)")],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("analyst"))],
) -> DocumentUploadResponse:
    """Root route alias for document upload."""
    return await _process_document_upload(
        file=file,
        db=db,
        settings=settings,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List indexed enterprise documents",
    description="Retrieve paginated list of indexed documents with optional status filtering. Requires viewer role.",
)
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    skip: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Max documents to return")
    ] = 50,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by status (e.g. indexed, pending, flagged)",
        ),
    ] = None,
) -> list[DocumentResponse]:
    """List documents from relational database."""
    query = select(Document)

    if status_filter:
        if status_filter == "flagged":
            query = query.where(
                (Document.status == "flagged") | (Document.flagged_injection.is_(True))
            )
        else:
            query = query.where(Document.status == status_filter)

    query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    documents = list(db.scalars(query).all())
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Retrieve document detail and semantic chunks",
    description="Retrieve a single document by its UUID along with its semantic chunk breakdown. Requires viewer role.",
)
def get_document(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> DocumentDetailResponse:
    """Retrieve document record with chunks."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    chunk_stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = list(db.scalars(chunk_stmt).all())

    chunk_details = [
        DocumentChunkDetail(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            embedding_id=chunk.embedding_id,
            metadata_json=chunk.metadata_json or {},
        )
        for chunk in chunks
    ]

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        content_hash=doc.content_hash,
        chunk_count=doc.chunk_count,
        flagged_injection=doc.flagged_injection,
        status=doc.status,
        created_at=doc.created_at,
        chunks=chunk_details,
    )
