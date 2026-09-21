"""Tests for AI investigation functionality."""

import json

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.services.rag.investigation import (
    InvestigationResult,
    _parse_investigation_response,
)
from app.services.rag.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    build_investigation_prompt,
)
from app.services.rag.retrieval import Evidence, RetrievalContext


class TestParseInvestigationResponse:
    """Tests for parsing LLM responses."""

    def test_parse_valid_json(self) -> None:
        """Test parsing a valid JSON response."""
        response = json.dumps({
            "summary": "Database connection timeout caused service outage",
            "severity_estimate": "SEV-2",
            "possible_causes": [
                {
                    "cause": "Connection pool exhaustion",
                    "confidence": 0.85,
                    "evidence_ids": ["doc-1-chunk-1"]
                }
            ],
            "recommended_actions": ["Increase connection pool size"],
            "insufficient_evidence": False
        })

        result = _parse_investigation_response(response)

        assert result.summary == "Database connection timeout caused service outage"
        assert result.severity_estimate == "SEV-2"
        assert len(result.possible_causes) == 1
        assert result.possible_causes[0].confidence == 0.85
        assert not result.insufficient_evidence

    def test_parse_json_with_surrounding_text(self) -> None:
        """Test parsing JSON when LLM adds explanation text."""
        response = """Here is my analysis:

{
    "summary": "Memory leak in worker process",
    "severity_estimate": "SEV-3",
    "possible_causes": [],
    "recommended_actions": [],
    "insufficient_evidence": true
}

Let me know if you need more details."""

        result = _parse_investigation_response(response)

        assert result.summary == "Memory leak in worker process"
        assert result.insufficient_evidence is True

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON raises ValueError."""
        response = "This is not JSON at all"

        with pytest.raises(ValueError, match="No JSON object found"):
            _parse_investigation_response(response)

    def test_parse_malformed_json(self) -> None:
        """Test parsing malformed JSON raises ValueError."""
        response = '{"summary": "incomplete'

        with pytest.raises(ValueError):
            _parse_investigation_response(response)

    def test_parse_missing_required_field(self) -> None:
        """Test parsing JSON missing required fields."""
        response = json.dumps({
            "summary": "Test",
            # Missing severity_estimate and other fields
        })

        with pytest.raises(ValidationError):  # ValidationError
            _parse_investigation_response(response)

    def test_parse_invalid_severity(self) -> None:
        """Test parsing JSON with invalid severity format."""
        response = json.dumps({
            "summary": "Test",
            "severity_estimate": "CRITICAL",  # Should be SEV-1 to SEV-4
            "possible_causes": [],
            "recommended_actions": [],
            "insufficient_evidence": False
        })

        with pytest.raises(ValidationError):  # ValidationError
            _parse_investigation_response(response)

    def test_parse_invalid_confidence(self) -> None:
        """Test parsing JSON with invalid confidence value."""
        response = json.dumps({
            "summary": "Test",
            "severity_estimate": "SEV-2",
            "possible_causes": [
                {
                    "cause": "Test cause",
                    "confidence": 1.5,  # Should be 0.0-1.0
                    "evidence_ids": []
                }
            ],
            "recommended_actions": [],
            "insufficient_evidence": False
        })

        with pytest.raises(ValidationError):  # ValidationError
            _parse_investigation_response(response)


class TestBuildInvestigationPrompt:
    """Tests for prompt construction."""

    def test_prompt_includes_incident_details(self) -> None:
        """Test that prompt includes incident information."""
        incident = Incident(
            id=1,
            title="Database Connection Timeout",
            description="Users reporting slow queries",
            severity=IncidentSeverity.SEV2,
            status=IncidentStatus.INVESTIGATING,
            owner_id=1,
        )

        context = RetrievalContext(
            incident=incident,
            evidence=[],
        )

        prompt = build_investigation_prompt(context)

        assert "Database Connection Timeout" in prompt
        assert "Users reporting slow queries" in prompt
        assert "SEV-2" in prompt
        assert "investigating" in prompt

    def test_prompt_includes_evidence(self) -> None:
        """Test that prompt includes evidence items."""
        incident = Incident(
            id=1,
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.OPEN,
            owner_id=1,
        )

        evidence = [
            Evidence(
                evidence_id="doc-1-chunk-1",
                source_type="attached_document",
                source_id=1,
                source_title="Runbook: DB Recovery",
                content="When database times out, restart the connection pool...",
                similarity=0.85,
            ),
            Evidence(
                evidence_id="incident-5",
                source_type="past_incident",
                source_id=5,
                source_title="Past Incident #5: DB Outage",
                content="Similar timeout issue occurred last month",
                similarity=0.72,
            ),
        ]

        context = RetrievalContext(
            incident=incident,
            evidence=evidence,
        )

        prompt = build_investigation_prompt(context)

        assert "[doc-1-chunk-1]" in prompt
        assert "Runbook: DB Recovery" in prompt
        assert "restart the connection pool" in prompt
        assert "[incident-5]" in prompt
        assert "Past Incident #5" in prompt

    def test_prompt_handles_no_evidence(self) -> None:
        """Test prompt generation with no evidence."""
        incident = Incident(
            id=1,
            title="New Incident",
            description="No matching docs",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.OPEN,
            owner_id=1,
        )

        context = RetrievalContext(
            incident=incident,
            evidence=[],
        )

        prompt = build_investigation_prompt(context)

        assert "No relevant evidence" in prompt
        assert "insufficient_evidence" in prompt

    def test_prompt_truncates_long_content(self) -> None:
        """Test that very long evidence content is truncated."""
        incident = Incident(
            id=1,
            title="Test",
            description="Test",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.OPEN,
            owner_id=1,
        )

        long_content = "x" * 5000
        evidence = [
            Evidence(
                evidence_id="doc-1-chunk-1",
                source_type="document",
                source_id=1,
                source_title="Long Doc",
                content=long_content,
                similarity=0.9,
            ),
        ]

        context = RetrievalContext(
            incident=incident,
            evidence=evidence,
        )

        prompt = build_investigation_prompt(context)

        # Content should be truncated with "..."
        assert "..." in prompt
        assert len(prompt) < len(long_content) + 1000

    def test_system_prompt_content(self) -> None:
        """Test system prompt has required instructions."""
        assert "cite evidence" in INVESTIGATION_SYSTEM_PROMPT.lower()
        assert "json" in INVESTIGATION_SYSTEM_PROMPT.lower()
        assert "evidence_id" in INVESTIGATION_SYSTEM_PROMPT
        assert "insufficient evidence" in INVESTIGATION_SYSTEM_PROMPT.lower()


class TestInvestigationResult:
    """Tests for InvestigationResult model."""

    def test_valid_result(self) -> None:
        """Test creating a valid investigation result."""
        result = InvestigationResult(
            summary="Test summary",
            severity_estimate="SEV-2",
            possible_causes=[],
            recommended_actions=["Action 1"],
            insufficient_evidence=False,
        )

        assert result.summary == "Test summary"
        assert result.severity_estimate == "SEV-2"

    def test_invalid_severity_format(self) -> None:
        """Test that invalid severity format is rejected."""
        with pytest.raises(ValidationError):  # ValidationError
            InvestigationResult(
                summary="Test",
                severity_estimate="HIGH",  # Invalid
                possible_causes=[],
                recommended_actions=[],
                insufficient_evidence=False,
            )

    def test_confidence_bounds(self) -> None:
        """Test that confidence must be 0-1."""
        from app.services.rag.investigation import PossibleCause

        # Valid confidence
        cause = PossibleCause(
            cause="Test",
            confidence=0.5,
            evidence_ids=[],
        )
        assert cause.confidence == 0.5

        # Invalid confidence
        with pytest.raises(ValidationError):
            PossibleCause(
                cause="Test",
                confidence=-0.1,
                evidence_ids=[],
            )


@pytest.mark.asyncio
async def test_investigation_endpoint_unauthenticated(client: AsyncClient) -> None:
    """Test investigation endpoint without authentication."""
    response = await client.post("/api/v1/incidents/1/investigate")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_investigation_endpoint_incident_not_found(
    client: AsyncClient, auth_headers
) -> None:
    """Test investigation with non-existent incident."""
    response = await client.post(
        "/api/v1/incidents/99999/investigate",
        headers=auth_headers,
    )
    # Will be 503 (Ollama unavailable) or 404 depending on order of checks
    assert response.status_code in [404, 503]


@pytest.mark.asyncio
async def test_ollama_status_endpoint(client: AsyncClient, auth_headers) -> None:
    """Test Ollama status check endpoint."""
    response = await client.get("/api/v1/ollama/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "healthy" in data
    assert "model_available" in data
    assert "model_name" in data


@pytest.mark.asyncio
async def test_investigation_stream_unauthenticated(client: AsyncClient) -> None:
    """Test streaming investigation without authentication."""
    response = await client.get("/api/v1/incidents/1/investigate/stream")
    assert response.status_code == 403
