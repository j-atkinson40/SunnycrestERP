"""Task substrate v1 — reminder-shape lifecycle tests.

Verifies reminder-shape state machine guards.
"""

from __future__ import annotations

import pytest

from app.services.tasks import lifecycle as lifecycle_mod
from app.services.tasks.lifecycle import (
    InvalidTransition,
    REMINDER_TRANSITIONS,
    is_terminal,
    validate_transition,
    valid_states_for,
)


def test_reminder_transitions_table_complete():
    expected_states = {"informational", "acknowledged", "dismissed"}
    assert set(REMINDER_TRANSITIONS.keys()) == expected_states


def test_validate_reminder_informational_to_acknowledged():
    validate_transition(
        lifecycle_shape="reminder",
        from_state="informational",
        to_state="acknowledged",
    )


def test_validate_reminder_informational_to_dismissed():
    validate_transition(
        lifecycle_shape="reminder",
        from_state="informational",
        to_state="dismissed",
    )


def test_validate_reminder_acknowledged_is_terminal():
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="reminder",
            from_state="acknowledged",
            to_state="dismissed",
        )


def test_validate_reminder_dismissed_is_terminal():
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="reminder",
            from_state="dismissed",
            to_state="acknowledged",
        )


def test_validate_reminder_rejects_action_states():
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="reminder",
            from_state="informational",
            to_state="done",
        )
    with pytest.raises(InvalidTransition):
        validate_transition(
            lifecycle_shape="reminder",
            from_state="created",
            to_state="acknowledged",
        )


def test_is_terminal_reminder():
    assert is_terminal(lifecycle_shape="reminder", state="acknowledged") is True
    assert is_terminal(lifecycle_shape="reminder", state="dismissed") is True
    assert is_terminal(lifecycle_shape="reminder", state="informational") is False


def test_valid_states_for_reminder():
    states = valid_states_for("reminder")
    assert set(states) == {"informational", "acknowledged", "dismissed"}


def test_valid_states_for_unknown_shape():
    with pytest.raises(ValueError):
        valid_states_for("bogus")


def test_apply_transition_reminder(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="reminder shape test",
        created_by_user_id=ts_ctx["user_id"],
        lifecycle_shape="reminder",
    )
    db_session.commit()
    assert td.lifecycle_shape == "reminder"
    assert td.current_state == "informational"

    td2 = lifecycle_mod.apply_transition(
        db_session,
        task_details_id=td.id,
        to_state="acknowledged",
        actor_user_id=ts_ctx["user_id"],
    )
    assert td2.current_state == "acknowledged"
    db_session.commit()


def test_apply_transition_reminder_terminal_rejects(db_session, ts_ctx):
    from app.services.tasks.service import create_task_with_provenance

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="reminder terminal test",
        created_by_user_id=ts_ctx["user_id"],
        lifecycle_shape="reminder",
    )
    db_session.commit()
    lifecycle_mod.apply_transition(
        db_session, task_details_id=td.id, to_state="acknowledged"
    )
    db_session.commit()
    with pytest.raises(InvalidTransition):
        lifecycle_mod.apply_transition(
            db_session, task_details_id=td.id, to_state="dismissed"
        )
    db_session.rollback()
