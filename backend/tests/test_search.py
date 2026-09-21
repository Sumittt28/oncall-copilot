"""Tests for search API endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_unauthenticated(client: AsyncClient) -> None:
    """Test search without authentication."""
    response = await client.get("/api/v1/search?q=test")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_missing_query(client: AsyncClient, auth_headers) -> None:
    """Test search without query parameter."""
    response = await client.get("/api/v1/search", headers=auth_headers)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_empty_query(client: AsyncClient, auth_headers) -> None:
    """Test search with empty query parameter."""
    response = await client.get("/api/v1/search?q=", headers=auth_headers)
    assert response.status_code == 422  # min_length=1


@pytest.mark.asyncio
async def test_search_invalid_limit(client: AsyncClient, auth_headers) -> None:
    """Test search with invalid limit parameter."""
    response = await client.get(
        "/api/v1/search?q=test&limit=100",
        headers=auth_headers,
    )
    assert response.status_code == 422  # limit max is 50


@pytest.mark.asyncio
async def test_search_invalid_similarity(client: AsyncClient, auth_headers) -> None:
    """Test search with invalid similarity parameter."""
    response = await client.get(
        "/api/v1/search?q=test&min_similarity=1.5",
        headers=auth_headers,
    )
    assert response.status_code == 422  # max is 1.0


# Note: Full integration tests for semantic search require PostgreSQL with pgvector
# The following tests verify the endpoint structure and parameters only
