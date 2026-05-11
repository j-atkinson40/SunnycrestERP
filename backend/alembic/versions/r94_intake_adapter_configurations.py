"""Phase R-6.2a — Intake adapter substrate tables + cascade extensions.

R-6.2 introduces two new intake adapters (form, file) parallel to the
email adapter from R-6.1. The cascade is source-agnostic: form
submissions + file uploads enter the same three-tier classification
pipeline. R-6.2a ships the backend substrate; R-6.2b ships the
frontend portal pages.

Schema:

  ``intake_form_configurations`` — per-adapter form configuration with
  three-scope inheritance (platform_default / vertical_default /
  tenant_override). ``form_schema`` JSONB carries field definitions;
  resolver walks tenant → vertical → platform at READ time, matching
  the R-6.1 + platform_themes canon.

  ``intake_file_configurations`` — per-adapter file upload point
  configuration. ``allowed_content_types`` + ``max_file_size_bytes``
  enforce server-side validation. ``r2_key_prefix_template`` builds
  the canonical R2 key on upload.

  ``intake_form_submissions`` — append-only record table for form
  submissions. ``submitted_data`` JSONB carries the family's input;
  ``submitter_metadata`` JSONB captures IP + user_agent for spam
  triage. Per-row denormalized classification outcome (tier,
  workflow_id, workflow_run_id, reasoning) stored directly — preserves
  R-6.1's email-bound ``workflow_email_classifications`` table
  untouched. Cross-source audit unification deferred to R-6.x hygiene.

  ``intake_file_uploads`` — append-only record table for file uploads.
  ``r2_key`` is the canonical R2 storage key; ``content_type`` +
  ``size_bytes`` reflect the upload's actual values (server-verified).

  ``tenant_workflow_email_rules.adapter_type`` discriminator added so
  a tenant can author rules per adapter type. Defaults to ``"email"``
  for backward compat with R-6.1 rules. ``match_conditions`` JSONB
  shape varies per adapter_type; tier_1_rules.evaluate dispatches
  based on adapter_type.

Indexes:

  ``ix_intake_form_configurations_slug_lookup`` partial unique on
  (tenant_id, slug) WHERE is_active=true AND tenant_id IS NOT NULL
  — tenant-scope slug uniqueness for tenant_override rows.

  ``ix_intake_form_configurations_vertical_slug`` partial unique on
  (vertical, slug) WHERE is_active=true AND tenant_id IS NULL AND
  vertical IS NOT NULL — vertical-scope slug uniqueness.

  ``ix_intake_form_configurations_platform_slug`` partial unique on
  (slug) WHERE is_active=true AND tenant_id IS NULL AND vertical IS
  NULL — platform-scope slug uniqueness.

  ``ix_intake_form_submissions_tenant_recent`` on (tenant_id,
  received_at DESC) — admin recent submissions list.

  Same triple for ``intake_file_configurations`` + same composite
  index for ``intake_file_uploads``.

Seeds:

  Three canonical vertical_default rows for funeral_home:
    - form: ``personalization-request`` (deceased_name +
      relationship + preferred_personalization + family_contact_*).
    - file: ``death-certificate`` (PDF only, 10MB, single file).
    - file: ``personalization-documents`` (PDF/JPEG/PNG, 50MB,
      multiple files).

Down: drops indexes + tables + the adapter_type column cleanly.
Reversible.

Revision ID: r94_intake_adapter_configurations
Revises: r93_workflow_email_classification
Create Date: 2026-05-11
"""
from typing import Sequence, Union
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "r94_intake_adapter_configurations"
down_revision: Union[str, Sequence[str], None] = "r93_workflow_email_classification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FORM_CFG = "intake_form_configurations"
_FILE_CFG = "intake_file_configurations"
_FORM_SUB = "intake_form_submissions"
_FILE_UP = "intake_file_uploads"

_IX_FORM_CFG_TENANT_SLUG = "ix_intake_form_configurations_slug_lookup"
_IX_FORM_CFG_VERTICAL_SLUG = "ix_intake_form_configurations_vertical_slug"
_IX_FORM_CFG_PLATFORM_SLUG = "ix_intake_form_configurations_platform_slug"
_IX_FILE_CFG_TENANT_SLUG = "ix_intake_file_configurations_slug_lookup"
_IX_FILE_CFG_VERTICAL_SLUG = "ix_intake_file_configurations_vertical_slug"
_IX_FILE_CFG_PLATFORM_SLUG = "ix_intake_file_configurations_platform_slug"
_IX_FORM_SUB_TENANT_RECENT = "ix_intake_form_submissions_tenant_recent"
_IX_FILE_UP_TENANT_RECENT = "ix_intake_file_uploads_tenant_recent"


def _conn():
    return op.get_bind()


def _table_exists(name: str) -> bool:
    insp = sa.inspect(_conn())
    return name in insp.get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    insp = sa.inspect(_conn())
    if not _table_exists(table):
        return False
    indexes = insp.get_indexes(table)
    return any(idx["name"] == index_name for idx in indexes)


def _column_exists(table: str, column: str) -> bool:
    insp = sa.inspect(_conn())
    if not _table_exists(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


# Canonical vertical_default form_schema for personalization-request.
_PERSONALIZATION_REQUEST_SCHEMA = {
    "version": "1.0",
    "fields": [
        {
            "id": "deceased_name",
            "type": "text",
            "label": "Name of the person who passed away",
            "required": True,
            "max_length": 200,
        },
        {
            "id": "relationship_to_deceased",
            "type": "select",
            "label": "Your relationship",
            "required": True,
            "options": [
                {"value": "spouse", "label": "Spouse"},
                {"value": "child", "label": "Child"},
                {"value": "parent", "label": "Parent"},
                {"value": "sibling", "label": "Sibling"},
                {"value": "other_family", "label": "Other family member"},
                {"value": "friend", "label": "Friend"},
            ],
        },
        {
            "id": "preferred_personalization",
            "type": "textarea",
            "label": "Tell us what you'd like included",
            "required": True,
            "help_text": (
                "Photos, religious symbols, hobbies, military service, "
                "anything meaningful."
            ),
            "max_length": 5000,
        },
        {
            "id": "family_contact_name",
            "type": "text",
            "label": "Your name",
            "required": True,
            "max_length": 200,
        },
        {
            "id": "family_contact_email",
            "type": "email",
            "label": "Email to reach you at",
            "required": True,
        },
        {
            "id": "family_contact_phone",
            "type": "phone",
            "label": "Phone (optional)",
            "required": False,
        },
    ],
    "captcha_required": True,
}


_DEATH_CERTIFICATE_METADATA_SCHEMA = {
    "version": "1.0",
    "fields": [
        {
            "id": "uploader_name",
            "type": "text",
            "label": "Your name",
            "required": True,
        },
        {
            "id": "uploader_email",
            "type": "email",
            "label": "Email",
            "required": True,
        },
        {
            "id": "deceased_name",
            "type": "text",
            "label": "Name on the certificate",
            "required": True,
        },
    ],
    "captcha_required": True,
}


_PERSONALIZATION_DOCUMENTS_METADATA_SCHEMA = {
    "version": "1.0",
    "fields": [
        {
            "id": "uploader_name",
            "type": "text",
            "label": "Your name",
            "required": True,
        },
        {
            "id": "uploader_email",
            "type": "email",
            "label": "Email",
            "required": True,
        },
        {
            "id": "description",
            "type": "textarea",
            "label": "Brief description",
            "required": False,
        },
    ],
    "captcha_required": True,
}


def upgrade() -> None:
    # ── tenant_workflow_email_rules.adapter_type ──────────────────
    # Discriminator so a tenant can author rules per adapter type.
    # Default "email" preserves R-6.1 backward compat.
    if not _column_exists("tenant_workflow_email_rules", "adapter_type"):
        op.add_column(
            "tenant_workflow_email_rules",
            sa.Column(
                "adapter_type",
                sa.String(32),
                nullable=False,
                server_default=sa.text("'email'"),
            ),
        )
        op.create_check_constraint(
            "ck_tenant_workflow_email_rules_adapter_type",
            "tenant_workflow_email_rules",
            "adapter_type IN ('email', 'form', 'file')",
        )

    # ── intake_form_configurations ────────────────────────────────
    if not _table_exists(_FORM_CFG):
        op.create_table(
            _FORM_CFG,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=True,
                index=True,
            ),
            sa.Column("vertical", sa.String(50), nullable=True),
            sa.Column("scope", sa.String(32), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("slug", sa.String(128), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "form_schema",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("success_message", sa.Text, nullable=True),
            sa.Column(
                "notification_email_template_id",
                sa.String(36),
                nullable=True,
            ),
            sa.Column(
                "is_active",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "updated_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
                name="ck_intake_form_configurations_scope",
            ),
        )

    op.create_index(
        _IX_FORM_CFG_TENANT_SLUG,
        _FORM_CFG,
        ["tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NOT NULL"
        ),
    )
    op.create_index(
        _IX_FORM_CFG_VERTICAL_SLUG,
        _FORM_CFG,
        ["vertical", "slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NULL AND vertical IS NOT NULL"
        ),
    )
    op.create_index(
        _IX_FORM_CFG_PLATFORM_SLUG,
        _FORM_CFG,
        ["slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NULL AND vertical IS NULL"
        ),
    )

    # ── intake_file_configurations ────────────────────────────────
    if not _table_exists(_FILE_CFG):
        op.create_table(
            _FILE_CFG,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=True,
                index=True,
            ),
            sa.Column("vertical", sa.String(50), nullable=True),
            sa.Column("scope", sa.String(32), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("slug", sa.String(128), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "allowed_content_types",
                JSONB,
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "max_file_size_bytes",
                sa.BigInteger,
                nullable=False,
                server_default=sa.text("10485760"),
            ),
            sa.Column(
                "max_file_count",
                sa.Integer,
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column(
                "r2_key_prefix_template",
                sa.String(255),
                nullable=False,
                server_default=sa.text(
                    "'tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}'"
                ),
            ),
            sa.Column(
                "metadata_schema",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("success_message", sa.Text, nullable=True),
            sa.Column(
                "notification_email_template_id",
                sa.String(36),
                nullable=True,
            ),
            sa.Column(
                "is_active",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "updated_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
                name="ck_intake_file_configurations_scope",
            ),
        )

    op.create_index(
        _IX_FILE_CFG_TENANT_SLUG,
        _FILE_CFG,
        ["tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NOT NULL"
        ),
    )
    op.create_index(
        _IX_FILE_CFG_VERTICAL_SLUG,
        _FILE_CFG,
        ["vertical", "slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NULL AND vertical IS NOT NULL"
        ),
    )
    op.create_index(
        _IX_FILE_CFG_PLATFORM_SLUG,
        _FILE_CFG,
        ["slug"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true AND tenant_id IS NULL AND vertical IS NULL"
        ),
    )

    # ── intake_form_submissions ───────────────────────────────────
    # Per-row denormalized classification outcome lives directly on
    # the submission. Cross-source audit unification deferred.
    if not _table_exists(_FORM_SUB):
        op.create_table(
            _FORM_SUB,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "config_id",
                sa.String(36),
                sa.ForeignKey(
                    "intake_form_configurations.id",
                    ondelete="RESTRICT",
                ),
                nullable=False,
            ),
            sa.Column(
                "submitted_data",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "submitter_metadata",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            # Denormalized classification outcome (post-cascade).
            sa.Column("classification_tier", sa.SmallInteger, nullable=True),
            sa.Column(
                "classification_workflow_id",
                sa.String(36),
                sa.ForeignKey("workflows.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "classification_workflow_run_id",
                sa.String(36),
                sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "classification_is_suppressed",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "classification_payload",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "classification_tier IS NULL OR classification_tier IN (1, 2, 3)",
                name="ck_intake_form_submissions_tier",
            ),
        )

    op.create_index(
        _IX_FORM_SUB_TENANT_RECENT,
        _FORM_SUB,
        ["tenant_id", "received_at"],
    )

    # ── intake_file_uploads ───────────────────────────────────────
    if not _table_exists(_FILE_UP):
        op.create_table(
            _FILE_UP,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "config_id",
                sa.String(36),
                sa.ForeignKey(
                    "intake_file_configurations.id",
                    ondelete="RESTRICT",
                ),
                nullable=False,
            ),
            sa.Column("r2_key", sa.String(512), nullable=False),
            sa.Column("original_filename", sa.String(512), nullable=False),
            sa.Column("content_type", sa.String(128), nullable=False),
            sa.Column("size_bytes", sa.BigInteger, nullable=False),
            sa.Column(
                "uploader_metadata",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            # Denormalized classification outcome (post-cascade).
            sa.Column("classification_tier", sa.SmallInteger, nullable=True),
            sa.Column(
                "classification_workflow_id",
                sa.String(36),
                sa.ForeignKey("workflows.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "classification_workflow_run_id",
                sa.String(36),
                sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "classification_is_suppressed",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "classification_payload",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "classification_tier IS NULL OR classification_tier IN (1, 2, 3)",
                name="ck_intake_file_uploads_tier",
            ),
        )

    op.create_index(
        _IX_FILE_UP_TENANT_RECENT,
        _FILE_UP,
        ["tenant_id", "received_at"],
    )

    # ── Seed canonical funeral_home vertical_default rows ─────────
    # Idempotent: skips when (vertical, slug) row already exists.
    _seed_funeral_defaults()


def _seed_funeral_defaults() -> None:
    """Idempotent seed of canonical funeral_home vertical_default rows.

    Re-running upgrade is a no-op when the rows are already present.
    """
    conn = _conn()

    # Personalization Request form
    existing = conn.execute(
        sa.text(
            "SELECT id FROM intake_form_configurations "
            "WHERE vertical = 'funeral_home' AND slug = 'personalization-request' "
            "AND tenant_id IS NULL AND is_active = true"
        )
    ).first()
    if existing is None:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO intake_form_configurations
                    (id, tenant_id, vertical, scope, name, slug, description,
                     form_schema, success_message, is_active)
                VALUES (
                    :id, NULL, 'funeral_home', 'vertical_default',
                    'Personalization Request',
                    'personalization-request',
                    'Family-facing form for collecting personalization '
                    'preferences for a memorial.',
                    CAST(:form_schema AS jsonb),
                    'Thank you. We''ve received your request and will be '
                    'in touch within 24 hours.',
                    true
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "form_schema": json.dumps(_PERSONALIZATION_REQUEST_SCHEMA),
            },
        )

    # Death Certificate file upload
    existing = conn.execute(
        sa.text(
            "SELECT id FROM intake_file_configurations "
            "WHERE vertical = 'funeral_home' AND slug = 'death-certificate' "
            "AND tenant_id IS NULL AND is_active = true"
        )
    ).first()
    if existing is None:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO intake_file_configurations
                    (id, tenant_id, vertical, scope, name, slug, description,
                     allowed_content_types, max_file_size_bytes, max_file_count,
                     r2_key_prefix_template, metadata_schema, success_message,
                     is_active)
                VALUES (
                    :id, NULL, 'funeral_home', 'vertical_default',
                    'Death Certificate',
                    'death-certificate',
                    'Family-facing upload point for the death certificate.',
                    CAST(:allowed_types AS jsonb),
                    10485760, 1,
                    'tenants/{{tenant_id}}/intake/death-certificate/{{upload_id}}',
                    CAST(:metadata_schema AS jsonb),
                    'Thank you. We''ve received the certificate.',
                    true
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "allowed_types": json.dumps(["application/pdf"]),
                "metadata_schema": json.dumps(
                    _DEATH_CERTIFICATE_METADATA_SCHEMA
                ),
            },
        )

    # Personalization Documents file upload
    existing = conn.execute(
        sa.text(
            "SELECT id FROM intake_file_configurations "
            "WHERE vertical = 'funeral_home' AND slug = 'personalization-documents' "
            "AND tenant_id IS NULL AND is_active = true"
        )
    ).first()
    if existing is None:
        conn.execute(
            sa.text(
                f"""
                INSERT INTO intake_file_configurations
                    (id, tenant_id, vertical, scope, name, slug, description,
                     allowed_content_types, max_file_size_bytes, max_file_count,
                     r2_key_prefix_template, metadata_schema, success_message,
                     is_active)
                VALUES (
                    :id, NULL, 'funeral_home', 'vertical_default',
                    'Personalization Documents',
                    'personalization-documents',
                    'Family-facing upload point for photos, written '
                    'memories, and other personalization materials.',
                    CAST(:allowed_types AS jsonb),
                    52428800, 10,
                    'tenants/{{tenant_id}}/intake/personalization-documents/{{upload_id}}',
                    CAST(:metadata_schema AS jsonb),
                    'Thank you. We''ve received your materials.',
                    true
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "allowed_types": json.dumps(
                    ["application/pdf", "image/jpeg", "image/png"]
                ),
                "metadata_schema": json.dumps(
                    _PERSONALIZATION_DOCUMENTS_METADATA_SCHEMA
                ),
            },
        )


def downgrade() -> None:
    if _index_exists(_FILE_UP, _IX_FILE_UP_TENANT_RECENT):
        op.drop_index(_IX_FILE_UP_TENANT_RECENT, table_name=_FILE_UP)
    if _table_exists(_FILE_UP):
        op.drop_table(_FILE_UP)

    if _index_exists(_FORM_SUB, _IX_FORM_SUB_TENANT_RECENT):
        op.drop_index(_IX_FORM_SUB_TENANT_RECENT, table_name=_FORM_SUB)
    if _table_exists(_FORM_SUB):
        op.drop_table(_FORM_SUB)

    for idx in (
        _IX_FILE_CFG_PLATFORM_SLUG,
        _IX_FILE_CFG_VERTICAL_SLUG,
        _IX_FILE_CFG_TENANT_SLUG,
    ):
        if _index_exists(_FILE_CFG, idx):
            op.drop_index(idx, table_name=_FILE_CFG)
    if _table_exists(_FILE_CFG):
        op.drop_table(_FILE_CFG)

    for idx in (
        _IX_FORM_CFG_PLATFORM_SLUG,
        _IX_FORM_CFG_VERTICAL_SLUG,
        _IX_FORM_CFG_TENANT_SLUG,
    ):
        if _index_exists(_FORM_CFG, idx):
            op.drop_index(idx, table_name=_FORM_CFG)
    if _table_exists(_FORM_CFG):
        op.drop_table(_FORM_CFG)

    # Drop adapter_type column from tenant_workflow_email_rules.
    if _column_exists("tenant_workflow_email_rules", "adapter_type"):
        # Drop the CHECK constraint first (PG names it predictably).
        try:
            op.drop_constraint(
                "ck_tenant_workflow_email_rules_adapter_type",
                "tenant_workflow_email_rules",
                type_="check",
            )
        except Exception:
            pass
        op.drop_column("tenant_workflow_email_rules", "adapter_type")
