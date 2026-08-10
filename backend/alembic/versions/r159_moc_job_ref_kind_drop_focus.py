"""FR-1 follow-on — tighten ck_moc_job_ref_kind to drop 'focus'.

FR-1 (`17354440`) removed the `focus` REF kind from the service: `REF_KINDS`,
its checker, its resolver, and the bridge that turned job refs into focus beats.
It deliberately did NOT touch the constraint, because a schema change is a
decision and should arrive as one rather than as a side effect of a removal
commit. This is that decision.

WHAT THIS CLOSES. Between FR-1 and this migration the service refuses a `focus`
ref and the database would accept one written around the service — a guard with
a hole, which is the shape this codebase has spent the week closing. After this,
both layers agree.

⚠️ THE `focus` BEAT KIND IS NOT AFFECTED, AND NOTHING HERE TOUCHES IT. Two
vocabularies share the word in `maps_of_content`: the REF kind (a `moc_job_ref`
row, removed) and the BEAT kind (`platform_map.py:88-102` builds
`{"key": "exhibit", "kind": "focus"}` from a direct FocusTemplate read, with no
ref involved). This constraint governs `moc_job_ref.ref_kind` only. The exhibit
grammar is untouched.

NO DATA WORK. Zero `focus` refs exist on production or dev — verified before
writing this, not assumed — so no row needs migrating and the tightened
constraint validates against existing data on both. The pre-flight below refuses
rather than failing mid-DDL if that ever stops being true somewhere else.

REVERSIBLE. The downgrade restores the permissive three-value constraint. It does
NOT restore the service-side kind — that is FR-1's commit to revert, and the two
are independent by design: the constraint may be loosened without the service
accepting the kind again.
"""
from alembic import op
import sqlalchemy as sa

revision = "r159_moc_job_ref_kind_drop_focus"
down_revision = "r158_accounting_cadence_captions"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_moc_job_ref_kind"
_TABLE = "moc_job_ref"


def upgrade() -> None:
    conn = op.get_bind()

    # PRE-FLIGHT — REFUSE, DO NOT FAIL MID-DDL. A surviving `focus` row would
    # make the new constraint invalid at creation time, and the failure would
    # arrive as a Postgres error mid-migration rather than as something an
    # operator can act on. Production and dev were both verified at zero before
    # this was written; this is for the environment nobody checked.
    stale = conn.execute(
        sa.text(f"SELECT count(*) FROM {_TABLE} WHERE ref_kind = 'focus'")
    ).scalar()
    if stale:
        raise RuntimeError(
            f"{stale} moc_job_ref row(s) still use ref_kind='focus'. The "
            f"tightened constraint would reject them. Decide what those refs "
            f"should be — most likely 'triage_queue', which is how the "
            f"accounting jobs reach their surfaces — then re-run. "
            f"Query: SELECT id, job_id, ref_key FROM {_TABLE} "
            f"WHERE ref_kind = 'focus';"
        )

    # DROP-then-ADD, not ALTER: Postgres has no ALTER CONSTRAINT for a CHECK
    # expression. IF EXISTS so a database that somehow lacks it (created outside
    # the migration chain) still reaches the intended end state rather than
    # erroring on the drop.
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.create_check_constraint(
        _CONSTRAINT, _TABLE,
        "ref_kind IN ('automation', 'triage_queue')",
    )


def downgrade() -> None:
    # Restores the permissive constraint ONLY. The service still refuses the
    # kind — reverting FR-1 is a separate act, and keeping them independent is
    # deliberate: loosening the database should never silently re-enable a
    # capability the service has removed.
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.create_check_constraint(
        _CONSTRAINT, _TABLE,
        "ref_kind IN ('automation', 'triage_queue', 'focus')",
    )
