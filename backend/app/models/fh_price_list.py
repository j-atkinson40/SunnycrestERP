import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.database import Base


class FHPriceListItem(Base):
    """General Price List (GPL) item for FTC-compliant funeral pricing."""

    __tablename__ = "fh_price_list"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    item_code = Column(String(50), nullable=False)
    category = Column(String(30), nullable=False)
    item_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    unit_price = Column(Numeric(12, 2), nullable=False)
    price_type = Column(String(20), nullable=False, default="flat")

    is_ftc_required_disclosure = Column(Boolean, default=False)
    ftc_disclosure_text = Column(Text, nullable=True)
    is_required_by_law = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    effective_date = Column(Date, nullable=True)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)


class FHPriceListVersion(Base):
    """Versioned snapshot of the General Price List."""

    __tablename__ = "fh_price_list_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    version_number = Column(Integer, nullable=False)
    effective_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    pdf_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
