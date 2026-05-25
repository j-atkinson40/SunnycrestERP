"""Task substrate v1 — subscriber registry tests.

Covers:
- 7 event types defined
- 6 v1 subscribers registered at module import
- registration / unregistration / replacement semantics
- sync dispatch order matches registration order
- one subscriber failure does not block others
- emit_event rejects unknown event_type
"""

from __future__ import annotations

import pytest

from app.services.tasks.subscribers import registry as reg_mod
from app.services.tasks.subscribers.registry import (
    EVENT_TYPES,
    emit_event,
    get_subscribers,
    is_registered,
    register_subscriber,
    unregister_subscriber,
)


def test_seven_event_types_defined():
    assert len(EVENT_TYPES) == 7
    expected = {
        "task_created",
        "task_assigned",
        "task_status_changed",
        "task_completed",
        "task_blocked",
        "task_unblocked",
        "task_cancelled",
    }
    assert set(EVENT_TYPES) == expected


def test_six_v1_subscribers_registered():
    subs = get_subscribers()
    expected = {
        "notification_dispatcher",
        "audit_writer",
        "briefings_invalidator",
        "pulse_invalidator",
        "workflow_resumer",
        "focus_closer",
    }
    assert set(subs) >= expected


def test_is_registered_true():
    assert is_registered("audit_writer") is True


def test_is_registered_false():
    assert is_registered("never_registered_xyz") is False


def test_register_subscriber_idempotent_replace():
    fired = []

    def h1(db, payload):
        fired.append("h1")

    def h2(db, payload):
        fired.append("h2")

    register_subscriber("test_replace_sub", h1, event_types=("task_created",))
    assert is_registered("test_replace_sub")
    register_subscriber("test_replace_sub", h2, event_types=("task_created",))
    # Now only h2 should fire (latest wins).
    emit_event(
        None,
        event_type="task_created",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )
    assert "h1" not in fired
    assert "h2" in fired
    unregister_subscriber("test_replace_sub")


def test_register_rejects_unknown_event_type():
    def h(db, payload):
        pass

    with pytest.raises(ValueError):
        register_subscriber("bad", h, event_types=("not_a_real_event",))


def test_emit_event_rejects_unknown_type():
    with pytest.raises(ValueError):
        emit_event(
            None,
            event_type="not_a_real_event",
            task_details_id="x",
            actor_user_id=None,
            payload={},
        )


def test_dispatch_order_matches_registration():
    fired = []

    def a(db, payload): fired.append("a")
    def b(db, payload): fired.append("b")
    def c(db, payload): fired.append("c")

    register_subscriber("order_a", a, event_types=("task_created",))
    register_subscriber("order_b", b, event_types=("task_created",))
    register_subscriber("order_c", c, event_types=("task_created",))

    emit_event(
        None,
        event_type="task_created",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )

    # Filter to only our test subscribers, preserving order.
    seen = [x for x in fired if x in {"a", "b", "c"}]
    # Registration order a,b,c; our entries should appear in that relative order.
    assert seen.index("a") < seen.index("b") < seen.index("c")

    for n in ("order_a", "order_b", "order_c"):
        unregister_subscriber(n)


def test_subscriber_failure_isolated():
    fired = []

    def failing(db, payload):
        raise RuntimeError("boom")

    def succeeding(db, payload):
        fired.append("succeeded")

    register_subscriber("fail_sub", failing, event_types=("task_created",))
    register_subscriber("ok_sub", succeeding, event_types=("task_created",))

    # Even though fail_sub raises, ok_sub still fires.
    emit_event(
        None,
        event_type="task_created",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )
    assert "succeeded" in fired

    unregister_subscriber("fail_sub")
    unregister_subscriber("ok_sub")


def test_subscriber_only_fires_for_subscribed_events():
    fired = []

    def selective(db, payload):
        fired.append(payload["event_type"])

    register_subscriber(
        "selective_sub", selective, event_types=("task_completed",)
    )

    emit_event(
        None,
        event_type="task_created",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )
    assert "task_created" not in fired

    emit_event(
        None,
        event_type="task_completed",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )
    assert "task_completed" in fired

    unregister_subscriber("selective_sub")


def test_unregister_returns_true_then_false():
    def h(db, payload): pass

    register_subscriber("xyz", h, event_types=("task_created",))
    assert unregister_subscriber("xyz") is True
    assert unregister_subscriber("xyz") is False


def test_audit_writer_on_task_created(db_session, ts_ctx):
    """audit_writer subscriber writes audit row for task_created event."""
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
        title="audit subscriber test",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    rows = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == td.id,
            AuditLog.action == "task.task_created",
        )
        .all()
    )
    assert len(rows) >= 1


def test_emit_event_with_no_subscribers_for_type():
    """An event with no matching subscribers does nothing (no error)."""

    # Register an isolated subscriber listening on only one event.
    fired = []

    def h(db, payload):
        fired.append(payload.get("event_type"))

    register_subscriber(
        "only_blocked", h, event_types=("task_blocked",)
    )
    # Emitting task_unblocked — should not trigger.
    emit_event(
        None,
        event_type="task_unblocked",
        task_details_id="x",
        actor_user_id=None,
        payload={},
    )
    assert "task_unblocked" not in fired
    unregister_subscriber("only_blocked")


def test_subscriber_count_at_least_six():
    subs = get_subscribers()
    # At least the 6 v1 subscribers, possibly more if other tests
    # registered+left.
    assert len(subs) >= 6
