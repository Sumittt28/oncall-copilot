"""Document schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentType


class DocumentChunkResponse(BaseModel):
    """Response schema for document chunks."""

    id: int
    document_id: int
    chunk_index: int
    content: str
    token_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Response schema for document data."""

    id: int
    title: str
    document_type: DocumentType
    filename: str
    file_size: int
    mime_type: str
    uploaded_by_id: int
    incident_id: int | None
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_chunks(cls, doc: "Document") -> "DocumentResponse":
        """Create response with chunk count from ORM object."""

        return cls(
            id=doc.id,
            title=doc.title,
            document_type=doc.document_type,
            filename=doc.filename,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            uploaded_by_id=doc.uploaded_by_id,
            incident_id=doc.incident_id,
            created_at=doc.created_at,
            chunk_count=len(doc.chunks) if doc.chunks else 0,
        )


class DocumentWithChunksResponse(DocumentResponse):
    """Response schema for document with all chunks."""

    chunks: list[DocumentChunkResponse] = []


class DocumentsListResponse(BaseModel):
    """Response schema for list of documents."""

    items: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    document: DocumentResponse
    message: str


class AttachDocumentRequest(BaseModel):
    """Request to attach a document to an incident."""

    incident_id: int


# Import for type hint
from app.models.document import Document  # noqa: E402
