import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subscription(Base):
    """Active subscription linking a company to a plan."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscription_company", "company_id"),
        Index("ix_subscription_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscription_plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active"
    )  # trialing, active, past_due, canceled, unpaid

    billing_interval: Mapped[str] = mapped_column(
        String(10), nullable=False, default="monthly"
    )  # monthly, yearly

    # Stripe
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Dates
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Usage metering
    current_user_count: Mapped[int] = mapped_column(default=0)
    current_storage_mb: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    company = relationship("Company", foreign_keys=[company_id])
    plan = relationship("SubscriptionPlan", foreign_keys=[plan_id])


class BillingEvent(Base):
    """Audit trail for billing events — payments, failures, plan changes."""

    __tablename__ = "billing_events"
    __table_args__ = (
        Index("ix_billing_event_company", "company_id"),
        Index("ix_billing_event_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    subscription_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subscriptions.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # payment_succeeded, payment_failed, plan_changed, subscription_canceled, trial_ending, dunning_started
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    stripe_event_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    stripe_invoice_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON for extra context
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
