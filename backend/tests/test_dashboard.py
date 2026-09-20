"""Tests for dashboard endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_empty(client: AsyncClient, auth_headers) -> None:
    """Test dashboard with no incidents."""
    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["active_incidents"] == 0
    assert data["stats"]["resolved_this_month"] == 0
    assert data["stats"]["avg_resolution_time_hours"] is None
    assert data["stats"]["total_incidents"] == 0
    assert data["by_severity"] == []
    assert data["by_status"] == []


@pytest.mark.asyncio
async def test_dashboard_unauthenticated(client: AsyncClient) -> None:
    """Test dashboard without authentication."""
    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_with_incidents(client: AsyncClient, auth_headers) -> None:
    """Test dashboard with multiple incidents."""
    # Create incidents with different severities
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Critical", "description": "Critical issue", "severity": "SEV-1"},
    )
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Major", "description": "Major issue", "severity": "SEV-2"},
    )
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Minor", "description": "Minor issue", "severity": "SEV-3"},
    )

    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["active_incidents"] == 3
    assert data["stats"]["total_incidents"] == 3
    assert len(data["by_severity"]) == 3
    assert len(data["by_status"]) == 1  # All open


@pytest.mark.asyncio
async def test_dashboard_resolved_count(client: AsyncClient, auth_headers) -> None:
    """Test that resolved incidents are counted correctly."""
    # Create and resolve an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "To resolve", "description": "Will be resolved"},
    )
    incident_id = create_response.json()["id"]

    await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "resolved"},
    )

    # Create an open incident
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Still open", "description": "Not resolved"},
    )

    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["active_incidents"] == 1
    assert data["stats"]["resolved_this_month"] == 1
    assert data["stats"]["total_incidents"] == 2


@pytest.mark.asyncio
async def test_dashboard_resolution_time(client: AsyncClient, auth_headers) -> None:
    """Test average resolution time calculation."""
    # Create and immediately resolve an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Quick fix", "description": "Fixed quickly"},
    )
    incident_id = create_response.json()["id"]

    await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "resolved"},
    )

    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # Resolution time should be very small (less than 1 hour for immediate resolution)
    assert data["stats"]["avg_resolution_time_hours"] is not None
    assert data["stats"]["avg_resolution_time_hours"] < 1.0


@pytest.mark.asyncio
async def test_dashboard_by_status_breakdown(client: AsyncClient, auth_headers) -> None:
    """Test status breakdown in dashboard."""
    # Create an open incident
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Open", "description": "Still open"},
    )

    # Create and move one to investigating
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Investigating", "description": "Under investigation"},
    )
    await client.patch(
        f"/api/v1/incidents/{create_response.json()['id']}",
        headers=auth_headers,
        json={"status": "investigating"},
    )

    response = await client.get("/api/v1/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    statuses = {item["status"]: item["count"] for item in data["by_status"]}
    assert statuses.get("open", 0) == 1
    assert statuses.get("investigating", 0) == 1
