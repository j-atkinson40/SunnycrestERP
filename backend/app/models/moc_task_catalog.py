"""Maps of Content — task-catalog model (MoC-2a, migration r112).

A vertical-default TASK CATALOG: named recurring automations per vertical
("Funeral Home Billing", "New Legacy Order"). This is a NEW concept — NOT the
runtime instance-tasks (vault_items item_type='task' / legacy tasks). Each row
references the ONE workflow_template it runs + (via MoCTaskCatalogFocus) the
MANY focus_templates it opens.

frequency + task_type are FREE-FORM strings: free-form pending a stable
vocabulary; promote to enum if the type/frequency set stabilizes (workflow
templates carry no trigger columns to derive frequency from; no task-type
taxonomy exists). Three-tier scope mirrors moc_pages. Actor columns FK-less
(cross-realm). Artifact references resolve at READ time through the cards'
_resolve_workflow/_resolve_focus (orphan-tolerant) — the FKs use ondelete so
template deletion never blocks.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCTaskCatalog(Base):
    __tablename__ = "moc_task_catalog"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # platform_default | vertical_default | tenant_override
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("verticals.slug"), nullable=True, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Free-form pending stable vocabulary; promote to enum if it stabilizes.
    frequency: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # The ONE workflow this task runs (deep-linked via the cards' resolver).
    workflow_template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # The MANY focuses this task opens (ordered).
    focuses: Mapped[list["MoCTaskCatalogFocus"]] = relationship(
        "MoCTaskCatalogFocus",
        cascade="all, delete-orphan",
        order_by="MoCTaskCatalogFocus.display_order",
        back_populates="task",
    )

    # The 0..N DESCRIPTIVE triggers (schedule|event|manual — MoC Triggers T-1a).
    # ORM cascade mirrors focuses; the DB FK also carries ON DELETE CASCADE so a
    # task delete never orphans a trigger regardless of load path.
    triggers: Mapped[list["MoCTaskTrigger"]] = relationship(  # noqa: F821
        "MoCTaskTrigger",
        cascade="all, delete-orphan",
        order_by="MoCTaskTrigger.display_order",
        primaryjoin="MoCTaskCatalog.id == MoCTaskTrigger.task_catalog_id",
    )


class MoCTaskCatalogFocus(Base):
    __tablename__ = "moc_task_catalog_focuses"

    task_catalog_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("moc_task_catalog.id", ondelete="CASCADE"),
        primary_key=True,
    )
    focus_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("focus_templates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0
    )

    task: Mapped["MoCTaskCatalog"] = relationship(
        "MoCTaskCatalog", back_populates="focuses"
    )
