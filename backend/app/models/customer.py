import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "account_number", "company_id", name="uq_customer_account_company"
        ),
    )

    # --- Standard fields ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # --- Core info ---
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Shipping / primary address ---
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="US"
    )

    # --- Billing address ---
    billing_address_line1: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    billing_address_line2: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    billing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    billing_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Charge account ---
    credit_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    # --- Other ---
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Seasonal / Spring burial ---
    typical_opening_date: Mapped[str | None] = mapped_column(String(5), nullable=True)  # MM-DD
    winter_closure_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # MM-DD
    is_seasonal: Mapped[bool] = mapped_column(Boolean, default=False)
    opening_date_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Billing / Statements ---
    billing_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statement_delivery_method: Mapped[str] = mapped_column(String(20), server_default="digital")
    statement_template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receives_statements: Mapped[bool] = mapped_column(Boolean, server_default="true")
    statement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- Billing profile ---
    billing_profile: Mapped[str] = mapped_column(String(20), server_default="cod")
    receives_monthly_statement: Mapped[bool] = mapped_column(Boolean, server_default="false")
    payment_terms: Mapped[str] = mapped_column(String(20), server_default="cod")
    preferred_delivery_method: Mapped[str] = mapped_column(String(20), server_default="email")

    # --- Customer classification ---
    customer_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'funeral_home', 'contractor', 'cemetery', 'other'

    # --- Sage sync ---
    sage_customer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Relationships ---
    company = relationship("Company")
    contacts = relationship(
        "CustomerContact",
        back_populates="customer",
        order_by="CustomerContact.is_primary.desc()",
    )
    customer_notes = relationship(
        "CustomerNote",
        back_populates="customer",
        order_by="CustomerNote.created_at.desc()",
    )
