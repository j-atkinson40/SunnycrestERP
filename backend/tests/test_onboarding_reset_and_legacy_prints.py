"""Tests for Sunnycrest onboarding reset infrastructure + legacy prints.

Uses local dev DB. Covers:
  - Legacy print service CRUD
  - Wilbert catalog prints cannot be deleted (only disabled)
  - Enable-all / disable-all
  - Custom print creation
"""

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from app.models.company import Company
from app.models.program_legacy_print import ProgramLegacyPrint
from app.services import legacy_print_service


DB_URL = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev"))
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def test_company(db):
    c = Company(
        id=str(uuid.uuid4()),
        name=f"LegacyPrint Test {uuid.uuid4().hex[:6]}",
        slug=f"legacy-print-test-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(c)
    db.commit()
    yield c
    db.execute(sql_text("DELETE FROM program_legacy_prints WHERE company_id = :cid"), {"cid": c.id})
    db.execute(sql_text("DELETE FROM tenant_product_lines WHERE company_id = :cid"), {"cid": c.id})
    db.delete(c)
    db.commit()


class TestLegacyPrintService:
    def test_create_custom_print(self, db, test_company):
        p = legacy_print_service.create_custom(
            db=db,
            company_id=test_company.id,
            program_code="vault",
            display_name="Test Cardinal",
            description="Company logo print",
            price_addition=Decimal("25.00"),
        )
        assert p.id
        assert p.is_custom is True
        assert p.is_enabled is True
        assert p.price_addition == Decimal("25.00")

    def test_list_prints_returns_company_scoped(self, db, test_company):
        legacy_print_service.create_custom(
            db, test_company.id, "vault", "Custom 1"
        )
        legacy_print_service.create_custom(
            db, test_company.id, "vault", "Custom 2"
        )
        prints = legacy_print_service.list_prints(db, test_company.id, "vault")
        assert len(prints) >= 2

    def test_cannot_delete_wilbert_catalog_print(self, db, test_company):
        # Manually create a Wilbert catalog (non-custom) print
        wilbert_print = ProgramLegacyPrint(
            company_id=test_company.id,
            program_code="vault",
            wilbert_catalog_key="classic_rose",
            display_name="Classic Rose",
            is_enabled=True,
            is_custom=False,
        )
        db.add(wilbert_print)
        db.commit()
        with pytest.raises(ValueError, match="Cannot delete"):
            legacy_print_service.delete_custom(db, test_company.id, wilbert_print.id)

    def test_delete_custom_print_succeeds(self, db, test_company):
        p = legacy_print_service.create_custom(
            db, test_company.id, "vault", "Deleteme"
        )
        ok = legacy_print_service.delete_custom(db, test_company.id, p.id)
        assert ok is True
        # Verify gone
        check = db.query(ProgramLegacyPrint).filter(ProgramLegacyPrint.id == p.id).first()
        assert check is None

    def test_enable_and_disable_print(self, db, test_company):
        p = legacy_print_service.create_custom(db, test_company.id, "vault", "Toggle")
        legacy_print_service.set_enabled(db, test_company.id, p.id, False)
        db.refresh(p)
        assert p.is_enabled is False
        legacy_print_service.set_enabled(db, test_company.id, p.id, True)
        db.refresh(p)
        assert p.is_enabled is True

    def test_set_price(self, db, test_company):
        p = legacy_print_service.create_custom(db, test_company.id, "vault", "Priced")
        legacy_print_service.set_price(db, test_company.id, p.id, Decimal("99.99"))
        db.refresh(p)
        assert p.price_addition == Decimal("99.99")

    def test_enable_all_wilbert_only_affects_non_custom(self, db, test_company):
        # Seed one Wilbert (disabled) and one custom (disabled)
        w = ProgramLegacyPrint(
            company_id=test_company.id,
            program_code="vault",
            wilbert_catalog_key="flag_only",
            display_name="Flag Only",
            is_enabled=False,
            is_custom=False,
        )
        c = ProgramLegacyPrint(
            company_id=test_company.id,
            program_code="vault",
            wilbert_catalog_key=None,
            display_name="Custom Only",
            is_enabled=False,
            is_custom=True,
        )
        db.add_all([w, c])
        db.commit()
        count = legacy_print_service.enable_all_wilbert(db, test_company.id, "vault")
        assert count >= 1
        db.refresh(w)
        db.refresh(c)
        assert w.is_enabled is True
        assert c.is_enabled is False  # Custom unchanged


class TestCommandBarActionRegistry:
    """Verify the action registry TS file has the expected new actions."""

    def test_new_actions_registered(self):
        from pathlib import Path
        registry = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "core" / "actionRegistry.ts"
        assert registry.exists()
        content = registry.read_text()

        # Critical new actions from the build prompt.
        # `create_disinterment` and `create_urn_order` were intentionally
        # removed — both are now covered by the universal `wf_create_order`
        # compose workflow (see comments in frontend/src/core/actionRegistry.ts).
        required_ids = [
            "nav_disinterments",
            "report_ar_aging",
            "report_ap_aging",
            "report_revenue",
            "run_statements",
            "nav_safety",
            "nav_npca",
            "audit_prep",
            "nav_ss_certs",
            "settings_programs",
            "settings_locations",
            "settings_team",
            "settings_product_lines",
            "nav_invoices",
            "nav_bills",
            "nav_purchase_orders",
            "nav_products",
            "nav_knowledge_base",
            "nav_team",
            "nav_spring_burials",
            "nav_transfers",
            "nav_call_log",
            "nav_agents",
        ]
        missing = [rid for rid in required_ids if f'"{rid}"' not in content]
        assert not missing, f"Missing action IDs: {missing}"

    def test_filter_actions_by_role_exported(self):
        from pathlib import Path
        registry = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "core" / "actionRegistry.ts"
        content = registry.read_text()
        assert "export function filterActionsByRole" in content

    def test_ar_aging_is_admin_only(self):
        """Financial reports must be tagged admin-only in the registry."""
        from pathlib import Path
        registry = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "core" / "actionRegistry.ts"
        content = registry.read_text()

        # Locate the report_ar_aging action and verify it only permits admin
        import re
        match = re.search(
            r'id:\s*"report_ar_aging".*?roles:\s*(\[[^\]]*\])',
            content,
            re.DOTALL,
        )
        assert match, "report_ar_aging action not found"
        roles = match.group(1)
        assert "admin" in roles
        assert "driver" not in roles
        assert "production" not in roles
