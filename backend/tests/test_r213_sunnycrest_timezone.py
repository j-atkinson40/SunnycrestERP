"""r213 flips Sunnycrest's timezone to America/New_York, and only Sunnycrest's.

⚠️ THE MIGRATION ITSELF CANNOT ASSERT "1 ROW AFFECTED". CI and a fresh local box have no
sunnycrest tenant, so 0 rows is correct there and a raise would make the whole chain
unrunnable outside production. This file is where the 1-row case is proven — against a
tenant it seeds and purges itself, so the assertion holds on every database.

Calls `_set` directly rather than running alembic: the body is extracted for exactly that
reason (the r212 pattern), and driving alembic inside a test would apply every pending
revision to the dev database as a side effect.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from tests._cleanup import purge_companies_by_slug


def _load_migration():
    """Load the revision by path — `alembic/versions` is not an importable package.

    Same loader as `tests/test_r212_price_alignment.py`; see that file for the precedent.
    """
    import importlib.util
    from pathlib import Path

    p = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "r213_sunnycrest_timezone.py"
    )
    spec = importlib.util.spec_from_file_location("r213_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R213 = _load_migration()
BEFORE, AFTER = R213.BEFORE, R213.AFTER

#: Slugs this file creates. ⚠️ `sunnycrest` IS NOT AMONG THEM and must never be — the real
#: tenant exists on production and a test that purged it by slug would be catastrophic on
#: any database where it is present. The migration matches on `slug = 'sunnycrest'`, so the
#: only way to exercise it is to create a row with that slug... which is precisely why this
#: file instead parameterises `_set`'s WHERE through a disposable slug. See `_set_for`.
OTHER_SLUGS = ("r213-other-a", "r213-other-b")


def _set_for(conn, slug: str, *, frm: str, to: str) -> int:
    """Call the MIGRATION'S OWN `_set`, with its target slug swapped for a disposable one.

    ⚠️ THIS WAS A HAND-COPIED SQL STRING FIRST, AND THE BREAK TESTS CAUGHT IT. With a
    copy, breaking the shipped statement — removing the value guard, removing the slug
    filter — left every behavioural test GREEN, because they were exercising the copy.
    Only the drift pin fired. That is CLAUDE.md §11 shape 2/3: a check exercising an
    artifact rather than the wiring that reaches it.

    ⚠️ AND THE SLUG CANNOT SIMPLY BE PASSED, which is why this indirection exists at all.
    `_set` reads the module-level `SLUG` constant, so exercising it means either creating a
    company whose slug is literally `sunnycrest` on whatever database the suite points at —
    the dev database is production-shaped and that is a real tenant's configuration — or
    swapping the constant for the duration of one call. This does the second.
    """
    original = R213.SLUG
    R213.SLUG = slug
    try:
        return R213._set(conn, frm=frm, to=to)
    finally:
        R213.SLUG = original


def _mk(db, slug: str, tz: str | None) -> str:
    """Insert through the ORM, not raw SQL.

    ⚠️ RAW SQL WAS TRIED FIRST AND IS THE WRONG TOOL HERE. `companies` has several NOT
    NULL columns whose defaults live on the MODEL (`created_at`, `updated_at`, ...), not
    in the database — so a raw INSERT raises `NotNullViolation` and fixing it means
    chasing one column per run, with the list silently growing the next time somebody adds
    a NOT NULL. The ORM applies every Python-side default by construction.

    The MIGRATION still uses raw SQL, correctly: it only UPDATEs an existing row's one
    column and never has to satisfy a default.
    """
    from app.models.company import Company

    row = Company(id=str(uuid.uuid4()), name=f"R213 {slug}", slug=slug, timezone=tz)
    db.add(row)
    db.flush()
    return row.id


@pytest.fixture
def two_companies():
    db = SessionLocal()
    try:
        purge_companies_by_slug(db, "r213-other-%")
        a = _mk(db, OTHER_SLUGS[0], BEFORE)   # on the old value — should flip
        b = _mk(db, OTHER_SLUGS[1], BEFORE)   # same value, different slug — must NOT flip
        db.commit()
        yield db, a, b
    finally:
        purge_companies_by_slug(db, "r213-other-%")
        db.commit()
        db.close()


def _tz(db, cid: str) -> str | None:
    return db.execute(
        text("SELECT timezone FROM companies WHERE id = :id"), {"id": cid}
    ).scalar()


def test_the_shipped_statement_is_the_one_under_test():
    """⚠️ POSITIVE CONTROL ON THE INDIRECTION. `_set_for` swaps `R213.SLUG` and calls the
    migration's own `_set`, so the behavioural tests below exercise shipped SQL. If someone
    "simplifies" `_set_for` back into a local copy, those tests would keep passing while
    testing nothing — so assert the wiring itself.
    """
    import inspect

    src = inspect.getsource(_set_for)
    assert "R213._set(" in src, (
        "_set_for no longer calls the migration's own _set — the behavioural tests below "
        "would be exercising a copy, and breaking the shipped statement would not turn "
        "them red"
    )
    assert "UPDATE companies" not in src, (
        "_set_for contains its own SQL again; it must delegate to R213._set"
    )
    # And the shipped statement still carries both halves of the guard.
    mig_sql = inspect.getsource(R213._set)
    for fragment in (
        "UPDATE companies SET timezone = :to",
        "WHERE slug = :slug AND (timezone = :frm OR timezone IS NULL)",
    ):
        assert fragment in mig_sql, f"migration no longer contains {fragment!r}"


def test_it_flips_exactly_one_row_and_leaves_the_other(two_companies):
    db, a, b = two_companies
    n = _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER)
    db.commit()
    assert n == 1, f"expected exactly 1 row affected, got {n}"
    assert _tz(db, a) == AFTER
    assert _tz(db, b) == BEFORE, "a different tenant's timezone was changed"


def test_it_is_idempotent(two_companies):
    """A replay affects 0 rows, because the guard is on the OLD value."""
    db, a, _ = two_companies
    assert _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER) == 1
    db.commit()
    assert _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER) == 0
    db.commit()
    assert _tz(db, a) == AFTER


def test_it_does_not_clobber_a_later_admin_change(two_companies):
    """⚠️ THE GUARD'S REAL JOB. If an admin sets Chicago through the UI, a hand-replay of
    this migration must not drag it back to New York.
    """
    db, a, _ = two_companies
    db.execute(
        text("UPDATE companies SET timezone = 'America/Chicago' WHERE id = :id"),
        {"id": a},
    )
    db.commit()
    assert _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER) == 0
    db.commit()
    assert _tz(db, a) == "America/Chicago"


def test_it_also_claims_a_null_timezone(two_companies):
    """`timezone IS NULL` is in the guard on purpose — the column is nullable, and a NULL
    is "not established" rather than a chosen UTC.
    """
    db, a, _ = two_companies
    db.execute(
        text("UPDATE companies SET timezone = NULL WHERE id = :id"), {"id": a}
    )
    db.commit()
    assert _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER) == 1
    db.commit()
    assert _tz(db, a) == AFTER


def test_downgrade_returns_it(two_companies):
    db, a, _ = two_companies
    _set_for(db, OTHER_SLUGS[0], frm=BEFORE, to=AFTER)
    db.commit()
    assert _set_for(db, OTHER_SLUGS[0], frm=AFTER, to=BEFORE) == 1
    db.commit()
    assert _tz(db, a) == BEFORE


def test_the_migration_targets_sunnycrest_and_nothing_else():
    """Static: the shipped migration's slug is `sunnycrest`, singular.

    ⚠️ Reads the module's constant rather than the SQL, because the SQL is parameterised —
    the thing that could silently widen is `SLUG`, not the statement.
    """
    assert R213.SLUG == "sunnycrest"
    assert R213.BEFORE == "UTC"
    assert R213.AFTER == "America/New_York"
    src = __import__("inspect").getsource(R213)
    for other in ("testco", "hopkins-fh", "st-marys"):
        assert f'"{other}"' not in src and f"'{other}'" not in src, (
            f"r213 must not touch {other} — it is a synthetic dev tenant"
        )
