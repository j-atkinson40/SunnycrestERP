import json
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

    # Tenant-specific settings (JSON blob — spring_burials_enabled, etc.)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Facility address (separate from mailing address above)
    company_legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facility_address_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    facility_address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facility_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facility_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    facility_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    facility_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    facility_longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 7), nullable=True)
    company_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # NPCA certification
    npca_certification_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="unknown"
    )
    npca_certification_set_by: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Spring burials
    spring_burials_known_at_creation: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    # Internal notes (platform admin only)
    internal_admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    @property
    def settings(self) -> dict:
        if not self.settings_json:
            return {}
        return json.loads(self.settings_json)

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        s = self.settings
        s[key] = value
        self.settings_json = json.dumps(s)

    users = relationship("User", back_populates="company", foreign_keys="[User.company_id]")
    roles = relationship("Role", back_populates="company", cascade="all, delete-orphan")
    children = relationship("Company", back_populates="parent", foreign_keys="[Company.parent_company_id]")
    parent = relationship("Company", back_populates="children", remote_side="[Company.id]", foreign_keys="[Company.parent_company_id]")
