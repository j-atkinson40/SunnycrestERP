"""Phase R-6.2a — Form intake adapter unit + integration tests.

Covers:
  - Form schema validation per-field-type (text/email/select/etc.)
  - Required vs optional field handling
  - submit_form: persistence + cascade hook
  - Three-scope resolver (tenant_override → vertical_default →
    platform_default)
"""

from __future__ import annotations

import uuid

import pytest

from tests._classification_fixtures import (  # noqa: F401
    db,
    tenant_pair,
)
from app.models.intake_form_configuration import IntakeFormConfiguration
from app.models.intake_form_submission import IntakeFormSubmission
from app.services.intake import (
    IntakeValidationError,
    resolve_form_config,
    submit_form,
    validate_form_payload,
)


# ── Schema validation ───────────────────────────────────────────────


def _personalization_schema():
    return {
        "version": "1.0",
        "fields": [
            {"id": "deceased_name", "type": "text", "required": True, "max_length": 200},
            {"id": "family_contact_email", "type": "email", "required": True},
            {
                "id": "relationship_to_deceased",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "spouse", "label": "Spouse"},
                    {"value": "child", "label": "Child"},
                ],
            },
            {"id": "phone", "type": "phone", "required": False},
            {"id": "notes", "type": "textarea", "required": False, "max_length": 1000},
            {"id": "needs_followup", "type": "checkbox", "required": False},
        ],
    }


def test_validate_form_payload_happy_path():
    schema = _personalization_schema()
    coerced = validate_form_payload(
        form_schema=schema,
        submitted_data={
            "deceased_name": "John Smith",
            "family_contact_email": "Mary@Hopkins.example.com",
            "relationship_to_deceased": "spouse",
            "phone": "555-123-4567",
            "notes": "Loved gardening.",
            "needs_followup": True,
        },
    )
    assert coerced["deceased_name"] == "John Smith"
    # Email lowercased.
    assert coerced["family_contact_email"] == "mary@hopkins.example.com"
    assert coerced["relationship_to_deceased"] == "spouse"
    assert coerced["phone"] == "555-123-4567"
    assert coerced["notes"] == "Loved gardening."
    assert coerced["needs_followup"] is True


def test_validate_form_payload_rejects_missing_required():
    schema = _personalization_schema()
    with pytest.raises(IntakeValidationError) as exc:
        validate_form_payload(
            form_schema=schema,
            submitted_data={
                "deceased_name": "John Smith",
                # Missing required email + relationship.
            },
        )
    err_strs = exc.value.details.get("errors", [])
    assert any("family_contact_email" in s for s in err_strs)
    assert any("relationship_to_deceased" in s for s in err_strs)


def test_validate_form_payload_rejects_invalid_email():
    schema = _personalization_schema()
    with pytest.raises(IntakeValidationError):
        validate_form_payload(
            form_schema=schema,
            submitted_data={
                "deceased_name": "John Smith",
                "family_contact_email": "not-an-email",
                "relationship_to_deceased": "spouse",
            },
        )


def test_validate_form_payload_rejects_invalid_select():
    schema = _personalization_schema()
    with pytest.raises(IntakeValidationError):
        validate_form_payload(
            form_schema=schema,
            submitted_data={
                "deceased_name": "John Smith",
                "family_contact_email": "ok@x.com",
                "relationship_to_deceased": "not-an-option",
            },
        )


def test_validate_form_payload_enforces_max_length():
    schema = _personalization_schema()
    with pytest.raises(IntakeValidationError):
        validate_form_payload(
            form_schema=schema,
            submitted_data={
                "deceased_name": "x" * 201,
                "family_contact_email": "ok@x.com",
                "relationship_to_deceased": "spouse",
            },
        )


def test_validate_form_payload_drops_unknown_fields():
    schema = _personalization_schema()
    coerced = validate_form_payload(
        form_schema=schema,
        submitted_data={
            "deceased_name": "John Smith",
            "family_contact_email": "ok@x.com",
            "relationship_to_deceased": "spouse",
            "unknown_field": "should be dropped",
        },
    )
    assert "unknown_field" not in coerced


def test_validate_form_payload_treats_empty_string_as_missing():
    """Empty strings for required fields trigger required-check
    failure (matches HTML form semantics)."""
    schema = _personalization_schema()
    with pytest.raises(IntakeValidationError):
        validate_form_payload(
            form_schema=schema,
            submitted_data={
                "deceased_name": "   ",  # whitespace only
                "family_contact_email": "ok@x.com",
                "relationship_to_deceased": "spouse",
            },
        )


# ── Three-scope resolver ────────────────────────────────────────────


def test_resolve_form_config_returns_vertical_default(db, tenant_pair):
    """Tenant with funeral_home vertical resolves canonical seeded
    personalization-request form."""
    a, _ = tenant_pair
    # Mutate vertical to funeral_home so the seeded vertical_default
    # matches.
    a.vertical = "funeral_home"
    db.commit()
    config = resolve_form_config(
        db, slug="personalization-request", tenant=a
    )
    assert config is not None
    assert config.scope == "vertical_default"
    assert config.tenant_id is None
    assert config.vertical == "funeral_home"


def test_resolve_form_config_tenant_override_wins(db, tenant_pair):
    """When tenant has an override, it wins over vertical_default."""
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    override = IntakeFormConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        vertical=None,
        scope="tenant_override",
        name="Hopkins-customized form",
        slug="personalization-request",
        form_schema={"version": "1.0", "fields": []},
        is_active=True,
    )
    db.add(override)
    db.commit()

    config = resolve_form_config(
        db, slug="personalization-request", tenant=a
    )
    assert config is not None
    assert config.scope == "tenant_override"
    assert config.tenant_id == a.id

    db.delete(override)
    db.commit()


def test_resolve_form_config_returns_none_when_no_match(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "manufacturing"  # not funeral_home — won't match seed
    db.commit()
    config = resolve_form_config(
        db, slug="personalization-request", tenant=a
    )
    # vertical_default is funeral_home; mfg tenant doesn't match.
    assert config is None


# ── submit_form persistence ─────────────────────────────────────────


def test_submit_form_persists_submission(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    # Stub out cascade so we don't fire LLMs in tests.
    from app.services.classification import dispatch as dispatch_mod

    def _stub_cascade(db, *, submission, config):
        return {"tier": None}

    monkeypatch.setattr(
        dispatch_mod, "classify_and_fire_form", _stub_cascade, raising=True
    )

    config = resolve_form_config(
        db, slug="personalization-request", tenant=a
    )
    assert config is not None

    submission = submit_form(
        db,
        config=config,
        submitted_data={
            "deceased_name": "John Smith",
            "family_contact_email": "mary@hopkins.example.com",
            "relationship_to_deceased": "spouse",
            "preferred_personalization": "Loved gardening.",
            "family_contact_name": "Mary Hopkins",
        },
        submitter_metadata={"ip": "1.2.3.4", "user_agent": "test"},
        tenant_id=a.id,
    )
    db.commit()

    assert submission.id
    assert submission.tenant_id == a.id
    assert submission.config_id == config.id
    assert submission.submitted_data["deceased_name"] == "John Smith"
    assert submission.submitted_data["family_contact_email"] == (
        "mary@hopkins.example.com"
    )
    assert submission.submitter_metadata["ip"] == "1.2.3.4"

    # Verify persisted via fresh query.
    fresh = (
        db.query(IntakeFormSubmission)
        .filter(IntakeFormSubmission.id == submission.id)
        .first()
    )
    assert fresh is not None


def test_submit_form_cascade_failure_does_not_block_persistence(
    db, tenant_pair, monkeypatch
):
    """Best-effort cascade — failure logs but persists submission."""
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    from app.services.classification import dispatch as dispatch_mod

    def _failing_cascade(db, *, submission, config):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        dispatch_mod, "classify_and_fire_form", _failing_cascade, raising=True
    )

    config = resolve_form_config(
        db, slug="personalization-request", tenant=a
    )
    submission = submit_form(
        db,
        config=config,
        submitted_data={
            "deceased_name": "John Smith",
            "family_contact_email": "mary@hopkins.example.com",
            "relationship_to_deceased": "spouse",
            "preferred_personalization": "...",
            "family_contact_name": "Mary",
        },
        submitter_metadata={},
        tenant_id=a.id,
    )
    db.commit()

    # Submission persisted regardless of cascade failure.
    assert submission.id
    fresh = (
        db.query(IntakeFormSubmission)
        .filter(IntakeFormSubmission.id == submission.id)
        .first()
    )
    assert fresh is not None
