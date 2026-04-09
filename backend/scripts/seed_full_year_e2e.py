"""Seed a complete 2025 calendar year of data for full E2E accounting agent testing.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python scripts/seed_full_year_e2e.py

Idempotent — running twice produces the same result (uses deterministic prefixes).
"""

import calendar
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Deterministic prefix for idempotency
PREFIX = "e2e25-"


def _dt(y, m, d, h=12):
    return datetime(y, m, d, h, 0, 0, tzinfo=timezone.utc)


def _uid(label: str) -> str:
    """Deterministic UUID from label for idempotency."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{PREFIX}{label}"))


def cleanup(db: Session, tid: str):
    """Remove previous E2E seed data."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.agent_run_step import AgentRunStep
    from app.models.period_lock import PeriodLock
    from app.models.statement import StatementRun

    # Clean agent data for this tenant (respect FK ordering)
    jobs = db.query(AgentJob).filter(AgentJob.tenant_id == tid).all()
    job_ids = [j.id for j in jobs]
    if job_ids:
        db.execute(text(
            "DELETE FROM agent_activity_log WHERE job_id IN :ids"
        ), {"ids": tuple(job_ids)})
        for j in jobs:
            db.query(AgentAnomaly).filter(AgentAnomaly.agent_job_id == j.id).delete()
            db.query(AgentRunStep).filter(AgentRunStep.agent_job_id == j.id).delete()
    db.query(AgentJob).filter(AgentJob.tenant_id == tid).delete()
    db.query(PeriodLock).filter(PeriodLock.tenant_id == tid).delete()

    # Clean statement runs
    db.query(StatementRun).filter(StatementRun.tenant_id == tid).delete()

    # Clean seeded records by prefix pattern
    db.execute(text(
        "DELETE FROM customer_payment_applications WHERE payment_id IN "
        "(SELECT id FROM customer_payments WHERE reference_number LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM customer_payments WHERE reference_number LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM invoice_lines WHERE invoice_id IN "
        "(SELECT id FROM invoices WHERE number LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM invoices WHERE number LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM sales_order_lines WHERE sales_order_id IN "
        "(SELECT id FROM sales_orders WHERE number LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM sales_orders WHERE number LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM vendor_payment_applications WHERE payment_id IN "
        "(SELECT id FROM vendor_payments WHERE reference_number LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM vendor_payments WHERE reference_number LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM vendor_bill_lines WHERE bill_id IN "
        "(SELECT id FROM vendor_bills WHERE number LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM vendor_bills WHERE number LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM inventory_transactions WHERE reference LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM journal_entry_lines WHERE journal_entry_id IN "
        "(SELECT id FROM journal_entries WHERE description LIKE :prefix)"
    ), {"prefix": f"{PREFIX}%"})
    db.execute(text(
        "DELETE FROM journal_entries WHERE description LIKE :prefix"
    ), {"prefix": f"{PREFIX}%"})

    db.flush()
    print("  Cleaned previous E2E data")


def seed(db: Session):
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
    from app.models.inventory_item import InventoryItem
    from app.models.inventory_transaction import InventoryTransaction
    from app.models.invoice import Invoice, InvoiceLine
    from app.models.journal_entry import JournalEntry, JournalEntryLine
    from app.models.product import Product
    from app.models.sales_order import SalesOrder, SalesOrderLine
    from app.models.user import User
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine
    from app.models.vendor_payment import VendorPayment
    from app.models.vendor_payment_application import VendorPaymentApplication

    tenant = db.query(Company).filter(Company.is_active == True).first()
    if not tenant:
        print("ERROR: No active company found.")
        return
    tid = tenant.id
    print(f"Tenant: {tenant.name} ({tid[:8]}...)")

    admin = db.query(User).filter(
        User.company_id == tid, User.is_active == True
    ).first()
    if not admin:
        print("ERROR: No active user.")
        return
    uid = admin.id

    cleanup(db, tid)

    # ─── CUSTOMERS ───────────────────────────────────────────────────
    customer_specs = [
        ("johnson-fh", "Johnson Funeral Home", "JFH-001", True),
        ("smith-fh", "Smith & Sons Funeral Home", "SSF-001", True),
        ("memorial", "Memorial Chapel", "MC-001", True),
        ("riverside", "Riverside Funeral Home", "RFH-001", False),
    ]
    customers = {}
    for key, name, acct, receives_stmt in customer_specs:
        cid = _uid(f"cust-{key}")
        existing = db.query(Customer).filter(Customer.id == cid).first()
        if existing:
            existing.name = name
            existing.receives_monthly_statement = receives_stmt
            existing.is_active = True
            customers[key] = existing
        else:
            c = Customer(
                id=cid,
                company_id=tid,
                name=name,
                account_number=acct,
                is_active=True,
                receives_monthly_statement=receives_stmt,
                billing_email=f"{key}@test.com",
                email=f"{key}@test.com",
                payment_terms="net_30",
            )
            db.add(c)
            customers[key] = c
    db.flush()
    print(f"  Customers: {len(customers)}")

    # ─── PRODUCTS ────────────────────────────────────────────────────
    product_specs = [
        ("bronze-triune", "Bronze Triune", "BT-001", Decimal("3864.00"), Decimal("1200.00")),
        ("sst-triune", "SST Triune", "ST-001", Decimal("2850.00"), Decimal("900.00")),
        ("venetian", "Venetian", "VN-001", Decimal("1934.00"), Decimal("620.00")),
        ("graveliner", "Graveliner", "GL-001", Decimal("996.00"), Decimal("320.00")),
    ]
    products = {}
    for key, name, sku, price, cost in product_specs:
        pid = _uid(f"prod-{key}")
        existing = db.query(Product).filter(Product.id == pid).first()
        if existing:
            existing.price = price
            existing.cost_price = cost
            existing.is_inventory_tracked = True
            products[key] = existing
        else:
            p = Product(
                id=pid,
                company_id=tid,
                name=name,
                sku=sku,
                price=price,
                cost_price=cost,
                is_active=True,
                is_inventory_tracked=True,
            )
            db.add(p)
            products[key] = p
    db.flush()
    print(f"  Products: {len(products)}")

    # ─── INVENTORY ───────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    inv_specs = [
        ("bronze-triune", 8, now - timedelta(days=45)),
        ("sst-triune", 12, now - timedelta(days=30)),
        ("venetian", 3, now - timedelta(days=200)),
        ("graveliner", 0, now - timedelta(days=60)),
    ]
    for key, qty, counted_at in inv_specs:
        iid = _uid(f"inv-item-{key}")
        existing = db.query(InventoryItem).filter(InventoryItem.id == iid).first()
        if existing:
            existing.quantity_on_hand = qty
            existing.last_counted_at = counted_at
        else:
            ii = InventoryItem(
                id=iid,
                company_id=tid,
                product_id=products[key].id,
                quantity_on_hand=qty,
                last_counted_at=counted_at,
                is_active=True,
            )
            db.add(ii)
    db.flush()

    # Inventory transactions — SST Triune has mismatch
    txn_specs = [
        ("bronze-triune", 8),   # matches on_hand
        ("sst-triune", 10),     # MISMATCH — on_hand is 12
        ("venetian", 3),        # matches
        ("graveliner", 0),      # matches
    ]
    for key, qty_after in txn_specs:
        txn_id = _uid(f"inv-txn-{key}")
        existing = db.query(InventoryTransaction).filter(InventoryTransaction.id == txn_id).first()
        if not existing:
            txn = InventoryTransaction(
                id=txn_id,
                company_id=tid,
                product_id=products[key].id,
                transaction_type="count",
                quantity_change=0,
                quantity_after=qty_after,
                reference=f"{PREFIX}initial-count",
                created_at=now - timedelta(days=35),
            )
            db.add(txn)
    db.flush()
    print(f"  Inventory items: {len(inv_specs)} with transactions")

    # ─── VENDORS ─────────────────────────────────────────────────────
    vendor_specs = [
        ("concrete", "Concrete Supplier Inc", True, "45-1234567"),
        ("rebar", "Rebar & Steel LLC", True, None),  # missing tax ID
        ("office", "Office Depot", False, None),
        ("trucking", "Acme Trucking", False, None),
    ]
    vendors = {}
    for key, name, is_1099, tax_id in vendor_specs:
        vid = _uid(f"vendor-{key}")
        existing = db.query(Vendor).filter(Vendor.id == vid).first()
        if existing:
            existing.is_1099_vendor = is_1099
            existing.tax_id = tax_id
            vendors[key] = existing
        else:
            v = Vendor(
                id=vid,
                company_id=tid,
                name=name,
                is_1099_vendor=is_1099,
                tax_id=tax_id,
                is_active=True,
            )
            db.add(v)
            vendors[key] = v
    db.flush()
    print(f"  Vendors: {len(vendors)}")

    # ─── SALES ORDERS + INVOICES + PAYMENTS ──────────────────────────
    # 24 orders: 2 per month (Johnson + Smith), delivered
    # 22 invoices (skip October = month 10 for both)
    # 20 payments (leave Smith Nov + Memorial old invoice unpaid)
    orders_created = 0
    invoices_created = 0
    payments_created = 0
    product_cycle = ["bronze-triune", "sst-triune"]

    for month in range(1, 13):
        last_day = calendar.monthrange(2025, month)[1]
        for i, cust_key in enumerate(["johnson-fh", "smith-fh"]):
            order_num = f"{PREFIX}SO-{month:02d}-{i+1}"
            oid = _uid(f"order-{month}-{i}")
            prod_key = product_cycle[(month + i) % 2]
            prod = products[prod_key]
            order_date = _dt(2025, month, min(5 + i * 10, last_day))
            delivered_at = _dt(2025, month, min(10 + i * 10, last_day))

            existing_order = db.query(SalesOrder).filter(SalesOrder.id == oid).first()
            if not existing_order:
                so = SalesOrder(
                    id=oid,
                    company_id=tid,
                    number=order_num,
                    customer_id=customers[cust_key].id,
                    status="delivered",
                    order_date=order_date,
                    delivered_at=delivered_at,
                    subtotal=prod.price,
                    total=prod.price,
                    created_by=uid,
                )
                db.add(so)
                db.flush()

                sol = SalesOrderLine(
                    id=_uid(f"sol-{month}-{i}"),
                    sales_order_id=oid,
                    product_id=prod.id,
                    description=prod.name,
                    quantity=Decimal("1"),
                    unit_price=prod.price,
                    line_total=prod.price,
                )
                db.add(sol)
                orders_created += 1

            # Skip invoices for October (month 10) — uninvoiced_delivery anomaly
            if month == 10:
                continue

            inv_num = f"{PREFIX}INV-{month:02d}-{i+1}"
            inv_id = _uid(f"inv-{month}-{i}")
            inv_date = _dt(2025, month, min(15 + i * 5, last_day))

            # Determine if paid
            is_paid = True
            # Smith November (month 11, i=1) — leave unpaid (30-day aging)
            if month == 11 and cust_key == "smith-fh":
                is_paid = False

            existing_inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if not existing_inv:
                inv = Invoice(
                    id=inv_id,
                    company_id=tid,
                    number=inv_num,
                    customer_id=customers[cust_key].id,
                    sales_order_id=oid,
                    status="paid" if is_paid else "sent",
                    invoice_date=inv_date,
                    due_date=inv_date + timedelta(days=30),
                    subtotal=prod.price,
                    total=prod.price,
                    amount_paid=prod.price if is_paid else Decimal("0"),
                    paid_at=inv_date + timedelta(days=20) if is_paid else None,
                    created_by=uid,
                )
                db.add(inv)
                db.flush()

                il = InvoiceLine(
                    id=_uid(f"il-{month}-{i}"),
                    invoice_id=inv_id,
                    product_id=prod.id,
                    description=prod.name,
                    quantity=Decimal("1"),
                    unit_price=prod.price,
                    line_total=prod.price,
                )
                db.add(il)
                invoices_created += 1

                if is_paid:
                    pay_id = _uid(f"pay-{month}-{i}")
                    pay = CustomerPayment(
                        id=pay_id,
                        company_id=tid,
                        customer_id=customers[cust_key].id,
                        payment_date=inv_date + timedelta(days=20),
                        total_amount=prod.price,
                        payment_method="check",
                        reference_number=f"{PREFIX}CHK-{month:02d}-{i+1}",
                        created_by=uid,
                    )
                    db.add(pay)
                    db.flush()

                    app = CustomerPaymentApplication(
                        id=_uid(f"pa-{month}-{i}"),
                        payment_id=pay_id,
                        invoice_id=inv_id,
                        amount_applied=prod.price,
                    )
                    db.add(app)
                    payments_created += 1

    # Memorial Chapel — old overdue invoice (95 days)
    memorial_inv_id = _uid("inv-memorial-old")
    existing_memorial = db.query(Invoice).filter(Invoice.id == memorial_inv_id).first()
    if not existing_memorial:
        old_date = now - timedelta(days=95)
        inv = Invoice(
            id=memorial_inv_id,
            company_id=tid,
            number=f"{PREFIX}INV-MEM-OLD",
            customer_id=customers["memorial"].id,
            status="overdue",
            invoice_date=old_date,
            due_date=old_date + timedelta(days=30),
            subtotal=Decimal("5200.00"),
            total=Decimal("5200.00"),
            amount_paid=Decimal("0"),
            created_by=uid,
        )
        db.add(inv)
        invoices_created += 1
    db.flush()

    print(f"  Orders: {orders_created}")
    print(f"  Invoices: {invoices_created} ({payments_created} paid, {invoices_created - payments_created} outstanding)")
    print(f"  Payments: {payments_created}")

    # ─── VENDOR BILLS & PAYMENTS ─────────────────────────────────────
    vbill_specs = [
        ("concrete", 12, Decimal("700.00")),   # $8400 total
        ("rebar", 6, Decimal("533.33")),        # ~$3200 total
        ("office", 12, Decimal("153.33")),      # ~$1840 total
        ("trucking", 3, Decimal("150.00")),     # $450 total
    ]
    vbills_created = 0
    vpay_created = 0
    for vkey, count, monthly_amt in vbill_specs:
        for m in range(1, count + 1):
            last_day = calendar.monthrange(2025, m)[1]
            bill_id = _uid(f"vbill-{vkey}-{m}")
            existing_vb = db.query(VendorBill).filter(VendorBill.id == bill_id).first()
            if not existing_vb:
                vb = VendorBill(
                    id=bill_id,
                    company_id=tid,
                    number=f"{PREFIX}VB-{vkey[:4].upper()}-{m:02d}",
                    vendor_id=vendors[vkey].id,
                    status="paid",
                    bill_date=_dt(2025, m, 1),
                    due_date=_dt(2025, m, last_day),
                    total=monthly_amt,
                    amount_paid=monthly_amt,
                    created_by=uid,
                )
                db.add(vb)
                db.flush()
                vbills_created += 1

                # Payment
                vp_id = _uid(f"vpay-{vkey}-{m}")
                vp = VendorPayment(
                    id=vp_id,
                    company_id=tid,
                    vendor_id=vendors[vkey].id,
                    payment_date=_dt(2025, m, 25),
                    total_amount=monthly_amt,
                    payment_method="check",
                    reference_number=f"{PREFIX}VCHK-{vkey[:4].upper()}-{m:02d}",
                    created_by=uid,
                )
                db.add(vp)
                db.flush()

                vpa = VendorPaymentApplication(
                    id=_uid(f"vpa-{vkey}-{m}"),
                    payment_id=vp_id,
                    bill_id=bill_id,
                    amount_applied=monthly_amt,
                )
                db.add(vpa)
                vpay_created += 1

    db.flush()
    print(f"  Vendor bills: {vbills_created}")
    print(f"  Vendor payments: {vpay_created}")

    # ─── VENDOR BILL LINES (uncategorized + orphaned) ────────────────
    # Pick first 5 concrete bills for uncategorized lines
    concrete_bills = (
        db.query(VendorBill)
        .filter(VendorBill.vendor_id == vendors["concrete"].id, VendorBill.number.like(f"{PREFIX}%"))
        .order_by(VendorBill.bill_date)
        .limit(7)
        .all()
    )
    vbl_created = 0
    for idx, vb in enumerate(concrete_bills):
        vbl_id = _uid(f"vbl-{vb.id[:8]}")
        existing_vbl = db.query(VendorBillLine).filter(VendorBillLine.id == vbl_id).first()
        if not existing_vbl:
            cat = None if idx < 5 else "nonexistent_category"  # 5 uncategorized + 2 orphaned
            vbl = VendorBillLine(
                id=vbl_id,
                bill_id=vb.id,
                description=f"Concrete supplies - month {idx+1}",
                quantity=Decimal("1"),
                unit_cost=vb.total,
                amount=vb.total,
                expense_category=cat,
            )
            db.add(vbl)
            vbl_created += 1
    db.flush()
    print(f"  Vendor bill lines: {vbl_created} (5 uncategorized, 2 orphaned)")

    # ─── JOURNAL ENTRIES ─────────────────────────────────────────────
    je_created = 0
    gl_acct_id = _uid("gl-acct-dummy")

    for month in range(1, 13):
        last_day = calendar.monthrange(2025, month)[1]

        # Revenue entry
        rev_id = _uid(f"je-rev-{month}")
        existing_je = db.query(JournalEntry).filter(JournalEntry.id == rev_id).first()
        if not existing_je:
            rev_amount = Decimal("7000.00") + Decimal(str(month * 200))  # ~$7200-$9400
            je = JournalEntry(
                id=rev_id,
                tenant_id=tid,
                entry_number=f"JE-REV-{month:02d}",
                entry_type="standard",
                status="posted",
                entry_date=date(2025, month, last_day),
                period_month=month,
                period_year=2025,
                description=f"{PREFIX}Monthly revenue - {calendar.month_name[month]} 2025",
                total_debits=rev_amount,
                total_credits=rev_amount,
                created_by=uid,
            )
            db.add(je)
            db.flush()

            # Debit AR, credit Revenue
            db.add(JournalEntryLine(
                id=_uid(f"jel-rev-dr-{month}"),
                tenant_id=tid,
                journal_entry_id=rev_id,
                line_number=1,
                gl_account_id=gl_acct_id,
                gl_account_number="1200",
                gl_account_name="Accounts Receivable",
                description="Monthly AR",
                debit_amount=rev_amount,
                credit_amount=Decimal("0"),
            ))
            db.add(JournalEntryLine(
                id=_uid(f"jel-rev-cr-{month}"),
                tenant_id=tid,
                journal_entry_id=rev_id,
                line_number=2,
                gl_account_id=gl_acct_id,
                gl_account_number="4000",
                gl_account_name="Sales Revenue",
                description="Monthly revenue",
                debit_amount=Decimal("0"),
                credit_amount=rev_amount,
            ))
            je_created += 1

        # Expense entry
        exp_id = _uid(f"je-exp-{month}")
        existing_exp = db.query(JournalEntry).filter(JournalEntry.id == exp_id).first()
        if not existing_exp:
            exp_amount = Decimal("3500.00") + Decimal(str(month * 100))  # ~$3600-$4700
            je = JournalEntry(
                id=exp_id,
                tenant_id=tid,
                entry_number=f"JE-EXP-{month:02d}",
                entry_type="standard",
                status="posted",
                entry_date=date(2025, month, last_day),
                period_month=month,
                period_year=2025,
                description=f"{PREFIX}Monthly expenses - {calendar.month_name[month]} 2025",
                total_debits=exp_amount,
                total_credits=exp_amount,
                created_by=uid,
            )
            db.add(je)
            db.flush()

            db.add(JournalEntryLine(
                id=_uid(f"jel-exp-dr-{month}"),
                tenant_id=tid,
                journal_entry_id=exp_id,
                line_number=1,
                gl_account_id=gl_acct_id,
                gl_account_number="6000",
                gl_account_name="Operating Expenses",
                description="Monthly operating expenses",
                debit_amount=exp_amount,
                credit_amount=Decimal("0"),
            ))
            db.add(JournalEntryLine(
                id=_uid(f"jel-exp-cr-{month}"),
                tenant_id=tid,
                journal_entry_id=exp_id,
                line_number=2,
                gl_account_id=gl_acct_id,
                gl_account_number="1000",
                gl_account_name="Cash",
                description="Cash paid",
                debit_amount=Decimal("0"),
                credit_amount=exp_amount,
            ))
            je_created += 1

        # Depreciation entry
        depr_id = _uid(f"je-depr-{month}")
        existing_depr = db.query(JournalEntry).filter(JournalEntry.id == depr_id).first()
        if not existing_depr:
            depr_amount = Decimal("850.00")  # Consistent monthly
            je = JournalEntry(
                id=depr_id,
                tenant_id=tid,
                entry_number=f"JE-DEPR-{month:02d}",
                entry_type="standard",
                status="posted",
                entry_date=date(2025, month, last_day),
                period_month=month,
                period_year=2025,
                description=f"{PREFIX}Monthly depreciation - {calendar.month_name[month]} 2025",
                total_debits=depr_amount,
                total_credits=depr_amount,
                created_by=uid,
            )
            db.add(je)
            db.flush()

            db.add(JournalEntryLine(
                id=_uid(f"jel-depr-dr-{month}"),
                tenant_id=tid,
                journal_entry_id=depr_id,
                line_number=1,
                gl_account_id=gl_acct_id,
                gl_account_number="6500",
                gl_account_name="Depreciation Expense",
                description="Monthly depreciation",
                debit_amount=depr_amount,
                credit_amount=Decimal("0"),
            ))
            db.add(JournalEntryLine(
                id=_uid(f"jel-depr-cr-{month}"),
                tenant_id=tid,
                journal_entry_id=depr_id,
                line_number=2,
                gl_account_id=gl_acct_id,
                gl_account_number="1510",
                gl_account_name="Accumulated Depreciation",
                description="Accumulated depreciation",
                debit_amount=Decimal("0"),
                credit_amount=depr_amount,
            ))
            je_created += 1

    # December accrual entry
    accrual_id = _uid("je-accrual-dec")
    existing_accrual = db.query(JournalEntry).filter(JournalEntry.id == accrual_id).first()
    if not existing_accrual:
        accrual_amt = Decimal("4200.00")
        je = JournalEntry(
            id=accrual_id,
            tenant_id=tid,
            entry_number="JE-ACCR-12",
            entry_type="standard",
            status="posted",
            entry_date=date(2025, 12, 31),
            period_month=12,
            period_year=2025,
            description=f"{PREFIX}accrued wages December",
            total_debits=accrual_amt,
            total_credits=accrual_amt,
            created_by=uid,
        )
        db.add(je)
        db.flush()

        db.add(JournalEntryLine(
            id=_uid("jel-accr-dr"),
            tenant_id=tid,
            journal_entry_id=accrual_id,
            line_number=1,
            gl_account_id=gl_acct_id,
            gl_account_number="6200",
            gl_account_name="Accrued Wages Expense",
            description="accrued wages December",
            debit_amount=accrual_amt,
            credit_amount=Decimal("0"),
        ))
        db.add(JournalEntryLine(
            id=_uid("jel-accr-cr"),
            tenant_id=tid,
            journal_entry_id=accrual_id,
            line_number=2,
            gl_account_id=gl_acct_id,
            gl_account_number="2100",
            gl_account_name="Accrued Wages Payable",
            description="accrued wages payable",
            debit_amount=Decimal("0"),
            credit_amount=accrual_amt,
        ))
        je_created += 1

    db.flush()
    print(f"  Journal entries: {je_created}")
    print(f"  Period: Jan 2025 - Dec 2025")

    db.commit()
    print("\nSeed complete!")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
