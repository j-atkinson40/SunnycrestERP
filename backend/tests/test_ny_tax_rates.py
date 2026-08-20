"""TAX-3 — New York's county rates, pinned to Publication 718.

⚠️ THIS FILE DETERMINES WHAT CUSTOMERS ARE CHARGED AND NOTHING TESTED IT.
`data/us-county-tax-rates.json` is the platform's rate source: onboarding reads
it (`county_geographic_service.get_tax_rate_for_county`), the suggestion
endpoint serves it (`tax.py::get_county_suggestions`), the operator ticks boxes,
and `POST /tax/jurisdictions/bulk-onboarding` copies the numbers into that
tenant's `tax_rates` rows. From then on the tenant's copy is frozen and the file
is never consulted again.

It had ONE commit ever, no updater, and no test. It was wrong for NINE of New
York's 57 counties when checked on 2026-08-20:

    Chautauqua 7.5→8 · Dutchess 7.75→8.125 · Erie 8→8.75 · Nassau 8.25→8.625
    Orange 7.75→8.125 · Putnam 8.125→8.375 · Suffolk 8.25→8.75
    Washington 8→7 · Westchester 7.375→8.375

Eight under-collected. Washington over-collected by a full point. And the five
NYC boroughs were absent entirely, so a Brooklyn customer resolved to no rate at
all.

⚠️ SUFFOLK IS THE FAILURE MODE IN ONE ROW. Publication 718-A records Suffolk
moving 4¼% → 4⅜%, ENACTED 17 Dec 2024, EFFECTIVE 1 March 2025. The file's
metadata read `last_updated: 2025-01-01` — compiled between those two dates,
carrying the old rate, and never touched again. The state changed a rate; the
file did not; nineteen months passed.

⚠️ THIS TEST IS DELIBERATELY A SECOND COPY OF THE SAME FACTS, and that is the
point rather than an oversight. The table below is a TRANSCRIPTION OF THE
AUTHORITY, dated and attributed; the JSON file is the IMPLEMENTATION. Two
producers of one fact are a defect when both are trying to be the source, and a
check when one is deliberately the record of what the source said and when. If
they disagree, someone changed the file without re-reading Pub 718 — which is
exactly the event nothing could previously detect.

⚠️ AND THE TEST STATES ITS OWN EXPIRY. `AUTHORITY_EFFECTIVE` is the edition this
was read from. When New York publishes a newer Pub 718, this table must be
re-transcribed and `VERIFIED_ON` updated — a passing test against a superseded
edition is the same silence in a new costume. See
`test_the_verification_date_is_recorded_in_the_file`.

Pure — reads the data file and compares to literals. No database, no fixture.
"""
from __future__ import annotations

import json
import pathlib

import pytest

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "us-county-tax-rates.json"

#: The edition transcribed below, and the day a human read it.
AUTHORITY = "NYS Publication 718 (2/25) — New York State Sales and Use Tax Rates by Jurisdiction"
AUTHORITY_URL = "https://www.tax.ny.gov/pdf/publications/sales/pub718.pdf"
AUTHORITY_EFFECTIVE = "2025-03-01"
VERIFIED_ON = "2026-08-20"

#: Every New York county, combined state+local rate, transcribed from the
#: publication named above. Counties marked (MCTD) include the 3/8% Metropolitan
#: Commuter Transportation District surcharge, per that document's footnote.
#: The five NYC boroughs each carry the single New York City rate.
PUB_718_NY: dict[str, float] = {
    "Albany": 8.0, "Allegany": 8.5, "Broome": 8.0, "Cattaraugus": 8.0,
    "Cayuga": 8.0, "Chautauqua": 8.0, "Chemung": 8.0, "Chenango": 8.0,
    "Clinton": 8.0, "Columbia": 8.0, "Cortland": 8.0, "Delaware": 8.0,
    "Dutchess": 8.125,  # MCTD
    "Erie": 8.75, "Essex": 8.0, "Franklin": 8.0, "Fulton": 8.0,
    "Genesee": 8.0, "Greene": 8.0, "Hamilton": 8.0, "Herkimer": 8.25,
    "Jefferson": 8.0, "Lewis": 8.0, "Livingston": 8.0, "Madison": 8.0,
    "Monroe": 8.0, "Montgomery": 8.0,
    "Nassau": 8.625,  # MCTD
    "Niagara": 8.0, "Oneida": 8.75, "Onondaga": 8.0, "Ontario": 7.5,
    "Orange": 8.125,  # MCTD
    "Orleans": 8.0, "Oswego": 8.0, "Otsego": 8.0,
    "Putnam": 8.375,  # MCTD
    "Rensselaer": 8.0,
    "Rockland": 8.375,  # MCTD
    # Pub 718 prints "St. Lawrence"; the rate file and the zip→county map both
    # use "St Lawrence". Left as-is deliberately — the two platform files agree
    # with each other, which is what `get_tax_rate_for_county` matches on, and
    # renaming one would break the join. Rate verified identical (8%, code 4091).
    "St Lawrence": 8.0,
    "Saratoga": 7.0, "Schenectady": 8.0,
    "Schoharie": 8.0, "Schuyler": 8.0, "Seneca": 8.0, "Steuben": 8.0,
    "Suffolk": 8.75,  # MCTD
    "Sullivan": 8.0, "Tioga": 8.0, "Tompkins": 8.0, "Ulster": 8.0,
    "Warren": 7.0, "Washington": 7.0, "Wayne": 8.0,
    "Westchester": 8.375,  # MCTD — see the Yonkers caveat below
    "Wyoming": 8.0, "Yates": 8.0,
    # New York City — one jurisdiction, five borough counties.
    "Bronx": 8.875, "Kings": 8.875, "New York": 8.875,
    "Queens": 8.875, "Richmond": 8.875,
}

#: Sunnycrest's configured counties. Called out separately because these are the
#: ones a wrong rate would bill TODAY, on the live tenant.
SUNNYCREST_COUNTIES = (
    "Cayuga", "Cortland", "Madison", "Monroe", "Oneida", "Onondaga",
    "Ontario", "Oswego", "Seneca", "Tompkins", "Wayne", "Yates",
)


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(DATA.read_text())


@pytest.fixture(scope="module")
def ny_rates(data) -> dict[str, float]:
    return {
        r["county"]: r["combined_rate"]
        for r in data["rates"]
        if r["state"] == "NY" and r.get("county")
    }


class TestEveryNewYorkRateMatchesPublication718:
    def test_no_rate_disagrees_with_the_authority(self, ny_rates):
        """⚠️ THE CHECK THAT WOULD HAVE CAUGHT ALL NINE. A wrong rate here is
        not a display bug: it is copied into a tenant's `tax_rates` at
        onboarding and then billed until someone audits it."""
        wrong = [
            f"{c}: file={ny_rates[c]} pub718={PUB_718_NY[c]}"
            for c in sorted(PUB_718_NY)
            if c in ny_rates and ny_rates[c] != PUB_718_NY[c]
        ]
        assert not wrong, (
            f"rates disagree with {AUTHORITY} (verified {VERIFIED_ON}):\n  "
            + "\n  ".join(wrong)
        )

    def test_every_new_york_county_is_present(self, ny_rates):
        """⚠️ A MISSING COUNTY IS NOT A SAFE FAILURE. `get_tax_rate_for_county`
        returns None, the suggestion arrives with `rate_found: False`, and the
        operator is asked to type a rate they have no source for. The five NYC
        boroughs were absent this way."""
        missing = sorted(set(PUB_718_NY) - set(ny_rates))
        assert not missing, f"New York counties with no rate row: {missing}"

    def test_no_unknown_new_york_county_has_crept_in(self, ny_rates):
        """The other direction — a row for something Pub 718 does not list is
        a rate with no authority behind it."""
        unknown = sorted(set(ny_rates) - set(PUB_718_NY))
        assert not unknown, f"rate rows not found in Pub 718: {unknown}"

    def test_new_york_has_all_sixty_two_counties(self, ny_rates):
        assert len(ny_rates) == 62, (
            f"New York has 62 counties; the file carries {len(ny_rates)}"
        )


class TestSunnycrestsOwnCounties:
    """These are the twelve configured on the live tenant. Held separately so a
    failure says immediately whether real billing is affected."""

    @pytest.mark.parametrize("county", SUNNYCREST_COUNTIES)
    def test_the_configured_county_matches_the_authority(self, county, ny_rates):
        assert ny_rates[county] == PUB_718_NY[county]


class TestTheFileRecordsWhatWasVerifiedAndWhen:
    """⚠️ THE OBLIGATION IS THE DELIVERABLE, NOT THE NUMBERS. Nine rates were
    wrong because nobody owned a quarterly diff — not because the compilation
    was careless. Rates change on announced dates (91% land on 1 Mar / 1 Jun /
    1 Sep / 1 Dec, median 81 days' notice), so a check is cheap and its ABSENCE
    is what decays. These assertions make the file state what was checked and
    when, so 'nobody has verified this since' is a readable fact rather than an
    archaeology exercise."""

    def test_the_ny_verification_block_names_its_authority_and_date(self, data):
        v = data["metadata"].get("verification", {}).get("NY")
        assert v, "no NY verification block — the file does not say what it was checked against"
        assert v["authority"] == AUTHORITY
        assert v["authority_effective"] == AUTHORITY_EFFECTIVE
        assert v["verified_on"] == VERIFIED_ON, (
            "the file's verification date and this test's have diverged — "
            "re-read Pub 718 and update BOTH, or the file is claiming a check "
            "that this table no longer backs"
        )
        assert v["url"] == AUTHORITY_URL

    def test_the_other_states_are_marked_unverified(self, data):
        """⚠️ ONLY NEW YORK WAS CHECKED. 51 states and 452 rows are in this
        file; one state has been read against a primary source. Saying so is the
        difference between a verified file and a file with a verified corner."""
        note = data["metadata"]["note"]
        assert "ONLY NEW YORK" in note.upper()
        assert set(data["metadata"]["verification"]) == {"NY"}, (
            "another state claims verification — it needs its own transcribed "
            "table and date, not an entry in this block"
        )

    def test_the_yonkers_divergence_is_recorded(self, data):
        """The one place the county-keyed model is provably wrong for NY today:
        Yonkers is 8.875% inside Westchester's 8.375%. Recorded rather than
        fixed, because fixing it means keying on jurisdiction, not county."""
        caveats = " ".join(data["metadata"]["verification"]["NY"]["caveats"])
        assert "Yonkers" in caveats
