"""Sunnycrest's timezone is America/New_York, not UTC.

James's go, 2026-10-16, step 2 of the confirm arc.

⚠️ WHY A MIGRATION RATHER THAN A ONE-OFF SCRIPT. `companies.timezone` is how eight
separate readers work out what "today" is for a tenant (enumerated below). Step 2 makes
the end-of-day batch one of them, and "the night of the service date" has to mean the
night in New York. A one-off script would fix production and leave dev, CI and every
future restore on the wrong value — the batch's own tests would then be asserting against
a timezone no real tenant has. A migration applies once, everywhere, and is auditable.

⚠️ THE COLUMN'S DEFAULT IS `"UTC"` (`app/models/company.py:39-41`), which is why every
tenant on production carries it. It is a default nobody chose, not a decision — the same
shape as `delivery_settings.modified_at = NULL`. Sunnycrest operates out of Skaneateles,
New York.

⚠️ THE OTHER THREE TENANTS ARE LEFT ALONE, BY DISPATCH. `testco`, `hopkins-fh` and
`st-marys` are synthetic dev/demo tenants (CLAUDE.md §7, canonical development tenants);
their timezone is not a fact about anywhere. Changing them would move the goalposts under
every test that was written against them.

⚠️ GUARDED ON THE OLD VALUE, so a re-run cannot clobber a later admin change. If somebody
sets Sunnycrest to something else through the UI, this migration has already run and will
not run again — but the guard means that even a hand-replay is a no-op rather than a
revert. Same pattern as `r212`.

WHAT CHANGES FOR SUNNYCREST (every reader of `companies.timezone`, enumerated 2026-10-16):

    reader                                             fallback      effect of the flip
    -------------------------------------------------- ------------- --------------------
    delivery_schedule_service._get_tenant_timezone     New_York      auto-finalize cutoff
      -> auto_finalize_pending_schedules:476                         moves 9am ET -> 1pm ET
      -> api/routes/dispatch.py:793                                  (its declared intent)
    order_list/service.today_for:60                    ⚠️ UTC        "today" becomes the
                                                                     Eastern date
    widgets/today_widget_service                       New_York      Today widget window
    note/settling_sweep._tz_for:65                     New_York      note settles midnight
    note/settling.py:115                               New_York      Eastern, not 8pm ET
    briefings/scheduler_integration._resolve_tz:151    New_York      a 7am briefing stops
                                                                     arriving at 3am ET
    workflow_scheduler._resolve_tenant_tz:68           New_York      tenant workflows fire
      -> check_time_based_workflows:397,428                          at their Eastern time
    maps_of_content/schedule_sweep:157                 New_York      MoC schedules (dry-run)

    NOT a reader: `agents.py:543,559` writes `AgentSchedule.timezone`, a different column.

⚠️ THE FALLBACKS DISAGREE WITH EACH OTHER AND WITH THE COLUMN DEFAULT. Seven readers fall
back to `America/New_York`; `order_list/service.today_for` falls back to `UTC`; the column
defaults to `UTC`. So today Sunnycrest gets UTC everywhere because the column is set, and
a tenant with a NULL timezone would get New_York from seven readers and UTC from one. That
inconsistency is NOT fixed here — it is recorded in
`docs/investigations/2026-10-16-scheduler-timezone.md` so the next person does not have to
re-derive it. Flipping the value makes it moot for Sunnycrest.

⚠️ AND ONE EFFECT IS A LATER TIME, NOT AN EARLIER ONE. `auto_finalize_pending_schedules`
currently fires for Sunnycrest on the first tick at or after 13:00 UTC — 9 AM Eastern.
After this, tomorrow's draft schedule auto-finalizes at 1 PM Eastern, four hours later in
absolute terms. That is what `AUTO_FINALIZE_HOUR = 13  # 1 pm tenant-local` has always
said it meant; it has simply never meant it for a tenant whose timezone was UTC.

Revision ID: r213_sunnycrest_timezone
Revises: r212_sunnycrest_price_list_alignment
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = "r213_sunnycrest_timezone"
down_revision = "r212_sunnycrest_price_list_alignment"
branch_labels = None
depends_on = None

SLUG = "sunnycrest"
BEFORE = "UTC"
AFTER = "America/New_York"


def _set(conn, *, frm: str, to: str) -> int:
    """Flip the timezone, guarded on the current value. Returns rows affected.

    ⚠️ EXTRACTED SO IT IS TESTABLE WITHOUT AN ALEMBIC CONTEXT, the r212 pattern.
    """
    result = conn.execute(
        sa.text(
            "UPDATE companies SET timezone = :to "
            "WHERE slug = :slug AND (timezone = :frm OR timezone IS NULL)"
        ),
        {"to": to, "frm": frm, "slug": SLUG},
    )
    return result.rowcount


def upgrade() -> None:
    conn = op.get_bind()
    # ⚠️ NOT ASSERTED TO BE 1. A database without the sunnycrest tenant — CI, a fresh
    # local dev box before `seed_dev.sh`, any test database — legitimately affects 0 rows,
    # and raising there would make the migration chain unrunnable everywhere except
    # production. `tests/test_r213_sunnycrest_timezone.py` is where the 1-row case is
    # proven, against a tenant it seeds itself.
    n = _set(conn, frm=BEFORE, to=AFTER)
    print(f"[r213] sunnycrest timezone {BEFORE} -> {AFTER}: {n} row(s)")


def downgrade() -> None:
    conn = op.get_bind()
    n = _set(conn, frm=AFTER, to=BEFORE)
    print(f"[r213] sunnycrest timezone {AFTER} -> {BEFORE}: {n} row(s)")
