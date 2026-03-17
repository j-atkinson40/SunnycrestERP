import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String, Text, func

from app.database import Base


class FHInvoice(Base):
    """Invoice for a funeral home case."""

    __tablename__ = "fh_invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    invoice_number = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="draft")

    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    amount_paid = Column(Numeric(12, 2), nullable=False, default=0)
    balance_due = Column(Numeric(12, 2), nullable=False)

    due_date = Column(Date, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    sent_to_email = Column(String(200), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
