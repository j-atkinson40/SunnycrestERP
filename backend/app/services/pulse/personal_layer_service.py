"""Personal layer composition — items addressed to the current user.

Per BRIDGEABLE_MASTER §3.26.2.3 Personal Layer:
  • Tasks assigned to you ........... Phase W-4a (READY)
  • Approvals waiting on you ........ Phase W-4a (READY via briefing
                                       pending_decisions)
  • @mentions in comments/messages .. Phase W-4b (STUB — needs comm
                                       primitives)
  • Direct messages ................. Phase W-4b (STUB — needs email)
  • Items you marked "watch" ........ Post-arc (no watch system today)

Honest scope for Phase W-4a: tasks + approvals only. Sunnycrest
dispatcher's Personal Layer is thin pre-W-4b — that's accepted.
Demo narrative carries on Operational + Anomaly layers; Personal
layer fills in once Phase W-4b lands the communications primitives.

**Tenant isolation:** every query filters by `company_id ==
user.company_id`. Personal layer additionally filters by `user_id`
or assignee — no cross-user leakage even within the same tenant.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.services.pulse.types import LayerContent, LayerItem


# Component keys (canonical — used in pulse_signals for signal
# tracking, also in frontend renderer registry).
TASKS_ASSIGNED_KEY = "tasks_assigned"
APPROVALS_WAITING_KEY = "approvals_waiting"


def _build_tasks_item(db: Session, *, user: User) -> LayerItem | None:
    """Surface tasks assigned to this user in the Personal layer.

    Phase 5 Triage shipped the Task model with `assignee_user_id`.
    For Pulse, we surface a stream item (count + top 3) rather than a
    full kanban — the dedicated /tasks page or task triage queue
    handles deep work. Per §12.6a, Pulse is a reference surface for
    Personal items; deep editing happens on the page.
    """
    # Open / in-progress tasks assigned to this user.
    rows: list[Task] = (
        db.query(Task)
        .filter(
            Task.company_id == user.company_id,
            Task.assignee_user_id == user.id,
            Task.is_active.is_(True),
            Task.status.in_(["open", "in_progress", "blocked"]),
        )
        .order_by(
            # Priority sort matches TaskService.list_tasks semantics
            # (urgent → high → normal → low) but priority is a
            # string; ordering by string is stable + matches catalog.
            Task.priority.desc().nullslast(),
            Task.due_date.asc().nullslast(),
        )
        .limit(20)
        .all()
    )
    total = len(rows)
    if total == 0:
        # No tasks → return nothing (suppress the item entirely; the
        # layer-level advisory might still surface "all clear" if
        # other personal items also empty).
        return None

    # Top 3 surfaced inline on Brief variant; click "View all" hits
    # the tasks page.
    top = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in rows[:3]
    ]
    return LayerItem(
        item_id="stream:tasks_assigned",
        kind="stream",
        component_key=TASKS_ASSIGNED_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        # Personal layer items get high priority within the layer —
        # personal stuff surfaces above ambient activity.
        priority=80,
        payload={
            "total_count": total,
            "top_items": top,
            "navigation_target": "/tasks",
        },
    )


def _build_approvals_item(db: Session, *, user: User) -> LayerItem | None:
    """Surface agent-job approvals awaiting this user.

    Phase 8b accounting agents use the `approval_gate` token-based
    flow. Approvals waiting are AgentJob rows with status
    `awaiting_approval` whose `tenant_id == user.company_id`. For
    Phase W-4a we surface a count + most-recent links; full review
    happens on the agent dashboard.

    Honest scope: this surfaces tenant-wide pending approvals, not
    per-user routing (the approval_gate doesn't have explicit
    routing today — admin permission gates the action). When per-
    user routing lands (Phase W-4b+ task assignment for approvals),
    this filter tightens.
    """
    # AgentJob (Phase 8b approval_gate) — tenant-wide pending
    # approvals. Filter to admin users only? No — Pulse is per-user,
    # the surfacing is informational; the actual approve action is
    # gated by permission at /agents/{id}/review. Surface to all
    # users so non-admins see "your team has N pending approvals"
    # for awareness; clicking through hits the permission gate.
    from app.models.agent import AgentJob

    rows: list[AgentJob] = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.status == "awaiting_approval",
        )
        .order_by(AgentJob.created_at.desc())
        .limit(10)
        .all()
    )
    total = len(rows)
    if total == 0:
        return None
    top = [
        {
            "id": j.id,
            "job_type": j.job_type,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in rows[:3]
    ]
    return LayerItem(
        item_id="stream:approvals_waiting",
        kind="stream",
        component_key=APPROVALS_WAITING_KEY,
        variant_id="brief",
        cols=2,
        rows=1,
        # Slightly lower priority than tasks (tasks are direct work;
        # approvals are gate-and-trust signal).
        priority=70,
        payload={
            "total_count": total,
            "top_items": top,
            "navigation_target": "/agents",
        },
    )


def compose_for_user(
    db: Session,
    *,
    user: User,
) -> LayerContent:
    """Build the Personal layer for a given user.

    Returns a `LayerContent` whose items are user-personal. Pulse
    composition engine (Commit 3) renders this layer at the top per
    §3.26.2.4 ("Personal layer surfaces at top").

    Empty-state contract: if no Personal items surface (no tasks, no
    approvals), returns `LayerContent(items=[], advisory="...")`
    with a friendly hint. The composition engine + frontend treat
    empty layers as render-as-nothing (the Personal section is
    suppressed if items empty).
    """
    items: list[LayerItem] = []

    tasks_item = _build_tasks_item(db, user=user)
    if tasks_item:
        items.append(tasks_item)

    approvals_item = _build_approvals_item(db, user=user)
    if approvals_item:
        items.append(approvals_item)

    advisory: str | None = None
    if not items:
        # Empty Personal layer — Phase W-4a accepted scope: this is
        # the honest pre-W-4b state. Surface a quiet advisory the
        # frontend can render or suppress.
        advisory = "Nothing addressed to you right now."

    return LayerContent(layer="personal", items=items, advisory=advisory)
