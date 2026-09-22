"""RAG services for AI investigation."""

from app.services.rag.investigation import (
    InvestigationOutput,
    InvestigationResult,
    PossibleCause,
    investigate_incident,
    investigate_incident_stream,
)
from app.services.rag.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    POSTMORTEM_SYSTEM_PROMPT,
    build_investigation_prompt,
    build_postmortem_prompt,
)
from app.services.rag.retrieval import (
    Evidence,
    RetrievalContext,
    retrieve_evidence,
)
from app.services.rag.storage import (
    save_investigation,
    validate_citations,
)

__all__ = [
    "Evidence",
    "INVESTIGATION_SYSTEM_PROMPT",
    "InvestigationOutput",
    "InvestigationResult",
    "POSTMORTEM_SYSTEM_PROMPT",
    "PossibleCause",
    "RetrievalContext",
    "build_investigation_prompt",
    "build_postmortem_prompt",
    "investigate_incident",
    "investigate_incident_stream",
    "retrieve_evidence",
    "save_investigation",
    "validate_citations",
]
