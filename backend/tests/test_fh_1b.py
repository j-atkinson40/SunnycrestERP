"""Tests for FH-1b: cemetery plot reservation, cross-tenant vault order,
Legacy Vault Print generation, monument catalog + AI suggestion, approve_all.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

# Ensure encryption key is set before importing services
os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.data import monument_catalog  # noqa: E402
from app.models.cemetery_plot import CemeteryPlot  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.funeral_case import CaseCemetery, CaseMerchandise, FuneralCase  # noqa: E402
from app.services.fh import (  # noqa: E402
    case_service,
    cemetery_plot_service,
    cross_tenant_vault_service,
    legacy_vault_print_service,
    story_thread_service,
)


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
def fh_company(db):
    c = Company(
        id=str(uuid.uuid4()),
        name=f"Test FH {uuid.uuid4().hex[:6]}",
        slug=f"test-fh-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="funeral_home",
    )
    db.add(c)
    db.commit()
    yield c
    for t in [
        "funeral_case_notes", "case_aftercare", "case_preneed", "case_financials",
        "case_merchandise", "case_veteran", "case_cremation", "case_cemetery",
        "case_disposition", "case_service", "case_informants", "case_deceased",
        "vault_access_log", "vault_tributes", "case_vaults", "funeral_cases",
        "case_field_config", "casket_products", "tenant_product_lines",
        "cemetery_plots", "cemetery_map_config",
    ]:
        db.execute(sql_text(f"DELETE FROM {t} WHERE company_id = :cid"), {"cid": c.id})
    db.delete(c)
    db.commit()


@pytest.fixture
def cemetery_company(db):
    c = Company(
        id=str(uuid.uuid4()),
        name=f"Test Cemetery {uuid.uuid4().hex[:6]}",
        slug=f"test-cem-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="cemetery",
    )
    db.add(c)
    db.commit()
    yield c
    db.execute(sql_text("DELETE FROM cemetery_plots WHERE company_id = :cid"), {"cid": c.id})
    db.execute(sql_text("DELETE FROM cemetery_map_config WHERE company_id = :cid"), {"cid": c.id})
    db.delete(c)
    db.commit()


def _make_plot(db, cemetery_id: str, section="A", row="4", number="12", price=2400):
    p = CemeteryPlot(
        id=str(uuid.uuid4()),
        company_id=cemetery_id,
        section=section,
        row=row,
        number=number,
        plot_label=f"{section}-{row}-{number}",
        plot_type="single",
        status="available",
        map_x=10, map_y=10, map_width=5, map_height=4,
        price=price,
        opening_closing_fee=850,
    )
    db.add(p)
    db.commit()
    return p


class TestCemeteryPlotReservation:
    def test_reserve_plot_changes_status(self, db, fh_company, cemetery_company):
        case = case_service.create_case(db, fh_company.id)
        plot = _make_plot(db, cemetery_company.id)
        result = cemetery_plot_service.reserve_plot(db, plot.id, case.id, fh_company.id)
        assert result["status"] == "reserved"
        db.refresh(plot)
        assert plot.status == "reserved"
        assert plot.reservation_expires_at is not None

    def test_cannot_double_reserve(self, db, fh_company, cemetery_company):
        case1 = case_service.create_case(db, fh_company.id)
        case2 = case_service.create_case(db, fh_company.id)
        plot = _make_plot(db, cemetery_company.id)
        cemetery_plot_service.reserve_plot(db, plot.id, case1.id, fh_company.id)
        r2 = cemetery_plot_service.reserve_plot(db, plot.id, case2.id, fh_company.id)
        assert r2["status"] == "already_reserved"

    def test_complete_payment_marks_sold_and_updates_case(self, db, fh_company, cemetery_company):
        case = case_service.create_case(db, fh_company.id)
        plot = _make_plot(db, cemetery_company.id)
        cemetery_plot_service.reserve_plot(db, plot.id, case.id, fh_company.id)
        result = cemetery_plot_service.complete_reservation_payment(
            db, plot.id, case.id, fh_company.id
        )
        assert result["status"] == "sold"
        assert "transaction_id" in result
        db.refresh(plot)
        assert plot.status == "sold"
        assert plot.transaction_id is not None
        cem = db.query(CaseCemetery).filter(CaseCemetery.case_id == case.id).first()
        assert cem.plot_id == plot.id
        assert cem.plot_payment_status == "paid"
        assert cem.section == "A"

    def test_expired_reservations_released(self, db, fh_company, cemetery_company):
        case = case_service.create_case(db, fh_company.id)
        plot = _make_plot(db, cemetery_company.id)
        cemetery_plot_service.reserve_plot(db, plot.id, case.id, fh_company.id)
        # Backdate reservation to force expiry
        plot.reservation_expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        db.commit()
        count = cemetery_plot_service.release_expired_reservations(db)
        assert count >= 1
        db.refresh(plot)
        assert plot.status == "available"


class TestCrossTenantVaultOrder:
    def test_manual_fallback_when_no_manufacturer_connection(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        # Set a vault product without manufacturer connection
        merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).first()
        merch.vault_product_name = "Test Vault"
        db.commit()
        result = cross_tenant_vault_service.create_vault_order(db, case.id, fh_company.id)
        assert result["status"] == "manual"
        assert result["reason"] == "no_manufacturer_connection"

    def test_manual_when_no_vault_selected(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        result = cross_tenant_vault_service.create_vault_order(db, case.id, fh_company.id)
        assert result["status"] == "manual"
        assert result["reason"] == "no_vault_selected"


class TestMonumentCatalog:
    def test_shapes_returns_all_seeded_shapes(self):
        shapes = monument_catalog.get_shapes()
        assert "upright_standard" in shapes
        assert "flat_marker" in shapes
        assert "obelisk" in shapes
        # Each shape has available stones
        for s in shapes.values():
            assert len(s["available_stones"]) > 0

    def test_engravings_filtered_by_category(self):
        religious = monument_catalog.get_engravings("religious")
        for v in religious.values():
            assert v["category"] == "religious"
        military = monument_catalog.get_engravings("military")
        assert "army" in military
        assert "navy" in military

    def test_accessories_filtered_by_shape(self):
        for_upright = monument_catalog.get_accessories_for_shape("upright_standard")
        assert "bronze_vase" in for_upright
        # flat_marker shouldn't have companion_flat_marker (not in its compatible_shapes)
        for_flat = monument_catalog.get_accessories_for_shape("flat_marker")
        assert "companion_flat_marker" not in for_flat

    def test_suggest_military_for_veteran(self):
        assert monument_catalog.suggest_engraving(is_veteran=True, branch="US Army") == "army"
        assert monument_catalog.suggest_engraving(is_veteran=True, branch="Navy") == "navy"
        assert monument_catalog.suggest_engraving(is_veteran=True, branch="Marines") == "marines"

    def test_suggest_cross_for_catholic(self):
        assert monument_catalog.suggest_engraving(religion="Catholic") == "cross_ornate"

    def test_suggest_star_for_jewish(self):
        assert monument_catalog.suggest_engraving(religion="Jewish") == "star_of_david"

    def test_default_suggestion_is_roses(self):
        assert monument_catalog.suggest_engraving() == "roses"


class TestLegacyVaultPrint:
    def test_generate_returns_path_and_url(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        # Minimal required data
        from app.models.funeral_case import CaseDeceased
        dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
        dec.first_name = "John"
        dec.last_name = "Smith"
        merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).first()
        merch.vault_product_name = "Monticello Standard"
        db.commit()

        result = legacy_vault_print_service.generate(db, case.id)
        assert "url" in result
        assert "filename" in result
        assert case.case_number in result["filename"]
        # File should exist on disk (HTML fallback if weasyprint missing)
        from pathlib import Path
        assert Path(result["path"]).exists()


class TestApproveAllFlow:
    def test_approve_all_handles_partial_state(self, db, fh_company):
        """Approve All should succeed even when vault manufacturer / plot
        aren't connected. Returns structured status per sub-step."""
        case = case_service.create_case(db, fh_company.id)
        merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).first()
        merch.vault_product_name = "Test Vault"
        from app.models.funeral_case import CaseDeceased
        dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
        dec.first_name = "Demo"
        dec.last_name = "Case"
        db.commit()

        result = story_thread_service.approve_all_selections(db, case.id, director_id="test")
        assert result["vault_order"]["status"] == "manual"  # no manufacturer
        assert result["cemetery_reservation"]["status"] in ("not_applicable", "manual")
        assert result["monument_order"]["status"] == "not_applicable"
        assert result["legacy_print"]["status"] == "generated"

        db.refresh(case)
        assert case.story_thread_status == "approved"
        assert case.all_selections_approved_at is not None


class TestFh1bApiRegistered:
    def test_new_endpoints_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        # Cemetery
        assert any("/fh/cemetery/" in p and "/map" in p for p in paths)
        assert any("/fh/cemetery/plots/" in p and "/reserve" in p for p in paths)
        assert any("/fh/cemetery/plots/" in p and "/complete-payment" in p for p in paths)
        # Network
        assert any(p.endswith("/fh/network/connections") for p in paths)
        # Monument
        assert any(p.endswith("/fh/monument/shapes") for p in paths)
        assert any(p.endswith("/fh/monument/engravings") for p in paths)
        assert any("/fh/monument/suggest/" in p for p in paths)
