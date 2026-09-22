"""Tests for analytics API."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.incident import Incident, IncidentSeverity, IncidentStatus


@pytest.mark.asyncio
async def test_analytics_unauthenticated(client: AsyncClient) -> None:
    """Test analytics requires authentication."""
    response = await client.get("/api/v1/analytics")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_analytics_empty(client: AsyncClient, auth_headers) -> None:
    """Test analytics with no incidents."""
    response = await client.get("/api/v1/analytics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_incidents"] == 0
    assert data["active_incidents"] == 0
    assert data["resolved_incidents"] == 0
    assert data["avg_resolution_hours"] == 0


@pytest.mark.asyncio
async def test_analytics_with_incidents(
    client: AsyncClient, auth_headers, db_session
) -> None:
    """Test analytics with some incidents."""
    from app.core.security import hash_password
    from app.models.user import User

    # Create user
    user = User(
        email="analytics_test@example.com",
        hashed_password=hash_password("testpassword"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(UTC)

    # Create incidents with different severities and statuses
    incidents = [
        Incident(
            title="SEV-1 Incident",
            description="Critical incident",
            severity=IncidentSeverity.SEV1,
            status=IncidentStatus.RESOLVED,
            owner_id=user.id,
            created_at=now - timedelta(hours=5),
            resolved_at=now - timedelta(hours=3),
        ),
        Incident(
            title="SEV-2 Incident",
            description="Major incident",
            severity=IncidentSeverity.SEV2,
            status=IncidentStatus.INVESTIGATING,
            owner_id=user.id,
            created_at=now - timedelta(hours=2),
        ),
        Incident(
            title="SEV-3 Incident",
            description="Minor incident",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.RESOLVED,
            owner_id=user.id,
            created_at=now - timedelta(hours=10),
            resolved_at=now - timedelta(hours=8),
        ),
    ]

    for incident in incidents:
        db_session.add(incident)
    await db_session.commit()

    response = await client.get("/api/v1/analytics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_incidents"] == 3
    assert data["active_incidents"] == 1
    assert data["resolved_incidents"] == 2
    assert data["avg_resolution_hours"] == 2.0  # (2 + 2) / 2


@pytest.mark.asyncio
async def test_analytics_severity_distribution(
    client: AsyncClient, auth_headers, db_session
) -> None:
    """Test severity distribution endpoint."""
    from app.core.security import hash_password
    from app.models.user import User

    # Create user
    user = User(
        email="sev_dist_test@example.com",
        hashed_password=hash_password("testpassword"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()

    # Create incidents with different severities
    for sev in [IncidentSeverity.SEV1, IncidentSeverity.SEV2, IncidentSeverity.SEV2]:
        incident = Incident(
            title=f"{sev.value} Incident",
            description="Test incident",
            severity=sev,
            status=IncidentStatus.OPEN,
            owner_id=user.id,
        )
        db_session.add(incident)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/severity-distribution",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should have all 4 severity levels
    assert len(data) == 4

    # Find SEV-2 (should have 2 incidents)
    sev2 = next((s for s in data if s["severity"] == "SEV-2"), None)
    assert sev2 is not None
    assert sev2["count"] == 2


@pytest.mark.asyncio
async def test_analytics_incidents_by_day(
    client: AsyncClient, auth_headers
) -> None:
    """Test incidents by day endpoint."""
    response = await client.get(
        "/api/v1/analytics/incidents-by-day?days=7",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["total_days"] == 7
    assert len(data["items"]) == 8  # 7 days + today


@pytest.mark.asyncio
async def test_analytics_top_root_causes_empty(
    client: AsyncClient, auth_headers
) -> None:
    """Test top root causes with no investigations."""
    response = await client.get(
        "/api/v1/analytics/top-root-causes",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data == []


@pytest.mark.asyncio
async def test_analytics_invalid_days_param(
    client: AsyncClient, auth_headers
) -> None:
    """Test analytics with invalid days parameter."""
    # Too few days
    response = await client.get(
        "/api/v1/analytics?days=1",
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Too many days
    response = await client.get(
        "/api/v1/analytics?days=1000",
        headers=auth_headers,
    )
    assert response.status_code == 422
