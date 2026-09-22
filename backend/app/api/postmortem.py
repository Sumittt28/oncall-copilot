"""Postmortem API routes."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident, IncidentEvent, IncidentEventType
from app.models.postmortem import Postmortem
from app.services.llm.ollama_client import check_ollama_health
from app.services.rag.postmortem import generate_postmortem

router = APIRouter()


# ============== Schemas ==============


class PostmortemResponse(BaseModel):
    """Schema for postmortem response."""

    model_config = {"protected_namespaces": ()}

    id: int
    incident_id: int
    content: str
    model_name: str
    processing_time_ms: float
    created_at: datetime
    updated_at: datetime


class PostmortemGenerateResponse(BaseModel):
    """Schema for postmortem generation response."""

    model_config = {"protected_namespaces": ()}

    id: int
    incident_id: int
    content: str
    model_name: str
    processing_time_ms: float
    is_new: bool


# ============== Endpoints ==============


@router.post(
    "/incidents/{incident_id}/postmortem",
    response_model=PostmortemGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_incident_postmortem(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PostmortemGenerateResponse:
    """Generate a postmortem for a resolved incident.

    If a postmortem already exists, it will be regenerated.
    """
    # Check if Ollama is available
    if not await check_ollama_health():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is not available. Please ensure it is running.",
        )

    # Verify incident exists and is resolved
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    if incident.resolved_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate postmortem for unresolved incident",
        )

    # Generate postmortem
    postmortem_result = await generate_postmortem(db, incident_id)

    if postmortem_result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=postmortem_result.error,
        )

    # Check if postmortem already exists
    existing_result = await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )
    existing = existing_result.scalar_one_or_none()

    is_new = existing is None

    if existing:
        # Update existing postmortem
        existing.content = postmortem_result.content
        existing.model_name = postmortem_result.model_name
        existing.processing_time_ms = postmortem_result.processing_time_ms
        existing.generated_by_id = current_user.id
        postmortem = existing
    else:
        # Create new postmortem
        postmortem = Postmortem(
            incident_id=incident_id,
            generated_by_id=current_user.id,
            content=postmortem_result.content,
            model_name=postmortem_result.model_name,
            processing_time_ms=postmortem_result.processing_time_ms,
        )
        db.add(postmortem)

    # Record event
    event = IncidentEvent(
        incident_id=incident_id,
        event_type=IncidentEventType.POSTMORTEM,
        content=f"Postmortem {'regenerated' if not is_new else 'generated'} by AI",
        actor_id=current_user.id,
    )
    db.add(event)

    await db.commit()
    await db.refresh(postmortem)

    return PostmortemGenerateResponse(
        id=postmortem.id,
        incident_id=postmortem.incident_id,
        content=postmortem.content,
        model_name=postmortem.model_name,
        processing_time_ms=postmortem.processing_time_ms,
        is_new=is_new,
    )


@router.get(
    "/incidents/{incident_id}/postmortem",
    response_model=PostmortemResponse,
)
async def get_incident_postmortem(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PostmortemResponse:
    """Get the postmortem for an incident."""
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Get postmortem
    postmortem_result = await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )
    postmortem = postmortem_result.scalar_one_or_none()

    if postmortem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Postmortem not found. Generate one first.",
        )

    return PostmortemResponse(
        id=postmortem.id,
        incident_id=postmortem.incident_id,
        content=postmortem.content,
        model_name=postmortem.model_name,
        processing_time_ms=postmortem.processing_time_ms,
        created_at=postmortem.created_at,
        updated_at=postmortem.updated_at,
    )
