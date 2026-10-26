"""Opas asks "why?" — the reason, its scope, and the rulebook it drafts into.

James's dispatch of 2026-10-26, "Opas asks why?", first slice, capture only. Migrations
authorised explicitly: "James's go, expand-only, reversible."

EXPAND-ONLY. Five nullable columns, one new table, no data written, nothing dropped or
renamed, nothing backfilled. `downgrade()` removes exactly what `upgrade()` added and
owns every one of those objects, so the round trip is real rather than nominal — the
caution CLAUDE.md records is about a downgrade touching rows an EARLIER migration wrote,
and this one wrote none.

⚠️ EVERY COLUMN IS NULLABLE WITH NO SERVER DEFAULT, which is CLAUDE.md §5 and not a
style choice. A non-null `reason_scope` would assert something about every
`opas_decisions` row that predates today — 'skipped', say, which reads like data and
would be a claim that somebody was asked and declined. Nobody was asked. NULL is "not
established", and that is the true thing about those rows.

⚠️ AND `is_active` ON `opas_rules` IS THE ONE NOT-NULL BOOLEAN, which is safe for the
opposite reason: the table is NEW and empty, so a default cannot mis-describe a row that
already exists. There are none. The §5 trap needs a populated table.

WHY A SNAPSHOT COLUMN EXISTS AT ALL (`capture_sessions.opas_proposed`). The dispatch
asks to compare "each field's value as Opas set it … with the approved value". Two of
the three ways a person changes a field are recoverable exactly without storing
anything — a switch taken and a pick answered both land in `resolutions`, so
re-extracting WITHOUT resolutions gives Opas's own reading. The third is not: the bar is
the only input, so changing the vault means RETYPING, and once the text says Continental
nothing anywhere remembers that Opas had read Monticello. That is the case James's own
walk exercises, so the pre-edit reading has to be kept.

⚠️ `capture_sessions.decision_id` EXISTS BECAUSE THE ID WAS BEING THROWN AWAY.
`decision_log.record_capture_open` returns the row it wrote and the capture route
discarded the return value, so a session had no way back to its own decision row — and
the dispatch says "the decision-log row for that capture gets the reason". Nullable
because sessions that predate today have no such link, and because the link is written
on the first text a session receives, which a prefill-only session has not had yet.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r217_opas_why_and_rulebook"
down_revision = "r216_capture_prefill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── what Opas proposed, so a change can be told from a first fill ──────────
    op.add_column(
        "capture_sessions",
        sa.Column("opas_proposed", JSONB(), nullable=True),
    )
    op.add_column(
        "capture_sessions",
        sa.Column("decision_id", sa.String(36), nullable=True),
    )
    # ⚠️ NO FOREIGN KEY TO `opas_decisions`, DELIBERATELY, AND CLAUDE.md §5 IS WHY.
    # `decision_log` swallows its own failures by design — a log that breaks the thing it
    # observes is worse than no log — so this id is best-effort. An FK would turn a
    # failed log write into a failed CAPTURE, which inverts that. ⚠️ AND A SECOND FK
    # over `opas_decisions` would carry its own ON DELETE: the default is NO ACTION,
    # which REVOKES a cascade an existing key grants. Neither risk buys anything here.

    # ── the reason, its scope, and the change it was about ────────────────────
    op.add_column("opas_decisions", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column(
        "opas_decisions", sa.Column("reason_scope", sa.String(8), nullable=True)
    )
    op.add_column(
        "opas_decisions", sa.Column("changed_field", sa.String(40), nullable=True)
    )
    op.add_column("opas_decisions", sa.Column("changed_from", sa.Text(), nullable=True))
    op.add_column("opas_decisions", sa.Column("changed_to", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_opas_decisions_reason_scope",
        "opas_decisions",
        "reason_scope IS NULL OR reason_scope IN ('today', 'always', 'skipped')",
    )
    # ⚠️ A REASON WITHOUT A SCOPE IS A HALF-ANSWERED QUESTION AND MUST NOT EXIST. The
    # flow is reason-then-scope, so a row holding one without the other means the second
    # step was lost — which would otherwise look like a deliberate record.
    #
    # ⚠️ 'skipped' IS THE EXCEPTION AND IT IS THE REASON THIS IS ONE-DIRECTIONAL: a skip
    # has a scope and no reason, by design. So scope-without-reason is permitted and
    # reason-without-scope is not.
    op.create_check_constraint(
        "ck_opas_decisions_reason_has_scope",
        "opas_decisions",
        "reason IS NULL OR reason_scope IS NOT NULL",
    )

    # ── the rulebook ──────────────────────────────────────────────────────────
    op.create_table(
        "opas_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # ⚠️ ONE PLAIN SENTENCE. "the model turns the reason plus the change into one
        # plain sentence" (dispatch). Text rather than a structured rule because nothing
        # EXECUTES these yet — slice 1 records and shows. A schema for a rule engine
        # that does not exist would be a guess about the engine.
        sa.Column("text", sa.Text(), nullable=False),
        # ⚠️ NULLABLE AND NO CASCADE: the rule outlives the decision it came from. A
        # rule whose provenance row was purged is still a rule the office wrote; losing
        # it because the log was tidied would be the log deciding what the rulebook says.
        sa.Column(
            "source_decision_id",
            sa.String(36),
            sa.ForeignKey("opas_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Safe as NOT NULL: the table is new and holds no rows to mis-describe.
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    # ⚠️ PARTIAL, ON THE ONLY QUESTION ANYONE ASKS OF THIS TABLE: which rules are in
    # force for this tenant. An index over inactive rows would serve the rulebook pane's
    # history, which slice 1 does not show.
    op.create_index(
        "ix_opas_rules_active",
        "opas_rules",
        ["company_id", "created_at"],
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("ix_opas_rules_active", table_name="opas_rules")
    op.drop_table("opas_rules")
    op.drop_constraint(
        "ck_opas_decisions_reason_has_scope", "opas_decisions", type_="check"
    )
    op.drop_constraint(
        "ck_opas_decisions_reason_scope", "opas_decisions", type_="check"
    )
    for column in ("changed_to", "changed_from", "changed_field", "reason_scope", "reason"):
        op.drop_column("opas_decisions", column)
    op.drop_column("capture_sessions", "decision_id")
    op.drop_column("capture_sessions", "opas_proposed")
