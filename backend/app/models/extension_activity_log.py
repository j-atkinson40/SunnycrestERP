"""Extension activity log — audit trail for extension install/disable/configure."""

import json
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class ExtensionActivityLog(Base):
    __tablename__ = "extension_activity_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    extension_id = Column(String(36), ForeignKey("extension_definitions.id"), nullable=False)
    action = Column(String(30), nullable=False)  # enabled, disabled, reconfigured, updated
    performed_by = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def details_dict(self) -> dict:
        if not self.details:
            return {}
        return json.loads(self.details)
