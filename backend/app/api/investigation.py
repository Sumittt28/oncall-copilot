"""AI investigation API routes."""

import json
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident, IncidentEvent, IncidentEventType
from app.models.investigation import AIInvestigation
from app.services.llm.ollama_client import check_model_available, check_ollama_health
from app.services.rag.investigation import (
    InvestigationOutput,
    investigate_incident,
    investigate_incident_stream,
)
from app.services.rag.storage import save_investigation, validate_citations

router = APIRouter()


# ============== Schemas ==============


class EvidenceItem(BaseModel):
    """Evidence item in investigation response."""

    evidence_id: str
    source_type: str
    source_title: str
    content: str
    similarity: float | None
    chunk_id: int | None = None
    source_incident_id: int | None = None
    cited_in_causes: bool = False
    cited_in_actions: bool = False


class PossibleCauseResponse(BaseModel):
    """Possible cause in investigation response."""

    cause: str
    confidence: float
    evidence_ids: list[str]


class CitationValidation(BaseModel):
    """Citation validation result."""

    is_valid: bool
    errors: list[str]


class InvestigationResponse(BaseModel):
    """Response schema for investigation results."""

    model_config = {"protected_namespaces": ()}

    id: int | None = None
    incident_id: int
    summary: str
    severity_estimate: str
    confidence: float
    possible_causes: list[PossibleCauseResponse]
    recommended_actions: list[str]
    insufficient_evidence: bool
    evidence: list[EvidenceItem]
    processing_time_ms: float
    model_name: str
    citation_validation: CitationValidation
    created_at: datetime | None = None


class InvestigationSummary(BaseModel):
    """Summary of an investigation for listing."""

    model_config = {"protected_namespaces": ()}

    id: int
    incident_id: int
    summary: str
    severity_estimate: str
    confidence: float
    insufficient_evidence: bool
    evidence_count: int
    model_name: str
    processing_time_ms: float
    created_at: datetime


class InvestigationListResponse(BaseModel):
    """Paginated list of investigations."""

    items: list[InvestigationSummary]
    total: int


class OllamaStatusResponse(BaseModel):
    """Response schema for Ollama status check."""

    model_config = {"protected_namespaces": ()}

    healthy: bool
    model_available: bool
    model_name: str
    base_url: str


# ============== Endpoints ==============


@router.get("/ollama/status", response_model=OllamaStatusResponse)
async def check_ollama_status(current_user: CurrentUser) -> OllamaStatusResponse:
    """Check if Ollama is running and the model is available."""
    from app.core.config import get_settings

    settings = get_settings()

    healthy = await check_ollama_health()
    model_available = await check_model_available() if healthy else False

    return OllamaStatusResponse(
        healthy=healthy,
        model_available=model_available,
        model_name=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )


@router.post(
    "/incidents/{incident_id}/investigate",
    response_model=InvestigationResponse,
    responses={
        404: {"description": "Incident not found"},
        503: {"description": "Ollama unavailable"},
    },
)
async def investigate(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> InvestigationResponse:
    """Run AI investigation on an incident.

    Retrieves relevant evidence from documents and past incidents,
    then uses the local LLM to analyze and provide root cause insights.

    The investigation is saved to the database for future reference.

    Returns structured analysis with:
    - Summary of findings
    - Possible causes with confidence scores
    - Evidence citations (validated)
    - Recommended actions
    """
    from app.core.config import get_settings

    settings = get_settings()

    # Check if Ollama is available
    if not await check_ollama_health():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is not available. Please ensure it is running.",
        )

    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Run investigation
    output: InvestigationOutput = await investigate_incident(db, incident_id)

    # Handle errors
    if output.error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=output.error,
        )

    if output.validation_error or output.result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=output.validation_error or "Failed to parse AI response",
        )

    # Validate citations
    is_valid, validation_errors = validate_citations(output.result)

    # Save investigation to database
    saved_investigation = await save_investigation(
        db=db,
        incident_id=incident_id,
        user_id=current_user.id,
        output=output,
    )

    # Record investigation event
    event = IncidentEvent(
        incident_id=incident_id,
        event_type=IncidentEventType.AI_INVESTIGATION,
        content=f"AI investigation #{saved_investigation.id} completed. Summary: {output.result.summary[:200]}...",
        actor_id=current_user.id,
    )
    db.add(event)
    await db.commit()

    # Calculate confidence
    confidence = 0.0
    if output.result.possible_causes:
        confidence = max(c.confidence for c in output.result.possible_causes)

    # Collect cited evidence IDs
    cited_evidence_ids = set()
    for cause in output.result.possible_causes:
        cited_evidence_ids.update(cause.evidence_ids)

    # Build evidence response
    evidence_items = [
        EvidenceItem(
            evidence_id=ev.evidence_id,
            source_type=ev.source_type,
            source_title=ev.source_title,
            content=ev.content[:500] + "..." if len(ev.content) > 500 else ev.content,
            similarity=ev.similarity,
            chunk_id=ev.source_id if ev.source_type in ("attached_document", "similar_document") else None,
            source_incident_id=ev.source_id if ev.source_type == "past_incident" else None,
            cited_in_causes=ev.evidence_id in cited_evidence_ids,
            cited_in_actions=any(ev.evidence_id in action for action in output.result.recommended_actions),
        )
        for ev in output.retrieval_context.evidence
    ]

    return InvestigationResponse(
        id=saved_investigation.id,
        incident_id=incident_id,
        summary=output.result.summary,
        severity_estimate=output.result.severity_estimate,
        confidence=confidence,
        possible_causes=[
            PossibleCauseResponse(
                cause=c.cause,
                confidence=c.confidence,
                evidence_ids=c.evidence_ids,
            )
            for c in output.result.possible_causes
        ],
        recommended_actions=output.result.recommended_actions,
        insufficient_evidence=output.result.insufficient_evidence,
        evidence=evidence_items,
        processing_time_ms=output.processing_time_ms,
        model_name=settings.ollama_model,
        citation_validation=CitationValidation(
            is_valid=is_valid,
            errors=validation_errors,
        ),
        created_at=saved_investigation.created_at,
    )


@router.get(
    "/incidents/{incident_id}/investigations",
    response_model=InvestigationListResponse,
)
async def list_investigations(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> InvestigationListResponse:
    """List all investigations for an incident."""
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Count total
    count_result = await db.execute(
        select(AIInvestigation)
        .where(AIInvestigation.incident_id == incident_id)
    )
    total = len(count_result.scalars().all())

    # Get paginated results
    inv_result = await db.execute(
        select(AIInvestigation)
        .where(AIInvestigation.incident_id == incident_id)
        .order_by(AIInvestigation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    investigations = inv_result.scalars().all()

    return InvestigationListResponse(
        items=[
            InvestigationSummary(
                id=inv.id,
                incident_id=inv.incident_id,
                summary=inv.summary,
                severity_estimate=inv.severity_estimate,
                confidence=inv.confidence,
                insufficient_evidence=inv.insufficient_evidence,
                evidence_count=inv.evidence_count,
                model_name=inv.model_name,
                processing_time_ms=inv.processing_time_ms,
                created_at=inv.created_at,
            )
            for inv in investigations
        ],
        total=total,
    )


@router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationResponse,
)
async def get_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> InvestigationResponse:
    """Get a specific investigation by ID with full details."""
    result = await db.execute(
        select(AIInvestigation)
        .options(selectinload(AIInvestigation.evidence_citations))
        .where(AIInvestigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()

    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    # Parse structured output - cast to Any for JSON data
    from typing import Any, cast
    structured: dict[str, Any] = cast(dict[str, Any], investigation.structured_output)
    possible_causes = [
        PossibleCauseResponse(
            cause=c["cause"],
            confidence=c["confidence"],
            evidence_ids=c.get("evidence_ids", []),
        )
        for c in structured.get("possible_causes", [])
    ]

    # Build evidence from stored citations
    evidence_items = [
        EvidenceItem(
            evidence_id=ev.evidence_id,
            source_type=ev.source_type,
            source_title=ev.source_title,
            content=ev.content_preview,
            similarity=ev.relevance_score,
            chunk_id=ev.chunk_id,
            source_incident_id=ev.source_incident_id,
            cited_in_causes=ev.cited_in_causes,
            cited_in_actions=ev.cited_in_actions,
        )
        for ev in investigation.evidence_citations
    ]

    # Validate citations from stored data
    from app.services.rag.investigation import InvestigationResult, PossibleCause

    result_obj = InvestigationResult(
        summary=investigation.summary,
        severity_estimate=investigation.severity_estimate,
        possible_causes=[
            PossibleCause(
                cause=c["cause"],
                confidence=c["confidence"],
                evidence_ids=c.get("evidence_ids", []),
            )
            for c in structured.get("possible_causes", [])
        ],
        recommended_actions=structured.get("recommended_actions", []),
        insufficient_evidence=investigation.insufficient_evidence,
    )
    is_valid, validation_errors = validate_citations(result_obj)

    return InvestigationResponse(
        id=investigation.id,
        incident_id=investigation.incident_id,
        summary=investigation.summary,
        severity_estimate=investigation.severity_estimate,
        confidence=investigation.confidence,
        possible_causes=possible_causes,
        recommended_actions=structured.get("recommended_actions", []),
        insufficient_evidence=investigation.insufficient_evidence,
        evidence=evidence_items,
        processing_time_ms=investigation.processing_time_ms,
        model_name=investigation.model_name,
        citation_validation=CitationValidation(
            is_valid=is_valid,
            errors=validation_errors,
        ),
        created_at=investigation.created_at,
    )


@router.get(
    "/incidents/{incident_id}/investigate/stream",
    responses={
        404: {"description": "Incident not found"},
        503: {"description": "Ollama unavailable"},
    },
)
async def investigate_stream(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Stream AI investigation on an incident via Server-Sent Events (SSE).

    Events emitted:
    - `evidence`: Evidence items being used (sent first)
    - `token`: Individual tokens as they are generated
    - `result`: Final structured result (if parsing succeeds)
    - `validation_error`: Parsing error (if result parsing fails)
    - `error`: Error messages
    - `done`: Completion signal with raw response
    """
    # Check if Ollama is available
    if not await check_ollama_health():
        async def error_stream() -> AsyncGenerator[str, None]:
            yield f"event: error\ndata: {json.dumps({'message': 'Ollama is not available'})}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
        )

    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        async def not_found_stream() -> AsyncGenerator[str, None]:
            yield f"event: error\ndata: {json.dumps({'message': 'Incident not found'})}\n\n"

        return StreamingResponse(
            not_found_stream(),
            media_type="text/event-stream",
        )

    # Stream investigation
    return StreamingResponse(
        investigate_incident_stream(db, incident_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
