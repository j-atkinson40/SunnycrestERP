"""James's rulings of 2026-10-28, second batch. His go for both writes.

    RULING 1  Sunnycrest sells BOTH Continentals.
              - link the existing Continental product -> BV-CON (Standard)
              - add a `Continental 34"` product -> BV-CON34, priced from the
                February 2026 price list

⚠️ THE PRICE IS MEASURED, TWICE, AND NOT INVENTED. The ruling says to stop and ask
if the price list has no 34" price. It has one:

    docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf
    sha256 b5f679c37a8efb40f4f833be811ac57cf3601c138352d2003ad701c122efde41
    298,155 bytes, 2 pages

    page 1, ODD SIZED group, aligned by COORDINATE rather than by list order:
        y=627.0  ->  $2,179
        y=627.3  ->  Continental 34"
    and independently, docs/catalog/2026-10-03-price-list-to-catalog-map.md:158
    records the same figure as "measured — p1".

    The same alignment puts `Continental` (standard) at $1,607, which is what the
    existing product already carries — so the two sit consistently on one list.

⚠️ DRY RUN BY DEFAULT. `--apply` writes. Rollback SQL is emitted either way.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.database import SessionLocal

TENANT_SLUG = "sunnycrest"

#: Continental / Standard — BV-CON. The existing product links here.
CON_STANDARD = "7eddfbea-d125-5435-b18d-0611911e1941"
#: Continental / 34 inch — BV-CON34. The new product links here.
CON_34 = "9e1bfebe-c005-503e-9c9e-d619fa92ebab"

EXISTING_SKU = "DEMO2-P002"
EXISTING_NAME = "Continental Burial Vault"

NEW_NAME = 'Continental 34"'
#: ⚠️ THE NAME IS THE LOAD-BEARING FIELD, NOT THE LINK — see the module note in the
#: report. `Continental 34"` resolves to exactly ONE catalogue candidate
#: (9e1bfebe), where `Continental Burial Vault` returns two and abstains. Measured
#: on production before writing.
NEW_SKU = "BV-CON34"
NEW_PRICE = Decimal("2179.00")


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

    now = datetime.now(timezone.utc)
    print(f"=== {mode} — tenant {TENANT_SLUG} ({tid}) at {now.isoformat()} ===\n")
    rollback: list[str] = []

    # ── 1a. link the existing Continental to BV-CON ────────────────────────────────
    print("--- 1a. existing Continental -> BV-CON (Standard) ---")
    sib = db.execute(text("""
        SELECT * FROM products WHERE company_id = :t AND sku = :sku
    """), {"t": tid, "sku": EXISTING_SKU}).mappings().one_or_none()
    if sib is None:
        print(f"  REFUSE: no product with sku {EXISTING_SKU!r} for this tenant")
        return 1
    if sib["name"] != EXISTING_NAME:
        print(f"  REFUSE: sku {EXISTING_SKU} is {sib['name']!r}, the ruling names "
              f"{EXISTING_NAME!r} — not the product this link was measured for")
        return 1

    prior = sib["variant_template_id"]
    if prior == CON_STANDARD:
        print(f"  NO-OP: already linked to {CON_STANDARD}")
    else:
        print(f"  {EXISTING_SKU} {sib['name']!r}  (${sib['price']})")
        print(f"     prior variant_template_id = {prior!r}")
        print(f"     new   variant_template_id = {CON_STANDARD!r}  (BV-CON, option 'Standard')")
        rollback.append(
            f"UPDATE products SET variant_template_id = "
            f"{'NULL' if prior is None else repr(prior)} "
            f"WHERE company_id = '{tid}' AND sku = '{EXISTING_SKU}';"
        )
        if args.apply:
            db.execute(text("""
                UPDATE products SET variant_template_id = :v, updated_at = :now
                WHERE company_id = :t AND sku = :sku
            """), {"v": CON_STANDARD, "t": tid, "sku": EXISTING_SKU, "now": now})

    # ── 1b. add the Continental 34" ────────────────────────────────────────────────
    print(f"\n--- 1b. add {NEW_NAME!r} -> BV-CON34 at ${NEW_PRICE} ---")
    dup = db.execute(text("""
        SELECT id, name, price, variant_template_id FROM products
        WHERE company_id = :t AND (sku = :sku OR name = :name)
    """), {"t": tid, "sku": NEW_SKU, "name": NEW_NAME}).mappings().first()
    if dup is not None:
        print(f"  NO-OP: a product already exists — {dup['name']!r} "
              f"${dup['price']} vtid={dup['variant_template_id']}")
    else:
        new_id = str(uuid.uuid4())
        print(f"  id    = {new_id}")
        print(f"  name  = {NEW_NAME!r}")
        print(f"  sku   = {NEW_SKU!r}")
        print(f"  price = {NEW_PRICE}  (price list p1, ODD SIZED, measured by coordinate)")
        print(f"  link  = {CON_34}  (BV-CON34, option '34 inch')")
        # ⚠️ EVERY OTHER FIELD IS CLONED FROM THE SIBLING RATHER THAN CHOSEN. A new
        # product on a real tenant's books should differ from its sibling in exactly
        # the three things the ruling names — name, sku, price — plus the link. Any
        # field I picked myself would be an unmeasured assertion about how Sunnycrest
        # sells this vault.
        cloned = {
            "category_id": sib["category_id"],
            "description": sib["description"],
            "cost_price": sib["cost_price"],
            "unit_of_measure": sib["unit_of_measure"],
            "is_active": sib["is_active"],
            "pricing_type": sib["pricing_type"],
            "source": sib["source"],
            "is_inventory_tracked": sib["is_inventory_tracked"],
            "is_direct_ship_product": sib["is_direct_ship_product"],
            "taxability": sib["taxability"],
            "is_call_office": sib["is_call_office"],
            "has_conditional_pricing": sib["has_conditional_pricing"],
            "is_extension_hidden": sib["is_extension_hidden"],
            "is_placer": sib["is_placer"],
            "is_lowering_device": sib["is_lowering_device"],
            "has_personalization": sib["has_personalization"],
            "tax_class": sib["tax_class"],
            "created_by": sib["created_by"],
            "is_manufactured": sib["is_manufactured"],
        }
        for k, v in cloned.items():
            print(f"     cloned {k:26} = {v!r}")
        # ⚠️ `has_personalization` IS CLONED AS-IS AND THE SIBLING SAYS False, WHICH
        # DISAGREES WITH THE CATALOGUE — availability permits `nameplate_only` on both
        # Continentals. Nothing in the capture or personalization path reads this
        # column (grepped), so the disagreement is inert; it is cloned rather than
        # "corrected" because correcting it would be an unmeasured write to a column
        # whose meaning is not documented. Flagged for James.
        rollback.append(
            f"DELETE FROM products WHERE company_id = '{tid}' AND sku = '{NEW_SKU}';"
        )
        if args.apply:
            db.execute(text("""
                INSERT INTO products (
                    id, company_id, category_id, name, sku, description, price,
                    cost_price, unit_of_measure, is_active, created_at, updated_at,
                    created_by, is_manufactured, pricing_type, source,
                    is_inventory_tracked, is_direct_ship_product, taxability,
                    is_call_office, has_conditional_pricing, is_extension_hidden,
                    is_placer, is_lowering_device, has_personalization, tax_class,
                    variant_template_id
                ) VALUES (
                    :id, :cid, :category_id, :name, :sku, :description, :price,
                    :cost_price, :unit_of_measure, :is_active, :now, :now,
                    :created_by, :is_manufactured, :pricing_type, :source,
                    :is_inventory_tracked, :is_direct_ship_product, :taxability,
                    :is_call_office, :has_conditional_pricing, :is_extension_hidden,
                    :is_placer, :is_lowering_device, :has_personalization, :tax_class,
                    :vtid
                )
            """), {"id": new_id, "cid": tid, "name": NEW_NAME, "sku": NEW_SKU,
                   "price": NEW_PRICE, "now": now, "vtid": CON_34, **cloned})

    print("\n" + "=" * 72)
    print("ROLLBACK SQL:")
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
