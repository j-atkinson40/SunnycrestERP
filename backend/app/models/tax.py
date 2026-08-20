"""Tax rate and jurisdiction models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaxRate(Base):
    __tablename__ = "tax_rates"
    __table_args__ = (UniqueConstraint("tenant_id", "rate_name", name="uq_tax_rate_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    rate_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    gl_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PlatformTaxRate(Base):
    """A taxing jurisdiction's rate, owned by the platform — r171 (TAX-3).

    ⚠️ THERE IS NO `tenant_id` AND THAT IS THE SAFETY PROPERTY. `wipe_tenant`
    deletes `tax_rates` filtered by tenant; a platform row carrying a tenant
    column — even a sentinel — would be reachable by a routine teardown. A query
    that filters `tenant_id` cannot name this table at all.

    ⚠️ A RATE CHANGE IS AN INSERT THAT CLOSES THE PRIOR ROW, NEVER AN UPDATE.
    `effective_to IS NULL` means in force. Overwriting `rate_percentage` would
    silently restate what an old invoice recomputes as — the defect
    `TaxRate` still has.

    `jurisdiction_code` is New York's four-digit reporting code, which is what
    an ST-100 is filed on. `county` is carried alongside because today's
    resolver is county-keyed; the two are not interchangeable (New York City is
    one code across five borough counties, and Yonkers differs from the rest of
    Westchester).
    """

    __tablename__ = "platform_tax_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    jurisdiction_code: Mapped[str] = mapped_column(String(8), nullable=False)
    jurisdiction_name: Mapped[str] = mapped_column(String(120), nullable=False)
    county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rate_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    enacted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_publication: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def is_in_force_on(self, on: date) -> bool:
        """Dated validity does the work, exactly as `TaxCertificate.is_valid_on`."""
        if on < self.effective_from:
            return False
        if self.effective_to and on >= self.effective_to:
            return False
        return True


class TaxJurisdiction(Base):
    __tablename__ = "tax_jurisdictions"
    __table_args__ = (UniqueConstraint("tenant_id", "state", "county", name="uq_jurisdiction_county"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    jurisdiction_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    county: Mapped[str] = mapped_column(String(100), nullable=False)
    zip_codes: Mapped[list | None] = mapped_column(ARRAY(String(10)), nullable=True)
    tax_rate_id: Mapped[str] = mapped_column(String(36), ForeignKey("tax_rates.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tax_rate = relationship("TaxRate", foreign_keys=[tax_rate_id])
