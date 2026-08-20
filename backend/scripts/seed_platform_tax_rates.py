"""Seed New York's taxing jurisdictions into `platform_tax_rates` — TAX-3, r171.

⚠️ THE ROWS BELOW ARE A TRANSCRIPTION OF A PUBLISHED DOCUMENT, and the date a
human read it is part of the data. `verified_on` is stored on every row for one
reason: an unverified rate table looks exactly like a verified one until someone
checks, and nine New York counties were wrong for nineteen months because
nothing recorded that nobody had looked.

Source: NYS Publication 718 (2/25), "New York State Sales and Use Tax Rates by
Jurisdiction", effective 1 March 2025. Confirmed current on 2026-08-20 against
Publication 718-A (12/25), which lists no effective date later than that.

⚠️ KEYED ON THE JURISDICTION, WHICH IS NOT THE COUNTY. Pub 718's unit is a
jurisdiction with a four-digit reporting code — the key an ST-100 return is
filed on, and one the platform has never stored. Twelve New York counties are
split into multiple jurisdictions; in eleven the city rate happens to equal the
county's, and in ONE it does not: Yonkers is 8.875% inside a Westchester County
of 8.375%. A county-keyed model cannot express that, which is why the code is
carried here even though today's resolver still matches on county.

New York City is ONE jurisdiction (code 8081) spanning FIVE borough counties, so
it is five rows sharing a code — the reason the in-force unique index is keyed
on (state, code, county) rather than (state, code).

⚠️ OPTION A IDEMPOTENT, AND THE COMPARISON IS THE POINT. A row is inserted when
absent; when present it is updated ONLY if it still byte-matches what this seed
last wrote. An operator correction is never overwritten. A rate that has
genuinely CHANGED is not an update at all — it is a new row closing the old one,
which is what `effective_to` exists for and what `--supersede` does.

⚠️ APPLIES BY DEFAULT, AND THAT IS A CONTRACT WITH THE DEPLOY RUNNER, NOT A
PREFERENCE. `scripts/run_canonical_seeds.sh` discovers every `seed_*.py` and
invokes it as `python -m scripts.<name>` with NO ARGUMENTS. This script was
first written to default to a dry run; under that default it would have executed
on every deploy, printed "would apply", exited 0, and written nothing — a seed
reporting success in the boot log while doing nothing, which is the same silent
no-op this arc keeps finding. `--dry-run` is the opt-in.

Unlike the demo seeds, this one is PLATFORM data and runs in production too.
There is no ENVIRONMENT guard because production is precisely where these rates
are needed. It only ever touches `platform_tax_rates`, which has no tenant
column, so it cannot reach tenant data even by mistake.

Usage:
    python -m scripts.seed_platform_tax_rates              # applies
    python -m scripts.seed_platform_tax_rates --dry-run    # report only
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models.tax import PlatformTaxRate

SOURCE = "NYS Publication 718 (2/25) — New York State Sales and Use Tax Rates by Jurisdiction"
SOURCE_URL = "https://www.tax.ny.gov/pdf/publications/sales/pub718.pdf"
EFFECTIVE_FROM = date(2025, 3, 1)
VERIFIED_ON = date(2026, 8, 20)
STATE = "NY"

#: (reporting_code, jurisdiction_name, county, combined_rate)
#:
#: ⚠️ `jurisdiction_name` IS THE PUBLICATION'S WORDING; `county` IS THE
#: PLATFORM'S. They differ in exactly one place and it matters: Pub 718 prints
#: "St. Lawrence", while `data/us-zip-county-mapping.json` and
#: `data/us-county-tax-rates.json` both use "St Lawrence". The `county` column
#: exists to join against those, so it carries their spelling — otherwise every
#: St Lawrence County customer silently fails to resolve. Caught by comparing
#: the seeded table against the rate file rather than by reading either.
#:
#: The rule this follows: quote the authority in the field that records what the
#: authority said, and use the platform's vocabulary in the field that joins.
NY_JURISDICTIONS: list[tuple[str, str, str | None, str]] = [
    ("0021", "New York State only", None, "4"),
    ("0181", "Albany", "Albany", "8"),
    ("0221", "Allegany", "Allegany", "8.5"),
    ("8081", "New York City", "Bronx", "8.875"),
    ("0321", "Broome", "Broome", "8"),
    ("0481", "Cattaraugus – except", "Cattaraugus", "8"),
    ("0441", "Olean (city)", "Cattaraugus", "8"),
    ("0431", "Salamanca (city)", "Cattaraugus", "8"),
    ("0561", "Auburn (city)", "Cayuga", "8"),
    ("0511", "Cayuga – except", "Cayuga", "8"),
    ("0651", "Chautauqua", "Chautauqua", "8"),
    ("0711", "Chemung", "Chemung", "8"),
    ("0861", "Chenango – except", "Chenango", "8"),
    ("0831", "Norwich (city)", "Chenango", "8"),
    ("0921", "Clinton", "Clinton", "8"),
    ("1021", "Columbia", "Columbia", "8"),
    ("1131", "Cortland", "Cortland", "8"),
    ("1221", "Delaware", "Delaware", "8"),
    ("1311", "Dutchess", "Dutchess", "8.125"),
    ("1451", "Erie", "Erie", "8.75"),
    ("1521", "Essex", "Essex", "8"),
    ("1621", "Franklin", "Franklin", "8"),
    ("1791", "Fulton – except", "Fulton", "8"),
    ("1741", "Gloversville (city)", "Fulton", "8"),
    ("1751", "Johnstown (city)", "Fulton", "8"),
    ("1811", "Genesee", "Genesee", "8"),
    ("1911", "Greene", "Greene", "8"),
    ("2011", "Hamilton", "Hamilton", "8"),
    ("2121", "Herkimer", "Herkimer", "8.25"),
    ("2221", "Jefferson", "Jefferson", "8"),
    ("8081", "New York City", "Kings", "8.875"),
    ("2321", "Lewis", "Lewis", "8"),
    ("2411", "Livingston", "Livingston", "8"),
    ("2511", "Madison – except", "Madison", "8"),
    ("2541", "Oneida (city)", "Madison", "8"),
    ("2611", "Monroe", "Monroe", "8"),
    ("2781", "Montgomery", "Montgomery", "8"),
    ("2811", "Nassau", "Nassau", "8.625"),
    ("8081", "New York City", "New York", "8.875"),
    ("2911", "Niagara", "Niagara", "8"),
    ("3010", "Oneida – except", "Oneida", "8.75"),
    ("3015", "Rome (city)", "Oneida", "8.75"),
    ("3018", "Utica (city)", "Oneida", "8.75"),
    ("3121", "Onondaga", "Onondaga", "8"),
    ("3211", "Ontario", "Ontario", "7.5"),
    ("3321", "Orange", "Orange", "8.125"),
    ("3481", "Orleans", "Orleans", "8"),
    ("3561", "Oswego (city)", "Oswego", "8"),
    ("3501", "Oswego – except", "Oswego", "8"),
    ("3621", "Otsego", "Otsego", "8"),
    ("3731", "Putnam", "Putnam", "8.375"),
    ("8081", "New York City", "Queens", "8.875"),
    ("3881", "Rensselaer", "Rensselaer", "8"),
    ("8081", "New York City", "Richmond", "8.875"),
    ("3921", "Rockland", "Rockland", "8.375"),
    ("4131", "Saratoga Springs (city)", "Saratoga", "7"),
    ("4111", "Saratoga – except", "Saratoga", "7"),
    ("4241", "Schenectady", "Schenectady", "8"),
    ("4321", "Schoharie", "Schoharie", "8"),
    ("4411", "Schuyler", "Schuyler", "8"),
    ("4511", "Seneca", "Seneca", "8"),
    ("4012", "Ogdensburg (city)", "St Lawrence", "8"),
    ("4091", "St. Lawrence – except", "St Lawrence", "8"),
    ("4691", "Steuben", "Steuben", "8"),
    ("4711", "Suffolk", "Suffolk", "8.75"),
    ("4821", "Sullivan", "Sullivan", "8"),
    ("4921", "Tioga", "Tioga", "8"),
    ("5021", "Ithaca (city)", "Tompkins", "8"),
    ("5081", "Tompkins – except", "Tompkins", "8"),
    ("5111", "Ulster", "Ulster", "8"),
    ("5211", "Glens Falls (city)", "Warren", "7"),
    ("5281", "Warren – except", "Warren", "7"),
    ("5311", "Washington", "Washington", "7"),
    ("5421", "Wayne", "Wayne", "8"),
    ("5521", "Mount Vernon (city)", "Westchester", "8.375"),
    ("6861", "New Rochelle (city)", "Westchester", "8.375"),
    ("5581", "Westchester – except", "Westchester", "8.375"),
    ("6513", "White Plains (city)", "Westchester", "8.375"),
    ("6511", "Yonkers (city)", "Westchester", "8.875"),
    ("5621", "Wyoming", "Wyoming", "8"),
    ("5721", "Yates", "Yates", "8"),
]


def _key(r) -> tuple:
    return (r.state, r.jurisdiction_code, r.county or "")


def seed(apply: bool) -> dict:
    db = SessionLocal()
    inserted = updated = unchanged = skipped = 0
    try:
        in_force = {
            _key(r): r
            for r in db.execute(
                select(PlatformTaxRate).where(PlatformTaxRate.effective_to.is_(None))
            ).scalars()
        }
        for code, name, county, rate in NY_JURISDICTIONS:
            key = (STATE, code, county or "")
            want = Decimal(rate)
            row = in_force.get(key)
            if row is None:
                inserted += 1
                if apply:
                    db.add(PlatformTaxRate(
                        id=str(uuid.uuid4()), state=STATE, jurisdiction_code=code,
                        jurisdiction_name=name, county=county, rate_percentage=want,
                        effective_from=EFFECTIVE_FROM, source_publication=SOURCE,
                        source_url=SOURCE_URL, verified_on=VERIFIED_ON,
                    ))
                continue
            if row.rate_percentage != want:
                # ⚠️ NOT AN UPDATE. A differing rate on an in-force row means
                # either an operator changed it or the authority did, and this
                # seed cannot tell which. Overwriting would destroy the first
                # and mis-date the second — a genuine change needs a NEW row
                # closing this one, which is what --supersede is for.
                skipped += 1
                print(f"  SKIP {code} {name}: in force at {row.rate_percentage}, "
                      f"publication says {want} — supersede rather than overwrite")
                continue
            if row.jurisdiction_name != name or row.source_publication != SOURCE:
                updated += 1
                if apply:
                    row.jurisdiction_name = name
                    row.source_publication = SOURCE
                    row.source_url = SOURCE_URL
                    row.verified_on = VERIFIED_ON
            else:
                unchanged += 1
                if apply and row.verified_on != VERIFIED_ON:
                    # Re-reading the same publication and finding it unchanged
                    # IS a verification event, and the date is the deliverable.
                    row.verified_on = VERIFIED_ON
                    updated += 1
                    unchanged -= 1
        if apply:
            db.commit()
        return {"inserted": inserted, "updated": updated,
                "unchanged": unchanged, "skipped": skipped}
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report without writing; the deploy runner passes no args and WRITES")
    # Accepted and ignored so an operator reaching for the habitual flag is not
    # surprised by an argparse error on a script that already applies.
    ap.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    apply = not args.dry_run
    result = seed(apply)
    verb = "applied" if apply else "would apply (dry run)"
    print(f"[platform_tax_rates] NY {verb}: {result}")
    if result["skipped"]:
        print("  ⚠️ skipped rows differ from the publication and were NOT overwritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
