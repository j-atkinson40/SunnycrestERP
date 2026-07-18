"""The map-completes-itself pins — kinds, the path's states, reality
completion, the showroom's record+notify+gating, the not-yet honesty,
the spine untouched."""
from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content import platform_map as pm


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    co = Company(name="MC", slug=f"mapc-{uuid.uuid4().hex[:6]}")
    db.add(co); db.commit()
    ids = {"co": co.id}
    db.close()
    yield ids
    db = SessionLocal()
    for t in ("plaid_items", "company_modules", "notifications", "audit_logs"):
        try:
            col = "tenant_id" if t == "plaid_items" else "company_id"
            db.execute(sql_text(f"DELETE FROM {t} WHERE {col} = :c"), {"c": ids["co"]})
        except Exception:
            db.rollback()
    db.execute(sql_text("DELETE FROM ponder_engagement WHERE company_id = :c"), {"c": ids["co"]})
    db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": ids["co"]})
    db.commit(); db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestJourney:
    def test_states_and_reality(self, db, world):
        j = pm.build_journey(db, tenant_id=world["co"])
        assert j["total"] >= 4
        states = {s["key"]: s["state"] for s in j["steps"]}
        # Fresh tenant: nothing done; the FIRST step is current, rest ahead.
        assert list(states.values())[0] == "current"
        assert all(v in ("current", "ahead") for v in states.values())
        # Reality completion: connect-your-bank flips by EXISTENCE.
        from app.models.plaid import PlaidItem
        from app.services.plaid import crypto as pc
        import os
        from cryptography.fernet import Fernet
        os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
        pc.reset_fernet_cache()
        db.add(PlaidItem(tenant_id=world["co"], plaid_item_id=f"i-{uuid.uuid4().hex[:8]}",
                         access_token_encrypted=pc.encrypt_token("t")))
        db.commit()
        j2 = pm.build_journey(db, tenant_id=world["co"])
        s2 = {s["key"]: s for s in j2["steps"]}
        assert s2["connect-your-bank"]["state"] == "done"
        assert s2["connect-your-bank"]["completion"] == "reality"
        assert "walked" in j2["prose"]

    def test_engagement_completion(self, db, world):
        from app.services.maps_of_content import engagement as eng
        eng.record(db, user_id=str(uuid.uuid4()), company_id=world["co"],
                   ponder_key="onboarding:welcome-map", event="completed")
        db.commit()
        j = pm.build_journey(db, tenant_id=world["co"])
        s = {x["key"]: x for x in j["steps"]}
        assert s["welcome-map"]["state"] == "done"
        assert s["welcome-map"]["completion"] == "engagement"


class TestPlatformCards:
    def test_command_bar_action_beat(self, db):
        s = pm.build_platform_ponder(db, key="command-bar", vertical="manufacturing")
        assert any("⌘K" in b["text"] for b in s["beats"])

    def test_focuses_carries_a_real_miniature(self, db):
        s = pm.build_platform_ponder(db, key="focuses", vertical="manufacturing")
        assert any(b.get("artifact", {}).get("type") == "focus" for b in s["beats"]
                   if b.get("artifact"))


class TestTips:
    def test_two_beat_script_and_empty_honest(self, db):
        tips = pm.list_tips(db, area="Accounting")
        assert len(tips) >= 2
        s = pm.build_tip_ponder(db, key=tips[0]["key"])
        assert len(s["beats"]) == 2  # the stage's shortest story
        assert pm.list_tips(db, area="NowhereArea") == []


class TestShowroom:
    def test_enable_records_notifies_gates(self, db, world):
        out = pm.set_module_enabled(
            db, tenant_id=world["co"], module_key="project_mgmt",
            enabled=True, actor_user_id=None)
        assert out["terms"] == "billing per your agreement"
        from app.models.company_module import CompanyModule
        row = db.query(CompanyModule).filter_by(
            company_id=world["co"], module="project_mgmt").one()
        assert row.enabled is True
        audit = db.execute(sql_text(
            "SELECT count(*) FROM audit_logs WHERE company_id=:c AND action='module_enabled'"),
            {"c": world["co"]}).scalar()
        assert audit >= 1
        # Enabled modules leave the showroom (honest inventory).
        cards = pm.showroom(db, tenant_id=world["co"])["cards"]
        assert all(c["key"] != "project_mgmt" for c in cards)
        # Disable: honest consequences, gating only.
        pm.set_module_enabled(db, tenant_id=world["co"], module_key="project_mgmt",
                              enabled=False, actor_user_id=None)
        db.refresh(row)
        assert row.enabled is False

    def test_locked_refuses_and_not_yet_untoggleable(self, db, world):
        with pytest.raises(ValueError):
            pm.set_module_enabled(db, tenant_id=world["co"], module_key="core",
                                  enabled=False, actor_user_id=None)
        cards = pm.showroom(db, tenant_id=world["co"])["cards"]
        payroll = next(c for c in cards if c["key"] == "payroll_check")
        assert payroll["toggleable"] is False
        s = pm.build_module_ponder(db, key="payroll_check", tenant_id=world["co"])
        assert any("2027" in b["text"] for b in s["beats"])  # the honest timeline


class TestSpineUntouched:
    def test_business_derivation_unchanged(self, db):
        # The business areas still derive purely from the catalog — the
        # platform rooms live in their own registry, never in tasks.
        from app.services.maps_of_content.task_catalog import resolve_task_catalog
        tasks = resolve_task_catalog(db, vertical="manufacturing", tenant_id=None)
        areas = {(t.get("task_type") or "General") for t in tasks}
        assert "Platform" not in areas
        assert "Onboarding & Setup" not in areas
        assert [a["area"] for a in pm.PLATFORM_AREAS] == [
            "Platform", "Onboarding & Setup", "Additional features"]
