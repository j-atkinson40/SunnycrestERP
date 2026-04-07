"""Add ar.update_order permission to roles

Revision ID: z9h5i6j7k8l9
Revises: z9g4h5i6j7k8
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "z9h5i6j7k8l9"
down_revision = "z9g4h5i6j7k8"
branch_labels = None
depends_on = None

# Roles that should receive ar.update_order
# (matches the updated defaults in permissions.py)
ROLES_NEEDING_UPDATE_ORDER = [
    "office_staff",
    "accounting",
    "manager",
]

# Roles that need ar.view + ar.update_order (new AR access)
ROLES_NEEDING_AR_VIEW_AND_UPDATE = [
    "production",
    "driver",
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add ar.update_order to roles that already have ar.create_order
    for slug in ROLES_NEEDING_UPDATE_ORDER:
        rows = conn.execute(
            sa.text("""
                SELECT r.id FROM roles r
                WHERE r.slug = :slug AND r.is_system = true
                AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_key = 'ar.update_order'
                )
            """),
            {"slug": slug},
        ).fetchall()
        for (role_id,) in rows:
            conn.execute(
                sa.text("""
                    INSERT INTO role_permissions (id, role_id, permission_key)
                    VALUES (:id, :rid, 'ar.update_order')
                """),
                {"id": str(uuid.uuid4()), "rid": role_id},
            )
        if rows:
            print(f"  Added ar.update_order to {len(rows)} '{slug}' roles")

    # 2. Add ar.view + ar.update_order to production and driver roles
    for slug in ROLES_NEEDING_AR_VIEW_AND_UPDATE:
        for perm_key in ("ar.view", "ar.update_order"):
            rows = conn.execute(
                sa.text("""
                    SELECT r.id FROM roles r
                    WHERE r.slug = :slug AND r.is_system = true
                    AND NOT EXISTS (
                        SELECT 1 FROM role_permissions rp
                        WHERE rp.role_id = r.id AND rp.permission_key = :perm
                    )
                """),
                {"slug": slug, "perm": perm_key},
            ).fetchall()
            for (role_id,) in rows:
                conn.execute(
                    sa.text("""
                        INSERT INTO role_permissions (id, role_id, permission_key)
                        VALUES (:id, :rid, :perm)
                    """),
                    {"id": str(uuid.uuid4()), "rid": role_id, "perm": perm_key},
                )
            if rows:
                print(f"  Added {perm_key} to {len(rows)} '{slug}' roles")


def downgrade() -> None:
    conn = op.get_bind()
    # Remove the newly added permissions
    for slug in ROLES_NEEDING_UPDATE_ORDER + ROLES_NEEDING_AR_VIEW_AND_UPDATE:
        conn.execute(
            sa.text("""
                DELETE FROM role_permissions
                WHERE permission_key = 'ar.update_order'
                AND role_id IN (SELECT id FROM roles WHERE slug = :slug AND is_system = true)
            """),
            {"slug": slug},
        )
    for slug in ROLES_NEEDING_AR_VIEW_AND_UPDATE:
        conn.execute(
            sa.text("""
                DELETE FROM role_permissions
                WHERE permission_key = 'ar.view'
                AND role_id IN (SELECT id FROM roles WHERE slug = :slug AND is_system = true)
            """),
            {"slug": slug},
        )
