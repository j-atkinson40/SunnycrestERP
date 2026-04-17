"""Legacy Vault Print — family-facing PDF keepsake generated at Approve All.

Uses WeasyPrint to render a branded PDF. In production this uploads to R2;
Phase 1 stores the PDF in the static directory and returns a local URL.
Integrating R2 is a follow-up that mirrors the urn catalog image flow.
"""

import os
import uuid
from datetime import datetime, timezone
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


def _static_dir() -> Path:
    """Backend static dir for generated PDFs."""
    p = Path(__file__).resolve().parent.parent.parent.parent / "static" / "legacy-vault-prints"
    p.mkdir(parents=True, exist_ok=True)
    return p


LEGACY_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    @page {{ size: Letter; margin: 0.6in 0.8in; }}
    body {{
      font-family: Georgia, 'Times New Roman', serif;
      background: #faf9f7;
      color: #2d2a26;
      line-height: 1.5;
    }}
    .wrap {{ max-width: 6.5in; margin: 0 auto; }}
    .fh {{ text-align: center; font-size: 11pt; color: #8a7c6c; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 0.3in; }}
    .name {{ font-size: 32pt; text-align: center; font-weight: normal; color: #1a1816; margin: 0; letter-spacing: 0.05em; }}
    .lifedates {{ text-align: center; font-size: 13pt; color: #6b6158; margin-top: 0.1in; margin-bottom: 0.4in; font-style: italic; }}
    .divider {{ border: 0; border-top: 1px solid #d4c8b8; margin: 0.3in 0; }}
    .vault-section {{ text-align: center; padding: 0.3in 0; }}
    .vault-label {{ font-size: 10pt; color: #8a7c6c; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.15in; }}
    .vault-name {{ font-size: 20pt; color: #1a1816; margin: 0.1in 0; }}
    .personalization {{ font-size: 12pt; color: #6b6158; margin-top: 0.1in; }}
    .service {{ margin: 0.4in 0; text-align: center; font-size: 12pt; color: #2d2a26; }}
    .service-label {{ font-size: 10pt; color: #8a7c6c; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.1in; }}
    .footer {{ text-align: center; font-size: 9pt; color: #a39688; margin-top: 0.5in; font-style: italic; }}
    .order-info {{ text-align: center; font-size: 9pt; color: #b5a898; margin-top: 0.15in; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="fh">{fh_name}</div>
    <h1 class="name">{deceased_name}</h1>
    <div class="lifedates">{life_span}</div>
    <hr class="divider"/>

    <div class="vault-section">
      <div class="vault-label">Commemorated With</div>
      <div class="vault-name">{vault_product_name}</div>
      <div class="personalization">{personalization_line}</div>
    </div>

    <hr class="divider"/>

    <div class="service">
      <div class="service-label">Service</div>
      <div>{service_date_line}</div>
      <div>{service_location}</div>
    </div>

    <div class="footer">A Bridgeable Memorial</div>
    <div class="order-info">Case {case_number} &middot; Order {order_ref}</div>
  </div>
</body>
</html>
"""


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


def generate(db: Session, case_id: str) -> dict:
    """Generate the Legacy Vault Print PDF for a case.

    Returns {url, path, filename}.
    If WeasyPrint is not installed, falls back to HTML file so demo still flows.
    """
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    svc = db.query(FHCaseService).filter(FHCaseService.case_id == case_id).first()
    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case_id).first()
    fh = db.query(Company).filter(Company.id == case.company_id).first()

    deceased_name = " ".join([
        p for p in [dec.first_name if dec else None, dec.middle_name if dec else None, dec.last_name if dec else None] if p
    ]) or case.case_number

    html = LEGACY_PRINT_TEMPLATE.format(
        fh_name=(fh.name if fh else "").upper(),
        deceased_name=deceased_name.upper(),
        life_span=_format_life_span(dec.date_of_birth if dec else None, dec.date_of_death if dec else None),
        vault_product_name=(merch.vault_product_name if merch else "") or "Vault",
        personalization_line=_personalization_line(merch),
        service_date_line=(
            svc.service_date.strftime("%A, %B %-d, %Y") + (
                f" at {svc.service_time.strftime('%-I:%M %p')}" if svc.service_time else ""
            )
        ) if svc and svc.service_date else "Date pending",
        service_location=(svc.service_location_name if svc else "") or "",
        case_number=case.case_number,
        order_ref=(merch.vault_order_id[:8] if merch and merch.vault_order_id else "—"),
    )

    out_dir = _static_dir()
    stem = f"{case.case_number}_vault_print"

    # Try WeasyPrint first
    pdf_path = None
    try:
        from weasyprint import HTML
        pdf_path = out_dir / f"{stem}.pdf"
        HTML(string=html).write_pdf(str(pdf_path))
    except Exception:
        # Fallback: write HTML
        pdf_path = out_dir / f"{stem}.html"
        pdf_path.write_text(html, encoding="utf-8")

    # Note + return
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case_id,
        company_id=case.company_id,
        note_type="system",
        content=f"Legacy Vault Print generated: {pdf_path.name}",
    ))
    db.commit()

    return {
        "filename": pdf_path.name,
        "path": str(pdf_path),
        "url": f"/static/legacy-vault-prints/{pdf_path.name}",
    }
