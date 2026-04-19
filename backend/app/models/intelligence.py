"""Bridgeable Intelligence models — unified AI layer backbone.

Seven tables:
  IntelligencePrompt            — prompt registry (platform + tenant overrides)
  IntelligencePromptVersion     — versioned content (never mutated once activated)
  IntelligenceModelRoute        — route_key → concrete model + pricing
  IntelligenceExecution         — every AI call (regulatory audit trail)
  IntelligenceExperiment        — A/B tests between prompt versions
  IntelligenceConversation      — Ask Bridgeable Assistant sessions
  IntelligenceMessage           — per-turn messages inside a conversation
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligencePrompt(Base):
    __tablename__ = "intelligence_prompts"
    __table_args__ = (
        UniqueConstraint("company_id", "prompt_key", name="uq_intelligence_prompts_company_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caller_module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    versions = relationship(
        "IntelligencePromptVersion",
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="IntelligencePromptVersion.version_number",
    )


class IntelligencePromptVersion(Base):
    __tablename__ = "intelligence_prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "prompt_id", "version_number", name="uq_intelligence_prompt_version_number"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prompt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    variable_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_preference: Mapped[str] = mapped_column(String(64), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    force_json: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_tool_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 2c-0b — multimodal support
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vision_content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prompt = relationship("IntelligencePrompt", back_populates="versions")


class IntelligenceModelRoute(Base):
    __tablename__ = "intelligence_model_routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    route_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    primary_model: Mapped[str] = mapped_column(String(128), nullable=False)
    fallback_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="anthropic")
    input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    output_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    max_tokens_default: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    temperature_default: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class IntelligenceExperiment(Base):
    __tablename__ = "intelligence_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    prompt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_a_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_b_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    traffic_split: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    min_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    winner_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    conclusion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntelligenceConversation(Base):
    __tablename__ = "intelligence_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    messages = relationship(
        "IntelligenceMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="IntelligenceMessage.created_at",
    )


class IntelligenceExecution(Base):
    __tablename__ = "intelligence_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    prompt_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_preference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rendered_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    caller_module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    caller_entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caller_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    caller_workflow_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_workflow_step_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    caller_workflow_run_step_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_run_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_agent_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_command_bar_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Phase 2c-0a — extended linkage for the long-tail migration
    caller_accounting_analysis_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    caller_price_list_import_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("price_list_imports.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_fh_case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fh_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_ringcentral_call_log_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ringcentral_call_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_kb_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("kb_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_import_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    experiment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_experiments.id", ondelete="SET NULL"),
        nullable=True,
    )
    experiment_variant: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Phase 3b — test executions flagged here, excluded from production stats
    is_test_execution: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )


class IntelligencePromptAuditLog(Base):
    """Append-only audit trail for every prompt state transition.

    Phase 3b — any activation, rollback, draft create/update/delete writes
    a row here. Never mutated once written; queried for the PromptDetail
    History tab.
    """

    __tablename__ = "intelligence_prompt_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prompt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # activate | rollback | create_draft | update_draft | delete_draft
    action: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changelog_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )


class IntelligenceMessage(Base):
    __tablename__ = "intelligence_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    conversation = relationship("IntelligenceConversation", back_populates="messages")
