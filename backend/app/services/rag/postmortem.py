"""AI Postmortem generation service."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentEvent
from app.models.investigation import AIInvestigation
from app.services.llm.ollama_client import (
    OllamaConnectionError,
    OllamaError,
    OllamaTimeoutError,
    generate,
)
from app.services.rag.prompts import POSTMORTEM_SYSTEM_PROMPT, build_postmortem_prompt

logger = logging.getLogger(__name__)


@dataclass
class PostmortemResult:
    """Result from postmortem generation."""

    content: str  # Markdown content
    incident_id: int
    processing_time_ms: float
    model_name: str
    error: str | None = None


async def generate_postmortem(
    db: AsyncSession,
    incident_id: int,
) -> PostmortemResult:
    """Generate a postmortem document for a resolved incident.

    Args:
        db: Database session.
        incident_id: ID of the resolved incident.

    Returns:
        PostmortemResult with markdown content or error.
    """
    from app.core.config import get_settings

    settings = get_settings()
    start_time = datetime.now(UTC)

    # Get incident with events
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if incident is None:
        return PostmortemResult(
            content="",
            incident_id=incident_id,
            processing_time_ms=0,
            model_name=settings.ollama_model,
            error="Incident not found",
        )

    if incident.resolved_at is None:
        return PostmortemResult(
            content="",
            incident_id=incident_id,
            processing_time_ms=0,
            model_name=settings.ollama_model,
            error="Incident is not resolved yet",
        )

    # Get timeline events
    events_result = await db.execute(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.created_at)
    )
    events = list(events_result.scalars().all())

    # Get latest investigation summary
    investigation_summary = "No AI investigation was performed."
    inv_result = await db.execute(
        select(AIInvestigation)
        .where(AIInvestigation.incident_id == incident_id)
        .order_by(AIInvestigation.created_at.desc())
        .limit(1)
    )
    investigation = inv_result.scalar_one_or_none()

    if investigation:
        investigation_summary = f"""Summary: {investigation.summary}

Severity Estimate: {investigation.severity_estimate}
Confidence: {investigation.confidence:.0%}

Possible Causes:
"""
        from typing import Any, cast
        structured: dict[str, Any] = cast(dict[str, Any], investigation.structured_output)
        for cause in structured.get("possible_causes", []):
            investigation_summary += f"- {cause.get('cause', 'Unknown')} (confidence: {cause.get('confidence', 0):.0%})\n"

        investigation_summary += "\nRecommended Actions:\n"
        for action in structured.get("recommended_actions", []):
            investigation_summary += f"- {action}\n"

    # Build prompt
    prompt = build_postmortem_prompt(
        incident=incident,
        investigation_summary=investigation_summary,
        timeline_events=events,
    )

    try:
        response = await generate(
            prompt=prompt,
            system=POSTMORTEM_SYSTEM_PROMPT,
            temperature=0.4,  # Slightly creative but mostly factual
            max_tokens=2000,
        )

        elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        return PostmortemResult(
            content=response.response,
            incident_id=incident_id,
            processing_time_ms=elapsed_ms,
            model_name=settings.ollama_model,
        )

    except OllamaConnectionError as e:
        return PostmortemResult(
            content="",
            incident_id=incident_id,
            processing_time_ms=0,
            model_name=settings.ollama_model,
            error=f"Cannot connect to Ollama: {e}",
        )

    except OllamaTimeoutError as e:
        return PostmortemResult(
            content="",
            incident_id=incident_id,
            processing_time_ms=0,
            model_name=settings.ollama_model,
            error=f"Ollama request timed out: {e}",
        )

    except OllamaError as e:
        return PostmortemResult(
            content="",
            incident_id=incident_id,
            processing_time_ms=0,
            model_name=settings.ollama_model,
            error=f"Ollama error: {e}",
        )
