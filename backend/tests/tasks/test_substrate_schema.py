"""Task substrate v1 — schema + migration tests.

Verifies r107 migration produces the expected table shape:
- task_details table exists with 21 columns
- 6 indexes (5 regular + 1 partial-unique idempotency)
- CHECK constraints on enum-shaped columns
- UNIQUE constraint on vault_item_id (1:1 enforcement)
- FK CASCADE on vault_item_id
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect, text

from app.database import SessionLocal


def _inspector():
    db = SessionLocal()
    try:
        return inspect(db.bind), db
    finally:
        pass  # caller closes


def test_task_details_table_exists():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        assert "task_details" in insp.get_table_names()
    finally:
        db.close()


def test_task_details_has_expected_columns():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        cols = {c["name"] for c in insp.get_columns("task_details")}
        expected = {
            "id", "vault_item_id", "assignee_realm", "assignee_user_id",
            "assignee_portal_user_id", "lifecycle_shape", "current_state",
            "provenance_kind", "provenance_ref_type", "provenance_ref_id",
            "event_kind", "visibility", "priority", "due_date",
            "due_datetime", "assigned_at", "completed_at",
            "resolution_outcome", "suppression_key", "created_at",
            "updated_at",
        }
        missing = expected - cols
        assert not missing, f"missing columns: {missing}"
    finally:
        db.close()


def test_task_details_indexes_present():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        idx_names = {i["name"] for i in insp.get_indexes("task_details")}
        # 5 indexes named via the migration's create_index calls.
        expected = {
            "ix_task_details_vault_item_id",
            "ix_task_details_assignee_state",
            "ix_task_details_due_date",
            "ix_task_details_provenance",
            "ix_task_details_lifecycle_state",
            "uq_task_details_idempotency",
        }
        missing = expected - idx_names
        assert not missing, (
            f"missing indexes: {missing} (have: {idx_names})"
        )
    finally:
        db.close()


def test_idempotency_index_is_unique():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        idx_list = insp.get_indexes("task_details")
        idem = [
            i for i in idx_list
            if i["name"] == "uq_task_details_idempotency"
        ]
        assert idem, "uq_task_details_idempotency not found"
        assert idem[0]["unique"] is True


    finally:
        db.close()


def test_check_constraints_present():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        checks = {c["name"] for c in insp.get_check_constraints("task_details")}
        expected = {
            "ck_task_details_assignee_realm",
            "ck_task_details_lifecycle_shape",
            "ck_task_details_visibility",
            "ck_task_details_priority",
            "ck_task_details_provenance_kind",
        }
        missing = expected - checks
        assert not missing, f"missing checks: {missing}"
    finally:
        db.close()


def test_vault_item_id_unique_constraint():
    """UNIQUE on vault_item_id enforces 1:1 with VaultItem."""
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="UQ-test",
            slug=f"uq-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)
        vi = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="x",
        )
        db.add(vi)
        db.flush()
        td1 = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="manual_creation",
            event_kind="manual",
        )
        db.add(td1)
        db.flush()
        # Adding a second task_details row pointing at the same vault_item
        # must fail.
        td2 = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="manual_creation",
            event_kind="manual",
        )
        db.add(td2)
        with pytest.raises(Exception):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_idempotency_partial_unique_constraint():
    """Two task_details rows with same composite key + non-null ref_id
    must fail to insert."""
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="IDEM-test",
            slug=f"idem-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)

        vi1 = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="t1",
        )
        vi2 = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="t2",
        )
        db.add(vi1)
        db.add(vi2)
        db.flush()

        ref_id = str(uuid.uuid4())
        td1 = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi1.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="anomaly_detection",
            provenance_ref_type="agent_anomaly",
            provenance_ref_id=ref_id,
            event_kind="produced",
        )
        td2 = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi2.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="anomaly_detection",
            provenance_ref_type="agent_anomaly",
            provenance_ref_id=ref_id,
            event_kind="produced",
        )
        db.add(td1)
        db.flush()
        db.add(td2)
        with pytest.raises(Exception):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_partial_unique_allows_null_provenance_ref():
    """Partial unique skips rows where provenance_ref_id IS NULL.
    Multiple manual-creation tasks with no ref are legal."""
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="NULL-test",
            slug=f"null-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)
        for i in range(3):
            vi = VaultItem(
                id=str(uuid.uuid4()),
                vault_id=vault.id,
                company_id=co.id,
                item_type="task",
                title=f"t{i}",
            )
            db.add(vi)
            db.flush()
            td = TaskDetails(
                id=str(uuid.uuid4()),
                vault_item_id=vi.id,
                lifecycle_shape="action",
                current_state="created",
                provenance_kind="manual_creation",
                provenance_ref_id=None,
                event_kind="manual",
            )
            db.add(td)
        # All three flush cleanly because provenance_ref_id is NULL.
        db.flush()
    finally:
        db.rollback()
        db.close()


def test_check_constraint_rejects_invalid_lifecycle_shape():
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="CHK-test",
            slug=f"chk-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)
        vi = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="x",
        )
        db.add(vi)
        db.flush()
        td = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi.id,
            lifecycle_shape="bogus_shape",
            current_state="x",
            provenance_kind="manual_creation",
            event_kind="manual",
        )
        db.add(td)
        with pytest.raises(Exception):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_check_constraint_rejects_invalid_provenance_kind():
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="CHK2-test",
            slug=f"chk2-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)
        vi = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="x",
        )
        db.add(vi)
        db.flush()
        td = TaskDetails(
            id=str(uuid.uuid4()),
            vault_item_id=vi.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="bogus_kind",
            event_kind="manual",
        )
        db.add(td)
        with pytest.raises(Exception):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_vault_item_cascade_delete():
    """Deleting the VaultItem cascades to task_details."""
    from app.models.company import Company
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from app.services.vault_service import get_or_create_company_vault

    db = SessionLocal()
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name="CASCADE-test",
            slug=f"cascade-test-{uuid.uuid4().hex[:6]}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        vault = get_or_create_company_vault(db, co.id)
        vi = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="cascade-target",
        )
        db.add(vi)
        db.flush()
        td_id = str(uuid.uuid4())
        td = TaskDetails(
            id=td_id,
            vault_item_id=vi.id,
            lifecycle_shape="action",
            current_state="created",
            provenance_kind="manual_creation",
            event_kind="manual",
        )
        db.add(td)
        db.flush()

        # Delete vault_item — cascade should remove task_details.
        db.execute(
            text("DELETE FROM vault_items WHERE id = :id"),
            {"id": vi.id},
        )
        db.flush()

        remaining = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == td_id)
            .first()
        )
        assert remaining is None, (
            "task_details survived VaultItem deletion — CASCADE not working"
        )
    finally:
        db.rollback()
        db.close()
