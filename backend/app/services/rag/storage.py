"""Storage service for AI investigation results."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.investigation import AIInvestigation, IncidentEvidence
from app.services.rag.investigation import InvestigationOutput, InvestigationResult

logger = logging.getLogger(__name__)
settings = get_settings()


async def save_investigation(
    db: AsyncSession,
    incident_id: int,
    user_id: int,
    output: InvestigationOutput,
) -> AIInvestigation:
    """Save an investigation result to the database.

    Args:
        db: Database session.
        incident_id: ID of the investigated incident.
        user_id: ID of the user who triggered the investigation.
        output: Investigation output to save.

    Returns:
        The saved AIInvestigation record.
    """
    result = output.result
    if result is None:
        raise ValueError("Cannot save investigation without a valid result")

    # Calculate overall confidence from causes
    confidence = 0.0
    if result.possible_causes:
        confidence = max(c.confidence for c in result.possible_causes)

    # Create the investigation record
    investigation = AIInvestigation(
        incident_id=incident_id,
        triggered_by_id=user_id,
        summary=result.summary,
        severity_estimate=result.severity_estimate,
        confidence=confidence,
        insufficient_evidence=result.insufficient_evidence,
        structured_output=result.model_dump(),
        raw_response=output.raw_response,
        processing_time_ms=output.processing_time_ms,
        evidence_count=len(output.retrieval_context.evidence),
        model_name=settings.ollama_model,
    )
    db.add(investigation)
    await db.flush()  # Get the ID

    # Collect all cited evidence IDs
    cited_evidence_ids = _collect_cited_evidence(result)

    # Save evidence citations
    for evidence in output.retrieval_context.evidence:
        is_cited_in_causes = evidence.evidence_id in cited_evidence_ids
        is_cited_in_actions = _is_cited_in_actions(
            evidence.evidence_id, result.recommended_actions
        )

        # Determine source IDs
        chunk_id = None
        source_incident_id = None
        commit_sha = None

        if evidence.source_type in ("attached_document", "similar_document"):
            chunk_id = evidence.source_id
        elif evidence.source_type == "past_incident":
            source_incident_id = evidence.source_id
        elif evidence.source_type == "commit":
            commit_sha = evidence.metadata.get("sha")

        evidence_record = IncidentEvidence(
            investigation_id=investigation.id,
            incident_id=incident_id,
            evidence_id=evidence.evidence_id,
            source_type=evidence.source_type,
            source_title=evidence.source_title,
            content_preview=evidence.content[:500] if evidence.content else "",
            chunk_id=chunk_id,
            source_incident_id=source_incident_id,
            commit_sha=str(commit_sha) if commit_sha else None,
            relevance_score=evidence.similarity or 0.0,
            cited_in_causes=is_cited_in_causes,
            cited_in_actions=is_cited_in_actions,
        )
        db.add(evidence_record)

    await db.flush()
    return investigation


def _collect_cited_evidence(result: InvestigationResult) -> set[str]:
    """Collect all evidence IDs cited in the result."""
    cited = set()
    for cause in result.possible_causes:
        cited.update(cause.evidence_ids)
    return cited


def _is_cited_in_actions(evidence_id: str, actions: list[str]) -> bool:
    """Check if an evidence ID is mentioned in recommended actions."""
    for action in actions:
        if evidence_id in action:
            return True
    return False


def validate_citations(result: InvestigationResult) -> tuple[bool, list[str]]:
    """Validate that all claims have proper citations.

    Args:
        result: The investigation result to validate.

    Returns:
        Tuple of (is_valid, list of validation errors).
    """
    errors = []

    # Check if insufficient_evidence is set appropriately
    if result.insufficient_evidence:
        # If marked as insufficient evidence, that's valid
        return True, []

    # If not insufficient evidence, we need at least one cause with citations
    if not result.possible_causes:
        errors.append("No possible causes identified but insufficient_evidence is False")
        return False, errors

    # Each cause should have at least one citation
    uncited_causes = []
    for i, cause in enumerate(result.possible_causes):
        if not cause.evidence_ids:
            uncited_causes.append(f"Cause {i + 1}: {cause.cause[:50]}...")

    if uncited_causes:
        errors.append(f"Causes without evidence citations: {', '.join(uncited_causes)}")

    # Check confidence levels are reasonable
    for i, cause in enumerate(result.possible_causes):
        if cause.confidence > 0.9 and len(cause.evidence_ids) < 2:
            errors.append(
                f"Cause {i + 1} has high confidence ({cause.confidence}) "
                f"but only {len(cause.evidence_ids)} citation(s)"
            )

    return len(errors) == 0, errors
