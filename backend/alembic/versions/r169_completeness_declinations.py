"""CR-3 D-1 — a place for a tenant to say "we don't do that".

⚠️ WHY THIS IS A TABLE AND THE EXPECTATIONS BESIDE IT ARE NOT. They are
different kinds of fact and the difference is the whole sub-arc.

A DECLARATION is a platform statement — a precast plant owes a daily production
log — identical for every tenant and versioned with the code that derives it. It
belongs in `services/completeness/expectations.py` and changes by deploy.

A DECLINATION is a tenant OBSERVATION — we don't run a delivery fleet — authored
by an operator, dated, attributable, and reversible without a release. Declaring
it in code would require a deploy every time a tenant answers, which means the
tenant cannot answer at all. That is the unreachable-capability shape this arc
exists to close, and putting it in code would move it rather than remove it.

Pre-D-1 it lived in `TENANT_DECLINED: dict[str, list[Declination]] = {}` — a code
dict nobody could write to, which is what a placeholder for this table looks
like. The dict is REMOVED in the same change: a code dict and a table both
answering "is this declined" is two producers of one fact, this codebase's
standing defect.

⚠️ REVOCATION IS IN-ROW, NOT A SECOND RECORD. `revoked_at` is the answer to "when
did we start doing this again", so the history the second-row shape wanted is
kept — a tenant who declines, resumes and declines again has one row per episode.
Three reasons it beats a second row:

  - a second row needs a `kind` discriminator, so one table holds two kinds of
    fact and a revocation's "reason" means something different from a
    declination's;
  - "is this declined now" becomes the PREDICATE `revoked_at IS NULL` rather than
    latest-wins over rows with no guaranteed order. Unspecified ordering deciding
    an outcome is a defect this repository has shipped twice —
    `_schedulable_workflows` returning `.all()` with no ORDER BY, and duplicate
    `step_order` resolved by whatever Postgres returned first;
  - `period_locks` is the closest analogue in the codebase — a signed,
    tenant-scoped, reversible assertion over a period — and it revokes in row via
    `unlocked_by` / `unlocked_at`, not by appending.

⚠️ THE SHAPE COMES FROM `period_locks`; THE FIELDS COME FROM r168. Deliberately
not inherited wholesale: `period_locks` has `unlocked_by` and NO name/role
snapshot, and A-2 established the snapshot as the half that matters. Roles change
and users are deactivated, so a join answers "what do they hold NOW", which is a
different question from "did they hold it when they answered". That fact is only
capturable at write time. Storing is irreversible if missed, so it is stored —
and a declination stands until revoked where a nil claim answers for one period,
so the author matters MORE here, not less.

⚠️ `reason` IS NOT NULL. "We don't do that" with no reason is the weak assertion
this arc rejected everywhere else, and unlike a nil claim it is permanent until
someone revokes it.

Revision ID: r169_completeness_declinations
Revises: r168_completeness_nil_claims
"""
from alembic import op
import sqlalchemy as sa

revision = "r169_completeness_declinations"
down_revision = "r168_completeness_nil_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "completeness_declinations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        # The obligation this answers. A string key, not an FK: expectations are
        # DECLARED IN CODE, so there is no row to point at. A declination against
        # a key that no longer exists stays readable rather than dangling — and
        # r168 made the same call for the same reason.
        sa.Column("expectation_key", sa.String(64), nullable=False),
        # ── The declination ──
        sa.Column("declined_on", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        # Nullable FK: a departed operator must not take their answer with them.
        sa.Column("declined_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        # Snapshotted at write time — see the module docstring.
        sa.Column("declined_by_name", sa.String(255), nullable=False),
        sa.Column("declined_by_role_slug", sa.String(64), nullable=False),
        # ── The revocation, in row ──
        # `revoked_on` is the first day the obligation is owed AGAIN, not the last
        # day it was declined. The range the resolver reads is half-open,
        # `[declined_on, revoked_on)`, so the period a tenant resumes in is owed
        # rather than forgiven and no period is ambiguous between two episodes.
        sa.Column("revoked_on", sa.Date, nullable=True),
        sa.Column("revoked_reason", sa.Text, nullable=True),
        sa.Column("revoked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_by_name", sa.String(255), nullable=True),
        sa.Column("revoked_by_role_slug", sa.String(64), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # ⚠️ TWO COLUMNS DESCRIBE THE REVOCATION AND THEY MUST AGREE THAT IT
        # HAPPENED. `revoked_on` is the EFFECTIVE date the obligation is owed
        # again; `revoked_at` is when the revocation was RECORDED. Legitimately
        # different values — an operator can revoke today effective the 1st — so
        # they are not collapsed. But their NULL-ness is one fact, and without
        # this constraint they can disagree about it:
        #
        #   MEASURED before adding it. A row with `revoked_on` set and
        #   `revoked_at` NULL made the resolver treat the episode as revoked
        #   (`declination_covering` stops at `revoked_on`) while
        #   `revoked_at IS NULL` — the partial unique index below, and the whole
        #   "is this declined now" predicate — still counted it live. Two
        #   derivations of one fact, in the table whose own design notes argue
        #   against them.
        #
        # Cheaper as a constraint than as a convention: the writer sets both, and
        # nothing has to remember that it must.
        sa.CheckConstraint(
            "(revoked_on IS NULL) = (revoked_at IS NULL)",
            name="ck_completeness_declination_revocation_coherent",
        ),
    )
    # ⚠️ AT MOST ONE LIVE EPISODE PER OBLIGATION, ENFORCED RATHER THAN INTENDED.
    # Partial-unique on the un-revoked rows is what makes `revoked_at IS NULL` a
    # PREDICATE instead of a query that could return two answers — the whole
    # reason in-row revocation beat a second row. Same shape as
    # `ux_completeness_nil_claim` and `platform_themes`' unique-on-active.
    #
    # Historical episodes are unconstrained because they must be: declining,
    # resuming and declining again is three rows on one obligation, and that
    # history is the thing a delete would have erased.
    op.create_index(
        "ux_completeness_declination_live",
        "completeness_declinations",
        ["tenant_id", "expectation_key"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    # The resolver's read is "every episode for this tenant", once per review.
    op.create_index(
        "ix_completeness_declination_tenant_key",
        "completeness_declinations",
        ["tenant_id", "expectation_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_completeness_declination_tenant_key",
        table_name="completeness_declinations",
    )
    op.drop_index(
        "ux_completeness_declination_live",
        table_name="completeness_declinations",
    )
    op.drop_table("completeness_declinations")
