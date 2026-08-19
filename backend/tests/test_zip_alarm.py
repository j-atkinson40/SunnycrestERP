"""TAX-2 B-2 — the alarm is swept, and it watches the set that costs money.

⚠️ THE ALARM WAS NOT DEAD. IT WAS UNSWEPT, AND THAT READ AS DEAD.
`run_incomplete_customer_profile_job` sat in `PROACTIVE_JOBS` — a registry that
IS consumed, by `POST /jobs/run/{job_name}` (`api/routes/proactive_agents.py:29`,
admin-only) — while `scheduler.py` imported its siblings by name and not this
one. Two registries, one swept. The unswept one read as working because its
entries were present and correct, and an alarm you can only fire by hand is an
alarm nobody fires. The first report on this called it dead and recommended
deleting it; deleting it would have removed a live manual capability AND the one
mechanism that catches TAX-2 B-2's defect regrowing.

⚠️ AND IT WATCHED A SET THAT IS EMPTY ON EVERY TENANT. It counted
`setup_complete=False`, of which production has ZERO — while 21 of 22 customers
carry no ZIP and therefore charge no sales tax. Scheduling it without changing
what it counts would have produced a nightly job that ran correctly, found
nothing, and reported all-clear on the exact defect the arc exists to fix. The
cheapest possible failure: a green alarm over a live problem.

⚠️ THE TWO SETS DIVERGE IN BOTH DIRECTIONS, WHICH IS WHY THERE ARE TWO
INDICATORS AND NOT ONE REWORDED ONE. `setup_complete` is a ONE-WAY FLAG —
`quick_create_customer` (`customer_service.py:899`) is its only writer and
`CustomerUpdate` carries no field for it, so nothing can set it back. A customer
created inline and afterwards given a full address keeps the flag forever while
taxing correctly. Meanwhile an imported customer is `setup_complete=True` and may
have arrived with no ZIP at all. Attaching the tax sentence to `setup_complete`
would tell an operator that taxable customers are untaxable, and vice versa.

Requires a database. Uses the canonical tenant fixture (create-scoped teardown).
"""
from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy import text

from app.services.customer_service import (
    count_customers_without_zip,
    get_incomplete_customer_count,
)
from tests._source import code_only
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID

# ⚠️ `behavioral_insights` IS HERE BECAUSE `generate_insight` COMMITS. The job
# under test raises a real insight, and that row OUTLIVES this file's rollback —
# so the `db` fixture's rollback is not sufficient teardown for the one test that
# runs the job end to end. Discovered by the litter tripwire on the bare axis,
# where it presented as a FK violation blocking the company DELETE.
canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("behavioral_insights", "customers"),
)

BACKEND = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def db():
    """Nothing here commits; the rollback is the teardown."""
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _customer(db, *, zip_code=None, billing_zip=None, setup_complete=True,
              is_active=True, tenant=TENANT) -> str:
    cid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO customers (id, company_id, name, zip_code, billing_zip,"
            " setup_complete, is_active, created_at, updated_at)"
            " VALUES (:i, :c, :n, :z, :b, :s, :a, now(), now())"
        ),
        {"i": cid, "c": tenant, "n": f"Fixture {cid[:8]}", "z": zip_code,
         "b": billing_zip, "s": setup_complete, "a": is_active},
    )
    db.flush()
    return cid


class TestEveryProactiveJobIsSwept:
    """⚠️ THE RATCHET, AND THE ONE TEST THAT WOULD HAVE CAUGHT THIS ORIGINALLY.

    The specific bug was one job missing from `scheduler.py`. The CLASS of bug is
    two registries where only one is swept, and asserting only about THIS job
    would leave the next unswept alarm to be found the same way — by someone
    noticing months later that a correct alarm never said anything.

    ⚠️ AND THE FIRST VERSION OF THIS TEST WAS TOO WEAK TO CATCH ITS OWN BUG.
    It asserted each job's name appeared ANYWHERE in `scheduler.py`, which a
    wrapper function satisfies whether or not anything calls it — a wrapper
    nothing registers is the same defect wearing a different hat. Deleting the
    nightly entry left it green. It now resolves wrapper → registration through
    `register_all_jobs`, the single function where every `add_job` happens, and
    fails on that deletion.

    Matched against comment-stripped source, per `tests/_source`: the scheduler
    wrapper's own docstring names the function it schedules, so an un-stripped
    match would pass on the documentation of the fix rather than the fix.
    """

    @staticmethod
    def _registration_body() -> str:
        """Source of `register_all_jobs` only — where scheduling actually happens."""
        import ast

        src = code_only((BACKEND / "app" / "scheduler.py").read_text())
        tree = ast.parse(src)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "register_all_jobs")
        return ast.get_source_segment(src, fn) or ""

    def test_every_registered_proactive_job_is_reachable_from_registration(self):
        import ast

        from app.services.proactive_agents import PROACTIVE_JOBS

        src = code_only((BACKEND / "app" / "scheduler.py").read_text())
        tree = ast.parse(src)
        # wrapper name -> the run_* functions its body names
        wrappers = {
            n.name: {d.id for d in ast.walk(n) if isinstance(d, ast.Name)}
            | {d.attr for d in ast.walk(n) if isinstance(d, ast.Attribute)}
            for n in tree.body if isinstance(n, ast.FunctionDef)
        }
        registration = self._registration_body()

        unswept = []
        for fn in PROACTIVE_JOBS.values():
            callers = [w for w, names in wrappers.items() if fn.__name__ in names]
            if not any(w in registration for w in callers):
                unswept.append(fn.__name__)
        assert not unswept, (
            "these proactive jobs are registered but `register_all_jobs` never "
            f"schedules them — they can only ever fire by hand: {sorted(unswept)}"
        )

    def test_the_zip_alarm_is_in_the_nightly_run(self):
        """The narrow claim, held separately so a failure says which broke.

        `JOB_REGISTRY` alone is NOT sufficient evidence of scheduling — it is
        the manual-trigger table, and membership in it is exactly the state this
        job was already in while never running.
        """
        from app import scheduler as sched

        assert "incomplete_customer_profile" in sched.JOB_REGISTRY
        code = code_only((BACKEND / "app" / "scheduler.py").read_text())
        nightly = code.split("nightly_jobs = [")[1].split("]")[0]
        assert "incomplete_customer_profile" in nightly, (
            "the job is manually triggerable but not in the nightly list — "
            "which is precisely the state it shipped in and stayed in"
        )


class TestTheCountWatchesWhatCostsMoney:
    """⚠️ `get_jurisdiction_for_order` READS `zip_code or billing_zip` AND HAS NO
    CITY PATH. So the taxable/untaxable line is drawn by those two columns and
    nothing else, and the count has to be drawn the same way or the alarm speaks
    about the wrong customers."""

    def test_a_customer_with_no_zip_at_all_is_counted(self, db):
        before = count_customers_without_zip(db, TENANT)
        _customer(db)
        assert count_customers_without_zip(db, TENANT) == before + 1

    def test_a_billing_zip_alone_is_enough(self, db):
        """The resolver falls back to it, so flagging this customer would be a
        false alarm on a customer that taxes correctly."""
        before = count_customers_without_zip(db, TENANT)
        _customer(db, billing_zip="13021")
        assert count_customers_without_zip(db, TENANT) == before

    def test_an_empty_string_counts_as_missing(self, db):
        """⚠️ A BLANK IS NOT A ZIP, AND IT IS THE LIKELIER SHAPE AFTER AN IMPORT.
        `zip_code.strip()[:5]` resolves nothing while the column LOOKS populated,
        so a count keyed on `IS NULL` would report healthy over the failure."""
        before = count_customers_without_zip(db, TENANT)
        _customer(db, zip_code="")
        _customer(db, zip_code="   ")
        assert count_customers_without_zip(db, TENANT) == before + 2

    def test_inactive_customers_are_not_counted(self, db):
        before = count_customers_without_zip(db, TENANT)
        _customer(db, is_active=False)
        assert count_customers_without_zip(db, TENANT) == before

    def test_the_count_is_tenant_scoped(self, db):
        """Every count in this arc is scoped; an alarm that leaks across tenants
        tells one operator about another's data."""
        other = db.execute(
            text("SELECT id FROM companies WHERE id <> :t LIMIT 1"), {"t": TENANT}
        ).scalar()
        if other is None:
            pytest.skip("single-tenant database")
        before = count_customers_without_zip(db, TENANT)
        _customer(db, tenant=other)
        assert count_customers_without_zip(db, TENANT) == before


class TestTheTwoSetsAreNotInterchangeable:
    def test_setup_complete_can_never_be_set_back_to_true(self):
        """⚠️ THE FACT THAT FORCED TWO INDICATORS INSTEAD OF ONE REWORDED ONE.

        If `CustomerUpdate` ever gains the field, the flag stops being one-way,
        the two sets converge, and the decision to keep the amber dot on
        provenance wording is worth revisiting. Failing here is the prompt to do
        that — not a bug in the new field.
        """
        from app.schemas.customer import CustomerUpdate

        assert "setup_complete" not in CustomerUpdate.model_fields, (
            "setup_complete is now clearable — revisit whether the amber dot "
            "and the ZIP indicator are still measuring different things"
        )

    def test_a_zipless_customer_alerts_even_with_no_incomplete_profiles(self, db):
        """⚠️ THE PRODUCTION CASE, AND THE REGRESSION THAT MATTERS MOST. Every
        tenant has zero `setup_complete=False` customers and many with no ZIP. An
        alarm that early-returns on the incomplete count alone is silent exactly
        where the problem is."""
        from app.services.proactive_agents import run_incomplete_customer_profile_job

        _customer(db, setup_complete=True, zip_code=None)
        assert get_incomplete_customer_count(db, TENANT) == 0
        assert count_customers_without_zip(db, TENANT) > 0

        result = run_incomplete_customer_profile_job(db, TENANT)
        assert result["alerted"] is True, (
            "no ZIPs on file and the alarm said nothing — which is the state it "
            "would have shipped in"
        )
        assert result["no_zip_count"] > 0


class TestOneSentenceForOneFact:
    """⚠️ THREE SURFACES STATE THIS FACT AND THEY HAVE TO STATE IT THE SAME WAY.
    An operator who meets one phrasing in the create form, the tax card and the
    nightly alarm learns the distinction between untaxed and exempt. Three
    phrasings of one fact teach nothing, and this is the distinction that carries
    the liability — zero tax because nothing resolved and zero tax because a
    certificate applies are the same number and different obligations."""

    PHRASE = "not the same as"

    def test_the_alarm_carries_it(self):
        src = (BACKEND / "app" / "services" / "proactive_agents.py").read_text()
        body = code_only(src).split("def run_incomplete_customer_profile_job")[1]
        body = body.split("\ndef ")[0]
        assert self.PHRASE in body and "exempt" in body

    def test_the_create_form_carries_it(self):
        src = (BACKEND.parent / "frontend" / "src" / "pages" / "customers.tsx").read_text()
        assert self.PHRASE in src and "exempt" in src

    def test_the_tax_card_carries_it(self):
        import importlib

        seed = importlib.import_module("scripts.seed_suite_jobs")
        beat = [nb for jn, bk, _o, nb in seed.BEAT_REWRITES
                if jn == "File sales tax" and bk == "today-resolve"][-1]
        assert self.PHRASE in beat["text"].lower()
        assert "exempt" in beat["text"].lower()


class TestTheLinkGoesSomewhereThatExists:
    def test_the_alarm_does_not_link_to_a_filter_that_was_never_built(self):
        """It pointed at `/customers?filter=incomplete`. `customers.tsx` reads no
        `filter` param, so the link landed on the unfiltered list and looked like
        it had worked — the same shape as the resolve beat linking at
        `/settings/tax` where the rates were already correct."""
        src = (BACKEND / "app" / "services" / "proactive_agents.py").read_text()
        assert "filter=incomplete" not in code_only(src)
