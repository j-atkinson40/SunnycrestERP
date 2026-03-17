import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class WorkOrderProduct(Base):
    __tablename__ = "work_order_products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    work_order_id = Column(String(36), ForeignKey("work_orders.id"), nullable=False)
    pour_event_id = Column(String(36), ForeignKey("pour_events.id"), nullable=True)
    serial_number = Column(String(50), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    product_variant_id = Column(String(36), nullable=True)
    status = Column(String(30), default="produced")
    qc_inspection_id = Column(String(36), nullable=True)
    received_to_inventory_at = Column(DateTime(timezone=True), nullable=True)
    received_by = Column(String(36), nullable=True)
    inventory_location = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
