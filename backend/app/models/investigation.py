"""AI Investigation models for storing investigation results."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import DocumentChunk
    from app.models.incident import Incident
    from app.models.user import User


class AIInvestigation(Base):
    """Stored AI investigation results."""

    __tablename__ = "ai_investigations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    triggered_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Investigation results
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity_estimate: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    insufficient_evidence: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Full structured output for debugging
    # Using JSON instead of JSONB for SQLite compatibility in tests
    structured_output: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="investigations")
    triggered_by: Mapped["User"] = relationship("User")
    evidence_citations: Mapped[list["IncidentEvidence"]] = relationship(
        "IncidentEvidence",
        back_populates="investigation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AIInvestigation(id={self.id}, incident_id={self.incident_id})>"


class IncidentEvidence(Base):
    """Evidence citations used in an investigation."""

    __tablename__ = "incident_evidence"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_investigations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )

    # Evidence reference
    evidence_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional foreign keys to source
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    source_incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Relevance and citation info
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    cited_in_causes: Mapped[bool] = mapped_column(default=False, nullable=False)
    cited_in_actions: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    investigation: Mapped["AIInvestigation"] = relationship(
        "AIInvestigation", back_populates="evidence_citations"
    )
    chunk: Mapped["DocumentChunk | None"] = relationship("DocumentChunk")
    source_incident: Mapped["Incident | None"] = relationship(
        "Incident",
        foreign_keys=[source_incident_id],
    )

    def __repr__(self) -> str:
        return f"<IncidentEvidence(id={self.id}, evidence_id={self.evidence_id})>"
