"""Tests for health check and API availability."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint is accessible without auth."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_openapi_available(client: AsyncClient) -> None:
    """Test OpenAPI schema is accessible."""
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "OnCall Copilot"


@pytest.mark.asyncio
async def test_docs_available(client: AsyncClient) -> None:
    """Test Swagger docs are accessible."""
    response = await client.get("/api/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redoc_available(client: AsyncClient) -> None:
    """Test ReDoc is accessible."""
    response = await client.get("/api/redoc")
    assert response.status_code == 200
