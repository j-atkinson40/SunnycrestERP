import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LegacyProof(Base):
    __tablename__ = "legacy_proofs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)
    personalization_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    legacy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    print_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_urn: Mapped[bool] = mapped_column(Boolean, server_default="false")
    inscription_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_additional: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    deceased_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    proof_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tif_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), server_default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    family_approved: Mapped[bool] = mapped_column(Boolean, server_default="false")
    proof_emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proof_emailed_to: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    watermarked: Mapped[bool] = mapped_column(Boolean, server_default="false")
    watermark_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")
    customer = relationship("Customer", foreign_keys=[customer_id])
    versions = relationship("LegacyProofVersion", back_populates="legacy_proof", order_by="LegacyProofVersion.version_number")


class LegacyProofVersion(Base):
    __tablename__ = "legacy_proof_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    legacy_proof_id: Mapped[str] = mapped_column(String(36), ForeignKey("legacy_proofs.id"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    proof_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tif_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_additional: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    kept: Mapped[bool] = mapped_column(Boolean, server_default="true")

    legacy_proof = relationship("LegacyProof", back_populates="versions")


class LegacyProofPhoto(Base):
    __tablename__ = "legacy_proof_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    legacy_proof_id: Mapped[str] = mapped_column(String(36), ForeignKey("legacy_proofs.id"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
