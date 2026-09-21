"""Tests for document endpoints."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_document_success(client: AsyncClient, auth_headers) -> None:
    """Test successful document upload."""
    content = "This is a test document with some content."
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Test Document", "document_type": "doc"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document"]["title"] == "Test Document"
    assert data["document"]["document_type"] == "doc"
    assert data["document"]["filename"] == "test.txt"
    assert data["document"]["chunk_count"] >= 1
    assert "uploaded successfully" in data["message"]


@pytest.mark.asyncio
async def test_upload_document_with_incident(client: AsyncClient, auth_headers) -> None:
    """Test uploading document attached to an incident."""
    # First create an incident
    incident_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Test Incident", "description": "For document test"},
    )
    incident_id = incident_response.json()["id"]

    # Upload document with incident_id
    content = "Runbook content for incident"
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("runbook.md", file, "text/markdown")},
        data={
            "title": "Incident Runbook",
            "document_type": "runbook",
            "incident_id": str(incident_id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document"]["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_upload_document_invalid_incident(client: AsyncClient, auth_headers) -> None:
    """Test uploading document with non-existent incident."""
    content = "Test content"
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={
            "title": "Test",
            "document_type": "doc",
            "incident_id": "99999",
        },
    )
    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: AsyncClient, auth_headers) -> None:
    """Test uploading unsupported file type."""
    content = b"binary data"
    file = io.BytesIO(content)

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.exe", file, "application/octet-stream")},
        data={"title": "Test", "document_type": "doc"},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient, auth_headers) -> None:
    """Test uploading empty file."""
    file = io.BytesIO(b"")

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("empty.txt", file, "text/plain")},
        data={"title": "Empty", "document_type": "doc"},
    )
    assert response.status_code == 400
    assert "Empty file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_large_file_chunking(client: AsyncClient, auth_headers) -> None:
    """Test that large files are properly chunked."""
    # Create a file large enough to require multiple chunks
    lines = [f"Log line {i}: " + "x" * 100 for i in range(200)]
    content = "\n".join(lines)
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("large.log", file, "text/plain")},
        data={"title": "Large Log", "document_type": "log"},
    )
    assert response.status_code == 201
    data = response.json()
    # Should have multiple chunks
    assert data["document"]["chunk_count"] > 1


@pytest.mark.asyncio
async def test_upload_markdown_file(client: AsyncClient, auth_headers) -> None:
    """Test uploading markdown file."""
    content = """# Runbook: Database Recovery

## Prerequisites
- Access to production database
- Admin credentials

## Steps
1. Stop the application
2. Run backup script
3. Restore from snapshot
"""
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("runbook.md", file, "text/markdown")},
        data={"title": "DB Recovery Runbook", "document_type": "runbook"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["mime_type"] == "text/markdown"


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient, auth_headers) -> None:
    """Test listing documents when none exist."""
    response = await client.get("/api/v1/documents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, auth_headers) -> None:
    """Test listing documents."""
    # Upload some documents
    for i in range(3):
        content = f"Document {i} content"
        file = io.BytesIO(content.encode())
        await client.post(
            "/api/v1/documents",
            headers=auth_headers,
            files={"file": (f"doc{i}.txt", file, "text/plain")},
            data={"title": f"Document {i}", "document_type": "doc"},
        )

    response = await client.get("/api/v1/documents", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_documents_filter_by_incident(client: AsyncClient, auth_headers) -> None:
    """Test filtering documents by incident."""
    # Create incident
    incident_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Filter Test", "description": "Test"},
    )
    incident_id = incident_response.json()["id"]

    # Upload document attached to incident
    file1 = io.BytesIO(b"Attached document")
    await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("attached.txt", file1, "text/plain")},
        data={"title": "Attached", "document_type": "doc", "incident_id": str(incident_id)},
    )

    # Upload document not attached
    file2 = io.BytesIO(b"Standalone document")
    await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("standalone.txt", file2, "text/plain")},
        data={"title": "Standalone", "document_type": "doc"},
    )

    # Filter by incident
    response = await client.get(
        f"/api/v1/documents?incident_id={incident_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Attached"


@pytest.mark.asyncio
async def test_list_documents_filter_by_type(client: AsyncClient, auth_headers) -> None:
    """Test filtering documents by type."""
    # Upload runbook
    file1 = io.BytesIO(b"Runbook content")
    await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("runbook.md", file1, "text/markdown")},
        data={"title": "Runbook", "document_type": "runbook"},
    )

    # Upload log
    file2 = io.BytesIO(b"Log content")
    await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("app.log", file2, "text/plain")},
        data={"title": "App Log", "document_type": "log"},
    )

    # Filter by type
    response = await client.get(
        "/api/v1/documents?document_type=runbook",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["document_type"] == "runbook"


@pytest.mark.asyncio
async def test_get_document_with_chunks(client: AsyncClient, auth_headers) -> None:
    """Test getting a document with all its chunks."""
    content = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
    file = io.BytesIO(content.encode())

    upload_response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Test Doc", "document_type": "doc"},
    )
    doc_id = upload_response.json()["document"]["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert "chunks" in data
    assert len(data["chunks"]) >= 1
    # Verify chunk structure
    chunk = data["chunks"][0]
    assert "content" in chunk
    assert "chunk_index" in chunk
    assert "token_count" in chunk


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, auth_headers) -> None:
    """Test getting non-existent document."""
    response = await client.get("/api/v1/documents/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_attach_document_to_incident(client: AsyncClient, auth_headers) -> None:
    """Test attaching existing document to incident."""
    # Upload standalone document
    file = io.BytesIO(b"Document content")
    upload_response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Standalone", "document_type": "doc"},
    )
    doc_id = upload_response.json()["document"]["id"]
    assert upload_response.json()["document"]["incident_id"] is None

    # Create incident
    incident_response = await client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={"title": "Attach Test", "description": "Test"},
    )
    incident_id = incident_response.json()["id"]

    # Attach document
    response = await client.post(
        f"/api/v1/documents/{doc_id}/attach",
        headers=auth_headers,
        json={"incident_id": incident_id},
    )
    assert response.status_code == 200
    assert response.json()["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_attach_document_invalid_incident(client: AsyncClient, auth_headers) -> None:
    """Test attaching document to non-existent incident."""
    file = io.BytesIO(b"Content")
    upload_response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Test", "document_type": "doc"},
    )
    doc_id = upload_response.json()["document"]["id"]

    response = await client.post(
        f"/api/v1/documents/{doc_id}/attach",
        headers=auth_headers,
        json={"incident_id": 99999},
    )
    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient, auth_headers) -> None:
    """Test deleting a document."""
    file = io.BytesIO(b"To be deleted")
    upload_response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("delete.txt", file, "text/plain")},
        data={"title": "Delete Me", "document_type": "doc"},
    )
    doc_id = upload_response.json()["document"]["id"]

    # Delete
    response = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify deleted
    get_response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_not_found(client: AsyncClient, auth_headers) -> None:
    """Test deleting non-existent document."""
    response = await client.delete("/api/v1/documents/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_unauthenticated(client: AsyncClient) -> None:
    """Test uploading without authentication."""
    file = io.BytesIO(b"Content")
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Test", "document_type": "doc"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_yaml_file(client: AsyncClient, auth_headers) -> None:
    """Test uploading YAML configuration file."""
    content = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  database_url: postgres://localhost:5432/db
"""
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("config.yaml", file, "text/yaml")},
        data={"title": "App Config", "document_type": "doc"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["mime_type"] == "text/yaml"


@pytest.mark.asyncio
async def test_upload_python_file(client: AsyncClient, auth_headers) -> None:
    """Test uploading Python source file."""
    content = '''def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
'''
    file = io.BytesIO(content.encode())

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("script.py", file, "text/x-python")},
        data={"title": "Python Script", "document_type": "doc"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_embed_document_not_found(client: AsyncClient, auth_headers) -> None:
    """Test embedding non-existent document."""
    response = await client.post("/api/v1/documents/99999/embed", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_documents_pagination(client: AsyncClient, auth_headers) -> None:
    """Test document listing with pagination."""
    # Upload multiple documents
    for i in range(5):
        file = io.BytesIO(f"Document {i}".encode())
        await client.post(
            "/api/v1/documents",
            headers=auth_headers,
            files={"file": (f"doc{i}.txt", file, "text/plain")},
            data={"title": f"Doc {i}", "document_type": "doc"},
        )

    # Get first page
    response = await client.get(
        "/api/v1/documents?limit=2&offset=0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5

    # Get second page
    response = await client.get(
        "/api/v1/documents?limit=2&offset=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_upload_document_missing_title(client: AsyncClient, auth_headers) -> None:
    """Test uploading document without title."""
    file = io.BytesIO(b"Content")
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"document_type": "doc"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_document_invalid_type(client: AsyncClient, auth_headers) -> None:
    """Test uploading document with invalid document_type."""
    file = io.BytesIO(b"Content")
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", file, "text/plain")},
        data={"title": "Test", "document_type": "invalid"},
    )
    assert response.status_code == 422
