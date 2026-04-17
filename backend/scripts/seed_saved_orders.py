"""Seed 2 sample saved orders for the Compose-templates demo.

1. Cement Reorder — user scope, 47 uses, typical repeat PO pattern
2. Hopkins Continental — company scope, 23 uses, common vault config

Idempotent: skips if a saved order with the same name already exists.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/seed_saved_orders.py [--tenant-id <uuid>]
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.company import Company
from app.models.company_module import CompanyModule
from app.models.saved_order import SavedOrder
from app.models.user import User
from app.models.workflow import Workflow

FIXTURES = [
    {
        "name": "Cement Reorder",
        "scope": "user",
        "trigger_keywords": ["cement", "cement reorder"],
        "product_type": "Purchase Order",
        "entry_intent": "order",
        "saved_fields": {
            "ask_vendor": "Acme Cement Co",
            "ask_product": "Portland Type I, 94 lb bag",
            "ask_quantity": "50",
        },
        "use_count": 47,
        "days_ago_last": 6,
    },
    {
        "name": "Hopkins Continental — Standard",
        "scope": "company",
        "trigger_keywords": ["hopkins continental", "hopkins"],
        "product_type": "Vault Order",
        "entry_intent": "order",
        "saved_fields": {
            "ask_customer": "Hopkins Funeral Home",
            "ask_product": "Continental Vault — Standard",
            "ask_equipment": "Full Equipment Package",
        },
        "use_count": 23,
        "days_ago_last": 2,
    },
]


def pick_tenant(db, tenant_id: str | None = None) -> Company | None:
    if tenant_id:
        return db.query(Company).filter(Company.id == tenant_id).first()
    tenants = (
        db.query(Company)
        .join(CompanyModule, CompanyModule.company_id == Company.id)
        .filter(
            Company.is_active.is_(True),
            CompanyModule.module_key == "sales",
            CompanyModule.is_enabled.is_(True),
        )
        .all()
    )
    return tenants[0] if tenants else None


def pick_user(db, company_id: str) -> User | None:
    return (
        db.query(User)
        .filter(User.company_id == company_id, User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .first()
    )


def pick_workflow(db, company_id: str) -> Workflow | None:
    # Prefer the wf_compose workflow; fall back to any for the tenant.
    w = (
        db.query(Workflow)
        .filter(
            Workflow.company_id == company_id,
            Workflow.workflow_key == "wf_compose",
        )
        .first()
    )
    if w:
        return w
    return (
        db.query(Workflow)
        .filter(Workflow.company_id == company_id)
        .order_by(Workflow.created_at.asc())
        .first()
    )


def seed_for_tenant(db, tenant: Company) -> int:
    user = pick_user(db, tenant.id)
    workflow = pick_workflow(db, tenant.id)
    if not user or not workflow:
        print(f"  ! tenant {tenant.id} missing user or workflow; skipping")
        return 0

    inserted = 0
    now = datetime.now(timezone.utc)

    for fx in FIXTURES:
        exists = (
            db.query(SavedOrder)
            .filter(
                SavedOrder.company_id == tenant.id,
                SavedOrder.name == fx["name"],
                SavedOrder.is_active.is_(True),
            )
            .first()
        )
        if exists:
            print(f"  · skip {fx['name']} (already exists)")
            continue

        so = SavedOrder(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            created_by_user_id=user.id,
            name=fx["name"],
            workflow_id=workflow.id,
            trigger_keywords=fx["trigger_keywords"],
            product_type=fx["product_type"],
            entry_intent=fx["entry_intent"],
            saved_fields=fx["saved_fields"],
            scope=fx["scope"],
            use_count=fx["use_count"],
            last_used_at=now - timedelta(days=fx["days_ago_last"]),
            last_used_by_user_id=user.id,
        )
        db.add(so)
        inserted += 1
        print(f"  + {fx['name']} · {fx['scope']} · {fx['use_count']} uses")

    if inserted:
        db.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", help="Target a specific tenant UUID")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = pick_tenant(db, args.tenant_id)
        if not tenant:
            print("No eligible tenant found.")
            sys.exit(1)
        print(f"Seeding saved orders for tenant: {tenant.name} ({tenant.id})")
        n = seed_for_tenant(db, tenant)
        print(f"Done. Inserted {n} saved order(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
