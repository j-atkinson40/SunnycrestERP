"""TAX-3 r171 — rates as platform data, effective-dated, out of tenant reach.

⚠️ THE TABLE'S DEFINING PROPERTY IS A COLUMN IT DOES NOT HAVE.
`scripts/wipe_tenant.py:106` deletes `tax_rates` and `tax_jurisdictions`
filtered by tenant. Had platform rates been added as a nullable `tenant_id` on
the existing table, a sentinel or mis-scoped row would be reachable by a routine
tenant teardown — the platform's rate table deleted by a tenant wipe, reported
as success. `platform_tax_rates` has no tenant column at all, so a query
filtering `tenant_id` cannot name it. That is the STOP condition the
investigation raised, and `TestATenantWipeCannotReachIt` is what holds it.

⚠️ AND THE FILE IT REPLACES WAS WRONG FOR NINETEEN MONTHS.
`data/us-county-tax-rates.json` had one commit, no updater, no owner and no
test; it disagreed with Publication 718 on nine New York counties. Suffolk shows
the whole cycle — enacted 17 Dec 2024, effective 1 Mar 2025, file compiled
2025-01-01 and never touched. Effective dating exists so that a change is an
INSERT closing the prior row rather than an UPDATE that silently restates what
an old invoice recomputes as.

Nothing bills from this table yet. `TaxJurisdiction.tax_rate_id` still points at
tenant `tax_rates`; repointing it, and giving the resolver an `on_date` so
effective dating means something at the point of sale, is a separate step. What
IS wired is the onboarding suggestion path, which now prefers the table and
falls back to the file for states that have not been loaded.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parent.parent
RATE_FILE = BACKEND / "data" / "us-county-tax-rates.json"


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _row(db, *, county, rate, code="9999", name=None, state="NY",
         effective_from=date(2025, 3, 1), effective_to=None):
    from app.models.tax import PlatformTaxRate

    r = PlatformTaxRate(
        id=str(uuid.uuid4()), state=state, jurisdiction_code=code,
        jurisdiction_name=name or f"{county} test", county=county,
        rate_percentage=rate, effective_from=effective_from,
        effective_to=effective_to, source_publication="test",
        verified_on=date(2026, 8, 20),
    )
    db.add(r)
    db.flush()
    return r


class TestATenantWipeCannotReachIt:
    """⚠️ THE STOP CONDITION, HELD AS A TEST. Not 'the wipe list happens not to
    mention it' — that would pass on a table with a `tenant_id` nobody had
    added to the list yet. The claim is stronger: there is no tenant-scoping
    column to filter on, so the wipe's whole mechanism cannot address a row
    here."""

    def test_the_table_has_no_tenant_scoping_column(self, db):
        cols = {
            r[0] for r in db.execute(text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'platform_tax_rates'"
            )).fetchall()
        }
        assert cols, "platform_tax_rates does not exist"
        offenders = sorted(c for c in cols if c in ("tenant_id", "company_id"))
        assert not offenders, (
            f"platform_tax_rates carries {offenders} — a tenant wipe filters on "
            "exactly these, so platform rates would be deletable by a routine "
            "teardown. This is the design the investigation rejected."
        )

    def test_the_wipe_script_does_not_list_it(self):
        """Belt to the braces above — and a live check on the file that would
        have to change for the risk to return."""
        from tests._source import code_only

        src = code_only((BACKEND / "scripts" / "wipe_tenant.py").read_text())
        assert "platform_tax_rates" not in src


class TestEffectiveDating:
    def test_a_superseded_row_is_not_in_force(self, db):
        r = _row(db, county="Testshire", rate="7.0000",
                 effective_from=date(2020, 1, 1), effective_to=date(2025, 3, 1))
        assert r.is_in_force_on(date(2024, 6, 1)) is True
        # ⚠️ THE BOUNDARY IS EXCLUSIVE AT THE CLOSE. A row ending 1 Mar and its
        # successor starting 1 Mar must not BOTH be in force on that day, or a
        # recompute of a 1 Mar invoice picks whichever the query returns first.
        assert r.is_in_force_on(date(2025, 3, 1)) is False
        assert r.is_in_force_on(date(2019, 12, 31)) is False

    def test_the_in_force_unique_index_permits_history(self, db):
        """A change is an insert that closes the prior row. Both rows coexist;
        only one has `effective_to IS NULL`."""
        _row(db, county="Histon", rate="7.0000", code="1111",
             effective_from=date(2020, 1, 1), effective_to=date(2025, 3, 1))
        _row(db, county="Histon", rate="8.0000", code="1111",
             effective_from=date(2025, 3, 1))
        db.flush()
        n = db.execute(text(
            "SELECT count(*) FROM platform_tax_rates WHERE county = 'Histon'"
        )).scalar()
        assert n == 2

    def test_two_in_force_rows_for_one_jurisdiction_are_rejected(self, db):
        """⚠️ THE CONSTRAINT THAT MAKES 'THE CURRENT RATE' A SINGLE ANSWER. Two
        open rows would make the in-force rate depend on row order."""
        from sqlalchemy.exc import IntegrityError

        _row(db, county="Dupe", rate="7.0000", code="2222")
        # `_row` flushes, so the violation surfaces on the second insert rather
        # than at a later explicit flush.
        with pytest.raises(IntegrityError):
            _row(db, county="Dupe", rate="8.0000", code="2222")

    def test_new_york_city_may_span_five_counties_on_one_code(self, db):
        """The reason the index is keyed on (state, code, county): NYC is one
        reporting code across five borough counties. A unique on (state, code)
        alone would reject four of them."""
        for b in ("BoroA", "BoroB", "BoroC"):
            _row(db, county=b, rate="8.8750", code="8081", name="New York City")
        db.flush()  # must not raise

    def test_a_backwards_date_range_is_rejected(self, db):
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            _row(db, county="Backwards", rate="8.0000",
                 effective_from=date(2025, 3, 1), effective_to=date(2024, 1, 1))


class TestTheSeedTranscription:
    """Pure — the seed's declared rows against the rate file. No database."""

    def test_the_seed_and_the_rate_file_agree_on_every_ny_county(self):
        """⚠️ TWO PLATFORM SOURCES, ONE FACT, AND THEY MUST NOT DRIFT. Until
        the file is retired both answer 'what is this county's rate', and the
        read path prefers the table — so a disagreement means a tenant onboarded
        before the table was loaded got a different number than one onboarded
        after.

        This comparison is also what caught the St Lawrence spelling: Pub 718
        prints "St. Lawrence" and both platform data files use "St Lawrence", so
        the seed's `county` carries the platform's spelling while
        `jurisdiction_name` quotes the publication.
        """
        from scripts.seed_platform_tax_rates import NY_JURISDICTIONS

        seeded = {
            county: float(rate)
            for _code, name, county, rate in NY_JURISDICTIONS
            if county and "(city)" not in name
        }
        file_rates = {
            r["county"]: r["combined_rate"]
            for r in json.loads(RATE_FILE.read_text())["rates"]
            if r["state"] == "NY" and r.get("county")
        }
        disagree = [
            f"{c}: seed={seeded.get(c)} file={file_rates[c]}"
            for c in sorted(file_rates)
            if seeded.get(c) != file_rates[c]
        ]
        assert not disagree, "the two platform rate sources disagree:\n  " + "\n  ".join(disagree)

    def test_every_new_york_county_is_seeded(self):
        from scripts.seed_platform_tax_rates import NY_JURISDICTIONS

        counties = {c for _code, _n, c, _r in NY_JURISDICTIONS if c}
        assert len(counties) == 62, f"expected 62 NY counties, seed declares {len(counties)}"

    def test_reporting_codes_are_present_and_four_digits(self):
        """The key an ST-100 is filed on, and the thing the platform has never
        stored. A blank code would make the table no better than the file."""
        from scripts.seed_platform_tax_rates import NY_JURISDICTIONS

        bad = [f"{n}: {code!r}" for code, n, _c, _r in NY_JURISDICTIONS
               if not (code and code.isdigit() and len(code) == 4)]
        assert not bad, f"bad reporting codes: {bad}"

    def test_yonkers_is_recorded_as_diverging_from_its_county(self):
        """⚠️ THE ONE PLACE A COUNTY-KEYED ANSWER IS PROVABLY WRONG FOR NY. The
        table can express it; the county-keyed resolver cannot use it. Held so
        that the limitation stays visible rather than becoming folklore."""
        from scripts.seed_platform_tax_rates import NY_JURISDICTIONS

        rates = {n: float(r) for _c, n, _co, r in NY_JURISDICTIONS}
        assert rates["Yonkers (city)"] == 8.875
        assert rates["Westchester – except"] == 8.375


class TestTheSeedWritesWhenTheDeployRunnerCallsIt:
    """⚠️ THE DEPLOY RUNNER PASSES NO ARGUMENTS, AND THIS SEED NEARLY DEFAULTED
    TO A DRY RUN. `run_canonical_seeds.sh` discovers every `seed_*.py` and
    invokes `python -m scripts.<name>` bare. Written the habitual way — apply
    behind `--apply` — it would have run on every deploy, logged
    "would apply", exited 0, and written nothing: a seed reporting success in
    the boot log while doing nothing. Same silent no-op as the unswept alarm and
    the swallowed health check.

    Pinned as a contract because the failure is invisible: the table stays
    empty, the read path falls back to the file, and everything looks fine."""

    @staticmethod
    def _capture(monkeypatch, argv: list[str]) -> dict:
        import scripts.seed_platform_tax_rates as seed_mod

        captured: dict = {}

        def fake_seed(apply):
            captured["apply"] = apply
            return {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0}

        monkeypatch.setattr(seed_mod, "seed", fake_seed)
        monkeypatch.setattr("sys.argv", argv)
        seed_mod.main()
        return captured

    def test_calling_main_with_no_arguments_applies(self, monkeypatch):
        captured = self._capture(monkeypatch, ["seed_platform_tax_rates"])
        assert captured["apply"] is True, (
            "the deploy runner calls this with no arguments — defaulting to a "
            "dry run means it never seeds and never says so"
        )

    def test_dry_run_is_the_opt_in(self, monkeypatch):
        captured = self._capture(monkeypatch, ["seed_platform_tax_rates", "--dry-run"])
        assert captured["apply"] is False

    def test_applying_twice_is_a_no_op(self):
        """⚠️ NOT COVERED BY THE SEED-IDEMPOTENCY CI GATE, WHICH HARDCODES TWO
        SEEDS. `.github/workflows/seed-idempotency.yml` triggers on any
        `backend/scripts/seed_*.py` change — so this file fires it — but
        `scripts/test_seed_idempotency.sh` only ever runs `seed_staging` and
        `seed_fh_demo`. A new seed therefore triggers a gate that does not test
        it, which reads as covered.

        Runs the real thing, twice, against the real session. That leaves the
        platform table populated, which is the correct end state everywhere —
        these rows are platform data with no tenant column, so they are not
        litter and the company tripwire cannot see them.
        """
        from scripts.seed_platform_tax_rates import NY_JURISDICTIONS, seed

        seed(apply=True)
        second = seed(apply=True)
        assert second["inserted"] == 0, "the second run inserted rows — not idempotent"
        assert second["updated"] == 0
        assert second["skipped"] == 0
        assert second["unchanged"] == len(NY_JURISDICTIONS)

    def test_a_locally_changed_rate_is_skipped_not_overwritten(self, db):
        """⚠️ OPTION A, AND THE REASON IT MATTERS MORE HERE THAN USUAL. If an
        in-force row's rate no longer matches the publication, the seed cannot
        tell whether an operator corrected it or the authority changed it.
        Overwriting would destroy the first and mis-date the second — a genuine
        change is a NEW row closing the old one, never an edit."""
        from app.models.tax import PlatformTaxRate
        from scripts.seed_platform_tax_rates import seed

        seed(apply=True)
        # Nudge one in-force row away from the publication, committed so the
        # seed's own session sees it.
        db.execute(text(
            "UPDATE platform_tax_rates SET rate_percentage = 1.0000"
            " WHERE state = 'NY' AND jurisdiction_code = '0511'"
            " AND effective_to IS NULL"
        ))
        db.commit()
        try:
            result = seed(apply=True)
            assert result["skipped"] >= 1, "a diverged rate was not skipped"
            still = db.execute(text(
                "SELECT rate_percentage FROM platform_tax_rates"
                " WHERE state = 'NY' AND jurisdiction_code = '0511'"
                " AND effective_to IS NULL"
            )).scalar()
            assert float(still) == 1.0, "the seed overwrote a diverged rate"
        finally:
            db.execute(text(
                "UPDATE platform_tax_rates SET rate_percentage = 8.0000"
                " WHERE state = 'NY' AND jurisdiction_code = '0511'"
                " AND effective_to IS NULL"
            ))
            db.commit()

    def test_the_runner_does_not_skip_it(self):
        """It must not land in SKIP_SEEDS — that list is for seeds invoked
        explicitly upstream, and this one has no explicit invocation."""
        from tests._source import code_only

        src = (BACKEND / "scripts" / "run_canonical_seeds.sh").read_text()
        skip_block = src.split("SKIP_SEEDS=(")[1].split(")")[0]
        assert "seed_platform_tax_rates" not in skip_block
        assert "seed_platform_tax_rates" not in code_only(
            (BACKEND / "railway-start.sh").read_text()
        ), "explicitly invoked AND auto-discovered would run it twice"


class TestTheReadPathPrefersTheTable:
    def test_a_loaded_state_reads_the_table_not_the_file(self, db):
        from app.services.county_geographic_service import get_tax_rate_for_county

        _row(db, county="Readshire", rate="9.1250", code="7777")
        db.flush()
        hit = get_tax_rate_for_county("NY", "Readshire", db=db)
        assert hit["combined_rate"] == 9.125
        assert hit["source"] == "platform_tax_rates"
        assert hit["jurisdiction_code"] == "7777"
        # ⚠️ THE PROVENANCE FIELDS ARE THE UPGRADE. The file could never say
        # which jurisdiction answered or when a human last checked it.
        assert hit["verified_on"] == "2026-08-20"

    def test_an_unloaded_state_falls_back_to_the_file(self, db):
        """Only New York has been verified against a primary source. Every other
        state must keep resolving exactly as before — the fallback is not a
        degraded path, it is the unchanged one."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        hit = get_tax_rate_for_county("PA", "Allegheny", db=db)
        assert hit is not None
        assert "source" not in hit

    def test_no_session_still_works(self):
        """`db` is optional so the function stays callable without a session."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        assert get_tax_rate_for_county("NY", "Cayuga")["combined_rate"] == 8.0

    def test_a_row_not_yet_in_force_is_not_used(self, db):
        """A rate announced for next quarter must not be charged today — the
        whole reason `effective_from` is stored rather than assumed."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        future = date.today() + timedelta(days=30)
        _row(db, county="Futureton", rate="9.9990", code="6666", effective_from=future)
        db.flush()
        assert get_tax_rate_for_county("NY", "Futureton", db=db) is None
        assert get_tax_rate_for_county("NY", "Futureton", db=db, on=future)["combined_rate"] == 9.999

    def test_a_city_row_does_not_answer_for_its_county(self, db):
        """Asked for a county, the county-wide row answers — not whichever
        jurisdiction the query happened to return first."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        _row(db, county="Splitshire", rate="8.0000", code="5551", name="Splitshire – except")
        _row(db, county="Splitshire", rate="8.8750", code="5552", name="Bigtown (city)")
        db.flush()
        assert get_tax_rate_for_county("NY", "Splitshire", db=db)["combined_rate"] == 8.0
