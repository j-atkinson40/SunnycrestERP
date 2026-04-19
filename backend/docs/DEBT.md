# Platform Debt Tracking

This document tracks known technical debt, architectural concerns, and
deferred improvements that don't rise to the level of active bugs (see
`BUGS.md`) but should be addressed eventually.

When a debt item is resolved, move the entry from **Active debt** to
**Resolved debt** with a date and a link to the fix.

---

## Active debt

### Intelligence stats endpoints perform live aggregation

**Discovered:** Phase 3a (April 2026)

**Current state:** `GET /intelligence/stats/prompt/{id}` and
`GET /intelligence/stats/overall` compute 30-day aggregates via live SQL
queries on `intelligence_executions`. With 300 seed executions, this is
fast. At production scale (projected: tens of thousands to millions of
executions per year), these queries will become slow — especially the
daily-breakdown group-by-date query and the per-prompt error-rate
aggregate that runs once per prompt on the list endpoint.

**Eventual fix:** Materialized daily rollup table
`intelligence_execution_daily_rollup` with columns:

- `date` (DATE, PK)
- `prompt_id` (FK, PK)
- `execution_count`
- `success_count`
- `error_count`
- `total_input_tokens`
- `total_output_tokens`
- `total_cost_usd`
- `avg_latency_ms`
- `p95_latency_ms` (optional — harder without percentile-cont)

Nightly job populates the table (or rolls forward from the previous day's
high-water mark). Stats endpoints query the rollup table instead of the
live executions table. Live table still used for queries scoped to
< 24 hours (today's partial-day window).

**Threshold for action:** when a single stats endpoint query exceeds
500ms on production data.

---

### Local-dev E2E harness

**Discovered:** Phase 3c (April 2026)

**Current state:** `frontend/tests/e2e/` (including the new
`intelligence/` folder) targets the staging deployment
(`determined-renewal-staging.up.railway.app`). There is no local-dev
Playwright harness — running tests requires staging to be up and
deployed with the expected migration head. This delays verification
during Phase 3c/3d builds where staging may be behind `main`.

**Eventual fix:** Add a `webServer` block to `playwright.config.ts` that
spins up backend + frontend locally (uvicorn + vite) for a local-dev
project. Seed an ephemeral SQLite/Postgres at test start. Either a
separate project in the existing config (e.g. `chromium-local`) or a
separate `playwright.local.config.ts` invoked via a new npm script.

**Threshold for action:** when a Phase 3d-or-later build requires E2E
verification before staging deploy is viable.

---

### AICommandBar frontend refactor

Tracked in `BUGS.md` → "Out-of-scope for cleanup". The component uses
the deprecated `/ai/prompt` endpoint with arbitrary `systemPrompt` prop,
defeating managed-prompt A/B testing and per-tenant overrides. Migration
to a dedicated `catalog.product_search` managed prompt + endpoint is
pending. Sunset date 2027-04-18.

---

### Legacy document models coexist with canonical Document

**Discovered:** Documents Phase D-1 (April 2026)
**Partially resolved:** Documents Phase D-2 (April 2026) — see "Resolved
debt" below for the email template + 3 inline HTML generators + safety
program PDF path migrations.

**Current state:** The canonical `app.models.canonical_document.Document`
and the legacy `app.models.document.Document` (now backed by table
`documents_legacy`) live side by side. The legacy model + table, plus
related models (`VaultDocument`, `FHDocument`, `KBDocument`,
`TenantTrainingDoc`, `DeliveryMedia`, `ProgramLegacyPrint`,
`OrderPersonalizationPhoto`, `SocialServiceCertificate.pdf_r2_key`,
`StatementRunItem.pdf_path` + `CustomerStatement.statement_pdf_url`)
all still exist and accept writes from callers that haven't migrated.

**D-2 update:** `SafetyProgramGeneration.pdf_document_id` now points at
the canonical `documents.id` AND `generate_pdf()` actually inserts
canonical rows (it was creating legacy rows pre-D-2, which was latently
broken — the FK pointed canonical but the writer pointed legacy).

**Remaining eventual fix (post-D-2):**
1. `SocialServiceCertificate.pdf_r2_key` → migrate generator to write
   canonical Document + link via a new `pdf_document_id` FK
2. `CustomerStatement.statement_pdf_url` — now mirrors the canonical
   Document's storage_key; consider adding a proper FK
3. KB / VaultDocument / VaultItem / FHDocument / DeliveryMedia /
   ProgramLegacyPrint — these are all specialized enough that they may
   stay as-is. Revisit per-model if production usage signals a need.

**Threshold for action:** when a specific legacy model actively blocks
a planned feature. Otherwise coexistence is fine.

---

### DocuSign code pending deletion after legacy envelopes resolve

**Discovered:** Phase D-4 (April 2026). **Partially resolved:** Phase
D-5 (April 2026).

**Current state (post-D-5):** Native signing fully handles disinterment.
`disinterment_service.send_for_signatures` creates native envelopes;
DocuSign originates zero new envelopes. `docusign_service.py` +
`docusign_webhook.py` stay alive only to service any pre-cutover
DocuSign envelopes that were in flight when D-5 shipped.
`create_envelope` emits a `DeprecationWarning` if called.

**Eventual fix:** delete `docusign_service.py`, `docusign_webhook.py`,
the `/api/v1/docusign/webhook` route registration, and the DocuSign
OAuth config once this query returns 0:

```sql
SELECT COUNT(*) FROM disinterment_cases
WHERE docusign_envelope_id IS NOT NULL
  AND status IN ('signatures_pending', 'signatures_sent');
```

Then also drop `DisintermentCase.sig_*` columns (replaced by envelope
party state).

**Threshold for action:** when the count above is zero in production
for 30 consecutive days (belt-and-suspenders window for any stuck
DocuSign callbacks to resolve).

---

### Delivery retry is inline; background queue is future work

**Discovered:** Phase D-7 (April 2026)

**Current state:** `DeliveryService.send()` retries retryable errors
inline within the caller's request. A failing upstream provider with
`max_retries=3` blocks the request for up to 3 retry windows (tens
of seconds for timeouts). No persistent queue across restarts; no
exponential backoff.

This is acceptable for Bridgeable's current delivery volume (hundreds
of emails/day). It breaks down when:
- A request hitting the hot path (envelope send during signing) has to
  wait 30s on flaky Resend.
- A tenant sends a batch of 100 collections emails and any provider
  flakiness cascades into latency.
- The worker restarts mid-retry — the retry state is lost.

**Eventual fix:** Redis-backed queue with worker polling. Deliveries
with `status=pending` and `retry_count < max_retries` get picked up.
Exponential backoff on retries. Dead-letter queue for exhausted
rows. Request latency drops to the single-attempt case.

**Threshold for action:** when average delivery latency (p95) exceeds
2× the provider's single-attempt latency, OR when admins report
that statement batches are slow.

---

### Resend webhook callbacks not wired

**Discovered:** Phase D-7 (April 2026)

**Current state:** A delivery transitions to `status=sent` when the
provider accepts the message. Resend then sends webhook callbacks
(`delivery`, `bounce`, `complaint`) that would flip the status to
`delivered` / `bounced`. We don't subscribe to those webhooks in D-7,
so deliveries stay at `sent` indefinitely (never showing `delivered`
in the UI even when the recipient clearly got the email).

Practical impact: minimal. Admins see `sent` and trust it. Bounces
surface as Resend errors on the NEXT send to the same address.

**Eventual fix:** subscribe to Resend webhooks, route to a new
`/api/v1/webhooks/resend` endpoint, map events onto delivery statuses
via `provider_message_id`. Also a good moment to handle the `opened` /
`clicked` events if we want engagement metrics. D-8 or later.

**Threshold for action:** when the product UX wants verified-delivered
status for compliance purposes (e.g. "certificate of delivery for this
government submission").

---

### Bulk send not implemented

**Discovered:** Phase D-7 (April 2026)

**Current state:** `DeliveryService.send()` is single-send. A statement
batch emailing 200 customers calls it 200 times in a loop, producing
200 delivery rows. That's correct but inefficient on the wire —
provider APIs (Resend, Twilio) often support batch endpoints that
reduce request count.

**Eventual fix:** add `DeliveryChannel.send_batch([ChannelSendRequest])`
as an optional method. EmailChannel implements it via Resend batch
endpoint; SMS stub raises NotImplemented. `DeliveryService.send_batch()`
creates one delivery row per recipient but dispatches via the batch
channel method when available.

**Threshold for action:** when statement-run batches start taking
minutes instead of seconds, or when Resend bills hit rate-limit
windows with monthly billing.

---

### Scheduled send column exists but unused

**Discovered:** Phase D-7 (April 2026)

**Current state:** `document_deliveries.scheduled_for` is present on
the schema but no scheduler reads it. All sends are immediate.

**Eventual fix:** a cron-like worker that polls for
`status=pending AND scheduled_for <= NOW()` and dispatches. Useful for
"send the Monday statement at 9am" patterns. Could reuse the retry
queue infrastructure above.

**Threshold for action:** when a feature (timed statements, delayed
onboarding follow-ups) concretely needs scheduled sends.

---

### Pre-D-6 cross-tenant data not backfilled into DocumentShare

**Discovered:** Phase D-6 (April 2026)

**Current state:** D-6 migrated the statement / delivery-confirmation /
legacy-vault-print generators to create `DocumentShare` rows at
creation time. Pre-D-6 cross-tenant data lives in ad-hoc structures:
`ReceivedStatement` rows (for statements already delivered),
`VaultItem.shared_with_company_ids` (for delivery media),
`FuneralCaseNote` references (for legacy vault prints). These pre-D-6
records are NOT backfilled into `document_shares`.

Impact: the admin inbox only shows documents shared since D-6
deployed. Older cross-tenant records remain in their original tables
but are invisible to the unified inbox.

**Eventual fix:** Write a backfill script
(`backend/scripts/backfill_d6_shares.py`) that walks each pre-D-6
cross-tenant surface and creates corresponding `DocumentShare` rows
(source_module = "d6_backfill"). Run once per environment after
deploying D-6. Idempotent via `ensure_share`.

**Threshold for action:** before any customer-visible inbox surface
ships (D-6 tenant-user inbox, or when admins start asking "where are
my older shared statements?").

---

### Training certificates / COIs / licensee transfer notifications lack generators

**Discovered:** Phase D-6 (April 2026)

**Current state:** The D-6 cross-tenant sharing infrastructure
(`document_shares` + `document_sharing_service` + `visible_to()`) is
ready for these document types, but their generators don't exist yet.
The audit that preceded D-6 identified them as conceptual cross-tenant
flows without backing platform implementations.

**Eventual fix:** As each generator ships:
1. Produce canonical `Document` via `document_renderer.render(...)`.
2. Call `document_sharing_service.ensure_share(...)` with the
   appropriate target tenant (employee's FH, counterparty on the COI,
   destination manufacturer on a licensee transfer).

No further infrastructure work — D-6 is complete for these types.

**Threshold for action:** when each generator gets scheduled as its
own product milestone.

---

### Cremation authorization still uses manual sign-off fields

**Discovered:** Phase D-5 (April 2026)

**Current state:** Unlike disinterment, cremation authorization flows
still rely on direct-edit status fields (no envelope, no audit trail).
D-5 explicitly scoped migration to disinterment only — cremation is
deferred to a separate focused build so the flow can be redesigned
alongside product-side changes to the funeral-home vertical.

**Eventual fix:** create cremation release-form template with
appropriate anchor strings, wire the cremation-authorization route to
`signature_service.create_envelope` following the disinterment pattern,
backfill any in-flight paper authorizations.

**Threshold for action:** funeral-home vertical milestone where
cremation authorization workflow is under active development.

---

### SMS verification stubbed, awaiting native SMS work

**Discovered:** Phase D-4 (April 2026)

**Current state:** `SignatureParty.phone` accepts a phone number but
D-4 does nothing with it. Email is the sole invite + auth channel. No
SMS verification of consent, no SMS backup for signer authentication.

**Eventual fix:** Native SMS (via Twilio or similar) is a cross-cutting
platform initiative — not specific to signing. Once SMS infrastructure
exists, `notification_service` grows an `send_invite_sms` counterpart
and the public signer flow can surface a phone-verification step.

**Threshold for action:** whenever platform-wide SMS ships.

---

### Notarization deferred indefinitely

**Discovered:** Phase D-4 (April 2026)

**Current state:** No notarization (remote online notarization / RON)
features. US ESIGN + UETA cover electronic signatures for most
routine business documents; RON is a separate regulatory regime
(state-by-state rules, identity verification requirements, notary
recordkeeping). The burial-vault and funeral-home use case doesn't
need RON for routine disinterment / authorization.

**Eventual fix:** When a customer requires RON (e.g. specific state
statutes for certain types of trust documents), integrate a third-party
RON provider (Notarize, NotaryCam, Proof). Not roadmapped.

**Threshold for action:** first customer requiring it.

---

### ~~Signing PDF cover page vs. inline anchor overlay~~ (Resolved in D-5)

**Originally discovered:** Phase D-4. **Resolved:** Phase D-5 (April
2026). `signature_renderer.apply_signatures_as_new_version` now uses
PyMuPDF-based anchor overlay — signatures are placed directly on the
source document at `/sig_*/` anchor positions with optional per-field
x/y offsets. Cover-page approach retained as fallback if overlay fails
entirely (R2 miss, PDF corruption, all anchors unresolvable).

---

### Client-side template preview uses simplified Jinja substitution

**Discovered:** Documents Phase D-3 (April 2026)

**Current state:** The admin template editor's Preview modal renders
in-browser with a minimal substitution function that handles
`{{ var }}` and `{{ var.path }}` references. It does NOT support
`{% if %}` / `{% for %}` control flow, filters, or macros.

Admins who want full-fidelity preview use the Test Render modal, which
calls the backend and runs real Jinja2.

**Eventual fix:** ship a true Jinja2 interpreter in the browser (via
a small WASM build or a JS-side reimplementation). Or: move preview
to a dedicated lightweight backend endpoint that renders HTML without
persisting. Not urgent — Test Render is one click away.

**Threshold for action:** if admins start reporting that Preview
gives misleading results for templates that use control flow.

---

### Email test sending deferred until D-7

**Discovered:** Documents Phase D-3 (April 2026)

**Current state:** Test Render produces HTML/PDF output visible in the
admin UI. It does NOT send test emails. There's no "send a sample to
myself" button because the delivery abstraction (Resend vs SMTP, per-
tenant sender config, attachment handling) is still direct — the
email_service.send_email() path is production-only.

**Eventual fix:** Phase D-7 adds the delivery abstraction. At that
point, Test Render can offer a "send a test to {admin_email}" option
that routes through the same path production emails take, with a
`delivery_mode=test` flag that prepends `[TEST]` and logs differently.

**Threshold for action:** D-7.

---

### Template registry file system still present

**Discovered:** Documents Phase D-2 (April 2026)

**Current state:** Phase D-2 moved PDF + email template content into the
`document_templates` + `document_template_versions` DB tables. The
source-of-truth is now the DB. But the original files under
`backend/app/templates/invoices/`, `statements/`, `price_lists/`,
`disinterment/` remain on disk — the `_template_seeds.py` helper reads
them at migration time.

**Eventual fix:** Once D-3 ships the editing UI and admins are
comfortable editing in-DB, delete the source files. The only risk is a
re-seed after a schema wipe loses the template content — but a re-seed
should be sourced from the DB backup, not from the files, by that point.

**Threshold for action:** after D-3 (template editing) ships and a few
weeks pass without anyone asking about the file copies.

---

### Three non-migrated WeasyPrint call sites

**Discovered:** Documents Phase D-2 (April 2026)

**Current state:** The ruff/pytest lint rule forbids `weasyprint`
imports outside `app/services/documents/`. Three files are on the
`TRANSITIONAL_ALLOWLIST` (see `tests/test_documents_d2_lint.py`):

- `app/services/pdf_generation_service.py::generate_template_preview_pdf`
  — admin template-preview tool used by the Price-List-style template
  builder. Not a production output path. Needs `render_pdf_bytes` wiring.
- `app/services/quote_service.py::generate_quote_pdf` — standalone
  500-line inline HTML quote generator. Needs a new `quote.default`
  platform template + seed migration.
- `app/services/wilbert_utils.py` — Wilbert urn engraving form PDF.
  Needs a `urn.wilbert_engraving_form` template_key.

**Eventual fix:** Migrate each to route through `document_renderer`
using a managed template. The preview tool is the smallest; quotes
and Wilbert form each require a seed migration adding a new
platform template row.

**Threshold for action:** before tenant template-editing UI (D-3)
ships — so admins discovering they can override these templates isn't
surprising.

---

## Resolved debt

### ✅ Frontend unit test framework — vitest installed (2026-04-19)

**Originally discovered:** Phase 3a (April 2026). Frontend had no test
framework — `tsc` + manual testing only.

**Resolved in:** Phase 3d follow-ups (April 19, 2026). Added vitest +
@testing-library/react + @testing-library/jest-dom + jsdom.

- `frontend/vite.config.ts` — test block (jsdom env, setupFiles)
- `frontend/src/test/setup.ts` — jest-dom matchers + cleanup hook
- `frontend/tsconfig.node.json` — vitest types
- `frontend/package.json` — `npm test`, `npm run test:watch`,
  `npm run test:coverage` scripts
- First test suites (59 tests, ~1s runtime):
  - `components/intelligence/formatting.test.ts` (25 tests — pure functions)
  - `components/intelligence/VisionContentBlock.test.tsx` (14 tests —
    the JSON-parse fallback that DEBT.md originally flagged as silent-
    bug-prone)
  - `components/intelligence/DiffView.test.tsx` (9 tests — field-level
    diff for activation/rollback dialogs)
  - `components/intelligence/VariablesEditor.test.ts` (12 tests —
    `renderTemplatePreview` client-side template substitution)

Patterns established — future admin UI additions (especially Phase 3b's
editing flows and Phase 3c's experiments UI) can write component tests
without bootstrapping.
