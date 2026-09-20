"""Incident schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.incident import IncidentEventType, IncidentSeverity, IncidentStatus
from app.schemas.user import UserResponse


class IncidentCreate(BaseModel):
    """Request schema for creating an incident."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    severity: IncidentSeverity = IncidentSeverity.SEV3


class IncidentUpdate(BaseModel):
    """Request schema for updating an incident."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None


class IncidentEventResponse(BaseModel):
    """Response schema for incident events."""

    id: int
    incident_id: int
    event_type: IncidentEventType
    content: str
    actor_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    """Response schema for incident data."""

    id: int
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    owner_id: int
    created_at: datetime
    resolved_at: datetime | None
    owner: UserResponse
    events: list[IncidentEventResponse] = []

    model_config = {"from_attributes": True}


class IncidentListItem(BaseModel):
    """Response schema for incident list items (without events)."""

    id: int
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    owner_id: int
    created_at: datetime
    resolved_at: datetime | None
    owner: UserResponse

    model_config = {"from_attributes": True}


class IncidentsListResponse(BaseModel):
    """Response schema for list of incidents."""

    items: list[IncidentListItem]
    total: int
