"""Phase R-6.1a — Cascade orchestrator end-to-end."""

from __future__ import annotations

from app.models.email_classification import WorkflowEmailClassification
from app.models.workflow import WorkflowRun
from app.services.classification import dispatch
from tests._classification_fixtures import (  # noqa: F401
    db,
    make_category,
    make_email_account,
    make_inbound_email,
    make_intelligence_result,
    make_rule,
    make_workflow,
    tenant_pair,
)


# ── Tier 1 dispatch ─────────────────────────────────────────────────


def test_tier_1_dispatch_fires_workflow(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, name="Disinterment intake")
    make_rule(
        db,
        a,
        priority=0,
        name="Disinterment rule",
        match_conditions={"subject_contains_any": ["disinterment"]},
        fire_workflow_id=wf.id,
    )

    fired = []

    def stub_start(db_, **kwargs):
        fired.append(kwargs)
        run = WorkflowRun(
            workflow_id=kwargs["workflow_id"],
            company_id=kwargs["company_id"],
            triggered_by_user_id=None,
            trigger_source=kwargs["trigger_source"],
            trigger_context=kwargs["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        stub_start,
    )

    msg = make_inbound_email(
        db, tenant=a, account=acct, subject="Disinterment for Smith"
    )
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    assert result.tier == 1
    assert result.selected_workflow_id == wf.id
    assert result.workflow_run_id is not None
    assert result.is_suppressed is False
    assert len(fired) == 1
    assert fired[0]["trigger_source"] == "email_classification"
    # R-6.0 contract: trigger_context.incoming_email shape.
    incoming = fired[0]["trigger_context"]["incoming_email"]
    assert incoming["from_email"] == msg.sender_email
    assert incoming["subject"] == msg.subject
    assert incoming["id"] == msg.id

    row = (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == msg.id)
        .one()
    )
    assert row.tier == 1


def test_tier_1_suppression_drops_message(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    make_rule(
        db,
        a,
        priority=0,
        name="Suppress LinkedIn",
        match_conditions={"sender_domain_in": ["linkedin.com"]},
        fire_workflow_id=None,
    )

    fired = []
    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        lambda *a_, **kw: fired.append(kw),
    )

    msg = make_inbound_email(
        db,
        tenant=a,
        account=acct,
        sender_email="news@linkedin.com",
        subject="You have new connections",
    )
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    assert result.tier == 1
    assert result.is_suppressed is True
    assert result.workflow_run_id is None
    assert fired == []  # no workflow fired


def test_tier_1_inactive_workflow_falls_through(
    db, tenant_pair, monkeypatch
):
    """Stale rule pointing at archived workflow — cascade falls
    through to Tier 2."""
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a)
    wf.is_active = False
    db.commit()

    make_rule(
        db,
        a,
        priority=0,
        name="Stale rule",
        match_conditions={},
        fire_workflow_id=wf.id,
    )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        lambda *a_, **kw: make_intelligence_result(
            response_parsed={
                "category_id": None,
                "confidence": 0.0,
                "reasoning": "no taxonomy",
            }
        ),
    )

    msg = make_inbound_email(db, tenant=a, account=acct)
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    # No taxonomy + no Tier 3 enrolled → unclassified.
    assert result.tier is None
    assert result.is_suppressed is False


# ── Tier 2 dispatch ─────────────────────────────────────────────────


def test_tier_2_dispatch_fires_workflow(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, name="Pricing reply")
    cat = make_category(
        db, a, label="Pricing", description="x", mapped_workflow_id=wf.id
    )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        lambda *a_, **kw: make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.85,
                "reasoning": "match",
            }
        ),
    )

    fired = []

    def stub_start(db_, **kw):
        fired.append(kw)
        run = WorkflowRun(
            workflow_id=kw["workflow_id"],
            company_id=kw["company_id"],
            triggered_by_user_id=None,
            trigger_source=kw["trigger_source"],
            trigger_context=kw["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        stub_start,
    )

    msg = make_inbound_email(db, tenant=a, account=acct, subject="Pricing?")
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    assert result.tier == 2
    assert result.selected_workflow_id == wf.id
    assert result.workflow_run_id is not None


# ── Tier 3 dispatch ─────────────────────────────────────────────────


def test_tier_3_dispatch_fires_workflow(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(
        db,
        a,
        name="Vendor catalog intake",
        tier3_enrolled=True,
        description="Process vendor catalog updates",
    )

    # Tier 2 returns null (no taxonomy match).
    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        lambda *a_, **kw: make_intelligence_result(
            response_parsed={
                "category_id": None,
                "confidence": 0.0,
                "reasoning": "n/a",
            }
        ),
    )
    # Tier 3 picks the workflow.
    monkeypatch.setattr(
        "app.services.classification.tier_3_registry.intelligence_service.execute",
        lambda *a_, **kw: make_intelligence_result(
            response_parsed={
                "workflow_id": wf.id,
                "confidence": 0.75,
                "reasoning": "matches description",
            }
        ),
    )

    fired = []

    def stub_start(db_, **kw):
        fired.append(kw)
        run = WorkflowRun(
            workflow_id=kw["workflow_id"],
            company_id=kw["company_id"],
            triggered_by_user_id=None,
            trigger_source=kw["trigger_source"],
            trigger_context=kw["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        stub_start,
    )

    msg = make_inbound_email(db, tenant=a, account=acct)
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    assert result.tier == 3
    assert result.selected_workflow_id == wf.id


# ── Unclassified ────────────────────────────────────────────────────


def test_all_tiers_fall_through_routes_to_triage(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)

    # No rule, no taxonomy, no Tier 3 enrolled — all empty.
    msg = make_inbound_email(db, tenant=a, account=acct)
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    assert result.tier is None
    assert result.selected_workflow_id is None
    assert result.is_suppressed is False
    assert result.workflow_run_id is None


# ── Audit row always written ────────────────────────────────────────


def test_every_path_writes_audit_row(db, tenant_pair, monkeypatch):
    """Cascade exhaustion still writes a row — never silently skip."""
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    dispatch.classify_and_fire(db, email_message=msg)
    db.commit()
    rows = (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == msg.id)
        .all()
    )
    assert len(rows) == 1


# ── Per-tenant confidence floor override ────────────────────────────


def test_tenant_overrides_confidence_floors(db, tenant_pair, monkeypatch):
    """Tenant lowers Tier 2 floor to 0.4 → 0.45 confidence dispatches."""
    a, _ = tenant_pair
    a.set_setting(
        "classification_confidence_floors",
        {"tier_2": 0.4, "tier_3": 0.5},
    )
    db.commit()

    acct = make_email_account(db, a)
    wf = make_workflow(db, a)
    cat = make_category(db, a, label="x", mapped_workflow_id=wf.id)

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        lambda *a_, **kw: make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.45,
                "reasoning": "low",
            }
        ),
    )

    fired = []
    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        lambda db_, **kw: (
            fired.append(kw)
            or WorkflowRun(
                workflow_id=kw["workflow_id"],
                company_id=kw["company_id"],
                triggered_by_user_id=None,
                trigger_source=kw["trigger_source"],
                trigger_context=kw["trigger_context"],
                status="running",
                input_data={},
                output_data={},
            )
        ),
    )

    msg = make_inbound_email(db, tenant=a, account=acct)
    result = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    # 0.45 ≥ tenant floor 0.4 — should dispatch.
    assert result.tier == 2


# ── Cross-tenant existence-hiding ────────────────────────────────────


def test_classify_only_cross_tenant_404(db, tenant_pair):
    from app.services.classification import (
        ClassificationNotFound,
        classify_only,
    )
    import pytest

    a, b = tenant_pair
    acct_a = make_email_account(db, a)
    msg_a = make_inbound_email(db, tenant=a, account=acct_a)

    with pytest.raises(ClassificationNotFound):
        classify_only(db, message_id=msg_a.id, tenant_id=b.id)


# ── Trigger context shape ───────────────────────────────────────────


def test_build_trigger_context_shape(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db, tenant=a, account=acct, subject="X", body_text="Y"
    )
    ctx = dispatch._build_trigger_context(msg)
    assert "incoming_email" in ctx
    incoming = ctx["incoming_email"]
    assert incoming["id"] == msg.id
    assert incoming["from_email"] == msg.sender_email
    assert incoming["subject"] == "X"
    assert incoming["body_text"] == "Y"
    assert incoming["tenant_id"] == a.id


# ── Replay tracking ─────────────────────────────────────────────────


def test_replay_writes_new_row_with_pointer(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    # First classification — unclassified.
    first = dispatch.classify_and_fire(db, email_message=msg)
    db.commit()

    # Now seed a Tier 1 rule + replay.
    wf = make_workflow(db, a)
    make_rule(
        db,
        a,
        priority=0,
        match_conditions={},
        fire_workflow_id=wf.id,
    )
    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        lambda db_, **kw: WorkflowRun(
            workflow_id=kw["workflow_id"],
            company_id=kw["company_id"],
            triggered_by_user_id=None,
            trigger_source=kw["trigger_source"],
            trigger_context=kw["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        ),
    )
    second = dispatch.classify_only(
        db, message_id=msg.id, tenant_id=a.id
    )
    db.commit()
    assert second.tier == 1
    rows = (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == msg.id)
        .order_by(WorkflowEmailClassification.created_at)
        .all()
    )
    assert len(rows) == 2
    assert rows[1].is_replay is True
    assert rows[1].replay_of_classification_id == first.classification_id


# ── list_unclassified de-dup against later replay ──────────────────


def test_list_unclassified_dedups_against_replay(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)

    # 2 messages: msg1 stays unclassified; msg2 originally unclassified
    # but a Tier 1 replay re-routes it.
    msg1 = make_inbound_email(db, tenant=a, account=acct, subject="X")
    msg2 = make_inbound_email(db, tenant=a, account=acct, subject="Y")
    dispatch.classify_and_fire(db, email_message=msg1)
    dispatch.classify_and_fire(db, email_message=msg2)
    db.commit()

    # Both should be unclassified at this point.
    unclassified = dispatch.list_unclassified(db, tenant_id=a.id)
    msg_ids = {row["email_message_id"] for row in unclassified}
    assert msg1.id in msg_ids
    assert msg2.id in msg_ids

    # Now retroactively classify msg2 via replay.
    wf = make_workflow(db, a)
    make_rule(
        db,
        a,
        priority=0,
        match_conditions={"subject_contains_any": ["Y"]},
        fire_workflow_id=wf.id,
    )
    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        lambda db_, **kw: WorkflowRun(
            workflow_id=kw["workflow_id"],
            company_id=kw["company_id"],
            triggered_by_user_id=None,
            trigger_source=kw["trigger_source"],
            trigger_context=kw["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        ),
    )
    dispatch.classify_only(db, message_id=msg2.id, tenant_id=a.id)
    db.commit()

    unclassified = dispatch.list_unclassified(db, tenant_id=a.id)
    msg_ids = {row["email_message_id"] for row in unclassified}
    assert msg1.id in msg_ids
    assert msg2.id not in msg_ids  # de-dup'd against later replay
