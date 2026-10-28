"""James's rulings of 2026-10-28 — two production writes, with his explicit go.

    RULING 1  products.variant_template_id — link Sunnycrest's products to the
              platform catalogue. Unambiguous matches only; the rest stay NULL
              and are listed.
    RULING 2  customers.customer_type — funeral homes `funeral_home`,
              St. Mary's `cemetery`.

⚠️ DRY RUN BY DEFAULT. `--apply` writes. Nothing here is a migration: these are
data writes against one tenant, so they do not belong in the alembic chain, and
re-running is a no-op rather than a second effect.

⚠️ EVERY WRITE RECORDS ITS PRIOR VALUE AND EMITS THE ROLLBACK SQL, per the
ruling. All priors are NULL today, which is exactly why they must be recorded —
"it was NULL" is a measurement that stops being available the moment the write
lands, and a rollback written from memory afterwards is a guess.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal

TENANT_SLUG = "sunnycrest"

# ── RULING 1 ──────────────────────────────────────────────────────────────────────
#
# ⚠️ ONE ENTRY. Measured against production 2026-10-28: of Sunnycrest's 10 products,
# exactly ONE matches a platform variant template unambiguously. The mapping and the
# reason for every one of the other nine is in
# docs/investigations/2026-10-28-linking-sunnycrest-to-the-catalogue.md.
#
# ⚠️ THE KEY IS THE SKU, NOT THE NAME, because the name is what I am claiming to have
# matched and using it as the lookup key would make the write agree with itself. The
# sku is the tenant's own identifier and is independent of the match.
VARIANT_LINKS = {
    # tenant sku -> (variant_template_id, tenant product name as measured, why)
    "DEMO2-P001": (
        "8a3c6253-7de4-5dac-8d6b-7071f63d13ec",
        "Monticello Burial Vault",
        "exact match on BOTH product_templates.display_name and "
        "product_variant_templates.display_name ('Monticello Burial Vault'); the "
        "catalogue's own product_name_resolver returns exactly ONE candidate and "
        "agrees; form=burial_vault, family=monticello, variant sku BV-MON, "
        "outside 90.5x34.5",
    ),
}

# ── RULING 2 ──────────────────────────────────────────────────────────────────────
#
# ⚠️ KEYED ON account_number, for the same reason the links are keyed on sku: the
# name is the evidence for the classification, so it must not also be the lookup.
#
# ⚠️ FAIRVIEW IS DELIBERATELY ABSENT — see FAIRVIEW_NOTE. Omission here is an
# abstention, not an oversight, and the ruling's own discipline for Ruling 1
# ("leave the rest NULL and list them") is what it follows.
CUSTOMER_TYPES = {
    "DEMO2-C001": ("Hopkins Funeral Home", "funeral_home"),
    "DEMO2-C003": ("Riverside Memorial Chapel", "funeral_home"),
    "DEMO2-C005": ("Lakeside Funeral Directors", "funeral_home"),
    "DEMO2-C002": ("St. Mary's Cemetery", "cemetery"),
}

FAIRVIEW_NOTE = """\
DEMO2-C004 'Fairview Burial Services' is LEFT NULL, deliberately.

What it is: demo seed data. `scripts/seed_accounting_demo.py:_CUSTOMERS` creates all
five of Sunnycrest's customers in one transaction, and that literal carries only
`(name, account_number, receives_monthly_statement)` — it declares NO TYPE for any of
them. So there is no repo artifact saying what Fairview is, and its name is the only
signal. "Burial Services" is genuinely ambiguous in the trade between a funeral home
and an interment/grave-services vendor, which is a different side of the transaction.

Why it no longer shows in "Which funeral home?": two independent reasons now. It has
zero orders (the fix in 8eef3e71), and its customer_type is not 'funeral_home' (this
ruling). Either alone is sufficient.

⚠️ Typing it `funeral_home` on the strength of its name would be the unmeasured-value
defect CLAUDE.md names — a plausible business value written to a row nobody measured.
One word from James settles it and it is a one-line follow-up."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    args = ap.parse_args()
    mode = "APPLY" if args.apply else "DRY RUN"

    db = SessionLocal()
    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = :s"), {"s": TENANT_SLUG}
    ).scalar()
    if not tid:
        print(f"no tenant {TENANT_SLUG!r}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).isoformat()
    print(f"=== {mode} — tenant {TENANT_SLUG} ({tid}) at {stamp} ===\n")
    rollback: list[str] = []

    # ── RULING 1 ──────────────────────────────────────────────────────────────────
    print("--- RULING 1: products.variant_template_id ---")
    for sku, (vtid, expect_name, why) in VARIANT_LINKS.items():
        row = db.execute(text("""
            SELECT id, name, variant_template_id FROM products
            WHERE company_id = :t AND sku = :sku
        """), {"t": tid, "sku": sku}).mappings().one_or_none()
        if row is None:
            print(f"  SKIP {sku}: no such product for this tenant")
            continue
        # ⚠️ THE NAME IS VERIFIED, NOT TRUSTED. If the product behind this sku is not
        # the one the mapping was measured against, the match does not transfer and
        # the write must not happen.
        if row["name"] != expect_name:
            print(f"  REFUSE {sku}: name is {row['name']!r}, mapping measured "
                  f"{expect_name!r} — not the product this link was derived for")
            continue
        prior = row["variant_template_id"]
        if prior == vtid:
            print(f"  NO-OP {sku} {row['name']!r}: already linked to {vtid}")
            continue
        print(f"  {sku} {row['name']!r}")
        print(f"     prior variant_template_id = {prior!r}")
        print(f"     new   variant_template_id = {vtid!r}")
        print(f"     why: {why}")
        rollback.append(
            f"UPDATE products SET variant_template_id = "
            f"{'NULL' if prior is None else repr(prior)} "
            f"WHERE company_id = '{tid}' AND sku = '{sku}';"
        )
        if args.apply:
            db.execute(text("""
                UPDATE products SET variant_template_id = :v, updated_at = now()
                WHERE company_id = :t AND sku = :sku
            """), {"v": vtid, "t": tid, "sku": sku})

    # ── RULING 2 ──────────────────────────────────────────────────────────────────
    print("\n--- RULING 2: customers.customer_type ---")
    for acct, (expect_name, ctype) in CUSTOMER_TYPES.items():
        row = db.execute(text("""
            SELECT id, name, customer_type, classification_method FROM customers
            WHERE company_id = :t AND account_number = :a
        """), {"t": tid, "a": acct}).mappings().one_or_none()
        if row is None:
            print(f"  SKIP {acct}: no such customer for this tenant")
            continue
        if row["name"] != expect_name:
            print(f"  REFUSE {acct}: name is {row['name']!r}, ruling names "
                  f"{expect_name!r} — not the customer this type was ruled for")
            continue
        prior, prior_m = row["customer_type"], row["classification_method"]
        if prior == ctype:
            print(f"  NO-OP {acct} {row['name']!r}: already {ctype!r}")
            continue
        print(f"  {acct} {row['name']!r}")
        print(f"     prior customer_type = {prior!r} (method {prior_m!r})")
        print(f"     new   customer_type = {ctype!r} (method 'manual')")
        rollback.append(
            f"UPDATE customers SET customer_type = "
            f"{'NULL' if prior is None else repr(prior)}, classification_method = "
            f"{'NULL' if prior_m is None else repr(prior_m)} "
            f"WHERE company_id = '{tid}' AND account_number = '{acct}';"
        )
        if args.apply:
            # ⚠️ `classification_method='manual'` IS PART OF THE WRITE. The column
            # exists to say HOW a type was decided, and a type with no method is a
            # value whose provenance was discarded at the moment it was created.
            db.execute(text("""
                UPDATE customers
                SET customer_type = :c,
                    classification_method = 'manual',
                    classification_reasoning = :r,
                    updated_at = now()
                WHERE company_id = :t AND account_number = :a
            """), {"c": ctype, "t": tid, "a": acct,
                   "r": f"James's ruling 2026-10-28. {ctype} per that ruling."})

    print("\n--- Fairview ---")
    print(FAIRVIEW_NOTE)

    print("\n" + "=" * 72)
    print("ROLLBACK SQL (every write above, reversed):")
    print("=" * 72)
    for line in rollback or ["-- nothing to roll back"]:
        print(line)

    if args.apply:
        db.commit()
        print("\nCOMMITTED")
    else:
        db.rollback()
        print("\nDRY RUN — nothing written. Re-run with --apply.")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
