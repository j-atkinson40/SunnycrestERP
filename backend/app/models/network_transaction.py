import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkTransaction(Base):
    """Cross-tenant transaction record with full audit trail."""

    __tablename__ = "network_transactions"
    __table_args__ = (
        Index("ix_network_tx_relationship", "relationship_id"),
        Index("ix_network_tx_source", "source_company_id"),
        Index("ix_network_tx_target", "target_company_id"),
        Index("ix_network_tx_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    relationship_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("network_relationships.id"), nullable=False
    )
    source_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    target_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # order, invoice, payment, case_transfer, status_update
    source_record_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g., "purchase_order", "vendor_bill"
    source_record_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    target_record_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    target_record_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    payload: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON payload snapshot
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, completed, failed, reversed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    relationship_obj = relationship("NetworkRelationship", foreign_keys=[relationship_id])
    source_company = relationship("Company", foreign_keys=[source_company_id])
    target_company = relationship("Company", foreign_keys=[target_company_id])
