import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeeRateConfig(Base):
    """Configurable fee rates per transaction type. All rates default to zero."""

    __tablename__ = "fee_rate_configs"
    __table_args__ = (
        Index("ix_fee_rate_tx_type", "transaction_type"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # order, invoice, payment, case_transfer
    fee_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="transaction_percent"
    )  # transaction_percent, flat_fee, subscription_addon
    rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0.0000")
    )
    min_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    max_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PlatformFee(Base):
    """Fee record attached to a cross-tenant network transaction."""

    __tablename__ = "platform_fees"
    __table_args__ = (
        Index("ix_platform_fee_tx", "network_transaction_id"),
        Index("ix_platform_fee_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    network_transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_transactions.id"),
        nullable=False,
    )
    fee_rate_config_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("fee_rate_configs.id"), nullable=True
    )
    fee_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # transaction_percent, flat_fee
    rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    calculated_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, collected, waived
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    waived_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    waived_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    transaction = relationship("NetworkTransaction", foreign_keys=[network_transaction_id])
