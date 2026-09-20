"""Dashboard routes."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import extract, func, select

from app.core.deps import CurrentUser, DbSession
from app.models.incident import Incident, IncidentStatus
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    SeverityCount,
    StatusCount,
)

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: DbSession,
    current_user: CurrentUser,
) -> DashboardResponse:
    """Get dashboard statistics.

    Returns:
        - Active incidents count (not resolved)
        - Resolved incidents this month
        - Average resolution time in hours
        - Total incidents count
        - Breakdown by severity
        - Breakdown by status
    """
    now = datetime.now(UTC)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Active incidents (not resolved)
    active_result = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.status != IncidentStatus.RESOLVED)
    )
    active_incidents = active_result.scalar() or 0

    # Resolved this month
    resolved_month_result = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.status == IncidentStatus.RESOLVED,
            Incident.resolved_at >= current_month_start,
        )
    )
    resolved_this_month = resolved_month_result.scalar() or 0

    # Average resolution time (for resolved incidents)
    # Calculate as average of (resolved_at - created_at) in hours
    avg_time_result = await db.execute(
        select(
            func.avg(
                extract(
                    "epoch",
                    Incident.resolved_at - Incident.created_at,
                )
                / 3600  # Convert seconds to hours
            )
        )
        .select_from(Incident)
        .where(
            Incident.status == IncidentStatus.RESOLVED,
            Incident.resolved_at.isnot(None),
        )
    )
    avg_resolution_time = avg_time_result.scalar()
    if avg_resolution_time is not None:
        avg_resolution_time = round(float(avg_resolution_time), 2)

    # Total incidents
    total_result = await db.execute(select(func.count()).select_from(Incident))
    total_incidents = total_result.scalar() or 0

    # By severity
    severity_result = await db.execute(
        select(Incident.severity, func.count())
        .group_by(Incident.severity)
        .order_by(Incident.severity)
    )
    by_severity = []
    for row in severity_result.all():
        sev = row[0]
        # Handle both enum and string (SQLite stores as string)
        sev_value = sev.value if hasattr(sev, "value") else str(sev)
        by_severity.append(SeverityCount(severity=sev_value, count=row[1]))

    # By status
    status_result = await db.execute(
        select(Incident.status, func.count())
        .group_by(Incident.status)
        .order_by(Incident.status)
    )
    by_status = []
    for status_row in status_result.all():
        stat = status_row[0]
        # Handle both enum and string (SQLite stores as string)
        stat_value = stat.value if hasattr(stat, "value") else str(stat)
        by_status.append(StatusCount(status=stat_value, count=status_row[1]))

    return DashboardResponse(
        stats=DashboardStats(
            active_incidents=active_incidents,
            resolved_this_month=resolved_this_month,
            avg_resolution_time_hours=avg_resolution_time,
            total_incidents=total_incidents,
        ),
        by_severity=by_severity,
        by_status=by_status,
    )
