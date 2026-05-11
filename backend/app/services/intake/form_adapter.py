"""Phase R-6.2a — Form intake adapter.

Canonical adapter contract (mirrors email adapter from R-6.1):

    adapter.ingest(db, *, tenant_config, source_payload)
        → canonical_record

For forms: ``submit_form(db, *, config, submitted_data,
submitter_metadata, tenant_id)`` validates against ``config.form_schema``,
persists an ``IntakeFormSubmission`` row, then fires the classification
cascade best-effort. Cascade failure NEVER blocks persistence — the
submission is recorded; classification is replayable later.

Field types v1: text, textarea, email, phone, date, select, checkbox.
Conditional logic + multiselect deferred.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.intake_form_configuration import IntakeFormConfiguration
from app.models.intake_form_submission import IntakeFormSubmission
from app.services.intake.resolver import IntakeValidationError

logger = logging.getLogger(__name__)


# RFC 5322 minimal email regex — pragmatic, not exhaustive. Client-side
# validation catches the obvious cases; server-side gate is the last
# line of defense before persistence.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Lenient phone regex — digits + optional separators / + prefix.
_PHONE_RE = re.compile(r"^[\d\s\-\+\(\)\.]{7,}$")


@dataclass
class FormSubmissionPayload:
    """Source payload shape for the form adapter.

    Mirrors ``ProviderFetchedMessage`` from the email adapter — the
    raw input before persistence.
    """

    submitted_data: dict[str, Any]
    submitter_metadata: dict[str, Any] = field(default_factory=dict)


# ── Schema validation ───────────────────────────────────────────────


def _validate_field(
    field_def: dict[str, Any],
    raw_value: Any,
) -> tuple[Any, str | None]:
    """Validate a single field against its schema definition.

    Returns ``(coerced_value, error_message)`` — error_message is None
    on success. Coerced value may be ``None`` for missing optional
    fields.
    """
    field_id = field_def.get("id")
    field_type = field_def.get("type") or "text"
    required = bool(field_def.get("required"))

    # Treat empty strings as missing for required-check purposes
    # (matches HTML form semantics).
    if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
        if required:
            return None, f"Field '{field_id}' is required."
        return None, None

    # Type-specific validation + coercion.
    if field_type in ("text", "textarea"):
        if not isinstance(raw_value, str):
            return None, f"Field '{field_id}' must be a string."
        max_length = field_def.get("max_length")
        if isinstance(max_length, int) and len(raw_value) > max_length:
            return None, (
                f"Field '{field_id}' exceeds max length {max_length}."
            )
        return raw_value, None

    if field_type == "email":
        if not isinstance(raw_value, str) or not _EMAIL_RE.match(raw_value):
            return None, f"Field '{field_id}' must be a valid email."
        return raw_value.lower(), None

    if field_type == "phone":
        if not isinstance(raw_value, str) or not _PHONE_RE.match(raw_value):
            return None, f"Field '{field_id}' must be a valid phone number."
        return raw_value, None

    if field_type == "date":
        if not isinstance(raw_value, str):
            return None, f"Field '{field_id}' must be a date string."
        # ISO date format YYYY-MM-DD (loose check).
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw_value):
            return None, f"Field '{field_id}' must be ISO date (YYYY-MM-DD)."
        return raw_value, None

    if field_type == "select":
        options = field_def.get("options") or []
        valid_values = {opt.get("value") for opt in options if isinstance(opt, dict)}
        if raw_value not in valid_values:
            return None, (
                f"Field '{field_id}' must be one of "
                f"{sorted(v for v in valid_values if v is not None)}."
            )
        return raw_value, None

    if field_type == "checkbox":
        if not isinstance(raw_value, bool):
            return None, f"Field '{field_id}' must be a boolean."
        return raw_value, None

    # Unknown field type — accept verbatim (forward-compat).
    return raw_value, None


def validate_form_payload(
    *,
    form_schema: dict[str, Any],
    submitted_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate + coerce ``submitted_data`` against ``form_schema``.

    Raises ``IntakeValidationError`` on any field failure (carries
    ``details["errors"]`` as a list of per-field error strings).
    Returns the coerced data dict on success (only known fields are
    included; unknown keys silently dropped).
    """
    if not isinstance(form_schema, dict):
        raise IntakeValidationError(
            "form_schema is malformed; cannot validate."
        )
    fields = form_schema.get("fields") or []
    if not isinstance(fields, list):
        raise IntakeValidationError("form_schema.fields must be a list.")

    coerced: dict[str, Any] = {}
    errors: list[str] = []

    for field_def in fields:
        if not isinstance(field_def, dict):
            continue
        field_id = field_def.get("id")
        if not isinstance(field_id, str):
            continue
        raw = submitted_data.get(field_id)
        value, err = _validate_field(field_def, raw)
        if err is not None:
            errors.append(err)
            continue
        if value is not None:
            coerced[field_id] = value

    if errors:
        raise IntakeValidationError(
            "Form payload failed validation.",
            details={"errors": errors},
        )

    return coerced


# ── Persistence + cascade ───────────────────────────────────────────


def submit_form(
    db: Session,
    *,
    config: IntakeFormConfiguration,
    submitted_data: dict[str, Any],
    submitter_metadata: dict[str, Any] | None = None,
    tenant_id: str,
) -> IntakeFormSubmission:
    """Validate + persist a form submission, then fire the cascade
    best-effort.

    Tenant isolation: ``tenant_id`` is mandatory (caller resolves
    from the public-page tenant slug). The submission's
    ``tenant_id`` is the resolved tenant, NOT the config's tenant_id
    (which may be None for platform/vertical-default configs).

    Returns the persisted submission. Cascade outcome is captured
    on ``submission.classification_*`` columns.
    """
    coerced = validate_form_payload(
        form_schema=config.form_schema or {},
        submitted_data=submitted_data,
    )

    submission = IntakeFormSubmission(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        config_id=config.id,
        submitted_data=coerced,
        submitter_metadata=submitter_metadata or {},
    )
    db.add(submission)
    db.flush()

    # Fire classification cascade best-effort. Caller commits.
    try:
        from app.services.classification.dispatch import (
            classify_and_fire_form,
        )

        classify_and_fire_form(
            db,
            submission=submission,
            config=config,
        )
        db.flush()
    except Exception:
        logger.exception(
            "Form classification cascade failed for submission %s — "
            "non-blocking; submission preserved for replay.",
            submission.id,
        )

    return submission
