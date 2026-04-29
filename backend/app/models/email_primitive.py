"""Email Primitive entity models — Phase W-4b Layer 1 Step 1.

All 17 entities for the Email Primitive (BRIDGEABLE_MASTER §3.26.15)
live in this single module. They share enough relationship topology
that splitting per-table would fragment the conceptual unit; future
phases may split if the file grows past comfort.

**Architectural separation reminder:** these models implement the
*conversation/thread/inbox* infrastructure (§3.26.15). The platform
already has *transactional-send* infrastructure (Phase D-7
DeliveryService + EmailService + email_sends + document_deliveries)
that handles fire-and-forget audit log of one-shot sends. The two
infrastructures coexist; the future ``TransactionalSendOnlyProvider``
stub *wraps* the existing DeliveryService rather than replacing it.

**Cross-tenant masking inheritance hooks** are present on every
relationship that crosses a tenant boundary (the
``cross_tenant_thread_pairing`` association in particular) — full
masking implementation defers to subsequent steps per §3.25.x
discipline. The hooks live as relationship+helper-method placeholders
that callers consult before reading sensitive fields.

**Per §3.26.15.13 Q1 decomposition:** my Session 2 §3.26.15.13 draft
described "email_user_status keyed on (thread_id, user_id)" as a
single conceptual entity. At implementation, this decomposed into
TWO tables — ``UserMessageRead`` (per-message read state, supports
re-marking individual messages unread) and ``EmailThreadStatus``
(per-thread archive/snooze/replied/flagged state). The conceptual
``email_user_status`` umbrella holds both; their state machines run
independently per the canonical per-user independence discipline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Vocabulary tuples (mirror migration CHECK constraints) ───────────
ACCOUNT_TYPES = ("shared", "personal")
PROVIDER_TYPES = ("gmail", "msgraph", "imap", "transactional")
ACCESS_LEVELS = ("read", "read_write", "admin")
SYNC_STATUSES = ("pending", "syncing", "synced", "error")
DIRECTIONS = ("inbound", "outbound")
PARTICIPANT_ROLES = ("from", "to", "cc", "bcc", "reply_to")
LINKAGE_SOURCES = (
    "manual_pre_link",
    "manual_post_link",
    "intelligence_inferred",
)
ATTACHMENT_STORAGE_KINDS = ("r2", "provider", "vault_item")


# ─────────────────────────────────────────────────────────────────────
# 1. EmailAccount — per-tenant email account configuration
# ─────────────────────────────────────────────────────────────────────


class EmailAccount(Base):
    __tablename__ = "email_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('shared', 'personal')",
            name="ck_email_accounts_account_type",
        ),
        CheckConstraint(
            "provider_type IN ('gmail', 'msgraph', 'imap', 'transactional')",
            name="ck_email_accounts_provider_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="shared"
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # provider_config holds provider-specific config + credentials.
    # Tokens stored encrypted at rest in subsequent step (Step 2 wires
    # encryption layer); Step 1 stubs accept plaintext placeholders.
    provider_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    signature_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_override: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Step 3 — per-account outbound gate (canon §3.26.15.5).
    # Defaults True; tenant admins toggle False to disable outbound
    # while keeping inbound sync flowing.
    outbound_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Step 2 — encrypted credential storage. Fernet-encrypted JSON blob
    # containing access_token / refresh_token / token_expiry (OAuth) OR
    # imap_password (IMAP). Encrypted under the platform-wide
    # CREDENTIAL_ENCRYPTION_KEY env var per the existing canon discipline
    # in app/services/credential_service.py. Per-row tenant isolation via
    # the tenant_id FK; NULL until first successful OAuth/credential
    # capture.
    encrypted_credentials: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_credential_op: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    last_credential_op_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Step 2 — initial backfill tracking (per §3.26.15.4).
    backfill_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    backfill_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_started"
    )
    backfill_progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    backfill_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    backfill_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    access_grants = relationship(
        "EmailAccountAccess",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    sync_state = relationship(
        "EmailAccountSyncState",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    threads = relationship(
        "EmailThread",
        back_populates="account",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 2. EmailAccountAccess — per-account user access junction
# ─────────────────────────────────────────────────────────────────────


class EmailAccountAccess(Base):
    __tablename__ = "email_account_access"
    __table_args__ = (
        CheckConstraint(
            "access_level IN ('read', 'read_write', 'admin')",
            name="ck_email_account_access_level",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    access_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="read"
    )
    granted_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    account = relationship("EmailAccount", back_populates="access_grants")
    user = relationship("User", foreign_keys=[user_id])
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


# ─────────────────────────────────────────────────────────────────────
# 3. EmailAccountSyncState — provider sync cursor + subscription state
# ─────────────────────────────────────────────────────────────────────


class EmailAccountSyncState(Base):
    __tablename__ = "email_account_sync_state"
    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'synced', 'error')",
            name="ck_email_sync_state_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_delta_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sync_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    sync_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Step 2 additions — circuit-breaker counter + provider-agnostic
    # cursor + sync mutex. last_provider_cursor supersedes the per-
    # provider cursor columns above (which stay for backward-compat
    # but become advisory; new code reads from last_provider_cursor).
    consecutive_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_provider_cursor: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    sync_in_progress: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_resource_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    account = relationship("EmailAccount", back_populates="sync_state")


# ─────────────────────────────────────────────────────────────────────
# 4. EmailThread — Thread entity
# ─────────────────────────────────────────────────────────────────────


class EmailThread(Base):
    __tablename__ = "email_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    participants_summary: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    first_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cross_tenant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    account = relationship("EmailAccount", back_populates="threads")
    messages = relationship(
        "EmailMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="EmailMessage.received_at",
    )
    participants = relationship(
        "EmailParticipant",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    user_status = relationship(
        "EmailThreadStatus",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    labels = relationship(
        "EmailThreadLabel",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    linkages = relationship(
        "EmailThreadLinkage",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    internal_comments = relationship(
        "InternalComment",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    assignment_log = relationship(
        "EmailThreadAssignmentLog",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="EmailThreadAssignmentLog.changed_at",
    )

    # Cross-tenant masking hook (placeholder per §3.25.x).
    # Step 1 returns False — no masking enforced yet. Subsequent steps
    # consult cross_tenant_thread_pairing + per-tenant data agreements
    # to determine which fields to mask for the caller.
    def is_field_masked_for(self, field: str, caller_tenant_id: str) -> bool:
        """Return True if ``field`` should be rendered as ``__MASKED__``
        for a caller from ``caller_tenant_id``.

        Step 1 always returns False (no masking enforced). Step 2+
        wires the cross-tenant masking discipline via §3.25.x.
        """
        return False


# ─────────────────────────────────────────────────────────────────────
# 5. EmailMessage — Message entity
# ─────────────────────────────────────────────────────────────────────


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_email_messages_direction",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    in_reply_to_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("email_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    is_draft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_internal_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Provider-specific raw payload retention per §3.26.15.4 hybrid
    # storage discipline. Cached body lives in body_html/body_text;
    # provider_message_id + this payload reconstitute provider-side.
    message_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Extracted entity references per §3.26.15.20 — populated by
    # Intelligence inference on inbound; pre-populated on outbound
    # via composer's pre-link affordance per §3.26.15.7.
    entity_references: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="messages")
    attachments = relationship(
        "EmailAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )
    participants = relationship(
        "MessageParticipant",
        back_populates="message",
        cascade="all, delete-orphan",
    )
    read_states = relationship(
        "UserMessageRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 6. EmailAttachment — hybrid storage attachment with vault promote
# ─────────────────────────────────────────────────────────────────────


class EmailAttachment(Base):
    __tablename__ = "email_attachments"
    __table_args__ = (
        CheckConstraint(
            "storage_kind IN ('r2', 'provider', 'vault_item')",
            name="ck_email_attachments_storage_kind",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="provider"
    )
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # When promoted-to-Vault (per §3.26.15.8 affordance), points at the
    # canonical VaultItem. Promotion is a step that copies bytes from
    # provider/r2 into the canonical storage_key on the VaultItem and
    # flips this column. Backward-compat: Step 1 ships the column;
    # promote-to-vault flow lands in Step 4+ (inbox UI).
    vault_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("vault_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_inline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    message = relationship("EmailMessage", back_populates="attachments")


# ─────────────────────────────────────────────────────────────────────
# 7. EmailParticipant — per-thread participant resolution
# ─────────────────────────────────────────────────────────────────────


class EmailParticipant(Base):
    __tablename__ = "email_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_company_entity_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="participants")
    message_roles = relationship(
        "MessageParticipant",
        back_populates="participant",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────────────────────
# 8. MessageParticipant — per-message role mapping junction
# ─────────────────────────────────────────────────────────────────────


class MessageParticipant(Base):
    __tablename__ = "message_participants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('from', 'to', 'cc', 'bcc', 'reply_to')",
            name="ck_message_participants_role",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    message = relationship("EmailMessage", back_populates="participants")
    participant = relationship(
        "EmailParticipant", back_populates="message_roles"
    )


# ─────────────────────────────────────────────────────────────────────
# 9. UserMessageRead — per-user-per-message read state (§3.26.15.13 Q1)
# ─────────────────────────────────────────────────────────────────────


class UserMessageRead(Base):
    __tablename__ = "user_message_read"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    message = relationship("EmailMessage", back_populates="read_states")
    user = relationship("User")


# ─────────────────────────────────────────────────────────────────────
# 10. EmailThreadStatus — per-user-per-thread status (§3.26.15.13 Q1)
# ─────────────────────────────────────────────────────────────────────


class EmailThreadStatus(Base):
    __tablename__ = "email_thread_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_snoozed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_replied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_flagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    flagged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    has_task: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    has_mention: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="user_status")
    user = relationship("User")


# ─────────────────────────────────────────────────────────────────────
# 11. InternalComment — Front-style teammate-only thread comments
# ─────────────────────────────────────────────────────────────────────


class InternalComment(Base):
    __tablename__ = "internal_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    mentioned_user_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    reply_to_comment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("internal_comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="internal_comments")
    author = relationship("User", foreign_keys=[author_user_id])


# ─────────────────────────────────────────────────────────────────────
# 12. EmailThreadAssignmentLog — ownership audit trail (§3.26.15.19)
# ─────────────────────────────────────────────────────────────────────


class EmailThreadAssignmentLog(Base):
    __tablename__ = "email_thread_assignment_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_from_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="assignment_log")


# ─────────────────────────────────────────────────────────────────────
# 13. EmailThreadLinkage — polymorphic linkage to entities (§3.26.15.7)
# ─────────────────────────────────────────────────────────────────────


class EmailThreadLinkage(Base):
    __tablename__ = "email_thread_linkages"
    __table_args__ = (
        CheckConstraint(
            "linkage_source IN ('manual_pre_link', 'manual_post_link', 'intelligence_inferred')",
            name="ck_email_thread_linkages_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    linked_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    linkage_source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    linked_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="linkages")


# ─────────────────────────────────────────────────────────────────────
# 14. CrossTenantThreadPairing — paired-thread junction across tenants
# ─────────────────────────────────────────────────────────────────────


class CrossTenantThreadPairing(Base):
    """Pairs two ``email_threads`` rows — one per paired tenant — into
    a single conceptual cross-tenant thread per §3.26.15.7 +
    §3.26.15.18.

    Each tenant has its **own copy** of the thread; this row tracks the
    pairing without merging state. Operational state changes (assign,
    archive, snooze) on tenant A's copy do NOT mirror to tenant B's
    copy. Cross-tenant masking per §3.25.x applies on read; full
    masking implementation defers to subsequent steps.
    """

    __tablename__ = "cross_tenant_thread_pairing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_a_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    thread_b_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_a_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    tenant_b_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    relationship_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("platform_tenant_relationships.id", ondelete="SET NULL"),
        nullable=True,
    )
    paired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    thread_a = relationship("EmailThread", foreign_keys=[thread_a_id])
    thread_b = relationship("EmailThread", foreign_keys=[thread_b_id])


# ─────────────────────────────────────────────────────────────────────
# 15. EmailLabel — tenant labels
# ─────────────────────────────────────────────────────────────────────


class EmailLabel(Base):
    __tablename__ = "email_labels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    threads = relationship(
        "EmailThreadLabel", back_populates="label", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────
# 16. EmailThreadLabel — thread ↔ label junction
# ─────────────────────────────────────────────────────────────────────


class EmailThreadLabel(Base):
    __tablename__ = "email_thread_labels"

    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("email_labels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    applied_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    thread = relationship("EmailThread", back_populates="labels")
    label = relationship("EmailLabel", back_populates="threads")


# ─────────────────────────────────────────────────────────────────────
# 17. EmailAuditLog — per-tenant email-action audit log (§3.26.15.8)
# ─────────────────────────────────────────────────────────────────────


class OAuthStateNonce(Base):
    """Short-lived signed-state record for OAuth CSRF protection.

    Step 2 issues a row at OAuth flow start (per ``GET /email-accounts/
    oauth/{provider}/authorize-url``) with a 10-minute expiry. The
    callback handler validates the nonce + tenant/user/provider match
    before exchanging the authorization code. Single-use:
    ``consumed_at`` flips to non-NULL on first successful validation.

    Pattern matches existing CSRF discipline elsewhere in the codebase
    (signing tokens, portal recovery tokens) — short-lived, single-use,
    scoped to the originating user.
    """

    __tablename__ = "oauth_state_nonces"

    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EmailAuditLog(Base):
    """Email-specific audit log.

    Distinct from the general ``audit_logs`` table because email events
    have email-specific shape (account_id linkage, provider context,
    cross-tenant pairing references) and the general audit log is
    already heavy. Subsequent steps may consolidate; for now, the
    Email primitive owns its audit channel per §3.26.15.8 discipline.
    """

    __tablename__ = "email_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
