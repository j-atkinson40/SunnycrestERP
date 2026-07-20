"""D-11 U-4 pins — the finale: faces converge, Vault symmetry, D-13's
retirement, D-14's seeds, THE MAP LANDING.

The map pins run the (idempotent, preserve-aware) seed first, then
assert the chapter's shape: four jobs, the entry-path story (NL absent),
the cross-seam walks, the authority-honest mirrors.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestSerializerCore:
    def test_both_faces_carry_the_same_money_block(self, db):
        """The core computed once — both serializers consume it."""
        from app.models.quote import Quote
        from app.services.quote_service import _quote_to_dict, quote_money_fields
        q = db.query(Quote).filter(Quote.tax_reason.isnot(None)).first()
        if q is None:
            pytest.skip("no reasoned quote on this DB")
        core = quote_money_fields(q)
        assert set(core) == {"subtotal", "tax_rate", "tax_amount",
                             "tax_reason", "total"}
        d = _quote_to_dict(q)
        assert d["tax_reason"] == core["tax_reason"]
        assert Decimal(str(d["total"])) == Decimal(str(core["total"]))


class TestVaultSymmetry:
    def test_qte_create_joins_the_timeline(self, db):
        """The QTE face's quotes now dual-write a VaultItem (create-side
        asymmetry closed)."""
        from datetime import datetime, timezone
        from app.models.company import Company
        from app.models.customer import Customer
        from app.models.role import Role
        from app.models.user import User
        from app.services import sales_service

        co = Company(name="U4V", slug=f"u4v-{uuid.uuid4().hex[:6]}")
        db.add(co); db.flush()
        role = Role(company_id=co.id, name="U4V", slug=f"u4v-{uuid.uuid4().hex[:4]}")
        db.add(role); db.flush()
        usr = User(company_id=co.id, email=f"u4v-{uuid.uuid4().hex[:6]}@example.com",
                   hashed_password="x", first_name="P", last_name="V",
                   role_id=role.id)
        cust = Customer(company_id=co.id, name="U4V FH",
                        account_number=f"U4V-{uuid.uuid4().hex[:5]}")
        db.add_all([usr, cust]); db.commit()
        try:
            class _L:
                product_id = None; description = "Vault"; sort_order = 0
                quantity = Decimal("1"); unit_price = Decimal("100.00")

            class _D:
                customer_id = cust.id
                quote_date = datetime.now(timezone.utc)
                expiry_date = quote_date; payment_terms = None
                tax_rate = Decimal("0"); notes = None
                lines = [_L()]
            q = sales_service.create_quote(db, co.id, usr.id, _D())
            n = db.execute(sql_text(
                "SELECT count(*) FROM vault_items WHERE company_id = :c "
                "AND item_type = 'quote' AND source_entity_id = :q"),
                {"c": co.id, "q": q.id}).scalar()
            assert n == 1
        finally:
            for stmt in (
                "DELETE FROM quote_lines WHERE quote_id IN (SELECT id FROM quotes WHERE company_id = :c)",
                "DELETE FROM quotes WHERE company_id = :c",
                "DELETE FROM vault_items WHERE company_id = :c",
                "DELETE FROM audit_logs WHERE company_id = :c",
                "DELETE FROM vaults WHERE company_id = :c",
                "DELETE FROM company_modules WHERE company_id = :c",
                "DELETE FROM financial_accounts WHERE company_id = :c",
                "DELETE FROM customers WHERE company_id = :c",
                "DELETE FROM users WHERE company_id = :c",
                "DELETE FROM roles WHERE company_id = :c",
                "DELETE FROM companies WHERE id = :c",
            ):
                try:
                    db.execute(sql_text(stmt), {"c": co.id}); db.commit()
                except Exception:
                    db.rollback()


class TestD13Retired:
    def test_nl_sales_order_declaration_gone(self):
        from typing import get_args
        from app.services.nl_creation.types import EntityType
        assert "sales_order" not in get_args(EntityType)
        assert set(get_args(EntityType)) == {"case", "event", "contact", "task"}


class TestTheMapLanding:
    @pytest.fixture(autouse=True, scope="class")
    def _seeded(self):
        from scripts.seed_so_map import main
        main()

    def test_four_jobs_in_the_area(self, db):
        from app.models.moc_job import MoCJob
        names = {j.name for j in db.query(MoCJob).filter(
            MoCJob.task_type == "Sales & Orders", MoCJob.is_active).all()}
        assert names >= {"Quote a customer", "Enter an order",
                         "Keep the order book honest", "Get paid"}

    def test_enter_an_order_walks_true_ways_nl_absent(self, db):
        from app.models.moc_job import MoCJob
        from app.services.maps_of_content.jobs import build_job_ponder_script
        job = db.query(MoCJob).filter(
            MoCJob.name == "Enter an order", MoCJob.is_active).first()
        script = build_job_ponder_script(db, job_id=job.id)
        stories = [b for b in script["beats"] if b["kind"] == "story"]
        assert len(stories) == 8  # the true ways — the retired NL absent
        joined = " ".join(b["text"].lower() for b in script["beats"])
        assert "natural language" not in joined

    def test_get_paid_walks_across_the_seam(self, db):
        from app.models.moc_job import MoCJob
        from app.services.maps_of_content.jobs import build_job_ponder_script
        job = db.query(MoCJob).filter(
            MoCJob.name == "Get paid", MoCJob.is_active).first()
        script = build_job_ponder_script(db, job_id=job.id)
        refs = [b.get("ponder_ref") for b in script["beats"]
                if b["kind"] == "story" and b.get("ponder_ref")]
        assert len(refs) == 2  # both accounting jobs walkable
        assert all(r["overlay_id"].startswith("job:") for r in refs)

    def test_mirrors_carry_authority_honesty(self, db):
        from app.models.moc_task_catalog import MoCTaskCatalog
        for name in ("Quote Auto-Expiry", "End-of-Day Draft Invoices"):
            row = db.query(MoCTaskCatalog).filter(
                MoCTaskCatalog.name == name,
                MoCTaskCatalog.is_active).first()
            assert row is not None, name
            assert row.task_type == "Sales & Orders"
            assert "platform scheduler" in (row.frequency or "") or \
                   "platform scheduler" in (row.description or "")

    def test_preserve_aware_rerun_creates_nothing(self, db):
        from app.models.moc_job import MoCJob
        from scripts.seed_so_map import main
        before = db.query(MoCJob).filter(MoCJob.is_active).count()
        main()
        after = db.query(MoCJob).filter(MoCJob.is_active).count()
        assert before == after


class TestD14Seeds:
    def test_the_four_shapes_present(self, db):
        """The dev seed's quotes demonstrate the unified system (this DB
        has run seed_staging; skip honestly where it hasn't)."""
        rows = db.execute(sql_text(
            "SELECT status, tax_reason, converted_to_order_id FROM quotes "
            "WHERE company_id = 'staging-test-001' "
            "AND notes LIKE '%[seed:d14]%'")).fetchall()
        if not rows:
            pytest.skip("seed_staging has not run on this DB")
        reasons = [r[1] or "" for r in rows]
        assert any(r.startswith("resolved:") for r in reasons)
        assert any(r.startswith("override:") for r in reasons)
        assert any(r[0] == "rejected" for r in rows)
        assert any(r[0] == "converted" and r[2] for r in rows)
