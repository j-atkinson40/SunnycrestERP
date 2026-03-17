import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String, Text, func

from app.database import Base


class FHPayment(Base):
    """Payment received against a funeral home invoice."""

    __tablename__ = "fh_payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)
    invoice_id = Column(String(36), ForeignKey("fh_invoices.id"), nullable=False)

    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(30), nullable=False)
    reference_number = Column(String(100), nullable=True)

    received_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
