"""Semantic search service using pgvector."""

import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.services.embeddings import generate_embedding

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result with relevance score."""

    chunk_id: int
    document_id: int
    document_title: str
    document_type: str
    incident_id: int | None
    content: str
    similarity: float


@dataclass
class IncidentSearchResult:
    """An incident search result with relevance score."""

    incident_id: int
    title: str
    description: str
    severity: str
    status: str
    similarity: float


async def search_documents(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    min_similarity: float = 0.3,
    document_type: str | None = None,
    incident_id: int | None = None,
) -> list[SearchResult]:
    """Search documents using semantic similarity.

    Args:
        db: Database session.
        query: Search query text.
        limit: Maximum number of results.
        min_similarity: Minimum similarity threshold (0-1).
        document_type: Filter by document type.
        incident_id: Filter by incident.

    Returns:
        List of SearchResult objects sorted by similarity.
    """
    # Generate embedding for query
    query_embedding = generate_embedding(query)

    # Build the SQL query using pgvector's cosine distance
    # Note: pgvector uses distance (lower is better), so we convert to similarity
    sql = """
        SELECT
            dc.id as chunk_id,
            dc.document_id,
            d.title as document_title,
            d.document_type,
            d.incident_id,
            dc.content,
            1 - (dc.embedding <=> :query_embedding::vector) as similarity
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.embedding IS NOT NULL
    """

    params: dict[str, object] = {"query_embedding": str(query_embedding)}

    if document_type:
        sql += " AND d.document_type = :document_type"
        params["document_type"] = document_type

    if incident_id:
        sql += " AND d.incident_id = :incident_id"
        params["incident_id"] = incident_id

    sql += """
        AND 1 - (dc.embedding <=> :query_embedding::vector) >= :min_similarity
        ORDER BY dc.embedding <=> :query_embedding::vector
        LIMIT :limit
    """
    params["min_similarity"] = min_similarity
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        SearchResult(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_title=row.document_title,
            document_type=row.document_type,
            incident_id=row.incident_id,
            content=row.content,
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def search_incidents(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    min_similarity: float = 0.3,
    status: str | None = None,
) -> list[IncidentSearchResult]:
    """Search incidents by finding similar document chunks attached to them.

    This searches through documents attached to incidents and returns
    the incidents ranked by the best matching chunk.

    Args:
        db: Database session.
        query: Search query text.
        limit: Maximum number of results.
        min_similarity: Minimum similarity threshold.
        status: Filter by incident status.

    Returns:
        List of IncidentSearchResult objects sorted by similarity.
    """
    query_embedding = generate_embedding(query)

    sql = """
        WITH ranked_chunks AS (
            SELECT
                d.incident_id,
                1 - (dc.embedding <=> :query_embedding::vector) as similarity,
                ROW_NUMBER() OVER (
                    PARTITION BY d.incident_id
                    ORDER BY dc.embedding <=> :query_embedding::vector
                ) as rn
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
            AND d.incident_id IS NOT NULL
        )
        SELECT
            i.id as incident_id,
            i.title,
            i.description,
            i.severity,
            i.status,
            rc.similarity
        FROM ranked_chunks rc
        JOIN incidents i ON rc.incident_id = i.id
        WHERE rc.rn = 1
        AND rc.similarity >= :min_similarity
    """

    params: dict[str, object] = {
        "query_embedding": str(query_embedding),
        "min_similarity": min_similarity,
    }

    if status:
        sql += " AND i.status = :status"
        params["status"] = status

    sql += """
        ORDER BY rc.similarity DESC
        LIMIT :limit
    """
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        IncidentSearchResult(
            incident_id=row.incident_id,
            title=row.title,
            description=row.description,
            severity=row.severity,
            status=row.status,
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def find_similar_chunks(
    db: AsyncSession,
    chunk_id: int,
    limit: int = 5,
    min_similarity: float = 0.5,
) -> list[SearchResult]:
    """Find chunks similar to a given chunk.

    Args:
        db: Database session.
        chunk_id: ID of the reference chunk.
        limit: Maximum number of results.
        min_similarity: Minimum similarity threshold.

    Returns:
        List of similar chunks (excluding the reference chunk).
    """
    # Get the reference chunk's embedding
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.id == chunk_id)
    )
    chunk = result.scalar_one_or_none()

    if chunk is None or chunk.embedding is None:
        return []

    # Search for similar chunks
    sql = """
        SELECT
            dc.id as chunk_id,
            dc.document_id,
            d.title as document_title,
            d.document_type,
            d.incident_id,
            dc.content,
            1 - (dc.embedding <=> :query_embedding::vector) as similarity
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.embedding IS NOT NULL
        AND dc.id != :exclude_id
        AND 1 - (dc.embedding <=> :query_embedding::vector) >= :min_similarity
        ORDER BY dc.embedding <=> :query_embedding::vector
        LIMIT :limit
    """

    result = await db.execute(
        text(sql),
        {
            "query_embedding": str(list(chunk.embedding)),
            "exclude_id": chunk_id,
            "min_similarity": min_similarity,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    return [
        SearchResult(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_title=row.document_title,
            document_type=row.document_type,
            incident_id=row.incident_id,
            content=row.content,
            similarity=float(row.similarity),
        )
        for row in rows
    ]
