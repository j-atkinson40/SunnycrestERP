# Documents Architecture — Phase D-1

The Bridgeable Documents layer replaces seven independent PDF-generation
services with one canonical pipeline. Every AI-generated or
template-rendered document now flows through `DocumentRenderer` and
lands as a `Document` row with full audit trail, versioning, and
workflow/Intelligence linkage.

Audience: developers adding a new document type or modifying an existing
one.

---

## The canonical model

Two tables at the core:

```
documents             — one row per logical document (e.g. "Invoice INV-42
                         for customer X"). Tenant-scoped via company_id.
document_versions     — one row per render. is_current=True on exactly one
                         version per document_id.
```

Plus `caller_document_id` on `intelligence_executions` to link AI calls
back to the documents they produced.

**Class names:** the canonical class is `app.models.canonical_document.Document`.
The module is named `canonical_document` (not `document`) because the
legacy generic Document class still exists at `app.models.document`.
Both live in the SQLAlchemy registry. Code that imports `Document` via
string resolution (`relationship("Document", ...)`) will hit a
disambiguation error — use the fully-qualified class reference or
`"app.models.canonical_document.Document"` in such relationships.

For convenience, `app.models.__init__` re-exports:

```python
from app.models import CanonicalDocument, DocumentVersion, Document  # Document is legacy
```

---

## The renderer

```python
from app.services.documents import document_renderer

doc = document_renderer.render(
    db,
    template_key="invoice.professional",
    context={"invoice_number": "INV-42", ...},
    document_type="invoice",
    title="Invoice INV-42",
    company_id=company.id,
    # Entity linkage — populate whichever apply
    entity_type="invoice",
    entity_id=invoice.id,
    invoice_id=invoice.id,
    sales_order_id=order.id,
    # Source linkage
    caller_module="my_service.my_function",
    caller_workflow_run_id=run_id,  # if called from a workflow
    intelligence_execution_id=exec.id,  # if content came from an AI call
    rendered_by_user_id=current_user.id,
)
# doc.storage_key  — R2 path for the PDF
# doc.id           — UUID; pass to caller_document_id on downstream calls
# doc.rendering_context_hash — SHA-256 of the JSON-serialized context
```

Under the hood:

1. `template_loader.load(template_key)` — D-1 reads from files under
   `backend/app/templates/`. D-2 replaces this with a DB-backed registry.
   Calling code doesn't change.
2. Jinja renders the template with your context.
3. WeasyPrint converts HTML → PDF bytes.
4. `legacy_r2_client.upload_bytes(data, key)` stores to R2 at
   `tenants/{company_id}/documents/{document_id}/v{n}.pdf`.
5. A `Document` row and its first `DocumentVersion` (`version_number=1`,
   `is_current=True`) are inserted.

Errors in steps 1-4 raise `DocumentRenderError`. The Document + Version
rows only exist if all four steps succeed.

### Re-rendering

```python
doc = document_renderer.rerender(
    db,
    document_id=existing_doc.id,
    context={...updated...},
    render_reason="data_updated",
    rendered_by_user_id=current_user.id,
)
```

Rerender:
- Creates a new `DocumentVersion` with `version_number = prev + 1`
- Flips the previous version's `is_current = False`
- Updates `Document.storage_key` to point at the new version
- Mirrors `file_size_bytes`, `rendering_duration_ms`, `rendered_at` onto `Document`

---

## Adding a new document type

Two paths:

### Path A: Jinja template + thin generator service

For documents tied to a specific entity (invoices, certificates, forms):

1. Add a template file under `backend/app/templates/<domain>/<variant>.html`
2. Register it in `backend/app/services/documents/template_loader.py::_TEMPLATE_REGISTRY`:
   ```python
   "<domain>.<variant>": ("<domain>", "<variant>.html"),
   ```
3. Write a thin generator service that builds the context dict and calls
   `document_renderer.render(...)`. Look at
   `disinterment_pdf_service.generate_release_form_document()` as the
   pattern to mirror.
4. Populate the specialty FK that matches your entity (e.g. `invoice_id`,
   `fh_case_id`) so "all documents for this entity" queries are cheap.

### Path B: Direct renderer call from a workflow

When the context is already assembled by prior workflow steps, use the
`generate_document` action without writing a new service:

```json
{
  "action_type": "generate_document",
  "template_key": "invoice.professional",
  "document_type": "invoice",
  "title": "Invoice {input.ask_invoice_number.value}",
  "context": {
    "invoice_number": "{input.ask_invoice_number.value}",
    "customer_name": "{output.extract_customer.name}"
  }
}
```

The workflow engine's `_handle_generate_document` resolves variables,
calls `document_renderer.render()`, auto-populates caller linkage from
`run.trigger_context`, and emits an output dict downstream steps can
reference:

```
{output.my_step.document_id} → UUID of the new Document
{output.my_step.pdf_url}     → 1-hour presigned R2 URL
{output.my_step.version_number} → 1 for initial renders
```

---

## Caller linkage — what gets populated when

Every Document row can carry three linkage axes:

### Entity linkage (who is this document about?)

| Column | When to populate |
|---|---|
| `entity_type` + `entity_id` | Polymorphic — any entity |
| `sales_order_id` | Document about a sales order |
| `fh_case_id` | Document about a funeral case |
| `disinterment_case_id` | Disinterment release form, etc. |
| `invoice_id` | Document about a specific invoice |
| `customer_statement_id` | Monthly statement PDF |
| `price_list_version_id` | Price list PDF |
| `safety_program_generation_id` | Monthly safety program PDF |

Populate the specialty FK when it applies AND the polymorphic
`entity_type`/`entity_id` pair. The specialty FK makes JOIN-based
queries cheap; the polymorphic pair makes iteration-based queries
possible without knowing the type upfront.

### Source linkage (who/what produced this document?)

| Column | When to populate |
|---|---|
| `caller_module` | Every call — use `"<service>.<function>"` naming |
| `caller_workflow_run_id` | When called from a workflow step |
| `caller_workflow_step_id` | When called from a specific workflow step |
| `intelligence_execution_id` | When content came from an AI call |

The workflow engine handler (`_handle_generate_document`) populates the
workflow fields automatically. Services calling `render()` directly
should set `caller_module` at minimum.

### Audit linkage (on intelligence_executions)

When an AI call produces a document, set `caller_document_id` on the
execution row so you can query "all AI calls that fed this document":

```python
result = intelligence_service.execute(
    db, prompt_key="...", variables={...},
    caller_document_id=document.id,  # <-- this
)
```

---

## Migrated generators (Phase D-1)

Four of the seven legacy generators now route through the Documents
layer. Their public functions are unchanged — callers keep working.

| Service | D-1 entry point | Public (legacy) |
|---|---|---|
| `disinterment_pdf_service` | `generate_release_form_document()` | `generate_release_form_pdf()` |
| `pdf_generation_service` (invoices) | `generate_invoice_document()` | `generate_invoice_pdf()` |
| `price_list_pdf_service` | `generate_price_list_document()` | `generate_price_list_pdf()` |
| `statement_pdf_service` (new) | `generate_statement_document()` | — |

The legacy byte-returning functions now internally call the Document
entry point and then fetch bytes from R2. Existing callers in
`routes/sales.py`, `routes/price_management.py`, and the DocuSign
integration in `docusign_service.py` keep working without change.

Not yet migrated (Phase D-2):
- Social Service Certificate — inline f-string HTML in
  `social_service_certificate_pdf.py`
- Legacy Vault Print — inline f-string HTML in
  `legacy_vault_print_service.py`
- Safety Program — Claude-generated HTML at runtime
- Email templates in `email_service.py` + `legacy_email_service.py`

---

## API surface

Mounted at `/api/v1/documents-v2/*`. All admin-gated, all tenant-scoped.

```
GET    /api/v1/documents-v2
       query: document_type, entity_type, entity_id, status, date_from,
              date_to, limit, offset
       returns: list of DocumentListItem

GET    /api/v1/documents-v2/{document_id}
       returns: DocumentDetailResponse with full version history

GET    /api/v1/documents-v2/{document_id}/download
       returns: 307 redirect to presigned R2 URL (1h TTL)

GET    /api/v1/documents-v2/{document_id}/versions/{version_id}/download
       returns: 307 redirect to presigned URL for that specific version

POST   /api/v1/documents-v2/{document_id}/regenerate
       body: { reason, context_override }
       returns: updated Document
```

The legacy `/api/v1/documents/*` routes continue to serve the old
Document model against the `documents_legacy` table; they will be
retired after callers migrate to the canonical API.

---

## Template registry (Phase D-2)

Templates moved from `backend/app/templates/*.html` files into two DB
tables:

```
document_templates            — one row per template_key, per scope
                                (platform=company_id NULL, or tenant)
document_template_versions    — versioned content. status = draft | active | retired.
                                Exactly one active version per template.
```

### Hybrid scoping

`template_key` is unique per `(company_id, template_key)` — platform
rows have `company_id=NULL`, tenant overrides have it set. Lookup
resolves tenant-specific first, falls back to platform:

```python
from app.services.documents import template_loader

loaded = template_loader.load(
    "invoice.professional",
    company_id=current_user.company_id,
    db=db,
)
# loaded.company_id is None if the platform template was used,
# company_id set if a tenant override took precedence.
```

### Output formats

Each template declares `output_format`: `pdf` | `html` | `text`.
`document_renderer.render()` dispatches on this:

- `pdf` → Jinja → WeasyPrint → R2 → canonical Document + DocumentVersion rows
- `html` → Jinja → string (no Document, no R2)
- `text` → Jinja → plain string (no Document, no R2)

**Resolution modes (D-9):**
`render()` accepts either `template_key` (current-active lookup —
tenant-first / platform-fallback, the production path) OR
`template_version_id` (specific-version lookup — used by the
test-render endpoint to render drafts / retired versions). The
test-render endpoint is a thin adapter that delegates to the renderer
with `is_test_render=True`; there is no duplicate rendering pipeline.

HTML + text callers use the convenience wrappers:

```python
from app.services.documents import document_renderer

# For email: renders HTML body + subject (if the template has one)
result = document_renderer.render_html(
    db,
    template_key="email.statement",
    context={"customer_name": "Joe", "tenant_name": "Wilbert", ...},
    company_id=company.id,
)
email_html = result.rendered_content   # str
email_subject = result.rendered_subject  # str | None
```

### Seeded platform templates (18 total, as of D-2)

**PDF — migrated from file-based (Phase D-1):**
- `invoice.{modern, professional, clean_minimal}`
- `statement.{modern, professional, clean_minimal}`
- `price_list.grouped`
- `disinterment.release_form`

**PDF — migrated from inline Python strings (Phase D-2):**
- `pdf.social_service_certificate`
- `pdf.legacy_vault_print`
- `pdf.safety_program_base` — structural wrapper; the AI-generated
  program body is embedded via the `ai_generated_html` context variable
  with `|safe` (trust established by the managed
  `safety.draft_monthly_program` Intelligence prompt)

**PDF — migrated from direct WeasyPrint (Phase D-9):**
- `quote.standard` — customer-facing quote. `quote_service` now creates
  canonical Documents with `entity_type="quote"`.
- `urn.wilbert_engraving_form` — Wilbert urn engraving submission form
  (one page per piece + companions). Bytes-only path; not persisted
  per call (transient physical-form output).

**Email — migrated from `email_service.py` + `legacy_email_service.py`:**
- `email.base_wrapper`, `email.statement`, `email.collections`
- `email.invitation`, `email.accountant_invitation`, `email.alert_digest`
- `email.legacy_proof`

File-based `backend/app/templates/*.html` directories are kept on disk
as reference for the PDF variants — the DB is the source of truth after
r21.

## Template editing (Phase D-3)

D-3 adds the editing surface. Tenant admins can create draft versions,
preview them, test-render them, and activate them with safety gates.
Every transition writes to `document_template_audit_log`.

### Draft lifecycle

```
         (no draft)                  ┌───────────────────┐
             │                       │                   ▼
             ▼                       │            ┌──────────┐
       ┌──────────┐   activate       │            │ retired  │
       │  draft   ├─────────────────►│            └──────────┘
       └──────────┘                  ▼                   ▲
             ▲                 ┌──────────┐  activate    │
             │ rollback        │  active  ├──────────────┘
             │ creates new     └──────────┘  (retires prior)
             │ version that                  ▲
             │ copies content                │ rollback creates
             │                               │ new version, target
             └───────────────────────────────┘ stays retired
```

- At most **one draft per template** at a time (service-layer enforcement).
- At most **one active version per template** — activation retires the
  prior active.
- **Rollback is not reactivation.** It clones a retired version's
  content into a new monotonically-numbered active version; the target
  stays retired. This keeps the audit trail linear.

### Permission model

| Template scope | Viewable by | Editable by | Confirmation required |
|---|---|---|---|
| Platform (`company_id IS NULL`) | Any admin | super_admin only | Yes — type the `template_key` verbatim |
| Tenant (`company_id = X`) | Tenant X admins | Tenant X admins | No |

Tenant admins who can't edit a platform template can **fork it to their
tenant**. The fork creates a tenant-scoped copy with independent version
history (version numbering restarts at 1). The tenant's copy
automatically takes precedence via the D-2 hybrid lookup.

### Variable schema validation

`app.services.documents.template_validator` parses the Jinja2 AST
(`jinja2.meta.find_undeclared_variables`) to extract referenced variables
— loop-locals and `{% set %}` names are automatically excluded. On
activation:

- **Error** (blocks activation): `invalid_jinja_syntax`,
  `undeclared_variable` (referenced but not in schema).
- **Warning** (surfaced but doesn't block): `unused_variable`
  (declared in schema, never referenced). Variables with
  `{"optional": true}` in their schema entry are excused.

Frontend surfaces errors inline in the activation dialog so the admin
can fix and retry.

### Test renders

Test renders flow through the same `document_renderer` + Jinja +
WeasyPrint pipeline as production, with two differences:

1. The persisted `Document.is_test_render` flag is `True`.
2. The Document Log excludes test renders by default; an
   `include_test_renders=true` query parameter opts in.

This isolates template-editor experiments from production stats. For
HTML/text templates, test renders don't persist a Document at all —
they're rendered in-memory and returned to the admin.

Test sending (e.g. firing an email to `support@`) is deferred to D-7
when the delivery abstraction lands.

### Audit log

`document_template_audit_log` captures every state transition with:

- `template_id` + `version_id` (the version being acted on, if any)
- `action` — one of `create_draft`, `update_draft`, `delete_draft`,
  `activate`, `rollback`, `fork_to_tenant`
- `actor_user_id` + `actor_email`
- `changelog_summary` (the user-supplied changelog)
- `meta_json` — free-form per-action metadata:
  - `activate`: `previous_active_version_id/number`
  - `rollback`: `rolled_back_to_version_id/number`,
    `previous_active_version_id/number`
  - `fork_to_tenant`: `source_template_id`, `source_version_id/number`,
    `target_company_id`
  - `update_draft`: `fields_changed`

The admin UI's Activity section is a paginated view of this table.

### Tenant override workflow (operational)

1. Admin opens `/admin/documents/templates/{id}` and sees the active
   platform version.
2. Clicking "Fork to tenant" copies the platform body into a new
   tenant-scoped template row + a v1 active version.
3. Admin edits the tenant copy (no super_admin needed) and activates.
4. Subsequent renders for that tenant use the override automatically
   via the D-2 lookup precedence (tenant first, platform fallback).

The platform template remains untouched. A tenant that retires its
override reverts to the platform default.

## Native signing (Phase D-4)

D-4 introduces `app.services.signing` — a full e-signature
infrastructure that runs in parallel with DocuSign. Native signing
gives admins a single UI + audit trail for every signed document
produced in the platform, with ESIGN-compliant consent recording,
tamper-detection hashes, and a Certificate of Completion.

Envelope = `SignatureEnvelope` record wrapping a canonical `Document`.
Parties are `SignatureParty` rows (one per signer, each with a unique
`signer_token` that's the sole auth for the public signing URL).
Fields are `SignatureField` rows (signature / initial / date /
checkbox / text) positioned by `anchor_string` or explicit page+x/y.
Every state transition writes an append-only `SignatureEvent`.

See `backend/docs/signing_architecture.md` for the full walkthrough,
state machines, ESIGN compliance checklist, and developer usage.

**What D-4 adds on top of the Documents layer:**

- Envelopes live inside the canonical Document graph — the envelope's
  `document_id` points at a Document; completion produces a new
  `DocumentVersion` with signatures applied. The Certificate of
  Completion is itself a Document via the managed
  `pdf.signature_certificate` template.
- Signing emails (`email.signing_invite`, `signing_completed`,
  `signing_declined`, `signing_voided`) are platform templates seeded
  by migration r23. Tenants can fork them via the D-3 editing flow.
- Public signer routes (`/api/v1/sign/*`) are unauthenticated — token
  is the only access check — and rate-limited to 10 req/min per token.
- Admin UI at `/admin/documents/signing/envelopes/*` mirrors the
  template/document library pattern (list + detail + wizard).

**D-5 completed the disinterment migration.** `DisintermentCase` now
has a `signature_envelope_id` FK that's populated on new cases.
`disinterment_service.send_for_signatures` creates a native envelope
with 4 parties (funeral home director, cemetery rep, next of kin,
manufacturer) in sequential routing, using anchor-based signature
placement (/sig_{role}/ anchors on the release-form template).
`signature_service.sync_disinterment_case_status` mirrors party state
into the legacy `sig_*` columns so existing code sees consistent
truth.

D-5 also replaced the D-4 **cover-page** signature approach with
**anchor-based inline overlay** via PyMuPDF. Signatures now appear on
the signature lines of the source document itself. See
`signing_architecture.md` § "Anchor-based overlay" for the mechanics.

DocuSign stays alive in the codebase for any in-flight pre-cutover
envelopes but is marked deprecated (`DeprecationWarning` emitted on
`create_envelope`). The webhook still receives status events for those
legacy envelopes. Deletion tracked by DEBT.md (threshold: zero
non-terminal `docusign_envelope_id` rows).

---

## Cross-tenant document sharing (Phase D-6)

D-6 introduces `document_shares` — the unified fabric for sharing
canonical Documents across tenant boundaries. Replaces 4 ad-hoc
mechanisms (statements emailed as attachments, delivery confirmations
exposed via VaultItems, etc.) with one grant/revoke/audit surface.

### The model

```
documents                   ← owner tenant's row (company_id = owner)
  ↓
document_shares             ← (document_id, target_company_id, revoked_at)
                              Non-revoked rows grant read access to target
  ↓
document_share_events       ← append-only audit (granted, revoked, accessed)
```

### Grant semantics

- `document_sharing_service.grant_share()` creates a share.
- Requires an active `PlatformTenantRelationship` between owner and
  target (either direction). This is the structural boundary — a
  tenant can't share into the void.
- Auto-generated shares from migrated generators use
  `ensure_share()` which bypasses the relationship check because the
  generator's existence is itself evidence of a business relationship
  (a manufacturer producing a statement FOR a customer tenant).
- Re-granting after revocation creates a new row (audit trail stays
  linear per-row; revoked shares are preserved forever).

### Revocation semantics

- Revocation is **future-access-only**. The share row stays; `revoked_at`
  is set. Previously-downloaded copies are outside the platform's
  control — revoke prevents API access, nothing more.
- This matches how DocuSign, S3 presigned URLs, and every
  production-grade system handle revocation. Pretending otherwise
  creates false security guarantees.
- UI copy makes this explicit.

### The `visible_to()` abstraction

Every cross-tenant-relevant Document query must route through
`Document.visible_to(company_id)`:

```python
rows = (
    db.query(Document)
    .filter(Document.visible_to(current_user.company_id))
    .filter(Document.deleted_at.is_(None))
    .all()
)
```

This returns `or_(Document.company_id == X, EXISTS(active share to X))`
— a single SQL expression that unifies owned + shared visibility.

Raw `Document.company_id == X` filters return only owned documents
and silently drop shares. A pytest lint gate
(`test_documents_d6_lint.py`) enforces this — any code querying
`Document.company_id` directly must either use `visible_to()` or
appear on `PERMANENT_ALLOWLIST` with a justification (owner-only
write paths, etc).

Owner-only operations (share creation, revocation, entity-linkage
lookups on your own documents) use `_get_owned_document_or_404()`
which is stricter — it rejects even valid shared-read visibility
because *writing* requires ownership.

### Migrated document types

| Type | Direction | Shared where | Status |
|---|---|---|---|
| Customer statement PDFs | Manufacturer → FH | `cross_tenant_statement_service.deliver_statement_cross_tenant` | D-6 ✓ |
| Delivery confirmations | Manufacturer → FH | `delivery_service._sync_media_to_vault` | D-6 ✓ |
| Legacy vault prints | FH → Manufacturer | `legacy_vault_print_service.generate` | D-6 ✓ |
| Training certificates | Mfg → Employees' FHs | — | Infra ready; no generator yet |
| Insurance certificates (COI) | Mfg ↔ FH | — | Infra ready; no generator yet |
| Licensee transfer notifications | Mfg A → Mfg B | — | Infra ready; part of licensee_transfer domain |

The 3 "infra-ready" rows exist as cross-tenant *concepts* in the
business model but haven't been built as platform features yet. When
their generators ship, they use `document_sharing_service.ensure_share()`
following the same pattern — no further infrastructure work needed.

### Inbox — the tenant's view

`/admin/documents/inbox` shows documents shared TO this tenant from
others. One row per share with the underlying document metadata +
owner tenant name. Filters by document_type + include_revoked toggle.

D-6 ships admin-only. A tenant-user-facing inbox (funeral home
directors seeing their statements, cemetery managers seeing delivery
confirmations) is a later phase; the backend supports it now.

### Symmetric Intelligence linkage

`intelligence_executions.caller_document_share_id` completes the
symmetric-linkage pattern Intelligence established. When an AI call
operates on a shared document (e.g. "summarize this statement a tenant
shared with me"), the execution links back to the share so auditors
can trace "which AI calls touched cross-tenant material."

---

## Delivery abstraction (Phase D-7)

D-7 introduces `app.services.delivery` — the channel-agnostic send
interface. Every email / SMS / future-channel send in the platform
flows through `DeliveryService.send()`, which writes a
`DocumentDelivery` row capturing the recipient, content, provider
response, and full source linkage.

Two implementations ship in D-7:
- **EmailChannel** wraps Resend — the ONLY place in the codebase
  allowed to import `resend` (lint-enforced).
- **SMSChannel** stubs out — returns `NOT_IMPLEMENTED` cleanly so
  callers get `status=rejected` rather than a crash.

Swapping providers (native email replacing Resend, native SMS
replacing the stub) is a one-line `register_channel()` call — no
caller changes.

`send_document` is a top-level workflow step type (mirrors `ai_prompt`
from Phase 3d) so workflows can orchestrate sends inline.

See `backend/docs/delivery_architecture.md` for the full walkthrough:
protocol definition, channel registry, content resolution,
attachment handling, retry semantics, adding a new channel, migrated
callers.

**Source linkage.** `document_deliveries.caller_*` columns + a new
`intelligence_executions.caller_delivery_id` close the symmetric
linkage loop. Any delivery is traceable to what triggered it, and any
Intelligence execution is traceable to the delivery it produced.

---

## Current limitations

- **No template editing UI.** D-2 ships read-only surfaces (Library,
  Detail, Log). Editing, activation, rollback, variable-schema validation
  and audit log are D-3 scope (Intelligence Phase 3b established the
  pattern).
- **No rendered-context persistence.** `DocumentVersion` only stores
  the SHA-256 hash. A future phase may add optional context persistence
  for truly reproducible regeneration.
- **`regenerate` endpoint doesn't re-build context from source data.**
  The D-1 endpoint only accepts an explicit `context_override`. Callers
  who want a "refresh with current data" should invoke the source
  generator (e.g. `generate_invoice_document`) which always rebuilds
  the context.
- ~~**3 non-migrated WeasyPrint call sites remain.**~~ Resolved in
  D-9 (April 19, 2026) — `pdf_generation_service.generate_template_preview_pdf`,
  `quote_service.generate_quote_pdf`, and `wilbert_utils.render_form_pdf`
  all route through `document_renderer` now. The transitional
  allowlist in `tests/test_documents_d2_lint.py` is empty; any
  new in-app WeasyPrint usage is a regression. Two new platform
  templates landed: `quote.standard` and `urn.wilbert_engraving_form`.
- **No cross-tenant document sharing.** D-6 adds the unified cross-tenant
  document fabric (today there are four mechanisms — statements,
  delivery confirmations, VaultItem sharing, raw cross-tenant order
  inserts).
- **No native signature capture inside Document.** DocuSign integration
  for disinterment release forms is production but lives outside the
  Documents layer; D-4/D-5 unifies these.

---

## Roadmap

| Phase | Delivers |
|---|---|
| **D-1 (this phase)** | Canonical model, renderer, 4 generators migrated, workflow hook, API |
| D-2 | DB-backed template registry, admin UI read surface, migrate the 3 inline-HTML generators + email templates |
| D-3 | Template editing, versioning, tenant overrides (mirrors Phase 3b for Intelligence) |
| D-4 | Native signature capture (replaces DocuSign for the disinterment case, extends to cremation auth, etc.) |
| D-5 | External submission implementations — EDRS, VA forms, insurance assignment (uses existing Playwright infra) |
| D-6 | Cross-tenant document fabric — unifies today's four mechanisms |
| D-7 | Delivery abstraction — email / portal / print, status tracking |
| D-8 | September demo polish |
| D-9 | Arc debt cleanup — last 3 WeasyPrint sites migrated, EmailService fallback removed, renderer paths unified |

---

## Anti-patterns to avoid

- **Don't instantiate `weasyprint.HTML(string=...).write_pdf()` outside
  `document_renderer.py`.** Everything should flow through the renderer
  so the pipeline stays centralized.
- **Don't create new Jinja Environments per service.** The renderer owns
  Jinja setup.
- **Don't bypass `Document` by stuffing PDF bytes somewhere else.** The
  whole point is one place to query every document the system produced.
- **Don't write to `documents.storage_key` directly.** Let the renderer
  manage it. It mirrors the current DocumentVersion for cheap list-page
  queries; a direct write breaks that invariant.
- **Don't populate only `entity_id` without `entity_type`.** The
  polymorphic pair needs both, or neither.

---

**Questions?** See `backend/docs/documents_audit.md` for the full audit
that led to this design, and `backend/docs/DEBT.md` for tracked
follow-ups.
