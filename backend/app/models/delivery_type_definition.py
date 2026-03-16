"""Delivery type definition — tenant-configurable delivery types."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class DeliveryTypeDefinition(Base):
    __tablename__ = "delivery_type_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_company_delivery_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    key = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(30), default="gray")
    icon = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    driver_instructions = Column(Text, nullable=True)
    requires_signature = Column(Boolean, default=False)
    requires_photo = Column(Boolean, default=False)
    requires_weight_ticket = Column(Boolean, default=False)
    allows_partial = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
