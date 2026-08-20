"""TAX-5 A-3 (cheap half) — a date the rate table cannot answer is refused.

⚠️ ASKING ABOUT 2019 RETURNED TODAY'S RATE. `get_tax_rate_for_county` takes an
`on` date. The platform lookup found no row in force for a pre-2025 date, fell
through to `us-county-tax-rates.json` — which has no date concept at all — and
handed back the CURRENT figure as though it were the historical one. The caller
supplied a date, got an answer, and the answer silently ignored it.

That is worse than not asking, and it is the condition the TAX-5 dispatch named:
"if every row's `effective_from` is the seed date, then the resolver can ask
about 2024 and get 2026's answer, which is worse than not asking."

⚠️ THE DECIDING QUESTION IS NOT "DID WE FIND A RATE" BUT "DOES THIS STATE HAVE
DATED COVERAGE." Two absences that look identical and mean opposite things:

  - state absent from `platform_tax_rates` (Ohio) → fall back to the file. We
    have no dated data and never claimed to; the file is undated for every date
    equally, so using it for a past date is no worse than for today.
  - state present, date outside its range (New York before 2025-03-01) →
    REFUSE. Dated coverage exists and this date is outside it; falling back
    would answer a historical question with a present number.

⚠️ LATENT, AND SAID SO. No caller passes a historical date — `build_suggestions`
omits `on` and always asks about now. This is the trap waiting for whoever
builds historical recompute, not a defect anyone is hitting. `platform_tax_rates`
holds ONE edition, so every pre-epoch question lands in the refusal.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent

#: The seeded epoch — every `platform_tax_rates` row carries this
#: `effective_from`, which is why any earlier date is unanswerable.
EPOCH = date(2025, 3, 1)


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(autouse=True)
def ny_dated_coverage(db):
    """New York has dated coverage. Created only when absent.

    ⚠️ THESE TESTS FIRST DEPENDED ON AMBIENT SEED STATE AND FAILED ON A BARE
    DATABASE. `platform_tax_rates` is empty until `seed_platform_tax_rates`
    runs, and that seed runs on DEPLOY — `run_canonical_seeds.sh` — not during a
    test run. Five of these tests passed on a seeded dev machine and failed on a
    fresh Postgres, which is the seeded-vs-bare axis that has turned main red
    twice in this codebase.

    Caught by running the file against a deliberately unseeded database rather
    than by noticing. The rule it re-earns: a test that reads platform data must
    put that data there itself, because "it was already on my machine" is not a
    property CI shares.

    Create-scoped: on a seeded machine this finds the real row and adds nothing;
    on a bare one it inserts a single Cayuga row inside the test transaction,
    which the rollback removes.
    """
    from app.models.tax import PlatformTaxRate

    present = (
        db.query(PlatformTaxRate)
        .filter(
            PlatformTaxRate.state == "NY",
            PlatformTaxRate.county.ilike("Cayuga"),
            PlatformTaxRate.effective_to.is_(None),
        )
        .first()
    )
    if present is not None:
        return
    db.add(PlatformTaxRate(
        id=str(uuid.uuid4()), state="NY", jurisdiction_code="0511",
        jurisdiction_name="Cayuga – except", county="Cayuga",
        rate_percentage=Decimal("8"), effective_from=EPOCH,
        source_publication="NYS Publication 718 (2/25)",
        verified_on=date(2026, 8, 20),
    ))
    db.flush()


class TestADateOutsideTheKnownRangeIsRefused:
    @pytest.mark.parametrize("asked", [
        EPOCH - timedelta(days=1),
        date(2024, 1, 1),
        date(2019, 6, 1),
    ])
    def test_a_pre_epoch_date_does_not_return_todays_rate(self, db, asked):
        from app.services.county_geographic_service import get_tax_rate_for_county

        got = get_tax_rate_for_county("NY", "Cayuga", db=db, on=asked)
        assert got is not None, "refusal should carry a reason, not vanish"
        assert got["combined_rate"] is None, (
            f"asking about {asked} returned a rate — the undated file answered a "
            "dated question"
        )
        assert asked.isoformat() in got["unknown_because"]

    def test_the_epoch_itself_resolves(self, db):
        """The boundary is inclusive at the open end — a row effective on the
        1st is in force on the 1st. Held so the refusal cannot creep forward."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        got = get_tax_rate_for_county("NY", "Cayuga", db=db, on=EPOCH)
        assert got["combined_rate"] == 8.0
        assert got["source"] == "platform_tax_rates"

    def test_today_still_resolves_from_the_platform_table(self, db):
        """The other arm — without it, the refusal tests would be satisfied by a
        lookup that returns nothing for every date."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        got = get_tax_rate_for_county("NY", "Cayuga", db=db, on=date.today())
        assert got["combined_rate"] == 8.0
        assert got["verified_on"] == "2026-08-20"


class TestAnUnloadedStateStillFallsBack:
    """⚠️ THE ABSENCE THAT MEANS SOMETHING DIFFERENT. Refusing here would break
    every non-New-York tenant to fix a New York problem — Ohio has no dated
    coverage, so its file rate is exactly as good (and as unverified) for 2019
    as for today."""

    @pytest.mark.parametrize("asked", [date.today(), date(2019, 6, 1)])
    def test_ohio_answers_from_the_file_whatever_the_date(self, db, asked):
        from app.services.county_geographic_service import get_tax_rate_for_county

        got = get_tax_rate_for_county("OH", "Cuyahoga", db=db, on=asked)
        assert got is not None and got["combined_rate"] is not None
        # And it does NOT claim verification it does not have.
        assert got.get("verified_on") is None
        assert got.get("source") is None

    def test_the_two_absences_are_distinguishable(self, db):
        """A caller must be able to tell "we have no dated data for this state"
        from "this date is outside our range" — different problems, and only one
        is fixed by seeding history."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        ny = get_tax_rate_for_county("NY", "Cayuga", db=db, on=date(2019, 6, 1))
        oh = get_tax_rate_for_county("OH", "Cuyahoga", db=db, on=date(2019, 6, 1))
        assert ny["combined_rate"] is None and "unknown_because" in ny
        assert oh["combined_rate"] is not None and "unknown_because" not in oh


class TestACountyTheTableNeverLoadedStillFallsBack:
    """⚠️ THE THIRD ABSENCE, AND THE ONE THE FIRST VERSION GOT WRONG. The guard
    originally asked whether the STATE had dated coverage, so a New York county
    absent from `platform_tax_rates` was refused rather than answered from the
    file — the file carries all 62 NY counties and could have answered.

    Caught by `test_platform_tax_rates.py` failing in the gate, not by noticing,
    which is the second time this arc that the deciding question was scoped one
    level too wide.
    """

    def test_a_ny_county_absent_from_the_table_reads_from_the_file(self, db):
        from app.models.tax import PlatformTaxRate
        from app.services.county_geographic_service import get_tax_rate_for_county

        # Precondition: NY has dated coverage, so a state-scoped guard WOULD
        # refuse here. Without this the test could pass for the wrong reason.
        assert db.query(PlatformTaxRate.id).filter(
            PlatformTaxRate.state == "NY").first() is not None

        assert db.query(PlatformTaxRate.id).filter(
            PlatformTaxRate.state == "NY",
            PlatformTaxRate.county.ilike("Nowhere"),
        ).first() is None

        got = get_tax_rate_for_county("NY", "Nowhere", db=db, on=date.today())
        # No file row either, so the honest answer is nothing — but it must
        # arrive by FALLING THROUGH, not by refusing.
        assert got is None or "unknown_because" not in got

    def test_a_loaded_ny_county_still_refuses_a_pre_epoch_date(self, db):
        """The other arm. Without it the fix above could be "never refuse"."""
        from app.services.county_geographic_service import get_tax_rate_for_county

        got = get_tax_rate_for_county("NY", "Cayuga", db=db, on=date(2019, 6, 1))
        assert got["combined_rate"] is None
        assert "Cayuga" in got["unknown_because"]


class TestTheSuggestionPayloadDoesNotClaimAFoundRate:
    def test_rate_found_keys_on_a_rate_not_on_a_dict(self, db):
        """⚠️ THE REFUSAL RETURNS A DICT WITHOUT A RATE, so the old
        `rate_info is not None` would have reported `rate_found: True` beside
        `combined_rate: None` — a found rate that is not a rate."""
        import inspect

        from app.services import county_geographic_service as svc

        src = inspect.getsource(svc.build_suggestions)
        assert '"rate_found": rate_info is not None' not in src
        assert 'combined_rate") is not None' in src

    def test_todays_suggestions_are_unaffected(self, db):
        """`build_suggestions` omits `on`, so it always asks about now — the
        refusal must not touch the live path."""
        from app.services.county_geographic_service import build_suggestions

        rows = build_suggestions(tenant_zip="13021", tenant_state="NY",
                                 radius_miles=30, db=db)
        cayuga = next(r for r in rows if r["county"] == "Cayuga")
        assert cayuga["rate_found"] is True
        assert cayuga["combined_rate"] == 8.0
        assert cayuga["rate_unknown_because"] is None


class TestTheEpochIsWhatMakesThisNecessary:
    def test_the_rate_table_still_holds_one_edition(self, db):
        """⚠️ WHEN THIS FAILS, THE REFUSAL STOPS BEING THE WHOLE FEATURE. One
        edition is why every pre-2025 question is unanswerable. Seed real
        history and most of them become answerable — at which point this test
        failing is the signal to revisit, not to relax."""
        from sqlalchemy import text

        editions = db.execute(text(
            "SELECT count(DISTINCT effective_from) FROM platform_tax_rates"
        )).scalar()
        assert editions <= 1, (
            "platform_tax_rates now carries more than one edition — historical "
            "questions have become answerable and the refusal's range should be "
            "re-derived rather than left pinned to a single epoch"
        )

    def test_the_seed_declares_that_epoch(self):
        from scripts.seed_platform_tax_rates import EFFECTIVE_FROM

        assert EFFECTIVE_FROM == EPOCH, (
            "the seed's epoch moved; this suite's EPOCH constant must follow it"
        )

    def test_the_static_file_has_no_date_concept(self):
        """The reason falling back to it is wrong for a dated question: it
        carries a `verified_on` for New York, but no per-rate effective date
        for anything."""
        doc = json.loads(
            (BACKEND / "data" / "us-county-tax-rates.json").read_text()
        )
        assert not any(
            "effective" in k for r in doc["rates"] for k in r
        ), "the static file gained effective dates — the fallback may now be datable"
