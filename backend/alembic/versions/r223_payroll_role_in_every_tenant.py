"""The Payroll role exists ready-made in every company, the way Admin does.

James's ruling, 2026-11-03: nobody should ever have to build this role by hand.

### Why this migration exists at all

`seed_default_roles` creates the system roles, and it runs at company
REGISTRATION (`auth_service.py:40`) or from a seed script — never retroactively.
So adding `payroll` to `_SYSTEM_ROLES` reaches new companies only, and production
had **zero** roles with that slug after r222 deployed.

⚠️ **AND THE HAND-MADE ALTERNATIVE WAS THE DANGEROUS ONE.** `RoleCreate` and
`RoleUpdate` carried no `limited_to_areas` field, so a "Payroll" role built in the
admin screen would have had `limited_to_areas = NULL` — NOT area-limited — and its
holder would have reached every one of the 1063 endpoints with no per-user gate.
It would have looked correct in the UI. That is why this ships as a migration
rather than as an instruction to an admin. (The schema gap is closed separately,
in the same arc, so areas can also be ADMINISTERED rather than only seeded.)

### What it does, and what it refuses to do

For each company with no role of slug `payroll`: create it, with
`payroll.view` + `payroll.approve` and `limited_to_areas = ["payroll"]`.

⚠️ **AN EXISTING `payroll` ROLE IS NEVER MODIFIED, EVEN IF IT DIVERGES.** If one
exists with different areas or different permissions, this migration REPORTS it
and leaves it alone. A tenant may have made deliberate local changes, and a
migration that "corrects" them is a migration that silently overwrites somebody's
decision. The report goes to the deploy log so divergence is visible and can be
settled per tenant by a person.

### Why the literals are inlined

`PAYROLL_DEFAULT_PERMISSIONS` and `KNOWN_AREAS` live in `app/core/`, and importing
them here would make this migration's behaviour change whenever that code changes.
A migration is a historical record of what was done on a date; it must keep doing
the same thing when re-run against a fresh database years later. So the two keys
and the one area are written out literally, and will not track the module.

### On DELETE

No new constraint. The rows created are ordinary `roles` and `role_permissions`,
already covered by `role_permissions.role_id` → `roles.id` ON DELETE CASCADE.
"""
from alembic import op
import sqlalchemy as sa

revision = "r223_payroll_role_in_every_tenant"
down_revision = "r222_grant_payroll_to_accountant_roles"
branch_labels = None
depends_on = None

SLUG = "payroll"
NAME = "Payroll"
DESCRIPTION = "Weekly payroll dues review only. Sees nothing else."
PERMISSIONS = ("payroll.view", "payroll.approve")
AREAS = '["payroll"]'


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Report divergence, change nothing ──────────────────────────────────
    existing = conn.execute(
        sa.text(
            """
            SELECT r.id, c.slug AS tenant, r.limited_to_areas::text AS areas,
                   coalesce(
                       (SELECT string_agg(rp.permission_key, ',' ORDER BY rp.permission_key)
                        FROM role_permissions rp WHERE rp.role_id = r.id),
                       ''
                   ) AS perms
            FROM roles r
            JOIN companies c ON c.id = r.company_id
            WHERE r.slug = :slug
            """
        ),
        {"slug": SLUG},
    ).fetchall()

    expected_perms = ",".join(sorted(PERMISSIONS))
    # ⚠️ `'null'` IS TREATED AS ABSENT. On any database seeded before the
    # `none_as_null=True` model fix, a role's `limited_to_areas` holds the JSON
    # value `null` rather than SQL NULL, and `::text` renders it `'null'`.
    # Without this, every such role would be reported divergent — a true
    # statement about the bytes and a false one about intent.
    def _areas_text(value: str | None) -> str:
        return "" if value in (None, "null") else value

    divergent = [
        row for row in existing
        if _areas_text(row.areas) != AREAS or row.perms != expected_perms
    ]
    print(f"[r223] existing '{SLUG}' roles found: {len(existing)}")
    if divergent:
        print(f"[r223] ⚠️ {len(divergent)} existing '{SLUG}' role(s) DIVERGE and were "
              f"NOT modified — settle these per tenant by hand:")
        for row in divergent:
            print(f"[r223]    tenant={row.tenant} role_id={row.id} "
                  f"areas={row.areas!r} perms={row.perms!r} "
                  f"(expected areas={AREAS!r} perms={expected_perms!r})")

    # ── 2. Create it where it is missing ──────────────────────────────────────
    # gen_random_uuid()::text matches the String(36) id convention and is how
    # r222 generated ids. pgcrypto/pg13+ provides it in core.
    result = conn.execute(
        sa.text(
            """
            INSERT INTO roles (id, company_id, name, slug, description,
                               is_system, is_active, created_at, updated_at,
                               limited_to_areas)
            SELECT gen_random_uuid()::text, c.id, :name, :slug, :description,
                   true, true, now(), now(), CAST(:areas AS jsonb)
            FROM companies c
            WHERE NOT EXISTS (
                SELECT 1 FROM roles r WHERE r.company_id = c.id AND r.slug = :slug
            )
            RETURNING id
            """
        ),
        {"name": NAME, "slug": SLUG, "description": DESCRIPTION, "areas": AREAS},
    )
    created_ids = [r[0] for r in result.fetchall()]
    print(f"[r223] created {len(created_ids)} '{SLUG}' role(s)")

    if created_ids:
        for key in PERMISSIONS:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (id, role_id, permission_key)
                    SELECT gen_random_uuid()::text, r.id, :key
                    FROM roles r
                    WHERE r.id = ANY(:ids)
                      AND NOT EXISTS (
                          SELECT 1 FROM role_permissions rp
                          WHERE rp.role_id = r.id AND rp.permission_key = :key
                      )
                    """
                ),
                {"key": key, "ids": created_ids},
            )
        print(f"[r223] granted {len(PERMISSIONS)} permission(s) to each new role")


def downgrade() -> None:
    # ⚠️ REMOVES ONLY WHAT THIS MIGRATION'S SHAPE DESCRIBES, and only roles with
    # no users on them. A `payroll` role someone has already been assigned to is
    # left in place: dropping it would strip that user's access as a side effect
    # of a schema rollback, and `users.role_id` has no ON DELETE to absorb it.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT r.id FROM roles r
                WHERE r.slug = :slug
                  AND r.limited_to_areas::text = :areas
                  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.role_id = r.id)
            )
            """
        ),
        {"slug": SLUG, "areas": AREAS},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM roles
            WHERE slug = :slug
              AND limited_to_areas::text = :areas
              AND NOT EXISTS (SELECT 1 FROM users u WHERE u.role_id = roles.id)
            """
        ),
        {"slug": SLUG, "areas": AREAS},
    )
