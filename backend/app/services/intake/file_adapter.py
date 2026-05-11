"""Phase R-6.2a — File intake adapter.

Two-phase upload flow:

  1. ``presign_file_upload`` — server validates content_type + size
     hint against config caps, builds canonical R2 key, returns
     presigned PUT URL (15 min TTL). Browser uploads bytes directly
     to R2 (no proxying through Bridgeable).

  2. ``complete_file_upload`` — browser POSTs metadata + R2 key.
     Server verifies object exists via head_object + re-checks
     size against the cap. Persists ``IntakeFileUpload`` row and
     fires the classification cascade.

Per-upload caps: ``allowed_content_types`` + ``max_file_size_bytes``
+ ``max_file_count``. Multi-file uploads make one IntakeFileUpload
row per file; the caller orchestrates the loop.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_file_upload import IntakeFileUpload
from app.services.intake.resolver import IntakeValidationError
from app.services import legacy_r2_client

logger = logging.getLogger(__name__)


@dataclass
class FileUploadPayload:
    """Source payload shape for the file adapter — the completion
    request after the browser has uploaded to R2."""

    r2_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploader_metadata: dict[str, Any] = field(default_factory=dict)


def _build_r2_key(
    config: IntakeFileConfiguration,
    *,
    tenant_id: str,
    upload_id: str,
    original_filename: str,
) -> str:
    """Build the canonical R2 key from the config template."""
    template = (
        config.r2_key_prefix_template
        or "tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}"
    )
    prefix = template.format(
        tenant_id=tenant_id,
        adapter_slug=config.slug,
        upload_id=upload_id,
    )
    # Strip path separators from filename — defense-in-depth.
    safe_filename = original_filename.replace("/", "_").replace("\\", "_")
    return f"{prefix.rstrip('/')}/{safe_filename}"


def presign_file_upload(
    db: Session,
    *,
    config: IntakeFileConfiguration,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    tenant_id: str,
    expires_in: int = 900,
) -> dict[str, Any]:
    """Validate the upload request + return a presigned PUT URL.

    The returned upload_id is the eventual IntakeFileUpload row id;
    the browser includes it in the completion POST so the server
    can reconstruct the R2 key.

    Returns ``{"upload_id": str, "r2_key": str, "url": str,
    "method": "PUT", "headers": {...}, "expires_in": int}``.

    Raises ``IntakeValidationError`` on validation failure.
    """
    if not isinstance(content_type, str) or not content_type:
        raise IntakeValidationError("content_type is required.")
    allowed = config.allowed_content_types or []
    if isinstance(allowed, list) and len(allowed) > 0:
        if content_type not in allowed:
            raise IntakeValidationError(
                f"content_type {content_type!r} not in allowed list.",
                details={"allowed": list(allowed)},
            )

    if not isinstance(size_bytes, int) or size_bytes <= 0:
        raise IntakeValidationError("size_bytes must be a positive integer.")
    if size_bytes > (config.max_file_size_bytes or 0):
        raise IntakeValidationError(
            "size_bytes exceeds configuration cap.",
            details={"max_file_size_bytes": config.max_file_size_bytes},
        )

    if not isinstance(original_filename, str) or not original_filename.strip():
        raise IntakeValidationError("original_filename is required.")

    upload_id = str(uuid.uuid4())
    r2_key = _build_r2_key(
        config,
        tenant_id=tenant_id,
        upload_id=upload_id,
        original_filename=original_filename,
    )

    try:
        signed = legacy_r2_client.generate_presigned_upload_url(
            r2_key,
            content_type=content_type,
            expires_in=expires_in,
            max_size_bytes=config.max_file_size_bytes,
        )
    except RuntimeError as exc:
        # R2 not configured — surface as 503 via http_status overload.
        raise IntakeValidationError(
            f"File upload backend unavailable: {exc}",
        )

    return {
        "upload_id": upload_id,
        "r2_key": r2_key,
        "url": signed["url"],
        "method": signed["method"],
        "headers": signed["headers"],
        "expires_in": expires_in,
    }


def complete_file_upload(
    db: Session,
    *,
    config: IntakeFileConfiguration,
    payload: FileUploadPayload,
    tenant_id: str,
    verify_r2_head: bool = True,
) -> IntakeFileUpload:
    """Validate the completion + persist + fire cascade best-effort.

    ``verify_r2_head=True`` (default) confirms the R2 object exists
    via head_object before persisting; tests + idempotent re-runs may
    skip when R2 is unavailable.

    Returns the persisted IntakeFileUpload row.
    """
    if not isinstance(payload.r2_key, str) or not payload.r2_key:
        raise IntakeValidationError("r2_key is required.")
    if not isinstance(payload.original_filename, str) or not payload.original_filename:
        raise IntakeValidationError("original_filename is required.")
    if not isinstance(payload.content_type, str) or not payload.content_type:
        raise IntakeValidationError("content_type is required.")

    allowed = config.allowed_content_types or []
    if isinstance(allowed, list) and len(allowed) > 0:
        if payload.content_type not in allowed:
            raise IntakeValidationError(
                f"content_type {payload.content_type!r} not in allowed list.",
                details={"allowed": list(allowed)},
            )

    if not isinstance(payload.size_bytes, int) or payload.size_bytes <= 0:
        raise IntakeValidationError("size_bytes must be a positive integer.")
    if payload.size_bytes > (config.max_file_size_bytes or 0):
        raise IntakeValidationError(
            "size_bytes exceeds configuration cap.",
            details={"max_file_size_bytes": config.max_file_size_bytes},
        )

    # Defense-in-depth: ensure the R2 key starts with the canonical
    # template prefix. Prevents abuse via a forged completion call.
    canonical_prefix = (
        (config.r2_key_prefix_template or "")
        .format(
            tenant_id=tenant_id,
            adapter_slug=config.slug,
            upload_id="",
        )
        .rstrip("/")
    )
    # We compare on the leading segments since the upload_id portion
    # is dynamic. The canonical_prefix above has upload_id="" expanded
    # to "" — what remains is the static head.
    if canonical_prefix and not payload.r2_key.startswith(
        canonical_prefix.split("{")[0]
    ):
        raise IntakeValidationError(
            "r2_key does not match canonical prefix.",
            details={"r2_key": payload.r2_key},
        )

    # Verify R2 object exists + size matches (optional).
    if verify_r2_head:
        head = legacy_r2_client.head_object(payload.r2_key)
        if head is None:
            raise IntakeValidationError(
                "Uploaded object not found in storage.",
                details={"r2_key": payload.r2_key},
            )
        actual_size = head.get("size_bytes")
        if isinstance(actual_size, int) and actual_size > (
            config.max_file_size_bytes or 0
        ):
            raise IntakeValidationError(
                "Stored object exceeds size cap.",
                details={
                    "max_file_size_bytes": config.max_file_size_bytes,
                    "actual_size": actual_size,
                },
            )
        # Use the verified actual size if present.
        if isinstance(actual_size, int) and actual_size > 0:
            payload.size_bytes = actual_size

    upload = IntakeFileUpload(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        config_id=config.id,
        r2_key=payload.r2_key,
        original_filename=payload.original_filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        uploader_metadata=payload.uploader_metadata or {},
    )
    db.add(upload)
    db.flush()

    # Fire classification cascade best-effort. Caller commits.
    try:
        from app.services.classification.dispatch import (
            classify_and_fire_file,
        )

        classify_and_fire_file(
            db,
            upload=upload,
            config=config,
        )
        db.flush()
    except Exception:
        logger.exception(
            "File classification cascade failed for upload %s — "
            "non-blocking; upload preserved for replay.",
            upload.id,
        )

    return upload
