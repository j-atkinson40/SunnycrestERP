"""Preserve the payroll access the `accountant` role already had.

### Why this is a MEASURED backfill and not an invented one

Until 2026-11-03 the seven payroll report endpoints gated on ROLE SLUG:

    ACCOUNTING_ROLES = ("admin", "accountant")      # completeness.py:113

so a user on a role with slug `accountant` reached every one of them. Swapping
those gates to `require_permission("payroll.view")` moves the question from the
slug to the permission table — and `role_service.seed_default_roles` SKIPS a role
that already exists (role_service.py:144-156), so adding `payroll.view` to
`ACCOUNTANT_DEFAULT_PERMISSIONS` reaches new tenants only.

Without this migration, every existing accountant at every tenant silently loses
payroll access on deploy. James's ruling for this slice is explicit that existing
admin and accountant behaviour is unchanged, so the grant is required.

⚠️ **THIS IS THE ONE CASE WHERE WRITING A VALUE ONTO EXISTING ROWS IS NOT A
CLAIM NOBODY MEASURED** (CLAUDE.md §5). The usual hazard is a plausible default
asserting something about rows that were never examined. Here the assertion is
"this role could reach the payroll endpoints yesterday", which is not a guess: it
is what the slug gate did, for exactly the slug being matched. The migration
preserves a measured fact rather than inventing one.

⚠️ **`admin` IS DELIBERATELY NOT TOUCHED.** `get_user_permissions` returns
`set(get_all_permission_keys())` for the system admin role
(permission_service.py:43), so admin acquires `payroll.view` the moment the key
exists in the catalogue. Granting it explicitly would add 2147 rows that change
nothing and would make the admin role look like it holds enumerated permissions
when it holds a wildcard.

⚠️ **`accounting` IS DELIBERATELY NOT TOUCHED EITHER, AND THE NEAR-MISS IS THE
POINT.** There are two adjacent slugs — 56 roles with slug `accounting` and 55
with `accountant` — and `ACCOUNTING_DEFAULT_PERMISSIONS` is a module-level ALIAS
of `ACCOUNTANT_DEFAULT_PERMISSIONS` (permissions.py:292), which makes them look
interchangeable. They are not, for this purpose: the old gate compared against
the literal string `"accountant"`, so a user on `accounting` was ALREADY refused.
Granting them payroll.view would not preserve behaviour, it would widen it to 56
roles that never had it.

Idempotent: inserts only where the row is absent.
"""
from alembic import op
import sqlalchemy as sa

revision = "r222_grant_payroll_to_accountant_roles"
down_revision = "r221_role_limited_to_areas"
branch_labels = None
depends_on = None

#: Exactly the slug the old gate matched. Not a prefix, not a LIKE.
PRESERVED_SLUG = "accountant"
KEYS = ("payroll.view", "payroll.approve")


def upgrade() -> None:
    conn = op.get_bind()
    for key in KEYS:
        conn.execute(
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
            {"key": key, "slug": PRESERVED_SLUG},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_key = ANY(:keys)
              AND role_id IN (SELECT id FROM roles WHERE slug = :slug)
            """
        ),
        {"keys": list(KEYS), "slug": PRESERVED_SLUG},
    )
