"""VaultSupplier model — configures how a buyer tenant receives vaults."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class VaultSupplier(Base):
    __tablename__ = "vault_suppliers"
    __table_args__ = (
        UniqueConstraint("company_id", "vendor_id", name="uq_vault_supplier_company_vendor"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey("vendors.id"), nullable=False)
    supplier_tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)

    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    delivery_schedule: Mapped[str] = mapped_column(String(20), nullable=False, default="on_demand")
    delivery_days: Mapped[list] = mapped_column(JSONB, default=list)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
