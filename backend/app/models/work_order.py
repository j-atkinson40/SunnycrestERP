import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    work_order_number = Column(String(50), nullable=False)
    trigger_type = Column(String(30), nullable=False)
    source_order_id = Column(String(36), nullable=True)
    source_order_line_id = Column(String(36), nullable=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    product_variant_id = Column(String(36), nullable=True)
    quantity_ordered = Column(Integer, nullable=False)
    quantity_produced = Column(Integer, default=0)
    quantity_passed_qc = Column(Integer, default=0)
    needed_by_date = Column(Date, nullable=True)
    priority = Column(String(20), default="standard")
    status = Column(String(30), default="draft")
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(String(36), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
