import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LegacyEmailSettings(Base):
    __tablename__ = "legacy_email_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)
    sender_tier: Mapped[str] = mapped_column(String(20), server_default="bridgeable")
    reply_to_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_from_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    domain_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    resend_domain_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_email_subject: Mapped[str] = mapped_column(String(500), server_default="'Legacy Proof — {name}'")
    proof_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_email_reply_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    print_email_subject: Mapped[str] = mapped_column(String(500), server_default="'Legacy Ready — {name}, needed by {deadline}'")
    print_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_invoice_branding: Mapped[bool] = mapped_column(Boolean, server_default="true")
    header_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")


class LegacyFHEmailConfig(Base):
    __tablename__ = "legacy_fh_email_config"
    __table_args__ = (UniqueConstraint("company_id", "customer_id", name="uq_legacy_fh_email_config"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False)
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    custom_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer")
