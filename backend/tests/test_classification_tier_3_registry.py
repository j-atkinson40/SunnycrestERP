"""Phase R-6.1a — Tier 3 workflow registry selection."""

from __future__ import annotations

from tests._classification_fixtures import (  # noqa: F401
    db,
    make_email_account,
    make_inbound_email,
    make_intelligence_result,
    make_workflow,
    tenant_pair,
)
from app.services.classification import tier_3_registry


def test_assemble_registry_tenant_scoped(db, tenant_pair):
    a, b = tenant_pair
    wf_a = make_workflow(
        db,
        a,
        name="A workflow",
        tier3_enrolled=True,
        description="Does A things",
    )
    wf_b = make_workflow(
        db,
        b,
        name="B workflow",
        tier3_enrolled=True,
        description="Does B things",
    )

    a_registry = tier_3_registry.assemble_registry(db, a.id)
    a_ids = {wf.id for wf in a_registry}
    assert wf_a.id in a_ids
    assert wf_b.id not in a_ids


def test_assemble_registry_includes_platform(db, tenant_pair):
    a, _ = tenant_pair
    platform_wf = make_workflow(
        db,
        None,
        name="Platform workflow",
        tier3_enrolled=True,
        description="Cross-tenant utility",
    )
    registry = tier_3_registry.assemble_registry(db, a.id)
    assert platform_wf.id in {wf.id for wf in registry}


def test_assemble_registry_skips_unenrolled(db, tenant_pair):
    a, _ = tenant_pair
    wf = make_workflow(
        db,
        a,
        name="Unenrolled",
        tier3_enrolled=False,
        description="Not opted in",
    )
    registry = tier_3_registry.assemble_registry(db, a.id)
    assert wf.id not in {w.id for w in registry}


def test_assemble_registry_skips_inactive(db, tenant_pair):
    a, _ = tenant_pair
    wf = make_workflow(
        db, a, name="Stale", tier3_enrolled=True, description="off"
    )
    wf.is_active = False
    db.commit()
    registry = tier_3_registry.assemble_registry(db, a.id)
    assert wf.id not in {w.id for w in registry}


def test_classify_above_floor_dispatches(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(
        db,
        a,
        name="Vendor catalog intake",
        tier3_enrolled=True,
        description="Process vendor catalog updates",
    )
    msg = make_inbound_email(db, tenant=a, account=acct)
    registry = [wf]

    def stub(db_, **kwargs):
        assert kwargs["prompt_key"] == "email.classify_into_registry"
        return make_intelligence_result(
            response_parsed={
                "workflow_id": wf.id,
                "confidence": 0.8,
                "reasoning": "Description matches catalog update intent.",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_3_registry.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_3_registry.classify(
        db, message=msg, registry=registry, confidence_floor=0.65
    )
    assert matched is not None
    assert matched.id == wf.id
    assert conf == 0.8
    assert err is None
    assert "Description matches" in reasoning


def test_classify_below_floor_no_match(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, tier3_enrolled=True, description="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "workflow_id": wf.id,
                "confidence": 0.5,
                "reasoning": "uncertain",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_3_registry.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_3_registry.classify(
        db, message=msg, registry=[wf], confidence_floor=0.65
    )
    assert matched is None
    assert conf == 0.5


def test_classify_null_workflow_id_falls_through(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, tier3_enrolled=True, description="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "workflow_id": None,
                "confidence": 0.0,
                "reasoning": "none fits",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_3_registry.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_3_registry.classify(
        db, message=msg, registry=[wf], confidence_floor=0.65
    )
    assert matched is None
    assert conf is None


def test_classify_hallucinated_id_silent_fallthrough(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, tier3_enrolled=True, description="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "workflow_id": "fake-not-in-registry",
                "confidence": 0.99,
                "reasoning": "fictional",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_3_registry.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_3_registry.classify(
        db, message=msg, registry=[wf], confidence_floor=0.65
    )
    assert matched is None
    assert conf == 0.99
    assert err is None  # silent fallthrough on hallucination


def test_classify_empty_registry_returns_none(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    matched, conf, err, reasoning = tier_3_registry.classify(
        db, message=msg, registry=[], confidence_floor=0.65
    )
    assert matched is None
    assert err is None
