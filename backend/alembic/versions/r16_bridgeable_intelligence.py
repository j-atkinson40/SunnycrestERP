"""Bridgeable Intelligence — unified AI layer backbone (Phase 1).

Creates the managed prompt library, versioned prompts, model routing, execution
audit trail, A/B experiments, and chat conversations. No caller migrations here
— those happen in Phase 2.

Tables:
  intelligence_prompts            — prompt registry (platform + tenant overrides)
  intelligence_prompt_versions    — versioned content (immutable once activated)
  intelligence_model_routes       — route_key → concrete model ID + pricing
  intelligence_executions         — every AI call (regulatory audit trail)
  intelligence_experiments        — A/B tests between prompt versions
  intelligence_conversations      — Ask Bridgeable Assistant sessions
  intelligence_messages           — per-turn messages inside a conversation

Revision ID: r16_bridgeable_intelligence
Revises: fh_08_step_display_name
"""

from alembic import op
import sqlalchemy as sa


revision = "r16_bridgeable_intelligence"
down_revision = "fh_08_step_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Prompt registry ──────────────────────────────────────────────
    op.create_table(
        "intelligence_prompts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("caller_module", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_intelligence_prompts_company_key",
        "intelligence_prompts",
        ["company_id", "prompt_key"],
    )
    op.create_index(
        "ix_intelligence_prompts_domain",
        "intelligence_prompts",
        ["domain"],
    )
    op.create_index(
        "ix_intelligence_prompts_key",
        "intelligence_prompts",
        ["prompt_key"],
    )

    # ── 2. Prompt versions ──────────────────────────────────────────────
    op.create_table(
        "intelligence_prompt_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "prompt_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_template", sa.Text, nullable=False),
        sa.Column("variable_schema", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("response_schema", sa.JSON, nullable=True),
        sa.Column("model_preference", sa.String(64), nullable=False),
        sa.Column("temperature", sa.Float, nullable=False, server_default=sa.text("0.7")),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default=sa.text("4096")),
        sa.Column("force_json", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("supports_streaming", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("supports_tool_use", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("changelog", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_intelligence_prompt_version_number",
        "intelligence_prompt_versions",
        ["prompt_id", "version_number"],
    )
    op.create_index(
        "ix_intelligence_prompt_versions_status",
        "intelligence_prompt_versions",
        ["prompt_id", "status"],
    )

    # ── 3. Model routes ─────────────────────────────────────────────────
    op.create_table(
        "intelligence_model_routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_key", sa.String(64), nullable=False, unique=True),
        sa.Column("primary_model", sa.String(128), nullable=False),
        sa.Column("fallback_model", sa.String(128), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="anthropic"),
        sa.Column("input_cost_per_million", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("output_cost_per_million", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("max_tokens_default", sa.Integer, nullable=False, server_default=sa.text("4096")),
        sa.Column("temperature_default", sa.Float, nullable=False, server_default=sa.text("0.7")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── 4. Experiments (must come before executions because executions FK it) ──
    op.create_table(
        "intelligence_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "prompt_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column(
            "version_a_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_b_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("traffic_split", sa.Integer, nullable=False, server_default="50"),
        sa.Column("min_sample_size", sa.Integer, nullable=False, server_default="100"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "winner_version_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompt_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conclusion_notes", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 5. Conversations (must come before messages) ────────────────────
    op.create_table(
        "intelligence_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context_snapshot", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_intelligence_conversations_company",
        "intelligence_conversations",
        ["company_id", "last_message_at"],
    )

    # ── 6. Executions — the audit trail ─────────────────────────────────
    op.create_table(
        "intelligence_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prompt_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prompt_version_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompt_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_preference", sa.String(64), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("input_variables", sa.JSON, nullable=True),
        sa.Column("rendered_system_prompt", sa.Text, nullable=True),
        sa.Column("rendered_user_prompt", sa.Text, nullable=True),
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("response_parsed", sa.JSON, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        # Caller linkage
        sa.Column("caller_module", sa.String(128), nullable=True),
        sa.Column("caller_entity_type", sa.String(64), nullable=True),
        sa.Column("caller_entity_id", sa.String(36), nullable=True),
        sa.Column(
            "caller_workflow_run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("caller_workflow_step_id", sa.String(36), nullable=True),
        sa.Column(
            "caller_workflow_run_step_id",
            sa.String(36),
            sa.ForeignKey("workflow_run_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "caller_agent_job_id",
            sa.String(36),
            sa.ForeignKey("agent_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "caller_conversation_id",
            sa.String(36),
            sa.ForeignKey("intelligence_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("caller_command_bar_session_id", sa.String(36), nullable=True),
        sa.Column(
            "experiment_id",
            sa.String(36),
            sa.ForeignKey("intelligence_experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("experiment_variant", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_intelligence_executions_company_created",
        "intelligence_executions",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_intelligence_executions_prompt_created",
        "intelligence_executions",
        ["prompt_id", "created_at"],
    )
    op.create_index(
        "ix_intelligence_executions_caller_module",
        "intelligence_executions",
        ["caller_module", "created_at"],
    )
    op.create_index(
        "ix_intelligence_executions_caller_entity",
        "intelligence_executions",
        ["caller_entity_type", "caller_entity_id"],
    )
    op.create_index(
        "ix_intelligence_executions_workflow_run",
        "intelligence_executions",
        ["caller_workflow_run_id"],
    )
    op.create_index(
        "ix_intelligence_executions_agent_job",
        "intelligence_executions",
        ["caller_agent_job_id"],
    )
    op.create_index(
        "ix_intelligence_executions_experiment",
        "intelligence_executions",
        ["experiment_id", "experiment_variant"],
    )

    # ── 7. Conversation messages ────────────────────────────────────────
    op.create_table(
        "intelligence_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("intelligence_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "execution_id",
            sa.String(36),
            sa.ForeignKey("intelligence_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_intelligence_messages_conversation",
        "intelligence_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_intelligence_messages_conversation", table_name="intelligence_messages")
    op.drop_table("intelligence_messages")
    op.drop_index("ix_intelligence_executions_experiment", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_agent_job", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_workflow_run", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_caller_entity", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_caller_module", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_prompt_created", table_name="intelligence_executions")
    op.drop_index("ix_intelligence_executions_company_created", table_name="intelligence_executions")
    op.drop_table("intelligence_executions")
    op.drop_index("ix_intelligence_conversations_company", table_name="intelligence_conversations")
    op.drop_table("intelligence_conversations")
    op.drop_table("intelligence_experiments")
    op.drop_table("intelligence_model_routes")
    op.drop_index("ix_intelligence_prompt_versions_status", table_name="intelligence_prompt_versions")
    op.drop_constraint("uq_intelligence_prompt_version_number", "intelligence_prompt_versions", type_="unique")
    op.drop_table("intelligence_prompt_versions")
    op.drop_index("ix_intelligence_prompts_key", table_name="intelligence_prompts")
    op.drop_index("ix_intelligence_prompts_domain", table_name="intelligence_prompts")
    op.drop_constraint("uq_intelligence_prompts_company_key", "intelligence_prompts", type_="unique")
    op.drop_table("intelligence_prompts")
