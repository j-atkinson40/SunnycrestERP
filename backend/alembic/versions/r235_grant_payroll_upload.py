"""Grant `payroll.upload` to every existing `payroll` role.

### Why a migration and not just the default list

`role_service.seed_default_roles` SKIPS a role that already exists, so adding
`payroll.upload` to `PAYROLL_DEFAULT_PERMISSIONS` reaches NEW tenants only.
Every payroll role already in a database would keep the old two keys and Susan
would still be refused — the exact shape r222 documents for `payroll.view`.

### What changed, and why the earlier ruling no longer holds

Until 2026-11-13 the uploads were admin-only, ruled so on 2026-11-03 with an
explicit premise:

    "Loading hours is the act that brings pay data into existence, and the
     payroll reviewer never needs to do it: in the finished shape it is the
     background payroll job running under its own system actor."

The premise was that Opas would pull the hours. The Monday pull is DESIGNED and
NOT BUILT (docs/designs/payroll-monday-pull.md), and until it exists Susan runs
her own week from uploads — which is the job she was given.

⚠️ **THE "BRINGS PAY DATA INTO EXISTENCE" GATE HAS NOT BEEN GIVEN AWAY. IT
MOVED TO THE CONTROL THAT ACTUALLY IS ONE.** The payroll DATA SWITCH stays
admin-only: it is tenant-wide, off by default, and while it is off NO upload
works for anybody, admin included. Uploading a week's hours against a tenant
whose switch is already on is routine work, not a change of regime. Susan pulls
the Check Register from Payentry today.

⚠️ **`accountant` IS DELIBERATELY NOT GRANTED.** r222 exists to PRESERVE the
access the old slug gate gave that role, and that gate never reached the
uploads — they were admin-only before this. Granting upload here would WIDEN
the accountant rather than preserve it, which is precisely the mistake r222's
own comment records for the `accounting` alias.

⚠️ **`admin` IS DELIBERATELY NOT TOUCHED.** `get_user_permissions` returns
every catalogue key for the system admin role, so admin acquires
`payroll.upload` the moment the key exists. Granting it explicitly would add
rows that change nothing and make a wildcard look enumerated.

Idempotent: inserts only where the row is absent.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r235_grant_payroll_upload"
down_revision = "r234_payroll_employee_status"
branch_labels = None
depends_on = None

KEY = "payroll.upload"

#: The one slug. NOT `accountant`, NOT `accounting`, NOT `admin` — see above.
GRANTED_SLUG = "payroll"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_key)
            SELECT gen_random_uuid()::text, r.id, :key
            FROM roles r
            WHERE r.slug = :slug
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_key = :key
              )
            """
        ),
        {"key": KEY, "slug": GRANTED_SLUG},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_key = :key
              AND role_id IN (SELECT id FROM roles WHERE slug = :slug)
            """
        ),
        {"key": KEY, "slug": GRANTED_SLUG},
    )
