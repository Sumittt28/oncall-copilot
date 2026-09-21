"""RAG retrieval service for gathering evidence."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.incident import Incident
from app.services.embeddings import generate_embedding

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """A piece of evidence for investigation."""

    evidence_id: str
    source_type: str  # "document_chunk", "incident", "commit", etc.
    source_id: int
    source_title: str
    content: str
    similarity: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class RetrievalContext:
    """Context gathered for AI investigation."""

    incident: Incident
    evidence: list[Evidence]
    total_chunks_searched: int = 0
    retrieval_time_ms: float = 0.0


async def retrieve_evidence(
    db: AsyncSession,
    incident: Incident,
    top_k: int = 8,
    min_similarity: float = 0.3,
) -> RetrievalContext:
    """Retrieve relevant evidence for an incident investigation.

    Combines:
    1. Semantic search over document chunks
    2. Related incident history
    3. Documents attached to this incident

    Args:
        db: Database session.
        incident: The incident to investigate.
        top_k: Maximum number of evidence items to return.
        min_similarity: Minimum similarity threshold.

    Returns:
        RetrievalContext with gathered evidence.
    """
    start_time = datetime.now(UTC)
    evidence_list: list[Evidence] = []
    evidence_ids_seen: set[str] = set()

    # 1. Get documents directly attached to this incident
    attached_docs = await _get_attached_documents(db, incident.id)
    for doc, chunk in attached_docs:
        eid = f"doc-{doc.id}-chunk-{chunk.id}"
        if eid not in evidence_ids_seen:
            evidence_ids_seen.add(eid)
            evidence_list.append(
                Evidence(
                    evidence_id=eid,
                    source_type="attached_document",
                    source_id=chunk.id,
                    source_title=f"{doc.title} ({doc.document_type.value})",
                    content=chunk.content,
                    similarity=1.0,  # Direct attachment = highest relevance
                    metadata={
                        "document_id": doc.id,
                        "document_type": doc.document_type.value,
                        "chunk_index": chunk.chunk_index,
                    },
                )
            )

    # 2. Semantic search for similar document chunks
    query_text = f"{incident.title}\n{incident.description}"
    similar_chunks = await _semantic_search_chunks(
        db, query_text, top_k=top_k * 2, min_similarity=min_similarity
    )

    for chunk, doc, similarity in similar_chunks:
        # Skip if already included as attached document
        eid = f"doc-{doc.id}-chunk-{chunk.id}"
        if eid in evidence_ids_seen:
            continue

        evidence_ids_seen.add(eid)
        evidence_list.append(
            Evidence(
                evidence_id=eid,
                source_type="similar_document",
                source_id=chunk.id,
                source_title=f"{doc.title} ({doc.document_type.value})",
                content=chunk.content,
                similarity=similarity,
                metadata={
                    "document_id": doc.id,
                    "document_type": doc.document_type.value,
                    "chunk_index": chunk.chunk_index,
                },
            )
        )

    # 3. Find similar past incidents
    similar_incidents = await _find_similar_incidents(
        db, incident, top_k=3, min_similarity=min_similarity
    )

    for past_incident, similarity in similar_incidents:
        eid = f"incident-{past_incident.id}"
        if eid not in evidence_ids_seen:
            evidence_ids_seen.add(eid)
            evidence_list.append(
                Evidence(
                    evidence_id=eid,
                    source_type="past_incident",
                    source_id=past_incident.id,
                    source_title=f"Past Incident #{past_incident.id}: {past_incident.title}",
                    content=f"Title: {past_incident.title}\nDescription: {past_incident.description}\nStatus: {past_incident.status.value if hasattr(past_incident.status, 'value') else past_incident.status}\nSeverity: {past_incident.severity.value if hasattr(past_incident.severity, 'value') else past_incident.severity}",
                    similarity=similarity,
                    metadata={
                        "incident_id": past_incident.id,
                        "status": past_incident.status.value if hasattr(past_incident.status, 'value') else str(past_incident.status),
                        "severity": past_incident.severity.value if hasattr(past_incident.severity, 'value') else str(past_incident.severity),
                        "resolved": past_incident.resolved_at is not None,
                    },
                )
            )

    # Sort by similarity and limit
    evidence_list.sort(key=lambda e: e.similarity or 0, reverse=True)
    evidence_list = evidence_list[:top_k]

    elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

    return RetrievalContext(
        incident=incident,
        evidence=evidence_list,
        total_chunks_searched=len(similar_chunks),
        retrieval_time_ms=elapsed_ms,
    )


async def _get_attached_documents(
    db: AsyncSession,
    incident_id: int,
) -> list[tuple[Document, DocumentChunk]]:
    """Get all document chunks attached to an incident."""
    result = await db.execute(
        select(Document, DocumentChunk)
        .join(DocumentChunk, Document.id == DocumentChunk.document_id)
        .where(Document.incident_id == incident_id)
        .order_by(Document.id, DocumentChunk.chunk_index)
    )
    rows = result.all()
    return [(row[0], row[1]) for row in rows]


async def _semantic_search_chunks(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
    min_similarity: float = 0.3,
) -> list[tuple[DocumentChunk, Document, float]]:
    """Search for similar document chunks using embeddings.

    Note: This requires PostgreSQL with pgvector. Returns empty list
    if embeddings are not available.
    """
    try:
        from sqlalchemy import text

        query_embedding = generate_embedding(query)

        sql = """
            SELECT
                dc.id as chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.content,
                dc.token_count,
                d.id as doc_id,
                d.title as doc_title,
                d.document_type,
                1 - (dc.embedding <=> :query_embedding::vector) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
            AND 1 - (dc.embedding <=> :query_embedding::vector) >= :min_similarity
            ORDER BY dc.embedding <=> :query_embedding::vector
            LIMIT :limit
        """

        result = await db.execute(
            text(sql),
            {
                "query_embedding": str(query_embedding),
                "min_similarity": min_similarity,
                "limit": top_k,
            },
        )
        rows = result.fetchall()

        results = []
        for row in rows:
            # Create lightweight objects for the results
            chunk = DocumentChunk(
                id=row.chunk_id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                token_count=row.token_count,
            )
            doc = Document(
                id=row.doc_id,
                title=row.doc_title,
                document_type=row.document_type,
                filename="",
                file_path="",
                file_size=0,
                mime_type="",
                uploaded_by_id=0,
            )
            results.append((chunk, doc, float(row.similarity)))

        return results

    except Exception as e:
        logger.warning(f"Semantic search failed (expected with SQLite): {e}")
        return []


async def _find_similar_incidents(
    db: AsyncSession,
    current_incident: Incident,
    top_k: int = 3,
    min_similarity: float = 0.3,
) -> list[tuple[Incident, float]]:
    """Find similar past incidents.

    For now, this uses simple keyword matching. In production,
    you'd use embeddings on incident descriptions.
    """
    # Get resolved incidents from the past (excluding current)
    result = await db.execute(
        select(Incident)
        .where(
            Incident.id != current_incident.id,
            Incident.resolved_at.isnot(None),
        )
        .order_by(Incident.resolved_at.desc())
        .limit(top_k * 3)  # Get more, then filter
    )
    past_incidents = result.scalars().all()

    if not past_incidents:
        return []

    # Simple similarity based on title/description overlap
    # In production, use embeddings
    current_words = set(
        (current_incident.title + " " + current_incident.description).lower().split()
    )

    scored_incidents = []
    for incident in past_incidents:
        incident_words = set(
            (incident.title + " " + incident.description).lower().split()
        )
        overlap = len(current_words & incident_words)
        total = len(current_words | incident_words)
        similarity = overlap / total if total > 0 else 0

        if similarity >= min_similarity:
            scored_incidents.append((incident, similarity))

    # Sort by similarity and return top_k
    scored_incidents.sort(key=lambda x: x[1], reverse=True)
    return scored_incidents[:top_k]
