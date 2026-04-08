"""Seed controlled month-end close test data for the previous full calendar month.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python scripts/seed_agent_test.py

Seeds agent-test-specific data only — does not touch existing staging data.
Creates 4 customers, 4 orders, 3 invoices, 4 payments with known anomaly triggers.
"""

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def _last_month_period():
    today = date.today()
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start, last_month_end


def seed(db: Session):
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
    from app.models.invoice import Invoice
    from app.models.sales_order import SalesOrder
    from app.models.user import User

    period_start, period_end = _last_month_period()
    mid = period_start + timedelta(days=14)
    print(f"Seeding agent test data for period: {period_start} – {period_end}")

    # Find or use first tenant
    tenant = db.query(Company).filter(Company.is_active == True).first()
    if not tenant:
        print("ERROR: No active company found. Run staging seed first.")
        return
    tid = tenant.id
    print(f"Using tenant: {tenant.name} ({tid})")

    # Find a user for triggered_by
    admin = db.query(User).filter(User.company_id == tid, User.is_active == True).first()
    if not admin:
        print("ERROR: No active user found for tenant.")
        return

    # Clean up previous agent test data (by account_number prefix)
    test_accounts = ["AGTEST-JFH", "AGTEST-SS", "AGTEST-MC", "AGTEST-RFH"]
    existing = db.query(Customer).filter(
        Customer.company_id == tid,
        Customer.account_number.in_(test_accounts),
    ).all()
    if existing:
        cids = [c.id for c in existing]
        # Delete related data
        db.query(CustomerPaymentApplication).filter(
            CustomerPaymentApplication.payment_id.in_(
                db.query(CustomerPayment.id).filter(CustomerPayment.customer_id.in_(cids))
            )
        ).delete(synchronize_session=False)
        db.query(CustomerPayment).filter(CustomerPayment.customer_id.in_(cids)).delete(synchronize_session=False)
        db.query(Invoice).filter(Invoice.customer_id.in_(cids)).delete(synchronize_session=False)
        db.query(SalesOrder).filter(SalesOrder.customer_id.in_(cids)).delete(synchronize_session=False)
        db.query(Customer).filter(Customer.id.in_(cids)).delete(synchronize_session=False)
        db.flush()
        print(f"Cleaned up {len(existing)} previous agent-test customers and related data.")

    # --- Customers ---
    johnson = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Johnson Funeral Home [AgTest]",
        account_number="AGTEST-JFH", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    smith = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Smith & Sons [AgTest]",
        account_number="AGTEST-SS", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    memorial = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Memorial Chapel [AgTest]",
        account_number="AGTEST-MC", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    riverside = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Riverside FH [AgTest]",
        account_number="AGTEST-RFH", is_active=True,
        receives_monthly_statement=False,  # NOT on statement
        receives_statements=True, payment_terms="cod",
    )
    db.add_all([johnson, smith, memorial, riverside])
    db.flush()
    print(f"Created 4 test customers (3 on statements, 1 not).")

    # --- Orders ---
    def _dt(d):
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    order_a = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-ORD-001",
        customer_id=johnson.id, status="delivered",
        order_date=_dt(period_start), delivered_at=_dt(mid), total=3864.00,
    )
    order_b = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-ORD-002",
        customer_id=smith.id, status="completed",
        order_date=_dt(period_start), delivered_at=_dt(mid), total=2850.00,
    )
    order_c = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-ORD-003",
        customer_id=memorial.id, status="delivered",
        order_date=_dt(period_start), delivered_at=_dt(mid), total=1934.00,
    )
    order_d = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-ORD-004",
        customer_id=johnson.id, status="confirmed",
        order_date=_dt(mid), total=500.00,
    )
    db.add_all([order_a, order_b, order_c, order_d])
    db.flush()
    print("Created 4 test orders (3 delivered, 1 confirmed).")

    # --- Invoices ---
    inv1 = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-INV-001",
        customer_id=johnson.id, sales_order_id=order_a.id,
        status="sent", total=3864.00, amount_paid=3864.00,
        invoice_date=_dt(mid), due_date=_dt(mid) + timedelta(days=30),
    )
    inv2 = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-INV-002",
        customer_id=smith.id, sales_order_id=order_b.id,
        status="overdue", total=2850.00, amount_paid=0,
        invoice_date=_dt(mid), due_date=_dt(mid) + timedelta(days=30),
    )
    old_date = datetime.now(timezone.utc) - timedelta(days=120)
    inv_old = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="AGTEST-INV-OLD",
        customer_id=smith.id, status="overdue",
        total=1500.00, amount_paid=0,
        invoice_date=old_date, due_date=old_date + timedelta(days=30),
    )
    db.add_all([inv1, inv2, inv_old])
    db.flush()
    print("Created 3 invoices (1 paid, 1 overdue, 1 90+ overdue). Order C has NO invoice.")

    # --- Payments ---
    pay1 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=johnson.id,
        payment_date=_dt(mid), total_amount=3864.00,
        payment_method="check", reference_number="AGTEST-CHK-1001",
    )
    pay2 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=riverside.id,
        payment_date=_dt(mid), total_amount=500.00,
        payment_method="check", reference_number="AGTEST-CHK-UNMATCHED",
    )
    pay3 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=smith.id,
        payment_date=_dt(mid), total_amount=1000.00,
        payment_method="check", reference_number="AGTEST-CHK-2001",
    )
    pay4 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=smith.id,
        payment_date=_dt(mid) + timedelta(days=2), total_amount=1000.00,
        payment_method="check", reference_number="AGTEST-CHK-2002",
    )
    db.add_all([pay1, pay2, pay3, pay4])
    db.flush()

    # Match pay1 → inv1
    app1 = CustomerPaymentApplication(
        id=str(uuid.uuid4()), payment_id=pay1.id,
        invoice_id=inv1.id, amount_applied=3864.00,
    )
    db.add(app1)
    db.flush()
    print("Created 4 payments (1 matched, 3 unmatched). Payments 3+4 are duplicate suspects.")

    db.commit()
    print("\n✓ Agent test data seeded successfully.")
    print(f"  Period: {period_start} – {period_end}")
    print(f"  Expected anomalies:")
    print(f"    CRITICAL: uninvoiced_delivery (Order C / Memorial Chapel)")
    print(f"    CRITICAL: duplicate_payment (Payments 3+4 / Smith & Sons)")
    print(f"    WARNING:  unmatched_payment (Payment 2 / Riverside FH)")
    print(f"    WARNING:  unmatched_payment (Payment 3 / Smith & Sons)")
    print(f"    WARNING:  unmatched_payment (Payment 4 / Smith & Sons)")
    print(f"    WARNING:  overdue_ar_90plus (INV-OLD / Smith & Sons)")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()
