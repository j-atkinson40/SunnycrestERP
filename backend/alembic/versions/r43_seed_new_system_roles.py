"""Seed new system roles (manager, office_staff, driver, production, legacy_designer).

Data-only migration — no schema changes. Creates the 5 new system roles
for all existing companies that don't already have them.

Revision ID: r43_seed_new_system_roles
Revises: r42_legacy_email_settings
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "r43_seed_new_system_roles"
down_revision = "r42_legacy_email_settings"
branch_labels = None
depends_on = None


# Permission lists for the new roles (must match permissions.py)
_MANAGER_EXCLUDE = {"users.delete", "roles.delete"}

_OFFICE_STAFF = [
    "dashboard.view", "customers.view", "customers.create", "customers.edit",
    "products.view", "ar.view", "ar.create_quote", "ar.create_order",
    "ar.create_invoice", "ar.record_payment", "delivery.view", "drivers.view",
    "routes.view", "safety.view", "announcements.view", "announcements.create",
    "legacy_studio.view", "legacy_studio.create", "legacy_studio.edit",
    "inventory.view", "equipment.view", "work_orders.view", "personalization.view",
]

_DRIVER = ["dashboard.view", "delivery.view", "routes.view", "drivers.view", "safety.view"]

_PRODUCTION = [
    "dashboard.view", "production_log.view", "production_log.create",
    "production_log.edit", "work_orders.view", "work_orders.create",
    "qc.view", "qc.create", "safety.view", "safety.create",
    "equipment.view", "inventory.view", "announcements.view", "personalization.view",
]

_LEGACY_DESIGNER = [
    "dashboard.view", "legacy_studio.view", "legacy_studio.create",
    "legacy_studio.edit", "legacy_studio.approve", "legacy_studio.send",
    "ar.view", "customers.view", "delivery.view", "announcements.view",
    "personalization.view",
]

# Full permission registry (must match permissions.py PERMISSIONS dict)
_ALL_PERMISSIONS = []
_PERMISSIONS = {
    "audit": ["view"], "company": ["view", "edit"], "dashboard": ["view"],
    "employees": ["view", "edit", "view_notes"],
    "users": ["view", "create", "edit", "delete"],
    "roles": ["view", "create", "edit", "delete"],
    "departments": ["view", "create", "edit", "delete"],
    "products": ["view", "create", "edit", "delete"],
    "inventory": ["view", "create", "edit", "delete"],
    "equipment": ["view", "create", "edit", "delete"],
    "customers": ["view", "create", "edit", "delete"],
    "vendors": ["view", "create", "edit", "delete"],
    "ap": ["view", "create_po", "receive", "create_bill", "approve_bill", "record_payment", "export", "void"],
    "ar": ["view", "create_quote", "create_order", "create_invoice", "record_payment", "void"],
    "delivery": ["view", "create", "edit", "delete", "dispatch", "track"],
    "drivers": ["view", "create", "edit", "delete"],
    "vehicles": ["view", "create", "edit", "delete"],
    "routes": ["view", "create", "edit", "delete", "dispatch"],
    "carriers": ["view", "create", "edit", "delete"],
    "qc": ["view", "create", "edit", "delete"],
    "safety": ["view", "create", "edit", "delete"],
    "fh_cases": ["view", "create", "edit", "delete"],
    "fh_price_list": ["view", "create", "edit"],
    "fh_vault_orders": ["view", "create", "edit"],
    "fh_obituaries": ["view", "create", "edit"],
    "fh_invoices": ["view", "create", "edit", "void"],
    "fh_compliance": ["view"], "fh_portal": ["manage"],
    "production_log": ["view", "create", "edit", "delete"],
    "work_orders": ["view", "create", "edit", "delete"],
    "pour_events": ["view", "create", "edit"],
    "mix_designs": ["view", "create", "edit", "delete"],
    "cure_schedules": ["view", "create", "edit", "delete"],
    "legacy_studio": ["view", "create", "edit", "approve", "send", "delete"],
    "announcements": ["view", "create", "edit", "delete"],
    "personalization": ["view", "create", "complete", "approve"],
}
for _mod, _actions in _PERMISSIONS.items():
    for _act in _actions:
        _ALL_PERMISSIONS.append(f"{_mod}.{_act}")

_MANAGER = [k for k in _ALL_PERMISSIONS if k not in _MANAGER_EXCLUDE]

_NEW_ROLES = [
    ("Manager", "manager", "Full access except billing settings and user deletion", _MANAGER),
    ("Office Staff", "office_staff", "Order entry, billing, AR, scheduling, and Legacy Studio", _OFFICE_STAFF),
    ("Driver", "driver", "Driver portal and route management only", _DRIVER),
    ("Production", "production", "Operations board, production logging, safety, and QC", _PRODUCTION),
    ("Legacy Designer", "legacy_designer", "Full Legacy Studio access with order and customer view only", _LEGACY_DESIGNER),
]


def upgrade() -> None:
    conn = op.get_bind()
    companies = conn.execute(sa.text("SELECT id FROM companies")).fetchall()

    for (company_id,) in companies:
        for name, slug, description, permissions in _NEW_ROLES:
            # Check if role already exists for this company
            existing = conn.execute(
                sa.text("SELECT id FROM roles WHERE company_id = :cid AND slug = :slug"),
                {"cid": company_id, "slug": slug},
            ).fetchone()
            if existing:
                continue

            role_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO roles (id, company_id, name, slug, description, is_system, is_active) "
                    "VALUES (:id, :cid, :name, :slug, :desc, true, true)"
                ),
                {"id": role_id, "cid": company_id, "name": name, "slug": slug, "desc": description},
            )
            for perm_key in permissions:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (id, role_id, permission_key) "
                        "VALUES (:id, :rid, :pk)"
                    ),
                    {"id": str(uuid.uuid4()), "rid": role_id, "pk": perm_key},
                )


def downgrade() -> None:
    conn = op.get_bind()
    for _, slug, _, _ in _NEW_ROLES:
        # Delete permissions first, then roles
        role_ids = conn.execute(
            sa.text("SELECT id FROM roles WHERE slug = :slug AND is_system = true"),
            {"slug": slug},
        ).fetchall()
        for (role_id,) in role_ids:
            conn.execute(
                sa.text("DELETE FROM role_permissions WHERE role_id = :rid"),
                {"rid": role_id},
            )
            conn.execute(
                sa.text("DELETE FROM roles WHERE id = :rid"),
                {"rid": role_id},
            )
