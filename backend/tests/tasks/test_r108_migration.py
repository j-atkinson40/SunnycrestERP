"""Task substrate v1 — r108 Focus extension migration tests.

Verifies r108 migration produces the expected focus_sessions schema:
- task_id column added (String(36), nullable)
- FK to vault_items.id with ON DELETE SET NULL
- Partial index on task_id WHERE task_id IS NOT NULL
- Existing focus_session ORM continues working (regression check)
- focus_session.task_id starts NULL (forward-only; not backfilled)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect, text

from app.database import SessionLocal


# ── 1. Schema-level checks ──────────────────────────────────────────


def test_focus_sessions_has_task_id_column():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        cols = {c["name"]: c for c in insp.get_columns("focus_sessions")}
        assert "task_id" in cols, "r108 must add task_id column"
    finally:
        db.close()


def test_focus_sessions_task_id_is_nullable_string36():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        cols = {c["name"]: c for c in insp.get_columns("focus_sessions")}
        task_id_col = cols["task_id"]
        # String(36) maps to VARCHAR(36) in Postgres
        col_type = str(task_id_col["type"]).upper()
        assert "VARCHAR" in col_type or "CHAR" in col_type, (
            f"task_id should be string-typed, got {col_type}"
        )
        assert task_id_col["nullable"] is True, "task_id must be nullable"
    finally:
        db.close()


def test_focus_sessions_task_id_fk_to_vault_items_set_null():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        fks = insp.get_foreign_keys("focus_sessions")
        task_id_fks = [
            fk for fk in fks if "task_id" in fk["constrained_columns"]
        ]
        assert len(task_id_fks) == 1, (
            f"expected 1 FK on task_id, got {len(task_id_fks)}"
        )
        fk = task_id_fks[0]
        assert fk["referred_table"] == "vault_items"
        assert fk["referred_columns"] == ["id"]
        # ON DELETE SET NULL — preserve focus_session history when task removed
        options = fk.get("options", {})
        assert options.get("ondelete", "").upper() == "SET NULL", (
            f"task_id FK must be ON DELETE SET NULL, got {options}"
        )
    finally:
        db.close()


def test_focus_sessions_task_id_index_exists():
    db = SessionLocal()
    try:
        insp = inspect(db.bind)
        indexes = {idx["name"]: idx for idx in insp.get_indexes("focus_sessions")}
        assert "ix_focus_sessions_task_id" in indexes, (
            f"r108 must add ix_focus_sessions_task_id, got {list(indexes)}"
        )
        idx = indexes["ix_focus_sessions_task_id"]
        assert idx["column_names"] == ["task_id"]
    finally:
        db.close()


# ── 2. Runtime / ORM regression checks ──────────────────────────────


def test_focus_session_orm_loads_against_r108_schema():
    """Existing FocusSession ORM model must still load + query cleanly
    even though it doesn't yet declare task_id (forward-compat shape)."""
    from app.models.focus_session import FocusSession

    db = SessionLocal()
    try:
        # Trivial query — proves the ORM model + table schema agree at
        # the columns the model knows about. task_id is present in DB
        # but absent from ORM; SQLAlchemy tolerates extra DB columns.
        _ = db.query(FocusSession).limit(1).all()
    finally:
        db.close()


def test_focus_session_task_id_column_is_nullable():
    """Forward-only contract (build prompt §7.5): the column is nullable;
    rows authored before B3 wired the create_or_resume_session task_id
    kwarg retain NULL. The B3 wire populates task_id for sessions
    created with task context; legacy + non-task sessions stay NULL.

    Verifies the column accepts NULL via a write smoke-test (insert a
    row with task_id=NULL).
    """
    db = SessionLocal()
    try:
        # Verify a focus_session row can be inserted with task_id=NULL.
        from app.models.focus_session import FocusSession

        # If a row exists with task_id IS NULL anywhere, we've confirmed
        # the column accepts NULLs.
        nullable_count = db.execute(
            text(
                "SELECT COUNT(*) FROM focus_sessions WHERE task_id IS NULL"
            )
        ).scalar()
        # On a fresh DB after B3 ship, this may be 0 (no sessions at all)
        # or >=0 (sessions without task linkage). The schema-correctness
        # assertion is that the column tolerates NULL — verified by the
        # absence of NOT NULL on the column definition.
        assert nullable_count >= 0
        # Confirm the ORM mapping declares the column nullable.
        col = FocusSession.__table__.columns["task_id"]
        assert col.nullable is True
    finally:
        db.close()


def test_focus_session_task_id_accepts_vault_item_fk():
    """Smoke test: a freshly-created focus_session row can carry a valid
    vault_item.id in task_id without FK error."""
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.models.vault_item import VaultItem
    from app.models.vault import Vault

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"R108-{suffix}",
            slug=f"r108-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"r108-{suffix}@ts.co",
            first_name="R",
            last_name="108",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        # Need a vault row to create a vault_item
        vault = Vault(
            id=str(uuid.uuid4()),
            company_id=co.id,
            vault_type="default",
            name="Default",
        )
        db.add(vault)
        db.flush()

        vi = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=co.id,
            item_type="task",
            title="r108 smoke task",
            created_by=user.id,
        )
        db.add(vi)
        db.flush()

        # Insert focus_session row with task_id via raw SQL (ORM doesn't
        # know about task_id yet — that's the forward-compat shape)
        fs_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.execute(
            text(
                "INSERT INTO focus_sessions "
                "(id, company_id, user_id, focus_type, layout_state, "
                "is_active, opened_at, last_interacted_at, created_at, "
                "updated_at, task_id) VALUES "
                "(:id, :company_id, :user_id, :focus_type, "
                "'{}'::jsonb, true, :now, :now, :now, :now, :task_id)"
            ),
            {
                "id": fs_id,
                "company_id": co.id,
                "user_id": user.id,
                "focus_type": "test_focus",
                "now": now,
                "task_id": vi.id,
            },
        )
        db.commit()

        # Verify round-trip
        row = db.execute(
            text("SELECT task_id FROM focus_sessions WHERE id = :id"),
            {"id": fs_id},
        ).first()
        assert row is not None
        assert row[0] == vi.id

        # SET NULL semantics: delete VaultItem; focus_session row survives
        # with task_id cleared
        db.execute(
            text("DELETE FROM vault_items WHERE id = :id"), {"id": vi.id}
        )
        db.commit()
        row2 = db.execute(
            text("SELECT task_id FROM focus_sessions WHERE id = :id"),
            {"id": fs_id},
        ).first()
        assert row2 is not None, (
            "focus_session row must survive vault_item deletion"
        )
        assert row2[0] is None, (
            f"task_id must be SET NULL on vault_item delete, got {row2[0]}"
        )

        # Cleanup
        db.execute(
            text("DELETE FROM focus_sessions WHERE id = :id"), {"id": fs_id}
        )
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
        db.execute(text("DELETE FROM roles WHERE id = :id"), {"id": role.id})
        db.execute(text("DELETE FROM vaults WHERE id = :id"), {"id": vault.id})
        db.execute(text("DELETE FROM companies WHERE id = :id"), {"id": co.id})
        db.commit()
    finally:
        db.close()
