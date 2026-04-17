"""Seed 4 sample quotes for the Quoting Hub demo.

Picks the first tenant with `sales` module enabled, grabs 2 existing
customers, and creates:
  1. Hopkins — sent 23 days ago (older, awaiting response)
  2. Murphy — sent 4 days ago, expiring in 3 days (the "Expiring Soon" card)
  3. Valley — draft (never sent)
  4. Hopkins — converted (won), modified this month

Idempotent: skips if quotes with these numbers already exist.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/seed_quotes.py [--tenant-id <uuid>]
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models.company import Company
from app.models.company_module import CompanyModule
from app.models.customer import Customer
from app.models.quote import Quote, QuoteLine


FIXTURES = [
    {
        "tag": "hopkins_sent_23d",
        "customer_match": "hopkins",
        "status": "sent",
        "quote_offset_days": -23,
        "expiry_offset_days": 7,  # expires a week out from now
        "lines": [
            {"description": "Continental Vault — Standard", "quantity": 1, "unit_price": 2450.00},
            {"description": "Full Equipment Package", "quantity": 1, "unit_price": 350.00},
        ],
        "notes": "Standard package for upcoming service.",
    },
    {
        "tag": "murphy_sent_4d_expiring",
        "customer_match": "murphy",
        "status": "sent",
        "quote_offset_days": -4,
        "expiry_offset_days": 3,  # expires in 3 days → Expiring Soon card
        "lines": [
            {"description": "Monticello Vault", "quantity": 1, "unit_price": 1875.00},
        ],
        "notes": "Monticello per phone discussion.",
    },
    {
        "tag": "valley_draft",
        "customer_match": "valley",
        "status": "draft",
        "quote_offset_days": 0,
        "expiry_offset_days": 30,
        "lines": [
            {"description": "Continental Vault — Premium", "quantity": 1, "unit_price": 3200.00},
            {"description": "Delivery & Setup", "quantity": 1, "unit_price": 225.00},
        ],
        "notes": "Premium continental for pre-need planning.",
    },
    {
        "tag": "hopkins_converted",
        "customer_match": "hopkins",
        "status": "converted",
        "quote_offset_days": -12,
        "expiry_offset_days": 18,
        "lines": [
            {"description": "Monticello Vault", "quantity": 1, "unit_price": 1875.00},
            {"description": "Full Equipment Package", "quantity": 1, "unit_price": 350.00},
        ],
        "notes": "Converted to SO.",
    },
]


def find_customer(db, company_id: str, match: str) -> Customer | None:
    """Find first active customer whose name ILIKEs the match term."""
    return (
        db.query(Customer)
        .filter(
            Customer.company_id == company_id,
            Customer.name.ilike(f"%{match}%"),
        )
        .first()
    )


def any_customer(db, company_id: str) -> Customer | None:
    return (
        db.query(Customer)
        .filter(Customer.company_id == company_id)
        .order_by(Customer.name)
        .first()
    )


def pick_tenant(db, tenant_id: str | None = None) -> Company | None:
    if tenant_id:
        return db.query(Company).filter(Company.id == tenant_id).first()
    # Find first active tenant with sales module
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


def seed_for_tenant(db, tenant: Company) -> int:
    """Returns count of quotes inserted."""
    now = datetime.now(timezone.utc)
    inserted = 0

    # Build a deterministic number scheme to make the script idempotent.
    for idx, fx in enumerate(FIXTURES):
        number = f"QTE-DEMO-{idx + 1:04d}"
        exists = (
            db.query(Quote)
            .filter(Quote.company_id == tenant.id, Quote.number == number)
            .first()
        )
        if exists:
            print(f"  · skip {number} (already exists)")
            continue

        cust = find_customer(db, tenant.id, fx["customer_match"]) or any_customer(db, tenant.id)
        if not cust:
            print(f"  ! no customers in tenant {tenant.id}; cannot seed quotes")
            return inserted

        subtotal = sum(
            Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"]))
            for l in fx["lines"]
        )
        tax_rate = Decimal("0.08")
        tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"))
        total = subtotal + tax_amount

        quote_date = now + timedelta(days=fx["quote_offset_days"])
        expiry_date = quote_date + timedelta(days=fx["expiry_offset_days"])

        q = Quote(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            number=number,
            customer_id=cust.id,
            customer_name=cust.name,
            status=fx["status"],
            quote_date=quote_date,
            expiry_date=expiry_date,
            payment_terms="Net 30",
            subtotal=subtotal.quantize(Decimal("0.01")),
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total.quantize(Decimal("0.01")),
            notes=fx["notes"],
            created_at=quote_date,
            modified_at=now if fx["status"] == "converted" else None,
        )
        db.add(q)
        db.flush()

        for sort_idx, ld in enumerate(fx["lines"]):
            db.add(
                QuoteLine(
                    id=str(uuid.uuid4()),
                    quote_id=q.id,
                    description=ld["description"],
                    quantity=Decimal(str(ld["quantity"])),
                    unit_price=Decimal(str(ld["unit_price"])),
                    line_total=(
                        Decimal(str(ld["quantity"])) * Decimal(str(ld["unit_price"]))
                    ).quantize(Decimal("0.01")),
                    sort_order=sort_idx,
                )
            )
        inserted += 1
        print(
            f"  + {number} · {cust.name} · {fx['status']} · ${total:,.2f}"
        )

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
            print("No eligible tenant found (needs sales module enabled).")
            sys.exit(1)
        print(f"Seeding quotes for tenant: {tenant.name} ({tenant.id})")
        n = seed_for_tenant(db, tenant)
        print(f"Done. Inserted {n} quote(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
