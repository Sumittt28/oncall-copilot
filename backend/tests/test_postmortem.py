"""Tests for postmortem generation."""

import pytest
from httpx import AsyncClient

from app.models.incident import Incident, IncidentSeverity, IncidentStatus


@pytest.mark.asyncio
async def test_generate_postmortem_unauthenticated(client: AsyncClient) -> None:
    """Test postmortem generation requires authentication."""
    response = await client.post("/api/v1/incidents/1/postmortem")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_postmortem_incident_not_found(
    client: AsyncClient, auth_headers
) -> None:
    """Test postmortem generation with non-existent incident."""
    response = await client.post(
        "/api/v1/incidents/99999/postmortem",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_postmortem_unresolved_incident(
    client: AsyncClient, auth_headers, db_session
) -> None:
    """Test postmortem generation fails for unresolved incident."""
    from app.core.security import hash_password
    from app.models.user import User

    # Create user
    user = User(
        email="pm_test@example.com",
        hashed_password=hash_password("testpassword"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()

    # Create unresolved incident
    incident = Incident(
        title="Unresolved Incident",
        description="This incident is not resolved",
        severity=IncidentSeverity.SEV3,
        status=IncidentStatus.INVESTIGATING,
        owner_id=user.id,
    )
    db_session.add(incident)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/incidents/{incident.id}/postmortem",
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "unresolved" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_postmortem_not_found(
    client: AsyncClient, auth_headers, db_session
) -> None:
    """Test getting postmortem that doesn't exist."""
    from datetime import UTC, datetime

    from app.core.security import hash_password
    from app.models.user import User

    # Create user
    user = User(
        email="pm_get_test@example.com",
        hashed_password=hash_password("testpassword"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()

    # Create resolved incident without postmortem
    incident = Incident(
        title="Resolved Incident",
        description="This incident is resolved",
        severity=IncidentSeverity.SEV3,
        status=IncidentStatus.RESOLVED,
        owner_id=user.id,
        resolved_at=datetime.now(UTC),
    )
    db_session.add(incident)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/incidents/{incident.id}/postmortem",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_postmortem_incident_not_found(
    client: AsyncClient, auth_headers
) -> None:
    """Test getting postmortem for non-existent incident."""
    response = await client.get(
        "/api/v1/incidents/99999/postmortem",
        headers=auth_headers,
    )
    assert response.status_code == 404
