"""capture_sessions.prefix_offers — the "did you mean" offers a read cannot recompute.

Slice 2 push 2, item 4 (James, 2026-10-28): *"'Did you mean…?' Yes/No pills for
Suggestions and PrefixOffers (showing 'instead of …')"*.

⚠️ A COLUMN RATHER THAN A RECOMPUTE, AND THE `switches` PRECEDENT DECIDED IT.
`PrefixOffer` is built by `extract_text` and lives on `TextExtraction` — NOT on
`CaptureState`, which is what `read_state` gets from `evaluate_typed`. So a read cannot
see the offers without re-running the extractor, and `read_state` is the hot path: one
call per pause per keystroke-burst, already paying for pills and a surface render.

`set_text` already persists exactly this shape of thing for exactly this reason —
`row.switches = [asdict(sw) for sw in ex.switches]`, alongside `unrecognized` and
`pending_picks`. This is the fourth member of that family and is stored the same way.

⚠️ NULLABLE, AND "NOT ESTABLISHED" IS THE POINT. Every session that existed before this
column did have offers computed for it — the extractor ran — and nobody wrote them down.
A `server_default` of `'[]'` would assert "this session had no prefix offers" about
thousands of rows where the truth is "nobody asked". CLAUDE.md §5: a value written
uniformly across rows nobody measured is the same false claim however it arrives.

⚠️ AND THE MODEL CARRIES NO `default=` EITHER. §5's enforcement note: a default can live
in two layers, and dropping one is not dropping it. `_store_prefix_offers` writes a list
explicitly on every `set_text`; an absent value stays absent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r228_capture_prefix_offers"
down_revision = "r227_tenant_invite_email_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        # ⚠️ `none_as_null=True` SO "NOT ESTABLISHED" STAYS QUERYABLE. Measured on a
        # plain `JSONB` column: assigning Python `None` stores the JSON value `null`,
        # and `prefix_offers IS NULL` is then FALSE — which would defeat the whole
        # reason this column is nullable. `r221`/`r224` are the precedent: that pair
        # shipped the plain form, every `IS NULL` over it was silently false, and a
        # second migration had to normalise the rows.
        sa.Column(
            "prefix_offers",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "prefix_offers")
