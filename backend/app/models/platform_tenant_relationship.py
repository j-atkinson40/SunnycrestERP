"""Generalized cross-tenant relationship for billing and supplier connections."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlatformTenantRelationship(Base):
    __tablename__ = "platform_tenant_relationships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "supplier_tenant_id", "relationship_type",
            name="uq_platform_tenant_rel",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    supplier_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)

    billing_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    billing_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_enabled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    connected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")

    legacy_fh_relationship_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer_tenant = relationship("Company", foreign_keys=[tenant_id])
    supplier_tenant = relationship("Company", foreign_keys=[supplier_tenant_id])
