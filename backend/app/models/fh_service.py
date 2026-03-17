import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.database import Base


class FHService(Base):
    """Service line item selected for a funeral home case."""

    __tablename__ = "fh_services"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    service_category = Column(String(30), nullable=False)
    service_code = Column(String(50), nullable=True)
    service_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False)
    extended_price = Column(Numeric(12, 2), nullable=False)

    is_required = Column(Boolean, default=False)
    is_selected = Column(Boolean, default=True)
    is_package_item = Column(Boolean, default=False)
    package_id = Column(String(36), nullable=True)

    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
