"""Dashboard schemas."""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Response schema for dashboard statistics."""

    active_incidents: int
    resolved_this_month: int
    avg_resolution_time_hours: float | None  # None if no resolved incidents
    total_incidents: int


class SeverityCount(BaseModel):
    """Count of incidents by severity."""

    severity: str
    count: int


class StatusCount(BaseModel):
    """Count of incidents by status."""

    status: str
    count: int


class DashboardResponse(BaseModel):
    """Full dashboard response."""

    stats: DashboardStats
    by_severity: list[SeverityCount]
    by_status: list[StatusCount]
