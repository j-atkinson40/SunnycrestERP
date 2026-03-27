"""Data migration run tracking model."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DataMigrationRun(Base):
    __tablename__ = "data_migration_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_progress"
    )  # in_progress | complete | partial | failed | rolled_back
    cutover_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_system: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # sage_100 | quickbooks | other

    # --- Import counts ---
    gl_accounts_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gl_accounts_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customers_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customers_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ar_invoices_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ar_invoices_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vendors_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vendors_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ap_bills_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ap_bills_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Financial totals ---
    total_ar_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    total_ap_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # --- Logs ---
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # --- Timestamps ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Metadata ---
    initiated_by: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # owner | accountant | admin

    # --- Rollback ---
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rolled_back_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # --- Relationships ---
    company = relationship("Company")
    rolled_back_by_user = relationship("User", foreign_keys=[rolled_back_by])
