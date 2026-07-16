"""MoC Task Triggers T-1a — the descriptive trigger substrate (headless).

Assembly tests (the WHOLE substrate before any UI, the JCF-1 discipline): a task
round-trips all three trigger kinds; the event condition persists as a STRUCTURED
LIST-OF-ONE (not a string — the expansion-ready proof); the validator rejects a
flat-string condition / a field the event doesn't expose / an event not in the
catalog; the event catalog seed is idempotent + carries filterable_fields;
humanize(schedule) derives a sane label; deleting a task cascades its triggers.

DESCRIPTIVE only — nothing fires. This proves the model before a pixel (T-1b).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content import trigger_events
from app.services.maps_of_content.task_catalog import create_task
from app.services.maps_of_content.triggers import (
    TriggerValidationError,
    add_trigger,
    delete_trigger,
    humanize_schedule,
    list_triggers,
    patch_trigger,
    validate_trigger,
)

VERT = "manufacturing"

_SCHEDULE = {"spec_kind": "time_of_day", "time": "18:00", "days": ["mon", "tue", "wed", "thu", "fri"]}
_EVENT = {"event": "order.created", "conditions": [{"field": "order_type", "operator": "==", "value": "funeral"}]}


@pytest.fixture
def db():
    s = SessionLocal()
    s._tasks: list[str] = []
    trigger_events.seed_events(s)  # idempotent; the event catalog the validator reads
    yield s
    s.rollback()
    for tid in s._tasks:
        # deleting the task cascades its triggers (FK ON DELETE CASCADE)
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :id"), {"id": tid})
    s.commit()
    s.close()


def _make_task(db) -> str:
    task = create_task(db, vertical=VERT, name=f"Trig Task {uuid.uuid4().hex[:6]}")
    db.commit()
    db._tasks.append(task.id)
    return task.id


def test_task_round_trips_all_three_trigger_kinds(db):
    tid = _make_task(db)
    add_trigger(db, task_catalog_id=tid, kind="schedule", config=_SCHEDULE)
    add_trigger(db, task_catalog_id=tid, kind="event", config=_EVENT)
    add_trigger(db, task_catalog_id=tid, kind="manual", config={})
    db.commit()

    trigs = list_triggers(db, task_catalog_id=tid)
    by_kind = {t.kind: t for t in trigs}
    assert set(by_kind) == {"schedule", "event", "manual"}
    assert by_kind["schedule"].config["spec_kind"] == "time_of_day"
    assert by_kind["schedule"].config["time"] == "18:00"
    assert by_kind["event"].config["event"] == "order.created"
    assert by_kind["manual"].config == {}


def test_event_condition_persists_as_structured_list_of_one(db):
    """THE expansion-ready proof — conditions is a LIST of {field,operator,value},
    NOT a flat string. Filtered→rich later is appending elements, no migration."""
    tid = _make_task(db)
    add_trigger(db, task_catalog_id=tid, kind="event", config=_EVENT)
    db.commit()

    trig = list_triggers(db, task_catalog_id=tid)[0]
    conditions = trig.config["conditions"]
    assert isinstance(conditions, list)  # a LIST, not a string
    assert conditions == [{"field": "order_type", "operator": "==", "value": "funeral"}]


def test_flat_string_conditions_is_rejected(db):
    """The structured-for-expansion guard: a flat-string condition is REJECTED."""
    with pytest.raises(TriggerValidationError, match="must be a list"):
        validate_trigger(
            db, kind="event", vertical=VERT,
            config={"event": "order.created", "conditions": "order_type==funeral"},
        )


def test_condition_on_unexposed_field_is_rejected(db):
    """Referential: a condition on a field the event doesn't expose is REJECTED."""
    with pytest.raises(TriggerValidationError, match="not exposed by event"):
        validate_trigger(
            db, kind="event", vertical=VERT,
            config={"event": "order.created",
                    "conditions": [{"field": "nonexistent_field", "operator": "==", "value": "x"}]},
        )


def test_event_not_in_catalog_is_rejected(db):
    with pytest.raises(TriggerValidationError, match="not in the catalog"):
        validate_trigger(
            db, kind="event", vertical=VERT,
            config={"event": "totally.madeup", "conditions": []},
        )


def test_bad_schedule_spec_is_rejected(db):
    with pytest.raises(TriggerValidationError, match="spec_kind"):
        validate_trigger(db, kind="schedule", vertical=VERT, config={"spec_kind": "bogus"})
    with pytest.raises(TriggerValidationError, match="requires 'time'"):
        validate_trigger(db, kind="schedule", vertical=VERT, config={"spec_kind": "time_of_day"})


def test_manual_takes_no_config(db):
    with pytest.raises(TriggerValidationError, match="no config"):
        validate_trigger(db, kind="manual", vertical=VERT, config={"anything": 1})


def test_event_catalog_seed_idempotent_and_carries_fields(db):
    trigger_events.seed_events(db)
    trigger_events.seed_events(db)
    n = db.execute(
        sql_text("SELECT COUNT(*) FROM moc_trigger_event_catalog WHERE scope = 'platform_default'")
    ).scalar()
    # 9 platform events since H1 added run.failed (91688bad) — the count was
    # stale at 8 (the H1 arc bumped the seed, not this pin; fixed P1 session).
    assert n == 9  # no dups

    order_created = trigger_events.get_event(db, event_key="order.created", vertical=VERT)
    assert order_created is not None
    fields = {f["field"] for f in order_created.filterable_fields}
    assert "order_type" in fields  # real column, feeds the condition builder
    order_type = next(f for f in order_created.filterable_fields if f["field"] == "order_type")
    assert order_type["values"] == ["funeral", "retail", "wholesale"]  # the real enum


def test_humanize_schedule_derives_a_label(db):
    # time_of_day, all weekdays → not daily, formatted 12h.
    label = humanize_schedule(_SCHEDULE)
    assert "6:00 PM" in label
    assert "Mon" in label
    # a monthly cron → "Monthly · 1st".
    monthly = humanize_schedule({"spec_kind": "cron", "cron": "0 6 1 * *"})
    assert "Monthly" in monthly and "1st" in monthly
    # after-record.
    after = humanize_schedule({"spec_kind": "time_after_event", "field": "service_date", "offset_days": 7})
    assert "7 days after service_date" == after


def test_delete_task_cascades_its_triggers(db):
    tid = _make_task(db)
    add_trigger(db, task_catalog_id=tid, kind="schedule", config=_SCHEDULE)
    add_trigger(db, task_catalog_id=tid, kind="manual", config={})
    db.commit()
    assert len(list_triggers(db, task_catalog_id=tid)) == 2

    db.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :id"), {"id": tid})
    db.commit()
    db._tasks.remove(tid)

    orphans = db.execute(
        sql_text("SELECT COUNT(*) FROM moc_task_trigger WHERE task_catalog_id = :id"),
        {"id": tid},
    ).scalar()
    assert orphans == 0  # cascaded


def test_add_trigger_to_unknown_task_is_rejected(db):
    with pytest.raises(TriggerValidationError, match="not found"):
        add_trigger(db, task_catalog_id=str(uuid.uuid4()), kind="manual", config={})


def test_patch_revalidates_resulting_config(db):
    tid = _make_task(db)
    trig = add_trigger(db, task_catalog_id=tid, kind="manual", config={})
    db.commit()
    # Flip manual → event with a bad (string) conditions → REJECTED on patch.
    with pytest.raises(TriggerValidationError, match="must be a list"):
        patch_trigger(db, trigger_id=trig.id, kind="event",
                      config={"event": "order.created", "conditions": "bad"})
    # A valid flip succeeds.
    patch_trigger(db, trigger_id=trig.id, kind="event", config=_EVENT)
    db.commit()
    assert list_triggers(db, task_catalog_id=tid)[0].kind == "event"


# ── API smoke (the HTTP layer + auth + error mapping) ──────────────────


@pytest.fixture
def api():
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app
    from app.models.platform_user import PlatformUser

    s = SessionLocal()
    trigger_events.seed_events(s)
    suffix = _uuid.uuid4().hex[:6]
    pu = PlatformUser(
        id=str(_uuid.uuid4()), email=f"trig-{suffix}@bridgeable.test",
        hashed_password="x", first_name="P", last_name="A",
        role="super_admin", is_active=True,
    )
    s.add(pu)
    task = create_task(s, vertical=VERT, name=f"API Trig {suffix}")
    s.commit()
    token = create_access_token({"sub": pu.id}, realm="platform")
    yield {
        "client": TestClient(app),
        "h": {"Authorization": f"Bearer {token}"},
        "task_id": task.id,
    }
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :id"), {"id": task.id})
    s.execute(sql_text("DELETE FROM platform_users WHERE id = :id"), {"id": pu.id})
    s.commit()
    s.close()


def test_api_requires_platform_auth(api):
    assert api["client"].get("/api/platform/admin/moc/trigger-events").status_code in (401, 403)


def test_api_trigger_events_lists_the_catalog(api):
    resp = api["client"].get("/api/platform/admin/moc/trigger-events", headers=api["h"])
    assert resp.status_code == 200
    keys = [e["event_key"] for e in resp.json()]
    assert "order.created" in keys


def test_api_trigger_crud_roundtrip(api):
    c, h, tid = api["client"], api["h"], api["task_id"]
    # Add an event trigger with a structured condition.
    add = c.post(
        f"/api/platform/admin/moc/tasks/{tid}/triggers",
        json={"kind": "event", "config": _EVENT},
        headers=h,
    )
    assert add.status_code == 201, add.text
    trig_id = add.json()["id"]
    assert add.json()["config"]["conditions"] == _EVENT["conditions"]

    # List.
    lst = c.get(f"/api/platform/admin/moc/tasks/{tid}/triggers", headers=h)
    assert lst.status_code == 200 and len(lst.json()) == 1

    # Patch label.
    patch = c.patch(f"/api/platform/admin/moc/triggers/{trig_id}",
                    json={"label": "On new funeral order"}, headers=h)
    assert patch.status_code == 200 and patch.json()["label"] == "On new funeral order"

    # Delete.
    assert c.delete(f"/api/platform/admin/moc/triggers/{trig_id}", headers=h).status_code == 200


def test_api_flat_string_condition_400(api):
    c, h, tid = api["client"], api["h"], api["task_id"]
    resp = c.post(
        f"/api/platform/admin/moc/tasks/{tid}/triggers",
        json={"kind": "event", "config": {"event": "order.created", "conditions": "order_type==funeral"}},
        headers=h,
    )
    assert resp.status_code == 400
    assert "list" in resp.json()["detail"]
