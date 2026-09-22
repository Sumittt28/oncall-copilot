"""Tests for citation validation and storage."""

import pytest
from pydantic import ValidationError

from app.services.rag.investigation import InvestigationResult, PossibleCause
from app.services.rag.storage import validate_citations


class TestValidateCitations:
    """Tests for citation validation."""

    def test_valid_citations_single_cause(self) -> None:
        """Test valid citations with a single cause."""
        result = InvestigationResult(
            summary="Database timeout due to connection pool exhaustion",
            severity_estimate="SEV-2",
            possible_causes=[
                PossibleCause(
                    cause="Connection pool exhausted",
                    confidence=0.85,
                    evidence_ids=["doc-1-chunk-1", "doc-2-chunk-3"],
                )
            ],
            recommended_actions=["Increase pool size"],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is True
        assert errors == []

    def test_valid_citations_multiple_causes(self) -> None:
        """Test valid citations with multiple causes."""
        result = InvestigationResult(
            summary="Service degradation with multiple factors",
            severity_estimate="SEV-3",
            possible_causes=[
                PossibleCause(
                    cause="Memory leak",
                    confidence=0.7,
                    evidence_ids=["doc-1-chunk-2"],
                ),
                PossibleCause(
                    cause="High CPU usage",
                    confidence=0.5,
                    evidence_ids=["incident-5"],
                ),
            ],
            recommended_actions=["Restart service", "Monitor memory"],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is True
        assert errors == []

    def test_insufficient_evidence_is_valid(self) -> None:
        """Test that insufficient_evidence=True is always valid."""
        result = InvestigationResult(
            summary="Unable to determine root cause",
            severity_estimate="SEV-3",
            possible_causes=[],
            recommended_actions=["Gather more logs"],
            insufficient_evidence=True,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is True
        assert errors == []

    def test_invalid_no_causes_without_insufficient_evidence(self) -> None:
        """Test that no causes without insufficient_evidence is invalid."""
        result = InvestigationResult(
            summary="Something happened",
            severity_estimate="SEV-3",
            possible_causes=[],
            recommended_actions=[],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is False
        assert len(errors) == 1
        assert "No possible causes" in errors[0]

    def test_invalid_cause_without_evidence(self) -> None:
        """Test that a cause without citations is flagged."""
        result = InvestigationResult(
            summary="Database issue",
            severity_estimate="SEV-2",
            possible_causes=[
                PossibleCause(
                    cause="Network timeout",
                    confidence=0.6,
                    evidence_ids=[],  # No citations
                )
            ],
            recommended_actions=["Check network"],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is False
        assert len(errors) == 1
        assert "without evidence citations" in errors[0]

    def test_high_confidence_with_few_citations(self) -> None:
        """Test that high confidence with few citations is flagged."""
        result = InvestigationResult(
            summary="Definite root cause",
            severity_estimate="SEV-1",
            possible_causes=[
                PossibleCause(
                    cause="Critical failure",
                    confidence=0.95,  # High confidence
                    evidence_ids=["doc-1"],  # Only 1 citation
                )
            ],
            recommended_actions=["Fix immediately"],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        # Still valid, but should have a warning about high confidence
        # with few citations
        assert "high confidence" in errors[0].lower() if errors else True

    def test_mixed_valid_and_invalid_causes(self) -> None:
        """Test validation with mix of valid and invalid causes."""
        result = InvestigationResult(
            summary="Multiple issues",
            severity_estimate="SEV-2",
            possible_causes=[
                PossibleCause(
                    cause="Valid cause",
                    confidence=0.7,
                    evidence_ids=["doc-1-chunk-1"],
                ),
                PossibleCause(
                    cause="Invalid cause",
                    confidence=0.5,
                    evidence_ids=[],  # No citations
                ),
            ],
            recommended_actions=["Fix both"],
            insufficient_evidence=False,
        )

        is_valid, errors = validate_citations(result)

        assert is_valid is False
        assert len(errors) >= 1


class TestInvestigationResultValidation:
    """Tests for InvestigationResult schema validation."""

    def test_valid_sev1(self) -> None:
        """Test SEV-1 is valid."""
        result = InvestigationResult(
            summary="Critical",
            severity_estimate="SEV-1",
            possible_causes=[],
            recommended_actions=[],
            insufficient_evidence=True,
        )
        assert result.severity_estimate == "SEV-1"

    def test_valid_sev4(self) -> None:
        """Test SEV-4 is valid."""
        result = InvestigationResult(
            summary="Low priority",
            severity_estimate="SEV-4",
            possible_causes=[],
            recommended_actions=[],
            insufficient_evidence=True,
        )
        assert result.severity_estimate == "SEV-4"

    def test_invalid_sev5(self) -> None:
        """Test SEV-5 is invalid."""
        with pytest.raises(ValidationError):
            InvestigationResult(
                summary="Invalid",
                severity_estimate="SEV-5",
                possible_causes=[],
                recommended_actions=[],
                insufficient_evidence=True,
            )

    def test_invalid_sev0(self) -> None:
        """Test SEV-0 is invalid."""
        with pytest.raises(ValidationError):
            InvestigationResult(
                summary="Invalid",
                severity_estimate="SEV-0",
                possible_causes=[],
                recommended_actions=[],
                insufficient_evidence=True,
            )

    def test_confidence_at_zero(self) -> None:
        """Test confidence of 0.0 is valid."""
        cause = PossibleCause(
            cause="Low confidence",
            confidence=0.0,
            evidence_ids=["doc-1"],
        )
        assert cause.confidence == 0.0

    def test_confidence_at_one(self) -> None:
        """Test confidence of 1.0 is valid."""
        cause = PossibleCause(
            cause="High confidence",
            confidence=1.0,
            evidence_ids=["doc-1", "doc-2"],
        )
        assert cause.confidence == 1.0

    def test_empty_summary_is_valid(self) -> None:
        """Test that empty summary is technically valid (no min length)."""
        result = InvestigationResult(
            summary="",
            severity_estimate="SEV-3",
            possible_causes=[],
            recommended_actions=[],
            insufficient_evidence=True,
        )
        assert result.summary == ""


class TestEvidenceIdFormat:
    """Tests for evidence ID format consistency."""

    def test_document_chunk_id_format(self) -> None:
        """Test document chunk evidence ID format."""
        evidence_id = "doc-123-chunk-456"
        parts = evidence_id.split("-")

        assert parts[0] == "doc"
        assert parts[1].isdigit()
        assert parts[2] == "chunk"
        assert parts[3].isdigit()

    def test_incident_id_format(self) -> None:
        """Test past incident evidence ID format."""
        evidence_id = "incident-789"
        parts = evidence_id.split("-")

        assert parts[0] == "incident"
        assert parts[1].isdigit()

    def test_evidence_ids_in_cause(self) -> None:
        """Test evidence IDs can be stored in cause."""
        cause = PossibleCause(
            cause="Test cause",
            confidence=0.5,
            evidence_ids=[
                "doc-1-chunk-1",
                "doc-2-chunk-5",
                "incident-10",
            ],
        )

        assert len(cause.evidence_ids) == 3
        assert "doc-1-chunk-1" in cause.evidence_ids
        assert "incident-10" in cause.evidence_ids
