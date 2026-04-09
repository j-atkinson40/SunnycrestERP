"""UrnTenantSettings model — per-tenant configuration for urn sales extension."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UrnTenantSettings(Base):
    __tablename__ = "urn_tenant_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, unique=True
    )

    ancillary_window_days: Mapped[int] = mapped_column(Integer, default=3)
    supplier_lead_days: Mapped[int] = mapped_column(Integer, default=7)
    fh_approval_token_expiry_days: Mapped[int] = mapped_column(Integer, default=3)

    proof_email_address: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    wilbert_submission_email: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Catalog PDF auto-fetch
    catalog_pdf_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # MD5 hex digest of last fetched PDF
    catalog_pdf_last_fetched: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    catalog_pdf_r2_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # R2 storage key for cached PDF

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])
