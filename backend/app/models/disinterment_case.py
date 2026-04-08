"""DisintermentCase — 5-stage pipeline: Intake → Quote → Signatures → Scheduled → Complete.

This is the core entity for the disinterment case management module.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DisintermentCase(Base):
    __tablename__ = "disinterment_cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    case_number: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True
    )  # DIS-{YYYY}-{NNNN}

    # Pipeline stage
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="intake"
    )
    # Valid statuses: intake, quoted, quote_accepted, signatures_pending,
    #   signatures_complete, scheduled, complete, cancelled

    # Decedent
    decedent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_death: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_burial: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_description: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )

    # Cemetery & location
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_entities.id"),
        nullable=True,
        index=True,
    )
    cemetery_lot_section: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    cemetery_lot_space: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    fulfilling_location_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )  # snapshot at case creation

    # Relationships — funeral home & contact
    funeral_home_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_entities.id"),
        nullable=True,
        index=True,
    )
    funeral_director_contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id"), nullable=True
    )
    next_of_kin: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'"
    )
    # [{name, email, phone, relationship}]

    # Intake form
    intake_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    intake_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    intake_submitted_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    # Quote
    quote_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("quotes.id"), nullable=True
    )
    accepted_quote_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    has_hazard_pay: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # DocuSign
    docusign_envelope_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    sig_funeral_home: Mapped[str] = mapped_column(
        String(20), server_default="not_sent"
    )
    sig_funeral_home_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sig_cemetery: Mapped[str] = mapped_column(
        String(20), server_default="not_sent"
    )
    sig_cemetery_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sig_next_of_kin: Mapped[str] = mapped_column(
        String(20), server_default="not_sent"
    )
    sig_next_of_kin_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sig_manufacturer: Mapped[str] = mapped_column(
        String(20), server_default="not_sent"
    )
    sig_manufacturer_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Scheduling & assignment
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_driver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    assigned_crew: Mapped[list] = mapped_column(
        JSONB, server_default="'[]'"
    )
    rotation_assignment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("union_rotation_assignments.id"),
        nullable=True,
    )

    # Completion
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=True
    )

    # Audit
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    cemetery = relationship("CompanyEntity", foreign_keys=[cemetery_id])
    funeral_home = relationship("CompanyEntity", foreign_keys=[funeral_home_id])
    funeral_director_contact = relationship("Contact")
    fulfilling_location = relationship("Company", foreign_keys=[fulfilling_location_id])
    quote = relationship("Quote")
    invoice = relationship("Invoice")
    assigned_driver = relationship("User", foreign_keys=[assigned_driver_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    rotation_assignment = relationship("UnionRotationAssignment")
