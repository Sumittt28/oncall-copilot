"""AI investigation API routes."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident, IncidentEvent, IncidentEventType
from app.services.llm.ollama_client import check_model_available, check_ollama_health
from app.services.rag.investigation import (
    InvestigationOutput,
    investigate_incident,
    investigate_incident_stream,
)

router = APIRouter()


class EvidenceItem(BaseModel):
    """Evidence item in investigation response."""

    evidence_id: str
    source_type: str
    source_title: str
    content: str
    similarity: float | None


class PossibleCauseResponse(BaseModel):
    """Possible cause in investigation response."""

    cause: str
    confidence: float
    evidence_ids: list[str]


class InvestigationResponse(BaseModel):
    """Response schema for investigation results."""

    incident_id: int
    summary: str
    severity_estimate: str
    possible_causes: list[PossibleCauseResponse]
    recommended_actions: list[str]
    insufficient_evidence: bool
    evidence: list[EvidenceItem]
    processing_time_ms: float
    raw_response: str


class InvestigationErrorResponse(BaseModel):
    """Response schema for investigation errors."""

    incident_id: int
    error: str
    validation_error: str | None = None
    raw_response: str | None = None


class OllamaStatusResponse(BaseModel):
    """Response schema for Ollama status check."""

    model_config = {"protected_namespaces": ()}

    healthy: bool
    model_available: bool
    model_name: str
    base_url: str


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

    Returns structured analysis with:
    - Summary of findings
    - Possible causes with confidence scores
    - Evidence citations
    - Recommended actions
    """
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

    # Record investigation event
    event = IncidentEvent(
        incident_id=incident_id,
        event_type=IncidentEventType.AI_INVESTIGATION,
        content=f"AI investigation completed. Summary: {output.result.summary[:200]}...",
        actor_id=current_user.id,
    )
    db.add(event)
    await db.flush()

    # Build evidence response
    evidence_items = [
        EvidenceItem(
            evidence_id=ev.evidence_id,
            source_type=ev.source_type,
            source_title=ev.source_title,
            content=ev.content[:500] + "..." if len(ev.content) > 500 else ev.content,
            similarity=ev.similarity,
        )
        for ev in output.retrieval_context.evidence
    ]

    return InvestigationResponse(
        incident_id=incident_id,
        summary=output.result.summary,
        severity_estimate=output.result.severity_estimate,
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
        raw_response=output.raw_response,
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
