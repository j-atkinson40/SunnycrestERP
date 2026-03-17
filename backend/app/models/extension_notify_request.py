"""Extension notify request — tracks tenant interest in coming_soon extensions."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.database import Base


class ExtensionNotifyRequest(Base):
    __tablename__ = "extension_notify_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "extension_id", name="uq_notify_tenant_extension"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    extension_id = Column(String(36), ForeignKey("extension_definitions.id"), nullable=False)
    employee_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
