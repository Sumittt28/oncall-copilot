"""Incident and IncidentEvent models."""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.investigation import AIInvestigation
    from app.models.postmortem import Postmortem
    from app.models.repository import Repository
    from app.models.user import User


class IncidentSeverity(str, Enum):
    """Incident severity levels."""

    SEV1 = "SEV-1"  # Critical - system down
    SEV2 = "SEV-2"  # Major - significant impact
    SEV3 = "SEV-3"  # Minor - limited impact
    SEV4 = "SEV-4"  # Low - minimal impact


class IncidentStatus(str, Enum):
    """Incident status values."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


# Valid status transitions
VALID_STATUS_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED},
    IncidentStatus.INVESTIGATING: {IncidentStatus.IDENTIFIED, IncidentStatus.RESOLVED},
    IncidentStatus.IDENTIFIED: {IncidentStatus.MONITORING, IncidentStatus.RESOLVED},
    IncidentStatus.MONITORING: {IncidentStatus.RESOLVED, IncidentStatus.IDENTIFIED},
    IncidentStatus.RESOLVED: set(),  # Terminal state
}


def is_valid_status_transition(current: IncidentStatus, new: IncidentStatus) -> bool:
    """Check if a status transition is valid."""
    if current == new:
        return True  # No change is always valid
    return new in VALID_STATUS_TRANSITIONS.get(current, set())


class IncidentEventType(str, Enum):
    """Types of incident timeline events."""

    CREATED = "created"
    STATUS_CHANGE = "status_change"
    COMMENT = "comment"
    SEVERITY_CHANGE = "severity_change"
    ASSIGNMENT = "assignment"
    AI_INVESTIGATION = "ai_investigation"
    POSTMORTEM = "postmortem"


class Incident(Base):
    """Incident record."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(
        String(10), default=IncidentSeverity.SEV3, nullable=False
    )
    status: Mapped[IncidentStatus] = mapped_column(
        String(20), default=IncidentStatus.OPEN, nullable=False
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="incidents")
    events: Mapped[list["IncidentEvent"]] = relationship(
        "IncidentEvent",
        back_populates="incident",
        lazy="selectin",
        order_by="IncidentEvent.created_at",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="incident",
        lazy="selectin",
    )
    investigations: Mapped[list["AIInvestigation"]] = relationship(
        "AIInvestigation",
        back_populates="incident",
        lazy="selectin",
        order_by="AIInvestigation.created_at.desc()",
    )
    repository: Mapped["Repository | None"] = relationship(
        "Repository",
        back_populates="incidents",
        lazy="selectin",
    )
    postmortem: Mapped["Postmortem | None"] = relationship(
        "Postmortem",
        back_populates="incident",
        uselist=False,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Incident(id={self.id}, title={self.title}, status={self.status})>"


class IncidentEvent(Base):
    """Timeline event for an incident."""

    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    event_type: Mapped[IncidentEventType] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")
    actor: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<IncidentEvent(id={self.id}, type={self.event_type})>"
