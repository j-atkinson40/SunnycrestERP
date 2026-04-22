#!/usr/bin/env python3
"""Seed staging database directly via SQLAlchemy ORM.

Run:  DATABASE_URL=postgresql://... python scripts/seed_staging.py

Creates a complete test tenant with users, customers, contacts,
cemeteries, products, orders, invoices, price list, and KB data.
"""

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# ---------------------------------------------------------------------------
# Bootstrap — add backend/ to sys.path so we can import app modules
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.permissions import (
    ACCOUNTANT_DEFAULT_PERMISSIONS,
    OFFICE_STAFF_DEFAULT_PERMISSIONS,
    DRIVER_DEFAULT_PERMISSIONS,
    PRODUCTION_DEFAULT_PERMISSIONS,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required.")
    print("Usage: DATABASE_URL=postgresql://user:pass@host:port/db python scripts/seed_staging.py")
    sys.exit(1)

CFG = {"company_id": "staging-test-001"}  # mutable so we can adopt existing company
COMPANY_NAME = "Test Vault Co"
COMPANY_SLUG = "testco"
NOW = datetime.now(timezone.utc)


def uid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
counts = {
    "tenant": "already exists",
    "users": 0,
    "roles": 0,
    "customers": 0,
    "company_entities": 0,
    "contacts": 0,
    "cemeteries": 0,
    "categories": 0,
    "products": 0,
    "orders": 0,
    "order_lines": 0,
    "invoices": 0,
    "invoice_lines": 0,
    "payments": 0,
    "price_list": "skipped",
    "kb_categories": 0,
    "kb_documents": 0,
}


def main():
    engine = create_engine(DATABASE_URL, echo=False)
    print(f"=== Staging DB Seed ===")
    print(f"Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '(local)'}")
    print(f"Tenant:   {CFG['company_id']} ({COMPANY_NAME})")
    print()

    with Session(engine) as db:
        # Check for existing tenant — by ID or by slug
        existing_by_id = db.execute(
            text("SELECT id FROM companies WHERE id = :id"),
            {"id": CFG["company_id"]},
        ).fetchone()
        existing_by_slug = db.execute(
            text("SELECT id FROM companies WHERE slug = :slug"),
            {"slug": COMPANY_SLUG},
        ).fetchone()

        if existing_by_id:
            print("[0] Tenant exists (by ID) — cleaning seed data for re-seed...")
            _cleanup(db)
            counts["tenant"] = "cleaned + re-seeded"
        elif existing_by_slug:
            # A company with this slug exists but different ID (e.g. from API seed).
            # Use that company's ID instead of our hardcoded one.
            CFG["company_id"] = existing_by_slug[0]
            print(f"[0] Found existing company with slug '{COMPANY_SLUG}' (id={CFG['company_id'][:12]}...)")
            print("    Adopting existing company ID and cleaning data for re-seed...")
            _cleanup(db)
            counts["tenant"] = "adopted existing + re-seeded"
        else:
            counts["tenant"] = "created"

        # ---- 1. Company ----
        print("[1] Creating tenant...")
        _seed_company(db)

        # ---- 2. Roles ----
        print("[2] Creating roles...")
        role_ids = _seed_roles(db)

        # ---- 3. Users ----
        print("[3] Creating users...")
        admin_id = _seed_users(db, role_ids)

        # ---- 3b. Permission overrides for office_finance ----
        print("[3b] Creating permission overrides...")
        _seed_permission_overrides(db, admin_id)

        # ---- 4. Company Entities + Customers ----
        print("[4] Creating funeral homes (company_entities + customers)...")
        fh_entities, customer_ids = _seed_funeral_homes(db, admin_id)

        # ---- 5. Contacts ----
        print("[5] Creating contacts...")
        _seed_contacts(db, fh_entities)

        # ---- 6. Cemetery entities + cemeteries ----
        print("[6] Creating cemeteries...")
        cemetery_ids = _seed_cemeteries(db)

        # ---- 7. Product categories + products ----
        print("[7] Creating products...")
        product_map = _seed_products(db, admin_id)

        # ---- 8. Orders ----
        print("[8] Creating orders...")
        order_ids = _seed_orders(db, customer_ids, cemetery_ids, product_map, admin_id)

        # ---- 9. Invoices ----
        print("[9] Creating invoices...")
        _seed_invoices(db, customer_ids, product_map, admin_id)

        # ---- 10. Price list version ----
        print("[10] Creating price list version...")
        _seed_price_list(db, product_map, admin_id)

        # ---- 11. KB ----
        print("[11] Creating knowledge base...")
        _seed_kb(db, admin_id, product_map)

        # ---- 12. Modules ----
        print("[12] Enabling modules...")
        _seed_modules(db)

        # ---- 13. Delivery settings ----
        print("[13] Creating delivery settings...")
        _seed_delivery_settings(db)

        db.commit()
        print()

    # ---- Summary ----
    print("=" * 50)
    print("SEED SUMMARY")
    print("=" * 50)
    print(f"  Tenant:           {counts['tenant']}")
    print(f"  Roles:            {counts['roles']} created")
    print(f"  Users:            {counts['users']} created")
    print(f"  Company entities: {counts['company_entities']} created")
    print(f"  Customers:        {counts['customers']} created")
    print(f"  Contacts:         {counts['contacts']} created")
    print(f"  Cemeteries:       {counts['cemeteries']} created")
    print(f"  Categories:       {counts['categories']} created")
    print(f"  Products:         {counts['products']} created")
    print(f"  Orders:           {counts['orders']} created ({counts['order_lines']} lines)")
    print(f"  Invoices:         {counts['invoices']} created ({counts['invoice_lines']} lines)")
    print(f"  Payments:         {counts['payments']} created")
    print(f"  Price list:       {counts['price_list']}")
    print(f"  KB categories:    {counts['kb_categories']} created")
    print(f"  KB documents:     {counts['kb_documents']} created")
    print()
    print(f"  Login: admin@testco.com / TestAdmin123!")
    print(f"  Slug:  {COMPANY_SLUG}")


# ===========================================================================
# Cleanup — delete seed data in correct FK order
# ===========================================================================

def _cleanup(db: Session):
    """Remove all data for the staging tenant so we can re-seed cleanly."""
    _run_cleanup_deletes(db, CFG["company_id"])


def _cleanup_company_id(db: Session, cid: str):
    """Remove all data for a specific company_id (used when replacing an API-seeded company)."""
    _run_cleanup_deletes(db, cid)


def _run_cleanup_deletes(db: Session, cid: str):
    """Delete all tenant data. Uses dynamic FK discovery to catch every referencing table."""
    # First, discover ALL tables that reference companies via company_id or tenant_id
    fk_rows = db.execute(text("""
        SELECT DISTINCT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'companies'
          AND ccu.column_name = 'id'
        ORDER BY tc.table_name
    """)).fetchall()

    # Build ordered delete list: leaf tables first, then parent tables
    # Start with known deep children that reference other tenant tables (not companies directly)
    deep_children = [
        "DELETE FROM kb_chunks WHERE tenant_id = :cid",
        "DELETE FROM kb_pricing_entries WHERE tenant_id = :cid",
        "DELETE FROM kb_extension_notifications WHERE tenant_id = :cid",
        "DELETE FROM price_list_items WHERE tenant_id = :cid",
        "DELETE FROM price_list_templates WHERE tenant_id = :cid",
        "DELETE FROM price_update_settings WHERE tenant_id = :cid",
        "DELETE FROM platform_email_settings WHERE tenant_id = :cid",
        "DELETE FROM customer_payment_applications WHERE payment_id IN (SELECT id FROM customer_payments WHERE company_id = :cid)",
        "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = :cid)",
        "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :cid)",
        "DELETE FROM user_permission_overrides WHERE user_id IN (SELECT id FROM users WHERE company_id = :cid)",
        "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE company_id = :cid)",
        "DELETE FROM user_ai_preferences WHERE user_id IN (SELECT id FROM users WHERE company_id = :cid)",
    ]

    # Then delete from all FK-referencing tables discovered dynamically
    fk_deletes = []
    for row in fk_rows:
        tbl, col = row[0], row[1]
        if tbl == "companies":
            continue  # skip self-references
        fk_deletes.append(f"DELETE FROM {tbl} WHERE {col} = :cid")

    all_stmts = deep_children + fk_deletes

    for stmt in all_stmts:
        try:
            db.execute(text("SAVEPOINT cleanup_sp"))
            db.execute(text(stmt), {"cid": cid})
            db.execute(text("RELEASE SAVEPOINT cleanup_sp"))
        except Exception:
            try:
                db.execute(text("ROLLBACK TO SAVEPOINT cleanup_sp"))
            except Exception:
                pass
    db.flush()


# ===========================================================================
# Seed functions
# ===========================================================================

def _seed_company(db: Session):
    existing = db.execute(
        text("SELECT id FROM companies WHERE id = :id"), {"id": CFG["company_id"]}
    ).fetchone()
    if existing:
        # Update in case fields changed
        db.execute(text("""
            UPDATE companies SET name = :name, slug = :slug, vertical = :vertical,
                is_active = true, updated_at = :now
            WHERE id = :id
        """), {"id": CFG["company_id"], "name": COMPANY_NAME, "slug": COMPANY_SLUG,
               "vertical": "manufacturing", "now": NOW})
    else:
        db.execute(text("""
            INSERT INTO companies (id, name, slug, vertical, is_active, timezone,
                                   created_at, updated_at)
            VALUES (:id, :name, :slug, :vertical, true, :tz, :now, :now)
        """), {"id": CFG["company_id"], "name": COMPANY_NAME, "slug": COMPANY_SLUG,
               "vertical": "manufacturing", "tz": "America/New_York", "now": NOW})
    db.flush()


def _seed_roles(db: Session):
    roles = [
        ("admin", "Admin", "Full access to all features"),
        ("accountant", "Accountant", "Financial operations and reporting"),
        ("office_staff", "Office Staff", "Office operations and order management"),
        ("driver", "Driver", "Delivery routes and confirmations"),
        ("production", "Production", "Production floor and inventory"),
    ]
    # Permission sets per role (admin gets wildcard via permission_service, no rows needed)
    role_permissions_map = {
        "accountant": ACCOUNTANT_DEFAULT_PERMISSIONS,
        "office_staff": OFFICE_STAFF_DEFAULT_PERMISSIONS,
        "driver": DRIVER_DEFAULT_PERMISSIONS,
        "production": PRODUCTION_DEFAULT_PERMISSIONS,
    }
    role_ids = {}
    for slug, name, desc in roles:
        # Check if role already exists (from prior API seed or company registration)
        existing = db.execute(text("""
            SELECT id FROM roles WHERE company_id = :cid AND slug = :slug
        """), {"cid": CFG["company_id"], "slug": slug}).fetchone()
        if existing:
            role_ids[slug] = existing[0]
            print(f"    -> Role '{slug}' already exists")
        else:
            rid = uid()
            db.execute(text("""
                INSERT INTO roles (id, company_id, name, slug, description, is_system, is_active,
                                   created_at, updated_at)
                VALUES (:id, :cid, :name, :slug, :desc, true, true, :now, :now)
            """), {"id": rid, "cid": CFG["company_id"], "name": name, "slug": slug,
                   "desc": desc, "now": NOW})
            role_ids[slug] = rid
            counts["roles"] += 1

    # Seed role_permissions for non-admin roles
    for slug, perms in role_permissions_map.items():
        rid = role_ids[slug]
        # Check existing permissions count
        existing_count = db.execute(text("""
            SELECT COUNT(*) FROM role_permissions WHERE role_id = :rid
        """), {"rid": rid}).scalar()
        if existing_count and existing_count >= len(perms):
            print(f"    -> Role '{slug}' already has {existing_count} permissions")
            continue
        # Clear and re-seed permissions
        db.execute(text("DELETE FROM role_permissions WHERE role_id = :rid"), {"rid": rid})
        for perm_key in perms:
            db.execute(text("""
                INSERT INTO role_permissions (id, role_id, permission_key)
                VALUES (:id, :rid, :perm)
            """), {"id": uid(), "rid": rid, "perm": perm_key})
        print(f"    -> Seeded {len(perms)} permissions for '{slug}'")

    db.flush()
    return role_ids


def _seed_users(db: Session, role_ids: dict) -> str:
    users = [
        ("admin@testco.com", "TestAdmin123!", "Admin", "User", "admin"),
        ("accountant@testco.com", "TestAccountant123!", "Alex", "Accountant", "accountant"),
        ("office@testco.com", "TestOffice123!", "Office", "Staff", "office_staff"),
        ("office_finance@testco.com", "TestOffice123!", "Fiona", "Finance", "office_staff"),
        ("driver@testco.com", "TestDriver123!", "Dave", "Driver", "driver"),
        ("production@testco.com", "TestProd123!", "Paul", "Producer", "production"),
        ("prodmanager@testco.com", "TestProd123!", "Pete", "Manager", "production"),
    ]
    admin_id = None
    for email, password, first, last, role_slug in users:
        # Check if user already exists
        existing = db.execute(text("""
            SELECT id FROM users WHERE company_id = :cid AND email = :email
        """), {"cid": CFG["company_id"], "email": email}).fetchone()
        if existing:
            if role_slug == "admin":
                admin_id = existing[0]
            # Update password to ensure test credentials work
            hashed = hash_password(password)
            db.execute(text("""
                UPDATE users SET hashed_password = :pw, first_name = :first,
                    last_name = :last, role_id = :rid, is_active = true, updated_at = :now
                WHERE id = :id
            """), {"pw": hashed, "first": first, "last": last,
                   "rid": role_ids[role_slug], "now": NOW, "id": existing[0]})
            print(f"    -> User '{email}' already exists (password updated)")
        else:
            user_id = uid()
            if role_slug == "admin":
                admin_id = user_id
            hashed = hash_password(password)
            db.execute(text("""
                INSERT INTO users (id, company_id, email, hashed_password, first_name, last_name,
                                   role_id, is_active, created_at, updated_at)
                VALUES (:id, :cid, :email, :pw, :first, :last, :rid, true, :now, :now)
            """), {"id": user_id, "cid": CFG["company_id"], "email": email, "pw": hashed,
                   "first": first, "last": last, "rid": role_ids[role_slug], "now": NOW})
            counts["users"] += 1
    db.flush()
    return admin_id


def _seed_permission_overrides(db: Session, admin_id: str):
    """Grant financial permissions to office_finance user via permission overrides."""
    # Find office_finance user
    row = db.execute(text("""
        SELECT id FROM users WHERE company_id = :cid AND email = :email
    """), {"cid": CFG["company_id"], "email": "office_finance@testco.com"}).fetchone()
    if not row:
        print("    -> office_finance user not found, skipping overrides")
        return
    user_id = row[0]

    overrides = [
        "financials.view",
        "financials.ar.view",
        "financials.invoices.view",
        "invoice.approve",
    ]
    for perm_key in overrides:
        existing = db.execute(text("""
            SELECT id FROM user_permission_overrides
            WHERE user_id = :uid AND permission_key = :perm
        """), {"uid": user_id, "perm": perm_key}).fetchone()
        if existing:
            continue
        db.execute(text("""
            INSERT INTO user_permission_overrides (id, user_id, permission_key, granted,
                granted_by_user_id, notes, created_at)
            VALUES (:id, :uid, :perm, true, :admin, :notes, :now)
        """), {"id": uid(), "uid": user_id, "perm": perm_key, "admin": admin_id,
               "notes": "Seeded for testing — office staff with financial access", "now": NOW})
    print(f"    -> Granted {len(overrides)} permission overrides to office_finance")
    db.flush()


def _seed_funeral_homes(db: Session, admin_id: str):
    """Create company_entities (CRM) + linked customers."""
    fhs = [
        ("Johnson Funeral Home", "315-555-0101", "orders@johnsonfh.com", "Auburn", "NY"),
        ("Smith & Sons Funeral Home", "315-555-0102", "smith@smithfh.com", "Syracuse", "NY"),
        ("Memorial Chapel", "315-555-0103", "info@memorialchapel.com", "Skaneateles", "NY"),
        ("Riverside Funeral Home", "315-555-0104", "riverside@funerals.com", "Ithaca", "NY"),
        ("Green Valley Memorial", "315-555-0105", "gvm@greenvalley.com", "Cortland", "NY"),
    ]
    entity_ids = {}
    customer_ids = {}
    for name, phone, email, city, state in fhs:
        # Company entity (CRM)
        eid = uid()
        db.execute(text("""
            INSERT INTO company_entities (id, company_id, name, phone, email, city, state,
                is_customer, is_funeral_home, is_active, is_active_customer,
                customer_type, classification_source,
                created_by, created_at, updated_at)
            VALUES (:id, :cid, :name, :phone, :email, :city, :state,
                true, true, true, true,
                'funeral_home', 'manual',
                :admin, :now, :now)
        """), {"id": eid, "cid": CFG["company_id"], "name": name, "phone": phone,
               "email": email, "city": city, "state": state, "admin": admin_id, "now": NOW})
        entity_ids[name] = eid
        counts["company_entities"] += 1

        # Linked customer record
        cid = uid()
        acct = f"FH-{counts['customers'] + 1:03d}"
        db.execute(text("""
            INSERT INTO customers (id, company_id, name, account_number, email, phone,
                city, state, customer_type, payment_terms, is_active,
                master_company_id, created_at, updated_at)
            VALUES (:id, :cid, :name, :acct, :email, :phone,
                :city, :state, 'funeral_home', 'net_30', true,
                :eid, :now, :now)
        """), {"id": cid, "cid": CFG["company_id"], "name": name, "acct": acct,
               "email": email, "phone": phone, "city": city, "state": state,
               "eid": eid, "now": NOW})
        customer_ids[name] = cid
        counts["customers"] += 1

    db.flush()
    return entity_ids, customer_ids


def _seed_contacts(db: Session, fh_entities: dict):
    """Create 2 contacts per funeral home."""
    contact_data = {
        "Johnson Funeral Home": [
            ("Jane Director", "Director", "jane@johnsonfh.com", "315-555-1001", True),
            ("Bob Manager", "Office Manager", "bob@johnsonfh.com", "315-555-1002", False),
        ],
        "Smith & Sons Funeral Home": [
            ("Tom Smith", "Owner/Director", "tom@smithfh.com", "315-555-2001", True),
            ("Sarah Smith", "Funeral Director", "sarah@smithfh.com", "315-555-2002", False),
        ],
        "Memorial Chapel": [
            ("Mike Chapel", "Director", "mike@memorialchapel.com", "315-555-3001", True),
            ("Lisa Coordinator", "Service Coordinator", "lisa@memorialchapel.com", "315-555-3002", False),
        ],
        "Riverside Funeral Home": [
            ("Karen Rivers", "Director", "karen@riverside.com", "315-555-4001", True),
            ("Jim Associate", "Associate Director", "jim@riverside.com", "315-555-4002", False),
        ],
        "Green Valley Memorial": [
            ("Dan Green", "Owner", "dan@greenvalley.com", "315-555-5001", True),
            ("Amy Planner", "Pre-Need Counselor", "amy@greenvalley.com", "315-555-5002", False),
        ],
    }
    for fh_name, contacts in contact_data.items():
        eid = fh_entities.get(fh_name)
        if not eid:
            continue
        for name, title, email, phone, is_primary in contacts:
            db.execute(text("""
                INSERT INTO contacts (id, company_id, master_company_id, name, title,
                    email, phone, is_primary, is_active, receives_invoices,
                    created_at, updated_at)
                VALUES (:id, :cid, :eid, :name, :title,
                    :email, :phone, :primary, true, :recv_inv,
                    :now, :now)
            """), {"id": uid(), "cid": CFG["company_id"], "eid": eid, "name": name,
                   "title": title, "email": email, "phone": phone,
                   "primary": is_primary, "recv_inv": is_primary, "now": NOW})
            counts["contacts"] += 1
    db.flush()


def _seed_cemeteries(db: Session):
    """Create cemetery company_entities + cemetery records."""
    cems = [
        ("Oakwood Cemetery", "Auburn", "NY", False, False, False),
        ("St. Mary's Cemetery", "Skaneateles", "NY", True, True, True),
        ("Lakeview Memorial Gardens", "Syracuse", "NY", False, False, False),
    ]
    cemetery_ids = {}
    for name, city, state, ld, grass, tent in cems:
        # Company entity
        eid = uid()
        db.execute(text("""
            INSERT INTO company_entities (id, company_id, name, city, state,
                is_cemetery, is_active, customer_type, classification_source,
                created_at, updated_at)
            VALUES (:id, :cid, :name, :city, :state, true, true,
                'cemetery', 'manual', :now, :now)
        """), {"id": eid, "cid": CFG["company_id"], "name": name, "city": city,
               "state": state, "now": NOW})
        counts["company_entities"] += 1

        # Cemetery record
        cid = uid()
        db.execute(text("""
            INSERT INTO cemeteries (id, company_id, name, city, state,
                cemetery_provides_lowering_device, cemetery_provides_grass,
                cemetery_provides_tent, master_company_id, is_active,
                created_at, updated_at)
            VALUES (:id, :cid, :name, :city, :state, :ld, :grass, :tent,
                :eid, true, :now, :now)
        """), {"id": cid, "cid": CFG["company_id"], "name": name, "city": city,
               "state": state, "ld": ld, "grass": grass, "tent": tent,
               "eid": eid, "now": NOW})
        cemetery_ids[name] = cid
        counts["cemeteries"] += 1
    db.flush()
    return cemetery_ids


def _seed_products(db: Session, admin_id: str):
    """Create product categories and products. Returns {product_name: (id, price, sku)}."""
    categories = {
        "Burial Vaults - Triple Reinforced": [
            ("Wilbert Bronze", "WB-001", 13452.00),
        ],
        "Burial Vaults - Double Reinforced": [
            ("Bronze Triune", "BT-001", 3864.00),
            ("Copper Triune", "CT-001", 3457.00),
            ("SST Triune", "SST-001", 2850.00),
            ("Cameo Rose", "CR-001", 2850.00),
            ("Veteran Triune", "VT-001", 2850.00),
        ],
        "Burial Vaults - Single Reinforced": [
            ("Tribute", "TR-001", 2570.00),
            ("Venetian", "VN-001", 1934.00),
            ("Continental", "CN-001", 1607.00),
            ("Salute", "SL-001", 1475.00),
            ("Monticello", "MN-001", 1405.00),
        ],
        "Burial Vaults - Non Reinforced": [
            ("Monarch", "MO-001", 1176.00),
            ("Graveliner", "GL-001", 996.00),
            ("Graveliner SS", "GS-001", 880.00),
        ],
        "Graveside Service": [
            ("Full Equipment (with product)", "FE-WP", 300.00),
            ("Full Equipment (without product)", "FE-NP", 600.00),
            ("Lowering Device & Grass (with)", "LD-WP", 185.00),
            ("Lowering Device & Grass (without)", "LD-NP", 487.00),
            ("Tent Only (with)", "TO-WP", 225.00),
            ("Tent Only (without)", "TO-NP", 557.00),
        ],
        "Other Charges": [
            ("Sunday & Holiday", "SH-001", 550.00),
            ("Saturday Spring Burial", "SSB-001", 200.00),
            ("Late Arrival per 30 min", "LA-001", 75.00),
            ("Legacy Rush Fee", "LR-001", 100.00),
            ("Late Notice", "LN-001", 250.00),
        ],
    }

    product_map = {}  # name -> (id, price, sku)

    for cat_name, products in categories.items():
        cat_id = uid()
        db.execute(text("""
            INSERT INTO product_categories (id, company_id, name, is_active,
                created_at, updated_at, created_by)
            VALUES (:id, :cid, :name, true, :now, :now, :admin)
        """), {"id": cat_id, "cid": CFG["company_id"], "name": cat_name,
               "now": NOW, "admin": admin_id})
        counts["categories"] += 1

        for pname, sku, price in products:
            pid = uid()
            db.execute(text("""
                INSERT INTO products (id, company_id, category_id, name, sku, price,
                    is_active, created_at, updated_at, created_by)
                VALUES (:id, :cid, :catid, :name, :sku, :price,
                    true, :now, :now, :admin)
            """), {"id": pid, "cid": CFG["company_id"], "catid": cat_id,
                   "name": pname, "sku": sku, "price": price,
                   "now": NOW, "admin": admin_id})
            product_map[pname] = (pid, Decimal(str(price)), sku)
            counts["products"] += 1

    db.flush()
    return product_map


def _seed_orders(db: Session, customer_ids: dict, cemetery_ids: dict,
                 product_map: dict, admin_id: str):
    """Create 10 orders spread across the last 30 days."""

    orders_spec = [
        # (customer, cemetery, deceased, vault, equip, status, days_ago, sched_today)
        ("Johnson Funeral Home", "Oakwood Cemetery", "Margaret Sullivan", "Bronze Triune", "Full Equipment (with product)", "draft", 2, False),
        ("Smith & Sons Funeral Home", "St. Mary's Cemetery", "Robert Williams", "SST Triune", "Lowering Device & Grass (with)", "draft", 1, False),
        ("Johnson Funeral Home", "Oakwood Cemetery", "Dorothy Anderson", "Venetian", "Full Equipment (with product)", "confirmed", 8, False),
        ("Smith & Sons Funeral Home", "Oakwood Cemetery", "James Mitchell", "Tribute", "Tent Only (with)", "confirmed", 0, True),
        ("Johnson Funeral Home", "St. Mary's Cemetery", "Patricia Thompson", "Continental", "Full Equipment (with product)", "confirmed", 15, False),
        ("Smith & Sons Funeral Home", "St. Mary's Cemetery", "William Davis", "Salute", "Lowering Device & Grass (with)", "processing", 0, True),
        ("Johnson Funeral Home", "Oakwood Cemetery", "Barbara Wilson", "Monticello", "Tent Only (with)", "processing", 0, True),
        ("Smith & Sons Funeral Home", "Oakwood Cemetery", "Richard Johnson", "Copper Triune", "Full Equipment (with product)", "completed", 22, False),
        ("Johnson Funeral Home", "St. Mary's Cemetery", "Helen Martinez", "Cameo Rose", "Full Equipment (with product)", "completed", 25, False),
        ("Smith & Sons Funeral Home", "St. Mary's Cemetery", "Charles Brown", "Veteran Triune", "Lowering Device & Grass (with)", "completed", 28, False),
    ]

    order_ids = []
    for i, (cust_name, cem_name, deceased, vault, equip, status, days_ago, sched_today) in enumerate(orders_spec, 1):
        oid = uid()
        order_date = NOW - timedelta(days=days_ago)
        so_number = f"SO-2026-{i:04d}"
        vault_pid, vault_price, _ = product_map[vault]
        equip_pid, equip_price, _ = product_map[equip]
        subtotal = vault_price + equip_price

        delivered_at = order_date + timedelta(days=1) if status == "completed" else None
        if sched_today:
            scheduled = date.today()
        elif status != "draft":
            scheduled = (order_date + timedelta(days=1)).date()
        else:
            scheduled = None

        db.execute(text("""
            INSERT INTO sales_orders (id, company_id, number, customer_id, cemetery_id,
                status, order_date, deceased_name, order_type, subtotal, total,
                scheduled_date, delivered_at, created_by, created_at)
            VALUES (:id, :cid, :num, :custid, :cemid,
                :status, :odate, :deceased, 'funeral', :sub, :total,
                :sched, :delivered, :admin, :odate)
        """), {
            "id": oid, "cid": CFG["company_id"], "num": so_number,
            "custid": customer_ids[cust_name], "cemid": cemetery_ids[cem_name],
            "status": status, "odate": order_date, "deceased": deceased,
            "sub": subtotal, "total": subtotal, "sched": scheduled,
            "delivered": delivered_at, "admin": admin_id,
        })
        counts["orders"] += 1

        # Order lines — vault + equipment
        for sort_idx, (prod_id, prod_price, desc) in enumerate([
            (vault_pid, vault_price, vault),
            (equip_pid, equip_price, equip),
        ]):
            db.execute(text("""
                INSERT INTO sales_order_lines (id, sales_order_id, product_id,
                    description, quantity, unit_price, line_total, sort_order)
                VALUES (:id, :oid, :pid, :desc, 1, :price, :price, :sort)
            """), {"id": uid(), "oid": oid, "pid": prod_id,
                   "desc": desc, "price": prod_price, "sort": sort_idx})
            counts["order_lines"] += 1

        order_ids.append(oid)

    db.flush()
    return order_ids


def _seed_invoices(db: Session, customer_ids: dict, product_map: dict, admin_id: str):
    """Create 3 invoices: 1 paid, 1 outstanding 30 days, 1 overdue 60 days."""

    invoices = [
        # (customer, product, status, days_ago, paid)
        ("Johnson Funeral Home", "Bronze Triune", "paid", 35, True),
        ("Smith & Sons Funeral Home", "SST Triune", "sent", 30, False),
        ("Memorial Chapel", "Venetian", "overdue", 60, False),
    ]

    for i, (cust_name, prod_name, status, days_ago, is_paid) in enumerate(invoices, 1):
        inv_id = uid()
        inv_date = NOW - timedelta(days=days_ago)
        due_date = inv_date + timedelta(days=30)
        prod_id, price, _ = product_map[prod_name]
        inv_number = f"INV-2026-{i:04d}"

        amount_paid = price if is_paid else Decimal("0.00")
        paid_at = inv_date + timedelta(days=15) if is_paid else None

        db.execute(text("""
            INSERT INTO invoices (id, company_id, number, customer_id, status,
                invoice_date, due_date, subtotal, total, amount_paid, paid_at,
                deceased_name, created_by, created_at)
            VALUES (:id, :cid, :num, :custid, :status,
                :inv_date, :due_date, :sub, :total, :paid, :paid_at,
                :deceased, :admin, :inv_date)
        """), {
            "id": inv_id, "cid": CFG["company_id"], "num": inv_number,
            "custid": customer_ids[cust_name], "status": status,
            "inv_date": inv_date, "due_date": due_date,
            "sub": price, "total": price, "paid": amount_paid,
            "paid_at": paid_at, "deceased": f"Estate of Client {i}",
            "admin": admin_id,
        })
        counts["invoices"] += 1

        # Invoice line
        db.execute(text("""
            INSERT INTO invoice_lines (id, invoice_id, product_id,
                description, quantity, unit_price, line_total, sort_order)
            VALUES (:id, :inv_id, :pid, :desc, 1, :price, :price, 0)
        """), {"id": uid(), "inv_id": inv_id, "pid": prod_id,
               "desc": prod_name, "price": price})
        counts["invoice_lines"] += 1

        # Payment for paid invoice
        if is_paid:
            pay_id = uid()
            db.execute(text("""
                INSERT INTO customer_payments (id, company_id, customer_id,
                    payment_date, total_amount, payment_method, reference_number,
                    created_by, created_at)
                VALUES (:id, :cid, :custid, :pdate, :amt, 'check', :ref,
                    :admin, :pdate)
            """), {
                "id": pay_id, "cid": CFG["company_id"],
                "custid": customer_ids[cust_name],
                "pdate": paid_at, "amt": price,
                "ref": f"CHK-{1000 + i}", "admin": admin_id,
            })
            # Payment application
            db.execute(text("""
                INSERT INTO customer_payment_applications (id, payment_id,
                    invoice_id, amount_applied)
                VALUES (:id, :payid, :invid, :amt)
            """), {"id": uid(), "payid": pay_id,
                   "invid": inv_id, "amt": price})
            counts["payments"] += 1

    db.flush()


def _seed_price_list(db: Session, product_map: dict, admin_id: str):
    """Create one active price list version with items for all products."""
    ver_id = uid()
    today = date.today()

    db.execute(text("""
        INSERT INTO price_list_versions (id, tenant_id, version_number, label,
            status, effective_date, activated_at, created_by_user_id, created_at)
        VALUES (:id, :tid, 1, :label, 'active', :eff, :now, :admin, :now)
    """), {"id": ver_id, "tid": CFG["company_id"], "label": "2026 Test Price List",
           "eff": today, "now": NOW, "admin": admin_id})

    # Build category lookup for display ordering
    category_order = {
        "Burial Vaults - Triple Reinforced": 10,
        "Burial Vaults - Double Reinforced": 20,
        "Burial Vaults - Single Reinforced": 30,
        "Burial Vaults - Non Reinforced": 40,
        "Graveside Service": 50,
        "Other Charges": 60,
    }

    # Query products with their categories for the price list items
    rows = db.execute(text("""
        SELECT p.id as product_id, p.name as product_name, p.sku, p.price,
               pc.name as category_name
        FROM products p
        LEFT JOIN product_categories pc ON p.category_id = pc.id
        WHERE p.company_id = :cid AND p.is_active = true
        ORDER BY pc.name, p.name
    """), {"cid": CFG["company_id"]}).fetchall()

    display = 0
    for row in rows:
        display += 1
        cat_order = category_order.get(row.category_name, 99)
        db.execute(text("""
            INSERT INTO price_list_items (id, tenant_id, version_id,
                product_name, product_code, category, standard_price,
                display_order, is_active, created_at, updated_at)
            VALUES (:id, :tid, :vid, :name, :code, :cat, :price,
                :disp, true, :now, :now)
        """), {
            "id": uid(), "tid": CFG["company_id"], "vid": ver_id,
            "name": row.product_name, "code": row.sku,
            "cat": row.category_name, "price": row.price,
            "disp": cat_order * 100 + display, "now": NOW,
        })

    counts["price_list"] = f"created (1 version, {len(rows)} items)"
    db.flush()


def _seed_kb(db: Session, admin_id: str, product_map: dict):
    """Create KB categories and one manual document."""
    kb_cats = [
        ("Product Pricing", "pricing", "Product pricing information and price lists", "DollarSign", 1),
        ("Product Specifications", "product_specs", "Technical specifications for burial vaults", "Package", 2),
        ("Personalization Options", "personalization_options", "Vault personalization and customization options", "Palette", 3),
        ("Company Policies", "company_policies", "Internal company policies and procedures", "FileText", 4),
        ("Cemetery Requirements", "cemetery_policies", "Cemetery-specific policies and requirements", "MapPin", 5),
    ]

    cat_ids = {}
    for name, slug, desc, icon, order in kb_cats:
        # Check if category exists (may have been auto-seeded)
        existing = db.execute(text("""
            SELECT id FROM kb_categories WHERE tenant_id = :tid AND slug = :slug
        """), {"tid": CFG["company_id"], "slug": slug}).fetchone()
        if existing:
            cat_ids[name] = existing[0]
            print(f"    -> KB category '{name}' already exists")
        else:
            cid = uid()
            db.execute(text("""
                INSERT INTO kb_categories (id, tenant_id, name, slug, description,
                    icon, display_order, is_system, created_at, updated_at)
                VALUES (:id, :tid, :name, :slug, :desc, :icon, :order, true, :now, :now)
            """), {"id": cid, "tid": CFG["company_id"], "name": name, "slug": slug,
                   "desc": desc, "icon": icon, "order": order, "now": NOW})
            cat_ids[name] = cid
            counts["kb_categories"] += 1

    # Create one manual pricing document
    pricing_content = "# Standard Vault Pricing 2026\n\n"
    pricing_content += "## Burial Vaults - Triple Reinforced\n"
    pricing_content += "- Wilbert Bronze: $13,452.00\n\n"
    pricing_content += "## Burial Vaults - Double Reinforced\n"
    for name in ["Bronze Triune", "Copper Triune", "SST Triune", "Cameo Rose", "Veteran Triune"]:
        _, price, _ = product_map[name]
        pricing_content += f"- {name}: ${price:,.2f}\n"
    pricing_content += "\n## Burial Vaults - Single Reinforced\n"
    for name in ["Tribute", "Venetian", "Continental", "Salute", "Monticello"]:
        _, price, _ = product_map[name]
        pricing_content += f"- {name}: ${price:,.2f}\n"
    pricing_content += "\n## Burial Vaults - Non Reinforced\n"
    for name in ["Monarch", "Graveliner", "Graveliner SS"]:
        _, price, _ = product_map[name]
        pricing_content += f"- {name}: ${price:,.2f}\n"
    pricing_content += "\n## Graveside Service\n"
    for name in ["Full Equipment (with product)", "Full Equipment (without product)",
                 "Lowering Device & Grass (with)", "Lowering Device & Grass (without)",
                 "Tent Only (with)", "Tent Only (without)"]:
        _, price, _ = product_map[name]
        pricing_content += f"- {name}: ${price:,.2f}\n"
    pricing_content += "\n## Other Charges\n"
    for name in ["Sunday & Holiday", "Saturday Spring Burial", "Late Arrival per 30 min",
                 "Legacy Rush Fee", "Late Notice"]:
        _, price, _ = product_map[name]
        pricing_content += f"- {name}: ${price:,.2f}\n"

    doc_id = uid()
    db.execute(text("""
        INSERT INTO kb_documents (id, tenant_id, category_id, title, description,
            raw_content, parsed_content, parsing_status, chunk_count,
            uploaded_by_user_id, is_active, created_at, updated_at)
        VALUES (:id, :tid, :catid, :title, :desc,
            :raw, :parsed, 'complete', 1,
            :admin, true, :now, :now)
    """), {
        "id": doc_id, "tid": CFG["company_id"], "catid": cat_ids["Product Pricing"],
        "title": "Standard Vault Pricing 2026",
        "desc": "Complete pricing for all burial vaults and services",
        "raw": pricing_content, "parsed": pricing_content,
        "admin": admin_id, "now": NOW,
    })
    counts["kb_documents"] += 1
    db.flush()


def _seed_modules(db: Session):
    """Enable all core modules for the staging tenant."""
    modules = [
        "sales", "products", "inventory", "driver_delivery", "purchasing",
        "safety", "hr_time", "pos",
    ]
    for mod in modules:
        existing = db.execute(text("""
            SELECT id FROM company_modules WHERE company_id = :cid AND module = :mod
        """), {"cid": CFG["company_id"], "mod": mod}).fetchone()
        if existing:
            db.execute(text("""
                UPDATE company_modules SET enabled = true WHERE id = :id
            """), {"id": existing[0]})
        else:
            db.execute(text("""
                INSERT INTO company_modules (id, company_id, module, enabled, created_at, updated_at)
                VALUES (:id, :cid, :mod, true, :now, :now)
            """), {"id": uid(), "cid": CFG["company_id"], "mod": mod, "now": NOW})
    print(f"    -> Enabled {len(modules)} modules")
    db.flush()


def _seed_delivery_settings(db: Session):
    """Create delivery_settings row for auto-delivery to work."""
    existing = db.execute(text("""
        SELECT id FROM delivery_settings WHERE company_id = :cid
    """), {"cid": CFG["company_id"]}).fetchone()
    if existing:
        db.execute(text("""
            UPDATE delivery_settings SET invoice_generation_mode = 'end_of_day',
                require_driver_status_updates = false, modified_at = :now
            WHERE id = :id
        """), {"id": existing[0], "now": NOW})
        print("    -> Delivery settings already exist (updated)")
    else:
        db.execute(text("""
            INSERT INTO delivery_settings (id, company_id, preset, invoice_generation_mode,
                require_driver_status_updates,
                require_photo_on_delivery, require_signature, require_weight_ticket,
                require_setup_confirmation, require_departure_photo, require_mileage_entry,
                allow_partial_delivery, allow_driver_resequence, track_gps,
                notify_customer_on_dispatch, notify_customer_on_arrival,
                notify_customer_on_complete, notify_connected_tenant_on_arrival,
                notify_connected_tenant_on_setup,
                enable_driver_messaging, enable_delivery_portal,
                auto_create_delivery_from_order, auto_invoice_on_complete,
                show_en_route_button, show_exception_button, show_delivered_button,
                show_equipment_checklist, show_funeral_home_contact,
                show_cemetery_contact, show_get_directions, show_call_office_button,
                require_personalization_complete, sms_carrier_updates, carrier_portal,
                created_at)
            VALUES (:id, :cid, 'standard', 'end_of_day',
                false,
                false, false, false,
                false, false, false,
                false, false, false,
                false, false,
                false, false,
                false,
                false, false,
                true, false,
                true, true, true,
                false, true,
                true, true, true,
                false, false, false,
                :now)
        """), {"id": uid(), "cid": CFG["company_id"], "now": NOW})
        print("    -> Created delivery settings (end_of_day mode)")
    db.flush()


# ===========================================================================
if __name__ == "__main__":
    main()
