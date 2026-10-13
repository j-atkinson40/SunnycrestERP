"""James's D2 and D3: St. Mary's Cemetery, and the four equipment packages.

⚠️ A PRODUCTION DATA WRITE, AUTHORIZED BY JAMES 2026-10-13 (dispatch "order
capture, final"). Recorded in DECISIONS as D2 and D3.

⚠️ IT DOES NOTHING ON A DATABASE WITHOUT THE `sunnycrest` TENANT, by instruction.
That is not politeness: this migration runs on every CI database and on every
developer's machine, and a row keyed to a tenant that is absent there would either
fail or land on whatever tenant happened to match. The guard is a lookup, and when
it misses the migration returns having written nothing.

⚠️ IDEMPOTENT BY MEASURING WHAT IS THERE, NOT BY `ON CONFLICT`. Neither target has
a unique constraint on the key we care about (`cemeteries` has none on
`(company_id, name)`; `products` has none on `(company_id, sku)` either), so an
upsert has nothing to conflict on. Each row is checked for by name/sku and skipped
if present, which also makes a re-run report `0 written` rather than a lie.

⚠️ REVERSIBLE, AND THE DOWNGRADE DELETES ONLY WHAT THIS MIGRATION'S OWN MARKERS
IDENTIFY. The four products carry `CE-*` SKUs created here; the cemetery is matched
on its exact name. A downgrade that deleted "every cemetery on sunnycrest" would
destroy rows a human had added since.

THE PRICES ARE FROM THE PRICE LIST, READ FROM THE PDF ITSELF.
`docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf`, GRAVESIDE SERVICE
table, "With Our Product" column. Decoded from the PDF's own CID fonts via its
ToUnicode CMaps rather than taken from the transcription in
`docs/catalog/2026-10-03-price-list-to-catalog-map.md` — CLAUDE.md §11 forbids
inheriting a figure, and agreeing with a derived document would prove only that two
derived documents agree. The PDF's two price columns read, in table-row order:

    Full Equipment            $300     ($600 without our product)
    Lowering Device & Grass   $185     ($487)
    Lowering Device Only      $140     ($487)
    Tent Only                 $225     ($557)
    Extra Chairs (Over 8)     $5       ($8)

Both columns agree on that row order, which is what makes the positional pairing
safe — the extracted text gives labels and prices in separate runs.

⚠️ ONLY THE "WITH OUR PRODUCT" PRICE IS STORED, AND THE OTHER ONE HAS NOWHERE TO GO.
The same package is two prices depending on whether Sunnycrest's vault is in the
ground — a property of the ORDER, not of the item, as
`docs/catalog/2026-10-03-price-list-to-catalog-map.md` §4a records. A capture order
always has our vault in it, so the with-product price is the right one here; the
without-product price is not modelled and is not invented.

⚠️ THREE PRICE-LIST PACKAGES ARE NOT CREATED. `Extra Chairs (Over 8)` is a per-unit
add-on, not a package, and `vault_placer` has no price-list line at all; James named
four and four are written. The capture offers seven packages, so three of them will
have no product and Approve will say so rather than guess.

Revision ID: r211_sunnycrest_cemetery_and_equipment
Revises: r210_order_capture_approve_columns
"""
import uuid
from decimal import Decimal

from alembic import op
from sqlalchemy import text

revision = "r211_sunnycrest_cemetery_and_equipment"
down_revision = "r210_order_capture_approve_columns"
branch_labels = None
depends_on = None

TENANT_SLUG = "sunnycrest"

CEMETERY_NAME = "St. Mary's Cemetery"
CEMETERY_CITY = "Skaneateles"
CEMETERY_STATE = "NY"

#: (sku, name, price). The NAME is what Approve matches a captured equipment
#: package against, so it must equal the package's label exactly — see
#: `EQUIPMENT_PACKAGES` in `app/services/capture/schema.py`.
EQUIPMENT = [
    ("CE-PKG-FULL", "Full Equipment", Decimal("300.00")),
    ("CE-PKG-TENT", "Tent Only", Decimal("225.00")),
    ("CE-PKG-LDG", "Lowering Device & Grass", Decimal("185.00")),
    ("CE-PKG-LD", "Lowering Device Only", Decimal("140.00")),
]


def _tenant_id(conn):
    return conn.execute(
        text("SELECT id FROM companies WHERE slug = :s"), {"s": TENANT_SLUG}
    ).scalar()


def upgrade() -> None:
    conn = op.get_bind()
    tid = _tenant_id(conn)
    if not tid:
        print(f"[r211] no {TENANT_SLUG!r} tenant on this database — wrote 0 rows")
        return

    written = {"cemeteries": 0, "products": 0}

    existing = conn.execute(
        text(
            "SELECT id FROM cemeteries WHERE company_id = :t AND name = :n"
        ),
        {"t": tid, "n": CEMETERY_NAME},
    ).scalar()
    if existing is None:
        conn.execute(
            text(
                "INSERT INTO cemeteries (id, company_id, name, city, state, is_active) "
                "VALUES (:i, :t, :n, :c, :s, true)"
            ),
            {
                "i": str(uuid.uuid4()),
                "t": tid,
                "n": CEMETERY_NAME,
                "c": CEMETERY_CITY,
                "s": CEMETERY_STATE,
            },
        )
        written["cemeteries"] += 1

    for sku, name, price in EQUIPMENT:
        found = conn.execute(
            text("SELECT id FROM products WHERE company_id = :t AND sku = :k"),
            {"t": tid, "k": sku},
        ).scalar()
        if found is not None:
            continue
        conn.execute(
            text(
                "INSERT INTO products (id, company_id, name, sku, price, is_active) "
                "VALUES (:i, :t, :n, :k, :p, true)"
            ),
            {"i": str(uuid.uuid4()), "t": tid, "n": name, "k": sku, "p": price},
        )
        written["products"] += 1

    print(
        f"[r211] {TENANT_SLUG}: wrote {written['cemeteries']} cemetery row(s) and "
        f"{written['products']} product row(s)"
    )


def downgrade() -> None:
    conn = op.get_bind()
    tid = _tenant_id(conn)
    if not tid:
        return
    conn.execute(
        text("DELETE FROM products WHERE company_id = :t AND sku = ANY(:k)"),
        {"t": tid, "k": [sku for sku, _, _ in EQUIPMENT]},
    )
    conn.execute(
        text("DELETE FROM cemeteries WHERE company_id = :t AND name = :n"),
        {"t": tid, "n": CEMETERY_NAME},
    )
