"""Allow `outcome = 'unresolved'` on the Opas decision log.

⚠️ RULED BY JAMES 2026-10-23: "when neither rules nor the model resolve a phrase, Opas
says so in the reply line and opens nothing… Log both: a routed-by-model row (with
latency and verdict) and a miss row (outcome = unresolved). Misses are the most valuable
test cases, so make sure they're kept."

`r214` wrote the CHECK as `outcome IN ('executed','asked','refused')`. A miss recorded as
`refused` says the rules DECLINED it, which is a different claim from "nothing resolved
this, including the model" — and the second is the one worth keeping, because it is the
test case.

⚠️ EXPAND-ONLY, AND `refused` IS DELIBERATELY STILL ACCEPTED. Rows written before today
carry it and are not rewritten: a migration that re-spelled existing rows would be
asserting something about phrases nobody re-measured. Both values are live; `unresolved`
is what new misses use.

⚠️ THE DOWNGRADE REFUSES RATHER THAN DELETES. Narrowing the CHECK again would fail on any
`unresolved` row, so the downgrade narrows only when none exist and otherwise raises with
the count. Silently deleting a director's recorded miss to make a constraint fit is the
opposite of why the table exists.
"""

from alembic import op
from sqlalchemy import text

revision = "r215_opas_decisions_unresolved"
down_revision = "r214_opas_decisions"
branch_labels = None
depends_on = None

_NAME = "ck_opas_decisions_outcome"
_OLD = "outcome IN ('executed','asked','refused')"
_NEW = "outcome IN ('executed','asked','refused','unresolved')"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(f"ALTER TABLE opas_decisions DROP CONSTRAINT IF EXISTS {_NAME}"))
    conn.execute(text(f"ALTER TABLE opas_decisions ADD CONSTRAINT {_NAME} CHECK ({_NEW})"))
    print(f"[r215] {_NAME}: {_NEW}")


def downgrade() -> None:
    conn = op.get_bind()
    n = conn.execute(
        text("SELECT count(*) FROM opas_decisions WHERE outcome = 'unresolved'")
    ).scalar()
    if n:
        raise RuntimeError(
            f"[r215] refusing to downgrade: {n} row(s) carry outcome='unresolved' and "
            "would have to be deleted or re-spelled. Those rows are recorded misses — "
            "the most valuable cases in the table. Decide what to do with them first."
        )
    conn.execute(text(f"ALTER TABLE opas_decisions DROP CONSTRAINT IF EXISTS {_NAME}"))
    conn.execute(text(f"ALTER TABLE opas_decisions ADD CONSTRAINT {_NAME} CHECK ({_OLD})"))
