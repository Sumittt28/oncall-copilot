"""Analytics API routes."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.investigation import AIInvestigation

router = APIRouter()


# ============== Schemas ==============


class IncidentTrend(BaseModel):
    """Incident count for a time period."""

    date: str
    count: int
    resolved: int


class SeverityDistribution(BaseModel):
    """Incident count by severity."""

    severity: str
    count: int
    percentage: float


class TopRootCause(BaseModel):
    """Top root cause from AI investigations."""

    cause: str
    count: int
    avg_confidence: float


class ResolutionStats(BaseModel):
    """Resolution time statistics."""

    avg_resolution_hours: float
    median_resolution_hours: float
    min_resolution_hours: float
    max_resolution_hours: float


class AnalyticsResponse(BaseModel):
    """Complete analytics response."""

    total_incidents: int
    active_incidents: int
    resolved_incidents: int
    avg_resolution_hours: float
    incidents_by_day: list[IncidentTrend]
    severity_distribution: list[SeverityDistribution]
    top_root_causes: list[TopRootCause]
    resolution_stats: ResolutionStats | None


class IncidentsByDayResponse(BaseModel):
    """Incidents by day response."""

    items: list[IncidentTrend]
    total_days: int


# ============== Endpoints ==============


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
) -> AnalyticsResponse:
    """Get comprehensive analytics data.

    Returns incident trends, severity distribution, top root causes,
    and resolution statistics.
    """
    # Calculate date range
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    # Get all incidents in range
    result = await db.execute(
        select(Incident).where(Incident.created_at >= start_date)
    )
    incidents = result.scalars().all()

    total_incidents = len(incidents)
    active_incidents = sum(1 for i in incidents if i.status != IncidentStatus.RESOLVED)
    resolved_incidents = sum(1 for i in incidents if i.status == IncidentStatus.RESOLVED)

    # Calculate average resolution time
    resolution_times = []
    for incident in incidents:
        if incident.resolved_at and incident.created_at:
            delta = incident.resolved_at - incident.created_at
            resolution_times.append(delta.total_seconds() / 3600)

    avg_resolution_hours = (
        sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
    )

    # Get incidents by day
    incidents_by_day = await _get_incidents_by_day(db, start_date, end_date)

    # Get severity distribution
    severity_distribution = await _get_severity_distribution(db, start_date)

    # Get top root causes
    top_root_causes = await _get_top_root_causes(db, start_date, limit=5)

    # Get resolution stats
    resolution_stats = None
    if resolution_times:
        sorted_times = sorted(resolution_times)
        median_idx = len(sorted_times) // 2
        resolution_stats = ResolutionStats(
            avg_resolution_hours=avg_resolution_hours,
            median_resolution_hours=sorted_times[median_idx],
            min_resolution_hours=min(resolution_times),
            max_resolution_hours=max(resolution_times),
        )

    return AnalyticsResponse(
        total_incidents=total_incidents,
        active_incidents=active_incidents,
        resolved_incidents=resolved_incidents,
        avg_resolution_hours=round(avg_resolution_hours, 2),
        incidents_by_day=incidents_by_day,
        severity_distribution=severity_distribution,
        top_root_causes=top_root_causes,
        resolution_stats=resolution_stats,
    )


@router.get("/analytics/incidents-by-day", response_model=IncidentsByDayResponse)
async def get_incidents_by_day(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(30, ge=7, le=365),
) -> IncidentsByDayResponse:
    """Get incident counts by day."""
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    items = await _get_incidents_by_day(db, start_date, end_date)

    return IncidentsByDayResponse(
        items=items,
        total_days=days,
    )


@router.get("/analytics/severity-distribution", response_model=list[SeverityDistribution])
async def get_severity_distribution(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(30, ge=7, le=365),
) -> list[SeverityDistribution]:
    """Get incident distribution by severity."""
    start_date = datetime.now(UTC) - timedelta(days=days)
    return await _get_severity_distribution(db, start_date)


@router.get("/analytics/top-root-causes", response_model=list[TopRootCause])
async def get_top_root_causes(
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
) -> list[TopRootCause]:
    """Get top root causes from AI investigations."""
    start_date = datetime.now(UTC) - timedelta(days=days)
    return await _get_top_root_causes(db, start_date, limit)


# ============== Helper Functions ==============


async def _get_incidents_by_day(
    db: DbSession,
    start_date: datetime,
    end_date: datetime,
) -> list[IncidentTrend]:
    """Get incident counts grouped by day."""
    # Get all incidents in range
    result = await db.execute(
        select(Incident).where(
            Incident.created_at >= start_date,
            Incident.created_at <= end_date,
        )
    )
    incidents = result.scalars().all()

    # Group by day
    day_counts: dict[str, dict[str, int]] = {}
    current = start_date.date()
    end = end_date.date()

    # Initialize all days with 0
    while current <= end:
        day_str = current.isoformat()
        day_counts[day_str] = {"count": 0, "resolved": 0}
        current += timedelta(days=1)

    # Count incidents
    for incident in incidents:
        day_str = incident.created_at.date().isoformat()
        if day_str in day_counts:
            day_counts[day_str]["count"] += 1
            if incident.status == IncidentStatus.RESOLVED:
                day_counts[day_str]["resolved"] += 1

    return [
        IncidentTrend(
            date=day,
            count=counts["count"],
            resolved=counts["resolved"],
        )
        for day, counts in sorted(day_counts.items())
    ]


async def _get_severity_distribution(
    db: DbSession,
    start_date: datetime,
) -> list[SeverityDistribution]:
    """Get incident distribution by severity."""
    result = await db.execute(
        select(Incident).where(Incident.created_at >= start_date)
    )
    incidents = result.scalars().all()

    total = len(incidents)
    if total == 0:
        return []

    # Count by severity
    severity_counts: dict[str, int] = {}
    for severity in IncidentSeverity:
        severity_counts[severity.value] = 0

    for incident in incidents:
        sev = incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity)
        if sev in severity_counts:
            severity_counts[sev] += 1

    return [
        SeverityDistribution(
            severity=severity,
            count=count,
            percentage=round(count / total * 100, 1) if total > 0 else 0,
        )
        for severity, count in sorted(severity_counts.items())
    ]


async def _get_top_root_causes(
    db: DbSession,
    start_date: datetime,
    limit: int = 5,
) -> list[TopRootCause]:
    """Extract top root causes from AI investigations."""
    result = await db.execute(
        select(AIInvestigation).where(AIInvestigation.created_at >= start_date)
    )
    investigations = result.scalars().all()

    # Aggregate causes
    cause_stats: dict[str, dict[str, Any]] = {}

    for inv in investigations:
        from typing import cast
        structured: dict[str, Any] = cast(dict[str, Any], inv.structured_output)
        for cause_data in structured.get("possible_causes", []):
            cause_text = cause_data.get("cause", "")[:100]  # Truncate
            confidence = cause_data.get("confidence", 0)

            if cause_text:
                if cause_text not in cause_stats:
                    cause_stats[cause_text] = {"count": 0, "total_confidence": 0}
                cause_stats[cause_text]["count"] += 1
                cause_stats[cause_text]["total_confidence"] += confidence

    # Sort by count and get top N
    sorted_causes = sorted(
        cause_stats.items(),
        key=lambda x: x[1]["count"],
        reverse=True,
    )[:limit]

    return [
        TopRootCause(
            cause=cause,
            count=stats["count"],
            avg_confidence=round(stats["total_confidence"] / stats["count"], 2),
        )
        for cause, stats in sorted_causes
    ]
