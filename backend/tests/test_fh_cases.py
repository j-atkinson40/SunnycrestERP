"""Tests for FH-1a case foundation: CaseService, staircase, SSN crypto, action registry."""

import os
import uuid
from datetime import date

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from app.models.company import Company
from app.models.funeral_case import (
    CaseDeceased,
    CaseDisposition,
    CaseInformant,
    CaseVeteran,
    FuneralCase,
)
from app.services.fh import case_service


# Generate a test key once per session
os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.services.fh import crypto  # noqa: E402  (after env var is set)


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
    # Clean up all related FH rows
    for table in [
        "funeral_case_notes",
        "case_aftercare", "case_preneed", "case_financials",
        "case_merchandise", "case_veteran", "case_cremation",
        "case_cemetery", "case_disposition", "case_service",
        "case_informants", "case_deceased",
        "vault_access_log", "vault_tributes", "case_vaults",
        "funeral_cases",
        "case_field_config",
        "casket_products",
        "tenant_product_lines",
    ]:
        db.execute(sql_text(f"DELETE FROM {table} WHERE company_id = :cid"), {"cid": c.id})
    db.delete(c)
    db.commit()


class TestCaseCreation:
    def test_create_case_generates_case_number_with_year(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        assert case.case_number.startswith(f"FC-")
        assert case.case_number.endswith("-0001")

    def test_create_case_creates_all_satellites(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        assert db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).count() == 1
        assert db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).count() == 1
        assert db.query(CaseVeteran).filter(CaseVeteran.case_id == case.id).count() == 1

        from app.models.funeral_case import (
            CaseAftercare, CaseCemetery, CaseCremation, CaseFinancials,
            CaseMerchandise, CasePreneed, CaseService as FHCaseService,
            FHCaseVault,
        )
        assert db.query(CaseAftercare).filter(CaseAftercare.case_id == case.id).count() == 1
        assert db.query(CaseCemetery).filter(CaseCemetery.case_id == case.id).count() == 1
        assert db.query(CaseCremation).filter(CaseCremation.case_id == case.id).count() == 1
        assert db.query(CaseFinancials).filter(CaseFinancials.case_id == case.id).count() == 1
        assert db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case.id).count() == 1
        assert db.query(CasePreneed).filter(CasePreneed.case_id == case.id).count() == 1
        assert db.query(FHCaseService).filter(FHCaseService.case_id == case.id).count() == 1
        assert db.query(FHCaseVault).filter(FHCaseVault.case_id == case.id).count() == 1

    def test_create_case_generates_sequential_numbers(self, db, fh_company):
        c1 = case_service.create_case(db, fh_company.id)
        c2 = case_service.create_case(db, fh_company.id)
        n1 = int(c1.case_number.split("-")[-1])
        n2 = int(c2.case_number.split("-")[-1])
        assert n2 == n1 + 1


class TestStaircase:
    def test_default_burial_case_hides_cremation_steps(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).first()
        disp.disposition_type = "burial"
        db.commit()
        steps = case_service.get_staircase(db, case.id)
        keys = [s["key"] for s in steps]
        assert "merchandise_urn" not in keys
        assert "cremation" not in keys
        assert "cemetery" in keys

    def test_cremation_case_hides_cemetery(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        disp = db.query(CaseDisposition).filter(CaseDisposition.case_id == case.id).first()
        disp.disposition_type = "cremation"
        db.commit()
        steps = case_service.get_staircase(db, case.id)
        keys = [s["key"] for s in steps]
        assert "cremation" in keys
        assert "merchandise_urn" in keys
        assert "cemetery" not in keys

    def test_non_veteran_hides_veterans_step(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        steps = case_service.get_staircase(db, case.id)
        keys = [s["key"] for s in steps]
        assert "veterans_benefits" not in keys

    def test_veteran_shows_veterans_step(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case.id).first()
        vet.ever_in_armed_forces = True
        db.commit()
        steps = case_service.get_staircase(db, case.id)
        keys = [s["key"] for s in steps]
        assert "veterans_benefits" in keys

    def test_advance_step_marks_completed_and_advances(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        assert case.current_step == "arrangement_conference"
        updated = case_service.advance_step(db, case.id, "arrangement_conference")
        assert "arrangement_conference" in (updated.completed_steps or [])
        assert updated.current_step != "arrangement_conference"


class TestNeedsAttention:
    def test_unsigned_authorization_flags_case(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        db.add(CaseInformant(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=fh_company.id,
            name="Test Spouse",
            is_authorizing=True,
            authorization_signed_at=None,
        ))
        db.commit()
        out = case_service.get_needs_attention(db, fh_company.id)
        assert any(r["case_id"] == case.id for r in out)
        entry = next(r for r in out if r["case_id"] == case.id)
        assert "Authorization unsigned" in entry["reasons"]

    def test_unfiled_dc_flags_case(self, db, fh_company):
        case = case_service.create_case(db, fh_company.id)
        # Default death_certificate_status is 'not_filed'
        out = case_service.get_needs_attention(db, fh_company.id)
        entry = next(r for r in out if r["case_id"] == case.id)
        assert "Death certificate not filed" in entry["reasons"]


class TestSsnEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        original = "123-45-6789"
        encrypted = crypto.encrypt_ssn(original)
        assert isinstance(encrypted, (bytes, bytearray))
        assert b"123456789" not in encrypted  # never plaintext in the bytes
        assert crypto.decrypt_ssn(encrypted) == "123456789"

    def test_last_four_extraction(self):
        assert crypto.ssn_last_four("123-45-6789") == "6789"
        assert crypto.ssn_last_four("123456789") == "6789"

    def test_mask_display(self):
        assert crypto.mask_ssn_display("6789") == "•••-••-6789"
        assert crypto.mask_ssn_display(None) == "•••-••-••••"


class TestFhCommandBarActions:
    def test_fh_actions_registered(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "core" / "actionRegistry.ts"
        content = p.read_text()
        for action_id in [
            "fh_new_arrangement",
            "fh_nav_cases",
            "fh_nav_home",
            "fh_add_case_note",
            "fh_start_scribe",
        ]:
            assert f'"{action_id}"' in content, f"Missing: {action_id}"

    def test_fh_actions_scoped_to_funeral_home_vertical(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "core" / "actionRegistry.ts"
        content = p.read_text()
        # funeralHomeActions block should exist
        assert "export const funeralHomeActions" in content
        assert 'vertical: "funeral_home"' in content
        # getActionsForVertical helper that routes by vertical
        assert "export function getActionsForVertical" in content
