"""Held words get a column, because they outlive the text they came from.

Slice 2, clause 1 (James, 2026-10-28, resumed 2026-11-03): *"words leave the bar when
typed past and fly into their field … held words saved in the new column."* The dispatch
authorises this: *"expand-only migration if needed, James's go."*

⚠️ **THE REASON IS MEASURED, AND I EXPECTED NOT TO NEED THIS COLUMN.** `unrecognized`
looks like the right home and cannot be: it is `list[str]` — no position, no state, no
identity — and it is **RECOMPUTED FROM THE TEXT ON EVERY READ**. Measured on production
during the 2026-10-28 design review: one session held
`['smith', '1', '1 oclock church', 'friday']`, all derived from `full_text`. Clause 1
takes the word OUT of the text in the same gesture that holds it, so a list computed
from the text cannot see it at all. The moment words leave the bar, `unrecognized`
becomes structurally incapable of holding them.

⚠️ **AND IT NEEDS AN IDENTITY, WHICH IS THE OTHER HALF.** Clause 4 (push 2) drags a held
word onto a field, edits it in place, and drops it with an ×; the prototype's chips carry
`data-h="<id>"` for exactly that. A bare string cannot be addressed by a drag that has
to say WHICH chip moved when two hold the same word — "smith" twice is not a strange
thing to type.

### The shape is `held.HeldWord`, not a shape of this migration's own

    word      the word as it stands now — the director's text, or their edit of it.
    origin    `typed` / `edited` / `dragged`, so the strip can say how it got there.
    declined  the TERMS the office has said No to, not a bare flag — clause 5 must not
              re-offer a declined suggestion, and storing the terms means editing the
              word to something else can still be suggested about.
    id        a client-addressable identity, added 2026-11-03 for the strip.

⚠️ **IT MIRRORS `HeldWord` RATHER THAN DEFINING ITS OWN SHAPE, AND MY FIRST DRAFT OF
THIS FILE DID NOT.** I wrote a `{id, text, at, no_suggest}` shape before reading
`held.py`, which has carried `word` / `origin` / `declined` and a tolerant `from_dict`
since 2026-10-29 — the whole reason that module was built first. A column whose keys
disagreed with the record that parses it is the two-bodies-of-one-rule shape this repo
has paid for twice (`CHAIRS_INCLUDED`, two `title_case_name`s). The ONLY thing this
slice adds to the record is `id`, because a drag has to name one chip.

⚠️ **AND `at` IS NOT STORED, WHICH THE FIRST DRAFT ALSO GOT WRONG.** Order comes from
the list's own order — JSONB preserves it — so a timestamp would be a second source for
the same fact. `HeldWord` never had one.

⚠️ **JSONB RATHER THAN A TABLE, AND THAT IS THE SAME CHOICE EVERY OTHER CAPTURE LIST
MADE.** `typed_lines`, `pending_picks`, `switches` and `resolutions` are all JSONB on
this row; held words have exactly their lifetime (one capture session), exactly their
cardinality (a handful), and no reader outside the session. A table would add a join to
every keystroke read for no query anyone wants to run.

⚠️ **NULLABLE WITH NO SERVER DEFAULT, matching `unrecognized` and `pending_picks` beside
it.** `NULL` and `[]` both read as "nothing held" through `row.held_words or []`, which
is how every other list on this row is read. A `server_default='[]'` would make the
column's absence indistinguishable from an empty one in a way nothing needs.

Downgrade drops the column. ⚠️ **AND THAT LOSES HELD WORDS RATHER THAN SILENTLY MOVING
THEM**, which is the honest direction: they are session-scoped and transient, no order
depends on one, and writing them back into `unrecognized` would put words into a field
that is recomputed from the text on the next keystroke and would therefore drop them
again — one read later, with no trace.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r219_capture_held_words"
down_revision = "r218_included_chairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        sa.Column(
            "held_words",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Words the engine could not place, which OUTLIVE the text they came "
                "from. Slice 2 clause 1 removes a placed word from the bar, so "
                "`unrecognized` — recomputed from `full_text` on every read — cannot "
                "hold them. Each entry is `held.HeldWord.as_dict()`: "
                "{word, origin, id, declined?}."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "held_words")
