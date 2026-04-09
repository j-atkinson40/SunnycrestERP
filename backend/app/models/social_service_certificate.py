"""Social Service Certificate — delivery confirmation for government benefit orders."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SocialServiceCertificate(Base):
    """A delivery certificate generated for Social Service Graveliner orders.

    Not an invoice — this is a government-facing document that funeral homes
    retain on file for benefit program verification.

    Lifecycle: pending_approval -> approved -> sent  (happy path)
               pending_approval -> voided            (rejected)
               approved -> voided                    (post-approval void)
    """

    __tablename__ = "social_service_certificates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    certificate_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    # Format: "{order.number}-SSC"  e.g. "SO-2025-0142-SSC"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales_orders.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_approval"
    )
    # pending_approval, approved, voided, sent

    pdf_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    order = relationship("SalesOrder", back_populates="social_service_certificate")
    company = relationship("Company")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    voided_by = relationship("User", foreign_keys=[voided_by_id])
