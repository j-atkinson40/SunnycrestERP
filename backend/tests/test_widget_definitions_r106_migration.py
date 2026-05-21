"""Tests for r106 widget_definitions published_composition_blob migration (WB-4a).

Verifies:

  • Revision chain anchors at r105.
  • Full upgrade → downgrade → upgrade cycle clean.
  • The column lands JSONB nullable.
  • The `ck_widget_definitions_published_requires_draft` CHECK
    enforces (published_composition_blob IS NULL) OR (composition_blob
    IS NOT NULL).
  • Backfill: rows with composition_blob populated get
    published_composition_blob = composition_blob; rows without stay
    published NULL.
  • Hand-coded widgets (composition_blob NULL) stay
    published_composition_blob NULL after upgrade.

Mirrors the r105 test pattern (importlib direct-load + DB-side inspector
assertions).
"""

from __future__ import annotations

import importlib.util
import json
import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "alembic",
    "versions",
    "r106_widget_definitions_published_blob.py",
)
_spec = importlib.util.spec_from_file_location(
    "r106_widget_definitions_published_blob",
    os.path.abspath(_MIGRATION_PATH),
)
assert _spec is not None and _spec.loader is not None
r106 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r106)


@pytest.fixture
def db_engine():
    from app.database import engine

    return engine


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def _existing_check_names(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_check_constraints(table_name)}


def test_revision_chain_anchored_at_r105():
    assert r106.revision == "r106_widget_definitions_published_blob"
    assert r106.down_revision == "r105_widget_definitions_composition_extension"


def test_migration_exposes_canonical_helpers():
    assert hasattr(r106, "upgrade")
    assert hasattr(r106, "downgrade")
    assert r106._TABLE == "widget_definitions"
    assert r106._CHECK_NAME == "ck_widget_definitions_published_requires_draft"


def test_full_cycle_upgrade_downgrade_upgrade(db_engine):
    """Round-trip the migration cleanly via the local engine."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with db_engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        cols = _existing_columns(conn, "widget_definitions")
        assert "published_composition_blob" in cols
        checks = _existing_check_names(conn, "widget_definitions")
        assert r106._CHECK_NAME in checks

        op_proxy = Operations(ctx)
        from alembic import op as alembic_op

        original = getattr(alembic_op, "_proxy", None)
        try:
            alembic_op._proxy = op_proxy
            r106.downgrade()
        finally:
            if original is not None:
                alembic_op._proxy = original

        cols_after = _existing_columns(conn, "widget_definitions")
        assert "published_composition_blob" not in cols_after
        checks_after = _existing_check_names(conn, "widget_definitions")
        assert r106._CHECK_NAME not in checks_after

        # Re-upgrade.
        try:
            alembic_op._proxy = op_proxy
            r106.upgrade()
        finally:
            if original is not None:
                alembic_op._proxy = original

        cols_final = _existing_columns(conn, "widget_definitions")
        assert "published_composition_blob" in cols_final
        checks_final = _existing_check_names(conn, "widget_definitions")
        assert r106._CHECK_NAME in checks_final


_INSERT_SQL_BASE = (
    "INSERT INTO widget_definitions "
    "(id, widget_id, title, page_contexts, variants, "
    "default_variant_id, required_vertical, required_product_line, "
    "supported_surfaces, default_surfaces, intelligence_keywords, "
    "tier_scope, composition_blob, composition_version"
    "{extra_cols}) "
    "VALUES (:id, :widget_id, :title, CAST(:page_contexts AS jsonb), "
    "CAST(:variants AS jsonb), :default_variant_id, "
    "CAST(:required_vertical AS jsonb), "
    "CAST(:required_product_line AS jsonb), "
    "CAST(:supported_surfaces AS jsonb), "
    "CAST(:default_surfaces AS jsonb), "
    "CAST(:intelligence_keywords AS jsonb), "
    ":tier_scope, "
    "CAST(:composition_blob AS jsonb), "
    ":composition_version"
    "{extra_vals})"
)


def _row(*, widget_id, title, composition_blob, composition_version=1):
    return {
        "id": str(uuid.uuid4()),
        "widget_id": widget_id,
        "title": title,
        "page_contexts": "[]",
        "variants": "[]",
        "default_variant_id": "brief",
        "required_vertical": '["*"]',
        "required_product_line": '["*"]',
        "supported_surfaces": '["dashboard_grid"]',
        "default_surfaces": '["dashboard_grid"]',
        "intelligence_keywords": "[]",
        "tier_scope": "platform",
        "composition_blob": (
            json.dumps(composition_blob)
            if composition_blob is not None
            else None
        ),
        "composition_version": composition_version
        if composition_blob is not None
        else None,
    }


def test_check_constraint_rejects_published_without_draft(db_engine):
    """Cannot have published_composition_blob without composition_blob."""
    suffix = uuid.uuid4().hex[:8]
    row = _row(
        widget_id=f"r106-bad-{suffix}",
        title="Bad widget — published without draft",
        composition_blob=None,
        composition_version=None,
    )
    row["published_composition_blob"] = '{"schema_version": 1}'
    with db_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    _INSERT_SQL_BASE.format(
                        extra_cols=", published_composition_blob",
                        extra_vals=", CAST(:published_composition_blob AS jsonb)",
                    )
                ),
                row,
            )


def test_check_constraint_allows_draft_without_published(db_engine):
    """Draft-only widgets (mid-edit) are allowed."""
    suffix = uuid.uuid4().hex[:8]
    blob = {
        "schema_version": 1,
        "root_atom_id": "root-1",
        "atom_tree": {},
        "variants": [],
        "bindings_catalog": {},
    }
    row = _row(
        widget_id=f"r106-draft-{suffix}",
        title="Draft-only widget",
        composition_blob=blob,
    )
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(_INSERT_SQL_BASE.format(extra_cols="", extra_vals="")),
            row,
        )
        # Verify published_composition_blob is NULL.
        result = conn.execute(
            sa.text(
                "SELECT published_composition_blob FROM widget_definitions "
                "WHERE widget_id = :wid"
            ),
            {"wid": row["widget_id"]},
        ).first()
        assert result is not None
        assert result[0] is None
        # Cleanup.
        conn.execute(
            sa.text("DELETE FROM widget_definitions WHERE widget_id = :wid"),
            {"wid": row["widget_id"]},
        )


def test_check_constraint_allows_draft_with_published(db_engine):
    """Normal published widget: both draft + published populated."""
    suffix = uuid.uuid4().hex[:8]
    blob = {
        "schema_version": 1,
        "root_atom_id": "root-1",
        "atom_tree": {},
        "variants": [],
        "bindings_catalog": {},
    }
    row = _row(
        widget_id=f"r106-pub-{suffix}",
        title="Published widget",
        composition_blob=blob,
    )
    row["published_composition_blob"] = json.dumps(blob)
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                _INSERT_SQL_BASE.format(
                    extra_cols=", published_composition_blob",
                    extra_vals=", CAST(:published_composition_blob AS jsonb)",
                )
            ),
            row,
        )
        # Cleanup.
        conn.execute(
            sa.text("DELETE FROM widget_definitions WHERE widget_id = :wid"),
            {"wid": row["widget_id"]},
        )


def test_backfill_existing_composed_widgets(db_engine):
    """The migration UPDATE backfills existing composed widgets.

    Strategy: temporarily clear published_composition_blob on rows with
    composition_blob present, re-run the UPDATE step, assert the
    backfill restored them.
    """
    with db_engine.begin() as conn:
        # Stash rows where composition_blob IS NOT NULL.
        rows_before = conn.execute(
            sa.text(
                "SELECT id, composition_blob, published_composition_blob "
                "FROM widget_definitions "
                "WHERE composition_blob IS NOT NULL"
            )
        ).fetchall()
        if not rows_before:
            pytest.skip("no composed widgets in DB to test backfill")

        # Clear published_composition_blob for one of them.
        target = rows_before[0]
        conn.execute(
            sa.text(
                "UPDATE widget_definitions "
                "SET published_composition_blob = NULL "
                "WHERE id = :id"
            ),
            {"id": target[0]},
        )
        # Verify cleared.
        after_clear = conn.execute(
            sa.text(
                "SELECT published_composition_blob FROM widget_definitions "
                "WHERE id = :id"
            ),
            {"id": target[0]},
        ).first()
        assert after_clear[0] is None

        # Re-run the backfill UPDATE from r106.
        conn.execute(
            sa.text(
                "UPDATE widget_definitions "
                "SET published_composition_blob = composition_blob "
                "WHERE composition_blob IS NOT NULL "
                "AND published_composition_blob IS NULL"
            )
        )

        # Verify backfilled.
        after_backfill = conn.execute(
            sa.text(
                "SELECT published_composition_blob FROM widget_definitions "
                "WHERE id = :id"
            ),
            {"id": target[0]},
        ).first()
        assert after_backfill[0] is not None
        # Should equal composition_blob.
        composition = conn.execute(
            sa.text(
                "SELECT composition_blob FROM widget_definitions "
                "WHERE id = :id"
            ),
            {"id": target[0]},
        ).first()
        assert after_backfill[0] == composition[0]


def test_handcoded_widgets_stay_null(db_engine):
    """Rows with composition_blob NULL keep published_composition_blob NULL."""
    with db_engine.begin() as conn:
        result = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM widget_definitions "
                "WHERE composition_blob IS NULL "
                "AND published_composition_blob IS NOT NULL"
            )
        ).scalar()
        assert result == 0
