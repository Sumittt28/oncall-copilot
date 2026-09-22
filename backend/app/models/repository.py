"""Repository model for GitHub integration."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.user import User


class Repository(Base):
    """GitHub repository connection."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Repository info
    github_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    github_url: Mapped[str] = mapped_column(String(500), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)

    # Access token (encrypted in production)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    # Owner
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="repositories")
    incidents: Mapped[list["Incident"]] = relationship(
        "Incident",
        back_populates="repository",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, name={self.github_full_name})>"
