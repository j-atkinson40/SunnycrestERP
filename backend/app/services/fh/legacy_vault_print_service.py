"""Legacy Vault Print — family-facing PDF keepsake generated at Approve All.

Phase D-2: routes through the managed template registry
(`pdf.legacy_vault_print`) and emits a canonical `Document` row. The
local-disk static/ write is kept as a secondary copy for any readers
still using the old `/static/legacy-vault-prints/...` URL until that
path is retired.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.funeral_case import (
    CaseDeceased,
    CaseMerchandise,
    CaseService as FHCaseService,
    FuneralCase,
    FuneralCaseNote,
)

logger = logging.getLogger(__name__)


def _static_dir() -> Path:
    """Backend static dir for generated PDFs — kept as secondary copy."""
    p = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "static"
        / "legacy-vault-prints"
    )
    p.mkdir(parents=True, exist_ok=True)
    return p


def _format_life_span(dob, dod) -> str:
    def fmt(d):
        if not d:
            return ""
        return d.strftime("%B %-d, %Y") if hasattr(d, "strftime") else str(d)

    left = fmt(dob)
    right = fmt(dod)
    if left and right:
        return f"{left} &mdash; {right}"
    return left or right or ""


def _personalization_line(merch: CaseMerchandise | None) -> str:
    if not merch or not merch.vault_personalization:
        return ""
    p = merch.vault_personalization
    parts = []
    if p.get("emblem_key") or p.get("emblem"):
        parts.append(f"Emblem: {p.get('emblem_key') or p.get('emblem')}")
    if p.get("name_display"):
        parts.append(f"Name: {p['name_display']}")
    if p.get("font"):
        parts.append(f"Font: {p['font']}")
    return " &middot; ".join(parts)


def _build_context(
    case: FuneralCase,
    dec: CaseDeceased | None,
    svc: FHCaseService | None,
    merch: CaseMerchandise | None,
    fh: Company | None,
) -> dict:
    deceased_name = (
        " ".join(
            [
                p
                for p in [
                    dec.first_name if dec else None,
                    dec.middle_name if dec else None,
                    dec.last_name if dec else None,
                ]
                if p
            ]
        )
        or case.case_number
    )

    service_date_line: str
    if svc and svc.service_date:
        service_date_line = svc.service_date.strftime("%A, %B %-d, %Y")
        if svc.service_time:
            service_date_line += f" at {svc.service_time.strftime('%-I:%M %p')}"
    else:
        service_date_line = "Date pending"

    return {
        "fh_name": (fh.name if fh else "").upper(),
        "deceased_name": deceased_name.upper(),
        "life_span": _format_life_span(
            dec.date_of_birth if dec else None,
            dec.date_of_death if dec else None,
        ),
        "vault_product_name": (merch.vault_product_name if merch else "")
        or "Vault",
        "personalization_line": _personalization_line(merch),
        "service_date_line": service_date_line,
        "service_location": (svc.service_location_name if svc else "") or "",
        "case_number": case.case_number,
        "order_ref": (
            merch.vault_order_id[:8]
            if merch and merch.vault_order_id
            else "\u2014"
        ),
    }


def generate(db: Session, case_id: str) -> dict:
    """Generate the Legacy Vault Print PDF for a case.

    Returns {url, path, filename, document_id}.
    Produces a canonical Document via the managed template registry AND
    writes a static-disk copy for legacy URL consumers.
    """
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    dec = (
        db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    )
    svc = (
        db.query(FHCaseService)
        .filter(FHCaseService.case_id == case_id)
        .first()
    )
    merch = (
        db.query(CaseMerchandise)
        .filter(CaseMerchandise.case_id == case_id)
        .first()
    )
    fh = db.query(Company).filter(Company.id == case.company_id).first()

    context = _build_context(case, dec, svc, merch, fh)

    # Canonical Document via registry
    from app.services.documents import document_renderer

    try:
        doc = document_renderer.render(
            db,
            template_key="pdf.legacy_vault_print",
            context=context,
            document_type="legacy_vault_print",
            title=(
                f"Legacy Vault Print \u2014 "
                f"{context['deceased_name'].title()} \u2014 "
                f"Case {case.case_number}"
            ),
            company_id=case.company_id,
            entity_type="fh_case",
            entity_id=case_id,
            fh_case_id=case_id,
            caller_module="legacy_vault_print_service.generate",
        )
        pdf_bytes = document_renderer.download_bytes(doc)
        document_id = doc.id
        storage_key = doc.storage_key
    except Exception as exc:
        logger.warning(
            "Legacy vault print canonical render failed for case %s: %s",
            case_id,
            exc,
        )
        # Fallback: render bytes only so the static/ copy still exists
        try:
            pdf_bytes = document_renderer.render_pdf_bytes(
                db,
                template_key="pdf.legacy_vault_print",
                context=context,
                company_id=case.company_id,
            )
        except Exception as fallback_exc:
            logger.error(
                "Legacy vault print fallback also failed for case %s: %s",
                case_id,
                fallback_exc,
            )
            pdf_bytes = None
        document_id = None
        storage_key = None

    # Secondary static-disk write for any readers still hitting the old URL
    out_dir = _static_dir()
    stem = f"{case.case_number}_vault_print"
    if pdf_bytes is not None:
        pdf_path = out_dir / f"{stem}.pdf"
        pdf_path.write_bytes(pdf_bytes)
    else:
        # Render HTML-only fallback for environments without WeasyPrint
        from app.services.documents import template_loader
        loaded = template_loader.load(
            "pdf.legacy_vault_print",
            company_id=case.company_id,
            db=db,
        )
        from jinja2 import Environment, select_autoescape

        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        html = env.from_string(loaded.body_template).render(**context)
        pdf_path = out_dir / f"{stem}.html"
        pdf_path.write_text(html, encoding="utf-8")

    # Audit note
    db.add(
        FuneralCaseNote(
            id=str(uuid.uuid4()),
            case_id=case_id,
            company_id=case.company_id,
            note_type="system",
            content=f"Legacy Vault Print generated: {pdf_path.name}",
        )
    )

    # Phase D-6: share the generated Document with the vault
    # manufacturer so they can see the Legacy Print the FH created
    # commemorating their product. Non-fatal on failure.
    if document_id and merch and merch.vault_manufacturer_company_id:
        try:
            _share_legacy_print_with_manufacturer(
                db,
                document_id=document_id,
                manufacturer_company_id=merch.vault_manufacturer_company_id,
                case_number=case.case_number,
            )
        except Exception:
            logger.warning(
                "Legacy vault print DocumentShare failed for case %s",
                case_id,
                exc_info=True,
            )

    db.commit()

    return {
        "filename": pdf_path.name,
        "path": str(pdf_path),
        "url": f"/static/legacy-vault-prints/{pdf_path.name}",
        "document_id": document_id,
        "storage_key": storage_key,
    }


def _share_legacy_print_with_manufacturer(
    db: Session,
    *,
    document_id: str,
    manufacturer_company_id: str,
    case_number: str,
) -> None:
    """D-6 — auto-share legacy vault print with the vault manufacturer."""
    from app.models.canonical_document import Document
    from app.services.documents import document_sharing_service

    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None or doc.company_id == manufacturer_company_id:
        return
    document_sharing_service.ensure_share(
        db,
        document=doc,
        target_company_id=manufacturer_company_id,
        reason=f"Legacy Vault Print — case {case_number}",
        source_module="legacy_vault_print_service",
        enforce_relationship=False,
    )
