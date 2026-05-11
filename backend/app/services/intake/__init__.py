"""Phase R-6.2a — Intake adapter service package.

Two new intake adapters (form, file) parallel to the email adapter
from R-6.1. The classification cascade is source-agnostic; form
submissions + file uploads dispatch through the same three-tier
pipeline.

Public surface:
  - ``resolve_form_config(db, *, slug, tenant)`` — three-scope walk.
  - ``resolve_file_config(db, *, slug, tenant)`` — three-scope walk.
  - ``submit_form(db, *, config, submitted_data, submitter_metadata)``
    — persist + cascade.
  - ``presign_file_upload(db, *, config, original_filename,
    content_type, size_bytes, tenant_id)`` — produce presigned URL.
  - ``complete_file_upload(db, *, config, r2_key,
    original_filename, content_type, size_bytes, uploader_metadata,
    tenant_id)`` — persist + cascade.

Exceptions:
  - ``IntakeError`` — base (carries http_status).
  - ``IntakeConfigNotFound`` — slug not resolvable for tenant.
  - ``IntakeValidationError`` — schema or upload validation failure.
"""

from app.services.intake.resolver import (
    IntakeConfigNotFound,
    IntakeError,
    IntakeValidationError,
    resolve_file_config,
    resolve_form_config,
)
from app.services.intake.form_adapter import (
    FormSubmissionPayload,
    submit_form,
    validate_form_payload,
)
from app.services.intake.file_adapter import (
    FileUploadPayload,
    complete_file_upload,
    presign_file_upload,
)

__all__ = [
    "IntakeError",
    "IntakeConfigNotFound",
    "IntakeValidationError",
    "resolve_form_config",
    "resolve_file_config",
    "FormSubmissionPayload",
    "validate_form_payload",
    "submit_form",
    "FileUploadPayload",
    "presign_file_upload",
    "complete_file_upload",
]
