"""Tests for incident endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_incident_success(client: AsyncClient, auth_headers) -> None:
    """Test creating an incident successfully."""
    response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "Database connection timeout",
            "description": "Users experiencing slow queries and timeouts",
            "severity": "SEV-2",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Database connection timeout"
    assert data["description"] == "Users experiencing slow queries and timeouts"
    assert data["severity"] == "SEV-2"
    assert data["status"] == "open"
    assert "id" in data
    assert "created_at" in data
    assert len(data["events"]) == 1  # Created event


@pytest.mark.asyncio
async def test_create_incident_default_severity(client: AsyncClient, auth_headers) -> None:
    """Test creating an incident with default severity."""
    response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "Minor UI glitch",
            "description": "Button color is off",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["severity"] == "SEV-3"  # Default


@pytest.mark.asyncio
async def test_create_incident_unauthenticated(client: AsyncClient) -> None:
    """Test creating an incident without authentication."""
    response = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Test incident",
            "description": "Test description",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_incident_empty_title(client: AsyncClient, auth_headers) -> None:
    """Test creating an incident with empty title."""
    response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "",
            "description": "Valid description",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_incident_invalid_severity(client: AsyncClient, auth_headers) -> None:
    """Test creating an incident with invalid severity."""
    response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "Test incident",
            "description": "Test description",
            "severity": "INVALID",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_incidents_empty(client: AsyncClient, auth_headers) -> None:
    """Test listing incidents when none exist."""
    response = await client.get("/api/v1/incidents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_incidents(client: AsyncClient, auth_headers) -> None:
    """Test listing incidents."""
    # Create some incidents
    for i in range(3):
        await client.post(
            "/api/v1/incidents",
            headers=auth_headers,
            json={
                "title": f"Incident {i}",
                "description": f"Description {i}",
            },
        )

    response = await client.get("/api/v1/incidents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_incidents_with_status_filter(client: AsyncClient, auth_headers) -> None:
    """Test listing incidents with status filter."""
    # Create an open incident
    await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Open incident", "description": "Still open"},
    )

    # Create and resolve another incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Resolved incident", "description": "Already fixed"},
    )
    incident_id = create_response.json()["id"]

    # First transition to investigating
    await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "investigating"},
    )

    # Then resolve
    await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "resolved"},
    )

    # Filter by open status
    response = await client.get(
        "/api/v1/incidents?status=open",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Open incident"


@pytest.mark.asyncio
async def test_get_incident(client: AsyncClient, auth_headers) -> None:
    """Test getting a single incident."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "Test incident",
            "description": "Test description",
        },
    )
    incident_id = create_response.json()["id"]

    # Get the incident
    response = await client.get(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == incident_id
    assert data["title"] == "Test incident"


@pytest.mark.asyncio
async def test_get_incident_not_found(client: AsyncClient, auth_headers) -> None:
    """Test getting a non-existent incident."""
    response = await client.get("/api/v1/incidents/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_incident_title(client: AsyncClient, auth_headers) -> None:
    """Test updating incident title."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Original title", "description": "Description"},
    )
    incident_id = create_response.json()["id"]

    # Update the title
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"title": "Updated title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"


@pytest.mark.asyncio
async def test_update_incident_status_valid_transition(client: AsyncClient, auth_headers) -> None:
    """Test valid status transition."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test", "description": "Test"},
    )
    incident_id = create_response.json()["id"]

    # Open -> Investigating (valid)
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "investigating"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "investigating"
    # Check that status change event was created
    assert len(data["events"]) == 2


@pytest.mark.asyncio
async def test_update_incident_status_invalid_transition(client: AsyncClient, auth_headers) -> None:
    """Test invalid status transition."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test", "description": "Test"},
    )
    incident_id = create_response.json()["id"]

    # Open -> Monitoring (invalid - must go through investigating first)
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "monitoring"},
    )
    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_incident_resolved_sets_timestamp(client: AsyncClient, auth_headers) -> None:
    """Test that resolving incident sets resolved_at timestamp."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test", "description": "Test"},
    )
    incident_id = create_response.json()["id"]

    # Resolve it (open -> resolved is valid)
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "resolved"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_update_incident_severity_creates_event(client: AsyncClient, auth_headers) -> None:
    """Test that changing severity creates an event."""
    # Create an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test", "description": "Test", "severity": "SEV-3"},
    )
    incident_id = create_response.json()["id"]

    # Change severity
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"severity": "SEV-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["severity"] == "SEV-1"
    # Should have created event + severity change event
    assert len(data["events"]) == 2
    assert "severity" in data["events"][-1]["content"].lower()


@pytest.mark.asyncio
async def test_update_incident_not_found(client: AsyncClient, auth_headers) -> None:
    """Test updating a non-existent incident."""
    response = await client.patch(
        "/api/v1/incidents/99999",
        headers=auth_headers,
        json={"title": "New title"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resolved_incident_cannot_transition(client: AsyncClient, auth_headers) -> None:
    """Test that resolved incidents cannot transition to other states."""
    # Create and resolve an incident
    create_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test", "description": "Test"},
    )
    incident_id = create_response.json()["id"]

    await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "resolved"},
    )

    # Try to transition back to investigating
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_headers,
        json={"status": "investigating"},
    )
    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]
