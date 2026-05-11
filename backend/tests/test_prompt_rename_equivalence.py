"""Phase R-6.2a — Tier 2/3 prompt-rename behavioral equivalence.

The R-6.1a ``email.classify_into_*`` prompts were renamed to
``intake.classify_into_*`` with an ``adapter_type`` variable. This
file verifies:

  - tier_2_taxonomy.classify uses the new prompt key.
  - tier_3_registry.classify uses the new prompt key.
  - When ``adapter_type="email"``, the variables shape passed to the
    prompt is equivalent to the R-6.1a-era shape (subject +
    sender_email + sender_name + body_excerpt + taxonomy_json /
    registry_json + the new ``adapter_type`` literal "email").

Pre-existing R-6.1a regression suites
(``test_classification_tier_2_taxonomy.py`` /
``test_classification_tier_3_registry.py``) MUST stay green after
this rename — they were updated in lockstep with this change.
"""

from __future__ import annotations

import uuid

from tests._classification_fixtures import (  # noqa: F401
    db,
    make_email_account,
    make_inbound_email,
    make_intelligence_result,
    make_workflow,
    tenant_pair,
)
from app.services.classification import tier_2_taxonomy, tier_3_registry


def test_tier_2_uses_intake_prompt_key(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)

    # Seed a taxonomy node so the LLM call fires.
    from app.models.email_classification import TenantWorkflowEmailCategory

    wf = make_workflow(db, a)
    cat = TenantWorkflowEmailCategory(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        label="Test category",
        mapped_workflow_id=wf.id,
        is_active=True,
    )
    db.add(cat)
    db.commit()

    captured_kwargs: dict = {}

    def _fake_execute(db, **kwargs):
        captured_kwargs.update(kwargs)
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.9,
                "reasoning": "matched",
            }
        )

    from app.services.intelligence import intelligence_service

    monkeypatch.setattr(intelligence_service, "execute", _fake_execute)

    taxonomy = tier_2_taxonomy.list_active_taxonomy(db, a.id)
    matched, conf, _err, _r = tier_2_taxonomy.classify(
        db,
        message=msg,
        taxonomy=taxonomy,
        confidence_floor=0.55,
    )

    # The renamed prompt is used.
    assert captured_kwargs.get("prompt_key") == "intake.classify_into_taxonomy"
    # adapter_type variable is passed and = "email" for email path.
    vars_ = captured_kwargs.get("variables", {})
    assert vars_.get("adapter_type") == "email"
    # R-6.1a-era variables still present.
    assert "subject" in vars_
    assert "sender_email" in vars_
    assert "taxonomy_json" in vars_
    # Caller module also updated.
    assert captured_kwargs.get("caller_module") == (
        "intake_classification.tier_2"
    )
    assert matched is not None


def test_tier_3_uses_intake_prompt_key(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    wf = make_workflow(db, a, tier3_enrolled=True)

    captured_kwargs: dict = {}

    def _fake_execute(db, **kwargs):
        captured_kwargs.update(kwargs)
        return make_intelligence_result(
            response_parsed={
                "workflow_id": wf.id,
                "confidence": 0.9,
                "reasoning": "matched",
            }
        )

    from app.services.intelligence import intelligence_service

    monkeypatch.setattr(intelligence_service, "execute", _fake_execute)

    registry = tier_3_registry.assemble_registry(db, a.id)
    matched, conf, _err, _r = tier_3_registry.classify(
        db,
        message=msg,
        registry=registry,
        confidence_floor=0.65,
    )

    assert captured_kwargs.get("prompt_key") == "intake.classify_into_registry"
    vars_ = captured_kwargs.get("variables", {})
    assert vars_.get("adapter_type") == "email"
    assert "registry_json" in vars_
    assert captured_kwargs.get("caller_module") == (
        "intake_classification.tier_3"
    )
    assert matched is not None


def test_tier_2_classify_form_passes_form_adapter_type(db, tenant_pair, monkeypatch):
    """When dispatching from a form, adapter_type must be "form"."""
    a, _ = tenant_pair

    from app.models.email_classification import TenantWorkflowEmailCategory

    wf = make_workflow(db, a)
    cat = TenantWorkflowEmailCategory(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        label="Form category",
        mapped_workflow_id=wf.id,
        is_active=True,
    )
    db.add(cat)
    db.commit()

    captured: dict = {}

    def _fake_execute(db, **kwargs):
        captured.update(kwargs)
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.9,
                "reasoning": "matched",
            }
        )

    from app.services.intelligence import intelligence_service

    monkeypatch.setattr(intelligence_service, "execute", _fake_execute)

    taxonomy = tier_2_taxonomy.list_active_taxonomy(db, a.id)
    matched, _conf, _err, _r = tier_2_taxonomy.classify_form(
        db,
        submission_id=str(uuid.uuid4()),
        tenant_id=a.id,
        form_slug="personalization-request",
        submitted_data={
            "family_contact_email": "mary@hopkins.example.com",
            "family_contact_name": "Mary Hopkins",
        },
        taxonomy=taxonomy,
        confidence_floor=0.55,
    )

    assert captured.get("prompt_key") == "intake.classify_into_taxonomy"
    assert captured["variables"]["adapter_type"] == "form"
    assert matched is not None


def test_tier_2_classify_file_passes_file_adapter_type(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair

    from app.models.email_classification import TenantWorkflowEmailCategory

    wf = make_workflow(db, a)
    cat = TenantWorkflowEmailCategory(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        label="File category",
        mapped_workflow_id=wf.id,
        is_active=True,
    )
    db.add(cat)
    db.commit()

    captured: dict = {}

    def _fake_execute(db, **kwargs):
        captured.update(kwargs)
        return make_intelligence_result(
            response_parsed={
                "category_id": cat.id,
                "confidence": 0.9,
                "reasoning": "matched",
            }
        )

    from app.services.intelligence import intelligence_service

    monkeypatch.setattr(intelligence_service, "execute", _fake_execute)

    taxonomy = tier_2_taxonomy.list_active_taxonomy(db, a.id)
    matched, _conf, _err, _r = tier_2_taxonomy.classify_file(
        db,
        upload_id=str(uuid.uuid4()),
        tenant_id=a.id,
        file_slug="death-certificate",
        original_filename="smith.pdf",
        content_type="application/pdf",
        uploader_metadata={"uploader_email": "mary@hopkins.example.com"},
        taxonomy=taxonomy,
        confidence_floor=0.55,
    )

    assert captured.get("prompt_key") == "intake.classify_into_taxonomy"
    assert captured["variables"]["adapter_type"] == "file"
    assert "filename" in captured["variables"]["body_excerpt"]
    assert matched is not None
