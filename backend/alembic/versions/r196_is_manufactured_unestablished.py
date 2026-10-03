"""is_manufactured stops asserting a fact nobody chose

Revision ID: r196_is_manufactured_unestablished
Revises: r195_price_list_catalog_load
Create Date: 2026-10-03

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Drops two server
defaults, makes one column nullable, and nulls one table's rows. No row is created
or deleted.

THE RULING, and the reason it is a product decision rather than a cleanup.

Wilbert's model is **licensed local manufacture**, so most licensees pour. The
tenant tier defaulted to `false` — the UNCOMMON answer — and the only tenant
available to check it against reality is Sunnycrest, which BUYS every vault it
sells and therefore makes the wrong default look right.

Measured in production 2026-10-03, read-only:

    products, all tenants, demo INCLUDED     33 rows
    is_manufactured = true                    0        ← not one, anywhere

The column has never been written by anything but its default. It is not that the
data is wrong; **there is no data, wearing a boolean's clothes.** NULL until
onboarding asks each licensee which products they make — a question already being
asked in a flow that exists.

WHAT CHANGES, PER TABLE, AND WHY THEY DIFFER:

1. **`products.is_manufactured`** — drop `server_default` (`false`, from
   `u3v4w5x6y7z8`), make NULLABLE, set **every** row to NULL.
   This is the default-driven form: `u3v4w5x6y7z8` added the column to an
   already-populated table via `op.add_column`, so every pre-existing product
   began asserting "we do not make this" without anyone deciding it.

2. **`product_catalog_templates.is_manufactured`** — drop `server_default`
   (`true`, from `x1y2z3a4b5c6:253`). ⚠️ **The rows are NOT nulled, deliberately.**

   Two reasons, and the second is the stronger:

   - That table is scheduled for removal in Phase 3. Nulling rows that are about
     to be dropped is work that gets discarded. Dropping the default is what
     matters: it stops NEW rows acquiring the assertion between now and then.
   - ⚠️ **Its values VARY, so they are decisions rather than a fill.** Measured on
     `bridgeable_dev`: 15 `true` against 10 `false`. `x1y2z3a4b5c6` writes
     `True, True, False, False` at `:284/:309/:333/:356`, and
     `catalog_template_seeder` writes `True` for Burial Vaults (`:87`), `True` for
     Urn Vaults (`:103`) and `False` for Cemetery Equipment (`:119`) — three
     loops, three categories, one of them different. **Vaults are poured and
     cemetery equipment is bought.** Somebody chose that. Nulling it would destroy
     a real finding to satisfy a rule aimed at fills.

   This is the distinction CLAUDE.md §5 turns on: "a value written UNIFORMLY
   across a bulk insert". Varying literals are per-row decisions and stay. The
   seeder's three writes were measured before this migration was written, exactly
   to decide this, and they stay.

⚠️ THE PYTHON-SIDE DEFAULT IS A SECOND MECHANISM AND IS HANDLED IN THE MODEL.
`product_catalog_template.py` declared `mapped_column(Boolean, default=True)` —
a SQLAlchemy-level default, not a server default. Dropping the server default
alone would leave every ORM-created row still asserting `True`. The model drops it
in the same commit. A migration that fixes only the database half of a two-sided
default has fixed nothing for the path that actually inserts.

NO READERS, re-verified before writing rather than inherited:
  - `products.is_manufactured` has **no ORM attribute at all** — it is
    structurally unreachable, not merely unread. r196 declares it (see the model
    change) so the column is finally describable.
  - `product_catalog_templates.is_manufactured` is written by the seeder, crosses
    the wire via a `ProductTemplateResponse` that is **declared and never
    imported**, and is read by nothing. `price_list_analysis_service:750` filters
    on `preset`; `onboarding_service:1754` queries the table without touching this
    column.
  - The detector was broken in both languages on 2026-10-03 — a planted Python
    branch and a planted TS branch were both found by the same search.

EXPAND/CONTRACT. ⚠️ MIXED, and stated rather than glossed. Making `products`
nullable WIDENS what the schema accepts, so an old reader is unaffected. But the
column had no ORM attribute, so no running code reads it, and nothing can observe
the value change. Dropping a server default narrows nothing — it only stops future
inserts acquiring a value they never asked for.

SAFE TO REVERSE. ⚠️ The downgrade restores `false` on every `products` row, which
is LOSSY in the direction that matters: it cannot distinguish "measured as not
manufactured" from "never established", which is the entire distinction this
migration adds. Stated so a downgrade is not mistaken for a round trip.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r196_is_manufactured_unestablished"
down_revision = "r195_price_list_catalog_load"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---- capture the template table's values so the assertion can prove they
    # ---- survived, rather than asserting a count that would hold either way.
    before = sorted(
        (r[0], r[1])
        for r in bind.execute(
            sa.text("SELECT id, is_manufactured FROM product_catalog_templates")
        )
    )

    # ---- 1. products: the default-driven form ------------------------------
    op.alter_column(
        "products",
        "is_manufactured",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    n_before = bind.execute(sa.text("SELECT count(*) FROM products")).scalar_one()
    res = bind.execute(sa.text("UPDATE products SET is_manufactured = NULL"))

    # ---- 2. product_catalog_templates: default only, rows untouched --------
    # Already nullable; only the server default is dropped.
    op.alter_column(
        "product_catalog_templates",
        "is_manufactured",
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=None,
    )

    # ---- postconditions, read back -----------------------------------------
    n_nonnull = bind.execute(
        sa.text("SELECT count(*) FROM products WHERE is_manufactured IS NOT NULL")
    ).scalar_one()
    assert n_nonnull == 0, f"{n_nonnull} products still assert a value"

    # ⚠️ THE POSITIVE CONTROL IS THE UPDATE'S OWN ROWCOUNT, not a row-count floor.
    # An earlier draft asserted `count(*) > 0` to stop the check above passing
    # vacuously — and it FIRED on a from-empty build, where `products` is
    # legitimately empty and "0 non-null" is the correct state. It conflated
    # "nothing to check" with "the check is blind".
    #
    # Comparing the UPDATE's rowcount to the pre-UPDATE count proves the statement
    # actually touched every row it should have, and is correct at zero: an empty
    # table yields 0 == 0. The control now scales with the data instead of
    # assuming it.
    assert res.rowcount == n_before, (
        f"UPDATE touched {res.rowcount} rows against {n_before} present"
    )

    after = sorted(
        (r[0], r[1])
        for r in bind.execute(
            sa.text("SELECT id, is_manufactured FROM product_catalog_templates")
        )
    )
    assert after == before, (
        "product_catalog_templates rows changed; they carry per-row decisions "
        "(varying values) and must be left alone"
    )

    for table in ("products", "product_catalog_templates"):
        d = bind.execute(
            sa.text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = 'is_manufactured'"
            ),
            {"t": table},
        ).scalar_one()
        assert d is None, f"{table}.is_manufactured still has a default: {d!r}"

    nullable = bind.execute(
        sa.text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'products' AND column_name = 'is_manufactured'"
        )
    ).scalar_one()
    assert nullable == "YES", f"products.is_manufactured is still {nullable}"


def downgrade() -> None:
    # ⚠️ LOSSY. Collapses "not established" back into "we do not make this".
    op.execute("UPDATE products SET is_manufactured = false WHERE is_manufactured IS NULL")
    op.alter_column(
        "products",
        "is_manufactured",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "product_catalog_templates",
        "is_manufactured",
        existing_type=sa.Boolean(),
        existing_nullable=True,
        server_default=sa.text("true"),
    )
