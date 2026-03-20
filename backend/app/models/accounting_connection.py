"""Accounting connection model — tracks provider connections per tenant."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AccountingConnection(Base):
    __tablename__ = "accounting_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Provider: quickbooks_online | quickbooks_desktop | sage_100
    provider: Mapped[str] = mapped_column(String(50), nullable=False)

    # Status: not_started | connecting | connected | error | disconnected | skipped
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="not_started"
    )

    # Stage: select_software | connect | configure_sync | complete
    setup_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── QBO-specific ──────────────────────────────────────────────
    qbo_realm_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qbo_company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qbo_access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    qbo_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    qbo_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── QB Desktop-specific ───────────────────────────────────────
    qbd_file_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qbd_qwc_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qbd_last_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Sage 100-specific ─────────────────────────────────────────
    sage_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sage_connection_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # api | csv
    sage_api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sage_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sage_csv_schedule: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Sync configuration ────────────────────────────────────────
    sync_config = mapped_column(JSONB, nullable=True)
    account_mappings = mapped_column(JSONB, nullable=True)

    # ── Last sync info ────────────────────────────────────────────
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_records: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Accountant invite ─────────────────────────────────────────
    accountant_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accountant_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accountant_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accountant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Skip tracking ─────────────────────────────────────────────
    skip_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    skipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Connection info ───────────────────────────────────────────
    connected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    company = relationship("Company", foreign_keys=[company_id])
