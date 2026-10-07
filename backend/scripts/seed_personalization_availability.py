"""Write per-vault personalization availability into a licensee's enrollment.

⚠️ DEV ONLY IN THIS REVISION, BY RULING (2026-10-07). `--apply` refuses unless the
database host is local AND `ENVIRONMENT` is not `production`. Running this against
production is a separate decision that has not been taken.

WHAT IT WRITES, AND WHERE

One key inside the existing `wilbert_program_enrollments.personalization_config`
JSONB, keyed by **`product_variant_templates.id`**:

    personalization_config = {
      "options":      { ... untouched ... },
      "availability": { "<variant_template_id>": { "personalization": [answers] } }
    }

⚠️ THE KEY IS THE PLATFORM VARIANT ID, NOT A TENANT PRODUCT ID, AND THE 0-OF-27
PRODUCT LINK DOES NOT BLOCK THIS. `products.variant_template_id` is populated for
0 of 27 tenant products, which is why the catalog pane cannot show a price. Capture
never goes through `products`: `product_name_resolver.build_index` reads
`product_variant_templates` directly, and `Resolution.variant_template_id` is a
`product_variant_templates.id`, which is what `resolve_and_evaluate` hands to
`read_availability`. So availability is reachable today and price is not.

⚠️ IDEMPOTENT AND REVERSIBLE, BOTH NEEDED FOR DIFFERENT REASONS. Idempotent because
a seed that is not can only be run once safely, and this one will be re-run as the
catalog grows. Reversible (`--revert`) because the mapping is James's reading of a
portal that disagrees with Sunnycrest's own spec sheet in at least one place, so
backing it out must not require hand-editing JSONB.

⚠️ IT TOUCHES ONLY THE `availability` KEY. `options` — the pre-r185 shape — is read
back and written through unchanged. A whole-column replace would silently drop it.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.personalization.questions import (  # noqa: E402
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
    ANSWER_NAMEPLATE_ONLY,
    PERSONALIZATION_QUESTION,
    QUESTION_PERSONALIZATION,
)

#: ⚠️ DERIVED FROM THE QUESTION, NOT TYPED OUT. `.answers` excludes `none`, which
#: must never appear in a stored permitted set — `Availability.permits` grants it
#: wherever the question is asked at all.
ALL_ANSWERS: list[str] = list(PERSONALIZATION_QUESTION.answers)

#: Nameplate and/or emblem — Salute, both forms. No print, no vinyl, so no mix.
NAMEPLATE_OR_EMBLEM: list[str] = [
    ANSWER_NAMEPLATE_ONLY,
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
]

#: Nameplate only — Continental. ⚠️ R2's ONE EXCLUSION: `cover_emblem_only` is
#: permitted on every vault that offers cover emblems, and Continental offers a
#: nameplate and no emblem, as in the ordering portal (`lib/products.ts:145-161`).
NAMEPLATE_ONLY: list[str] = [ANSWER_NAMEPLATE_ONLY]

#: ⚠️ EMPTY IS A DELIBERATE REFUSAL, NOT AN ABSENCE. `read_availability` reads `[]`
#: as NOT_OFFERED and an ABSENT key as NOT_CONFIGURED. Writing `[]` is the licensee
#: saying "none on this vault"; omitting the key is the licensee saying nothing.
NOT_OFFERED: list[str] = []

#: SKU -> permitted answers. ⚠️ BY SKU, NOT BY NAME. Names are what the portal and
#: the spec sheet disagree about; SKUs are the catalog's own identifiers and every
#: one here is asserted to exist before anything is written.
#:
#: ⚠️ EVERY ENTRY IS JAMES'S RULING OF 2026-10-07, not derived from the portal by
#: this script. The portal's own vault list is ambiguous between burial and urn forms
#: for twelve names; James ruled that a plain portal name means the BURIAL vault and
#: the urn forms take theirs from the portal's separate "... Urn Vault" rows.
AVAILABILITY_BY_SKU: dict[str, list[str]] = {
    # ── burial, all types (the portal's `wilbertPersonalizationFields`) ──
    "BV-WBR": ALL_ANSWERS,      # Wilbert Bronze
    "BV-BTRI": ALL_ANSWERS,     # Bronze Triune
    "BV-CTRI": ALL_ANSWERS,     # Copper Triune
    "BV-SSTRI": ALL_ANSWERS,    # Stainless Steel Triune
    "BV-CRTRI": ALL_ANSWERS,    # Cameo Rose Triune
    "BV-VTRI": ALL_ANSWERS,     # Veteran Triune
    "BV-WTRIB": ALL_ANSWERS,    # White Tribute
    "BV-GTRIB": ALL_ANSWERS,    # Gray Tribute
    # Venetian and White Venetian -> BOTH colour variants, by ruling.
    "BV-GVEN": ALL_ANSWERS,
    "BV-WVEN": ALL_ANSWERS,
    # ── burial, narrower ──
    "BV-CON": NAMEPLATE_ONLY,
    "BV-CON34": NAMEPLATE_ONLY,   # both sizes, by ruling
    "BV-SAL": NAMEPLATE_OR_EMBLEM,
    # ── burial, none ──
    "BV-MON": NOT_OFFERED,
    "BV-MRC": NOT_OFFERED,
    # ── urn vaults, all types ──
    "UV-BTRI": ALL_ANSWERS,
    "UV-CTRI": ALL_ANSWERS,
    "UV-SSTRI": ALL_ANSWERS,
    "UV-CRTRI": ALL_ANSWERS,
    "UV-VET": ALL_ANSWERS,
    "UV-GVEN": ALL_ANSWERS,
    "UV-WVEN": ALL_ANSWERS,
    # ── urn vaults, narrower ──
    "UV-SAL": NAMEPLATE_OR_EMBLEM,
    # ── urn vaults, none ──
    "UV-MON": NOT_OFFERED,
    "UV-UCG": NOT_OFFERED,
    "UV-UWS": NOT_OFFERED,
    "UV-GL": NOT_OFFERED,
    # ── graveliners, none ──
    "GL-STD": NOT_OFFERED,
    "GL-34": NOT_OFFERED,
    "GL-38": NOT_OFFERED,
    "GL-SS": NOT_OFFERED,
    # ── cemetery equipment, none ──
    "CE-LD": NOT_OFFERED,
    "CE-TS": NOT_OFFERED,
    "CE-TD": NOT_OFFERED,
    "CE-GM": NOT_OFFERED,
    "CE-CH": NOT_OFFERED,
    "CE-CT": NOT_OFFERED,
}

#: ⚠️ DELIBERATELY ABSENT FROM THE MAP ABOVE, SO THEY STAY NOT_CONFIGURED. By
#: ruling: urns (P-series, 12) and infant vaults (LC-, 3) are pending James.
#:
#: ⚠️ AND THE SPEC SHEET DOES HAVE A READING FOR THE INFANT ONES, WHICH IS WHY
#: LEAVING THEM ABSENT IS A CHOICE RATHER THAN AN OVERSIGHT.
#: `docs/catalog/2026-10-02-sunnycrest-product-specs.csv` leaves the Personalization
#: column EMPTY for all three Loved & Cherished rows — the same marker it uses for
#: Monticello, Monarch and the graveliners, which everyone agrees offer none. r193
#: already translated that to `[]` on `product_templates.personalization_capability`.
#: Writing `[]` here would merely agree with the sheet; the ruling says wait.
PENDING_JAMES: tuple[str, ...] = (
    "P300", "P300P", "P300WS", "P310", "P310P", "P310WS",
    "P363", "P440", "P440A", "P440B", "P445", "P600",
    "LC-19", "LC-24", "LC-31",
)


def _refuse_non_dev() -> None:
    url = os.environ.get("DATABASE_URL", "")
    host = (urlparse(url).hostname or "").lower()
    env = os.environ.get("ENVIRONMENT", "dev").lower()
    if env == "production":
        sys.exit("REFUSED: ENVIRONMENT=production. This revision is dev-only.")
    if host not in ("localhost", "127.0.0.1", "::1", ""):
        sys.exit(f"REFUSED: database host {host!r} is not local. This revision is dev-only.")


def _resolve_skus(db) -> dict[str, str]:
    """SKU -> variant_template_id, asserting every mapped SKU exists.

    ⚠️ ASSERTS RATHER THAN SKIPS. A SKU that silently does not resolve means a vault
    gets no availability and therefore reads NOT_CONFIGURED — indistinguishable from
    a licensee who has said nothing, which is the one state this whole mechanism
    exists to keep separate.
    """
    rows = db.execute(text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    )).all()
    by_sku = {sku: vid for sku, vid in rows}
    assert len(by_sku) > 40, f"only {len(by_sku)} active variants — catalog unseeded?"
    missing = sorted(set(AVAILABILITY_BY_SKU) - set(by_sku))
    assert not missing, f"mapped SKUs not in the catalog: {missing}"
    pending_missing = sorted(set(PENDING_JAMES) - set(by_sku))
    assert not pending_missing, f"pending SKUs not in the catalog: {pending_missing}"
    return by_sku


def build_availability(db) -> dict[str, dict[str, list[str]]]:
    by_sku = _resolve_skus(db)
    return {
        by_sku[sku]: {QUESTION_PERSONALIZATION: list(answers)}
        for sku, answers in AVAILABILITY_BY_SKU.items()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default is dry run)")
    ap.add_argument("--revert", action="store_true", help="remove the availability key")
    ap.add_argument("--company-id", help="limit to one company")
    args = ap.parse_args()

    if args.apply:
        _refuse_non_dev()

    db = SessionLocal()
    try:
        desired = build_availability(db)
        print(f"mapped {len(desired)} variants; {len(PENDING_JAMES)} left NOT_CONFIGURED")

        q = ("SELECT id, company_id, personalization_config "
             "FROM wilbert_program_enrollments WHERE personalization_config IS NOT NULL")
        params: dict = {}
        if args.company_id:
            q += " AND company_id = :c"
            params["c"] = args.company_id
        rows = db.execute(text(q + " ORDER BY is_active DESC, id"), params).all()
        print(f"enrollments with a config: {len(rows)}")

        changed = 0
        for eid, company_id, config in rows:
            config = config if isinstance(config, dict) else {}
            new = copy.deepcopy(config)
            if args.revert:
                if "availability" not in new:
                    print(f"  {eid}  no availability key — nothing to revert")
                    continue
                new.pop("availability")
            else:
                if new.get("availability") == desired:
                    print(f"  {eid}  already current — no write")
                    continue
                new["availability"] = desired
            changed += 1
            verb = "REVERT" if args.revert else "WRITE"
            print(f"  {eid}  {verb}  (company {company_id})")
            if args.apply:
                db.execute(text(
                    "UPDATE wilbert_program_enrollments "
                    "SET personalization_config = CAST(:p AS jsonb) WHERE id = :i"
                ), {"p": json.dumps(new), "i": eid})

        if args.apply:
            db.commit()
            print(f"committed: {changed} enrollment(s) changed")
        else:
            print(f"DRY RUN: {changed} enrollment(s) would change (pass --apply)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
