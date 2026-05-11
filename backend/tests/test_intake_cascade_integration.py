"""Phase R-6.2a — Form + file cascade integration tests.

Verifies:
  - Tier 1 form rules + file rules evaluate correctly per adapter_type
  - dispatch.classify_and_fire_form fires workflows + updates
    submission.classification_* columns
  - dispatch.classify_and_fire_file mirrors the form path
  - cascade exhaustion writes payload with tier=None
  - Tier 1 suppression (workflow_id=None) sets is_suppressed=True
"""

from __future__ import annotations

import uuid

from tests._classification_fixtures import (  # noqa: F401
    db,
    make_intelligence_result,
    make_workflow,
    tenant_pair,
)
from app.models.email_classification import TenantWorkflowEmailRule
from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_file_upload import IntakeFileUpload
from app.models.intake_form_configuration import IntakeFormConfiguration
from app.models.intake_form_submission import IntakeFormSubmission
from app.services.classification import tier_1_rules
from app.services.classification.dispatch import (
    classify_and_fire_file,
    classify_and_fire_form,
)


def _make_form_config(db, tenant):
    cfg = IntakeFormConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        vertical=None,
        scope="tenant_override",
        name="Test form",
        slug="test-form",
        form_schema={
            "version": "1.0",
            "fields": [
                {"id": "deceased_name", "type": "text", "required": True},
                {
                    "id": "family_contact_email",
                    "type": "email",
                    "required": True,
                },
            ],
        },
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _make_file_config(db, tenant):
    cfg = IntakeFileConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        vertical=None,
        scope="tenant_override",
        name="Test file",
        slug="test-file",
        allowed_content_types=["application/pdf"],
        max_file_size_bytes=10 * 1024 * 1024,
        max_file_count=1,
        r2_key_prefix_template=(
            "tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}"
        ),
        metadata_schema={"version": "1.0", "fields": []},
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _make_submission(db, tenant, config, **submitted):
    sub = IntakeFormSubmission(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        config_id=config.id,
        submitted_data=submitted,
        submitter_metadata={},
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _make_upload(db, tenant, config, **fields):
    fields.setdefault("r2_key", f"tenants/{tenant.id}/intake/test-file/{uuid.uuid4()}/x.pdf")
    fields.setdefault("original_filename", "x.pdf")
    fields.setdefault("content_type", "application/pdf")
    fields.setdefault("size_bytes", 100_000)
    fields.setdefault("uploader_metadata", {})
    up = IntakeFileUpload(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        config_id=config.id,
        **fields,
    )
    db.add(up)
    db.commit()
    db.refresh(up)
    return up


# ── Tier 1 form rule matching ───────────────────────────────────────


def test_match_form_form_slug_equals(db, tenant_pair):
    a, _ = tenant_pair
    assert tier_1_rules.match_form(
        {"form_slug_equals": "personalization-request"},
        form_slug="personalization-request",
        submitted_data={},
        submitter_metadata={},
    )
    assert not tier_1_rules.match_form(
        {"form_slug_equals": "personalization-request"},
        form_slug="other-slug",
        submitted_data={},
        submitter_metadata={},
    )


def test_match_form_submitter_domain_in(db, tenant_pair):
    a, _ = tenant_pair
    assert tier_1_rules.match_form(
        {"submitter_domain_in": ["hopkins.example.com"]},
        form_slug="x",
        submitted_data={"family_contact_email": "mary@hopkins.example.com"},
        submitter_metadata={},
    )
    assert not tier_1_rules.match_form(
        {"submitter_domain_in": ["hopkins.example.com"]},
        form_slug="x",
        submitted_data={"family_contact_email": "other@elsewhere.test"},
        submitter_metadata={},
    )


def test_match_form_field_value_contains(db, tenant_pair):
    assert tier_1_rules.match_form(
        {"field_value_contains": {"preferred_personalization": "garden"}},
        form_slug="x",
        submitted_data={
            "preferred_personalization": "Loved Gardening as a hobby."
        },
        submitter_metadata={},
    )
    assert not tier_1_rules.match_form(
        {"field_value_contains": {"preferred_personalization": "garden"}},
        form_slug="x",
        submitted_data={"preferred_personalization": "Loved music."},
        submitter_metadata={},
    )


# ── Tier 1 file rule matching ───────────────────────────────────────


def test_match_file_content_type_in(db, tenant_pair):
    assert tier_1_rules.match_file(
        {"content_type_in": ["application/pdf"]},
        file_slug="x",
        content_type="application/pdf",
        original_filename="x.pdf",
        uploader_metadata={},
    )
    assert not tier_1_rules.match_file(
        {"content_type_in": ["application/pdf"]},
        file_slug="x",
        content_type="image/jpeg",
        original_filename="x.jpg",
        uploader_metadata={},
    )


def test_match_file_filename_contains_any(db, tenant_pair):
    assert tier_1_rules.match_file(
        {"filename_contains_any": ["death_cert", "death-certificate"]},
        file_slug="x",
        content_type="application/pdf",
        original_filename="smith_DEATH_CERT.pdf",
        uploader_metadata={},
    )
    assert not tier_1_rules.match_file(
        {"filename_contains_any": ["death_cert"]},
        file_slug="x",
        content_type="application/pdf",
        original_filename="invoice.pdf",
        uploader_metadata={},
    )


# ── dispatch.classify_and_fire_form ─────────────────────────────────


def test_classify_and_fire_form_tier_1_fires_workflow(db, tenant_pair):
    a, _ = tenant_pair
    cfg = _make_form_config(db, a)
    wf = make_workflow(db, a)

    # Author a Tier 1 form rule that matches.
    rule = TenantWorkflowEmailRule(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        adapter_type="form",
        priority=0,
        name="Match all forms",
        match_conditions={"form_slug_equals": "test-form"},
        fire_action={"workflow_id": wf.id},
        is_active=True,
    )
    db.add(rule)
    db.commit()

    sub = _make_submission(
        db,
        a,
        cfg,
        deceased_name="John",
        family_contact_email="mary@hopkins.example.com",
    )

    result = classify_and_fire_form(db, submission=sub, config=cfg)
    db.commit()
    db.refresh(sub)

    assert result["tier"] == 1
    assert result["selected_workflow_id"] == wf.id
    assert sub.classification_tier == 1
    assert sub.classification_workflow_id == wf.id
    assert sub.classification_workflow_run_id is not None
    assert sub.classification_payload["tier_reasoning"]["tier1"][
        "matched_rule_id"
    ] == rule.id


def test_classify_and_fire_form_tier_1_suppression(db, tenant_pair):
    """Tier 1 rule with workflow_id=null suppresses the submission."""
    a, _ = tenant_pair
    cfg = _make_form_config(db, a)
    rule = TenantWorkflowEmailRule(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        adapter_type="form",
        priority=0,
        name="Suppress",
        match_conditions={"form_slug_equals": "test-form"},
        fire_action={"workflow_id": None},
        is_active=True,
    )
    db.add(rule)
    db.commit()

    sub = _make_submission(
        db, a, cfg,
        deceased_name="John",
        family_contact_email="mary@hopkins.example.com",
    )
    result = classify_and_fire_form(db, submission=sub, config=cfg)
    db.commit()
    db.refresh(sub)

    assert result["tier"] == 1
    assert result["is_suppressed"] is True
    assert sub.classification_is_suppressed is True
    assert sub.classification_workflow_id is None


def test_classify_and_fire_form_unclassified(db, tenant_pair, monkeypatch):
    """When no rules match + no taxonomy + no registry, classification
    falls through to unclassified (tier=None)."""
    a, _ = tenant_pair
    cfg = _make_form_config(db, a)
    sub = _make_submission(
        db, a, cfg,
        deceased_name="John",
        family_contact_email="mary@hopkins.example.com",
    )

    # No rules + no taxonomy + no registry — cascade exhausts.
    result = classify_and_fire_form(db, submission=sub, config=cfg)
    db.commit()
    db.refresh(sub)

    assert result["tier"] is None
    assert sub.classification_tier is None
    assert sub.classification_payload["tier_reasoning"]["tier1"] is None


# ── dispatch.classify_and_fire_file ─────────────────────────────────


def test_classify_and_fire_file_tier_1_fires_workflow(db, tenant_pair):
    a, _ = tenant_pair
    cfg = _make_file_config(db, a)
    wf = make_workflow(db, a)

    rule = TenantWorkflowEmailRule(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        adapter_type="file",
        priority=0,
        name="Match PDFs",
        match_conditions={"content_type_in": ["application/pdf"]},
        fire_action={"workflow_id": wf.id},
        is_active=True,
    )
    db.add(rule)
    db.commit()

    up = _make_upload(db, a, cfg)
    result = classify_and_fire_file(db, upload=up, config=cfg)
    db.commit()
    db.refresh(up)

    assert result["tier"] == 1
    assert result["selected_workflow_id"] == wf.id
    assert up.classification_tier == 1
    assert up.classification_workflow_id == wf.id
    assert up.classification_workflow_run_id is not None


def test_classify_and_fire_file_unclassified(db, tenant_pair):
    a, _ = tenant_pair
    cfg = _make_file_config(db, a)
    up = _make_upload(db, a, cfg)

    result = classify_and_fire_file(db, upload=up, config=cfg)
    db.commit()
    db.refresh(up)

    assert result["tier"] is None
    assert up.classification_tier is None
