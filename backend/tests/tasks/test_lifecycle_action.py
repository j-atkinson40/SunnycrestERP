"""Task substrate v1 — action-shape lifecycle tests.

Verifies action-shape state machine guards + event emission.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.tasks import lifecycle as lifecycle_mod
from app.services.tasks.lifecycle import (
    ACTION_TRANSITIONS,
    InvalidTransition,
    events_for_transition,
    is_terminal,
    legacy_status_to_action_state,
    validate_transition,
)


def test_action_transitions_table_complete():
    expected_states = {
        "created", "assigned", "in_progress", "blocked", "done", "cancelled"
    }
    assert set(ACTION_TRANSITIONS.keys()) == expected_states


def test_validate_legal_transitions():
    # created -> assigned
    validate_transition(
        lifecycle_shape="action", from_state="created", to_state="assigned"
    )
    # assigned -> in_progress
    validate_transition(
        lifecycle_shape="action", from_state="assigned", to_state="in_progress"
    )
    # in_progress -> done
    validate_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="done"
    )
    # in_progress -> blocked
    validate_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="blocked"
    )
    # blocked -> in_progress
    validate_transition(
        lifecycle_shape="action", from_state="blocked", to_state="in_progress"
    )


def test_validate_idempotent_same_state_ok():
    # Same-state transitions are idempotent no-ops, not errors.
    validate_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="in_progress"
    )


def test_validate_rejects_illegal_transition():
    # cannot go from done back to anything
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="action", from_state="done", to_state="in_progress"
        )
    # cannot go from cancelled back to anything
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="action", from_state="cancelled", to_state="in_progress"
        )
    # cannot jump created -> done
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="action", from_state="created", to_state="done"
        )


def test_validate_rejects_unknown_state():
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="action", from_state="bogus", to_state="created"
        )
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="action", from_state="created", to_state="bogus"
        )


def test_validate_rejects_unknown_shape():
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="bogus", from_state="created", to_state="assigned"
        )


def test_is_terminal_action():
    assert is_terminal(lifecycle_shape="action", state="done") is True
    assert is_terminal(lifecycle_shape="action", state="cancelled") is True
    assert is_terminal(lifecycle_shape="action", state="in_progress") is False
    assert is_terminal(lifecycle_shape="action", state="created") is False


def test_events_for_transition_status_changed_always_emitted():
    events = events_for_transition(
        lifecycle_shape="action", from_state="assigned", to_state="in_progress"
    )
    assert "task_status_changed" in events


def test_events_for_transition_assigned_emits_task_assigned():
    events = events_for_transition(
        lifecycle_shape="action", from_state="created", to_state="assigned"
    )
    assert "task_assigned" in events


def test_events_for_transition_done_emits_completed():
    events = events_for_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="done"
    )
    assert "task_completed" in events


def test_events_for_transition_blocked_emits_task_blocked():
    events = events_for_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="blocked"
    )
    assert "task_blocked" in events


def test_events_for_transition_unblocked_emits_task_unblocked():
    events = events_for_transition(
        lifecycle_shape="action", from_state="blocked", to_state="in_progress"
    )
    assert "task_unblocked" in events


def test_events_for_transition_cancelled_emits_task_cancelled():
    events = events_for_transition(
        lifecycle_shape="action", from_state="in_progress", to_state="cancelled"
    )
    assert "task_cancelled" in events


def test_legacy_status_map_open_with_assignee():
    assert legacy_status_to_action_state("open", has_assignee=True) == "assigned"


def test_legacy_status_map_open_without_assignee():
    assert legacy_status_to_action_state("open", has_assignee=False) == "created"


def test_legacy_status_map_in_progress():
    assert (
        legacy_status_to_action_state("in_progress", has_assignee=True)
        == "in_progress"
    )


def test_legacy_status_map_blocked():
    assert (
        legacy_status_to_action_state("blocked", has_assignee=True)
        == "blocked"
    )


def test_legacy_status_map_done():
    assert legacy_status_to_action_state("done", has_assignee=True) == "done"


def test_legacy_status_map_cancelled():
    assert (
        legacy_status_to_action_state("cancelled", has_assignee=False)
        == "cancelled"
    )


def test_apply_transition_records_state_change(db_session, ts_ctx):
    from app.models.task_details import TaskDetails
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="apply transition test",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    assert td.current_state == "assigned"

    td2 = lifecycle_mod.apply_transition(
        db_session,
        task_details_id=td.id,
        to_state="in_progress",
        actor_user_id=ts_ctx["user_id"],
    )
    assert td2.current_state == "in_progress"

    td3 = lifecycle_mod.apply_transition(
        db_session,
        task_details_id=td.id,
        to_state="done",
        actor_user_id=ts_ctx["user_id"],
        resolution_outcome="completed",
    )
    assert td3.current_state == "done"
    assert td3.completed_at is not None
    assert td3.resolution_outcome == "completed"
    db_session.commit()


def test_apply_transition_invalid_raises(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="invalid transition test",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    # Cannot jump from created directly to done.
    with pytest.raises(InvalidTransition):
        lifecycle_mod.apply_transition(
            db_session,
            task_details_id=td.id,
            to_state="done",
        )
    db_session.rollback()


def test_apply_transition_writes_audit_row(db_session, ts_ctx):
    from app.models.audit_log import AuditLog
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="audit row test",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    lifecycle_mod.apply_transition(
        db_session,
        task_details_id=td.id,
        to_state="in_progress",
        actor_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    audit_rows = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "task_details",
            AuditLog.entity_id == td.id,
            AuditLog.action == "task.transition",
        )
        .all()
    )
    assert len(audit_rows) >= 1


def test_apply_transition_not_found_raises(db_session):
    from app.services.tasks.lifecycle import TaskDetailsNotFound
    with pytest.raises(TaskDetailsNotFound):
        lifecycle_mod.apply_transition(
            db_session,
            task_details_id=str(uuid.uuid4()),
            to_state="done",
        )


def test_apply_transition_idempotent_same_state(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="idempotent test",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    # Same-state transition: idempotent no-op.
    td2 = lifecycle_mod.apply_transition(
        db_session,
        task_details_id=td.id,
        to_state="created",
    )
    assert td2.current_state == "created"
    db_session.commit()


def test_all_action_transitions_pairs():
    """Every (from, to) in ACTION_TRANSITIONS is legal; the reverse is illegal
    unless explicitly listed."""
    all_states = set(ACTION_TRANSITIONS.keys())
    for from_state, allowed in ACTION_TRANSITIONS.items():
        for to_state in allowed:
            # legal — must not raise
            validate_transition(
                lifecycle_shape="action",
                from_state=from_state,
                to_state=to_state,
            )
        illegal = all_states - allowed - {from_state}
        for to_state in illegal:
            with pytest.raises(InvalidTransition):
                validate_transition(
                    lifecycle_shape="action",
                    from_state=from_state,
                    to_state=to_state,
                )
