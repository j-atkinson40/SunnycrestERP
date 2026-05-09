"""Phase R-6.1a — Migration r93 schema verification."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, inspect

os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())


DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev"),
)


def _inspector():
    return inspect(create_engine(DB_URL))


def test_tenant_workflow_email_rules_exists():
    insp = _inspector()
    assert "tenant_workflow_email_rules" in insp.get_table_names()


def test_tenant_workflow_email_categories_exists():
    insp = _inspector()
    assert "tenant_workflow_email_categories" in insp.get_table_names()


def test_workflow_email_classifications_exists():
    insp = _inspector()
    assert "workflow_email_classifications" in insp.get_table_names()


def test_rules_columns():
    insp = _inspector()
    cols = {c["name"] for c in insp.get_columns("tenant_workflow_email_rules")}
    expected = {
        "id",
        "tenant_id",
        "priority",
        "name",
        "match_conditions",
        "fire_action",
        "is_active",
        "created_by_user_id",
        "updated_by_user_id",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols), expected - cols


def test_categories_columns():
    insp = _inspector()
    cols = {
        c["name"]
        for c in insp.get_columns("tenant_workflow_email_categories")
    }
    expected = {
        "id",
        "tenant_id",
        "parent_id",
        "label",
        "description",
        "mapped_workflow_id",
        "position",
        "is_active",
    }
    assert expected.issubset(cols), expected - cols


def test_classifications_columns():
    insp = _inspector()
    cols = {
        c["name"]
        for c in insp.get_columns("workflow_email_classifications")
    }
    expected = {
        "id",
        "tenant_id",
        "email_message_id",
        "tier",
        "tier1_rule_id",
        "tier2_category_id",
        "tier2_confidence",
        "tier3_confidence",
        "selected_workflow_id",
        "is_suppressed",
        "workflow_run_id",
        "is_replay",
        "replay_of_classification_id",
        "error_message",
        "latency_ms",
        "tier_reasoning",
        "created_at",
    }
    assert expected.issubset(cols), expected - cols


def test_workflows_tier3_enrolled_column():
    insp = _inspector()
    cols = {c["name"] for c in insp.get_columns("workflows")}
    assert "tier3_enrolled" in cols


def test_unclassified_partial_index_present():
    insp = _inspector()
    indexes = {
        idx["name"]
        for idx in insp.get_indexes("workflow_email_classifications")
    }
    assert "ix_workflow_email_classifications_unclassified" in indexes


def test_tier3_enrolled_partial_index_present():
    insp = _inspector()
    indexes = {idx["name"] for idx in insp.get_indexes("workflows")}
    assert "ix_workflows_tier3_enrolled" in indexes


def test_check_constraint_tier_present():
    insp = _inspector()
    checks = insp.get_check_constraints("workflow_email_classifications")
    names = {c["name"] for c in checks}
    assert "ck_workflow_email_classifications_tier" in names
