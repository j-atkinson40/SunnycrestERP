# Document Handling Audit — Bridgeable Platform

**Audit date:** 2026-04-19
**Scope:** Every document-handling surface in the codebase, read-only.
**Deliverable:** This document — ground truth for the Documents workstream
planning conversation.

---

## Executive summary

Document handling on Bridgeable today is **more mature than a greenfield
Documents layer would imply — but the maturity is distributed across ~18
tenant-scoped models and 7+ independent PDF generators with no unifying
abstraction.** Every service that produces a PDF instantiates its own
Jinja2 environment, owns its own template, builds its own context dict,
and decides for itself how/whether to persist the output. Two of the
seven generators don't even use template files — they build HTML as
Python f-strings inside the service. Email templates are entirely inline
f-strings with no Jinja rendering at all.

Storage and e-signature, by contrast, are in notably good shape:
Cloudflare R2 is the primary backend with lazy migration for legacy
local files; all files are tenant-scoped with presigned-URL serving;
DocuSign is **fully integrated** (HMAC-validated webhooks, 4-party
sequential routing, R2-persisted release forms) for disinterment cases.
The external-submission story is the opposite of storage — it's a blank
slate except for one live Uline vendor-order script. EDRS death
certificate filing, VA benefits, insurance assignment are all
placeholder workflows (`is_coming_soon=True`, empty steps). Cross-tenant
document flows are real and production (statements, delivery
confirmations, vault items, cross-tenant sales orders) but permissioning
is ad-hoc — `shared_with_company_ids` JSONB on VaultItem plus per-model
company_id filters; no unified cross-tenant document model exists.

---

## Step 1 — Document generation sites

### PDF libraries in use

| Library | Purpose | Version pinned | Files using it |
|---|---|---|---|
| **WeasyPrint** | Primary PDF rendering (HTML → PDF) | `>=60.0` | All 7 generation sites |
| **Jinja2** | HTML templating for PDFs | `>=3.1.0` | 5 of 7 (2 sites use inline f-strings) |
| **PyMuPDF (fitz)** | PDF **extraction** (catalog parsing) | `>=1.24.0` | 1 site — extraction only, NOT generation |
| **pdfplumber** | PDF content extraction | `>=0.10.0` | Not document generation — used for price list import |
| **resend** | Email sending with PDF attachments | `>=2.0.0` | Email delivery layer |

No reportlab, fpdf, or pdfkit. WeasyPrint is the entire PDF story.

### Generation sites (7 distinct systems)

#### 1. Invoice PDFs — `pdf_generation_service.py`

- **File:** `backend/app/services/pdf_generation_service.py` (lines 22-418)
- **What:** Customer invoices
- **Template:** File-based — `backend/app/templates/invoices/{modern,professional,clean_minimal}.html` (3 variants, tenant-selectable)
- **Input:** Invoice + Company + Customer + SalesOrder + InvoiceLine via `_build_context()` at line 59
- **Output:** PDF bytes returned to caller (in-process cached)
- **Route entry:** `backend/app/api/routes/sales.py:777, 855` — download + email
- **Tenant:** All verticals
- **Sync/async:** Sync

#### 2. Price List PDFs — `price_list_pdf_service.py`

- **File:** `backend/app/services/price_list_pdf_service.py` (lines 27-238)
- **What:** Tenant-branded price lists, grouped by category
- **Template:** `backend/app/templates/price_lists/grouped.html`
- **Input:** PriceListVersion + PriceListTemplate + PriceListItem
- **Output:** PDF bytes (returned to HTTP client or None if WeasyPrint unavailable)
- **Route entry:** `backend/app/api/routes/price_management.py:337, 491` — download + email
- **Tenant:** Manufacturing primary, all verticals
- **Sync/async:** Sync

#### 3. Disinterment Release Forms — `disinterment_pdf_service.py`

- **File:** `backend/app/services/disinterment_pdf_service.py` (lines 22-88)
- **What:** Multi-page legal release authorization form
- **Template:** `backend/app/templates/disinterment/release_form.html`
- **Input:** DisintermentCase + Company at lines 36-51
- **Output:** PDF bytes + base64 variant (for DocuSign)
- **Route entry:** Called by DocuSign integration flow
- **Tenant:** Funeral home vertical (disinterment module)
- **Sync/async:** Sync

#### 4. Social Service Certificates — `social_service_certificate_pdf.py`

- **File:** `backend/app/utils/pdf_generators/social_service_certificate_pdf.py` (lines 11-231)
- **What:** Government benefit program delivery confirmation
- **Template:** **Inline f-string** (lines 52-225, no separate template file)
- **Input:** Certificate metadata dict (certificate_number, deceased_name, funeral_home_name, etc.)
- **Output:** PDF bytes
- **Route entry:** Auto-triggered by `social_service_certificate_service.py::generate_pending()` on delivery completion
- **Tenant:** FH vertical
- **Sync/async:** Sync
- **Notable:** No Jinja template — HTML lives in a Python f-string. Custom `_esc()` HTML escape function

#### 5. Legacy Vault Prints — `legacy_vault_print_service.py`

- **File:** `backend/app/services/fh/legacy_vault_print_service.py` (lines 32-148)
- **What:** Family-facing commemorative keepsake (vault inscription)
- **Template:** **Inline f-string** `LEGACY_PRINT_TEMPLATE` at lines 32-86 (no separate file)
- **Input:** FuneralCase + CaseDeceased + FHCaseService + CaseMerchandise + Company
- **Output:** PDF file **saved to `backend/static/legacy-vault-prints/`** (local disk, not R2)
- **Route entry:** FuneralCase "Approve All" workflow
- **Tenant:** FH → Manufacturer (cross-tenant; see Step 7)
- **Sync/async:** Sync
- **Notable:** Only generator that writes to local disk instead of R2; only one with fallback to HTML-only when WeasyPrint unavailable

#### 6. Safety Program PDFs — `safety_program_generation_service.py`

- **File:** `backend/app/services/safety_program_generation_service.py` (lines 96-384)
- **What:** Monthly OSHA-compliant written safety programs
- **Template:** **Claude-generated HTML** (no pre-built template files; system prompt at lines 75-93 directs Claude to emit semantic HTML)
- **Input:** SafetyTrainingTopic + OSHA-scraped standard text + Company → Claude Sonnet
- **Output:** HTML stored on `SafetyProgramGeneration.generated_html`; PDF via WeasyPrint at lines 330-384; saved to R2, Document record created, linked via `pdf_document_id` FK
- **Route entry:** Background tasks in `safety_program_generation.py` routes; also scheduler-triggered monthly
- **Tenant:** All verticals with safety module enabled
- **Sync/async:** Async (scrape → generate → approve → PDF is a multi-step pipeline)

#### 7. Customer Statement PDFs — via `email_service.py`

- **File:** `backend/app/services/statement_service.py` (generation metadata) + `backend/app/services/email_service.py:94, 252, 268` (PDF materialization)
- **What:** Monthly AR statements
- **Template:** **Python f-string in email_service** — `_statement_html()` at lines 94-112
- **Input:** CustomerStatement + Customer + Invoice models via `calculate_balances()` and `get_period_invoices()`
- **Output:** PDF bytes as base64 email attachment; `StatementRunItem.pdf_path` on disk; `CustomerStatement.statement_pdf_url` for direct download
- **Route entry:** Statement-run endpoints + email delivery jobs
- **Tenant:** All verticals (monthly billing is the default pattern)
- **Sync/async:** Sync generation, async email delivery
- **Notable:** Only path where PDF materialization is **embedded in the email delivery layer** rather than a dedicated generator service — atypical

### PDF extraction (not generation)

For completeness — `wilbert_pdf_parser.py` uses PyMuPDF to parse the Wilbert catalog PDF (259 products, 78 pages) and extract product metadata + embedded images. This is ingestion, not generation, but worth knowing for scope awareness.

---

## Step 2 — Template storage and rendering patterns

### Template files found

Located at `backend/app/templates/`:

```
backend/app/templates/
├── invoices/
│   ├── modern.html           (hero-block w/ company logo)
│   ├── professional.html     (conservative)
│   └── clean_minimal.html    (minimal aesthetic)
├── statements/
│   ├── modern.html
│   ├── professional.html
│   └── clean_minimal.html
├── price_lists/
│   └── grouped.html          (category-grouped layout)
└── disinterment/
    └── release_form.html     (legal form)
```

**8 HTML template files total.** Three of the seven generators do NOT have
corresponding template files:
- Social Service Certificates — inline f-string
- Legacy Vault Prints — inline f-string
- Safety Programs — Claude-generated HTML at runtime (no source template)

### Data models flowing into templates

Each template consumes a Jinja2 context dict built by its service's
`_build_context()` helper. Shape varies per template:

| Template | Top-level keys | Tenant-specific | Branding |
|---|---|---|---|
| invoices/*.html | ~50 keys (invoice, company, customer, line_items, colors, toggles) | Yes | Logo URL, primary/secondary colors, fonts |
| price_lists/grouped.html | title, grouped_items, settings toggles, colors | Yes | Logo, color, footer text |
| disinterment/release_form.html | decedent info, cemetery, reason, next_of_kin list, quote | Yes | Company name, case number |

Statement templates follow the same pattern but are built lazily in
email_service.py rather than via Jinja.

### Template-rendering abstraction layer

**There is none.** Each service independently:

1. Instantiates its own Jinja2 Environment (`_get_jinja_env()` is defined
   separately in `pdf_generation_service.py:22`,
   `price_list_pdf_service.py:27`, `disinterment_pdf_service.py:22`)
2. Calls its own db queries to build context
3. Renders the template
4. Converts to PDF via `HTML(string=html_str).write_pdf()`

Email templates are entirely separate — no Jinja at all. Pure Python
string formatting in `email_service.py`:
- `_BASE_HTML` (wrapper, lines 19-58)
- `_statement_html()`, `_collections_html()`, `_invitation_html()`,
  `_accountant_invitation_html()`, `_alert_digest_html()`
- `legacy_email_service.py::build_proof_email_html()` (lines 99-149)

**Consolidation opportunity:** A shared `DocumentRenderer` or
`TemplateManager` that owns Jinja setup, WeasyPrint conversion, and
fallback handling would de-duplicate ~100 lines across 5 services and
establish one place to add new capabilities (e.g. tenant-wide branding
tokens, A/B template variants, i18n).

---

## Step 3 — File upload and storage

### Storage backends

**Primary: Cloudflare R2 (S3-compatible via boto3)**
- Configured via `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET_NAME`, `R2_PUBLIC_URL`
- Client: `backend/app/services/legacy_r2_client.py` (lines 15-106)
- Endpoint: `https://{account_id}.r2.cloudflarestorage.com`
- Default bucket: `bridgeable-legacy`

**Legacy: Local disk (deprecated)**
- Pre-R2 documents stored in `uploads/` directory tree
- **Lazy migration** to R2 on access — `document_service.py::_lazy_migrate_to_r2()`
  at lines 31-70. First `get_document()` call triggers upload, updates `r2_key`,
  logs failures but continues
- Admin bulk migration: `POST /documents/admin/migrate-local-docs`

### Key file-tracking models

| Model | File | Scope | Storage column | Used by |
|---|---|---|---|---|
| **Document** | models/document.py | company_id | `r2_key` + `file_path` (dual for migration) | Generic entity attachment — employees, products, companies |
| **VaultDocument** | models/vault_document.py | company_id | `file_key` (R2 only) | Modern vault layer; supports `is_family_accessible` for next-of-kin portal |
| **VaultItem** | models/vault_item.py | company_id | `r2_key` (when item_type='document') | Polymorphic — documents + events + communications + reminders + assets + compliance items in one table |
| **FHDocument** | models/fh_document.py | company_id | `file_url` | Funeral home case documents (death certs, permits, auth) |
| **SocialServiceCertificate** | models/social_service_certificate.py | company_id | `pdf_r2_key` | Auto-gen on delivery |
| **DeliveryMedia** | models/delivery_media.py | company_id | `file_url` | Driver mobile uploads (photo, signature, weight ticket) |
| **TenantTrainingDoc** | models/tenant_training_doc.py | tenant_id | `file_url` | Per-topic training material uploads |
| **ProgramLegacyPrint** | models/program_legacy_print.py | company_id | `file_url`, `thumbnail_url` | Personalization catalog (vault prints, urn designs) |
| **OrderPersonalizationPhoto** | models/order_personalization_photo.py | company_id | `file_url` | Photo for engraving/photo printing |
| **UrnProduct** | models/urn_product.py | tenant_id | `r2_image_key` | Urn catalog images (primary) + `image_url` (Wilbert fallback) |

### Upload endpoints

Every one is tenant-scoped via `company_id` and auth-gated:

- **`POST /documents/upload`** (routes/documents.py:21-37) — generic multipart upload; `entity_type` + `entity_id` query params; 10 MB max; path `tenants/{company_id}/{entity_type}s/{entity_id}/{uuid}.{ext}`; requires `employees.edit` permission
- **`POST /driver/media`** — driver mobile media (delivery photos, signatures)
- **`POST /documents/upload`** (routes/knowledge_base.py) — KB documents
- **`POST /company/logo-upload`** (routes/sales.py) — branding asset
- **`POST /price-list-import`** — CSV/Excel price sheet (staging only, not persisted)
- **`POST /cemetery-csv/upload`**, **`POST /funeral-home-csv/upload`** (routes/unified_import.py) — bulk import staging
- **`POST /{case_id}/documents`** (routes/cases.py, fh/cases.py, fh_portal.py) — case-attached docs
- **`POST /urn-sales/.../upload-proof`** — engraving proofs

### Serving patterns

- **Presigned URLs** — default. `legacy_r2_client.generate_signed_url()` at lines 89-98. TTL = **3600s (1 hour)**. boto3 `generate_presigned_url("get_object", ...)` with S3v4 signature.
- **307 redirects** — `GET /documents/{id}/download` returns a 307 redirect to the presigned URL (routes/documents.py:70). Browser handles the redirect natively.
- **Direct R2 public URLs** — for static assets like urn product images that are explicitly public (`legacy_r2_client.get_public_url()`).
- **Streaming fallback** — legacy local files use `FileResponse` (routes/documents.py:73-77) only when `r2_key` is NULL AND the local path still exists.

### Retention / cleanup

- **Soft delete:** VaultDocument uses `is_active=False` flag. No file removed from R2 — recoverable.
- **Hard delete:** `Document.delete()` removes the DB row and attempts R2 delete, falling back to local file cleanup if R2 unavailable.
- **No TTL-based cleanup.** No automated file expiration code found. Files persist indefinitely unless explicitly deleted.
- **No orphan collection.** If a parent entity is deleted, its Documents may or may not cascade depending on FK — not consistent across models.

---

## Step 4 — Signature capture

### Summary: DocuSign is LIVE for disinterment

**This is not a greenfield.** A production DocuSign integration with
HMAC-validated webhooks, 4-party sequential routing, and R2-persisted
release forms exists today.

### DocuSign service — `docusign_service.py`

- **Per-tenant config** — reads from `company.settings` JSON:
  - `docusign_integration_key`
  - `docusign_account_id`
  - `docusign_base_url`
  - `docusign_access_token`
- **Stub mode for dev/test** — `ENVIRONMENT != 'production'` returns fake envelope IDs
- **Graceful fallback** — if the `docusign-esign` Python package isn't installed, the service still works in stub mode

### Envelope creation — 4-party signature flow

`docusign_service.py::create_envelope()` (lines 53-220):

1. Funeral home director
2. Cemetery representative
3. Next of kin (family)
4. Manufacturer (vault/urn provider)

Sequential routing order. Anchor-based `SignHere` tabs positioned by
strings like `/sig_funeral_home/` embedded in the release PDF. The PDF
is auto-generated on-the-fly via
`disinterment_pdf_service.generate_release_form_base64()` at lines 85-88.

### Release form persistence to R2

- Path: `tenants/{company_id}/disinterment_cases/{case_id}/release_form/Release-Form-{case_number}.pdf`
- Metadata captures: case_id, case_number, decedent_name, funeral_home_id, cemetery_id, signers email list
- Metadata used by the call overlay for drill-through

### Webhook validation — `routes/docusign_webhook.py`

- **HMAC-SHA256** on `X-DocuSign-Signature-1` header (lines 33-53)
- HMAC key from `DOCUSIGN_HMAC_KEY` env or per-tenant settings
- Dev mode can skip validation if no key set
- Event extraction parses signers, role names, status (lines 56-82)
- Maps DocuSign status → `"Completed"` / `"Declined"` → updates `DisintermentCase.sig_*`

### Signature tracking — `DisintermentCase` model

Four signature parties, each with independent status + timestamp:

| Field | Type |
|---|---|
| `docusign_envelope_id` | string(100) |
| `sig_funeral_home` | string(20) — `not_sent` \| `sent` \| `viewed` \| `signed` \| `declined` |
| `sig_funeral_home_signed_at` | datetime |
| `sig_cemetery`, `sig_cemetery_signed_at` | same pattern |
| `sig_next_of_kin`, `sig_next_of_kin_signed_at` | same pattern |
| `sig_manufacturer`, `sig_manufacturer_signed_at` | same pattern |

### Other signature surfaces

- **FHCase.cremation_authorization** — manual sign-off fields only, NOT DocuSign:
  - `cremation_authorization_status` (string)
  - `cremation_authorization_signed_at` (datetime)
  - `cremation_authorization_signed_by` (string — free-text user name)
- **FuneralCase.authorization_signed_at** — timestamp only, no signer identity
- **DeliveryMedia.media_type = 'signature'** — driver captures delivery signature on mobile, stored as image in R2

### Assessment

Production-grade DocuSign infrastructure exists for one document type
(disinterment release forms). Extending it to other documents (cremation
authorization, insurance assignment, VA forms) is a pattern-replication
exercise, not a build-from-scratch. The tenant-scoped settings pattern
and HMAC webhook validation are reusable.

---

## Step 5 — External submission automation

### Summary: 1 live script (Uline) + 3 placeholder workflows

### Live automation — Playwright script registry

**File:** `backend/app/services/playwright_scripts/__init__.py`

```python
PLAYWRIGHT_SCRIPTS = {
    "uline_place_order": UlineOrderScript,
    # "staples_place_order": StaplesOrderScript,      # commented out
    # "grainger_place_order": GraingerOrderScript,    # commented out
    # "ss_certificate_submit": SSCertificateScript,   # commented out
    # "insurance_assignment": InsuranceAssignmentScript,  # commented out
}
```

### Uline order placement — the only live script

- **File:** `backend/app/services/playwright_scripts/uline_order.py`
- **External system:** uline.com (vendor order placement)
- **Data submitted:** Item SKU + quantity
- **How:** Playwright Chromium browser automation, 6 steps:
  1. Navigate → locate sign-in link → fill email/password from encrypted credentials → click submit → verify login
  2. Navigate to product detail page
  3. Set quantity → "Add to Cart"
  4. Navigate to cart → "Checkout"
  5. Click "Place Order" (uses Uline-side stored shipping + payment)
  6. Extract confirmation number, total, estimated delivery via regex on page content
- **Approval gate:** Configurable per-workflow via `requires_approval` (workflow_engine.py:554); not default
- **Error handling:** No built-in retry. On failure raises `PlaywrightScriptError` with optional debug screenshot to `/tmp/playwright_*`
- **Credentials:** Fetched via `credential_service.get_credentials()` (encrypted at rest). Script never touches DB directly.
- **Audit:** Every run creates `PlaywrightExecutionLog` row (workflow_run_id, company_id, script_name, status, input_data, output_data, error_message, screenshot_path, timings)

### Execution pathway — workflow engine integration

`backend/app/services/workflow_engine.py::_handle_playwright_action()` at lines 531-670:

1. Extract `script_name` from workflow step config
2. Approval gate check (`requires_approval=true` returns `awaiting_approval`)
3. Resolve variables via `resolve_variables()`
4. Fetch script from `PLAYWRIGHT_SCRIPTS` registry
5. Fetch decrypted credentials
6. Create `PlaywrightExecutionLog` row (status: running)
7. Execute in isolated asyncio event loop
8. Map outputs, update log (status: success/failed)

### Planned but NOT implemented — placeholder workflows

Three funeral-home external-submission workflows exist in
`backend/app/data/default_workflows.py` as `is_coming_soon: True` with
empty steps:

| Workflow ID | Purpose | Line |
|---|---|---|
| `wf_tpl_fh_insurance_assignment` | "Pre-fill and submit insurance assignment forms via Playwright" | 1392 |
| `wf_tpl_fh_edrs_submission` | "Pre-fill and submit death certificate via state EDRS portal using Playwright" | 1406 |
| `wf_tpl_fh_preneed_check` | Pre-need policy verification (not strictly submission) | 1146 |

Empty `steps: []` and `is_coming_soon: True` — visible in workflow
library, unrunnable.

### What's NOT automated

- **EDRS death certificate filing** — state-specific portals, manual
  today
- **VA.gov benefits forms** — manual
- **FTC Funeral Rule compliance disclosures** — compliance *scoring* is
  automated (see Step 6) but form submission is not
- **CMS / Social Security death notifications** — manual
- **Insurance company assignment forms** — manual

### Assessment

The execution layer (registry, approval gates, credential encryption,
audit logging) is production-ready. The script library is essentially
empty for the death care domain. EDRS and VA are explicit stretch goals
with placeholder workflows, not imminent builds.

---

## Step 6 — Compliance and reporting

### Report generators — 15 distinct types

**Central service:** `backend/app/services/financial_report_service.py`
(13 financial + audit health)

| Report | Location | Output | Generation | Trigger |
|---|---|---|---|---|
| Income Statement | financial_report_service.py:33-65 | Structured dict | GL-account aggregation | API or scheduled |
| AR Aging | financial_report_service.py:72-99 | Structured dict | Invoice-status bucketing by days outstanding | API |
| AP Aging | financial_report_service.py:106-120 | Structured dict | Bill-status bucketing | API |
| Sales by Customer | routes/reports.py:64 | Structured dict | Invoice aggregation by customer | API |
| Invoice Register | routes/reports.py:71 | Structured dict | Line-item listing | API |
| Tax Summary | routes/reports.py:79 | Structured dict | GL-type aggregation for tax prep | API |
| Balance Sheet | report_intelligence_service.py:39-50 | Structured dict | Assets/liabilities/equity calc | API |
| OSHA 300 Log | models/osha_300_entry.py | DB-stored entries | Manual entry + incident link | User/incident |
| Safety Program (Monthly) | safety_program_generation_service.py | HTML + PDF | Claude + OSHA scrape + WeasyPrint | Scheduled/manual |
| Audit Package | report.py:28-45 | Multi-report PDF | Bundled generation | Admin/manual |
| Audit Health Check | financial_report_service.py::run_health_check | Structured dict (green/amber/red) | Data-quality + completeness checks | Scheduled/on-demand |
| Report Snapshot | report_intelligence_service.py:74-100 | JSON key metrics | Extraction on report generation | Fire-and-forget |
| Report Commentary | report_intelligence_service.py | Natural-language insights | Claude API (managed prompt) | Scheduled/manual |
| FTC Compliance Score | ftc_compliance_service.py, routes/ftc_compliance.py:21-29 | Structured dict | GPL version check, price list audit | Dashboard/on-demand |
| FTC GPL History | ftc_compliance_service.py, routes/ftc_compliance.py:32-38 | List of GPL versions | Historical retrieval | Dashboard |

### Report API endpoints — `routes/reports.py`

All admin-gated, all tenant-scoped (`current_user.company_id`):

- `GET /income-statement?period_start=&period_end=&comparison_start=&comparison_end=`
- `GET /ar-aging?as_of=`
- `GET /ap-aging?as_of=`
- `GET /sales-by-customer?period_start=&period_end=`
- `GET /invoice-register?period_start=&period_end=`
- `GET /tax-summary?period_start=&period_end=`
- `GET /audit-health` — latest check or triggers new run

### Compliance-specific surfaces

**FTC Compliance** — `ftc_compliance_service.py`
- Hardcoded `FTC_REQUIRED_ITEMS` list (lines 16-80+) — Basic Services, Embalming, etc.
- `GET /compliance-score` — dashboard with scoring, gated by `fh_compliance.view` permission
- `GET /gpl-history` — General Price List version history, same permission gate

**Safety Program Generation** — Claude + OSHA + WeasyPrint pipeline
- OSHA regulation scraping via `osha_scraper_service.scrape_osha_standard()`
- Claude model: `claude-sonnet-4-20250514`, max 4096 tokens
- Pipeline: scrape → generate (HTML) → approve (human review) → PDF (R2) → Document record

### Report-storage models

- **ReportRun** (`models/report.py:13-25`) — one row per report execution.
  Tracks: type, parameters, status, row_count, generated_by, timestamps,
  `audit_package_id` (nullable — links to parent bundle).
- **AuditPackage** (`models/report.py:28-45`) — bundles multiple reports.
  `reports_included` JSON list + `pdf_path` on disk + `natural_language_input`
  (the user's request in plain English).
- **AuditHealthCheck** (`models/report.py:47-59`) — daily/on-demand checks.
  Green/Amber/Red counts + findings JSONB.
- **ReportSchedule** (`models/report.py:62-73`) — recurring report cadence.

### Overlap with Step 1

- **Safety Program PDFs** ARE a document-generation site (Step 1 entry #6)
- **Audit Packages** generate bundled PDFs via `financial_report_service.generate_audit_package_pdf()` (not itemized in Step 1 but same WeasyPrint pattern)
- **FTC GPL PDFs** — price list history is browseable but GPL PDF generation is per the price list generator (Step 1 entry #2)

Financial reports themselves **do not** generate PDFs inside the report
service — they return structured dicts. PDF rendering happens downstream
in the audit package bundler or UI (frontend renders via tables, not
PDFs). Ad-hoc PDF export of individual financial reports is not a
built-in capability.

---

## Step 7 — Cross-tenant data sharing

### Four distinct patterns

#### Pattern 1 — PlatformTenantRelationship (bilateral generic link)

- **Model:** `models/platform_tenant_relationship.py:12-40`
- **Crosses:** Billing relationship metadata (enabled flag, timestamps, status)
- **Direction:** Bidirectional — `tenant_id` ↔ `supplier_tenant_id` (both FK companies)
- **Data examples:** Customer statement delivery (manufacturer → FH), supplier pricing
- **Permissioning:** `billing_enabled` flag; `status` field
- **Document involvement:** Statement PDFs cross via `cross_tenant_statement_service.deliver_statement_cross_tenant()` (lines 17-90)

#### Pattern 2 — VaultItem sharing (one-to-many visibility)

- **Model:** `models/vault_item.py:72-74`
- **Field:** `shared_with_company_ids` (JSONB list)
- **Crosses:** Documents, events, training records, compliance certs, QC photos, COIs, batch records
- **Document types that commonly cross:** `delivery_confirmation`, `training_completion`, `inspection_cert`, `repair_record`, `asset_photo`, `coi` (Certificate of Insurance)
- **Direction:** One-to-many — a single item can be visible to multiple tenants
- **Permissioning:** Query filters check `shared_with_company_ids` JSONB contains current tenant
- **Visibility enum:** `private` | `internal` | `shared` | `public`

#### Pattern 3 — LicenseeTransfer (manufacturer A → manufacturer B)

- **Model:** `models/licensee_transfer.py:14-76`
- **Crosses:** Order + transfer items + billing chain + invoice data
- **Parties:** `home_tenant_id` (requesting mfg) ↔ `area_tenant_id` (regional mfg)
- **Flow:** FH requests burial at a cemetery in area_tenant's territory → area_tenant locates a vault → home creates a LicenseeTransfer → platform routes to area mfg's queue → billing chain: `area_invoice_id` → `home_passthrough_invoice_id` → `home_vendor_bill_id`
- **Document involvement:** Transfer notifications (email + PDF) flow between tenants; area tenant's delivery confirmation becomes visible to home tenant

#### Pattern 4 — Cross-tenant vault order (FH → Manufacturer auto-order)

- **Service:** `services/fh/cross_tenant_vault_service.py:23-120`
- **Trigger:** FH approves a vault in the Case Story step
- **Crosses:** Sales order inserted directly into manufacturer's `sales_orders` table via raw SQL (lines 79-106) — order_number prefix `XT-`, `source='cross_tenant'`
- **Direction:** Unidirectional — FH → manufacturer
- **Document involvement:** The Legacy Vault Print PDF generated on FH approval is the primary document artifact; it flows to the manufacturer for printing/engraving

### Models carrying cross-tenant FKs

| Model | FK | Direction |
|---|---|---|
| PlatformTenantRelationship | `tenant_id` + `supplier_tenant_id` (both FK companies) | Bilateral |
| VaultItem | `shared_with_company_ids` (JSONB list) | One-to-many |
| LicenseeTransfer | `home_tenant_id` + `area_tenant_id` | Bilateral |
| ReceivedStatement | `from_tenant_id` (FK companies) | Unidirectional |

### Documents that cross tenant boundaries today

| Document | Origin | Destination | Mechanism |
|---|---|---|---|
| Customer Statement PDF | Manufacturer | Funeral home | `deliver_statement_cross_tenant()` creates a `ReceivedStatement` on destination |
| Delivery Confirmation | Manufacturer | FH | VaultItem with `shared_with_company_ids` |
| Cross-tenant sales order | Funeral home | Manufacturer | Raw SQL insert into manufacturer's `sales_orders` |
| Training Certificate | Source tenant | Shared recipients | VaultItem sharing |
| Insurance Certificate (COI) | Issuer | Shared recipients | VaultItem sharing |
| Licensee Transfer Notification | Home mfg | Area mfg | `TransferNotification` with `recipient_tenant_id` |
| Legacy Vault Print | FH | Manufacturer | Implicit — referenced in FuneralCase.vault_print_url, visible to mfg via the cross-tenant sales order |

### Permissioning summary

- **VaultItem:** queries filter on `shared_with_company_ids` JSONB contains current tenant
- **PlatformTenantRelationship.billing_enabled:** gates statement delivery
- **LicenseeTransfer.status:** workflow (pending → accepted → fulfilled) controls when area mfg sees the transfer
- **ReceivedStatement:** scoped on destination FH's `tenant_id`; created at delivery time
- **Cross-tenant sales orders:** raw insert to mfg's table; subsequent visibility via normal `company_id` scoping

No unified RBAC override exists for cross-tenant access. Boundary enforcement is **per-model** via `company_id` filters and conditional JSONB checks.

---

## Step 8 — Intelligence / workflow integration points

### AI-generated document content

Five services produce document-like content via managed prompts:

| Service | Prompt key | Output | Downstream |
|---|---|---|---|
| `obituary_service.py::generate_with_ai` (lines 46-118) | `fh.obituary.generate` | HTML/text obituary body (~250 words) | `FHObituary.content` row → portal + case detail |
| `safety_program_generation_service.py::generate_program_content` (lines 96-175) | `safety.draft_monthly_program` | Full HTML safety program | `SafetyProgramGeneration.generated_html` → WeasyPrint PDF → Document |
| `fh/scribe_service.py::_call_claude_extract` (lines 35-56) | `scribe.extract_case_fields` | JSON field extraction | Auto-populates case fields; `FuneralCaseNote` row |
| `fh/scribe_service.py` (first call variant) | `scribe.extract_first_call` | JSON field extraction | Same as above |
| Training services | `training.generate_procedure`, `training.generate_curriculum_track` | HTML procedure / curriculum | Training course material |

### Workflow `ai_prompt` step integration

`workflow_engine.py::_execute_ai_prompt()` (lines 989-1065)

Config shape:
```json
{
  "prompt_key": "fh.obituary.generate",
  "variables": {
    "deceased_name": "{current_record.deceased_name}",
    "birth_date": "{current_record.birth_date}"
  }
}
```

Variable resolution supports: `{input.step.field}`, `{output.step.field}`,
`{current_user.id}`, `{current_company.name}`, `{current_record.field}`.

Output is stored in `WorkflowRunStep.output_data`. The executor
auto-populates Intelligence linkage from `run.trigger_context.entity_type`
(fh_case → `caller_fh_case_id`, etc.).

### Workflow action_type = "generate_document" — stub only

`workflow_engine.py::_execute_action()` lines 626-627:

```python
if action_type == "generate_document":
    return {"type": "document_generated", "pdf_url": None}
```

The hook exists but the implementation is empty. `pdf_url: None` — it
logs the intent and returns. **This is a clean integration point for
the Documents workstream.**

### Managed prompts that produce document-like output

From the 73 platform-global prompts seeded via `scripts/seed_intelligence_*.py`:

- **Document generators** (HTML/text output → PDF or stored as content):
  - `fh.obituary.generate` — obituary HTML
  - `safety.draft_monthly_program` — safety program HTML
  - `training.generate_procedure` — procedure document HTML
  - `training.generate_curriculum_track` — curriculum narrative
  - `briefing.generate_narrative` — briefing HTML/text
  - `crm.draft_rescue_email` — email body (not document, but adjacent)

- **Extractors** (structured JSON from document inputs):
  - `scribe.extract_first_call` / `scribe.extract_case_fields` / `scribe.extract_case_fields_live`
  - `accounting.extract_check_image` — vision, check details
  - `pricing.extract_pdf_text` — vision, price list extraction
  - `urn.extract_intake_email` — intake email fields
  - `kb.parse_document` — knowledge base chunking
  - `import.detect_order_csv_columns` — CSV column mapping

Together these span the two ends of a document lifecycle: AI-extract
structured data from an inbound document; AI-generate an outbound
document from structured data. What doesn't exist today is the middle —
a unified "Document" concept those prompts attach to.

---

## Step 9 — Frontend document UI

### Upload surfaces

| Location | File | Entity | Endpoint |
|---|---|---|---|
| Case detail (Documents tab) | pages/funeral-home/case-detail.tsx | fh_case | via DocumentList |
| Generic entity attachment | components/document-list.tsx (lines 1-170) | entityType + entityId params | POST `/documents/upload` |
| Knowledge base | pages/knowledge-base.tsx (lines ~150-400) | category-scoped | internal |
| Safety training documents | pages/safety/safety-training-documents.tsx | topic | URL + filename form (not file picker) |

### Download / view surfaces

| Location | Mechanism |
|---|---|
| DocumentList (all entities) | `documentService.downloadDocument()` — fetches blob, creates Object URL, triggers `<a download>` click |
| Invoice detail page | `window.open(/api/v1/sales/invoices/{id}/preview?format=pdf)` — direct browser open |
| Price list version row | Fetch + blob → "Download PDF" button |
| Legacy proof generator | `downloadFile(url, filename)` — blob fetch + link trigger |
| Case detail tabs | Vault tab + Obituary tab + Documents tab + Invoice tab — each renders its own surface |

### Existing document abstraction

**There is no unified "Document Library" page.**

Reusable components:
- `DocumentList` (components/document-list.tsx) — generic upload/download for any entity, but only embedded in entity detail pages

Per-feature document UIs (fragmented):
- Generic Document system (`Document` model + `documents.py` route)
- VaultDocument layer (separate tenant-facing abstraction for cross-entity vault items, supports family access)
- Knowledge Base documents (category-scoped, parsed for RAG)
- FH case documents (death certs, permits)
- Social Service Certificates (auto-generated PDF)
- Safety Program PDFs (HTML → PDF pipeline)
- Training documents (per-topic)
- Legacy vault prints (personalization catalog)

There's no unified search across all document types. Download flows
default to 307 redirect to R2. No frontend PDF viewer — browser native
or external links.

---

## Step 10 — Database models for documents

### Summary — 18 document-adjacent models

| Model | File | Tenant | Storage | Attached to | Kind |
|---|---|---|---|---|---|
| Document | document.py | company_id | `r2_key` + `file_path` | entity (generic) | Container |
| VaultDocument | vault_document.py | company_id | `file_key` | vault_id, entity | Container |
| VaultItem | vault_item.py | company_id | `r2_key` (when doc) | vault_id, entity | Polymorphic container |
| FHDocument | fh_document.py | company_id | `file_url` | fh_case_id | Container |
| FHObituary | fh_obituary.py | company_id | text field | fh_case_id | Content |
| SocialServiceCertificate | social_service_certificate.py | company_id | `pdf_r2_key` | sales_order_id | Container |
| CustomerStatement | statement.py | tenant_id | `statement_pdf_url` | run, customer | Container |
| StatementRunItem | statement.py | tenant_id | `pdf_path` | run, customer | Container |
| SafetyProgramGeneration | safety_program_generation.py | tenant_id | `pdf_document_id` FK | topic, schedule | Container + Content |
| SafetyProgram | safety_program.py | company_id | text | topic, schedule | Content |
| KBDocument | kb_document.py | tenant_id | `raw_content` + `parsed_content` | category | Content |
| KBChunk | kb_chunk.py | tenant_id | text chunk | kb_document | Content |
| TenantTrainingDoc | tenant_training_doc.py | tenant_id | `file_url` | topic | Container |
| DeliveryMedia | delivery_media.py | company_id | `file_url` | delivery, event | Container |
| ProgramLegacyPrint | program_legacy_print.py | company_id | `file_url`, `thumbnail_url` | program | Container (catalog) |
| OrderPersonalizationPhoto | order_personalization_photo.py | company_id | `file_url` | order, task | Container |
| ReportRun | report.py | tenant_id | N/A | — | Metadata |
| AuditPackage | report.py | tenant_id | `pdf_path` | — | Container |

### Salient model details

- **Document** — the generic entity attachment. `entity_type` (string) + `entity_id` (string) gives flexible attachment to any model. Dual storage (`file_path` + `r2_key`) supports lazy migration. No soft-delete in schema; hard delete with R2 fallback.
- **VaultDocument** — modern abstraction. R2-only (no local fallback). `is_family_accessible` for portal exposure. `workflow_run_id` links output to the workflow step that produced it. Soft delete via `is_active`.
- **VaultItem** — polymorphic "vault" container. `item_type` discriminator (document | event | communication | reminder | order | quote | case | contact | asset | compliance_item | production_record). Document-specific fields include `r2_key`, `file_size_bytes`, `mime_type`, `document_type`. Cross-tenant sharing via `shared_with_company_ids` JSONB. Hierarchy via `parent_item_id`. Most flexible / most complex model.
- **FHObituary** — text content stored directly in `content` field. Generation tracking (`generated_by`, `ai_prompt_used`). Family approval workflow (`family_approved_at`, `family_approved_by_contact_id`). `published_locations` JSON for external site publication.
- **SocialServiceCertificate** — unique per `order_id`. Status lifecycle: pending_approval → approved → sent, or voided. Approval fields (`approved_at`, `approved_by_id`, `voided_at`, `voided_by_id`, `void_reason`). Distribution (`sent_at`, `email_sent_to`).
- **CustomerStatement** — per-customer-per-period record. Rich delivery tracking (`delivery_method`, `sent_at`, `email_sent_to`, `send_error`). Review workflow (`flagged`, `flag_reasons`, `review_status`). Cross-tenant delivery fields (`cross_tenant_delivered_at`, `cross_tenant_received_statement_id`, payment tracking).
- **SafetyProgramGeneration** — combines generation pipeline state (OSHA scrape status, Claude generation status, PDF status, approval workflow). References `pdf_document_id` FK to Document. Multi-step status makes this the closest existing model to a "Documents workstream" state machine.
- **KBDocument** / **KBChunk** — content-only (no R2 files). Used for RAG; `parsed_content` is chunked into KBChunks for retrieval.

### Models worth flagging for planning

- **VaultItem + VaultDocument** are the two most recent document models. VaultItem is broader (polymorphic) but VaultDocument is narrower and more production-used. Either could become the foundation for a unified Documents layer, but reconciling the two will be a planning decision.
- **Document (generic)** is the oldest and most widely used. Migration away from it would touch a lot of surface area.
- **StatementRunItem** vs **CustomerStatement** — two overlapping statement models, with `pdf_path` on the former and `statement_pdf_url` on the latter. Worth understanding which is canonical before changes.

---

## Synthesis

### Current state assessment

**Is document handling coherent or ad-hoc?**

**Ad-hoc, with pockets of maturity.** Ad-hoc in the generator layer —
seven independent PDF services, three of which bypass Jinja entirely
(inline f-strings or Claude-generated HTML). Coherent in storage —
Cloudflare R2 is the one blessed backend, with lazy migration from local
files. Mature-but-isolated in e-signature — DocuSign is production for
one document type, unused for everything else. Mature in cross-tenant
flows — five document types cross boundaries today via three different
mechanisms.

**How many distinct document types?**

At least 10 generated or captured:
1. Invoices (3 template variants)
2. Monthly customer statements
3. Price lists
4. Disinterment release forms (DocuSigned)
5. Social service certificates
6. Legacy vault prints (personalization)
7. Safety programs (monthly, AI-generated)
8. Audit packages (multi-report PDFs)
9. Obituaries (text content, portal-rendered)
10. Delivery-confirmation media (photos + signatures)

Plus ingested documents:
- Knowledge base documents (parsed for RAG)
- Price list imports (CSV/PDF)
- Urn catalog PDFs (parsed via PyMuPDF)
- Driver-captured delivery photos and signatures

### Library use

- **WeasyPrint** is the entire PDF story. No reportlab, pdfkit, fpdf. Simple, one fewer thing to reason about.
- **Jinja2** is the partial template story — used by 4 of 7 generators. The other 3 (Social Service Cert, Legacy Vault Print, Safety Program) bypass it entirely.
- **Email templates** are pure Python string formatting, outside the Jinja world.
- **PyMuPDF** is the extraction library for Wilbert catalog parsing; not a generator.

### Template storage

- **8 template files** in `backend/app/templates/{invoices,statements,price_lists,disinterment}/`
- **Inline f-string templates** for Social Service Certificates + Legacy Vault Prints — no source file
- **Runtime-generated HTML** from Claude for Safety Programs — no source template at all
- **Email HTML** via Python f-strings in `email_service.py`

### Storage

- **R2 primary.** All new uploads and generations land in R2.
- **Local disk legacy**, lazy-migrated on access. Bulk migration endpoint exists for admins.
- **Generic Document model + many purpose-built models** (VaultDocument, FHDocument, SocialServiceCertificate, etc.). No unified metadata schema — some use `r2_key`, some `file_key`, some `file_url`, some `pdf_r2_key`.

### Gap analysis for a Documents workstream

**What would a Documents backbone need that doesn't exist today?**

1. **A unified DocumentRenderer / TemplateManager** that owns Jinja setup, WeasyPrint conversion, and provides fallback handling. De-duplicates ~100 LOC across 5 services; establishes one seam for tenant-wide branding, A/B template experimentation, i18n, accessibility.
2. **A unified Document model** with a single storage contract (one column name, not 4 variants) and a clean tenant-scoping + access-control pattern. Probably sits on top of VaultDocument or is a natural evolution of it.
3. **A managed `document.render` / `document.generate` API** analogous to `intelligence_service.execute()` — accepts a template key + context dict + tenant, returns a persisted Document record. Optional: cost tracking, rendering time metrics, version history (template version was v3 at render time).
4. **A Document library / file manager UI** — single page that browses every document visible to the current user/tenant, with faceted search by document type, entity, date range. Today every entity detail page embeds its own DocumentList fragment.
5. **A signature abstraction** that extends the DocuSign integration beyond disinterment to cover cremation authorization, insurance assignment, EDRS submissions. The pattern (per-tenant settings, HMAC webhooks, 4-party routing) is reusable.
6. **External submission implementations** (EDRS, VA, insurance) — the workflow engine hook exists, the Playwright infrastructure is production, the placeholder workflows exist. All three are empty.
7. **A cross-tenant document fabric** that unifies today's five separate flows (statement, delivery confirmation, cross-tenant order, training cert, COI). Current state is four separate mechanisms all with their own permission checks.

**What existing code would be migrated vs left alone?**

- **Migrate:** The 7 generators could all flow through a unified `DocumentRenderer` without changing their templates. That's the smallest high-value refactor.
- **Migrate:** The 4 different storage column names (`r2_key` / `file_key` / `file_url` / `pdf_r2_key`) could normalize. But that's across 18+ models and risks breaking a lot of read paths — defer unless a specific pain point demands it.
- **Leave alone:** DocuSign integration for disinterment — it's production, pattern is clean, just extend by adding new document types rather than refactoring what works.
- **Leave alone:** KB documents — they're content-only with RAG chunking, a different concern from output-document management.
- **Evolve carefully:** VaultItem polymorphism is broad. It may or may not be the right foundation for the Documents layer — needs a design call.

**Integration points with existing systems**

- **Intelligence (managed prompts):** at least 5 prompts already produce document content. A Documents backbone could automatically persist their output as Document records with linkage back to the `intelligence_executions` audit row. The `execution_id` plumbing already exists.
- **Workflow engine:** `_execute_ai_prompt` already runs managed prompts. The empty `action_type = "generate_document"` hook in `_execute_action` is a ready-made integration point for "workflow step → render Document record."
- **Cross-tenant:** A Documents backbone could formalize the shared-visibility model that VaultItem's `shared_with_company_ids` prototypes. Today's four mechanisms could become one.
- **E-signature:** DocuSign integration's per-tenant settings pattern is the template for signature capture on any document type, not just disinterment.

**"Category C" equivalent — ad-hoc generators bypassing any abstraction**

Three generators produce documents via inline Python HTML / runtime-generated Claude HTML rather than from a template file:

1. Social Service Certificate — f-string HTML in `social_service_certificate_pdf.py`
2. Legacy Vault Print — f-string HTML in `legacy_vault_print_service.py`
3. Safety Program — Claude-generated HTML at runtime

Plus **all email templates** via `email_service.py` + `legacy_email_service.py` (pure Python string formatting, not Jinja).

These are the targets if the Documents workstream wants a "no templates
outside the managed template registry" lint, analogous to the
Intelligence TID251 ruff rule that forbids anthropic SDK imports
outside the Intelligence package.

### Near-term document priorities

**Which document types are generated most frequently?**

By structural position:
1. **Invoices** — every order produces one; highest-volume daily
2. **Customer Statements** — monthly per funeral home customer, batch-generated
3. **Delivery Media** — every delivery produces photos + signatures
4. **Legacy Vault Prints** — every funeral case produces one
5. **Safety Programs** — monthly per tenant with safety enabled
6. **Social Service Certificates** — one per SS order delivery
7. **Audit Packages** — on-demand, infrequent
8. **Disinterment Release Forms** — rare, high-stakes

**Which have obvious user-facing quality issues?**

- Social Service Certificates and Legacy Vault Prints — inline f-string HTML is hard to iterate on. Design changes require code deploys. Tenants can't customize branding.
- Email templates — same problem, plus they're scattered across two service files.
- Safety Programs — Claude generates HTML fresh every month; no template baseline, no consistency guarantees, hard to quality-check.

**Which are blocking user workflows?**

- **EDRS death certificate filing** — blocks FH compliance workflow; FHs today do this manually elsewhere.
- **Insurance assignment** — blocks FH billing collection; manual today.
- **VA forms** — blocks FH veteran benefit processing; manual today.

All three have `is_coming_soon=True` placeholder workflows in the library; no implementation.

### September demo relevance

**Which document types would Wilbert licensees encounter during a demo?**

Manufacturer demo primary surface:
1. **Invoices** (AR review, delivery-day statements)
2. **Customer Statements** (monthly FH billing)
3. **Delivery tickets** (route cards, confirmation signatures — currently just photos/signatures, not formal tickets)
4. **Price Lists** (tenant branding, send-to-customer flow)
5. **Safety Programs** (monthly OSHA compliance — FLIP-able demo)
6. **Audit Packages** (accountant read-only view)

Manufacturer demo secondary:
7. **Cross-tenant delivery confirmations** (a FH receiving a delivery cert from the vault manufacturer is a good "network effect" story)
8. **Legacy Vault Prints** (personalization preview)

**Which need to look polished vs internally functional?**

Polished (demo-facing):
- **Price lists** — tenant uploads logo, picks template, sends to customer
- **Invoices** — same polish level; template variants already exist
- **Safety Programs** — the "AI generates your OSHA program" demo; needs to actually look like a real program
- **Monthly Statements** — cross-tenant delivery story

Internally functional:
- **Audit Packages** — accountant-only, plain is fine
- **Driver delivery media** — utility, not presentation
- **Legacy Vault Prints** — family-facing but low-demo-visibility

### Cross-tenant document flows

**What crosses today:**
- Customer Statement PDFs (mfg → FH)
- Delivery Confirmations (mfg → FH via VaultItem sharing)
- Cross-tenant Sales Orders (FH → mfg)
- Training Certificates (source → shared recipients)
- Insurance Certificates / COI (issuer → recipients)
- Licensee Transfer Notifications (home mfg → area mfg)
- Legacy Vault Prints (FH → mfg, implicitly via cross-tenant sales order)

**What's planned but not built:**
- Formal "document shared with you" inbox on the receiving tenant side
- Cross-tenant revocation (today sharing is additive, never revoked)
- Cross-tenant audit trail (who saw the document, when)
- Cross-tenant e-signature (DocuSign handles multi-party but all parties are known parties, not cross-tenant *tenants*)

**Security model today:**
- Per-model `company_id` scoping
- `shared_with_company_ids` JSONB lookup for VaultItems
- `billing_enabled` flag on PlatformTenantRelationship
- Status workflows on LicenseeTransfer
- No unified permission model; no audit log of cross-tenant access

### Signature and submission reality

**Signature capture today:**
- **DocuSign** is live for disinterment release forms (4-party, HMAC webhooks, R2 storage). Production quality.
- **Manual sign-off fields** for cremation authorization (timestamp + string signer name) on FHCase and FuneralCase. Not legally equivalent to e-sig.
- **Driver mobile signatures** (image capture on phone, stored as DeliveryMedia with `media_type='signature'`). Not cryptographically verified.

**External submissions today:**
- **Uline vendor ordering** is the only live Playwright script.
- **EDRS death certificate, insurance assignment, VA benefits** — placeholder workflows, empty implementations.

**What's needed at minimum for FH compliance:**
- EDRS death certificate filing (state-specific, ~50 different portals; Playwright-appropriate)
- Signed cremation authorization (DocuSign extension of the disinterment pattern)
- Insurance assignment forms (Playwright + carrier portals)
- VA form 40-1330 (headstone/marker application) and VA form 21-530 (burial benefits)
- Social Security death notification (form SSA-721)
- FTC Funeral Rule compliance documentation (GPL, CPL, Casket Price List) — compliance scoring exists; generation + versioning exists via price_list; distribution to customers exists. This one is arguably done.

---

## Recommended Documents workstream phasing (ballpark)

This is a sketch, not a detailed plan. The detailed plan comes next.

### Phase D-1 — Documents backbone (unified renderer + storage contract)

- **DocumentRenderer / TemplateManager** service — Jinja setup once, WeasyPrint conversion once, fallback handling once. Migrate the 4 template-based generators to use it. Leave the 3 inline-HTML ones alone initially.
- **Unified Document model consolidation plan** — decide whether Document, VaultDocument, or VaultItem is the canonical. Draft migration paths for each alternative. Pick one. Write a migration that preserves data.
- **A `document.generate` / `document.render` service API** analogous to `intelligence_service.execute()`. Returns a persisted Document record with metadata (template version at render time, input hash, rendering cost).
- **Tests:** renderer contract tests, migration rollback test, one integration test per migrated generator.

### Phase D-2 — Templates in a managed registry (analogous to Intelligence prompts)

- **`document_templates` table** with versioning, tenant overrides, changelog, activation/retirement. Mirror the IntelligencePrompt / IntelligencePromptVersion shape.
- **Admin UI** for browsing + editing templates (mirror PromptLibrary / PromptDetail). Preview mode: render with sample data, no actual PDF.
- **Migrate the 3 inline-HTML generators** into managed templates. This is the "Category C" equivalent — extract the f-strings into versioned template rows.
- **Lint gate** — forbid new `weasyprint.HTML(string=...)` outside the DocumentRenderer. Ruff rule + pytest-based check.

### Phase D-3 — Signature fabric (extend DocuSign beyond disinterment)

- **Per-document-type signature flow config** — an admin can mark any document type as "signature required" with a list of signer roles.
- **Cremation authorization → DocuSign**. Reuse the pattern. New DocuSignFlow model rows per document type.
- **A signature_captured webhook event** that other services subscribe to (e.g., case service advances case status when all signatures are in).

### Phase D-4 — External submission library (EDRS + insurance + VA)

- **Playwright script for one state's EDRS portal.** Pick a representative state (NY, FL, OH are reasonable choices). Establishes the pattern.
- **Playwright script for insurance assignment** — pick one carrier.
- **Playwright script for a VA form** — start with 40-1330 (headstone).
- **Submission-specific Document model** that tracks submission status, confirmation numbers, screenshots, retry history.

### Phase D-5 — Cross-tenant document fabric

- **Unified cross-tenant sharing model** — supersedes today's four mechanisms. `DocumentShare` table with source_company_id, shared_with_company_ids, document_id, visibility, shared_at, revoked_at, audit trail.
- **Cross-tenant document inbox** — every tenant has a "documents shared with me" view.
- **Audit trail** — who viewed / downloaded / signed / responded.

### Phase D-6 — Document UI (library, manager, browser)

- **`/admin/documents`** unified library, analogous to `/admin/intelligence/prompts`.
- **Faceted search:** by document type, entity, date range, signature status, cross-tenant source.
- **Reuse the Intelligence admin UI patterns** (URL-state filters, cost/latency/table layouts). Same component library.

---

## Open questions for human decision

These need answers before Phase D-1 scope is locked:

1. **Canonical document model: Document, VaultDocument, or VaultItem?** VaultItem is the most flexible but most complex. VaultDocument is clean but narrow. Document is widely used but has dual storage columns. Pick one; the others either get deprecated or co-exist with a migration path.

2. **Templates in DB vs files on disk?** Intelligence prompts are in the DB (with versioning + tenant overrides). Today's document templates are files in git. Moving to DB enables admin UI editing + tenant branding, but adds complexity. Decision point.

3. **How hard do we gate PDF generation bypasses?** The Intelligence work added a TID251 ruff rule forbidding direct Anthropic SDK imports. Do we add an equivalent for WeasyPrint? It would force the 3 inline-HTML generators to migrate, but it's disruptive.

4. **Cross-tenant permissioning model.** Four mechanisms exist today, all ad-hoc. Unify now (cost: migration), defer indefinitely (cost: four things to maintain forever), or take a hybrid (cost: accept two in production).

5. **September demo — document polish budget.** How much time is worth investing in template polish vs functional coverage? Price list templates already have 3 variants; do we add 3 more? Or is "it works" good enough and we invest in the EDRS demo story instead?

6. **EDRS portal coverage scope.** 50 states, 50 portals. Which state's portal do we implement first? Is there a sample tenant that drives this pick?

7. **Signature platform: DocuSign-only or also build our own?** DocuSign works but costs money and requires per-tenant account setup. A "typed name + tick box + audit row" pattern works for low-stakes signatures (delivery confirmations, internal approvals) and removes a vendor dependency. Decision on which tier of signature each document type needs.

8. **Audit Package vs financial report PDFs.** Today, individual financial reports are NOT available as PDFs — only the bundled audit package is. Is individual-report PDF a priority, or is the bundled format enough?

9. **Legacy email template migration.** Email templates in `email_service.py` are inline Python strings. Migrating them to Jinja (or to the managed template registry) has the same cost/benefit tradeoff as the three inline-HTML PDF generators. Same decision point but separate system.

10. **VaultItem's polymorphism.** VaultItem holds documents, events, communications, reminders, assets, compliance items, production records — all in one table. Is this the final shape, or do we split it in the Documents workstream? Splitting is a large migration; keeping unified means the Documents layer has to work alongside a polymorphic superclass.

---

**End of audit.**

_This document is intended to inform the next planning conversation. If
something is missing, flag it and I'll investigate further before Phase
D-1 is scoped._
