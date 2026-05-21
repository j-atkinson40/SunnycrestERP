"""Tests for r105 widget_definitions composition substrate migration.

Exercises the migration via the local DB engine: upgrade → downgrade
→ upgrade full cycle, schema verification, CHECK constraint
enforcement, and backfill correctness on pre-existing
widget_definitions rows.

WB-1 reconnaissance sub-arc per investigation
`docs/investigations/2026-05-21-widget-builder.md` Area 7. Mirrors
the r104 migration test pattern (importlib direct-load + DB-side
inspector assertions).
"""

from __future__ import annotations

import importlib.util
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
    "r105_widget_definitions_composition_extension.py",
)
_spec = importlib.util.spec_from_file_location(
    "r105_widget_definitions_composition_extension",
    os.path.abspath(_MIGRATION_PATH),
)
assert _spec is not None and _spec.loader is not None
r105 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r105)


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


def test_revision_chain_anchored_at_r104():
    """r105 must chain off r104 (current head before WB-1)."""
    assert r105.revision == "r105_widget_definitions_composition_extension"
    assert r105.down_revision == "r104_migrate_focus_templates_to_freeform"


def test_migration_module_exposes_canonical_helpers():
    """Module-level shape sanity check — catches accidental rename."""
    assert hasattr(r105, "upgrade")
    assert hasattr(r105, "downgrade")
    assert r105._TABLE == "widget_definitions"
    assert r105._CHECK_NAME == (
        "ck_widget_definitions_composition_blob_version_paired"
    )


def test_full_cycle_upgrade_downgrade_upgrade(db_engine):
    """The migration must round-trip cleanly via the alembic CLI.

    Pre-condition: alembic upgrade head ran via the test bootstrap;
    the columns are already present. We test by mock-running each
    pass via the migration's idempotent guards.
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with db_engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        # First: assert schema is already upgraded (columns present).
        cols = _existing_columns(conn, "widget_definitions")
        assert "composition_blob" in cols
        assert "composition_version" in cols
        assert "tier_scope" in cols
        assert "last_edit_session_id" in cols
        assert "last_edit_session_at" in cols
        assert "last_edit_session_actor_id" in cols

        # Downgrade.
        op_proxy = Operations(ctx)
        from alembic import op as alembic_op

        original = getattr(alembic_op, "_proxy", None)
        try:
            alembic_op._proxy = op_proxy
            r105.downgrade()
        finally:
            if original is not None:
                alembic_op._proxy = original

        cols_after_down = _existing_columns(conn, "widget_definitions")
        assert "composition_blob" not in cols_after_down
        assert "composition_version" not in cols_after_down
        assert "tier_scope" not in cols_after_down
        assert "last_edit_session_id" not in cols_after_down
        assert "last_edit_session_at" not in cols_after_down
        assert "last_edit_session_actor_id" not in cols_after_down

        checks_after_down = _existing_check_names(conn, "widget_definitions")
        assert r105._CHECK_NAME not in checks_after_down

        # Re-upgrade.
        try:
            alembic_op._proxy = op_proxy
            r105.upgrade()
        finally:
            if original is not None:
                alembic_op._proxy = original

        cols_after_up = _existing_columns(conn, "widget_definitions")
        assert "composition_blob" in cols_after_up
        assert "composition_version" in cols_after_up
        assert "tier_scope" in cols_after_up
        assert "last_edit_session_id" in cols_after_up
        assert "last_edit_session_at" in cols_after_up
        assert "last_edit_session_actor_id" in cols_after_up

        checks_after_up = _existing_check_names(conn, "widget_definitions")
        assert r105._CHECK_NAME in checks_after_up


_INSERT_SQL = (
    "INSERT INTO widget_definitions "
    "(id, widget_id, title, page_contexts, variants, "
    "default_variant_id, required_vertical, required_product_line, "
    "supported_surfaces, default_surfaces, intelligence_keywords, "
    "tier_scope"
    "{extra_cols}) "
    "VALUES (:id, :widget_id, :title, CAST(:page_contexts AS jsonb), "
    "CAST(:variants AS jsonb), :default_variant_id, "
    "CAST(:required_vertical AS jsonb), "
    "CAST(:required_product_line AS jsonb), "
    "CAST(:supported_surfaces AS jsonb), "
    "CAST(:default_surfaces AS jsonb), "
    "CAST(:intelligence_keywords AS jsonb), "
    ":tier_scope"
    "{extra_vals})"
)


def _base_row(*, widget_id: str, title: str, tier_scope: str = "platform") -> dict:
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
        "tier_scope": tier_scope,
    }


def test_check_constraint_rejects_blob_without_version(db_engine):
    """The CHECK enforces blob+version jointly present-or-absent."""
    suffix = uuid.uuid4().hex[:8]
    bad_row = _base_row(widget_id=f"test-bad-{suffix}", title="Bad widget")
    bad_row["composition_blob"] = '{"schema_version": 1}'
    with db_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    _INSERT_SQL.format(
                        extra_cols=", composition_blob",
                        extra_vals=", CAST(:composition_blob AS jsonb)",
                    )
                ),
                bad_row,
            )


def test_check_constraint_rejects_version_without_blob(db_engine):
    suffix = uuid.uuid4().hex[:8]
    bad_row = _base_row(widget_id=f"test-bad2-{suffix}", title="Bad widget 2")
    bad_row["composition_version"] = 1
    with db_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    _INSERT_SQL.format(
                        extra_cols=", composition_version",
                        extra_vals=", :composition_version",
                    )
                ),
                bad_row,
            )


def test_check_constraint_accepts_both_null(db_engine):
    """Legacy hand-coded widget shape: both NULL is valid."""
    suffix = uuid.uuid4().hex[:8]
    legacy_row = _base_row(
        widget_id=f"test-legacy-{suffix}", title="Legacy widget"
    )
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(_INSERT_SQL.format(extra_cols="", extra_vals="")),
            legacy_row,
        )
        conn.execute(
            sa.text("DELETE FROM widget_definitions WHERE id = :id"),
            {"id": legacy_row["id"]},
        )


def test_check_constraint_accepts_both_populated(db_engine):
    """Composed widget shape: blob + version both populated is valid."""
    suffix = uuid.uuid4().hex[:8]
    composed_row = _base_row(
        widget_id=f"test-composed-{suffix}",
        title="Composed widget",
        tier_scope="vertical",
    )
    composed_row["composition_blob"] = (
        '{"schema_version": 1, "root_atom_id": "a1", '
        '"atom_tree": {}, "variants": [], "bindings_catalog": {}}'
    )
    composed_row["composition_version"] = 1
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                _INSERT_SQL.format(
                    extra_cols=", composition_blob, composition_version",
                    extra_vals=(
                        ", CAST(:composition_blob AS jsonb), "
                        ":composition_version"
                    ),
                )
            ),
            composed_row,
        )
        conn.execute(
            sa.text("DELETE FROM widget_definitions WHERE id = :id"),
            {"id": composed_row["id"]},
        )


def test_tier_scope_enum_rejects_invalid_value(db_engine):
    suffix = uuid.uuid4().hex[:8]
    bad_row = _base_row(
        widget_id=f"test-tier-{suffix}",
        title="Bad tier widget",
        tier_scope="tenant",  # not in {platform, vertical}
    )
    with db_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(_INSERT_SQL.format(extra_cols="", extra_vals="")),
                bad_row,
            )


def test_backfill_set_all_existing_to_platform(db_engine):
    """After r105 upgrade, every existing widget_definitions row
    carries tier_scope='platform'. The migration backfilled them."""
    with db_engine.connect() as conn:
        result = conn.execute(
            sa.text(
                "SELECT tier_scope FROM widget_definitions "
                "WHERE composition_blob IS NULL"
            )
        ).fetchall()
        # Empty DB is also acceptable (test bootstrap may not seed).
        for (tier,) in result:
            assert tier == "platform", (
                f"backfill should set every legacy row to 'platform'; "
                f"got {tier!r}"
            )
