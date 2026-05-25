"""Task substrate v1 — 5 task type behavior plugin tests.

Each of the 5 plugins is verified for:
- registration
- declared defaults (lifecycle_shape / routing_mode / priority / visibility)
- on_status_change / render_default_payload hook shape
"""

from __future__ import annotations

import pytest

from app.services.tasks.plugins import type_behaviors


def test_all_five_v1_plugins_registered():
    expected = {
        "generic_task",
        "review_approval_task",
        "scheduled_recurring_task",
        "customer_communication_task",
        "anomaly_resolution_task",
    }
    registered = set(type_behaviors.list_task_type_behaviors())
    missing = expected - registered
    assert not missing, f"missing plugins: {missing}"


# ── generic_task ────────────────────────────────────────────────────


def test_generic_task_defaults():
    b = type_behaviors.get_task_type_behavior("generic_task")
    assert b.default_lifecycle_shape == "action"
    assert b.default_routing_mode == "direct_user"
    assert b.default_priority == "normal"
    assert b.default_visibility == "operator_internal"


def test_generic_task_on_status_change_noop(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="gen",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    b = type_behaviors.get_task_type_behavior("generic_task")
    # No-op should not raise.
    b.on_status_change(
        db_session,
        task_details_id=td.id,
        from_state="created",
        to_state="in_progress",
        actor_user_id=None,
    )


def test_generic_task_render_default_payload(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="gen-render",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    b = type_behaviors.get_task_type_behavior("generic_task")
    payload = b.render_default_payload(
        db_session, task_details_id=td.id
    )
    assert payload["task_details_id"] == td.id
    assert payload["current_state"] == "created"
    assert payload["priority"] == "normal"


# ── review_approval_task ────────────────────────────────────────────


def test_review_approval_defaults():
    b = type_behaviors.get_task_type_behavior("review_approval_task")
    assert b.default_lifecycle_shape == "action"
    assert b.default_routing_mode == "direct_user"


def test_review_approval_done_hook_sets_outcome_from_metadata(
    db_session, ts_ctx
):
    from app.services.tasks.service import (
        create_task_with_provenance,
        transition_task,
    )

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_job",
        provenance_ref_id="job-abc",
        event_kind="produced",
        task_type_key="review_approval_task",
        title="approve me",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
        metadata={"outcome": "approved"},
    )
    db_session.commit()
    transition_task(
        db_session, task_details_id=td.id, to_state="in_progress"
    )
    db_session.commit()
    td2 = transition_task(
        db_session, task_details_id=td.id, to_state="done"
    )
    db_session.commit()
    assert td2.resolution_outcome == "approved"


def test_review_approval_done_hook_defaults_to_completed(
    db_session, ts_ctx
):
    from app.services.tasks.service import (
        create_task_with_provenance,
        transition_task,
    )

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_job",
        provenance_ref_id="job-abc2",
        event_kind="produced",
        task_type_key="review_approval_task",
        title="approve me 2",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
        metadata={},  # no outcome
    )
    db_session.commit()
    transition_task(
        db_session, task_details_id=td.id, to_state="in_progress"
    )
    db_session.commit()
    td2 = transition_task(
        db_session, task_details_id=td.id, to_state="done"
    )
    db_session.commit()
    assert td2.resolution_outcome == "completed"


# ── scheduled_recurring_task ────────────────────────────────────────


def test_scheduled_recurring_defaults():
    b = type_behaviors.get_task_type_behavior("scheduled_recurring_task")
    assert b.default_lifecycle_shape == "action"
    assert b.default_routing_mode == "round_robin"


def test_scheduled_recurring_on_created_populates_due_date(
    db_session, ts_ctx
):
    """If metadata.recurrence_offset_days is set, due_date is populated."""
    from app.models.task_details import TaskDetails
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="scheduled_recurring",
        provenance_ref_type="cron",
        provenance_ref_id="job-x",
        event_kind="fired",
        task_type_key="scheduled_recurring_task",
        title="recurring",
        created_by_user_id=ts_ctx["user_id"],
        metadata={"recurrence_offset_days": 5},
    )
    db_session.commit()
    # Re-fetch.
    td2 = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.id == td.id)
        .first()
    )
    assert td2.due_date is not None


def test_scheduled_recurring_no_offset_no_due_date(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="scheduled_recurring",
        provenance_ref_type="cron",
        provenance_ref_id="job-no-offset",
        event_kind="fired",
        task_type_key="scheduled_recurring_task",
        title="no-offset",
        created_by_user_id=ts_ctx["user_id"],
        metadata={},
    )
    db_session.commit()
    assert td.due_date is None


# ── customer_communication_task ─────────────────────────────────────


def test_customer_communication_defaults():
    b = type_behaviors.get_task_type_behavior("customer_communication_task")
    assert b.default_lifecycle_shape == "action"
    assert b.default_routing_mode == "direct_user"
    assert b.default_visibility == "operator_internal"


def test_customer_communication_hook_invokes_on_done(db_session, ts_ctx):
    """Hook fires on done; v1.0 logs only — verify no exception."""
    from app.services.tasks.service import (
        create_task_with_provenance,
        transition_task,
    )

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="communication_inbound",
        provenance_ref_type="email_message",
        provenance_ref_id="msg-1",
        event_kind="received",
        task_type_key="customer_communication_task",
        title="comm",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
        metadata={"outbound_response": "thanks!"},
    )
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="in_progress")
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="done")
    db_session.commit()


# ── anomaly_resolution_task ─────────────────────────────────────────


def test_anomaly_resolution_defaults():
    b = type_behaviors.get_task_type_behavior("anomaly_resolution_task")
    assert b.default_lifecycle_shape == "action"
    assert b.default_priority == "high"


def test_anomaly_resolution_render_payload(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_anomaly",
        provenance_ref_id="anom-1",
        event_kind="detected",
        task_type_key="anomaly_resolution_task",
        title="anom",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    b = type_behaviors.get_task_type_behavior("anomaly_resolution_task")
    payload = b.render_default_payload(
        db_session, task_details_id=td.id
    )
    assert payload["task_type"] == "anomaly_resolution_task"
    assert payload["provenance_ref_id"] == "anom-1"


def test_anomaly_resolution_done_hook_safe_when_anomaly_missing(
    db_session, ts_ctx
):
    """Done hook tolerates missing AgentAnomaly row (best-effort)."""
    from app.services.tasks.service import (
        create_task_with_provenance,
        transition_task,
    )

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_anomaly",
        provenance_ref_id="anom-does-not-exist",
        event_kind="detected",
        task_type_key="anomaly_resolution_task",
        title="anom2",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="in_progress")
    db_session.commit()
    # Should not raise even though anomaly row doesn't exist.
    transition_task(db_session, task_details_id=td.id, to_state="done")
    db_session.commit()


# ── plugin lookup affordances ───────────────────────────────────────


def test_get_task_type_behavior_unknown_returns_none():
    assert type_behaviors.get_task_type_behavior("never_registered") is None


def test_unregister_then_re_register():
    b = type_behaviors.get_task_type_behavior("generic_task")
    assert b is not None
    assert type_behaviors.unregister_task_type_behavior("generic_task") is True
    assert type_behaviors.get_task_type_behavior("generic_task") is None
    type_behaviors.register_task_type_behavior(b)
    assert type_behaviors.get_task_type_behavior("generic_task") is b
