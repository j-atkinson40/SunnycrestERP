import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.database import Base


class FHVaultOrder(Base):
    """Order placed with a vault manufacturer for a funeral home case."""

    __tablename__ = "fh_vault_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    manufacturer_tenant_id = Column(String(36), ForeignKey("companies.id"), nullable=True)
    order_number = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="draft")

    vault_product_id = Column(String(36), nullable=True)
    vault_product_name = Column(String(200), nullable=True)
    vault_product_sku = Column(String(50), nullable=True)

    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=True)

    requested_delivery_date = Column(Date, nullable=True)
    confirmed_delivery_date = Column(Date, nullable=True)
    delivery_address = Column(Text, nullable=True)
    delivery_contact_name = Column(String(200), nullable=True)
    delivery_contact_phone = Column(String(20), nullable=True)

    special_instructions = Column(Text, nullable=True)
    manufacturer_order_id = Column(String(36), nullable=True)
    delivery_status_last_updated_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
