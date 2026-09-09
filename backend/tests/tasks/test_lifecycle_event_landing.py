"""Do lifecycle transition events actually LAND, with an actor?

The note arc's settling phase would generate "you completed N tasks" from
recorded events. Production holds 2,345 tasks, every one in `created`, and
`audit_logs` carries `task.task_created` only — 2,345 rows, ZERO with an actor.

That is the shared-symptom trap: an unused platform and a broken transition
path produce identical evidence. This file breaks the tie on the CONDITION
rather than on the reporter — it exercises real transitions and looks for the
rows. **The answer is that the path works**, so the production absence is
honest: nobody has worked a task, and settling is untestable rather than
unbuildable.

⚠️ TWO CONSTRUCTED NAMES CAUGHT WHILE WRITING THIS, both of which produced a
confident false defect before being corrected:

  1. The ACTION is `task.transition`, not `task.task_status_changed`. The audit
     subscriber deliberately returns early for the status-changed EVENT
     (`audit_subscriber.py:55`) because `lifecycle.apply_transition` writes the
     row itself under a different action name, avoiding a double write.
  2. Creating a task WITH an assignee lands it in `assigned` immediately, so a
     `created -> assigned` transition is a no-op that emits nothing. The first
     draft transitioned to the state the task was already in and read the empty
     result as a broken emitter.

⚠️ The pre-existing `test_audit_writer_on_task_created` asserts `len(rows) >= 1`
and never inspects `user_id`. These tests assert the actor explicitly, because
"you completed N tasks" is a first-person claim and the actor is what makes it
sayable.
"""

from __future__ import annotations

import json

import pytest

from app.models.audit_log import AuditLog
from app.services.tasks.service import (
    create_task_with_provenance,
    transition_task,
)
from tests._cleanup import purge_companies_by_slug


@pytest.fixture
def unassigned_task(db_session, ts_ctx):
    """A task in `created` — NOT assigned, so transitions are real."""
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="lifecycle event landing",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    assert td.current_state == "created", (
        f"precondition: expected `created`, got {td.current_state!r} — a task "
        "created with an assignee starts `assigned` and makes the first "
        "transition a silent no-op"
    )
    return td


def _audit(db, td_id, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == td_id, AuditLog.action == action)
        .all()
    )


def _walk(db, td_id, actor, states):
    for s in states:
        transition_task(
            db, task_details_id=td_id, to_state=s, actor_user_id=actor
        )
    db.commit()


def test_transition_lands_an_audit_row_with_from_and_to(
    db_session, ts_ctx, unassigned_task
):
    """The row settling reads: what changed, and from what."""
    _walk(db_session, unassigned_task.id, ts_ctx["user_id"], ["assigned"])

    rows = _audit(db_session, unassigned_task.id, "task.transition")
    assert len(rows) >= 1, "no task.transition row after a real transition"

    changes = json.loads(rows[0].changes)
    assert changes["from"] == "created"
    assert changes["to"] == "assigned"


def test_transition_row_carries_the_actor(db_session, ts_ctx, unassigned_task):
    """`you completed N tasks` needs to know who."""
    _walk(db_session, unassigned_task.id, ts_ctx["user_id"], ["assigned"])

    rows = _audit(db_session, unassigned_task.id, "task.transition")
    assert rows, "precondition: no transition row to inspect"
    assert all(r.user_id == ts_ctx["user_id"] for r in rows), (
        "task.transition landed WITHOUT the actor — first-person settling "
        f"text would be unsupportable. user_ids: {[r.user_id for r in rows]}"
    )


def test_completion_is_its_own_event_distinct_from_cancellation(
    db_session, ts_ctx, unassigned_task
):
    """⚠️ THE RULING: the record says what happened, not that it was completed.

    `done` emits `task_completed`; `cancelled` emits `task_cancelled`. Both are
    terminal and both resolve the prompt, and they are DIFFERENT SENTENCES. A
    settled note that forced cancellation into "you completed 1 task" would
    state something the user did not do.
    """
    _walk(
        db_session, unassigned_task.id, ts_ctx["user_id"],
        ["assigned", "in_progress", "done"],
    )

    completed = _audit(db_session, unassigned_task.id, "task.task_completed")
    cancelled = _audit(db_session, unassigned_task.id, "task.task_cancelled")

    assert len(completed) == 1, "reaching `done` did not emit task_completed"
    assert completed[0].user_id == ts_ctx["user_id"]
    assert cancelled == [], "a completed task must not also read as cancelled"


def test_cancellation_emits_cancelled_and_never_completed(
    db_session, ts_ctx, unassigned_task
):
    """The other half of the ruling — and the one that would have been a lie."""
    _walk(
        db_session, unassigned_task.id, ts_ctx["user_id"],
        ["assigned", "cancelled"],
    )

    completed = _audit(db_session, unassigned_task.id, "task.task_completed")
    cancelled = _audit(db_session, unassigned_task.id, "task.task_cancelled")

    assert len(cancelled) == 1, "reaching `cancelled` did not emit task_cancelled"
    assert cancelled[0].user_id == ts_ctx["user_id"]
    assert completed == [], (
        "a CANCELLED task emitted task_completed — settling would say "
        "'you completed 1 task' about work that was abandoned"
    )


def test_reaching_done_sets_completed_at(db_session, ts_ctx, unassigned_task):
    """`completed_at` is NULL on all 2,345 production rows."""
    _walk(
        db_session, unassigned_task.id, ts_ctx["user_id"],
        ["assigned", "in_progress", "done"],
    )
    db_session.refresh(unassigned_task)

    assert unassigned_task.current_state == "done"
    assert unassigned_task.completed_at is not None


def test_cleanup(db_session):
    """Ratchet: this file's tenants do not survive it (`ts-` prefix)."""
    purge_companies_by_slug(db_session, "ts-%")
    db_session.commit()
