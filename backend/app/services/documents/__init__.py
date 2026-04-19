"""Bridgeable Documents layer — canonical Document model + DocumentRenderer.

Phase D-1 shipped the backbone. Phase D-2 added the managed template
registry (platform + tenant hybrid scoping) and HTML/text output paths
for email templates.

Public surface:

    from app.services.documents import document_renderer
    # PDF — creates Document row, uploads to R2
    doc = document_renderer.render(
        db=db,
        template_key="invoice.professional",
        context={...},
        document_type="invoice",
        title="Invoice INV-2026-0042",
        company_id=company.id,
        invoice_id=invoice.id,
    )

    # HTML — returns RenderResult, no Document
    result = document_renderer.render_html(
        db=db,
        template_key="email.statement",
        context={...},
        company_id=company.id,
    )
    email_html = result.rendered_content
    email_subject = result.rendered_subject
"""

from app.services.documents.document_renderer import (
    DocumentRenderError,
    RenderResult,
    render,
    rerender,
    render_html,
    render_text,
)

__all__ = [
    "DocumentRenderError",
    "RenderResult",
    "render",
    "rerender",
    "render_html",
    "render_text",
]
