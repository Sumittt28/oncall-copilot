"""Postmortem model for storing generated postmortems."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.user import User


class Postmortem(Base):
    """Generated postmortem document."""

    __tablename__ = "postmortems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    generated_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="postmortem")
    generated_by: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Postmortem(id={self.id}, incident_id={self.incident_id})>"
