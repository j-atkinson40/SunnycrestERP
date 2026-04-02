"""CompanyMigrationReview — tracks uncertain fuzzy matches during data migration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CompanyMigrationReview(Base):
    __tablename__ = "company_migration_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    suggested_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)
    suggested_company_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    current_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    suggested_company = relationship("CompanyEntity", foreign_keys=[suggested_company_id])
    current_company = relationship("CompanyEntity", foreign_keys=[current_company_id])
