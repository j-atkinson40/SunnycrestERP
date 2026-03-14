from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Subscription Plans
# ---------------------------------------------------------------------------


class SubscriptionPlanCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    price_monthly: Decimal = Decimal("0.00")
    price_yearly: Decimal = Decimal("0.00")
    currency: str = "USD"
    max_users: int | None = None
    max_storage_gb: int | None = None
    included_modules: str | None = None  # JSON string
    stripe_product_id: str | None = None
    stripe_monthly_price_id: str | None = None
    stripe_yearly_price_id: str | None = None
    sort_order: int = 0


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_monthly: Decimal | None = None
    price_yearly: Decimal | None = None
    max_users: int | None = None
    max_storage_gb: int | None = None
    included_modules: str | None = None
    stripe_product_id: str | None = None
    stripe_monthly_price_id: str | None = None
    stripe_yearly_price_id: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    price_monthly: Decimal
    price_yearly: Decimal
    currency: str
    max_users: int | None = None
    max_storage_gb: int | None = None
    included_modules: str | None = None
    stripe_product_id: str | None = None
    stripe_monthly_price_id: str | None = None
    stripe_yearly_price_id: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


class SubscriptionCreate(BaseModel):
    company_id: str
    plan_id: str
    billing_interval: str = "monthly"
    stripe_customer_id: str | None = None


class SubscriptionResponse(BaseModel):
    id: str
    company_id: str
    plan_id: str
    status: str
    billing_interval: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_end: datetime | None = None
    canceled_at: datetime | None = None
    current_user_count: int
    current_storage_mb: int
    created_at: datetime
    updated_at: datetime
    plan: SubscriptionPlanResponse | None = None
    company_name: str | None = None

    class Config:
        from_attributes = True


class ChangePlanRequest(BaseModel):
    plan_id: str
    billing_interval: str | None = None


class PaginatedSubscriptions(BaseModel):
    items: list[SubscriptionResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Billing Events
# ---------------------------------------------------------------------------


class BillingEventResponse(BaseModel):
    id: str
    company_id: str
    subscription_id: str | None = None
    event_type: str
    amount: Decimal | None = None
    currency: str
    stripe_event_id: str | None = None
    stripe_invoice_id: str | None = None
    metadata_json: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedBillingEvents(BaseModel):
    items: list[BillingEventResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Billing Stats
# ---------------------------------------------------------------------------


class BillingStats(BaseModel):
    total_subscriptions: int
    active_subscriptions: int
    past_due: int
    canceled: int
    mrr: Decimal  # Monthly Recurring Revenue
    total_revenue_30d: Decimal
