"""The remaining 20 tenant-scoped columns get a companies FK, ON DELETE CASCADE

Revision ID: r184_tenant_column_company_fks
Revises: r183_tenant_health_scores_company_fk
Create Date: 2026-09-14

⚠️ PREREQUISITE: `python -m scripts.purge_test_litter --apply` if the suite has
run since the last purge. `ADD CONSTRAINT` fails on a single violating row, and
it fails loudly — no pre-delete here and no exception handler, same as r183.
Measured immediately before authoring: 0 violations across all 20.

──────────────────────────────────────────────────────────────────────────
⚠️ WHY TWENTY AT ONCE RATHER THAN TWENTY COMMITS

Because a PARTIAL application displaces the problem instead of fixing it, and
that was measured rather than predicted.

r183 constrained `tenant_health_scores`. The follow-up fix to `test_responders`
gave two tests a real company and deleted it in teardown — and produced **+2
orphaned `platform_incidents` rows per run**, because that table had no
constraint. It then broke its own test: enough accumulated `infra` incidents
make the responder escalate rather than resolve.

An orphan can only land in a table with NO constraint. Constrain the whole set
and there is nowhere left to displace to. Constrain half and the litter simply
moves next door.

⚠️ AND THE PRODUCER NEEDS NO FIXING. Deleting a company is ordinary test
behaviour — 98 test files do it, 51 through the shared helper and 42 hand-rolled.
It produces litter ONLY where a constraint is missing. `purge_companies_by_slug`
covers 72 tables and exactly ONE of these 20; extending it would work until the
next table, which is what its own docstring has been saying for months.

CASCADE FOR ALL TWENTY

Ruled 2026-09-14. These are tenant-scoped rows whose meaning ends with the
tenant. 19 of the 20 are LEAVES — nothing references them, verified from the FK
catalogue rather than assumed.

⚠️ The catalogue majority is 83% NO ACTION and is the wrong guide here, for the
same reason as r183: NO ACTION means the class cannot recur SILENTLY, CASCADE
means it cannot recur. NO ACTION would also leave every future company delete
either raising or orphaning, which is the mechanism that produced 60,469 orphans
in the one table that had accumulated any.

⚠️ TWO REFERRERS MOVE WITH `platform_incidents`, THE ONLY NON-LEAF

`platform_incidents.tenant_id` cannot take CASCADE while its own children are
NO ACTION — the cascade would reach them and raise, leaving the class open at
its one hard table. Both are checked rather than assumed:

  platform_notifications.incident_id  — 202 rows, ALL with an incident_id. There
      are no standalone notifications, so one outliving its incident is a
      notification about nothing.
  platform_incidents.previous_incident_id — a self-reference marking recurrence.
      1 of 517 rows uses it, and the linked incident belongs to the same tenant,
      so it would be deleted by the tenant cascade regardless.

Neither holds anything worth surviving a tenant delete. If that ever changes,
the right move is SET NULL on that referrer, not NO ACTION.

⚠️ WHAT THE DOWNGRADE COSTS. Dropping constraints is cheap. It does NOT restore
rows a cascade removed, and this migration cannot know which they were.
Downgrade returns the schema, never the data. It also restores the two referrers
to NO ACTION, which restores the raise.

THE MODEL LAYER IS NOT FIXED HERE. Zero of the 20 declared a ForeignKey in the
ORM — that is the convention that produced them, and a migration alone leaves it
intact. `tests/test_tenant_column_fk_guard.py` is what stops table 21: it derives
every tenant-scoped column from information_schema at run time and fails naming
any without a constraint.
"""
from alembic import op


revision = "r184_tenant_column_company_fks"
down_revision = "r183_tenant_health_scores_company_fk"
branch_labels = None
depends_on = None


#: (table, column). Derived 2026-09-14 from information_schema, not hand-listed:
#: every tenant-scoped column with no FK to companies.id at that moment.
TARGETS: list[tuple[str, str]] = [
    ("activity_log", "tenant_id"),
    ("agent_anomalies", "tenant_id"),
    ("ai_agent_runs", "tenant_id"),
    ("ai_company_insights", "tenant_id"),
    ("ai_name_suggestions", "tenant_id"),
    ("ai_pattern_alerts", "tenant_id"),
    ("ai_rescue_drafts", "tenant_id"),
    ("ai_upsell_insights", "tenant_id"),
    ("cash_flow_forecasts", "tenant_id"),
    ("company_migration_reviews", "tenant_id"),
    ("duplicate_reviews", "tenant_id"),
    ("extension_widgets", "tenant_id"),
    ("legacy_proof_photos", "company_id"),
    ("legacy_proof_versions", "company_id"),
    ("order_personalization_photos", "company_id"),
    ("platform_incidents", "tenant_id"),
    ("platform_notifications", "tenant_id"),
    ("ponder_engagement", "company_id"),
    ("user_ai_preferences", "tenant_id"),
    ("user_widget_layouts", "tenant_id"),
]

#: (constraint, table, column) — NO ACTION children of platform_incidents that
#: must become CASCADE, or the cascade onto incidents raises.
REFERRERS: list[tuple[str, str, str]] = [
    ("platform_notifications_incident_id_fkey", "platform_notifications", "incident_id"),
    ("platform_incidents_previous_incident_id_fkey", "platform_incidents", "previous_incident_id"),
]


def _name(table: str, column: str) -> str:
    return f"fk_{table}_{column}_companies"


def upgrade() -> None:
    # Referrers first: platform_incidents cannot take CASCADE while its own
    # children would raise under it.
    for constraint, table, column in REFERRERS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="platform_incidents",
            local_cols=[column],
            remote_cols=["id"],
            ondelete="CASCADE",
        )

    for table, column in TARGETS:
        op.create_foreign_key(
            _name(table, column),
            source_table=table,
            referent_table="companies",
            local_cols=[column],
            remote_cols=["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table, column in TARGETS:
        op.drop_constraint(_name(table, column), table, type_="foreignkey")

    # Restore the referrers to NO ACTION — which restores the raise.
    for constraint, table, column in REFERRERS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            source_table=table,
            referent_table="platform_incidents",
            local_cols=[column],
            remote_cols=["id"],
        )
