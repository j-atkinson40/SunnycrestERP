"""Audit log for feature flag evaluations that block requests."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class FlagAuditLog(Base):
    __tablename__ = "flag_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    flag_key = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # "blocked", "toggled_on", "toggled_off", "override_removed"
    endpoint = Column(String(500), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
