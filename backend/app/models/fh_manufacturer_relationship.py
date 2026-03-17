import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class FHManufacturerRelationship(Base):
    """Cross-tenant relationship between a funeral home and a vault manufacturer."""

    __tablename__ = "fh_manufacturer_relationships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    funeral_home_tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    manufacturer_tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    account_number = Column(String(50), nullable=True)
    default_delivery_instructions = Column(Text, nullable=True)
    is_primary = Column(Boolean, default=False)
    negotiated_price_tier = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
