"""Platform template seed definitions — Phase D-2.

This module is the single source of truth for the platform-global templates
seeded into `document_templates` + `document_template_versions` by the
r21_document_template_registry migration.

Each seed is a dict with the columns the migration inserts. File-based
templates (invoice, statement, price_list, disinterment) read their body
from `backend/app/templates/` at import time so the migration doesn't
duplicate the HTML. Inline templates (email.*, pdf.social_service_certificate,
pdf.legacy_vault_print, pdf.safety_program_base) embed their Jinja body
verbatim.

To add a new platform template:
  1. Add an entry to `PLATFORM_TEMPLATE_SEEDS`
  2. Run the D-3 "seed missing platform templates" management command
     (or rerun r21 migration if pre-production)

The migration is idempotent: seeds only insert if (NULL company_id,
template_key) doesn't already exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict


_TEMPLATES_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "templates"
)


class PlatformTemplateSeed(TypedDict, total=False):
    template_key: str
    document_type: str
    output_format: str  # "pdf" | "html" | "text"
    description: str
    supports_variants: bool
    body_template: str
    subject_template: str | None
    variable_schema: dict | None
    css_variables: dict | None


def _read_file_template(rel_dir: str, filename: str) -> str:
    """Load a Jinja template from `backend/app/templates/{rel_dir}/{filename}`."""
    return (_TEMPLATES_ROOT / rel_dir / filename).read_text(encoding="utf-8")


# ── PDF templates from existing files ────────────────────────────────────

def _file_based_pdf_seeds() -> list[PlatformTemplateSeed]:
    return [
        {
            "template_key": "invoice.modern",
            "document_type": "invoice",
            "output_format": "pdf",
            "description": "Modern invoice layout — clean grid, accent color header.",
            "supports_variants": True,
            "body_template": _read_file_template("invoices", "modern.html"),
        },
        {
            "template_key": "invoice.professional",
            "document_type": "invoice",
            "output_format": "pdf",
            "description": "Professional invoice layout — traditional business formatting.",
            "supports_variants": True,
            "body_template": _read_file_template("invoices", "professional.html"),
        },
        {
            "template_key": "invoice.clean_minimal",
            "document_type": "invoice",
            "output_format": "pdf",
            "description": "Clean minimal invoice — maximum whitespace, understated.",
            "supports_variants": True,
            "body_template": _read_file_template("invoices", "clean_minimal.html"),
        },
        {
            "template_key": "statement.modern",
            "document_type": "statement",
            "output_format": "pdf",
            "description": "Modern monthly statement layout.",
            "supports_variants": True,
            "body_template": _read_file_template("statements", "modern.html"),
        },
        {
            "template_key": "statement.professional",
            "document_type": "statement",
            "output_format": "pdf",
            "description": "Professional monthly statement layout.",
            "supports_variants": True,
            "body_template": _read_file_template("statements", "professional.html"),
        },
        {
            "template_key": "statement.clean_minimal",
            "document_type": "statement",
            "output_format": "pdf",
            "description": "Clean minimal monthly statement layout.",
            "supports_variants": True,
            "body_template": _read_file_template("statements", "clean_minimal.html"),
        },
        {
            "template_key": "price_list.grouped",
            "document_type": "price_list",
            "output_format": "pdf",
            "description": "Price list PDF grouped by category.",
            "supports_variants": False,
            "body_template": _read_file_template("price_lists", "grouped.html"),
        },
        {
            "template_key": "disinterment.release_form",
            "document_type": "disinterment_release",
            "output_format": "pdf",
            "description": "Disinterment release form — next-of-kin signature.",
            "supports_variants": False,
            "body_template": _read_file_template("disinterment", "release_form.html"),
        },
    ]


# ── PDF templates migrated from inline Python strings ────────────────────

# Extracted from app/utils/pdf_generators/social_service_certificate_pdf.py.
# F-string expressions converted to Jinja. The `_esc` helper is replaced by
# Jinja's autoescape=True behavior (which the renderer sets on the env).
PDF_SOCIAL_SERVICE_CERTIFICATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {
    size: letter portrait;
    margin: 1in 1in 1in 1in;
  }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1a1a1a;
    line-height: 1.5;
    margin: 0;
    padding: 0;
  }
  .header {
    text-align: center;
    padding-bottom: 18px;
    border-bottom: 2px solid #1a1a1a;
    margin-bottom: 24px;
  }
  .header .company-name {
    font-size: 16pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }
  .header .company-address {
    font-size: 9pt;
    color: #555;
  }
  .title {
    text-align: center;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 16px 0;
    border-top: 1.5px solid #333;
    border-bottom: 1.5px solid #333;
    margin-bottom: 24px;
  }
  .section-title {
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 10px 0 6px;
    border-top: 1.5px solid #333;
    border-bottom: 1.5px solid #333;
    margin: 20px 0 14px;
  }
  .details-table {
    width: 100%;
    border-collapse: collapse;
  }
  .details-table tr td {
    padding: 6px 0;
    vertical-align: top;
  }
  .details-table tr td:first-child {
    font-weight: 600;
    color: #333;
    width: 180px;
  }
  .disclaimer {
    margin-top: 30px;
    padding: 16px;
    border: 1px solid #ccc;
    background: #fafafa;
    font-size: 9.5pt;
    line-height: 1.6;
    color: #444;
  }
  .footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 8pt;
    color: #888;
    padding: 12px 0;
    border-top: 1px solid #ddd;
  }
</style>
</head>
<body>

<div class="header">
  <div class="company-name">{{ company_name }}</div>
  <div class="company-address">
    {{ street }}<br>
    {{ city_state_zip }}<br>
    {{ phone }}{% if email %} &middot; {{ email }}{% endif %}
  </div>
</div>

<div class="title">Service Delivery Certificate</div>

<table class="details-table">
  <tr>
    <td>Certificate No:</td>
    <td>{{ certificate_number }}</td>
  </tr>
  <tr>
    <td>Date Issued:</td>
    <td>{{ date_issued }}</td>
  </tr>
</table>

<div class="section-title">Service Details</div>

<table class="details-table">
  <tr>
    <td>Product:</td>
    <td>{{ product_name }}</td>
  </tr>
  <tr>
    <td>Price:</td>
    <td>{{ price_fmt }}</td>
  </tr>
  <tr>
    <td>Deceased:</td>
    <td>{{ deceased_name }}</td>
  </tr>
  <tr>
    <td>Funeral Home:</td>
    <td>{{ funeral_home_name }}</td>
  </tr>
  <tr>
    <td>Cemetery:</td>
    <td>{{ cemetery_name }}</td>
  </tr>
  <tr>
    <td>Date of Service:</td>
    <td>{{ date_issued }}</td>
  </tr>
  <tr>
    <td>Time of Service:</td>
    <td>{{ time_of_service }}</td>
  </tr>
</table>

<div class="disclaimer">
  This certificate confirms delivery of the above burial vault product
  for the purposes of government benefit program verification.<br><br>
  This document is not an invoice. The funeral home will receive a
  separate invoice through standard billing channels.
</div>

<div class="footer">
  {{ company_name }} &middot; {{ street }}, {{ city_state_zip }} &middot; {{ phone }}{% if email %} &middot; {{ email }}{% endif %}
</div>

</body>
</html>
"""


# Extracted from app/services/fh/legacy_vault_print_service.py::LEGACY_PRINT_TEMPLATE.
# Python f-string braces doubled {{ }} → single { } → converted to Jinja {{ var }}.
PDF_LEGACY_VAULT_PRINT = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    @page { size: Letter; margin: 0.6in 0.8in; }
    body {
      font-family: Georgia, 'Times New Roman', serif;
      background: #faf9f7;
      color: #2d2a26;
      line-height: 1.5;
    }
    .wrap { max-width: 6.5in; margin: 0 auto; }
    .fh { text-align: center; font-size: 11pt; color: #8a7c6c; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 0.3in; }
    .name { font-size: 32pt; text-align: center; font-weight: normal; color: #1a1816; margin: 0; letter-spacing: 0.05em; }
    .lifedates { text-align: center; font-size: 13pt; color: #6b6158; margin-top: 0.1in; margin-bottom: 0.4in; font-style: italic; }
    .divider { border: 0; border-top: 1px solid #d4c8b8; margin: 0.3in 0; }
    .vault-section { text-align: center; padding: 0.3in 0; }
    .vault-label { font-size: 10pt; color: #8a7c6c; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.15in; }
    .vault-name { font-size: 20pt; color: #1a1816; margin: 0.1in 0; }
    .personalization { font-size: 12pt; color: #6b6158; margin-top: 0.1in; }
    .service { margin: 0.4in 0; text-align: center; font-size: 12pt; color: #2d2a26; }
    .service-label { font-size: 10pt; color: #8a7c6c; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.1in; }
    .footer { text-align: center; font-size: 9pt; color: #a39688; margin-top: 0.5in; font-style: italic; }
    .order-info { text-align: center; font-size: 9pt; color: #b5a898; margin-top: 0.15in; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="fh">{{ fh_name }}</div>
    <h1 class="name">{{ deceased_name }}</h1>
    <div class="lifedates">{{ life_span|safe }}</div>
    <hr class="divider"/>

    <div class="vault-section">
      <div class="vault-label">Commemorated With</div>
      <div class="vault-name">{{ vault_product_name }}</div>
      <div class="personalization">{{ personalization_line|safe }}</div>
    </div>

    <hr class="divider"/>

    <div class="service">
      <div class="service-label">Service</div>
      <div>{{ service_date_line }}</div>
      <div>{{ service_location }}</div>
    </div>

    <div class="footer">A Bridgeable Memorial</div>
    <div class="order-info">Case {{ case_number }} &middot; Order {{ order_ref }}</div>
  </div>
</body>
</html>
"""


# Extracted structural wrapper from safety_program_generation_service._wrap_program_html.
# The Claude-generated HTML body is embedded via {{ ai_generated_html|safe }}.
# Tenants can override this wrapper to adjust branding without touching the
# Claude-generated content.
PDF_SAFETY_PROGRAM_BASE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {
    size: letter portrait;
    margin: 0.75in 0.75in 1in 0.75in;
    @bottom-center {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #888;
    }
  }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #1a1a1a;
    line-height: 1.6;
    margin: 0;
    padding: 0;
  }
  .cover-header {
    text-align: center;
    padding: 20px 0 16px;
    border-bottom: 3px solid #1a365d;
    margin-bottom: 24px;
  }
  .cover-header .company-name {
    font-size: 14pt;
    font-weight: 700;
    color: #1a365d;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }
  .cover-header .program-title {
    font-size: 18pt;
    font-weight: 700;
    margin: 12px 0 8px;
  }
  .cover-header .osha-ref {
    font-size: 10pt;
    color: #555;
  }
  .cover-header .date-line {
    font-size: 10pt;
    color: #555;
    margin-top: 4px;
  }
  h2 {
    font-size: 13pt;
    font-weight: 700;
    color: #1a365d;
    border-bottom: 1.5px solid #1a365d;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }
  h3 {
    font-size: 11pt;
    font-weight: 700;
    color: #2d3748;
    margin-top: 16px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }
  p { margin: 0 0 8px; }
  ul, ol { margin: 0 0 12px; padding-left: 24px; }
  li { margin-bottom: 4px; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 10pt;
  }
  table th, table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  table th {
    background: #edf2f7;
    font-weight: 600;
  }
  .disclaimer {
    margin-top: 30px;
    padding: 12px;
    border: 1px solid #ccc;
    background: #f7fafc;
    font-size: 9pt;
    color: #555;
    line-height: 1.5;
  }
  .footer-line {
    margin-top: 24px;
    border-top: 1px solid #ddd;
    padding-top: 8px;
    font-size: 8.5pt;
    color: #888;
    text-align: center;
  }
</style>
</head>
<body>

<div class="cover-header">
  <div class="company-name">{{ company_name }}</div>
  <div class="program-title">{{ program_title }}</div>
  <div class="program-title" style="font-size: 12pt; font-weight: 400;">Written Safety Program</div>
  <div class="osha-ref">{% if osha_standard %}OSHA Standard: {{ osha_standard }}{% endif %}</div>
  <div class="date-line">{{ date_line }}</div>
</div>

{{ ai_generated_html|safe }}

<div class="disclaimer">
  This written safety program is generated as a starting point and should be reviewed
  and customized by the designated safety trainer or safety manager before implementation.
  It does not constitute legal advice. Consult with qualified safety professionals and
  legal counsel to ensure full compliance with all applicable OSHA regulations and
  state-specific requirements.
</div>

<div class="footer-line">
  {{ company_name }} &mdash; Written Safety Program &mdash; {{ date_line }}
</div>

</body>
</html>
"""


def _inline_pdf_seeds() -> list[PlatformTemplateSeed]:
    return [
        {
            "template_key": "pdf.social_service_certificate",
            "document_type": "social_service_certificate",
            "output_format": "pdf",
            "description": "Government-facing Social Service delivery confirmation.",
            "supports_variants": False,
            "body_template": PDF_SOCIAL_SERVICE_CERTIFICATE,
        },
        {
            "template_key": "pdf.legacy_vault_print",
            "document_type": "legacy_vault_print",
            "output_format": "pdf",
            "description": "Family-facing Legacy Vault Print keepsake.",
            "supports_variants": False,
            "body_template": PDF_LEGACY_VAULT_PRINT,
        },
        {
            "template_key": "pdf.safety_program_base",
            "document_type": "safety_program",
            "output_format": "pdf",
            "description": (
                "Structural wrapper for AI-generated monthly safety program. "
                "The body variable `ai_generated_html` is the Claude-generated "
                "content; the template provides branding + pagination + footer."
            ),
            "supports_variants": False,
            "body_template": PDF_SAFETY_PROGRAM_BASE,
        },
    ]


# ── Email templates (all output_format=html, with subject_template) ──────

EMAIL_BASE_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .body p:last-child { margin-bottom: 0; }
    .cta { display: inline-block; margin: 24px 0; padding: 12px 24px; background: #09090b; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
    .divider { height: 1px; background: #e4e4e7; margin: 24px 0; }
    .highlight-box { background: #f4f4f5; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }
    .highlight-box p { color: #3f3f46; margin: 0; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">{{ header_sub }}</p>
    </div>
    <div class="body">
      {{ body_content|safe }}
    </div>
    <div class="footer">
      <p>{{ footer_text }}</p>
    </div>
  </div>
</body>
</html>
"""


# email.statement — self-contained (includes wrapper)
EMAIL_STATEMENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
    .highlight-box { background: #f4f4f5; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }
    .highlight-box p { color: #3f3f46; margin: 0; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">Monthly Statement from {{ tenant_name }}</p>
    </div>
    <div class="body">
      <p>Dear {{ customer_name }},</p>
      <p>Your monthly account statement from <strong>{{ tenant_name }}</strong> for <strong>{{ statement_month }}</strong> is ready.</p>
      <div class="highlight-box">
        <p>Your statement is attached to this email as a PDF. Please review it at your earliest convenience.</p>
      </div>
      <p>If you have any questions about your account balance or charges, please contact {{ tenant_name }} directly.</p>
    </div>
    <div class="footer">
      <p>This statement was sent on behalf of {{ tenant_name }} via Bridgeable. Contact {{ tenant_name }} with any billing questions.</p>
    </div>
  </div>
</body>
</html>
"""

EMAIL_STATEMENT_SUBJECT = "Your {{ statement_month }} Statement — {{ tenant_name }}"


EMAIL_COLLECTIONS = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
    .divider { height: 1px; background: #e4e4e7; margin: 24px 0; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">Message from {{ tenant_name }}</p>
    </div>
    <div class="body">
      <p>Dear {{ customer_name }},</p>
      {% for paragraph in body_paragraphs %}<p>{{ paragraph }}</p>{% endfor %}
      <div class="divider"></div>
      <p style="font-size:13px;color:#71717a;">
        This message was sent on behalf of <strong>{{ tenant_name }}</strong>.
        Please reply directly to this email to reach their team.
      </p>
    </div>
    <div class="footer">
      <p>You are receiving this because you have an outstanding account with {{ tenant_name }}.</p>
    </div>
  </div>
</body>
</html>
"""


EMAIL_INVITATION = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .cta { display: inline-block; margin: 24px 0; padding: 12px 24px; background: #09090b; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">Platform Invitation</p>
    </div>
    <div class="body">
      <p>Hi {{ name }},</p>
      <p>You've been invited to join <strong>{{ tenant_name }}</strong> on Bridgeable — the platform built for the Wilbert licensee network.</p>
      <p>Click the button below to accept your invitation and set up your account:</p>
      <a href="{{ invite_url }}" class="cta">Accept Invitation</a>
      <p style="font-size:13px;color:#71717a;">This invitation link will expire in 7 days. If you did not expect this invitation, you can safely ignore this email.</p>
    </div>
    <div class="footer">
      <p>You are receiving this because someone at your organization invited you to Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""

EMAIL_INVITATION_SUBJECT = "You've been invited to {{ tenant_name }} on Bridgeable"


EMAIL_ACCOUNTANT_INVITATION = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .cta { display: inline-block; margin: 24px 0; padding: 12px 24px; background: #09090b; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; }
    .highlight-box { background: #f4f4f5; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }
    .highlight-box p { color: #3f3f46; margin: 0; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">Action Required: {{ tenant_name }} Data Migration</p>
    </div>
    <div class="body">
      <p>Hi,</p>
      <p>Your client <strong>{{ tenant_name }}</strong> is migrating their accounting data to Bridgeable and needs your help to get started.</p>
      <p>Please click the button below to access the secure data migration portal:</p>
      <a href="{{ migration_url }}" class="cta">Open Data Migration Portal</a>
      <div class="highlight-box">
        <p>This link is unique to your client and will expire in <strong>{{ expires_days }} days</strong>. You do not need to create an account — the link grants you direct access.</p>
      </div>
      <p>If you have any questions, please contact the Bridgeable support team at <a href="mailto:{{ support_email }}">{{ support_email }}</a>.</p>
    </div>
    <div class="footer">
      <p>This invitation was generated on behalf of {{ tenant_name }}. This link is confidential — do not share it.</p>
    </div>
  </div>
</body>
</html>
"""

EMAIL_ACCOUNTANT_INVITATION_SUBJECT = "Accounting Data Migration — {{ tenant_name }}"


EMAIL_ALERT_DIGEST = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ subject }}</title>
  <style>
    body { margin: 0; padding: 0; background: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #18181b; }
    .wrapper { max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .header { background: #09090b; padding: 24px 32px; }
    .header-title { color: #ffffff; font-size: 18px; font-weight: 600; margin: 0; letter-spacing: -0.3px; }
    .header-sub { color: #a1a1aa; font-size: 13px; margin: 4px 0 0; }
    .body { padding: 32px; }
    .body p { margin: 0 0 16px; line-height: 1.6; font-size: 15px; color: #3f3f46; }
    .highlight-box { background: #f4f4f5; border-radius: 6px; padding: 16px 20px; margin: 16px 0; }
    .highlight-box p { color: #3f3f46; margin: 0; }
    .footer { border-top: 1px solid #e4e4e7; padding: 20px 32px; background: #fafafa; }
    .footer p { margin: 0; font-size: 12px; color: #71717a; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">Bridgeable</p>
      <p class="header-sub">Daily Action Digest for {{ tenant_name }}</p>
    </div>
    <div class="body">
      <p>Here is your daily action summary for <strong>{{ tenant_name }}</strong>. The following items require your attention:</p>
      {% for alert in alerts %}
      <div class="highlight-box" style="margin-bottom:12px;">
        <p style="font-weight:600;margin-bottom:4px;">{{ alert.title }}</p>
        <p style="font-size:14px;">{{ alert.summary }}</p>
      </div>
      {% endfor %}
      <p>Log in to Bridgeable to review and act on these items.</p>
    </div>
    <div class="footer">
      <p>You are receiving this digest because you have active alerts in Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""

EMAIL_ALERT_DIGEST_SUBJECT = "{{ count }} item{{ plural }} require your attention — {{ tenant_name }}"


# Legacy proof — extracted from legacy_email_service.build_proof_email_html.
EMAIL_LEGACY_PROOF = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F8FAFC;font-family:Arial,Helvetica,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC"><tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="background:{{ header_color }};padding:24px 32px;border-radius:12px 12px 0 0">{{ logo_html|safe }}<p style="margin:8px 0 0;font-size:14px;color:rgba(255,255,255,0.7)">Legacy Proof</p></td></tr>
<tr><td style="background:#fff;padding:32px;border:1px solid #E2E8F0;border-top:none;border-radius:0 0 12px 12px">
<p style="font-size:15px;color:#475569;line-height:1.6;margin:0 0 24px">Please find the legacy proof below for your review.</p>
{% if proof_url %}<img src="{{ proof_url }}" alt="Legacy Proof" style="width:100%;max-width:600px;border-radius:8px;border:1px solid #E2E8F0">{% endif %}
<table style="width:100%;margin-top:24px;font-size:14px;color:#1a1a1a">
{% if inscription_name %}<tr><td style="color:#64748B;padding:4px 12px 4px 0">Name</td><td style="font-weight:600">{{ inscription_name }}</td></tr>{% endif %}
{% if inscription_dates %}<tr><td style="color:#64748B;padding:4px 12px 4px 0">Dates</td><td>{{ inscription_dates }}</td></tr>{% endif %}
{% if inscription_additional %}<tr><td style="color:#64748B;padding:4px 12px 4px 0">Additional</td><td>{{ inscription_additional }}</td></tr>{% endif %}
{% if print_name %}<tr><td style="color:#64748B;padding:4px 12px 4px 0">Print</td><td>{{ print_name }}</td></tr>{% endif %}
{% if service_date %}<tr><td style="color:#64748B;padding:4px 12px 4px 0">Service</td><td>{{ service_date }}</td></tr>{% endif %}
</table>
{% if custom_notes %}
<div style="background:#F1F5F9;border-radius:8px;padding:16px;margin-top:20px">
<p style="font-size:13px;color:#64748B;margin:0 0 4px">Note from {{ company_name }}:</p>
<p style="font-size:14px;color:#1a1a1a;margin:0">{{ custom_notes }}</p>
</div>
{% endif %}
<p style="font-size:14px;color:#475569;line-height:1.6;margin-top:24px">Please review the proof and reply to this email with any corrections or your approval.</p>
{% if watermark_enabled %}<p style="font-size:12px;color:#94A3B8;margin-top:16px"><em>The watermark will not appear on the final printed vault.</em></p>{% endif %}
</td></tr>
<tr><td style="padding:24px;text-align:center"><p style="font-size:12px;color:#94A3B8;margin:0">{{ company_name }}<br>Sent via Bridgeable</p></td></tr>
</table>
</td></tr></table>
</body></html>
"""


def _email_seeds() -> list[PlatformTemplateSeed]:
    return [
        {
            "template_key": "email.base_wrapper",
            "document_type": "email",
            "output_format": "html",
            "description": (
                "Reusable email wrapper (header + body slot + footer). Used by "
                "legacy email_service._wrap_html. Future D-3+ migrations can "
                "extend this via Jinja inheritance."
            ),
            "supports_variants": False,
            "body_template": EMAIL_BASE_WRAPPER,
        },
        {
            "template_key": "email.statement",
            "document_type": "email",
            "output_format": "html",
            "description": "Monthly statement notification email (with PDF attachment separately).",
            "supports_variants": False,
            "body_template": EMAIL_STATEMENT,
            "subject_template": EMAIL_STATEMENT_SUBJECT,
        },
        {
            "template_key": "email.collections",
            "document_type": "email",
            "output_format": "html",
            "description": "Collections sequence email on behalf of a tenant.",
            "supports_variants": False,
            "body_template": EMAIL_COLLECTIONS,
            "subject_template": "{{ subject }}",
        },
        {
            "template_key": "email.invitation",
            "document_type": "email",
            "output_format": "html",
            "description": "Platform user invitation email.",
            "supports_variants": False,
            "body_template": EMAIL_INVITATION,
            "subject_template": EMAIL_INVITATION_SUBJECT,
        },
        {
            "template_key": "email.accountant_invitation",
            "document_type": "email",
            "output_format": "html",
            "description": "Accountant data migration invitation email.",
            "supports_variants": False,
            "body_template": EMAIL_ACCOUNTANT_INVITATION,
            "subject_template": EMAIL_ACCOUNTANT_INVITATION_SUBJECT,
        },
        {
            "template_key": "email.alert_digest",
            "document_type": "email",
            "output_format": "html",
            "description": "Daily action-required alerts digest.",
            "supports_variants": False,
            "body_template": EMAIL_ALERT_DIGEST,
            "subject_template": EMAIL_ALERT_DIGEST_SUBJECT,
        },
        {
            "template_key": "email.legacy_proof",
            "document_type": "email",
            "output_format": "html",
            "description": "Legacy proof email sent to funeral homes for approval.",
            "supports_variants": False,
            "body_template": EMAIL_LEGACY_PROOF,
            "subject_template": "Legacy Proof — {{ inscription_name }}",
        },
    ]


# ── Phase D-4 signing templates ───────────────────────────────────────

PDF_SIGNATURE_CERTIFICATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: letter portrait; margin: 0.75in; }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #1a1a1a;
    line-height: 1.5;
  }
  .header {
    text-align: center;
    padding-bottom: 18px;
    border-bottom: 2px solid #1a365d;
    margin-bottom: 24px;
  }
  .header h1 {
    font-size: 18pt;
    font-weight: 700;
    color: #1a365d;
    margin: 0 0 4px;
    letter-spacing: 0.5px;
  }
  .header .subtitle { font-size: 10pt; color: #555; }
  h2 {
    font-size: 12pt;
    color: #1a365d;
    border-bottom: 1.5px solid #1a365d;
    padding-bottom: 4px;
    margin-top: 18px;
    margin-bottom: 10px;
  }
  .meta-row { display: flex; padding: 3px 0; font-size: 10pt; }
  .meta-label { font-weight: 600; width: 160px; color: #333; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 9.5pt;
  }
  table th, table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  table th { background: #edf2f7; font-weight: 600; }
  .party-block {
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 10px 12px;
    margin: 8px 0;
    background: #fafafa;
  }
  .party-block .party-name { font-weight: 700; font-size: 11pt; }
  .party-block .party-role { color: #555; font-size: 9pt; text-transform: uppercase; letter-spacing: 0.5px; }
  .party-block .party-meta { margin-top: 6px; font-size: 9pt; }
  .sig-img {
    margin-top: 8px;
    max-width: 220px;
    max-height: 80px;
    border: 1px solid #e2e2e2;
    padding: 4px;
    background: white;
  }
  .integrity {
    margin-top: 12px;
    padding: 10px;
    background: #f0f9ff;
    border: 1px solid #bfdbfe;
    font-size: 9pt;
  }
  .integrity .hash { font-family: 'Courier New', monospace; word-break: break-all; }
  .events { font-size: 8.5pt; }
  .footer {
    margin-top: 24px;
    padding-top: 10px;
    border-top: 1px solid #ddd;
    font-size: 8.5pt;
    color: #666;
    text-align: center;
  }
</style>
</head>
<body>

<div class="header">
  <h1>Certificate of Completion</h1>
  <div class="subtitle">Electronic Signature Record</div>
</div>

<h2>Envelope</h2>
<div class="meta-row"><div class="meta-label">Subject</div><div>{{ envelope_subject }}</div></div>
{% if envelope_description %}<div class="meta-row"><div class="meta-label">Description</div><div>{{ envelope_description }}</div></div>{% endif %}
<div class="meta-row"><div class="meta-label">Envelope ID</div><div style="font-family:monospace;">{{ envelope_id }}</div></div>
<div class="meta-row"><div class="meta-label">Created</div><div>{{ envelope_created_at }}</div></div>
<div class="meta-row"><div class="meta-label">Completed</div><div>{{ envelope_completed_at }}</div></div>
<div class="meta-row"><div class="meta-label">Routing</div><div>{{ envelope_routing_type }}</div></div>

<h2>Parties</h2>
{% for p in parties %}
<div class="party-block">
  <div class="party-name">{{ p.display_name }}</div>
  <div class="party-role">{{ p.role }} &middot; Order {{ p.signing_order }}</div>
  <div class="party-meta">
    <div><strong>Email:</strong> {{ p.email }}</div>
    <div><strong>Consent recorded:</strong> {{ p.consented_at }}</div>
    <div><strong>Signed:</strong> {{ p.signed_at }}</div>
    <div><strong>IP:</strong> {{ p.signing_ip_address }}</div>
    <div style="font-size:8pt;color:#666;"><strong>User-agent:</strong> {{ p.signing_user_agent }}</div>
    <div><strong>Signature type:</strong> {{ p.signature_type }}</div>
    {% if p.signature_image_src %}
      <img class="sig-img" src="{{ p.signature_image_src }}" alt="signature" />
    {% elif p.typed_signature_name %}
      <div style="font-family:'Caveat','Brush Script MT',cursive;font-size:22pt;margin-top:6px;">{{ p.typed_signature_name }}</div>
    {% endif %}
  </div>
</div>
{% endfor %}

<h2>Document Integrity</h2>
<div class="integrity">
  <div><strong>Original document hash (SHA-256):</strong></div>
  <div class="hash">{{ original_document_hash }}</div>
  {% if signed_document_hash %}
    <div style="margin-top:6px;"><strong>Signed document hash (SHA-256):</strong></div>
    <div class="hash">{{ signed_document_hash }}</div>
  {% endif %}
</div>

<h2>Event Timeline</h2>
<table class="events">
  <thead>
    <tr>
      <th style="width:60px;">#</th>
      <th style="width:160px;">When</th>
      <th style="width:160px;">Event</th>
      <th>Party</th>
      <th style="width:110px;">IP</th>
    </tr>
  </thead>
  <tbody>
    {% for e in events %}
    <tr>
      <td>{{ e.sequence_number }}</td>
      <td>{{ e.created_at }}</td>
      <td>{{ e.event_type }}</td>
      <td>{{ e.party_name }}</td>
      <td>{{ e.ip_address }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div class="footer">
  This Certificate of Completion provides an audit trail for the electronic
  signature of this document under the United States ESIGN Act of 2000
  (15 U.S.C. &sect; 7001 et seq.) and applicable state laws. Each party
  consented to use electronic signatures before signing. The signatures
  recorded here have the same legal effect as handwritten signatures.
</div>

</body>
</html>
"""


EMAIL_SIGNING_INVITE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{ subject }}</title>
<style>
  body { margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#18181b; }
  .wrapper { max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }
  .header { background:#1a365d; padding:24px 32px; }
  .header-title { color:#fff; font-size:18px; font-weight:600; margin:0; }
  .header-sub { color:#a5b4fc; font-size:13px; margin:4px 0 0; }
  .body { padding:32px; }
  .body p { margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }
  .cta { display:inline-block; margin:24px 0; padding:14px 28px; background:#1a365d; color:#fff !important; text-decoration:none; border-radius:6px; font-size:15px; font-weight:600; }
  .highlight-box { background:#f0f9ff; border-left:3px solid #1a365d; padding:14px 18px; margin:16px 0; font-size:14px; }
  .footer { border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }
  .footer p { margin:0; font-size:12px; color:#71717a; line-height:1.5; }
</style></head>
<body>
<div class="wrapper">
  <div class="header">
    <p class="header-title">{{ company_name }}</p>
    <p class="header-sub">Signature Request</p>
  </div>
  <div class="body">
    <p>Hi {{ signer_name }},</p>
    <p><strong>{{ sender_name }}</strong> has requested your signature on:</p>
    <div class="highlight-box">
      <strong>{{ envelope_subject }}</strong>
      {% if envelope_description %}<br><span style="color:#64748b;font-size:13px;">{{ envelope_description }}</span>{% endif %}
    </div>
    <p>You are signing as the <strong>{{ signer_role }}</strong>.</p>
    <a href="{{ signer_url }}" class="cta">Review and Sign</a>
    <p style="font-size:13px;color:#64748b;">This link expires on {{ expires_at }}. If you have questions, reply directly to this email.</p>
  </div>
  <div class="footer">
    <p>This signing request was sent on behalf of {{ company_name }} via Bridgeable.</p>
  </div>
</div>
</body></html>
"""

EMAIL_SIGNING_INVITE_SUBJECT = "Please sign: {{ envelope_subject }}"


EMAIL_SIGNING_COMPLETED = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{ subject }}</title>
<style>
  body { margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#18181b; }
  .wrapper { max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }
  .header { background:#15803d; padding:24px 32px; }
  .header-title { color:#fff; font-size:18px; font-weight:600; margin:0; }
  .header-sub { color:#bbf7d0; font-size:13px; margin:4px 0 0; }
  .body { padding:32px; }
  .body p { margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }
  .footer { border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }
  .footer p { margin:0; font-size:12px; color:#71717a; line-height:1.5; }
</style></head>
<body>
<div class="wrapper">
  <div class="header">
    <p class="header-title">{{ company_name }}</p>
    <p class="header-sub">Signing Complete</p>
  </div>
  <div class="body">
    <p>Hi {{ signer_name }},</p>
    <p>Good news — this document has been fully signed by all parties:</p>
    <p><strong>{{ envelope_subject }}</strong></p>
    <p>Attached to this email:</p>
    <ul>
      <li>The signed document</li>
      <li>The Certificate of Completion (your ESIGN audit trail)</li>
    </ul>
    <p>Keep these for your records.</p>
  </div>
  <div class="footer">
    <p>This notice was sent on behalf of {{ company_name }} via Bridgeable.</p>
  </div>
</div>
</body></html>
"""

EMAIL_SIGNING_COMPLETED_SUBJECT = "Completed: {{ envelope_subject }}"


EMAIL_SIGNING_DECLINED = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{ subject }}</title>
<style>
  body { margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#18181b; }
  .wrapper { max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }
  .header { background:#991b1b; padding:24px 32px; }
  .header-title { color:#fff; font-size:18px; font-weight:600; margin:0; }
  .header-sub { color:#fecaca; font-size:13px; margin:4px 0 0; }
  .body { padding:32px; }
  .body p { margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }
  .reason-box { background:#fef2f2; border-left:3px solid #991b1b; padding:14px 18px; margin:16px 0; font-size:14px; }
  .footer { border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }
  .footer p { margin:0; font-size:12px; color:#71717a; line-height:1.5; }
</style></head>
<body>
<div class="wrapper">
  <div class="header">
    <p class="header-title">{{ company_name }}</p>
    <p class="header-sub">Signing Declined</p>
  </div>
  <div class="body">
    <p>The following signing request was declined:</p>
    <p><strong>{{ envelope_subject }}</strong></p>
    <p>Declined by <strong>{{ decliner_name }}</strong> ({{ decliner_role }}).</p>
    <div class="reason-box">
      <strong>Reason:</strong> {{ decline_reason }}
    </div>
    <p>The envelope has been cancelled. No further signing will be requested.</p>
  </div>
  <div class="footer">
    <p>This notice was sent on behalf of {{ company_name }} via Bridgeable.</p>
  </div>
</div>
</body></html>
"""

EMAIL_SIGNING_DECLINED_SUBJECT = "Declined: {{ envelope_subject }}"


EMAIL_SIGNING_VOIDED = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{ subject }}</title>
<style>
  body { margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#18181b; }
  .wrapper { max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }
  .header { background:#57534e; padding:24px 32px; }
  .header-title { color:#fff; font-size:18px; font-weight:600; margin:0; }
  .header-sub { color:#d6d3d1; font-size:13px; margin:4px 0 0; }
  .body { padding:32px; }
  .body p { margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }
  .reason-box { background:#f5f5f4; border-left:3px solid #57534e; padding:14px 18px; margin:16px 0; font-size:14px; }
  .footer { border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }
  .footer p { margin:0; font-size:12px; color:#71717a; line-height:1.5; }
</style></head>
<body>
<div class="wrapper">
  <div class="header">
    <p class="header-title">{{ company_name }}</p>
    <p class="header-sub">Signing Request Cancelled</p>
  </div>
  <div class="body">
    <p>Hi {{ signer_name }},</p>
    <p>This signing request has been cancelled by the sender:</p>
    <p><strong>{{ envelope_subject }}</strong></p>
    {% if void_reason %}
    <div class="reason-box">
      <strong>Reason:</strong> {{ void_reason }}
    </div>
    {% endif %}
    <p>The signing link you were sent is no longer active. You don't need to take any action.</p>
  </div>
  <div class="footer">
    <p>This notice was sent on behalf of {{ company_name }} via Bridgeable.</p>
  </div>
</div>
</body></html>
"""

EMAIL_SIGNING_VOIDED_SUBJECT = "Cancelled: {{ envelope_subject }}"


def _signing_seeds() -> list[PlatformTemplateSeed]:
    return [
        {
            "template_key": "pdf.signature_certificate",
            "document_type": "signature_certificate",
            "output_format": "pdf",
            "description": (
                "Certificate of Completion for a signed envelope. Includes "
                "parties, signatures, timestamps, IPs, document hashes, and "
                "the full audit-event timeline. ESIGN-compliant."
            ),
            "supports_variants": False,
            "body_template": PDF_SIGNATURE_CERTIFICATE,
        },
        {
            "template_key": "email.signing_invite",
            "document_type": "email",
            "output_format": "html",
            "description": "Sent to a signer when an envelope is ready for them to sign.",
            "supports_variants": False,
            "body_template": EMAIL_SIGNING_INVITE,
            "subject_template": EMAIL_SIGNING_INVITE_SUBJECT,
        },
        {
            "template_key": "email.signing_completed",
            "document_type": "email",
            "output_format": "html",
            "description": "Sent to all parties when an envelope is fully signed.",
            "supports_variants": False,
            "body_template": EMAIL_SIGNING_COMPLETED,
            "subject_template": EMAIL_SIGNING_COMPLETED_SUBJECT,
        },
        {
            "template_key": "email.signing_declined",
            "document_type": "email",
            "output_format": "html",
            "description": "Sent to the envelope creator when a party declines.",
            "supports_variants": False,
            "body_template": EMAIL_SIGNING_DECLINED,
            "subject_template": EMAIL_SIGNING_DECLINED_SUBJECT,
        },
        {
            "template_key": "email.signing_voided",
            "document_type": "email",
            "output_format": "html",
            "description": "Sent to pending signers when an envelope is voided.",
            "supports_variants": False,
            "body_template": EMAIL_SIGNING_VOIDED,
            "subject_template": EMAIL_SIGNING_VOIDED_SUBJECT,
        },
    ]


def list_platform_template_seeds() -> list[PlatformTemplateSeed]:
    """All platform-global template seeds.

    D-2: 18 (8 file PDF + 3 inline PDF + 7 email).
    D-4: +5 (1 signing certificate PDF + 4 signing emails) = 23 total.
    D-9: +2 (quote.standard + urn.wilbert_engraving_form) = 25 total.
    """
    return [
        *_file_based_pdf_seeds(),
        *_inline_pdf_seeds(),
        *_email_seeds(),
        *_signing_seeds(),
        *_d9_seeds(),
    ]


# ── D-9 additions ────────────────────────────────────────────────────────
#
# Two PDF templates migrated from direct WeasyPrint call-sites in D-9:
#   quote.standard               — customer-facing quote PDF
#   urn.wilbert_engraving_form   — Wilbert engraving submission form
#
# Both had their inline HTML lifted verbatim, f-string slots replaced
# with Jinja `{{ variable }}` expressions, and helpers ({{ money() }})
# exposed as Jinja filters via `_inline_pdf_seeds`' existing patterns.

PDF_QUOTE_STANDARD = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;color:#1a1a1a;margin:0;padding:40px;}
.header{display:flex;justify-content:space-between;margin-bottom:40px;border-bottom:2px solid #1a1a1a;padding-bottom:20px;}
.company-name{font-size:22px;font-weight:700;letter-spacing:-.5px;}
.quote-label{font-size:28px;font-weight:300;color:#666;text-align:right;}
.quote-number{font-size:13px;color:#666;text-align:right;margin-top:4px;}
.details{display:flex;gap:60px;margin-bottom:36px;}
.detail-block label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:#888;display:block;margin-bottom:4px;}
.detail-block p{margin:0;font-size:13px;font-weight:500;}
table{width:100%;border-collapse:collapse;margin-bottom:24px;}
th{background:#f5f5f5;padding:10px 12px;text-align:left;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#666;}
td{padding:12px;border-bottom:1px solid #f0f0f0;font-size:13px;}
td.right{text-align:right;}
.total-row td{font-weight:700;font-size:14px;border-bottom:none;border-top:2px solid #1a1a1a;}
.footer{margin-top:40px;padding-top:20px;border-top:1px solid #eee;font-size:11px;color:#888;}
.expiry-note{background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:10px 14px;margin-bottom:24px;font-size:12px;color:#92400e;}
.notes-block{margin-bottom:24px;}
.notes-block .notes-label{font-size:10px;font-weight:600;text-transform:uppercase;color:#888;letter-spacing:.6px;margin-bottom:6px;}
.notes-block .notes-body{font-size:13px;}
</style></head><body>
<div class="header">
  <div><div class="company-name">{{ company_name }}</div></div>
  <div>
    <div class="quote-label">QUOTE</div>
    <div class="quote-number">#{{ quote_number }}</div>
    <div class="quote-number">{{ quote_date }}</div>
  </div>
</div>
<div class="details">
  {% if customer_name %}
  <div class="detail-block"><label>Prepared for</label><p>{{ customer_name }}</p></div>
  {% endif %}
  <div class="detail-block"><label>Prepared by</label><p>{{ company_name }}</p></div>
  {% if expiry_date %}
  <div class="detail-block"><label>Valid until</label><p>{{ expiry_date }}</p></div>
  {% endif %}
</div>
{% if expiry_date %}
<div class="expiry-note">This quote is valid until {{ expiry_date }}. Prices subject to change after expiry.</div>
{% endif %}
<table>
  <thead><tr>
    <th>Description</th>
    <th style="text-align:right">Qty</th>
    <th style="text-align:right">Unit Price</th>
    <th style="text-align:right">Total</th>
  </tr></thead>
  <tbody>
    {% if lines %}
      {% for ln in lines %}
      <tr>
        <td>{{ ln.description }}</td>
        <td class="right">{{ "%g" | format(ln.quantity) }}</td>
        <td class="right">{{ ln.unit_price_formatted }}</td>
        <td class="right">{{ ln.line_total_formatted }}</td>
      </tr>
      {% endfor %}
    {% else %}
      <tr><td colspan="4" style="color:#999;text-align:center;">No line items.</td></tr>
    {% endif %}
    {% if total_formatted %}
    <tr class="total-row">
      <td colspan="3">Total</td>
      <td class="right">{{ total_formatted }}</td>
    </tr>
    {% endif %}
  </tbody>
</table>
{% if notes %}
<div class="notes-block">
  <div class="notes-label">Notes</div>
  <div class="notes-body">{{ notes }}</div>
</div>
{% endif %}
<div class="footer">
  <p>Thank you for your business. To accept this quote, please reply or contact us directly.</p>
  <p style="margin-top:8px;">{{ company_name }}</p>
</div>
</body></html>"""


PDF_WILBERT_ENGRAVING_FORM = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body { font-family: Arial, sans-serif; margin: 20px; }
.form-page { page-break-after: always; border: 2px solid #333; padding: 24px; margin-bottom: 20px; }
.form-page:last-child { page-break-after: auto; }
h1 { font-size: 18px; text-align: center; margin: 0 0 16px; border-bottom: 2px solid #333; padding-bottom: 8px; }
.field { display: flex; margin: 6px 0; font-size: 13px; }
.label { font-weight: bold; width: 160px; flex-shrink: 0; }
.value { flex: 1; border-bottom: 1px solid #ccc; min-height: 18px; padding-left: 4px; }
.engraving-section { margin: 12px 0; padding: 12px; background: #f8f8f8; border: 1px solid #ddd; }
.engraving-section h2 { font-size: 14px; margin: 0 0 8px; }
</style></head><body>
{% for piece in pieces %}
<div class="form-page">
  <h1>Wilbert Engraving Order Form</h1>
  {% for label, value in piece.non_engraving %}
  <div class="field">
    <span class="label">{{ label }}:</span>
    <span class="value">{{ value }}</span>
  </div>
  {% endfor %}
  {% if piece.engraving %}
  <div class="engraving-section">
    <h2>Engraving — {{ piece.piece_label }}</h2>
    {% for label, value in piece.engraving %}
    <div class="field">
      <span class="label">{{ label }}:</span>
      <span class="value">{{ value }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</div>
{% endfor %}
</body></html>"""


def _d9_seeds() -> list[PlatformTemplateSeed]:
    return [
        {
            "template_key": "quote.standard",
            "document_type": "quote",
            "output_format": "pdf",
            "description": (
                "Customer-facing quote PDF. Header with company + quote "
                "number, line items, optional expiry, footer."
            ),
            "supports_variants": False,
            "body_template": PDF_QUOTE_STANDARD,
        },
        {
            "template_key": "urn.wilbert_engraving_form",
            "document_type": "urn_engraving_form",
            "output_format": "pdf",
            "description": (
                "Wilbert engraving submission form — one page per piece "
                "(main + companions). Printed, signed, and emailed to "
                "Wilbert engraving."
            ),
            "supports_variants": False,
            "body_template": PDF_WILBERT_ENGRAVING_FORM,
        },
    ]


# ── Approval Gate — Agent review email (Phase 8b.5) ──────────────────
#
# Replaces the hardcoded HTML previously inlined at
# `ApprovalGateService._build_review_email_html()`. Semantic
# equivalence — visual structure preserved but variables flow
# through Jinja rather than f-string interpolation. Single template
# serves all 12 agent job types; `job_type_label` is the
# human-readable name resolved from `JOB_TYPE_LABELS` by the caller.


EMAIL_APPROVAL_GATE_REVIEW_SUBJECT = (
    "Agent Review: {{ job_type_label }}"
    "{% if period_label %} — {{ period_label }}{% endif %}"
)

EMAIL_APPROVAL_GATE_REVIEW = """<!DOCTYPE html>
<html>
<head><style>
    body { margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
    .wrapper { max-width:600px; margin:32px auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }
    .header { background:#09090b; padding:24px 32px; }
    .header-title { color:#fff; font-size:18px; font-weight:600; margin:0; }
    .header-sub { color:#a1a1aa; font-size:13px; margin:4px 0 0; }
    .body { padding:32px; }
    .body p { margin:0 0 16px; line-height:1.6; font-size:15px; color:#3f3f46; }
    .btn { display:inline-block; padding:14px 32px; border-radius:6px; font-size:15px; font-weight:600; text-decoration:none; margin-right:12px; }
    .btn-approve { background:#16a34a; color:#fff !important; }
    .btn-reject { background:#fff; color:#dc2626 !important; border:2px solid #dc2626; }
    .footer { border-top:1px solid #e4e4e7; padding:20px 32px; background:#fafafa; }
    .footer p { margin:0; font-size:12px; color:#71717a; }
    .alert-warn { background:#fef3c7;border-radius:6px;padding:16px;margin:16px 0; }
    .alert-warn-text { margin:0;font-weight:600;color:#92400e; }
    .alert-ok { background:#dcfce7;border-radius:6px;padding:16px;margin:16px 0; }
    .alert-ok-text { margin:0;font-weight:600;color:#166534; }
    .dry-run { background:#fef9c3;border:1px solid #fde68a;border-radius:6px;padding:12px;margin:16px 0; }
    .dry-run-text { margin:0;font-size:13px;color:#854d0e; }
    .review-link { font-size:13px;color:#71717a; }
    .review-link a { color:#2563eb; }
</style></head>
<body>
<div class="wrapper">
    <div class="header">
        <p class="header-title">Bridgeable</p>
        <p class="header-sub">Agent Review Required — {{ tenant_name }}</p>
    </div>
    <div class="body">
        <p><strong>{{ job_type_label }}</strong>{% if period_label %} for <strong>{{ period_label }}</strong>{% endif %} has completed and requires your review.</p>
        {% if dry_run %}
        <div class="dry-run">
            <p class="dry-run-text">
                <strong>Dry Run:</strong> No changes were committed. This is a read-only preview.
            </p>
        </div>
        {% endif %}
        {% if anomaly_count and anomaly_count > 0 %}
        <div class="alert-warn">
            <p class="alert-warn-text">
                {{ anomaly_count }} anomal{% if anomaly_count == 1 %}y{% else %}ies{% endif %} found
                {% if critical_count and critical_count > 0 %}({{ critical_count }} critical){% endif %}
            </p>
        </div>
        {% else %}
        <div class="alert-ok">
            <p class="alert-ok-text">No anomalies found</p>
        </div>
        {% endif %}
        <p style="margin:24px 0;">
            <a href="{{ approve_url }}" class="btn btn-approve">Approve &amp; Lock Period</a>
            <a href="{{ reject_url }}" class="btn btn-reject">Reject</a>
        </p>
        <p class="review-link">
            <a href="{{ review_url }}">View full report in Bridgeable</a>
        </p>
    </div>
    <div class="footer">
        <p>This approval link expires in 72 hours. If you did not expect this email, contact {{ tenant_name }}.</p>
    </div>
</div>
</body>
</html>"""


def _approval_gate_seeds() -> list[PlatformTemplateSeed]:
    """Workflow Arc Phase 8b.5 — managed template for the agent
    approval review email. Replaces the hardcoded HTML path at
    `ApprovalGateService._build_review_email_html`. Single template
    serves all 12 job types via `job_type_label` context variable."""
    return [
        {
            "template_key": "email.approval_gate_review",
            "document_type": "email",
            "output_format": "html",
            "description": (
                "Agent approval review email — sent when a background "
                "agent completes and awaits human review. Serves all "
                "12 agent job types via the `job_type_label` variable."
            ),
            "supports_variants": False,
            "body_template": EMAIL_APPROVAL_GATE_REVIEW,
            "subject_template": EMAIL_APPROVAL_GATE_REVIEW_SUBJECT,
        },
    ]
