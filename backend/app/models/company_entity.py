"""CompanyEntity — master CRM entity representing a real-world company or organization.

A CompanyEntity can simultaneously be a customer, vendor, cemetery, funeral home,
licensee, crematory, or print shop. Role flags control which facets are active.
Existing customers/vendors/cemeteries link here via master_company_id.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


class CompanyEntity(Base):
    __tablename__ = "company_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Address
    address_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), server_default="US")

    # Role flags — a company can be multiple things simultaneously
    is_customer: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_vendor: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_cemetery: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_funeral_home: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_licensee: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_crematory: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_print_shop: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Classification
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contractor_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_aggregate: Mapped[bool] = mapped_column(Boolean, server_default="false")
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification_reasons: Mapped[list] = mapped_column(JSONB, server_default="'[]'")
    original_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    name_cleanup_actions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    classification_reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    classification_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active_customer: Mapped[bool] = mapped_column(Boolean, server_default="false")
    first_order_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    google_places_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_places_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Billing group fields
    parent_company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("company_entities.id"), nullable=True
    )
    is_billing_group: Mapped[bool] = mapped_column(Boolean, server_default="false")
    billing_preference: Mapped[str] = mapped_column(
        String(30), server_default="separate"
    )  # separate | consolidated_single_payer | consolidated_split_payment

    # Cemetery location mapping — which tenant location fulfills jobs at this cemetery
    fulfilling_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    locations = relationship(
        "CompanyEntity",
        foreign_keys=[parent_company_id],
        backref=backref("parent_group", remote_side="CompanyEntity.id"),
    )
    fulfilling_location = relationship(
        "Company", foreign_keys=[fulfilling_location_id]
    )
