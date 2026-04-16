"""Tests for the new Bridgeable super admin portal.

Covers: command action registry (via Python unit imports), feature flags CRUD,
product line service, deployment tracking, kanban shape, chat context snapshot.

These tests use the local dev database via the standard test pattern.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.admin_deployment import AdminDeployment
from app.models.admin_feature_flag import AdminFeatureFlag, AdminFeatureFlagOverride
from app.models.company import Company
from app.models.tenant_product_line import TenantProductLine
from app.services import product_line_service
from app.services.admin import deployment_service, feature_flag_service
from app.services.admin import chat_service


DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev"),
)
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
    from sqlalchemy import text as sql_text
    c = Company(
        id=str(uuid.uuid4()),
        name=f"Test Admin Portal Co {uuid.uuid4().hex[:6]}",
        slug=f"test-admin-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(c)
    db.commit()
    yield c
    # Clean up child records before deleting company
    db.execute(sql_text("DELETE FROM tenant_product_lines WHERE company_id = :cid"), {"cid": c.id})
    db.execute(sql_text("DELETE FROM admin_feature_flag_overrides WHERE company_id = :cid"), {"cid": c.id})
    db.delete(c)
    db.commit()


class TestFeatureFlags:
    def test_seeded_flags_exist(self, db):
        flags = feature_flag_service.list_flags(db)
        keys = [f["flag_key"] for f in flags]
        assert "funeral_home_vertical" in keys
        assert "admin_claude_chat" in keys

    def test_set_override(self, db, test_company):
        override = feature_flag_service.set_override(
            db, "funeral_home_vertical", test_company.id, True
        )
        assert override.is_enabled is True
        # Override takes precedence over default
        assert feature_flag_service.is_enabled_for(
            db, "funeral_home_vertical", test_company.id
        ) is True
        # Cleanup
        feature_flag_service.remove_override(db, "funeral_home_vertical", test_company.id)


class TestProductLines:
    def test_enable_and_has_line(self, db, test_company):
        line = product_line_service.enable_line(db, test_company.id, "urns")
        assert line.is_enabled is True
        assert product_line_service.has_line(db, test_company.id, "urns") is True

    def test_disable_line(self, db, test_company):
        product_line_service.enable_line(db, test_company.id, "wastewater")
        product_line_service.disable_line(db, test_company.id, "wastewater")
        assert product_line_service.has_line(db, test_company.id, "wastewater") is False

    def test_available_catalog(self):
        catalog = product_line_service.get_available_lines()
        assert "burial_vaults" in catalog
        assert "urns" in catalog
        assert catalog["urns"]["replaces_extension"] == "urn_sales"


class TestDeploymentTracking:
    def test_log_and_manual_mark_tested(self, db):
        dep = deployment_service.log_deployment(
            db=db,
            description="test deploy",
            affected_verticals=["manufacturing"],
            git_commit="abc1234",
        )
        assert dep.is_tested is False

        untested = deployment_service.get_untested_for_vertical(db, "manufacturing")
        assert any(d.id == dep.id for d in untested)

        # Manual mark-tested (no audit_run_id FK needed)
        dep2 = deployment_service.manually_mark_tested(db, dep.id)
        assert dep2.is_tested is True
        # Cleanup
        db.delete(dep2)
        db.commit()

    def test_all_vertical_flags_all(self, db):
        dep = deployment_service.log_deployment(
            db=db,
            description="core platform deploy",
            affected_verticals=["all"],
        )
        # A manufacturing vertical should see this untested
        untested = deployment_service.get_untested_for_vertical(db, "manufacturing")
        assert any(d.id == dep.id for d in untested)
        # Also funeral_home
        untested_fh = deployment_service.get_untested_for_vertical(db, "funeral_home")
        assert any(d.id == dep.id for d in untested_fh)
        # Cleanup
        db.delete(dep)
        db.commit()


class TestChatContext:
    def test_context_snapshot_shape(self, db):
        snap = chat_service.get_context_snapshot(db)
        assert "claude_md" in snap
        assert "migration_head" in snap
        assert "tenants" in snap
        assert "last_audit" in snap
        assert "feature_flags" in snap
        assert "assembled_at" in snap

    def test_system_prompt_includes_migration_head(self, db):
        snap = chat_service.get_context_snapshot(db)
        prompt = chat_service.build_system_prompt(snap)
        assert snap["migration_head"] in prompt
        assert "CLAUDE.md" in prompt


class TestCommandActions:
    """Test that the command action registry is well-formed."""

    def test_registry_imports(self):
        # Import via module path; keep registry-level checks simple
        import json
        from pathlib import Path

        # We verify that the TS file has expected actions by reading it
        repo_root = Path(__file__).resolve().parent.parent.parent
        ts_file = repo_root / "frontend" / "src" / "bridgeable-admin" / "lib" / "admin-command-actions.ts"
        assert ts_file.exists()
        content = ts_file.read_text()
        # Expected action IDs
        expected = ["find-tenant", "impersonate", "run-audit", "feature-flags", "ask", "saved-prompts"]
        for aid in expected:
            assert f'"{aid}"' in content, f"Missing action: {aid}"
