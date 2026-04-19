"""DocumentRenderer — unified Jinja + WeasyPrint + R2 storage pipeline.

Phase D-1 shipped PDF-only rendering with a persisted Document row for
every call. Phase D-2 extends the pipeline to support three output
formats:

  pdf   — Jinja → WeasyPrint → R2 upload → Document + DocumentVersion rows
          (the D-1 behavior; still the default for PDF templates)
  html  — Jinja → rendered string returned to caller, no R2, no Document
  text  — Jinja → rendered string, plain-text-intended

The template's `output_format` column drives the default; callers may
override via the `output_format` kwarg on `render()`.

Key behaviors (PDF path — unchanged from D-1):

- Every `render()` call writes a Document AND a DocumentVersion row.
  The first version has is_current=True.
- `rerender()` flips the previous version's is_current=False and
  creates a new version with the incremented version_number.
- Rendering_context_hash (SHA-256 of the JSON-serialized context) is
  captured for every version so downstream code can detect
  dedup / data-changed / no-op regenerate situations.
- R2 storage path: `tenants/{company_id}/documents/{document_id}/v{n}.pdf`

Key behaviors (HTML/text path — new in D-2):

- No R2 upload, no Document row inserted.
- `RenderResult.rendered_content` holds the rendered string.
- If the template has a `subject_template`, it's also rendered and
  returned as `RenderResult.rendered_subject`.
- Caller is responsible for what to do with the output (email, log, etc).

Errors in any phase raise `DocumentRenderError`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.canonical_document import Document, DocumentVersion
from app.services import legacy_r2_client
from app.services.documents import template_loader

logger = logging.getLogger(__name__)


class DocumentRenderError(Exception):
    """Raised when template render or PDF generation fails."""


@dataclass
class RenderResult:
    """Result from `render()`.

    For PDF output:
      - output_format = "pdf"
      - document is the persisted Document row
      - rendered_content is the PDF bytes
    For HTML/text output:
      - output_format = "html" | "text"
      - document is None
      - rendered_content is the rendered string
      - rendered_subject is set if the template has a subject_template
    """

    output_format: str
    document: Document | None
    rendered_content: str | bytes
    template_version_id: str
    rendered_at: datetime
    rendered_subject: str | None = None


def _hash_context(context: dict[str, Any]) -> str:
    canonical = json.dumps(context, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _storage_key(company_id: str, document_id: str, version_number: int) -> str:
    return (
        f"tenants/{company_id}/documents/{document_id}/v{version_number}.pdf"
    )


def _jinja_env():
    """Return a Jinja2 Environment with safe-by-default autoescape for HTML."""
    try:
        from jinja2 import Environment, select_autoescape
    except ImportError as exc:
        raise DocumentRenderError(
            "Jinja2 is not installed — cannot render document template"
        ) from exc
    return Environment(autoescape=select_autoescape(["html", "xml"]))


def _render_jinja(body_template: str, context: dict[str, Any]) -> str:
    env = _jinja_env()
    try:
        tpl = env.from_string(body_template)
        return tpl.render(**context)
    except Exception as exc:  # noqa: BLE001
        raise DocumentRenderError(f"Template render failed: {exc}") from exc


def _html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Convert HTML to PDF via WeasyPrint. The ONLY place in the codebase
    allowed to instantiate `weasyprint.HTML(string=...)`. The ruff rule
    TID251 forbids usage outside this package."""
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise DocumentRenderError(
            "WeasyPrint is not installed — cannot generate PDF"
        ) from exc

    try:
        return HTML(string=html, base_url=base_url).write_pdf()
    except Exception as exc:  # noqa: BLE001
        raise DocumentRenderError(f"WeasyPrint failed: {exc}") from exc


# ── render() — unified entry point ─────────────────────────────────────


def render(
    db: Session,
    *,
    template_key: str | None = None,
    context: dict[str, Any],
    company_id: str,
    # D-9 addition — render a SPECIFIC version rather than the current
    # active for `template_key`. When provided, `template_key` is
    # ignored for lookup (the loader resolves by version id) but must
    # still be None or match the version's parent template_key for
    # clarity.
    template_version_id: str | None = None,
    # PDF-path metadata (ignored for html/text)
    document_type: str | None = None,
    title: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    caller_module: str | None = None,
    caller_workflow_run_id: str | None = None,
    caller_workflow_step_id: str | None = None,
    intelligence_execution_id: str | None = None,
    description: str | None = None,
    render_reason: str = "initial",
    # Specialty linkage kwargs
    sales_order_id: str | None = None,
    fh_case_id: str | None = None,
    disinterment_case_id: str | None = None,
    invoice_id: str | None = None,
    customer_statement_id: str | None = None,
    price_list_version_id: str | None = None,
    safety_program_generation_id: str | None = None,
    rendered_by_user_id: str | None = None,
    # D-2 additions
    output_format: str | None = None,
    return_document: bool | None = None,
    # D-3 addition — flags test renders so they're excluded from the
    # production Document Log by default.
    is_test_render: bool = False,
) -> RenderResult | Document:
    """Render a template to PDF/HTML/text.

    Resolution modes:
      - `template_key` (without `template_version_id`): loads the current
        active version via `template_loader.load` (tenant-first /
        platform-fallback). This is the production path.
      - `template_version_id`: loads THAT specific version directly via
        `template_loader.load_by_version_id`. Used by the test-render
        endpoint to render drafts + retired versions. D-9 unification.

    Exactly one of `template_key` / `template_version_id` must be provided.

    **Return value depends on output_format:**

    - output_format="pdf" (default when template is a PDF):
      Creates Document + DocumentVersion rows, uploads to R2. Returns a
      `Document` (for D-1 backward compat) — unless `return_document=False`
      is passed, in which case a full `RenderResult` is returned.

    - output_format="html"/"text": No Document is persisted. Returns a
      `RenderResult` with rendered_content (str) + rendered_subject (str|None).

    D-1 callers pass PDF templates and get a `Document` back — nothing
    changes for them. New D-2 callers (email_service) pass html templates
    and get `RenderResult` back.
    """
    if template_version_id is None and template_key is None:
        raise DocumentRenderError(
            "render() requires either `template_key` or `template_version_id`"
        )
    if template_version_id is not None:
        loaded = template_loader.load_by_version_id(
            template_version_id, db=db
        )
    else:
        # template_key is non-None here (checked above) but mypy needs
        # the narrow.
        assert template_key is not None
        loaded = template_loader.load(
            template_key, company_id=company_id, db=db
        )
    # Use the loaded template's key for the Document row even when the
    # caller invoked us with a version id — keeps the audit lineage
    # correct if the version's parent template_key differed.
    effective_template_key = loaded.template_key
    effective_format = output_format or loaded.output_format

    # HTML / text path: render + return, no Document
    if effective_format in ("html", "text"):
        rendered_body = _render_jinja(loaded.body_template, context)
        rendered_subject: str | None = None
        if loaded.subject_template:
            try:
                rendered_subject = _render_jinja(
                    loaded.subject_template, context
                )
            except DocumentRenderError:
                # Subject failures fall back to None rather than failing
                # the whole render; log and continue.
                logger.warning(
                    "Subject template render failed for %s — falling back to None",
                    template_key,
                )
        return RenderResult(
            output_format=effective_format,
            document=None,
            rendered_content=rendered_body,
            template_version_id=loaded.version_id,
            rendered_at=datetime.now(timezone.utc),
            rendered_subject=rendered_subject,
        )

    # PDF path: the D-1 flow
    if document_type is None or title is None:
        raise DocumentRenderError(
            "PDF render requires both `document_type` and `title`"
        )

    start = time.perf_counter()
    html = _render_jinja(loaded.body_template, context)
    pdf_bytes = _html_to_pdf(html, base_url=loaded.template_dir)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    context_hash = _hash_context(context)

    document_id = str(uuid.uuid4())
    storage_key = _storage_key(company_id, document_id, version_number=1)

    try:
        legacy_r2_client.upload_bytes(
            pdf_bytes, storage_key, content_type="application/pdf"
        )
    except Exception as exc:  # noqa: BLE001
        raise DocumentRenderError(
            f"R2 upload failed for document {document_id}: {exc}"
        ) from exc

    now = datetime.now(timezone.utc)
    doc = Document(
        id=document_id,
        company_id=company_id,
        document_type=document_type,
        title=title,
        description=description,
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        status="rendered",
        template_key=effective_template_key,
        template_version=loaded.version,
        rendered_at=now,
        rendered_by_user_id=rendered_by_user_id,
        rendering_duration_ms=elapsed_ms,
        rendering_context_hash=context_hash,
        entity_type=entity_type,
        entity_id=entity_id,
        sales_order_id=sales_order_id,
        fh_case_id=fh_case_id,
        disinterment_case_id=disinterment_case_id,
        invoice_id=invoice_id,
        customer_statement_id=customer_statement_id,
        price_list_version_id=price_list_version_id,
        safety_program_generation_id=safety_program_generation_id,
        caller_module=caller_module,
        caller_workflow_run_id=caller_workflow_run_id,
        caller_workflow_step_id=caller_workflow_step_id,
        intelligence_execution_id=intelligence_execution_id,
        is_test_render=is_test_render,
    )
    db.add(doc)
    db.flush()

    version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        version_number=1,
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        rendered_at=now,
        rendered_by_user_id=rendered_by_user_id,
        rendering_context_hash=context_hash,
        render_reason=render_reason,
        is_current=True,
    )
    db.add(version)

    logger.info(
        "Document rendered — id=%s type=%s template=%s version=1 "
        "bytes=%d duration=%dms",
        doc.id,
        document_type,
        template_key,
        len(pdf_bytes),
        elapsed_ms,
    )

    # Return shape: D-1 callers get a Document directly; callers that opt
    # into the new API get a RenderResult.
    if return_document is False:
        return RenderResult(
            output_format="pdf",
            document=doc,
            rendered_content=pdf_bytes,
            template_version_id=loaded.version_id,
            rendered_at=now,
            rendered_subject=None,
        )
    return doc


def rerender(
    db: Session,
    *,
    document_id: str,
    context: dict[str, Any],
    render_reason: str = "manual_regenerate",
    rendered_by_user_id: str | None = None,
) -> Document:
    """Re-render an existing document (PDF only — D-2 scope).

    Creates a new DocumentVersion, flips the previous version's
    is_current=False, and updates Document.storage_key to point at the
    new version.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise ValueError(f"Document {document_id!r} not found")
    if doc.template_key is None:
        raise DocumentRenderError(
            f"Document {document_id!r} has no template_key — can't rerender"
        )

    start = time.perf_counter()

    loaded = template_loader.load(
        doc.template_key, company_id=doc.company_id, db=db
    )
    html = _render_jinja(loaded.body_template, context)
    pdf_bytes = _html_to_pdf(html, base_url=loaded.template_dir)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    context_hash = _hash_context(context)

    current = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .first()
    )
    next_number = ((current.version_number if current else 0)) + 1
    storage_key = _storage_key(doc.company_id, doc.id, next_number)

    try:
        legacy_r2_client.upload_bytes(
            pdf_bytes, storage_key, content_type="application/pdf"
        )
    except Exception as exc:  # noqa: BLE001
        raise DocumentRenderError(
            f"R2 upload failed for document {document_id} v{next_number}: {exc}"
        ) from exc

    now = datetime.now(timezone.utc)
    if current is not None:
        current.is_current = False

    new_version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        version_number=next_number,
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        rendered_at=now,
        rendered_by_user_id=rendered_by_user_id,
        rendering_context_hash=context_hash,
        render_reason=render_reason,
        is_current=True,
    )
    db.add(new_version)

    doc.storage_key = storage_key
    doc.file_size_bytes = len(pdf_bytes)
    doc.status = "rendered"
    doc.template_version = loaded.version
    doc.rendered_at = now
    doc.rendered_by_user_id = rendered_by_user_id
    doc.rendering_duration_ms = elapsed_ms
    doc.rendering_context_hash = context_hash
    doc.updated_at = now

    db.flush()

    logger.info(
        "Document re-rendered — id=%s v%d reason=%s bytes=%d duration=%dms",
        doc.id,
        next_number,
        render_reason,
        len(pdf_bytes),
        elapsed_ms,
    )
    return doc


def download_bytes(doc: Document) -> bytes:
    return legacy_r2_client.download_bytes(doc.storage_key)


def presigned_url(doc: Document, expires_in: int = 3600) -> str:
    return legacy_r2_client.generate_signed_url(doc.storage_key, expires_in)


# ── Helpers for email-flavored callers ────────────────────────────────


def render_html(
    db: Session | None,
    *,
    template_key: str,
    context: dict[str, Any],
    company_id: str | None = None,
) -> RenderResult:
    """Convenience wrapper for HTML email callers. Returns a RenderResult."""
    return _render_non_pdf(db, template_key, context, company_id, "html")


def render_text(
    db: Session | None,
    *,
    template_key: str,
    context: dict[str, Any],
    company_id: str | None = None,
) -> RenderResult:
    """Convenience wrapper for plain-text callers."""
    return _render_non_pdf(db, template_key, context, company_id, "text")


def _render_non_pdf(
    db: Session | None,
    template_key: str,
    context: dict[str, Any],
    company_id: str | None,
    output_format: str,
) -> RenderResult:
    """Shared HTML/text path. Doesn't require a full Session — opens a
    short-lived one if needed so legacy callers without a session can
    still use the registry."""
    loaded = template_loader.load(template_key, company_id=company_id, db=db)
    rendered_body = _render_jinja(loaded.body_template, context)
    rendered_subject: str | None = None
    if loaded.subject_template:
        try:
            rendered_subject = _render_jinja(
                loaded.subject_template, context
            )
        except DocumentRenderError:
            logger.warning(
                "Subject template render failed for %s — falling back to None",
                template_key,
            )
    return RenderResult(
        output_format=output_format,
        document=None,
        rendered_content=rendered_body,
        template_version_id=loaded.version_id,
        rendered_at=datetime.now(timezone.utc),
        rendered_subject=rendered_subject,
    )


def render_pdf_bytes(
    db: Session | None,
    *,
    template_key: str,
    context: dict[str, Any],
    company_id: str | None = None,
) -> bytes:
    """Render a template directly to PDF bytes without creating a Document
    row. Used by legacy byte-returning functions that need to maintain
    their signature during migration.

    New code should prefer `render()` with a PDF template so the output is
    persisted + observable. Use this only for shimming legacy callers.
    """
    loaded = template_loader.load(template_key, company_id=company_id, db=db)
    if loaded.output_format != "pdf":
        raise DocumentRenderError(
            f"Template {template_key!r} is {loaded.output_format}, not pdf"
        )
    html = _render_jinja(loaded.body_template, context)
    return _html_to_pdf(html, base_url=loaded.template_dir)
