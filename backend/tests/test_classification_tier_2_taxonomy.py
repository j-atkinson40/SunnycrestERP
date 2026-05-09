"""Phase R-6.1a — Tier 2 taxonomy classification."""

from __future__ import annotations

from tests._classification_fixtures import (  # noqa: F401
    db,
    make_category,
    make_email_account,
    make_inbound_email,
    make_intelligence_result,
    make_workflow,
    tenant_pair,
)
from app.services.classification import tier_2_taxonomy


def test_empty_taxonomy_returns_none(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[], confidence_floor=0.55
    )
    assert matched is None
    assert conf is None
    assert err is None
    assert reasoning is None


def test_classify_dispatches_above_floor(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a, name="Pricing reply")
    cat = make_category(
        db,
        a,
        label="Pricing inquiry",
        description="Customer asks about pricing",
        mapped_workflow_id=wf.id,
    )
    msg = make_inbound_email(db, tenant=a, account=acct)
    taxonomy = [cat]

    def stub(db_, **kwargs):
        assert kwargs.get("prompt_key") == "email.classify_into_taxonomy"
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.9,
                "reasoning": "Subject mentions pricing.",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )

    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=taxonomy, confidence_floor=0.55
    )
    assert matched is not None
    assert matched.id == cat.id
    assert conf == 0.9
    assert err is None
    assert reasoning == "Subject mentions pricing."


def test_classify_below_floor_returns_no_match(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a)
    cat = make_category(db, a, label="x", mapped_workflow_id=wf.id)
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.4,
                "reasoning": "uncertain",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None
    assert conf == 0.4
    assert err is None
    assert reasoning == "uncertain"


def test_classify_null_category_id_falls_through(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    cat = make_category(db, a, label="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "category_id": None,
                "confidence": 0.0,
                "reasoning": "no good fit",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None
    assert conf is None
    assert err is None
    assert reasoning == "no good fit"


def test_classify_hallucinated_id_silent_fallthrough(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    cat = make_category(db, a, label="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "category_id": "fake-id-not-in-taxonomy",
                "confidence": 0.95,
                "reasoning": "I made this up",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None
    assert conf == 0.95
    assert err is None  # silent fallthrough


def test_classify_unmapped_category_falls_through(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    cat = make_category(db, a, label="x")  # mapped_workflow_id=None
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.95,
                "reasoning": "match",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None
    assert conf == 0.95


def test_classify_inactive_workflow_falls_through(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a)
    wf.is_active = False
    db.commit()
    cat = make_category(db, a, label="x", mapped_workflow_id=wf.id)
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.95,
                "reasoning": "match",
            }
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None


def test_classify_llm_failure_returns_error_string(
    db, tenant_pair, monkeypatch
):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    cat = make_category(db, a, label="x")
    msg = make_inbound_email(db, tenant=a, account=acct)

    def stub(db_, **kwargs):
        return make_intelligence_result(
            status="api_error",
            response_parsed=None,
            error_message="rate limited",
        )

    monkeypatch.setattr(
        "app.services.classification.tier_2_taxonomy.intelligence_service.execute",
        stub,
    )
    matched, conf, err, reasoning = tier_2_taxonomy.classify(
        db, message=msg, taxonomy=[cat], confidence_floor=0.55
    )
    assert matched is None
    assert err is not None
    assert "tier_2_status" in err
