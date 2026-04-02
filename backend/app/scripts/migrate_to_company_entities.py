"""Migrate existing customers, vendors, and cemeteries to the company_entities table.

Run once after the r44 migration:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python -m app.scripts.migrate_to_company_entities

Idempotent — safe to run multiple times. Skips records that already have
master_company_id set.
"""

import os
import sys
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run():
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev")
    engine = create_engine(db_url)

    stats = {
        "customers_migrated": 0,
        "customers_skipped": 0,
        "vendors_migrated": 0,
        "vendors_auto_merged": 0,
        "vendors_needs_review": 0,
        "vendors_new": 0,
        "vendors_skipped": 0,
        "cemeteries_migrated": 0,
        "cemeteries_auto_merged": 0,
        "cemeteries_needs_review": 0,
        "cemeteries_new": 0,
        "cemeteries_skipped": 0,
        "entities_created": 0,
    }

    with Session(engine) as db:
        # ── Step 1: Migrate customers ────────────────────────────────────
        print("\n=== Step 1: Migrating customers ===")
        customers = db.execute(text(
            "SELECT id, company_id, name, phone, email, website, "
            "address_line1, address_line2, city, state, zip_code, country, "
            "customer_type, master_company_id "
            "FROM customers WHERE is_active = true"
        )).fetchall()

        for c in customers:
            if c.master_company_id:
                stats["customers_skipped"] += 1
                continue

            eid = str(uuid.uuid4())
            is_fh = (c.customer_type or "").lower() in ("funeral_home", "funeral home")
            is_cem = (c.customer_type or "").lower() in ("cemetery",)

            db.execute(text(
                "INSERT INTO company_entities "
                "(id, company_id, name, phone, email, website, "
                "address_line1, address_line2, city, state, zip, country, "
                "is_customer, is_funeral_home, is_cemetery, is_active) "
                "VALUES (:id, :cid, :name, :phone, :email, :website, "
                ":a1, :a2, :city, :state, :zip, :country, "
                "true, :is_fh, :is_cem, true)"
            ), {
                "id": eid, "cid": c.company_id, "name": c.name,
                "phone": c.phone, "email": c.email, "website": c.website,
                "a1": c.address_line1, "a2": c.address_line2,
                "city": c.city, "state": c.state, "zip": c.zip_code,
                "country": c.country or "US",
                "is_fh": is_fh, "is_cem": is_cem,
            })

            db.execute(text(
                "UPDATE customers SET master_company_id = :eid WHERE id = :cid"
            ), {"eid": eid, "cid": c.id})

            stats["customers_migrated"] += 1
            stats["entities_created"] += 1

        db.commit()
        print(f"  Migrated: {stats['customers_migrated']}, Skipped: {stats['customers_skipped']}")

        # ── Step 2: Migrate vendors ──────────────────────────────────────
        print("\n=== Step 2: Migrating vendors ===")
        vendors = db.execute(text(
            "SELECT id, company_id, name, phone, email, website, "
            "address_line1, address_line2, city, state, zip_code, country, "
            "master_company_id "
            "FROM vendors WHERE is_active = true"
        )).fetchall()

        for v in vendors:
            if v.master_company_id:
                stats["vendors_skipped"] += 1
                continue

            # Fuzzy match against existing entities for this tenant
            match = db.execute(text(
                "SELECT id, name, SIMILARITY(name, :vname) as score "
                "FROM company_entities "
                "WHERE company_id = :tid AND is_active = true "
                "ORDER BY SIMILARITY(name, :vname) DESC "
                "LIMIT 1"
            ), {"vname": v.name, "tid": v.company_id}).fetchone()

            if match and match.score and Decimal(str(match.score)) >= Decimal("0.85"):
                # HIGH CONFIDENCE — auto-merge
                db.execute(text(
                    "UPDATE company_entities SET is_vendor = true WHERE id = :eid"
                ), {"eid": match.id})
                db.execute(text(
                    "UPDATE vendors SET master_company_id = :eid WHERE id = :vid"
                ), {"eid": match.id, "vid": v.id})
                print(f"  AUTO-MERGED: vendor '{v.name}' → entity '{match.name}' (score: {match.score:.3f})")
                stats["vendors_auto_merged"] += 1
                stats["vendors_migrated"] += 1

            elif match and match.score and Decimal(str(match.score)) >= Decimal("0.60"):
                # UNCERTAIN — create new + review record
                eid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_entities "
                    "(id, company_id, name, phone, email, website, "
                    "address_line1, address_line2, city, state, zip, country, "
                    "is_vendor, is_active) "
                    "VALUES (:id, :cid, :name, :phone, :email, :website, "
                    ":a1, :a2, :city, :state, :zip, :country, true, true)"
                ), {
                    "id": eid, "cid": v.company_id, "name": v.name,
                    "phone": v.phone, "email": v.email, "website": v.website,
                    "a1": v.address_line1, "a2": v.address_line2,
                    "city": v.city, "state": v.state, "zip": v.zip_code,
                    "country": v.country or "US",
                })
                db.execute(text(
                    "UPDATE vendors SET master_company_id = :eid WHERE id = :vid"
                ), {"eid": eid, "vid": v.id})

                # Create review record
                rid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_migration_reviews "
                    "(id, tenant_id, source_type, source_id, source_name, "
                    "suggested_company_id, suggested_company_name, similarity_score, "
                    "current_company_id, status) "
                    "VALUES (:id, :tid, 'vendor', :sid, :sname, "
                    ":sug_id, :sug_name, :score, :cur_id, 'pending')"
                ), {
                    "id": rid, "tid": v.company_id,
                    "sid": v.id, "sname": v.name,
                    "sug_id": match.id, "sug_name": match.name,
                    "score": float(match.score), "cur_id": eid,
                })

                print(f"  NEEDS REVIEW: vendor '{v.name}' possible match '{match.name}' (score: {match.score:.3f})")
                stats["vendors_needs_review"] += 1
                stats["vendors_migrated"] += 1
                stats["entities_created"] += 1

            else:
                # NO MATCH — create new entity
                eid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_entities "
                    "(id, company_id, name, phone, email, website, "
                    "address_line1, address_line2, city, state, zip, country, "
                    "is_vendor, is_active) "
                    "VALUES (:id, :cid, :name, :phone, :email, :website, "
                    ":a1, :a2, :city, :state, :zip, :country, true, true)"
                ), {
                    "id": eid, "cid": v.company_id, "name": v.name,
                    "phone": v.phone, "email": v.email, "website": v.website,
                    "a1": v.address_line1, "a2": v.address_line2,
                    "city": v.city, "state": v.state, "zip": v.zip_code,
                    "country": v.country or "US",
                })
                db.execute(text(
                    "UPDATE vendors SET master_company_id = :eid WHERE id = :vid"
                ), {"eid": eid, "vid": v.id})
                stats["vendors_new"] += 1
                stats["vendors_migrated"] += 1
                stats["entities_created"] += 1

        db.commit()
        print(f"  Migrated: {stats['vendors_migrated']} "
              f"(auto-merged: {stats['vendors_auto_merged']}, "
              f"review: {stats['vendors_needs_review']}, "
              f"new: {stats['vendors_new']})")

        # ── Step 3: Migrate cemeteries ───────────────────────────────────
        print("\n=== Step 3: Migrating cemeteries ===")
        cemeteries = db.execute(text(
            "SELECT id, company_id, name, phone, address, city, state, zip_code, "
            "master_company_id "
            "FROM cemeteries WHERE is_active = true"
        )).fetchall()

        for cem in cemeteries:
            if cem.master_company_id:
                stats["cemeteries_skipped"] += 1
                continue

            match = db.execute(text(
                "SELECT id, name, SIMILARITY(name, :cname) as score "
                "FROM company_entities "
                "WHERE company_id = :tid AND is_active = true "
                "ORDER BY SIMILARITY(name, :cname) DESC "
                "LIMIT 1"
            ), {"cname": cem.name, "tid": cem.company_id}).fetchone()

            if match and match.score and Decimal(str(match.score)) >= Decimal("0.85"):
                db.execute(text(
                    "UPDATE company_entities SET is_cemetery = true WHERE id = :eid"
                ), {"eid": match.id})
                db.execute(text(
                    "UPDATE cemeteries SET master_company_id = :eid WHERE id = :cid"
                ), {"eid": match.id, "cid": cem.id})
                print(f"  AUTO-MERGED: cemetery '{cem.name}' → entity '{match.name}' (score: {match.score:.3f})")
                stats["cemeteries_auto_merged"] += 1

            elif match and match.score and Decimal(str(match.score)) >= Decimal("0.60"):
                eid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_entities "
                    "(id, company_id, name, phone, address_line1, city, state, zip, "
                    "is_cemetery, is_active) "
                    "VALUES (:id, :cid, :name, :phone, :a1, :city, :state, :zip, true, true)"
                ), {
                    "id": eid, "cid": cem.company_id, "name": cem.name,
                    "phone": cem.phone, "a1": cem.address,
                    "city": cem.city, "state": cem.state, "zip": cem.zip_code,
                })
                db.execute(text(
                    "UPDATE cemeteries SET master_company_id = :eid WHERE id = :cid"
                ), {"eid": eid, "cid": cem.id})

                rid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_migration_reviews "
                    "(id, tenant_id, source_type, source_id, source_name, "
                    "suggested_company_id, suggested_company_name, similarity_score, "
                    "current_company_id, status) "
                    "VALUES (:id, :tid, 'cemetery', :sid, :sname, "
                    ":sug_id, :sug_name, :score, :cur_id, 'pending')"
                ), {
                    "id": rid, "tid": cem.company_id,
                    "sid": cem.id, "sname": cem.name,
                    "sug_id": match.id, "sug_name": match.name,
                    "score": float(match.score), "cur_id": eid,
                })
                print(f"  NEEDS REVIEW: cemetery '{cem.name}' possible match '{match.name}' (score: {match.score:.3f})")
                stats["cemeteries_needs_review"] += 1
                stats["entities_created"] += 1

            else:
                eid = str(uuid.uuid4())
                db.execute(text(
                    "INSERT INTO company_entities "
                    "(id, company_id, name, phone, address_line1, city, state, zip, "
                    "is_cemetery, is_active) "
                    "VALUES (:id, :cid, :name, :phone, :a1, :city, :state, :zip, true, true)"
                ), {
                    "id": eid, "cid": cem.company_id, "name": cem.name,
                    "phone": cem.phone, "a1": cem.address,
                    "city": cem.city, "state": cem.state, "zip": cem.zip_code,
                })
                db.execute(text(
                    "UPDATE cemeteries SET master_company_id = :eid WHERE id = :cid"
                ), {"eid": eid, "cid": cem.id})
                stats["cemeteries_new"] += 1
                stats["entities_created"] += 1

            stats["cemeteries_migrated"] += 1

        db.commit()
        print(f"  Migrated: {stats['cemeteries_migrated']} "
              f"(auto-merged: {stats['cemeteries_auto_merged']}, "
              f"review: {stats['cemeteries_needs_review']}, "
              f"new: {stats['cemeteries_new']})")

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("MIGRATION SUMMARY")
    print("=" * 50)
    print(f"Customers migrated:  {stats['customers_migrated']} ({stats['customers_skipped']} skipped)")
    print(f"Vendors migrated:    {stats['vendors_migrated']}")
    print(f"  Auto-merged:       {stats['vendors_auto_merged']}")
    print(f"  Needs review:      {stats['vendors_needs_review']}")
    print(f"  New entities:      {stats['vendors_new']}")
    print(f"Cemeteries migrated: {stats['cemeteries_migrated']}")
    print(f"  Auto-merged:       {stats['cemeteries_auto_merged']}")
    print(f"  Needs review:      {stats['cemeteries_needs_review']}")
    print(f"  New entities:      {stats['cemeteries_new']}")
    print(f"Total entities created: {stats['entities_created']}")
    print(f"Total auto-merges:   {stats['vendors_auto_merged'] + stats['cemeteries_auto_merged']}")
    print(f"Total needing review: {stats['vendors_needs_review'] + stats['cemeteries_needs_review']}")


if __name__ == "__main__":
    run()
