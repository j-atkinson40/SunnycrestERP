"""Pydantic schemas for Social Service Certificate endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SocialServiceCertificateSummary(BaseModel):
    """Returned in list views (e.g. pending approvals)."""

    id: str
    certificate_number: str
    status: str
    deceased_name: str | None = None
    funeral_home_name: str | None = None
    cemetery_name: str | None = None
    product_price: Decimal | None = None
    delivered_at: datetime | None = None
    generated_at: datetime

    model_config = {"from_attributes": True}


class SocialServiceCertificateDetail(SocialServiceCertificateSummary):
    """Full detail view with approval/void metadata."""

    order_id: str
    order_number: str | None = None
    approved_at: datetime | None = None
    approved_by_name: str | None = None
    voided_at: datetime | None = None
    voided_by_name: str | None = None
    void_reason: str | None = None
    sent_at: datetime | None = None
    email_sent_to: str | None = None

    model_config = {"from_attributes": True}


class VoidCertificateRequest(BaseModel):
    reason: str
