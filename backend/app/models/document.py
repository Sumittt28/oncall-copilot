"""Document and DocumentChunk models for file management."""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.services.embeddings import EMBEDDING_DIMENSION

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.user import User


class DocumentType(str, Enum):
    """Type of document."""

    RUNBOOK = "runbook"
    POSTMORTEM = "postmortem"
    LOG = "log"
    DOC = "doc"


# Supported file extensions and their MIME types
SUPPORTED_FILE_TYPES: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".log": "text/plain",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".xml": "text/xml",
    ".csv": "text/csv",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".sh": "text/x-shellscript",
    ".sql": "text/x-sql",
    ".conf": "text/plain",
    ".cfg": "text/plain",
    ".ini": "text/plain",
    ".env": "text/plain",
}

# Maximum file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class Document(Base):
    """Document metadata for uploaded files."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)  # Size in bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    uploaded_by: Mapped["User"] = relationship("User")
    incident: Mapped["Incident | None"] = relationship(
        "Incident", back_populates="documents"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, type={self.document_type})>"


class DocumentChunk(Base):
    """Chunked text from a document for RAG retrieval."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)  # Order within document
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)  # Approximate token count
    embedding = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)  # pgvector
    embedded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    # Indexes for efficient retrieval
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
    )

    @property
    def has_embedding(self) -> bool:
        """Check if this chunk has been embedded."""
        return self.embedding is not None

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
