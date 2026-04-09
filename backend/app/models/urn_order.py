"""UrnOrder model — urn sales orders tied to funeral homes."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UrnOrder(Base):
    __tablename__ = "urn_orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Case linkage — deferred to future phase
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Funeral home
    funeral_home_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("company_entities.id"), nullable=True, index=True
    )
    fh_contact_email: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Product
    urn_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("urn_products.id"), nullable=False, index=True
    )

    # Fulfillment
    fulfillment_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # stocked | drop_ship — copied from product at creation
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    need_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # with_vault | separate_delivery | will_call

    # Status pipeline
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", index=True
    )
    # draft | confirmed | engraving_pending | proof_pending |
    # awaiting_fh_approval | fh_approved | fh_changes_requested |
    # proof_approved | fulfilling | delivered | cancelled

    # Wilbert tracking
    wilbert_order_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    tracking_number: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    expected_arrival_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    # Pricing snapshot (captured at confirmation)
    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    unit_retail: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Intake
    intake_channel: Mapped[str] = mapped_column(
        String(30), default="manual"
    )  # manual | email_intake | call_intelligence

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft delete + audit
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])
    funeral_home = relationship("CompanyEntity", foreign_keys=[funeral_home_id])
    urn_product = relationship("UrnProduct", foreign_keys=[urn_product_id])
    engraving_jobs = relationship(
        "UrnEngravingJob", back_populates="urn_order", cascade="all, delete-orphan"
    )
    created_by_user = relationship("User", foreign_keys=[created_by])
