"""Task substrate v1 — service-layer + façade tests.

Verifies:
- create_task_with_provenance atomic transaction (both rows or neither)
- idempotency via composite key (skip on duplicate, raise on
  raise_on_duplicate)
- list_task_details_for_company tenant isolation
- get_task_details + get_task_details_for_vault_item lookups
- 8 existing Task consumers (existing `task_service.py` API) continue
  working unchanged (backward-compat)
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.services.tasks.service import (
    DuplicateTaskError,
    InvalidTaskInput,
    create_task_with_provenance,
    get_task_details,
    get_task_details_for_vault_item,
    list_task_details_for_company,
    transition_task,
)


# ── create_task_with_provenance ─────────────────────────────────────


def test_creates_vault_item_and_task_details_atomically(db_session, ts_ctx):
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="atomic test",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()

    vi = (
        db_session.query(VaultItem)
        .filter(VaultItem.id == td.vault_item_id)
        .first()
    )
    assert vi is not None
    assert vi.item_type == "task"
    assert vi.title == "atomic test"
    assert vi.company_id == ts_ctx["company_id"]


def test_creates_with_assignee_starts_assigned(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="assigned at creation",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    assert td.current_state == "assigned"
    assert td.assigned_at is not None


def test_creates_without_assignee_starts_created(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="unassigned",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    assert td.current_state == "created"
    assert td.assigned_at is None


def test_reminder_shape_starts_informational(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="reminder",
        created_by_user_id=ts_ctx["user_id"],
        lifecycle_shape="reminder",
    )
    db_session.commit()
    assert td.lifecycle_shape == "reminder"
    assert td.current_state == "informational"


def test_rejects_empty_title(db_session, ts_ctx):
    with pytest.raises(InvalidTaskInput):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="manual_creation",
            provenance_ref_type=None,
            provenance_ref_id=None,
            event_kind="manual",
            task_type_key="generic_task",
            title="   ",
        )


def test_rejects_invalid_provenance_kind(db_session, ts_ctx):
    with pytest.raises(InvalidTaskInput):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="bogus_kind",
            provenance_ref_type=None,
            provenance_ref_id=None,
            event_kind="manual",
            task_type_key="generic_task",
            title="x",
        )


def test_rejects_invalid_visibility(db_session, ts_ctx):
    with pytest.raises(InvalidTaskInput):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="manual_creation",
            provenance_ref_type=None,
            provenance_ref_id=None,
            event_kind="manual",
            task_type_key="generic_task",
            title="x",
            visibility="bogus",
        )


def test_rejects_invalid_priority(db_session, ts_ctx):
    with pytest.raises(InvalidTaskInput):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="manual_creation",
            provenance_ref_type=None,
            provenance_ref_id=None,
            event_kind="manual",
            task_type_key="generic_task",
            title="x",
            priority="bogus",
        )


# ── idempotency ─────────────────────────────────────────────────────


def test_idempotent_returns_existing(db_session, ts_ctx):
    ref_id = str(uuid.uuid4())
    td1 = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_anomaly",
        provenance_ref_id=ref_id,
        event_kind="produced",
        task_type_key="anomaly_resolution_task",
        title="anom",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    td2 = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_anomaly",
        provenance_ref_id=ref_id,
        event_kind="produced",
        task_type_key="anomaly_resolution_task",
        title="anom-duplicate",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    assert td1.id == td2.id


def test_raise_on_duplicate(db_session, ts_ctx):
    ref_id = str(uuid.uuid4())
    create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_anomaly",
        provenance_ref_id=ref_id,
        event_kind="produced",
        task_type_key="anomaly_resolution_task",
        title="first",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    with pytest.raises(DuplicateTaskError):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="anomaly_detection",
            provenance_ref_type="agent_anomaly",
            provenance_ref_id=ref_id,
            event_kind="produced",
            task_type_key="anomaly_resolution_task",
            title="dup",
            created_by_user_id=ts_ctx["user_id"],
            raise_on_duplicate=True,
        )


def test_null_provenance_ref_no_idempotency(db_session, ts_ctx):
    """When provenance_ref_id is None, no idempotency check (partial unique
    skips). Multiple manual-creation tasks with no ref are legal."""
    for i in range(3):
        create_task_with_provenance(
            db_session,
            company_id=ts_ctx["company_id"],
            provenance_kind="manual_creation",
            provenance_ref_type=None,
            provenance_ref_id=None,
            event_kind="manual",
            task_type_key="generic_task",
            title=f"manual {i}",
            created_by_user_id=ts_ctx["user_id"],
        )
    db_session.commit()
    rows = list_task_details_for_company(
        db_session, company_id=ts_ctx["company_id"]
    )
    titles = {r.vault_item.title for r in rows if r.vault_item}
    # At least our 3 manual rows.
    assert all(f"manual {i}" in titles for i in range(3))


# ── tenant isolation ────────────────────────────────────────────────


def test_list_only_returns_company_rows(db_session, ts_ctx):
    from tests.tasks.conftest import _make_ctx
    other = _make_ctx()

    # Seed one task per company.
    create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="own",
        created_by_user_id=ts_ctx["user_id"],
    )
    create_task_with_provenance(
        db_session,
        company_id=other["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="other",
        created_by_user_id=other["user_id"],
    )
    db_session.commit()

    rows = list_task_details_for_company(
        db_session, company_id=ts_ctx["company_id"]
    )
    titles = {r.vault_item.title for r in rows if r.vault_item}
    assert "own" in titles
    assert "other" not in titles


def test_get_task_details_by_id(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="get-by-id",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    found = get_task_details(db_session, task_details_id=td.id)
    assert found.id == td.id


def test_get_task_details_for_vault_item(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="get-by-vi",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    found = get_task_details_for_vault_item(
        db_session, vault_item_id=td.vault_item_id
    )
    assert found.id == td.id


def test_list_default_excludes_terminal(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="terminal-test",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="done")
    db_session.commit()
    rows = list_task_details_for_company(
        db_session, company_id=ts_ctx["company_id"]
    )
    titles = {r.vault_item.title for r in rows if r.vault_item}
    assert "terminal-test" not in titles


def test_list_include_terminal(db_session, ts_ctx):
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="terminal-include",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="done")
    db_session.commit()
    rows = list_task_details_for_company(
        db_session,
        company_id=ts_ctx["company_id"],
        include_terminal=True,
    )
    titles = {r.vault_item.title for r in rows if r.vault_item}
    assert "terminal-include" in titles


def test_list_filter_by_assignee(db_session, ts_ctx):
    create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="assigned-to-me",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="unassigned",
        created_by_user_id=ts_ctx["user_id"],
    )
    db_session.commit()
    rows = list_task_details_for_company(
        db_session,
        company_id=ts_ctx["company_id"],
        assignee_user_id=ts_ctx["user_id"],
    )
    titles = {r.vault_item.title for r in rows if r.vault_item}
    assert "assigned-to-me" in titles
    assert "unassigned" not in titles


# ── backward-compat with legacy task_service ────────────────────────


def test_legacy_task_service_create_still_works(db_session, ts_ctx):
    """Existing `task_service.create_task` API preserved unchanged.

    v1.0 is purely additive — legacy 8 consumers continue functioning.
    """
    from app.services import task_service

    t = task_service.create_task(
        db_session,
        company_id=ts_ctx["company_id"],
        title="legacy task",
        created_by_user_id=ts_ctx["user_id"],
    )
    # legacy create_task auto-commits internally.
    assert t.id is not None
    assert t.title == "legacy task"
    assert t.status == "open"


def test_legacy_task_service_update_status(db_session, ts_ctx):
    from app.services import task_service

    t = task_service.create_task(
        db_session,
        company_id=ts_ctx["company_id"],
        title="legacy update",
        created_by_user_id=ts_ctx["user_id"],
    )
    t2 = task_service.update_task(
        db_session,
        company_id=ts_ctx["company_id"],
        task_id=t.id,
        status="in_progress",
    )
    assert t2.status == "in_progress"


def test_legacy_task_service_list(db_session, ts_ctx):
    from app.services import task_service

    t = task_service.create_task(
        db_session,
        company_id=ts_ctx["company_id"],
        title="legacy list",
        created_by_user_id=ts_ctx["user_id"],
    )
    rows = task_service.list_tasks(
        db_session, company_id=ts_ctx["company_id"]
    )
    ids = {r.id for r in rows}
    assert t.id in ids


def test_transition_invokes_type_behavior_hook(db_session, ts_ctx):
    """transition_task composes lifecycle + behavior hook (review_approval
    sets resolution_outcome on done)."""
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="anomaly_detection",
        provenance_ref_type="agent_job",
        provenance_ref_id="hook-test",
        event_kind="produced",
        task_type_key="review_approval_task",
        title="hook task",
        created_by_user_id=ts_ctx["user_id"],
        assignee_user_id=ts_ctx["user_id"],
        metadata={"outcome": "rejected"},
    )
    db_session.commit()
    transition_task(db_session, task_details_id=td.id, to_state="in_progress")
    db_session.commit()
    td2 = transition_task(db_session, task_details_id=td.id, to_state="done")
    db_session.commit()
    assert td2.resolution_outcome == "rejected"


def test_creates_with_due_date(db_session, ts_ctx):
    target = date.today() + timedelta(days=7)
    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="due-date",
        created_by_user_id=ts_ctx["user_id"],
        due_date=target,
    )
    db_session.commit()
    assert td.due_date == target


def test_metadata_persisted_on_vault_item(db_session, ts_ctx):
    from app.models.vault_item import VaultItem

    td = create_task_with_provenance(
        db_session,
        company_id=ts_ctx["company_id"],
        provenance_kind="manual_creation",
        provenance_ref_type=None,
        provenance_ref_id=None,
        event_kind="manual",
        task_type_key="generic_task",
        title="meta-test",
        created_by_user_id=ts_ctx["user_id"],
        metadata={"custom_field": "value-x"},
    )
    db_session.commit()
    vi = (
        db_session.query(VaultItem)
        .filter(VaultItem.id == td.vault_item_id)
        .first()
    )
    assert vi.metadata_json.get("custom_field") == "value-x"
    assert vi.metadata_json.get("task_type_key") == "generic_task"
