"""Tests for GitHub integration."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.services.github.client import (
    GitHubClient,
    GitHubCommit,
    GitHubError,
)
from app.services.github.correlation import (
    CommitCorrelation,
    calculate_commit_relevance,
)


class TestGitHubClient:
    """Tests for GitHubClient."""

    @pytest.mark.asyncio
    async def test_client_context_manager(self) -> None:
        """Test client can be used as context manager."""
        async with GitHubClient("test_token") as client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self) -> None:
        """Test error when client used without context manager."""
        client = GitHubClient("test_token")
        with pytest.raises(GitHubError, match="Client not initialized"):
            await client._request("GET", "/test")


class TestCommitCorrelation:
    """Tests for commit correlation."""

    def test_evidence_id_format(self) -> None:
        """Test evidence ID format for commits."""
        commit = GitHubCommit(
            sha="abc123def456",
            message="Fix database connection",
            author_name="Test User",
            author_email="test@example.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/owner/repo/commit/abc123def456",
            files_changed=["db.py"],
        )

        correlation = CommitCorrelation(
            commit=commit,
            minutes_before_incident=30,
            relevance_score=0.75,
            correlation_reason="Committed shortly before incident",
        )

        assert correlation.evidence_id == "commit-abc123d"
        assert "abc123d" in correlation.evidence_content
        assert "Fix database connection" in correlation.evidence_content
        assert "30 minutes" in correlation.evidence_content

    def test_evidence_content_with_files(self) -> None:
        """Test evidence content includes file information."""
        commit = GitHubCommit(
            sha="abc123def456",
            message="Update config\n\nDetailed description",
            author_name="Test User",
            author_email="test@example.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/owner/repo/commit/abc123def456",
            files_changed=["config.yaml", "deployment.yaml", "app.py"],
        )

        correlation = CommitCorrelation(
            commit=commit,
            minutes_before_incident=15,
            relevance_score=0.9,
            correlation_reason="Committed immediately before incident",
        )

        content = correlation.evidence_content
        assert "config.yaml" in content
        assert "deployment.yaml" in content
        assert "app.py" in content

    def test_evidence_content_truncates_many_files(self) -> None:
        """Test evidence content truncates when many files changed."""
        commit = GitHubCommit(
            sha="abc123def456",
            message="Large refactor",
            author_name="Test User",
            author_email="test@example.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/owner/repo/commit/abc123def456",
            files_changed=[f"file{i}.py" for i in range(10)],
        )

        correlation = CommitCorrelation(
            commit=commit,
            minutes_before_incident=45,
            relevance_score=0.6,
            correlation_reason="Committed within window",
        )

        content = correlation.evidence_content
        assert "+5 more" in content


class TestCalculateCommitRelevance:
    """Tests for relevance calculation."""

    def test_closer_commits_more_relevant(self) -> None:
        """Test that commits closer to incident are more relevant."""
        commit = GitHubCommit(
            sha="abc123",
            message="Some change",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        incident = MagicMock()
        incident.title = "Database error"
        incident.description = "Connection timeout"

        # Commit 5 minutes before should be more relevant than 55 minutes
        relevance_5min = calculate_commit_relevance(commit, incident, 5, 60)
        relevance_55min = calculate_commit_relevance(commit, incident, 55, 60)

        assert relevance_5min > relevance_55min

    def test_keyword_matching_increases_relevance(self) -> None:
        """Test that keyword matches increase relevance."""
        commit = GitHubCommit(
            sha="abc123",
            message="Fix database connection timeout",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        incident = MagicMock()
        incident.title = "Database timeout"
        incident.description = "Connection issues"

        relevance_matching = calculate_commit_relevance(commit, incident, 30, 60)

        # Change commit message to not match
        commit_no_match = GitHubCommit(
            sha="def456",
            message="Update README",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        relevance_no_match = calculate_commit_relevance(commit_no_match, incident, 30, 60)

        assert relevance_matching > relevance_no_match

    def test_config_files_increase_relevance(self) -> None:
        """Test that config/deploy files increase relevance."""
        commit_config = GitHubCommit(
            sha="abc123",
            message="Update config",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=["config.yaml", "deployment.yaml"],
        )

        commit_normal = GitHubCommit(
            sha="def456",
            message="Update code",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=["app.py", "utils.py"],
        )

        incident = MagicMock()
        incident.title = "Service error"
        incident.description = "Something broke"

        relevance_config = calculate_commit_relevance(commit_config, incident, 30, 60)
        relevance_normal = calculate_commit_relevance(commit_normal, incident, 30, 60)

        assert relevance_config > relevance_normal


class TestRepositoryEndpoints:
    """Tests for repository API endpoints."""

    @pytest.mark.asyncio
    async def test_list_repositories_unauthenticated(self, client: AsyncClient) -> None:
        """Test listing repositories without authentication."""
        response = await client.get("/api/v1/repositories")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_repositories_empty(self, client: AsyncClient, auth_headers) -> None:
        """Test listing repositories when none connected."""
        response = await client.get("/api/v1/repositories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_connect_repository_invalid_name(
        self, client: AsyncClient, auth_headers
    ) -> None:
        """Test connecting repository with invalid name format."""
        response = await client.post(
            "/api/v1/repositories",
            headers=auth_headers,
            json={
                "github_full_name": "invalid-name",  # Missing /
                "access_token": "test_token_12345",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_correlated_commits_incident_not_found(
        self, client: AsyncClient, auth_headers
    ) -> None:
        """Test getting correlated commits for non-existent incident."""
        response = await client.get(
            "/api/v1/incidents/99999/correlated-commits",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_correlated_commits_no_repository(
        self, client: AsyncClient, auth_headers, db_session
    ) -> None:
        """Test getting correlated commits for incident without repository."""
        from app.models.incident import Incident, IncidentSeverity

        # Create incident without repository
        incident = Incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.SEV3,
            owner_id=1,
        )
        db_session.add(incident)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/incidents/{incident.id}/correlated-commits",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["commits"] == []
        assert data["total"] == 0


class TestCorrelationWindowEdgeCases:
    """Tests for correlation window edge cases."""

    def test_commit_at_exact_boundary(self) -> None:
        """Test commit exactly at the window boundary."""
        # A commit at exactly 60 minutes before should be included
        # with 0 relevance (at the edge)
        window_minutes = 60
        minutes_before = 60

        commit = GitHubCommit(
            sha="abc123",
            message="Boundary commit",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        incident = MagicMock()
        incident.title = "Test"
        incident.description = "Test"

        relevance = calculate_commit_relevance(commit, incident, minutes_before, window_minutes)

        # At the boundary, time score should be 0
        assert relevance >= 0
        assert relevance <= 1

    def test_commit_just_inside_window(self) -> None:
        """Test commit just inside the window."""
        window_minutes = 60
        minutes_before = 59

        commit = GitHubCommit(
            sha="abc123",
            message="Just inside commit",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        incident = MagicMock()
        incident.title = "Test"
        incident.description = "Test"

        relevance = calculate_commit_relevance(commit, incident, minutes_before, window_minutes)

        # Should have some time-based relevance
        assert relevance > 0

    def test_very_recent_commit(self) -> None:
        """Test commit very close to incident time."""
        window_minutes = 60
        minutes_before = 1

        commit = GitHubCommit(
            sha="abc123",
            message="Very recent commit",
            author_name="Test",
            author_email="test@test.com",
            committed_at=datetime.now(UTC),
            url="https://github.com/test",
            files_changed=[],
        )

        incident = MagicMock()
        incident.title = "Test"
        incident.description = "Test"

        relevance = calculate_commit_relevance(commit, incident, minutes_before, window_minutes)

        # Very recent commit should have high time-based relevance
        # Time score = (1 - 1/60) * 0.5 ≈ 0.49
        assert relevance >= 0.45
