"""Feature flag model — global flag definitions."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="general")
    default_enabled = Column(Boolean, nullable=False, default=False)
    is_global = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant_flags = relationship("TenantFeatureFlag", back_populates="flag")
