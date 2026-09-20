"""Incident management routes."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import (
    Incident,
    IncidentEvent,
    IncidentEventType,
    IncidentSeverity,
    IncidentStatus,
    is_valid_status_transition,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentListItem,
    IncidentResponse,
    IncidentsListResponse,
    IncidentUpdate,
)

router = APIRouter()


def get_enum_value(val: Any) -> str:
    """Get the value from an enum or return string as-is.

    SQLite stores enums as strings, PostgreSQL as enum values.
    """
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    request: IncidentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """Create a new incident.

    The current user becomes the owner of the incident.
    """
    incident = Incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        owner_id=current_user.id,
    )
    db.add(incident)
    await db.flush()

    # Create initial event
    event = IncidentEvent(
        incident_id=incident.id,
        event_type=IncidentEventType.CREATED,
        content=f"Incident created with severity {request.severity.value}",
        actor_id=current_user.id,
    )
    db.add(event)
    await db.flush()

    # Refresh to load relationships
    await db.refresh(incident)
    return incident


@router.get("", response_model=IncidentsListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> IncidentsListResponse:
    """List all incidents with optional filtering.

    Supports pagination and status filtering.
    """
    # Base query
    query = select(Incident).order_by(Incident.created_at.desc())

    # Apply status filter if provided
    if status_filter:
        query = query.where(Incident.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Incident)
    if status_filter:
        count_query = count_query.where(Incident.status == status_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    incidents = result.scalars().all()

    return IncidentsListResponse(
        items=[IncidentListItem.model_validate(i) for i in incidents],
        total=total,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """Get a specific incident by ID."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    request: IncidentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """Update an incident.

    Validates status transitions to prevent invalid state changes.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Track changes for events
    events_to_create: list[IncidentEvent] = []

    # Update fields if provided
    if request.title is not None:
        incident.title = request.title

    if request.description is not None:
        incident.description = request.description

    # Normalize current values (SQLite stores as string, Postgres as enum)
    current_severity = (
        incident.severity
        if isinstance(incident.severity, IncidentSeverity)
        else IncidentSeverity(incident.severity)
    )
    current_status = (
        incident.status
        if isinstance(incident.status, IncidentStatus)
        else IncidentStatus(incident.status)
    )

    if request.severity is not None and request.severity != current_severity:
        old_severity = current_severity
        incident.severity = request.severity
        events_to_create.append(
            IncidentEvent(
                incident_id=incident.id,
                event_type=IncidentEventType.SEVERITY_CHANGE,
                content=f"Severity changed from {old_severity.value} to {request.severity.value}",
                actor_id=current_user.id,
            )
        )

    if request.status is not None and request.status != current_status:
        # Validate status transition
        if not is_valid_status_transition(current_status, request.status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {current_status.value} to {request.status.value}",
            )

        old_status = current_status
        incident.status = request.status

        # Set resolved_at if transitioning to resolved
        if request.status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(UTC)

        events_to_create.append(
            IncidentEvent(
                incident_id=incident.id,
                event_type=IncidentEventType.STATUS_CHANGE,
                content=f"Status changed from {old_status.value} to {request.status.value}",
                actor_id=current_user.id,
            )
        )

    # Create events
    for event in events_to_create:
        db.add(event)

    await db.flush()
    await db.refresh(incident)
    return incident
