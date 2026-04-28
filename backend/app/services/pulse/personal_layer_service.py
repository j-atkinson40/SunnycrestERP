"""Personal layer composition — items addressed to the current user.

**Phase W-4a Cleanup Session B.1 (2026-05-04) status: items deferred.**

Per Phase W-4b canon expansion (BRIDGEABLE_MASTER §3.26.2.3 +
§3.26.2.4 amendment + §3.26.9 Communications Layer + D-COMMS-4),
the Personal layer literal is **scheduled for hard-cutover removal**.
Tasks + approvals migrate to the Operational layer; the Personal
layer slot at the top of the canonical layer order is reclaimed by
the Communications layer. The migration is wholesale — this file
itself rewrites to `communications_layer_service.py` with the
tasks-assigned + approvals-waiting builders moving to
`operational_layer_service.py`.

Pre-Phase-W-4b state: composition_engine.py only synthesizes
IntelligenceStream entries for `anomaly_intelligence`
(per Commit 3 V1 anomaly intelligence). Tasks-assigned + approvals-
waiting items emitted with `kind="stream"` had no matching
IntelligenceStream registry entry on the frontend dispatch side, so
PulsePiece's stream-rendering path returned null and rendered an
empty Pattern 2 chrome card. Phase W-4a Step 6 Commit 4 (`91df9a4`)
empty-slot filter surfaced this drift; Cleanup Session B.1 closes
it.

**Per §3.26.7.5 canonical-quality discipline**: build at canonical
quality WHEN the widget is needed, not preemptively against
speculative composition shapes that may evolve. The intermediate
"stream-in-Personal" framing is itself transitional. Building stream
or widget UI now produces ~5 weeks of useful life followed by
retirement when Phase W-4b's hard cutover lands. The canonical fix
is to defer emission until the migration ships proper Operational-
layer rendering.

**Builders deferred to Phase W-4b:**
  • `_build_tasks_item` ............. Returns None always
  • `_build_approvals_item` ......... Returns None always
  • Both functions retained as scaffolding so the Phase W-4b migration
    can MOVE them (rename + relocate to operational_layer_service)
    rather than recreate them — the data shapes + tenant-isolation
    queries are correct; only the layer destination is being
    deferred. Restore by removing the early return + uncomment the
    return-LayerItem block.

**Reversibility**: re-enabling the pre-deferral emission requires
removing the early `return None` lines from both `_build_*` functions.
If Phase W-4b's hard cutover doesn't ship cleanly, the deferral can
be flipped without architectural rework.

**Empty-state advisory unchanged**: `compose_for_user` continues to
emit the canonical "Nothing addressed to you right now." advisory
when `items == []`. Per Option (i) confirmed in Session B.1: no new
copy invented; honest empty state.

**Tenant isolation contract preserved**: when builders eventually
re-enable in Phase W-4b at their new home, the query filters
(`company_id == user.company_id` + assignee/user_id scoping) carry
forward verbatim. Cleanup Session B.1 doesn't rewrite the data
queries — only gates the LayerItem emission.

**Path forward**:
  1. Phase W-4b implementation lands operational_layer_service
     additions for tasks + approvals
  2. Phase W-4b implementation lands communications_layer_service
     replacing this file
  3. This file deletes (or gets repurposed as the foundation for
     communications_layer_service per the canonical migration note)
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

    **Phase W-4a Cleanup Session B.1 (2026-05-04) — DEFERRED to
    Phase W-4b**: returns None always pending Phase W-4b migration to
    operational_layer_service. Pre-deferral, this function emitted
    `kind="stream"` LayerItems but composition_engine had no matching
    IntelligenceStream registration on the dispatch side, producing
    empty Pattern 2 chrome cards. Per §3.26.7.5 canonical-quality
    discipline, the canonical fix is to defer emission until Phase
    W-4b ships proper Operational-layer rendering — not to ship
    transitional UI that retires in ~5 weeks. See file-level docstring
    for full context.

    The pre-deferral query logic is preserved as scaffolding below
    (after the early return) so Phase W-4b can MOVE this builder
    (rename + relocate to operational_layer_service.py) rather than
    recreate it. Tenant isolation contract (`company_id ==
    user.company_id`) carries forward when re-enabled.

    To re-enable: remove the `return None` line below.
    """
    # ── Phase W-4a Cleanup Session B.1 deferral (per §3.26.7.5)
    # Re-enable in Phase W-4b at new home in operational_layer_service.
    return None
    # NOTE: lines below preserved as scaffolding for Phase W-4b
    # migration. Tenant isolation + query correctness verified
    # pre-deferral; data shape unchanged.
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

    **Phase W-4a Cleanup Session B.1 (2026-05-04) — DEFERRED to
    Phase W-4b**: returns None always pending Phase W-4b migration to
    operational_layer_service. Pre-deferral, this function emitted
    `kind="stream"` LayerItems but composition_engine had no matching
    IntelligenceStream registration on the dispatch side, producing
    empty Pattern 2 chrome cards. Per §3.26.7.5 canonical-quality
    discipline, the canonical fix is to defer emission until Phase
    W-4b ships proper Operational-layer rendering — not to ship
    transitional UI that retires in ~5 weeks. See file-level docstring
    for full context.

    The pre-deferral query logic is preserved as scaffolding below
    (after the early return) so Phase W-4b can MOVE this builder
    (rename + relocate to operational_layer_service.py) rather than
    recreate it. Tenant isolation contract (`tenant_id ==
    user.company_id`) carries forward when re-enabled.

    To re-enable: remove the `return None` line below.
    """
    # ── Phase W-4a Cleanup Session B.1 deferral (per §3.26.7.5)
    # Re-enable in Phase W-4b at new home in operational_layer_service.
    return None
    # NOTE: lines below preserved as scaffolding for Phase W-4b
    # migration. Tenant isolation + query correctness verified
    # pre-deferral; data shape unchanged.
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
