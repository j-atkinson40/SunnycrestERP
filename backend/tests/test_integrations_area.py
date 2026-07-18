"""Integrations area pins — dependents derivation, the three faces, the
onboarding re-point, isolation."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.plaid import PlaidItem
from app.services.maps_of_content.integration_ponder import (
    build_integration_ponder, connection_state, derive_dependents,
    integration_summary,
)
from app.services.plaid import crypto as plaid_crypto


@pytest.fixture(scope="module", autouse=True)
def _key():
    import os
    from cryptography.fernet import Fernet
    prior = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    plaid_crypto.reset_fernet_cache()
    yield
    if prior is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior
    plaid_crypto.reset_fernet_cache()


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    sx = uuid.uuid4().hex[:6]
    co = Company(name="IG", slug=f"integ-{sx}")
    co2 = Company(name="IG2", slug=f"integ2-{sx}")
    db.add_all([co, co2]); db.commit()
    ids = {"a": co.id, "b": co2.id}
    db.close()
    yield ids
    db = SessionLocal()
    for c in ids.values():
        db.execute(sql_text("DELETE FROM plaid_items WHERE tenant_id = :c"), {"c": c})
        db.execute(sql_text("DELETE FROM ponder_engagement WHERE company_id = :c"), {"c": c})
        db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": c})
    db.commit(); db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestDependents:
    def test_derived_from_the_spine(self, db):
        deps = derive_dependents(db, "plaid")
        assert "Bank reconciliation" in deps["jobs"]
        assert deps["automation_count"] >= 2  # Pull + Cash Receipts (min)

    def test_unknown_integration_empty(self, db):
        assert derive_dependents(db, "nope") == {"jobs": [], "automation_count": 0}


class TestThreeFaces:
    def test_never_then_degraded_then_connected(self, db, world):
        assert connection_state(db, world["a"])["face"] == "never"
        s = build_integration_ponder(db, key="plaid", tenant_id=world["a"])
        state = next(b for b in s["beats"] if b["key"] == "state")
        assert "onboarding" in state["text"]
        assert state["ponder_ref"]["overlay_id"] == "onboarding:connect-your-bank"

        item = PlaidItem(
            tenant_id=world["a"], plaid_item_id=f"it-{uuid.uuid4().hex[:8]}",
            institution_name="First Platypus Bank",
            access_token_encrypted=plaid_crypto.encrypt_token("t"),
            status="login_required",
        )
        db.add(item); db.commit()
        assert connection_state(db, world["a"])["face"] == "degraded"
        s2 = build_integration_ponder(db, key="plaid", tenant_id=world["a"])
        assert "needs re-connecting" in next(
            b for b in s2["beats"] if b["key"] == "state")["text"]

        item.status = "active"; db.commit()
        assert connection_state(db, world["a"])["face"] == "connected"
        summ = integration_summary(db, tenant_id=world["a"])
        assert summ["integrations"][0]["face"] == "connected"
        # ISOLATION: tenant B still never-connected.
        assert connection_state(db, world["b"])["face"] == "never"

    def test_job_ponder_three_faces(self, db, world):
        from app.models.moc_job import MoCJob
        from app.services.maps_of_content.jobs import build_job_ponder_script
        job = (
            db.query(MoCJob)
            .filter(MoCJob.name == "Bank reconciliation",
                    MoCJob.vertical == "manufacturing",
                    MoCJob.is_active.is_(True)).one()
        )
        # Tenant B: NEVER — the beat teaches + routes to onboarding.
        s = build_job_ponder_script(db, job_id=job.id, company_id=world["b"])
        feed = next(b for b in s["beats"] if b["key"] == "feed")
        assert "onboarding" in feed["text"]
        assert feed["ponder_ref"]["overlay_id"] == "onboarding:connect-your-bank"
        # Tenant A (active item from prior test): CONNECTED face.
        s2 = build_job_ponder_script(db, job_id=job.id, company_id=world["a"])
        feed2 = next(b for b in s2["beats"] if b["key"] == "feed")
        assert "connected" in feed2["text"]
        # Degrade → the warning face routes to Integrations.
        item = db.query(PlaidItem).filter(PlaidItem.tenant_id == world["a"]).one()
        item.status = "login_required"; db.commit()
        s3 = build_job_ponder_script(db, job_id=job.id, company_id=world["a"])
        feed3 = next(b for b in s3["beats"] if b["key"] == "feed")
        assert "re-connecting" in feed3["text"]
        assert feed3["link"]["href"] == "/bridgeable-map/Integrations"
        item.status = "active"; db.commit()


class TestOnboardingRePoint:
    def test_setup_rule_opens_the_onboarding_ponder(self, db, world):
        from app.services.maps_of_content.engagement import build_suggestions
        out = build_suggestions(
            db, user_id=str(uuid.uuid4()), company_id=world["b"],
            vertical="manufacturing", role_slug="admin", is_admin=True,
        )
        card = next(s for s in out if s["rule"] == "setup")
        assert card["ponder_key"] == "onboarding:connect-your-bank"
        assert "href" not in card
        # Rule 1 does NOT double-surface the same composition.
        assert sum(1 for s in out
                   if s["ponder_key"] == "onboarding:connect-your-bank") == 1

    def test_retire_by_reality_carries(self, db, world):
        from app.services.maps_of_content.engagement import build_suggestions
        out = build_suggestions(
            db, user_id=str(uuid.uuid4()), company_id=world["a"],  # connected
            vertical="manufacturing", role_slug="admin", is_admin=True,
        )
        assert all(s["rule"] != "setup" for s in out)

    def test_dismissal_final_under_the_new_key(self, db, world):
        from app.services.maps_of_content import engagement as eng
        uid = str(uuid.uuid4())
        eng.record(db, user_id=uid, company_id=world["b"],
                   ponder_key="onboarding:connect-your-bank", event="dismissed")
        db.commit()
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["b"],
            vertical="manufacturing", role_slug="admin", is_admin=True,
        )
        assert all(s["rule"] != "setup" for s in out)

    def test_onboarding_script_carries_the_action_link(self, db):
        from app.services.maps_of_content.area_ponder import build_onboarding_script
        s = build_onboarding_script(db, key="connect-your-bank")
        action = next(b for b in s["beats"] if b["key"] == "action")
        assert action["link"]["href"] == "/bridgeable-map/Integrations"
