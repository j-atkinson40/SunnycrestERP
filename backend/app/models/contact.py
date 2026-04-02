"""Contact — CRM contact linked to a CompanyEntity.

Each contact represents a person at a real-world company (funeral home,
vendor, cemetery, etc). A contact can optionally be linked to a platform
user for auto-population.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    master_company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Contact info
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_ext: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Role at their company
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Flags
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    receives_invoices: Mapped[bool] = mapped_column(Boolean, server_default="false")
    receives_legacy_proofs: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Platform link
    linked_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    linked_auto: Mapped[bool] = mapped_column(Boolean, server_default="false")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    master_company = relationship("CompanyEntity", foreign_keys=[master_company_id])
    linked_user = relationship("User", foreign_keys=[linked_user_id])
