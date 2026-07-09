"""C-10 heal — schema-drift check + r124 heal-guard pins.

The edited-after-applied migration class: a migration file edited after an
environment recorded its revision never re-runs there; fresh-DB CI rebuilds
from the EDITED file so it always matches; only the live schema knows its
own history. Staging carried a quotes table missing the f1g2h3i4j5k6 block
for months this way (every Quote ORM query 500'd). The boot-time drift
check is the only witness this class has; r124 is the guarded heal.
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from app.database import engine
from app.services.schema_drift import assert_no_schema_drift, find_schema_drift

_R124_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic" / "versions" / "r124_heal_quotes_quick_quote_columns.py"
)


def _load_r124():
    spec = importlib.util.spec_from_file_location("r124_heal", _R124_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _quotes_columns(conn) -> dict[str, str]:
    return {
        r[0]: r[1] for r in conn.execute(text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name='quotes'"
        ))
    }


class TestDriftCheck:
    def test_healthy_dev_db_is_clean(self):
        assert find_schema_drift(engine) == []

    def test_missing_column_is_caught_loud_with_precise_name(self):
        """Simulate the staging condition: hide a model-mapped column (rename,
        committed, restored in finally), assert the check names it exactly and
        the boot wrapper raises."""
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE quotes RENAME COLUMN customer_name TO _drift_probe_hidden"
            ))
        try:
            drift = find_schema_drift(engine)
            assert "quotes.customer_name" in drift
            with pytest.raises(RuntimeError, match="quotes.customer_name"):
                assert_no_schema_drift(engine)
        finally:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE quotes RENAME COLUMN _drift_probe_hidden TO customer_name"
                ))
        assert "quotes.customer_name" not in find_schema_drift(engine)

    def test_boot_cost_is_bounded(self):
        """The boot-cost tripwire: names-only information_schema pass. Cold
        measured ~500 ms on the 60k-tenant dev DB; warm ~17 ms. Bound
        generously — this pins against reintroducing per-table reflection
        (the inspector approach measured 11+ SECONDS on the same DB)."""
        find_schema_drift(engine)  # warm the catalog
        t0 = time.perf_counter()
        find_schema_drift(engine)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"drift check took {elapsed:.2f}s — reflection crept back in?"


class TestR124HealGuards:
    def test_r124_is_noop_on_healthy_db(self):
        """All 11 columns present + customer_id already nullable → the
        guarded upgrade produces zero schema delta. Run inside a rolled-back
        transaction against dev."""
        from alembic.runtime.migration import MigrationContext
        from alembic.operations import Operations

        mod = _load_r124()
        with engine.connect() as c0:
            before = set(_quotes_columns(c0))
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    mod.upgrade()
                assert set(_quotes_columns(conn)) == before
            finally:
                trans.rollback()

    def test_r124_heals_a_stale_quotes_table(self):
        """The staging condition in miniature: strip the f1g2 block inside a
        transaction, run r124's upgrade(), assert every column is back and
        customer_id is nullable again. Rolled back — dev untouched."""
        from alembic.runtime.migration import MigrationContext
        from alembic.operations import Operations

        mod = _load_r124()
        block = [name for name, _ in mod._QUOTES_BLOCK]
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                for name in block:
                    conn.execute(text(f"ALTER TABLE quotes DROP COLUMN {name}"))
                # NOTE: the customer_id NOT-NULL half of the simulation can't
                # run against dev (live walk-in quotes carry NULLs) — the
                # relax path was witnessed against the simulated-stale DB
                # (schema-only clone; see the r124 commit message) and its
                # guard no-op is asserted below.

                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    mod.upgrade()

                cols = _quotes_columns(conn)
                for name in block:
                    assert name in cols, f"r124 failed to heal quotes.{name}"
                assert cols["customer_id"] == "YES"  # relax re-applied
            finally:
                trans.rollback()

    def test_r124_downgrade_is_noop(self):
        """One-way heal: downgrade must never drop columns (they belong
        canonically to f1g2h3i4j5k6 on healthy DBs)."""
        from alembic.runtime.migration import MigrationContext
        from alembic.operations import Operations

        mod = _load_r124()
        with engine.connect() as c0:
            before = set(_quotes_columns(c0))
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    mod.downgrade()
                assert set(_quotes_columns(conn)) == before
            finally:
                trans.rollback()
