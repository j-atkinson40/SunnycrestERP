import uuid
from datetime import datetime, timezone

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(63), unique=True, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Vertical / preset type
    vertical: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Address
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Configuration
    timezone: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="UTC"
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Financial Settings
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    default_payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_terms_options: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Email Settings
    email_from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Accounting Integration
    accounting_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )  # none, sage_csv, quickbooks_online — set during tenant onboarding
    accounting_config: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON blob for provider-specific settings (OAuth tokens, mappings, etc.)

    # Organizational Hierarchy
    parent_company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    hierarchy_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # corporate, regional, location
    hierarchy_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Materialized path: "corp1.region2.loc5"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", use_alter=True), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", use_alter=True), nullable=True
    )

    users = relationship("User", back_populates="company", foreign_keys="[User.company_id]")
    roles = relationship("Role", back_populates="company", cascade="all, delete-orphan")
    children = relationship("Company", back_populates="parent", foreign_keys="[Company.parent_company_id]")
    parent = relationship("Company", back_populates="children", remote_side="[Company.id]", foreign_keys="[Company.parent_company_id]")
