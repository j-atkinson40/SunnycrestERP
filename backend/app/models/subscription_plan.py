import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubscriptionPlan(Base):
    """Billing plan definition — maps to a Stripe Price/Product."""

    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    price_yearly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )

    # Limits
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Feature inclusion (JSON list of module keys)
    included_modules: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: ["core", "sales", "purchasing", "inventory"]

    # Stripe mapping
    stripe_product_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_monthly_price_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_yearly_price_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
