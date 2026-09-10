"""Retire the `pulse-widget` ComponentKind.

Revision ID: r182_retire_pulse_widget_kind
Revises: r181_note_settled_records
Create Date: 2026-09-10

Pulse is retired. `pulse-widget` was declared in the ComponentKind enum and
carried by two CHECK constraints, and NOTHING WAS EVER REGISTERED AS ONE.

⚠️ NO DATA MIGRATION, AND THAT IS MEASURED RATHER THAN ASSUMED.

    component_configurations       WHERE component_kind  = 'pulse-widget'  -> 0
    component_class_configurations WHERE component_class = 'pulse-widget'  -> 0

Both read against PRODUCTION 2026-09-10 through a connection-level
`default_transaction_read_only=on` guard.

The dev database says the same thing and says it worthlessly: both tables are
ENTIRELY EMPTY there, so a filtered count of zero is trivially true. Production
is the informative measurement — `component_configurations` IS populated, and
enumerating its distinct kinds returns `['widget']` alone. That is an absence
established by ENUMERATION rather than by a filtered count that cannot
distinguish "none of these" from "none of anything".

⚠️ ON DELETE — CHECKED, PER THE r177 PRECEDENT.

r177 is the worked example of a constraint revoking a behaviour: a second FK
over a parent an existing key already cascaded from omitted `ondelete`, took
the `NO ACTION` default, and turned deletes that used to cascade into raises —
surfacing as 64 teardown errors in unrelated suites.

That shape cannot occur here, established rather than asserted:

  · Both constraints altered are CHECK. A CHECK has no delete semantics to
    revoke — it constrains rows, not the graph.
  · No FK is added, dropped or altered by this migration. The FKs on these
    tables are untouched: component_configurations.tenant_id -> companies
    ON DELETE CASCADE, and created_by/updated_by -> users ON DELETE SET NULL
    on both tables.
  · NO INBOUND FK POINTS AT EITHER TABLE, so nothing cascades from them and
    nothing loses a cascade when their CHECKs change.

Enumerated from pg_constraint against production, not read off the models.

⚠️ RECREATING A CHECK VALIDATES EVERY EXISTING ROW. If a `pulse-widget` row
ever appears, `upgrade()` fails loudly at that statement rather than dropping
the value silently. The explicit pre-check below exists only to make the
failure legible; the constraint itself is the real guard.
"""
from alembic import op
import sqlalchemy as sa

revision = "r182_retire_pulse_widget_kind"
down_revision = "r181_note_settled_records"
branch_labels = None
depends_on = None

#: Post-retirement vocabulary — 11 values, `pulse-widget` absent.
_KINDS = (
    "widget", "focus", "focus-template", "document-block",
    "workflow-node", "layout", "composite",
    "entity-card", "button", "form-input", "surface-card",
)
#: What the constraints carried before this migration: the same 11 plus one.
_KINDS_WITH_PULSE = _KINDS[:4] + ("pulse-widget",) + _KINDS[4:]

_TARGETS = (
    ("component_configurations", "component_kind", "ck_component_configs_kind"),
    ("component_class_configurations", "component_class",
     "ck_component_class_configs_class"),
)


def _in_list(values: tuple[str, ...], col: str) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _rebuild(values: tuple[str, ...]) -> None:
    for table, col, name in _TARGETS:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, _in_list(values, col))


def upgrade() -> None:
    conn = op.get_bind()
    for table, col, _ in _TARGETS:
        n = conn.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {col} = 'pulse-widget'")
        ).scalar()
        if n:
            raise RuntimeError(
                f"{table} holds {n} row(s) with {col}='pulse-widget'. This "
                "migration was authored against a measured zero in production. "
                "Reclassify those rows before retiring the kind — do not widen "
                "the constraint back to accommodate them."
            )
    _rebuild(_KINDS)


def downgrade() -> None:
    # Restores `pulse-widget` as an ACCEPTED value. It does not restore Pulse,
    # and no row will use it — the kind had zero registrations for its whole
    # life. This exists so the migration is reversible, not because reversing
    # it recovers anything.
    _rebuild(_KINDS_WITH_PULSE)
