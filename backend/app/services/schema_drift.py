"""Boot-time schema-drift check — model→DB, fail loud (C-10 heal, 2026-07-09).

WHY THIS EXISTS: fresh-DB tests can never catch the edited-after-applied
migration class — CI rebuilds the schema from the EDITED file, so it always
matches the models. Only a live database knows its own history. Staging
carried a `quotes` table missing the f1g2h3i4j5k6 quotes block for months
(the migration was edited after staging recorded it; alembic never re-ran
it): every Quote ORM query 500'd, QUOTE_AUTO_EXPIRY failed nightly, and
nothing surfaced it because CI was green and the errors lived in warn-tier
logs. This check is the only witness that class has.

CONTRACT: at startup, one inspector pass diffs every model-mapped table
against the live DB. A model-mapped column missing from its table (or a
model-mapped table missing entirely) FAILS THE BOOT — the deploy never
serves, same tier as a failed migration. DB-extra columns/tables are noise,
not breakage (e.g. the orphaned `tenant_settings` table) — ignored.

COST: one information_schema.columns query for names only — measured on
local PostgreSQL 16 (~240 mapped tables, 60k-tenant dev DB) at ~500 ms
cold / ~17 ms warm. We deliberately do NOT use SQLAlchemy's inspector
reflection (get_multi_columns) — it fetches types/defaults/comments per
column and measured 11+ SECONDS on the same DB. Names are all a
missing-column check needs.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def find_schema_drift(engine: Engine) -> list[str]:
    """Return sorted 'table.column' / 'table (missing table)' drift entries.

    Model→DB direction only: everything the ORM maps must exist in the DB.
    Empty list = no drift.
    """
    from app.database import Base
    import app.models  # noqa: F401 — ensure every model is registered

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )).all()
    db_columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        db_columns.setdefault(table_name, set()).add(column_name)

    drift: list[str] = []
    for table in Base.metadata.tables.values():
        db_cols = db_columns.get(table.name)
        if db_cols is None:
            drift.append(f"{table.name} (missing table)")
            continue
        for col in table.columns:
            if col.name not in db_cols:
                drift.append(f"{table.name}.{col.name}")
    return sorted(drift)


def assert_no_schema_drift(engine: Engine) -> None:
    """Fail-loud wrapper for the boot path. Raises RuntimeError on drift."""
    t0 = time.perf_counter()
    drift = find_schema_drift(engine)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if drift:
        raise RuntimeError(
            "SCHEMA DRIFT — the live database is missing columns the ORM maps "
            "(edited-after-applied migration class; alembic will not self-heal "
            "this). Refusing to serve. Author a guarded heal migration (r124 "
            f"precedent). Missing: {', '.join(drift)}"
        )
    from app.database import Base

    logger.info(
        "Schema drift check: clean (%d tables, %.1f ms)",
        len(Base.metadata.tables), elapsed_ms,
    )
