"""Command Bar intelligence ORM models — search index + history."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentSearchIndex(Base):
    """Unified full-text search index across VaultDocuments, KB articles,
    safety programs, training topics, etc. One row per source entity.
    """

    __tablename__ = "document_search_index"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("vault_documents.id", ondelete="CASCADE"), nullable=True
    )
    content_source: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'vault_document' | 'kb_article' | 'safety_program' | 'training_topic' | 'compliance_item'
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_chunks: Mapped[list] = mapped_column(JSONB, nullable=False)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommandBarHistory(Base):
    """Per-user history of command bar selections. Used for 'recent' list
    and to pre-fill overlay values from last use."""

    __tablename__ = "command_bar_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    result_type: Mapped[str] = mapped_column(String(50), nullable=False)
    result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_title: Mapped[str] = mapped_column(String(255), nullable=False)
    query_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
