"""Tenant module configuration — tracks which modules are enabled per tenant."""

import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from app.database import Base


class TenantModuleConfig(Base):
    __tablename__ = "tenant_module_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uq_tenant_module_config"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    module_key = Column(String(80), nullable=False)
    enabled = Column(Boolean, default=True)
    enabled_at = Column(DateTime(timezone=True), nullable=True)
    disabled_at = Column(DateTime(timezone=True), nullable=True)
    enabled_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
