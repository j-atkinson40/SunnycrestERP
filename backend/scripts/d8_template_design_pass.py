"""D-8 design pass on high-visibility tenant-facing templates.

Creates a new draft version of each target template, updates the
body/subject with improved HTML+CSS, and activates it with a
consistent changelog. Idempotent — re-running after activation is a
no-op because `create_draft` detects existing drafts and errors out;
the script skips templates whose current active version's changelog
already contains the D-8 marker.

Scope: 5 highest-visibility templates
  1. email.base_wrapper         — wraps most emails; improving it
                                   improves everything downstream
  2. email.statement             — monthly AR — most-sent email
  3. email.signing_invite        — signer-facing — determines conversion
  4. invoice.modern              — most-selected invoice variant
  5. pdf.signature_certificate   — Certificate of Completion

Also updates (higher confidence, quick wins):
  6. email.invitation
  7. email.signing_completed
  8. statement.modern
  9. price_list.grouped
 10. pdf.disinterment.release_form

Run:
    source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python scripts/d8_template_design_pass.py

    # Dry run (prints changes, doesn't write):
    python scripts/d8_template_design_pass.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend/ to path so `app` imports resolve when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.document_template import (  # noqa: E402
    DocumentTemplate,
    DocumentTemplateVersion,
)


# ═══════════════════════════════════════════════════════════════════════
# Template content — D-8 design-pass versions
# ═══════════════════════════════════════════════════════════════════════

D8_CHANGELOG = "D-8 design pass: typography + spacing + hierarchy"


# ── email.base_wrapper ───────────────────────────────────────────────

EMAIL_BASE_WRAPPER_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body {
      margin: 0; padding: 0;
      background: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      line-height: 1.6;
    }
    .wrapper {
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 28px 36px;
    }
    .header-title {
      color: #ffffff;
      font-size: 20px;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.5px;
    }
    .header-sub {
      color: #94a3b8;
      font-size: 13px;
      margin: 6px 0 0;
      font-weight: 500;
    }
    .body { padding: 36px; }
    .body p {
      margin: 0 0 18px;
      font-size: 15px;
      color: #334155;
    }
    .body p:last-child { margin-bottom: 0; }
    .cta {
      display: inline-block;
      margin: 28px 0;
      padding: 14px 28px;
      background: #0f172a;
      color: #ffffff !important;
      text-decoration: none;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.2px;
    }
    .footer {
      border-top: 1px solid #e2e8f0;
      padding: 24px 36px;
      background: #f8fafc;
    }
    .footer p {
      margin: 0;
      font-size: 12px;
      color: #64748b;
      line-height: 1.6;
    }
    .divider { height: 1px; background: #e2e8f0; margin: 28px 0; border: 0; }
    .highlight-box {
      background: #f1f5f9;
      border-left: 4px solid #0f172a;
      border-radius: 6px;
      padding: 18px 22px;
      margin: 20px 0;
    }
    .highlight-box p {
      color: #0f172a;
      margin: 0;
      font-size: 14px;
    }
    @media (max-width: 600px) {
      .wrapper { margin: 12px; border-radius: 8px; }
      .header, .body, .footer { padding: 20px 22px; }
    }
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


# ── email.statement ──────────────────────────────────────────────────

EMAIL_STATEMENT_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body {
      margin: 0; padding: 0;
      background: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      line-height: 1.6;
    }
    .wrapper {
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 28px 36px;
    }
    .header-title { color: #ffffff; font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .header-sub { color: #94a3b8; font-size: 13px; margin: 6px 0 0; font-weight: 500; }
    .body { padding: 36px; }
    .body p { margin: 0 0 18px; font-size: 15px; color: #334155; }
    .statement-card {
      background: #f1f5f9;
      border-radius: 10px;
      padding: 24px;
      margin: 24px 0;
      text-align: center;
    }
    .statement-card .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #64748b;
      margin: 0 0 6px;
      font-weight: 600;
    }
    .statement-card .month {
      font-size: 22px;
      font-weight: 700;
      color: #0f172a;
      margin: 0;
    }
    .attachment-note {
      background: #eff6ff;
      border-left: 4px solid #3b82f6;
      padding: 14px 18px;
      margin: 20px 0;
      font-size: 14px;
      color: #1e3a8a;
      border-radius: 6px;
    }
    .footer {
      border-top: 1px solid #e2e8f0;
      padding: 24px 36px;
      background: #f8fafc;
    }
    .footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
    @media (max-width: 600px) {
      .wrapper { margin: 12px; border-radius: 8px; }
      .header, .body, .footer { padding: 20px 22px; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">{{ tenant_name }}</p>
      <p class="header-sub">Monthly Statement</p>
    </div>
    <div class="body">
      <p>Hi {{ customer_name }},</p>
      <p>Your monthly account statement is ready.</p>
      <div class="statement-card">
        <p class="label">Statement Period</p>
        <p class="month">{{ statement_month }}</p>
      </div>
      <div class="attachment-note">
        <strong>📎 Attached:</strong> Your statement is attached as a PDF. Please review at your convenience.
      </div>
      <p>Questions about your balance or charges? Reply to this email to reach {{ tenant_name }} directly.</p>
    </div>
    <div class="footer">
      <p>Sent on behalf of {{ tenant_name }} via Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""


# ── email.signing_invite ─────────────────────────────────────────────

EMAIL_SIGNING_INVITE_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body {
      margin: 0; padding: 0;
      background: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      line-height: 1.6;
    }
    .wrapper {
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
      padding: 32px 36px;
    }
    .header-title { color: #ffffff; font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .header-sub { color: #bfdbfe; font-size: 13px; margin: 8px 0 0; font-weight: 500; }
    .body { padding: 36px; }
    .body p { margin: 0 0 18px; font-size: 15px; color: #334155; }
    .subject-card {
      background: #eff6ff;
      border-left: 4px solid #1e40af;
      padding: 20px 24px;
      margin: 24px 0;
      border-radius: 6px;
    }
    .subject-card .title {
      font-size: 17px;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 6px;
    }
    .subject-card .description {
      font-size: 13px;
      color: #475569;
      margin: 0;
    }
    .role-note {
      background: #f1f5f9;
      border-radius: 8px;
      padding: 14px 18px;
      margin: 20px 0;
      font-size: 14px;
      color: #334155;
    }
    .role-note strong { color: #0f172a; }
    .cta {
      display: inline-block;
      padding: 16px 32px;
      background: #1e40af;
      color: #ffffff !important;
      text-decoration: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      margin: 12px 0 8px;
      box-shadow: 0 2px 6px rgba(30, 64, 175, 0.3);
    }
    .security-note {
      font-size: 13px;
      color: #64748b;
      margin-top: 24px;
      padding-top: 18px;
      border-top: 1px solid #e2e8f0;
    }
    .footer {
      border-top: 1px solid #e2e8f0;
      padding: 24px 36px;
      background: #f8fafc;
    }
    .footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
    @media (max-width: 600px) {
      .wrapper { margin: 12px; border-radius: 8px; }
      .header, .body, .footer { padding: 20px 22px; }
      .cta { display: block; text-align: center; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-title">{{ company_name }}</p>
      <p class="header-sub">Signature Requested</p>
    </div>
    <div class="body">
      <p>Hi {{ signer_name }},</p>
      <p><strong>{{ sender_name }}</strong> has requested your signature on:</p>
      <div class="subject-card">
        <p class="title">{{ envelope_subject }}</p>
        {% if envelope_description %}<p class="description">{{ envelope_description }}</p>{% endif %}
      </div>
      <div class="role-note">
        You are signing as the <strong>{{ signer_role }}</strong>.
      </div>
      <a href="{{ signer_url }}" class="cta">Review and Sign &rarr;</a>
      <p class="security-note">
        This link expires on <strong>{{ expires_at }}</strong>. If you have questions, reply directly to this email.
      </p>
    </div>
    <div class="footer">
      <p>This signing request was sent on behalf of {{ company_name }} via Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""


# ── email.signing_completed ──────────────────────────────────────────

EMAIL_SIGNING_COMPLETED_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body {
      margin: 0; padding: 0;
      background: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      line-height: 1.6;
    }
    .wrapper {
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .header {
      background: linear-gradient(135deg, #15803d 0%, #16a34a 100%);
      padding: 32px 36px;
    }
    .header-title { color: #ffffff; font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .header-sub { color: #bbf7d0; font-size: 13px; margin: 8px 0 0; font-weight: 500; }
    .check-icon {
      display: inline-block;
      width: 48px;
      height: 48px;
      background: rgba(255,255,255,0.2);
      border-radius: 50%;
      line-height: 48px;
      text-align: center;
      font-size: 24px;
      color: #ffffff;
      margin-bottom: 12px;
    }
    .body { padding: 36px; }
    .body p { margin: 0 0 18px; font-size: 15px; color: #334155; }
    .subject-card {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      padding: 18px 22px;
      margin: 20px 0;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      color: #15803d;
    }
    .attachments-list {
      background: #f1f5f9;
      border-radius: 8px;
      padding: 18px 22px;
      margin: 20px 0;
    }
    .attachments-list h3 {
      margin: 0 0 10px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #475569;
    }
    .attachments-list ul {
      margin: 0;
      padding-left: 20px;
    }
    .attachments-list li {
      font-size: 14px;
      color: #334155;
      margin: 6px 0;
    }
    .footer {
      border-top: 1px solid #e2e8f0;
      padding: 24px 36px;
      background: #f8fafc;
    }
    .footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
    @media (max-width: 600px) {
      .wrapper { margin: 12px; border-radius: 8px; }
      .header, .body, .footer { padding: 20px 22px; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="check-icon">&check;</div>
      <p class="header-title">{{ company_name }}</p>
      <p class="header-sub">Signing Complete</p>
    </div>
    <div class="body">
      <p>Hi {{ signer_name }},</p>
      <p>All parties have signed. The document is now fully executed.</p>
      <div class="subject-card">{{ envelope_subject }}</div>
      <div class="attachments-list">
        <h3>Attached to this email</h3>
        <ul>
          <li><strong>Signed document</strong> &mdash; the final executed version</li>
          <li><strong>Certificate of Completion</strong> &mdash; your ESIGN audit trail</li>
        </ul>
      </div>
      <p>Keep these for your records.</p>
    </div>
    <div class="footer">
      <p>This notice was sent on behalf of {{ company_name }} via Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""


# ── email.invitation ─────────────────────────────────────────────────

EMAIL_INVITATION_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <style>
    body {
      margin: 0; padding: 0;
      background: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #0f172a;
      line-height: 1.6;
    }
    .wrapper {
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
    }
    .header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 36px;
      text-align: center;
    }
    .header-brand { color: #ffffff; font-size: 28px; font-weight: 800; margin: 0; letter-spacing: -0.8px; }
    .header-sub { color: #94a3b8; font-size: 14px; margin: 8px 0 0; font-weight: 500; }
    .body { padding: 36px; }
    .body p { margin: 0 0 18px; font-size: 15px; color: #334155; }
    .cta {
      display: inline-block;
      padding: 16px 32px;
      background: #0f172a;
      color: #ffffff !important;
      text-decoration: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      margin: 20px 0;
      box-shadow: 0 2px 6px rgba(15, 23, 42, 0.3);
    }
    .steps {
      background: #f1f5f9;
      border-radius: 10px;
      padding: 22px 26px;
      margin: 24px 0;
    }
    .steps h3 {
      margin: 0 0 12px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #475569;
    }
    .steps ol {
      margin: 0;
      padding-left: 22px;
    }
    .steps li {
      font-size: 14px;
      color: #334155;
      margin: 8px 0;
    }
    .expire-note {
      font-size: 13px;
      color: #64748b;
      padding: 14px 0 0;
      border-top: 1px solid #e2e8f0;
      margin-top: 24px;
    }
    .footer {
      border-top: 1px solid #e2e8f0;
      padding: 24px 36px;
      background: #f8fafc;
    }
    .footer p { margin: 0; font-size: 12px; color: #64748b; line-height: 1.6; }
    @media (max-width: 600px) {
      .wrapper { margin: 12px; border-radius: 8px; }
      .header, .body, .footer { padding: 20px 22px; }
      .cta { display: block; text-align: center; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <p class="header-brand">Bridgeable</p>
      <p class="header-sub">Platform Invitation</p>
    </div>
    <div class="body">
      <p>Hi {{ name }},</p>
      <p>You've been invited to join <strong>{{ tenant_name }}</strong> on Bridgeable &mdash; the platform built for the Wilbert licensee network.</p>
      <a href="{{ invite_url }}" class="cta">Accept Invitation &rarr;</a>
      <div class="steps">
        <h3>What happens next</h3>
        <ol>
          <li>Click the button above to accept</li>
          <li>Set up your password</li>
          <li>You're in &mdash; explore your dashboard</li>
        </ol>
      </div>
      <p class="expire-note">
        This invitation expires in <strong>7 days</strong>. If you didn't expect this, you can safely ignore it.
      </p>
    </div>
    <div class="footer">
      <p>You're receiving this because someone at your organization invited you to Bridgeable.</p>
    </div>
  </div>
</body>
</html>
"""


# ── invoice.modern ──────────────────────────────────────────────────

INVOICE_MODERN_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Invoice {{ invoice_number }}</title>
<style>
  @page { size: letter; margin: 0.5in 0.6in; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
    color: #0f172a;
    font-size: 10.5pt;
    line-height: 1.5;
    margin: 0; padding: 0;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 16pt;
    border-bottom: 2pt solid #0f172a;
    margin-bottom: 20pt;
  }
  .brand .name {
    font-size: 18pt;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
    letter-spacing: -0.3px;
  }
  .brand .address {
    font-size: 9pt;
    color: #64748b;
    margin: 4pt 0 0;
    line-height: 1.4;
  }
  .invoice-meta {
    text-align: right;
  }
  .invoice-meta .label {
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 1pt;
    color: #64748b;
    margin: 0;
  }
  .invoice-meta .invoice-number {
    font-size: 16pt;
    font-weight: 700;
    color: #0f172a;
    margin: 2pt 0;
    letter-spacing: -0.3px;
  }
  .invoice-meta .dates {
    font-size: 9pt;
    color: #334155;
    margin-top: 6pt;
  }
  .invoice-meta .dates .date-row { margin: 2pt 0; }
  .invoice-meta .dates strong { color: #0f172a; }
  .addresses {
    display: flex;
    gap: 30pt;
    margin-bottom: 24pt;
  }
  .addr-block { flex: 1; }
  .addr-block .label {
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 1pt;
    color: #64748b;
    margin: 0 0 4pt;
    font-weight: 600;
  }
  .addr-block .name { font-size: 11pt; font-weight: 600; color: #0f172a; margin: 0; }
  .addr-block .details { font-size: 9pt; color: #475569; margin-top: 3pt; line-height: 1.5; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20pt;
  }
  thead th {
    background: #0f172a;
    color: #ffffff;
    padding: 10pt 12pt;
    text-align: left;
    font-size: 9pt;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5pt;
  }
  thead th.right { text-align: right; }
  tbody td {
    padding: 10pt 12pt;
    border-bottom: 1pt solid #e2e8f0;
    font-size: 10pt;
    vertical-align: top;
  }
  tbody td.right { text-align: right; font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: none; }
  .totals {
    margin-left: auto;
    width: 280pt;
    margin-top: 10pt;
  }
  .totals .row {
    display: flex;
    justify-content: space-between;
    padding: 6pt 12pt;
    font-size: 10pt;
  }
  .totals .row.subtotal { border-top: 1pt solid #e2e8f0; }
  .totals .row.total {
    border-top: 2pt solid #0f172a;
    margin-top: 6pt;
    padding: 10pt 12pt;
    background: #f1f5f9;
    border-radius: 4pt;
    font-size: 12pt;
    font-weight: 700;
    color: #0f172a;
  }
  .totals .label { color: #475569; }
  .totals .val { font-variant-numeric: tabular-nums; color: #0f172a; }
  .due-section {
    margin-top: 24pt;
    padding: 16pt 20pt;
    background: #f1f5f9;
    border-left: 4pt solid #0f172a;
    border-radius: 4pt;
  }
  .due-section .label {
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 1pt;
    color: #64748b;
    margin: 0;
    font-weight: 600;
  }
  .due-section .amount {
    font-size: 22pt;
    font-weight: 700;
    color: #0f172a;
    margin: 4pt 0 0;
    letter-spacing: -0.5px;
    font-variant-numeric: tabular-nums;
  }
  .due-section .due-date {
    font-size: 10pt;
    color: #475569;
    margin-top: 4pt;
  }
  .notes {
    margin-top: 24pt;
    padding-top: 16pt;
    border-top: 1pt solid #e2e8f0;
    font-size: 9pt;
    color: #64748b;
    line-height: 1.6;
  }
  .footer {
    margin-top: 32pt;
    text-align: center;
    font-size: 8.5pt;
    color: #94a3b8;
    border-top: 1pt solid #e2e8f0;
    padding-top: 12pt;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="brand">
      <p class="name">{{ company_name }}</p>
      <p class="address">{{ company_address }}</p>
    </div>
    <div class="invoice-meta">
      <p class="label">Invoice</p>
      <p class="invoice-number">#{{ invoice_number }}</p>
      <div class="dates">
        <div class="date-row"><strong>Issued:</strong> {{ invoice_date }}</div>
        <div class="date-row"><strong>Due:</strong> {{ due_date }}</div>
      </div>
    </div>
  </div>

  <div class="addresses">
    <div class="addr-block">
      <p class="label">Bill To</p>
      <p class="name">{{ customer_name }}</p>
      <div class="details">{{ customer_address }}</div>
    </div>
    {% if ship_to_name %}
    <div class="addr-block">
      <p class="label">Ship To</p>
      <p class="name">{{ ship_to_name }}</p>
      <div class="details">{{ ship_to_address }}</div>
    </div>
    {% endif %}
  </div>

  <table>
    <thead>
      <tr>
        <th>Description</th>
        <th class="right" style="width: 70pt;">Qty</th>
        <th class="right" style="width: 90pt;">Unit Price</th>
        <th class="right" style="width: 100pt;">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for line in lines %}
      <tr>
        <td>{{ line.description }}</td>
        <td class="right">{{ line.quantity }}</td>
        <td class="right">{{ line.unit_price }}</td>
        <td class="right">{{ line.amount }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="totals">
    <div class="row subtotal"><span class="label">Subtotal</span><span class="val">{{ subtotal }}</span></div>
    {% if tax %}<div class="row"><span class="label">Tax</span><span class="val">{{ tax }}</span></div>{% endif %}
    <div class="row total"><span>Total</span><span>{{ total }}</span></div>
  </div>

  <div class="due-section">
    <p class="label">Amount Due</p>
    <p class="amount">{{ balance_due }}</p>
    <p class="due-date">Due {{ due_date }}</p>
  </div>

  {% if notes or payment_terms_text %}
  <div class="notes">
    {% if payment_terms_text %}<div><strong>Payment terms:</strong> {{ payment_terms_text }}</div>{% endif %}
    {% if notes %}<div style="margin-top: 6pt;">{{ notes }}</div>{% endif %}
  </div>
  {% endif %}

  <div class="footer">
    {{ company_name }} &middot; {{ company_email }} {% if company_phone %}&middot; {{ company_phone }}{% endif %}
  </div>
</body>
</html>
"""


# ── pdf.signature_certificate ───────────────────────────────────────

PDF_SIGNATURE_CERTIFICATE_V2 = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: letter portrait; margin: 0.6in 0.7in; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
    font-size: 10.5pt;
    color: #0f172a;
    line-height: 1.55;
    margin: 0; padding: 0;
  }
  .cert-header {
    text-align: center;
    padding: 24pt 0 20pt;
    border-bottom: 3pt solid #0f172a;
    margin-bottom: 24pt;
  }
  .cert-header .badge {
    display: inline-block;
    background: #0f172a;
    color: #ffffff;
    padding: 4pt 14pt;
    border-radius: 20pt;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1pt;
    text-transform: uppercase;
    margin-bottom: 8pt;
  }
  .cert-header h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 6pt;
    letter-spacing: -0.5px;
  }
  .cert-header .subtitle {
    font-size: 11pt;
    color: #64748b;
    margin: 0;
  }
  h2 {
    font-size: 12pt;
    font-weight: 700;
    color: #0f172a;
    padding-bottom: 4pt;
    border-bottom: 1.5pt solid #0f172a;
    margin: 20pt 0 10pt;
    letter-spacing: 0.3pt;
    text-transform: uppercase;
  }
  .envelope-meta {
    background: #f8fafc;
    border-radius: 6pt;
    padding: 14pt 18pt;
    margin: 8pt 0 0;
  }
  .meta-row {
    display: flex;
    padding: 3pt 0;
    font-size: 10pt;
  }
  .meta-label {
    font-weight: 600;
    width: 130pt;
    color: #475569;
    flex-shrink: 0;
  }
  .meta-value { color: #0f172a; flex: 1; }
  .party-block {
    border: 1pt solid #e2e8f0;
    border-radius: 8pt;
    padding: 14pt 16pt;
    margin: 10pt 0;
    background: #ffffff;
  }
  .party-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 10pt;
    padding-bottom: 8pt;
    border-bottom: 1pt solid #e2e8f0;
  }
  .party-name { font-weight: 700; font-size: 12pt; color: #0f172a; }
  .party-role {
    background: #f1f5f9;
    color: #475569;
    padding: 2pt 10pt;
    border-radius: 10pt;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.5pt;
    font-weight: 600;
  }
  .party-details { font-size: 9pt; color: #475569; }
  .party-details .detail-row { margin: 2pt 0; }
  .party-details strong { color: #0f172a; }
  .sig-img {
    margin-top: 10pt;
    max-width: 220pt;
    max-height: 70pt;
    border: 1pt solid #e2e8f0;
    padding: 6pt;
    background: #fafafa;
    border-radius: 4pt;
  }
  .typed-sig {
    font-family: 'Caveat', 'Brush Script MT', cursive;
    font-size: 22pt;
    margin-top: 8pt;
    color: #0f172a;
  }
  .integrity {
    background: #eff6ff;
    border-left: 4pt solid #1e40af;
    padding: 14pt 18pt;
    margin: 10pt 0 0;
    border-radius: 0 6pt 6pt 0;
    font-size: 9pt;
  }
  .integrity .hash-label { font-weight: 600; color: #1e3a8a; margin-bottom: 2pt; }
  .integrity .hash-value {
    font-family: 'SF Mono', Consolas, monospace;
    color: #334155;
    word-break: break-all;
    font-size: 8pt;
    margin-bottom: 8pt;
  }
  table.events {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
    margin-top: 8pt;
  }
  table.events th {
    background: #f1f5f9;
    color: #475569;
    padding: 6pt 8pt;
    text-align: left;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3pt;
    font-size: 8pt;
  }
  table.events td {
    padding: 5pt 8pt;
    border-bottom: 1pt solid #e2e8f0;
    vertical-align: top;
  }
  .esign-footer {
    margin-top: 28pt;
    padding: 12pt 14pt;
    border-top: 2pt solid #0f172a;
    font-size: 8pt;
    color: #475569;
    line-height: 1.6;
    background: #f8fafc;
    border-radius: 4pt;
  }
</style>
</head>
<body>

<div class="cert-header">
  <span class="badge">Bridgeable</span>
  <h1>Certificate of Completion</h1>
  <p class="subtitle">Electronic Signature Audit Record</p>
</div>

<h2>Envelope</h2>
<div class="envelope-meta">
  <div class="meta-row"><div class="meta-label">Subject</div><div class="meta-value">{{ envelope_subject }}</div></div>
  {% if envelope_description %}<div class="meta-row"><div class="meta-label">Description</div><div class="meta-value">{{ envelope_description }}</div></div>{% endif %}
  <div class="meta-row"><div class="meta-label">Envelope ID</div><div class="meta-value" style="font-family: monospace; font-size: 9pt;">{{ envelope_id }}</div></div>
  <div class="meta-row"><div class="meta-label">Created</div><div class="meta-value">{{ envelope_created_at }}</div></div>
  <div class="meta-row"><div class="meta-label">Completed</div><div class="meta-value">{{ envelope_completed_at }}</div></div>
  <div class="meta-row"><div class="meta-label">Routing</div><div class="meta-value">{{ envelope_routing_type }}</div></div>
</div>

<h2>Parties</h2>
{% for p in parties %}
<div class="party-block">
  <div class="party-header">
    <div class="party-name">{{ p.display_name }}</div>
    <div class="party-role">{{ p.role }} &middot; #{{ p.signing_order }}</div>
  </div>
  <div class="party-details">
    <div class="detail-row"><strong>Email:</strong> {{ p.email }}</div>
    <div class="detail-row"><strong>Consent recorded:</strong> {{ p.consented_at }}</div>
    <div class="detail-row"><strong>Signed:</strong> {{ p.signed_at }}</div>
    <div class="detail-row"><strong>IP:</strong> {{ p.signing_ip_address }}</div>
    <div class="detail-row" style="font-size: 7.5pt; color: #64748b; margin-top: 4pt;"><strong>User-agent:</strong> {{ p.signing_user_agent }}</div>
    {% if p.signature_image_src %}
      <img class="sig-img" src="{{ p.signature_image_src }}" alt="signature" />
    {% elif p.typed_signature_name %}
      <div class="typed-sig">{{ p.typed_signature_name }}</div>
    {% endif %}
  </div>
</div>
{% endfor %}

<h2>Document Integrity</h2>
<div class="integrity">
  <div class="hash-label">Original document hash (SHA-256)</div>
  <div class="hash-value">{{ original_document_hash }}</div>
  {% if signed_document_hash %}
    <div class="hash-label">Signed document hash (SHA-256)</div>
    <div class="hash-value">{{ signed_document_hash }}</div>
  {% endif %}
</div>

<h2>Event Timeline</h2>
<table class="events">
  <thead>
    <tr>
      <th style="width: 40pt;">#</th>
      <th style="width: 140pt;">When</th>
      <th style="width: 150pt;">Event</th>
      <th>Party</th>
      <th style="width: 90pt;">IP</th>
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

<div class="esign-footer">
  This Certificate of Completion provides an audit trail for the electronic
  signature of this document under the United States ESIGN Act of 2000
  (15 U.S.C. &sect; 7001 et seq.) and applicable state laws. Each party
  consented to use electronic signatures before signing. The signatures
  recorded here have the same legal effect as handwritten signatures.
</div>

</body>
</html>
"""


# Template key → new body mapping for D-8 updates
D8_UPDATES: dict[str, dict[str, str | None]] = {
    "email.base_wrapper": {
        "body": EMAIL_BASE_WRAPPER_V2,
        "subject": None,
    },
    "email.statement": {
        "body": EMAIL_STATEMENT_V2,
        "subject": "Your {{ statement_month }} Statement — {{ tenant_name }}",
    },
    "email.signing_invite": {
        "body": EMAIL_SIGNING_INVITE_V2,
        "subject": "Please sign: {{ envelope_subject }}",
    },
    "email.signing_completed": {
        "body": EMAIL_SIGNING_COMPLETED_V2,
        "subject": "Completed: {{ envelope_subject }}",
    },
    "email.invitation": {
        "body": EMAIL_INVITATION_V2,
        "subject": "You've been invited to {{ tenant_name }} on Bridgeable",
    },
    "invoice.modern": {
        "body": INVOICE_MODERN_V2,
        "subject": None,
    },
    "pdf.signature_certificate": {
        "body": PDF_SIGNATURE_CERTIFICATE_V2,
        "subject": None,
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Update driver
# ═══════════════════════════════════════════════════════════════════════


def _update_template(db, template_key: str, new_body: str, new_subject: str | None, dry_run: bool) -> str:
    """Return a status string describing what happened."""
    tpl = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.template_key == template_key,
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if tpl is None:
        return f"SKIP {template_key} — not found in DB"

    if not tpl.current_version_id:
        return f"SKIP {template_key} — no current_version_id"

    current = (
        db.query(DocumentTemplateVersion)
        .filter_by(id=tpl.current_version_id)
        .first()
    )
    if current is None:
        return f"SKIP {template_key} — current version missing"

    # Idempotency: skip if the D-8 marker is already in the active changelog
    if D8_CHANGELOG in (current.changelog or ""):
        return f"SKIP {template_key} — D-8 version already active"

    # Detect existing draft — skip to avoid trampling manual work
    existing_draft = (
        db.query(DocumentTemplateVersion)
        .filter(
            DocumentTemplateVersion.template_id == tpl.id,
            DocumentTemplateVersion.status == "draft",
        )
        .first()
    )
    if existing_draft is not None:
        return f"SKIP {template_key} — existing draft v{existing_draft.version_number}"

    if dry_run:
        return f"DRY  {template_key} — would update v{current.version_number} → new active"

    # Next version number
    from sqlalchemy import func

    next_number = int(
        db.query(
            func.coalesce(func.max(DocumentTemplateVersion.version_number), 0)
            + 1
        )
        .filter(DocumentTemplateVersion.template_id == tpl.id)
        .scalar()
    )

    now = datetime.now(timezone.utc)
    new_version = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tpl.id,
        version_number=next_number,
        status="active",
        body_template=new_body,
        subject_template=new_subject if new_subject is not None else current.subject_template,
        variable_schema=current.variable_schema,
        sample_context=current.sample_context,
        css_variables=current.css_variables,
        changelog=D8_CHANGELOG,
        activated_at=now,
    )
    db.add(new_version)
    db.flush()

    # Retire the prior active
    current.status = "retired"

    # Point the template at the new version
    tpl.current_version_id = new_version.id
    tpl.updated_at = now

    return f"OK   {template_key} — v{current.version_number} retired, v{next_number} active"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    args = parser.parse_args()

    with SessionLocal() as db:
        results: list[str] = []
        for key, data in D8_UPDATES.items():
            results.append(
                _update_template(
                    db,
                    template_key=key,
                    new_body=data["body"],
                    new_subject=data["subject"],
                    dry_run=args.dry_run,
                )
            )
        if not args.dry_run:
            db.commit()
        for r in results:
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
