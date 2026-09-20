"""Document management routes."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.models.document import (
    MAX_FILE_SIZE,
    SUPPORTED_FILE_TYPES,
    Document,
    DocumentChunk,
    DocumentType,
)
from app.models.incident import Incident
from app.schemas.document import (
    AttachDocumentRequest,
    DocumentResponse,
    DocumentsListResponse,
    DocumentUploadResponse,
    DocumentWithChunksResponse,
)
from app.services.chunking import chunk_text

router = APIRouter()
settings = get_settings()

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension from filename."""
    return Path(filename).suffix.lower()


def validate_file(file: UploadFile) -> tuple[str, str]:
    """Validate uploaded file.

    Returns:
        Tuple of (extension, mime_type)

    Raises:
        HTTPException: If file is invalid
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    ext = get_file_extension(file.filename)
    if ext not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(SUPPORTED_FILE_TYPES.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Supported types: {supported}",
        )

    return ext, SUPPORTED_FILE_TYPES[ext]


async def save_file(file: UploadFile, ext: str) -> tuple[str, int]:
    """Save uploaded file to disk.

    Returns:
        Tuple of (file_path, file_size)

    Raises:
        HTTPException: If file is too large
    """
    # Generate unique filename
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / unique_name

    # Read and save file with size check
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return str(file_path), file_size


def read_file_content(file_path: str) -> str:
    """Read text content from file."""
    with open(file_path, encoding="utf-8", errors="replace") as f:
        return f.read()


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: DocumentType = Form(...),
    incident_id: int | None = Form(None),
) -> DocumentUploadResponse:
    """Upload a document.

    Supports text-based files: .txt, .md, .log, .json, .yaml, .py, etc.
    Files are chunked for RAG retrieval.
    Optionally attach to an incident.
    """
    # Validate file
    ext, mime_type = validate_file(file)

    # If incident_id provided, verify it exists
    if incident_id is not None:
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalar_one_or_none()
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

    # Save file
    file_path, file_size = await save_file(file, ext)

    try:
        # Read content for chunking
        content = read_file_content(file_path)

        # Create document record
        document = Document(
            title=title,
            document_type=document_type,
            filename=file.filename or "unknown",
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by_id=current_user.id,
            incident_id=incident_id,
        )
        db.add(document)
        await db.flush()

        # Chunk the content
        chunks = chunk_text(content)

        # Create chunk records
        for chunk in chunks:
            db_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                token_count=chunk.token_count,
            )
            db.add(db_chunk)

        await db.flush()
        await db.refresh(document)

        return DocumentUploadResponse(
            document=DocumentResponse.from_orm_with_chunks(document),
            message=f"Document uploaded successfully with {len(chunks)} chunks",
        )

    except Exception as e:
        # Clean up file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        ) from e


@router.get("", response_model=DocumentsListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: int | None = Query(None),
    document_type: DocumentType | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DocumentsListResponse:
    """List documents with optional filtering."""
    query = select(Document).order_by(Document.created_at.desc())

    # Apply filters
    if incident_id is not None:
        query = query.where(Document.incident_id == incident_id)
    if document_type is not None:
        query = query.where(Document.document_type == document_type)

    # Get total count
    count_query = select(func.count()).select_from(Document)
    if incident_id is not None:
        count_query = count_query.where(Document.incident_id == incident_id)
    if document_type is not None:
        count_query = count_query.where(Document.document_type == document_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentsListResponse(
        items=[DocumentResponse.from_orm_with_chunks(doc) for doc in documents],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentWithChunksResponse)
async def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentWithChunksResponse:
    """Get a document with all its chunks."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentWithChunksResponse(
        id=document.id,
        title=document.title,
        document_type=document.document_type,
        filename=document.filename,
        file_size=document.file_size,
        mime_type=document.mime_type,
        uploaded_by_id=document.uploaded_by_id,
        incident_id=document.incident_id,
        created_at=document.created_at,
        chunk_count=len(document.chunks),
        chunks=document.chunks,
    )


@router.post("/{document_id}/attach", response_model=DocumentResponse)
async def attach_to_incident(
    document_id: int,
    request: AttachDocumentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentResponse:
    """Attach an existing document to an incident."""
    # Get document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Verify incident exists
    incident_result = await db.execute(
        select(Incident).where(Incident.id == request.incident_id)
    )
    incident = incident_result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Attach document
    document.incident_id = request.incident_id
    await db.flush()
    await db.refresh(document)

    return DocumentResponse.from_orm_with_chunks(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a document and its chunks."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete file from disk
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Delete document (chunks cascade)
    await db.delete(document)
