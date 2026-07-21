"""Sales-tax filing models — the certificate axes + the period accumulator.

TaxCertificate is ONE model with TWO attachment points: customer-level
blanket (sales_order_id NULL) and job-level (sales_order_id set) — the
June design's record core carrying the precast per-job reality. Dated
validity does the expiry work: a cert past valid_through is simply not
valid. The Vault document reference holds the scan when provided; the
record stands without it, honestly unattached. The website-era lifecycle
(reminders, state verification, portal upload) is deliberately future.

TaxPeriod is the accumulator: jurisdiction × period rows derived from
invoices' stored truth, rebuilt idempotently (recompute-and-replace, so
re-running is drift-free by construction).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

CERT_TYPES = ("resale", "exempt_org", "government", "other")

# Product tax classes: 'inherit' = not yet reviewed (resolves TAXABLE,
# the default law); 'taxable' and 'exempt' are the operator's explicit
# marks. Nothing is guessed exempt.
PRODUCT_TAX_CLASSES = ("inherit", "taxable", "exempt")


class TaxCertificate(Base):
    __tablename__ = "tax_certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    sales_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True, index=True)
    cert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    cert_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_through: Mapped[date | None] = mapped_column(Date, nullable=True)
    vault_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    customer = relationship("Customer")

    def is_valid_on(self, on: date) -> bool:
        """Dated validity does the work — expired is simply not valid."""
        if not self.is_active:
            return False
        if self.valid_from and on < self.valid_from:
            return False
        if self.valid_through and on > self.valid_through:
            return False
        return True


class TaxPeriod(Base):
    __tablename__ = "tax_periods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-Q2" (NY sales-tax quarter)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    jurisdiction_name: Mapped[str] = mapped_column(String(120), nullable=False)
    gross_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    taxable_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    exempt_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    exempt_by_class: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tax_computed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gaps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_accumulated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
