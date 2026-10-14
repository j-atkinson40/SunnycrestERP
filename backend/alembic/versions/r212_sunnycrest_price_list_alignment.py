"""James 2026-10-14: two vault prices to the price list, two equipment products added.

⚠️ A PRODUCTION DATA WRITE, AUTHORIZED BY JAMES 2026-10-14 (dispatch items 1 and 2).
Same style as `r211` by instruction: guarded on the tenant, idempotent by measuring,
reversible, and a no-op on any database without the `sunnycrest` tenant.

WHAT IT DOES

  1. `Monticello Burial Vault`   1250.00 -> 1405.00
  2. `Continental Burial Vault`  1850.00 -> 1607.00   ⚠️ A DECREASE of $243
  3. inserts `Vault Placer`             at    0.00
  4. inserts `Extra Chairs (Over 8)`    at    5.00

⚠️ IT DOES NOT TOUCH `sales_order_lines`, BY INSTRUCTION, AND A LIVE ORDER DEPENDS ON
THAT. `SO-2026-0001` exists on production (created 2026-10-14 14:35 UTC, status
`draft`, total $1,550.00) and carries a `Monticello Burial Vault` line at
`unit_price = 1250.0000`. A line price is what was agreed when the order was taken;
re-pricing it from the product would silently restate a quote the office already
gave. After this migration the PRODUCT reads $1,405 and that LINE still reads $1,250,
and the order total is still $1,550.00. `test_r212_price_alignment.py` asserts it.

WHERE THE PRICES COME FROM

`docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf`
(md5 `ab3fb519423c09fd766b0a265f288cee`, 298,155 bytes), read from the PDF itself.
BURIAL VAULTS table, Single Reinforced band: `Continental $1,607`,
`Monticello $1,405`. GRAVESIDE SERVICE table, "With Our Product" column:
`Extra Chairs (Over 8) $5`.

⚠️ THE PDF'S TEXT LAYER EMITS LABELS AND PRICES AS TWO SEPARATE RUNS, so the pairing
is POSITIONAL and could in principle be off by one. It is anchored rather than
assumed: the same price run contains `$300 / $185 / $140 / $225`, which is exactly
what `r211` wrote for Full Equipment / Lowering Device & Grass / Lowering Device Only
/ Tent Only and is live on production today. Counting back from that anchor lands
Monticello on $1,405 and Continental on $1,607 with the four "...Reinforced" band
headers carrying no price — a consistent reading of the whole run, not a guess at two
rows of it.

⚠️ AND A SECOND, INDEPENDENTLY-WRITTEN SOURCE IN THIS REPO AGREES ON ALL THREE.
`app/services/sunnycrest_product_seeder.py` carries `Continental 1607.00` (:116),
`Monticello 1405.00` (:122), `Vault Placer 0.00` (:241) and
`Extra Chairs (over 8) 5.00` (:254) — written before this arc by someone reading the
same price list. Per CLAUDE.md §11 two derived documents agreeing proves only that
they agree, so this is NOT offered as proof of the prices; it is offered as
corroboration of the POSITIONAL PAIRING, which is the part of the PDF read that
could have been wrong. Both readings of the vault band produce the same two numbers.

⚠️ THAT SEEDER HAS NEVER RUN ON SUNNYCREST AND ITS NAMES WOULD NOT MATCH IF IT DID.
It creates `Monticello` and `Continental`; production carries `Monticello Burial
Vault` and `Continental Burial Vault` (SKUs `DEMO2-P001`/`DEMO2-P002`), which is what
the capture resolves and what `SO-2026-0001` already bills. Running it would add a
SECOND Monticello at a different name and the capture would keep matching the first.
Not touched here — flagged to James 2026-10-14 as live debt, because the seeder is
reachable from `POST /products/seed-sunnycrest` (`app/api/routes/products.py:254`)
and nothing stops an admin pressing it.

WHY TWO MORE EQUIPMENT PRODUCTS

`r211` wrote four of the seven packages the capture offers and said so:
"THREE PRICE-LIST PACKAGES ARE NOT CREATED. `Extra Chairs (Over 8)` is a per-unit
add-on, not a package, and `vault_placer` has no price-list line at all." That
reasoning is SUPERSEDED by James 2026-10-14, who ruled both in: Vault Placer at
$0.00 because it is no additional charge, Extra Chairs at $5.00 per chair. With these
two, all seven packages the capture can answer have a billable product and Approve
stops refusing orders the office can actually place.

⚠️ `Vault Placer` AT $0.00 IS A PRICE, NOT A MISSING ONE. `approval.assess` blocks on
`prod.price is None` and not on a zero, so a $0.00 product produces a real line at
$0.00 — which is what "no additional charge, but it was on the order" should look
like on a statement. A NULL price would have blocked Approve instead.

Revision ID: r212_sunnycrest_price_list_alignment
Revises: r211_sunnycrest_cemetery_and_equipment
"""
import uuid
from decimal import Decimal

from alembic import op
from sqlalchemy import text

revision = "r212_sunnycrest_price_list_alignment"
down_revision = "r211_sunnycrest_cemetery_and_equipment"
branch_labels = None
depends_on = None

TENANT_SLUG = "sunnycrest"

#: (product name, price before, price after).
#:
#: ⚠️ THE "BEFORE" IS PART OF THE GUARD, NOT DECORATION. The update fires only on a
#: row still carrying the old price, which makes a re-run write 0 rows AND makes the
#: migration refuse to clobber a price a human has changed since. A bare
#: `SET price = :new WHERE name = :n` would be idempotent in the weak sense — same
#: end state — while quietly overwriting an intervening decision.
REPRICE = [
    ("Monticello Burial Vault", Decimal("1250.00"), Decimal("1405.00")),
    ("Continental Burial Vault", Decimal("1850.00"), Decimal("1607.00")),
]

#: (sku, name, price). The NAME is what Approve matches a captured equipment package
#: against, so it must equal the package's label in `EQUIPMENT_PACKAGES`
#: (`app/services/capture/schema.py`). `test_r212_price_alignment.py` asserts that
#: correspondence rather than leaving it to a reader to notice.
EQUIPMENT = [
    ("CE-PKG-VP", "Vault Placer", Decimal("0.00")),
    ("CE-CHAIR-EX", "Extra Chairs (Over 8)", Decimal("5.00")),
]


def _tenant_id(conn):
    return conn.execute(
        text("SELECT id FROM companies WHERE slug = :s"), {"s": TENANT_SLUG}
    ).scalar()


# ⚠️ THE BODY IS PARAMETERISED BY TENANT AND THE ALEMBIC HOOKS ARE THIN WRAPPERS,
# SO THAT THIS CAN BE TESTED WITHOUT AN ALEMBIC CONTEXT OR A `sunnycrest` ROW.
# `op.get_bind()` needs a migration context, and a test that ran `alembic upgrade`
# against the dev database would mutate state shared with every other test — which
# CLAUDE.md §11 names as the reason a before-and-after pair stops being repeatable.
# `test_r212_price_alignment.py` builds its own throwaway tenant, calls these two,
# and asserts the real SQL. Dev cannot exercise it otherwise: measured 2026-10-14,
# the dev `sunnycrest` carries no `Continental Burial Vault` at all.


def _apply(conn, tid) -> tuple[int, int]:
    """Returns `(repriced, added)`."""
    repriced = 0
    for name, before, after in REPRICE:
        res = conn.execute(
            text(
                "UPDATE products SET price = :after "
                "WHERE company_id = :t AND lower(btrim(name)) = lower(btrim(:n)) "
                "AND price = :before"
            ),
            {"t": tid, "n": name, "before": before, "after": after},
        )
        repriced += res.rowcount or 0

    added = 0
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
        added += 1

    return repriced, added


def _revert(conn, tid) -> None:
    # ⚠️ THE REVERSE GUARD IS THE NEW PRICE, for the same reason the forward one is
    # the old. A downgrade must not reset a price someone has since set deliberately.
    for name, before, after in REPRICE:
        conn.execute(
            text(
                "UPDATE products SET price = :before "
                "WHERE company_id = :t AND lower(btrim(name)) = lower(btrim(:n)) "
                "AND price = :after"
            ),
            {"t": tid, "n": name, "before": before, "after": after},
        )
    conn.execute(
        text("DELETE FROM products WHERE company_id = :t AND sku = ANY(:k)"),
        {"t": tid, "k": [sku for sku, _, _ in EQUIPMENT]},
    )


def upgrade() -> None:
    conn = op.get_bind()
    tid = _tenant_id(conn)
    if not tid:
        print(f"[r212] no {TENANT_SLUG!r} tenant on this database — wrote 0 rows")
        return
    repriced, added = _apply(conn, tid)
    print(
        f"[r212] {TENANT_SLUG}: repriced {repriced} product(s), "
        f"added {added} product(s)"
    )


def downgrade() -> None:
    conn = op.get_bind()
    tid = _tenant_id(conn)
    if not tid:
        return
    _revert(conn, tid)
