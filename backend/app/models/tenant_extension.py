"""Tenant extension — per-tenant extension enablement and configuration."""

import json
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func

from app.database import Base


class TenantExtension(Base):
    __tablename__ = "tenant_extensions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "extension_key", name="uq_tenant_extension"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    extension_key = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    config = Column(Text, nullable=True)  # JSON config values
    enabled_at = Column(DateTime(timezone=True), nullable=True)
    enabled_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def config_dict(self) -> dict:
        if not self.config:
            return {}
        return json.loads(self.config)

    def get_config_value(self, key: str, default=None):
        return self.config_dict.get(key, default)
