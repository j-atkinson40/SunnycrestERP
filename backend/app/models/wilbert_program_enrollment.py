"""WilbertProgramEnrollment — tracks which Wilbert programs a company participates in."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WilbertProgramEnrollment(Base):
    __tablename__ = "wilbert_program_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    program_code: Mapped[str] = mapped_column(String(50), nullable=False)
    program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    territory_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    uses_vault_territory: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled_product_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
