"""case_merchandise.vault_personalization: schema_version 1 -> 2 (answers, not tasks)

Revision ID: r185_personalization_record_v2
Revises: r184_tenant_column_company_fks
Create Date: 2026-09-22

⚠️ THIS IS A DATA MIGRATION AND IT WRITES TO PRODUCTION ON DEPLOY.
`backend/railway-start.sh:45` runs `alembic upgrade head` on every deploy and
aborts the deploy on failure, so merging this to `main` IS applying it.

⚠️ NO SCHEMA CHANGE. Not a column, not a constraint, not an index. The column is
already `JSONB`; only the shape of what is inside it moves.

WHAT IT TOUCHES, MEASURED RATHER THAN ESTIMATED

Read-only against production 2026-09-22 14:16 UTC:

    case_merchandise                      3 rows
      vault_personalization NOT NULL      1 row   <- the only row this touches
    order_personalization_tasks           0 rows

That one row is the seeded Hopkins demo case FC-2026-0001. It holds
`physical_emblem: {}` with `physical_nameplate: null` — an emblem with no
nameplate — which becomes `nameplate_cover_emblem: cover_emblem_only`. That is
the answer the re-key nearly modelled away, so the only row in existence is also
the one worth migrating carefully.

⚠️ THE VAULT IS DELIBERATELY NOT CORRECTED. The row names "Monticello Standard",
and the ordering portal records Monticello as taking no personalization at all.
That is a DATA correction, not a shape correction, and there is nothing valid to
correct it to yet — Sunnycrest's catalog on production is four `DEMO2-*` products
with no personalization configured. It belongs to the seeding work. This
migration changes shape only; `vault_product_name` is passed through untouched.

⚠️ WHY THE TRANSFORM IS IMPORTED RATHER THAN FROZEN INTO THIS FILE. A migration
that inlines its own copy is immune to later code movement, which is the usual
argument for doing it. Here it would mean TWO copies of the v1->v2 mapping — and
two copies of one rule drifting apart is the exact defect this whole re-key
exists to remove. One copy, tested by `tests/test_personalization_question_layer.py`,
whose round-trip proof covers all 16 combinations of the canonical four.

THE DOWNGRADE IS EXACT, and that is tested rather than asserted. `to_v2` keeps
the original `options` object verbatim under `legacy_v1_options`, so `to_v1`
restores the record rather than reconstructing something that merely means the
same. ⚠️ "Exact" means dict-equality: the column is JSONB, which normalises key
order on write, so byte-equality is not in anyone's gift.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r185_personalization_record_v2"
down_revision = "r184_tenant_column_company_fks"
branch_labels = None
depends_on = None


def _transform(direction: str) -> None:
    from app.services.personalization.records import (
        SCHEMA_VERSION_V1, SCHEMA_VERSION_V2, to_v1, to_v2,
    )

    conn = op.get_bind()
    want = SCHEMA_VERSION_V1 if direction == "up" else SCHEMA_VERSION_V2
    fn = to_v2 if direction == "up" else to_v1

    rows = conn.execute(sa.text(
        "SELECT id, vault_personalization FROM case_merchandise "
        "WHERE vault_personalization IS NOT NULL "
        "AND (vault_personalization->>'schema_version')::int = :v"
    ), {"v": want}).fetchall()

    for row_id, payload in rows:
        conn.execute(
            sa.text("UPDATE case_merchandise SET vault_personalization = "
                    "CAST(:p AS jsonb) WHERE id = :i"),
            {"p": json.dumps(fn(payload)), "i": row_id},
        )
    print(f"r185: {direction}graded {len(rows)} vault_personalization record(s)")


def upgrade() -> None:
    # ⚠️ NO try/except. A record this cannot transform is a record whose shape
    # nobody anticipated, and the deploy should stop rather than leave a mix of
    # v1 and v2 behind a green migration.
    _transform("up")


def downgrade() -> None:
    _transform("down")
