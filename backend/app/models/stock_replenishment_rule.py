import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class StockReplenishmentRule(Base):
    __tablename__ = "stock_replenishment_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    product_variant_id = Column(String(36), nullable=True)
    minimum_stock_quantity = Column(Integer, nullable=False)
    target_stock_quantity = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
