"""Hopkins pilot config repair — repoint legacy /cases pins + drop the
CI-residue funeral_home theme rows (fh-case-table-split fix, 2026-07).

Two one-time data repairs (the source-side seed/registry/nav/executor
fixes ship in the same arc so this never regenerates):

1. **Space pins.** Every user whose seeded spaces carry a legacy
   `/cases` nav pin or `default_home_route` is repointed to the
   canonical FH-1 list `/fh/cases`. The `/cases/new` pin is DROPPED —
   there is no canonical standalone create route (create lives on the
   `/fh/cases` list; NL creation via the command bar is the primary
   path). General by design: any FH tenant's legacy pins are fixed, not
   just Hopkins. JSONB surgery is a Python dict round-trip through the
   bound connection — clean + readable.

2. **funeral_home theme residue.** `07-commit-overrides-persist.spec.ts`
   wrote `funeral_home` vertical_default on every push (write-side
   versioning accreted 254 rows on staging; active row carried a blue
   accent + a recursively self-nested token_overrides from the
   pre-R-1.6.15 double-wrap bug). The spec is rescoped to testco in the
   same arc so this stops regenerating. Here we deactivate ALL
   `funeral_home` vertical_default rows so the vertical inherits the
   calibrated PLATFORM tokens (ink light accent) — the correct end
   state is NO funeral_home vertical row. Scoped strictly to
   `vertical='funeral_home'`; no other vertical is touched (and none
   has a vertical_default theme row anyway).

Environment safety: prod has no FH tenant, so both repairs no-op there.
Idempotent: re-running finds no `/cases` pins and no active
funeral_home rows. Downgrade is intentionally a no-op — resurrecting
the legacy pins / blue residue is never desirable.

Revision ID: r145_hopkins_pilot_config_repair
Revises: r144_case_deceased_trigram_index
"""

from __future__ import annotations

import json

from alembic import op
from sqlalchemy import text


revision = "r145_hopkins_pilot_config_repair"
down_revision = "r144_case_deceased_trigram_index"
branch_labels = None
depends_on = None


_LEGACY_LIST = "/cases"
_LEGACY_NEW = "/cases/new"
_CANONICAL_LIST = "/fh/cases"


def _repoint_pins() -> int:
    """Rewrite legacy /cases pins + default_home_route in every user's
    spaces JSONB. Returns the number of users mutated."""
    bind = op.get_bind()
    rows = bind.execute(
        text("SELECT id, preferences FROM users WHERE preferences IS NOT NULL")
    ).fetchall()

    mutated = 0
    for user_id, prefs in rows:
        if isinstance(prefs, str):
            prefs = json.loads(prefs)
        if not isinstance(prefs, dict):
            continue
        spaces = prefs.get("spaces")
        if not isinstance(spaces, list):
            continue

        changed = False
        for sp in spaces:
            if not isinstance(sp, dict):
                continue
            if sp.get("default_home_route") == _LEGACY_LIST:
                sp["default_home_route"] = _CANONICAL_LIST
                changed = True
            pins = sp.get("pins")
            if not isinstance(pins, list):
                continue
            new_pins = []
            for pin in pins:
                if not isinstance(pin, dict):
                    new_pins.append(pin)
                    continue
                tid = pin.get("target_id")
                if tid == _LEGACY_NEW:
                    changed = True  # drop the New-Case pin
                    continue
                if tid == _LEGACY_LIST:
                    pin["target_id"] = _CANONICAL_LIST
                    changed = True
                new_pins.append(pin)
            if len(new_pins) != len(pins):
                sp["pins"] = new_pins

        if changed:
            bind.execute(
                text("UPDATE users SET preferences = :p WHERE id = :i"),
                {"p": json.dumps(prefs), "i": user_id},
            )
            mutated += 1
    return mutated


def _deactivate_fh_theme_residue() -> int:
    """Deactivate every active funeral_home vertical_default theme row
    so the vertical inherits platform tokens. Returns rows affected."""
    bind = op.get_bind()
    result = bind.execute(
        text(
            "UPDATE platform_themes SET is_active = FALSE "
            "WHERE scope = 'vertical_default' "
            "AND vertical = 'funeral_home' AND is_active = TRUE"
        )
    )
    return result.rowcount or 0


def upgrade() -> None:
    users = _repoint_pins()
    themes = _deactivate_fh_theme_residue()
    print(
        f"r145: repointed /cases pins for {users} user(s); "
        f"deactivated {themes} funeral_home vertical_default theme row(s)."
    )


def downgrade() -> None:
    # Intentional no-op: the legacy /cases pins and the blue theme
    # residue are exactly what this migration exists to remove;
    # resurrecting them on downgrade is never desirable. The source-
    # side seed/nav/executor fixes are the durable owners of the new
    # state.
    pass
