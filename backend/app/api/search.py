"""Search API routes."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import CurrentUser, DbSession
from app.models.document import DocumentType
from app.models.incident import IncidentStatus
from app.services.search import search_documents, search_incidents

router = APIRouter()


class DocumentSearchResult(BaseModel):
    """Response schema for document search results."""

    chunk_id: int
    document_id: int
    document_title: str
    document_type: str
    incident_id: int | None
    content: str
    similarity: float


class IncidentSearchResult(BaseModel):
    """Response schema for incident search results."""

    incident_id: int
    title: str
    description: str
    severity: str
    status: str
    similarity: float


class SearchResponse(BaseModel):
    """Response schema for search results."""

    query: str
    documents: list[DocumentSearchResult]
    incidents: list[IncidentSearchResult]
    total_documents: int
    total_incidents: int


@router.get("", response_model=SearchResponse)
async def search(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results per category"),
    min_similarity: float = Query(
        0.3, ge=0.0, le=1.0, description="Minimum similarity threshold"
    ),
    document_type: DocumentType | None = Query(None, description="Filter by document type"),
    incident_status: IncidentStatus | None = Query(None, description="Filter incidents by status"),
) -> SearchResponse:
    """Search documents and incidents using semantic similarity.

    Uses embeddings to find semantically similar content, not just keyword matching.
    Returns both matching document chunks and related incidents.

    Args:
        q: The search query text.
        limit: Maximum number of results per category.
        min_similarity: Minimum cosine similarity (0-1) to include in results.
        document_type: Filter documents by type (runbook, log, doc, postmortem).
        incident_status: Filter incidents by status.
    """
    # Search documents
    doc_results = await search_documents(
        db=db,
        query=q,
        limit=limit,
        min_similarity=min_similarity,
        document_type=document_type.value if document_type else None,
    )

    # Search incidents
    incident_results = await search_incidents(
        db=db,
        query=q,
        limit=limit,
        min_similarity=min_similarity,
        status=incident_status.value if incident_status else None,
    )

    return SearchResponse(
        query=q,
        documents=[
            DocumentSearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                document_type=r.document_type,
                incident_id=r.incident_id,
                content=r.content,
                similarity=r.similarity,
            )
            for r in doc_results
        ],
        incidents=[
            IncidentSearchResult(
                incident_id=r.incident_id,
                title=r.title,
                description=r.description,
                severity=r.severity,
                status=r.status,
                similarity=r.similarity,
            )
            for r in incident_results
        ],
        total_documents=len(doc_results),
        total_incidents=len(incident_results),
    )
