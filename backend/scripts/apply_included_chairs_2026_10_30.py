"""Set `products.included_chairs` for Sunnycrest's five equipment bundles.

Ruling B' (James, 2026-10-30), with the final value ruled separately the same day:

    Full Equipment            8
    Tent Only                 8
    Lowering Device & Grass   8     <- ruled explicitly: "a family comes"
    Lowering Device Only      0
    Vault Placer              0

Rule behind the numbers: *"a bundle includes chairs when a family is coming; no-family
bundles include none."* Billable extras = max(0, chairs - included_chairs), billed on
`Extra Chairs (Over 8)` at its price ($5.00 each).

    # dry run (default) — prints what it WOULD do and changes nothing
    cd backend
    PYTHONPATH=$PWD railway run --project <id> --environment production \
      --service SunnycrestERP -- .venv/bin/python scripts/apply_included_chairs_2026_10_30.py

    # the write
    ... -- .venv/bin/python scripts/apply_included_chairs_2026_10_30.py --apply

⚠️ KEYED ON SKU, NOT NAME. The product NAME is the evidence that a row is the bundle the
ruling names, so matching on it would make the match its own justification. The skus were
measured on production 2026-10-30 and are listed with their names below so a reader can
check the pairing rather than trust it.

⚠️ EXACTLY FIVE ROWS, OR IT REFUSES. A sku that matches nothing, or matches more than one
row, means the catalog is not what this script was written against — and a partial write
would leave some bundles deriving extras and others unable to. It is all five or none.

⚠️ IT PRINTS THE PRIOR VALUE OF EVERY ROW AND THE SQL TO RESTORE IT. The prior values
are expected to be NULL (r218 writes no data), but "expected" is not "verified" and the
rollback is only trustworthy if it is built from what was actually there.

⚠️ AND IT REFUSES IF THE COLUMN IS ABSENT rather than failing partway. `r218_included_chairs`
must have deployed first; this is checked against information_schema, not assumed from the
model.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

#: (sku, name as measured on production, included chairs per ruling B')
#:
#: ⚠️ THE NAME IS DOCUMENTATION HERE AND IS ALSO CHECKED. It is not the key, but a sku
#: whose row carries a different name than recorded means the catalog moved under the
#: ruling, and that is a stop rather than a surprise.
BUNDLES: tuple[tuple[str, str, int], ...] = (
    ("CE-PKG-FULL", "Full Equipment", 8),
    ("CE-PKG-TENT", "Tent Only", 8),
    ("CE-PKG-LDG", "Lowering Device & Grass", 8),
    ("CE-PKG-LD", "Lowering Device Only", 0),
    ("CE-PKG-VP", "Vault Placer", 0),
)

TENANT_SLUG = "sunnycrest"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    p = urlparse(url)
    print(f"host={p.hostname} port={p.port} db={(p.path or '').lstrip('/')}")
    print(f"mode={'APPLY' if args.apply else 'DRY RUN'}\n")

    # ⚠️ READ-ONLY UNTIL --apply. The dry run cannot write even by mistake.
    connect_args = {} if args.apply else {"options": "-c default_transaction_read_only=on"}
    eng = create_engine(url, connect_args=connect_args)

    with eng.connect() as c:
        have = c.execute(text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='products' AND column_name='included_chairs'"
        )).scalar()
        if not have:
            print("REFUSING: products.included_chairs does not exist. "
                  "r218_included_chairs has not deployed yet.", file=sys.stderr)
            return 3

        tid = c.execute(text("SELECT id FROM companies WHERE slug=:s"),
                        {"s": TENANT_SLUG}).scalar()
        if not tid:
            print(f"REFUSING: no tenant with slug {TENANT_SLUG!r}.", file=sys.stderr)
            return 3

        rows = []
        for sku, name, want in BUNDLES:
            got = c.execute(text(
                "SELECT id, name, sku, included_chairs FROM products "
                "WHERE company_id=:t AND sku=:k"), {"t": tid, "k": sku}).mappings().all()
            if len(got) != 1:
                print(f"REFUSING: sku {sku!r} matched {len(got)} rows, expected exactly 1.",
                      file=sys.stderr)
                return 3
            r = got[0]
            if r["name"] != name:
                print(f"REFUSING: sku {sku!r} is named {r['name']!r}, "
                      f"but the ruling names {name!r}.", file=sys.stderr)
                return 3
            rows.append((r["id"], sku, name, r["included_chairs"], want))

        print("ROWS AND THEIR PRIOR VALUES")
        for _id, sku, name, prior, want in rows:
            change = "no change" if prior == want else f"{prior!r} -> {want}"
            print(f"  {sku:14} {name!r:28} {change}")

        print("\nROLLBACK SQL (restores exactly what was there)")
        for _id, sku, _name, prior, _want in rows:
            val = "NULL" if prior is None else str(prior)
            print(f"  UPDATE products SET included_chairs = {val} WHERE id = '{_id}';")

        if not args.apply:
            print("\nDRY RUN — nothing written. Re-run with --apply.")
            return 0

    with eng.begin() as c:
        for _id, _sku, _name, _prior, want in rows:
            c.execute(text("UPDATE products SET included_chairs=:v WHERE id=:i"),
                      {"v": want, "i": _id})

    # ⚠️ READ BACK FROM A FRESH CONNECTION. Reporting the values this script just sent
    # would be reporting its own intent; reading them back reports the database.
    with eng.connect() as c:
        print("\nAS WRITTEN, read back from the database:")
        for _id, sku, name, _prior, want in rows:
            got = c.execute(text("SELECT included_chairs FROM products WHERE id=:i"),
                            {"i": _id}).scalar()
            ok = "OK" if got == want else f"MISMATCH (wanted {want})"
            print(f"  {sku:14} {name!r:28} included_chairs={got}  {ok}")
        stray = c.execute(text(
            "SELECT count(*) FROM products WHERE company_id=:t AND included_chairs IS NOT NULL"),
            {"t": tid}).scalar()
        print(f"\n  Sunnycrest rows with a non-null included_chairs: {stray} "
              f"(must be {len(rows)} — nothing else may have been touched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
