"""Phase R-6.1a — Audit log writer."""

from __future__ import annotations

from app.models.email_classification import WorkflowEmailClassification
from app.services.classification.audit import write_classification_audit
from tests._classification_fixtures import (  # noqa: F401
    db,
    make_email_account,
    make_inbound_email,
    tenant_pair,
)


def test_write_unclassified_row(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    row = write_classification_audit(
        db,
        tenant_id=a.id,
        email_message_id=msg.id,
        tier=None,
        latency_ms=42,
        tier_reasoning={"tier1": None, "tier2": None, "tier3": None},
    )
    db.commit()

    assert row.id
    assert row.tier is None
    assert row.is_suppressed is False
    assert row.is_replay is False
    assert row.latency_ms == 42
    assert row.created_at is not None


def test_write_tier1_dispatch(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    row = write_classification_audit(
        db,
        tenant_id=a.id,
        email_message_id=msg.id,
        tier=1,
        tier1_rule_id=None,
        selected_workflow_id=None,
        workflow_run_id=None,
        latency_ms=5,
    )
    db.commit()
    assert row.tier == 1


def test_write_replay_chain(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    original = write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=None
    )
    db.commit()
    replay = write_classification_audit(
        db,
        tenant_id=a.id,
        email_message_id=msg.id,
        tier=2,
        is_replay=True,
        replay_of_classification_id=original.id,
    )
    db.commit()
    assert replay.is_replay is True
    assert replay.replay_of_classification_id == original.id


def test_write_suppression_marker(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    row = write_classification_audit(
        db,
        tenant_id=a.id,
        email_message_id=msg.id,
        tier=1,
        is_suppressed=True,
    )
    db.commit()
    assert row.tier == 1
    assert row.is_suppressed is True
    assert row.selected_workflow_id is None


def test_two_classifications_for_same_message(db, tenant_pair):
    """Append-only — same message can have multiple rows."""
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=None
    )
    db.commit()
    write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=2
    )
    db.commit()
    rows = (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == msg.id)
        .all()
    )
    assert len(rows) == 2
