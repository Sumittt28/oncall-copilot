"""AI investigation service for incidents."""

import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.services.llm.ollama_client import (
    OllamaConnectionError,
    OllamaError,
    OllamaTimeoutError,
    generate,
    generate_stream,
)
from app.services.rag.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    build_investigation_prompt,
)
from app.services.rag.retrieval import RetrievalContext, retrieve_evidence

logger = logging.getLogger(__name__)


# Pydantic models for structured output validation
class PossibleCause(BaseModel):
    """A possible cause with confidence and citations."""

    cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationResult(BaseModel):
    """Structured result from AI investigation."""

    summary: str
    severity_estimate: str = Field(pattern=r"^SEV-[1-4]$")
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


@dataclass
class InvestigationOutput:
    """Complete investigation output with metadata."""

    result: InvestigationResult | None
    raw_response: str
    retrieval_context: RetrievalContext
    processing_time_ms: float
    error: str | None = None
    validation_error: str | None = None


async def investigate_incident(
    db: AsyncSession,
    incident_id: int,
    max_retries: int = 2,
) -> InvestigationOutput:
    """Run AI investigation on an incident.

    Args:
        db: Database session.
        incident_id: ID of the incident to investigate.
        max_retries: Number of retries on validation failure.

    Returns:
        InvestigationOutput with results or error.
    """
    start_time = datetime.now(UTC)

    # Get incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        return InvestigationOutput(
            result=None,
            raw_response="",
            retrieval_context=RetrievalContext(
                incident=Incident(id=incident_id, title="", description="", owner_id=0),
                evidence=[],
            ),
            processing_time_ms=0,
            error="Incident not found",
        )

    # Retrieve evidence
    context = await retrieve_evidence(db, incident)

    # Build prompt
    prompt = build_investigation_prompt(context)

    # Try to generate and validate response
    last_error = None
    raw_response = ""

    for attempt in range(max_retries + 1):
        try:
            # Add retry hint if not first attempt
            retry_prompt = prompt
            if attempt > 0:
                retry_prompt += f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION: {last_error}\nPlease ensure your response is valid JSON matching the exact schema."

            # Generate response
            response = await generate(
                prompt=retry_prompt,
                system=INVESTIGATION_SYSTEM_PROMPT,
                temperature=0.3,  # Lower temperature for more consistent output
            )
            raw_response = response.response

            # Parse and validate
            investigation_result = _parse_investigation_response(raw_response)

            elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return InvestigationOutput(
                result=investigation_result,
                raw_response=raw_response,
                retrieval_context=context,
                processing_time_ms=elapsed_ms,
            )

        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            logger.warning(f"Investigation validation failed (attempt {attempt + 1}): {e}")
            continue

        except OllamaConnectionError as e:
            elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return InvestigationOutput(
                result=None,
                raw_response=raw_response,
                retrieval_context=context,
                processing_time_ms=elapsed_ms,
                error=f"Cannot connect to Ollama: {e}",
            )

        except OllamaTimeoutError as e:
            elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return InvestigationOutput(
                result=None,
                raw_response=raw_response,
                retrieval_context=context,
                processing_time_ms=elapsed_ms,
                error=f"Ollama request timed out: {e}",
            )

        except OllamaError as e:
            elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return InvestigationOutput(
                result=None,
                raw_response=raw_response,
                retrieval_context=context,
                processing_time_ms=elapsed_ms,
                error=f"Ollama error: {e}",
            )

    # All retries failed
    elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
    return InvestigationOutput(
        result=None,
        raw_response=raw_response,
        retrieval_context=context,
        processing_time_ms=elapsed_ms,
        validation_error=f"Failed to get valid response after {max_retries + 1} attempts: {last_error}",
    )


async def investigate_incident_stream(
    db: AsyncSession,
    incident_id: int,
) -> AsyncGenerator[str, None]:
    """Stream AI investigation on an incident.

    Yields SSE-formatted events:
    - event: token - Individual tokens as they are generated
    - event: evidence - Evidence items used
    - event: error - Error messages
    - event: done - Completion signal

    Args:
        db: Database session.
        incident_id: ID of the incident to investigate.

    Yields:
        SSE-formatted event strings.
    """
    # Get incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        yield _format_sse_event("error", {"message": "Incident not found"})
        return

    # Retrieve evidence
    try:
        context = await retrieve_evidence(db, incident)

        # Send evidence items
        for ev in context.evidence:
            yield _format_sse_event(
                "evidence",
                {
                    "evidence_id": ev.evidence_id,
                    "source_type": ev.source_type,
                    "source_title": ev.source_title,
                    "similarity": ev.similarity,
                },
            )

    except Exception as e:
        yield _format_sse_event("error", {"message": f"Evidence retrieval failed: {e}"})
        return

    # Build prompt
    prompt = build_investigation_prompt(context)

    # Stream response
    full_response = ""
    try:
        async for token in generate_stream(
            prompt=prompt,
            system=INVESTIGATION_SYSTEM_PROMPT,
            temperature=0.3,
        ):
            full_response += token
            yield _format_sse_event("token", {"content": token})

        # Try to parse the complete response
        try:
            investigation_result = _parse_investigation_response(full_response)
            yield _format_sse_event(
                "result",
                investigation_result.model_dump(),
            )
        except Exception as e:
            yield _format_sse_event(
                "validation_error",
                {"message": str(e), "raw_response": full_response},
            )

    except OllamaConnectionError as e:
        yield _format_sse_event("error", {"message": f"Cannot connect to Ollama: {e}"})

    except OllamaTimeoutError as e:
        yield _format_sse_event("error", {"message": f"Request timed out: {e}"})

    except OllamaError as e:
        yield _format_sse_event("error", {"message": f"Ollama error: {e}"})

    except Exception as e:
        yield _format_sse_event("error", {"message": f"Unexpected error: {e}"})

    finally:
        yield _format_sse_event("done", {"raw_response": full_response})


def _format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format data as an SSE event."""
    json_data = json.dumps(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _parse_investigation_response(response: str) -> InvestigationResult:
    """Parse and validate the investigation response.

    Args:
        response: Raw LLM response string.

    Returns:
        Validated InvestigationResult.

    Raises:
        ValueError: If response cannot be parsed.
        ValidationError: If response doesn't match schema.
    """
    # Try to extract JSON from the response
    # Sometimes LLMs add text before/after the JSON
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        raise ValueError("No JSON object found in response")

    json_str = json_match.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    # Validate with Pydantic
    return InvestigationResult.model_validate(data)
