"""Prompt templates for AI investigation."""

from app.models.incident import Incident, IncidentEvent
from app.services.rag.retrieval import RetrievalContext

# System prompt for incident investigation
INVESTIGATION_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) and incident responder. Your task is to analyze incidents and provide root cause analysis based on the available evidence.

IMPORTANT RULES:
1. You MUST cite evidence for every claim using [evidence_id] format
2. If you don't have enough evidence, say "insufficient evidence" - NEVER guess
3. Provide confidence scores (0.0-1.0) based on evidence strength
4. Be specific and actionable in your recommendations
5. Consider multiple possible causes if evidence supports them

Your output MUST be valid JSON matching this exact schema:
{
  "summary": "Brief 1-2 sentence summary of the incident and likely cause",
  "severity_estimate": "SEV-1 | SEV-2 | SEV-3 | SEV-4",
  "possible_causes": [
    {
      "cause": "Description of the potential cause",
      "confidence": 0.0,
      "evidence_ids": ["evidence_id_1", "evidence_id_2"]
    }
  ],
  "recommended_actions": ["Action 1", "Action 2"],
  "insufficient_evidence": false
}

If you cannot determine any likely cause due to lack of evidence, set insufficient_evidence to true and explain in the summary."""


def build_investigation_prompt(context: RetrievalContext) -> str:
    """Build the investigation prompt with incident context and evidence.

    Args:
        context: RetrievalContext with incident and evidence.

    Returns:
        Formatted prompt string.
    """
    incident = context.incident

    # Build incident section
    incident_section = f"""## INCIDENT TO INVESTIGATE

**Title:** {incident.title}
**ID:** #{incident.id}
**Severity:** {incident.severity.value if hasattr(incident.severity, 'value') else incident.severity}
**Status:** {incident.status.value if hasattr(incident.status, 'value') else incident.status}
**Created:** {incident.created_at.isoformat() if incident.created_at else 'Unknown'}

**Description:**
{incident.description}
"""

    # Build evidence section
    if context.evidence:
        evidence_section = "## AVAILABLE EVIDENCE\n\n"
        for ev in context.evidence:
            similarity_str = f"{ev.similarity:.2f}" if ev.similarity is not None else "N/A"
            content_truncated = ev.content[:1500] + "..." if len(ev.content) > 1500 else ev.content
            evidence_section += f"""### [{ev.evidence_id}] {ev.source_title}
**Type:** {ev.source_type}
**Relevance:** {similarity_str}

{content_truncated}

---

"""
    else:
        evidence_section = """## AVAILABLE EVIDENCE

No relevant evidence was found. You should indicate insufficient_evidence=true in your response.

"""

    # Build the full prompt
    prompt = f"""{incident_section}

{evidence_section}

## YOUR TASK

Analyze the incident above using the available evidence. Provide a root cause analysis following these steps:

1. Review the incident description and understand what happened
2. Examine each piece of evidence and note relevant findings
3. Identify patterns or correlations between evidence
4. Determine the most likely root cause(s) with confidence levels
5. Recommend specific actions to resolve and prevent recurrence

Remember:
- ALWAYS cite evidence using [evidence_id] format
- NEVER make claims without supporting evidence
- If evidence is insufficient, say so clearly
- Output ONLY valid JSON matching the required schema

Respond with your analysis in JSON format:"""

    return prompt


def build_postmortem_prompt(
    incident: Incident,
    investigation_summary: str,
    timeline_events: list[IncidentEvent],
) -> str:
    """Build prompt for generating a postmortem document.

    Args:
        incident: The resolved incident.
        investigation_summary: Previous AI investigation summary.
        timeline_events: List of incident events.

    Returns:
        Formatted prompt string.
    """
    # Format timeline
    timeline_str = ""
    for event in timeline_events:
        event_time = event.created_at.isoformat() if event.created_at else "Unknown"
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
        timeline_str += f"- [{event_time}] {event_type}: {event.content}\n"

    if not timeline_str:
        timeline_str = "No timeline events recorded."

    # Calculate resolution time
    resolution_time = "Unknown"
    if incident.created_at and incident.resolved_at:
        delta = incident.resolved_at - incident.created_at
        hours = delta.total_seconds() / 3600
        if hours < 1:
            resolution_time = f"{int(delta.total_seconds() / 60)} minutes"
        elif hours < 24:
            resolution_time = f"{hours:.1f} hours"
        else:
            resolution_time = f"{hours / 24:.1f} days"

    prompt = f"""Generate a comprehensive postmortem document for the following resolved incident.

## INCIDENT DETAILS

**Title:** {incident.title}
**ID:** #{incident.id}
**Severity:** {incident.severity.value if hasattr(incident.severity, 'value') else incident.severity}
**Created:** {incident.created_at.isoformat() if incident.created_at else 'Unknown'}
**Resolved:** {incident.resolved_at.isoformat() if incident.resolved_at else 'Unknown'}
**Resolution Time:** {resolution_time}

**Description:**
{incident.description}

## TIMELINE

{timeline_str}

## AI INVESTIGATION SUMMARY

{investigation_summary}

## YOUR TASK

Generate a complete postmortem document with the following sections:

1. **Overview** - Brief summary of the incident
2. **Impact** - Who/what was affected and how severely
3. **Timeline** - Key events in chronological order
4. **Root Cause** - The underlying cause(s) of the incident
5. **Contributing Factors** - Secondary factors that made the incident worse
6. **Detection** - How the incident was detected and time to detection
7. **Resolution** - Steps taken to resolve the incident
8. **Corrective Actions** - Specific actions to prevent recurrence (with owners and deadlines)
9. **Lessons Learned** - Key takeaways for the team

Format your response as a well-structured Markdown document."""

    return prompt


POSTMORTEM_SYSTEM_PROMPT = """You are an expert SRE writing postmortem documents. Your postmortems are:
- Blameless and focused on systemic improvements
- Specific with actionable corrective actions
- Written clearly for both technical and non-technical readers
- Honest about what went wrong and what can be improved

Write professional, comprehensive postmortem documents that help teams learn and improve."""
