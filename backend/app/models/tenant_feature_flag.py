"""Tenant-level feature flag override."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func

from app.database import Base


class TenantFeatureFlag(Base):
    __tablename__ = "tenant_feature_flags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "flag_id", name="uq_tenant_flag"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    flag_id = Column(String(36), ForeignKey("feature_flags.id"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    from sqlalchemy.orm import relationship

    flag = relationship("FeatureFlag", back_populates="tenant_flags")
