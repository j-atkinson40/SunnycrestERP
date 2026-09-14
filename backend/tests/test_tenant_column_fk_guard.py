"""Every tenant-scoped column carries a foreign key to `companies.id`.

⚠️ THIS GUARD EXISTS BECAUSE THE ALTERNATIVE WAS A HAND-MAINTAINED LIST.

`tests/_cleanup.py::purge_companies_by_slug` deletes from 72 tables and its own
docstring has said for months: *"of 387 tables with a FK path to companies, this
helper covered 58 … THE OTHER 322 ARE STILL UNCOVERED … it fails on whichever
table a new test first populates — silently."* Measured 2026-09-14: of the 20
tables that had no constraint, it covered exactly one.

Extending that list would work until the next table. The constraint is what
actually closes it, and this guard is what stops a new table being added without
one.

⚠️ THE POPULATION IS DERIVED, NEVER DECLARED. It is read from
`information_schema` at run time, so a table added tomorrow is in scope tomorrow
with nobody updating anything. A declared list is precisely the failure mode
this replaces — and `test_job_outcome_ratchet`'s POPULATION, right in this
suite, is the worked example of a declared list being correct about one question
and then read as the answer to another.

WHY AN FK RATHER THAN CLEANUP. An orphaned row can only land in a table with no
constraint. Deleting a company is ordinary test behaviour; it produces litter
ONLY where a constraint is missing. So this is not a rule about how tests should
behave — it is the removal that makes the bad state unexpressible, per CLAUDE.md
§11's "removal before recognition".

⚠️ IT DOES NOT ASSERT AN `ON DELETE` RULE. Existence is the invariant; the rule
is a per-table judgement. `CASCADE` suits derived data at a leaf, `NO ACTION`
suits a child whose loss should block the parent's delete. Both satisfy this
guard, and neither can orphan.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

TENANT_COLUMNS = ("company_id", "tenant_id")


def _conn():
    from app.database import engine

    return engine.connect()


def _tenant_scoped_columns(conn) -> set[tuple[str, str]]:
    return {
        (r[0], r[1])
        for r in conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name = ANY(:c)"
            ),
            {"c": list(TENANT_COLUMNS)},
        ).all()
    }


def _columns_with_company_fk(conn) -> set[tuple[str, str]]:
    return {
        (r[0], r[1])
        for r in conn.execute(
            text("""
                SELECT tc.table_name, k.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage k
                     ON k.constraint_name = tc.constraint_name
                JOIN information_schema.constraint_column_usage u
                     ON u.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND u.table_name = 'companies' AND u.column_name = 'id'
                  AND k.column_name = ANY(:c)
            """),
            {"c": list(TENANT_COLUMNS)},
        ).all()
    }


def _unconstrained(conn) -> list[str]:
    scoped = _tenant_scoped_columns(conn)
    constrained = _columns_with_company_fk(conn)
    return sorted(f"{t}.{c}" for t, c in scoped - constrained)


# ── the guard ────────────────────────────────────────────────────────────


def test_every_tenant_scoped_column_has_a_company_fk():
    """⚠️ A RED HERE IS A WORKLIST, NOT A MYSTERY — it names every offender.

    If you have just added a table with a `company_id` or `tenant_id`, give the
    column `ForeignKey("companies.id", ondelete=...)` in the model AND a
    migration. Both: the model is where the convention lives, and twenty columns
    reached this state because fourteen models declared a plain `String(36)`.
    """
    with _conn() as conn:
        missing = _unconstrained(conn)
    assert missing == [], (
        f"{len(missing)} tenant-scoped column(s) have no foreign key to "
        f"companies.id, so deleting a company strands their rows silently:\n  "
        + "\n  ".join(missing)
    )


# ── controls ─────────────────────────────────────────────────────────────


def test_the_enumeration_is_NOT_EMPTY_and_sees_the_real_surface():
    """⚠️ CONTROL. An assertion that a set is empty is satisfied for free by an
    enumeration that finds nothing. This proves the query sees the surface."""
    with _conn() as conn:
        scoped = _tenant_scoped_columns(conn)
        constrained = _columns_with_company_fk(conn)
    assert len(scoped) > 300, f"only {len(scoped)} tenant-scoped columns found"
    assert len(constrained) > 300, f"only {len(constrained)} carry an FK"
    assert constrained <= scoped, (
        "columns claim an FK to companies.id but are not tenant-scoped columns — "
        "the two queries disagree about the population"
    )


def test_the_detector_DISCRIMINATES(monkeypatch):
    """⚠️ CONTROL. Hide one column's FK; the guard must name that column.

    Without this, green proves the two queries return the same rows — which is
    also what two identically-broken queries return.
    """
    import tests.test_tenant_column_fk_guard as mod

    with _conn() as conn:
        real = _columns_with_company_fk(conn)
    assert real, "no constrained columns at all — the control cannot run"
    victim = sorted(real)[0]

    monkeypatch.setattr(mod, "_columns_with_company_fk", lambda c: real - {victim})
    with _conn() as conn:
        missing = mod._unconstrained(conn)
    assert f"{victim[0]}.{victim[1]}" in missing
    assert len(missing) == len(
        [x for x in missing if x != f"{victim[0]}.{victim[1]}"]
    ) + 1


def test_the_guard_reads_the_DATABASE_not_the_models():
    """⚠️ CONTROL ON THE SOURCE. A guard built from the ORM would pass whenever
    the models are self-consistent, including when the database disagrees with
    them — which is the case it exists to catch. It must read
    information_schema, and it must not import a model to do so.
    """
    import inspect

    import tests.test_tenant_column_fk_guard as mod

    # ⚠️ SCOPED TO THE QUERY FUNCTIONS, NOT THE MODULE. A first version read
    # `getsource(mod)` and failed on the forbidden strings appearing in THIS
    # test's own source — a control tripping over the literals it searches for.
    sources = "".join(
        inspect.getsource(f)
        for f in (mod._tenant_scoped_columns, mod._columns_with_company_fk,
                  mod._unconstrained)
    )
    assert "information_schema" in sources
    for forbidden in ("app.models", "__table__", "Base.metadata"):
        assert forbidden not in sources, (
            f"the guard references {forbidden} — it would be reading the models, "
            "not the database"
        )
