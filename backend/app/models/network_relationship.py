import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkRelationship(Base):
    """Cross-tenant relationship between two companies."""

    __tablename__ = "network_relationships"
    __table_args__ = (
        Index("ix_network_rel_requesting", "requesting_company_id"),
        Index("ix_network_rel_target", "target_company_id"),
        Index(
            "ix_network_rel_pair",
            "requesting_company_id",
            "target_company_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    requesting_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    target_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # supplier, customer, partner, affiliated
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, active, suspended, terminated
    permissions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: what data the partner can see
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    requesting_company = relationship("Company", foreign_keys=[requesting_company_id])
    target_company = relationship("Company", foreign_keys=[target_company_id])
