# Platform Debt Tracking

This document tracks known technical debt, architectural concerns, and
deferred improvements that don't rise to the level of active bugs (see
`BUGS.md`) but should be addressed eventually.

When a debt item is resolved, move the entry from **Active debt** to
**Resolved debt** with a date and a link to the fix.

---

## Active debt

### R-2.1 — flat slug array sub-composition (Option 3) vs row-based sub-compositions (Option 2)

**Discovered:** R-2.1 entity-card sub-section ship (2026-05-08).

**Current state:** Sub-section R-4 button composition uses a flat
`buttonSlugs: string[]` prop (Option 3 from
`/tmp/r2_1_subsection_scope.md` Section 8). Order = array index.
Layout treatment locked (always a row of buttons; no grouped rows,
no conditional rendering, no per-tenant separator authoring).

**The deferred path (Option 2):** row-based sub-compositions —
the actions sub-section accepts an authored composition record
that follows R-3.0/3.1's row-based DnD pattern, supporting grouped
buttons + conditional rendering + per-tenant layout flexibility.

**Why Option 3 chosen for R-2.1:** simplest substrate; existing
`array<componentReference>` schema supports it directly; no schema
work required. Substrate is in place + admins can author. **Avoids
premature abstraction** (canon §3.26.7.5) — no operator has yet
asked for "place buttons in a grid inside an entity card."

**Forward-only migration:** when a tenant builds something the
flat-array editor can't express (grouped action rows, conditional
button rendering based on entity state, separators, etc.), open
R-2.x as a separate scoped phase with its own canon-level
architectural call. Migration path:
1. Schema: `buttonSlugs: string[]` deprecates → new
   `actionsLayout: SubCompositionRecord | string[]` (string[] still
   accepted as the simple legacy shape; new SubCompositionRecord
   shape activates Option 2 when authored).
2. Service: per-section sub-composition resolution layer parallels
   R-3.0/3.1's per-row composition resolver.
3. Editor: actions sub-section's PropsTab gains a row-based DnD
   editor for the `actionsLayout` shape.
4. Existing flat-array authoring continues working unchanged —
   one-release coexistence then full migration.

**No action needed for R-2.1.** Flagged so any future R-2.x author
finds the canonical migration path documented.

### R-2.1.x — selectedComponentName backwards-compat shim removal

**Discovered:** R-2.1 entity-card sub-section ship (2026-05-08).

**Current state:** EditModeContext exposes both:
- `selection: RuntimeSelection` (R-2.1 NEW — discriminated union)
- `selectedComponentName: string | null` (R-2.1 derived shim)

The shim derives via `selection.kind === "none" ? null :
selection.componentName` so pre-R-2.1 callers see the same string.

**Callers of `selectedComponentName` to audit before removing the shim:**
- `InspectorPanel.tsx` — header + tab body lookup
- `SelectionOverlay.tsx` — `[data-component-name="${name}"]` query
  for the brass selection border tracking
- Any runtime-writers that may read it
- Any test fixtures asserting on it

**Migration path (R-2.1.x):**
1. Audit every reader (grep `selectedComponentName`)
2. Migrate each to read `selection` + branch on kind
3. Remove the shim from EditModeState + makeStub + the value memo
4. tsc verification + vitest regression

**No action needed for R-2.1.** Shim is essential during the
transition window.

### Journal Entry VaultItem coverage — deferred after V-1f+g

**Discovered:** V-1f+g investigation (April 20, 2026).

**Current state:** JournalEntry writes to the GL but does NOT write
a VaultItem anywhere in the codebase (verified: `create_vault_item`
callers under `app/services/` never touch `JournalEntry`). The V-1f+g
audit identified this as **Case A** — nothing to fix, but also
nothing surfacing JE activity in the Vault timeline / overview
widgets. A lint-style regression test
(`test_je_posts_do_not_write_vault_item_today` in
`tests/test_vault_v1fg_vault_item_hygiene.py`) asserts this assumption
so a future slip is loud.

**Eventual fix:** Decide whether JEs should surface in Vault activity.
If yes, the correct `item_type` is probably `"document"` with
`document_type="journal_entry"` (JEs are historical artifacts, not
timeline events — using `item_type="event"` would pollute the V-2
Calendar). Wire the dual-write in whatever service posts JEs (likely
`journal_entry_service.post_entry` when it lands) and delete the lint
guard in favor of a real behavioral test.

**Impact:** zero right now — JEs are a power-user / accountant
surface and the Vault Overview widgets don't promise JE visibility.
Grows to low-medium when V-2 Calendar ships — at that point the
product decision "should accounting appear on the calendar?" forces
the question.

---

### Existing Quotes backfill — not done in V-1f+g

**Discovered:** V-1f+g (April 20, 2026).

**Current state:** V-1f+g ships forward-only VaultItem dual-write for
Quote. New Quotes get a VaultItem; existing Quotes in the DB do not.
The `_update_quote_vault_item` helper logs + noops when it can't find
a VaultItem for a Quote being updated, so pre-V-1f quotes don't
crash when their status changes — they just don't appear in Vault
activity.

**Eventual fix:** one-off backfill script that walks `quotes` and
creates a VaultItem for each row that doesn't already have one
(dedupe by `source_entity_id = quote.id`). Probably a management
command rather than a migration (migrations should be structural;
bulk data population is better as an idempotent script).

**Impact:** small — Sunnycrest dev DB has a handful of test quotes;
no production tenants have quotes yet. Skip unless customer asks
"where are my old quotes in Vault activity?"

---

### Statement-template editor deferred from V-1e

**Discovered:** V-1e (April 20, 2026).

**Current state:** The Statement Templates sub-tab at
`/vault/accounting/statements` is a read-only split view —
platform defaults on one side, tenant customizations on the other.
There's no editor: no fork-to-tenant action, no inline edit, no
template designer. Admins who need to customize a statement template
have to do it by direct SQL or through whatever private surface the
statement-generation service currently exposes.

**Eventual fix:** Ship a full template editor component — similar
to the DocumentTemplate editor built in D-3 (draft/activate/rollback
+ audit trail). Probably adds two endpoints to
`vault_accounting.py`: `POST /statement-templates/{id}/fork`
(create tenant-scoped override) and `PATCH /statement-templates/{id}`
(edit tenant-owned template). The existing `StatementTemplate` model
already supports the platform-vs-tenant scope via nullable
`tenant_id`, so no schema changes needed.

**Impact:** low right now — tenant customizations are rare and can
be handled via direct DB access by engineering. Grows to medium if
customer demand for statement branding picks up.

---

### Cron-editor for agent schedules deferred from V-1e

**Discovered:** V-1e (April 20, 2026).

**Current state:** The Agent Schedules sub-tab at
`/vault/accounting/agents` lets admins toggle schedules on/off but
does NOT let them edit the cron expression, `run_day_of_month`, or
`run_hour` inline. Editing those fields requires the existing
`POST /agents/schedules` upsert endpoint, which has no UI surface
yet.

**Eventual fix:** Add an edit modal per schedule row — cron
expression input with human-readable preview ("Every day at 3am ET"),
day-of-month + hour pickers, timezone dropdown, notify-emails list,
auto-approve toggle. Call the existing upsert endpoint on save.

**Impact:** low — most accounting agents have reasonable defaults
from the scheduler seed, and power users can still edit via API.
Medium when tenants want to shift a monthly close run off the default
3rd-of-month.

---

### V-1e widget seed coordination across fresh deploys

**Discovered:** V-1e (April 20, 2026).

**Current state:** Three new widget definitions
(`vault_pending_period_close`, `vault_gl_classification_review`,
`vault_agent_recent_activity`) were added to
`widget_registry.WIDGET_DEFINITIONS`. The seed runs on app startup
via `seed_widget_definitions(db)` in `app/main.py`. But test
environments that don't trigger full startup (e.g. direct
`TestClient(app)` usage) start with an un-seeded DB — the V-1e
tests worked around this by running a one-off seed before the test
session. On a fresh production deploy the startup path handles it.

**Eventual fix:** Consider moving widget seeding to a migration
step, or an explicit `ensure_seeded()` call on the first
`/vault/overview/widgets` request. Either makes the seed a first-
class part of the data model rather than a startup side-effect.

**Impact:** low in practice (prod auto-seeds; tests can seed
explicitly), but it's a smell that tests and production take
different bootstrap paths.

---

### Vault V-1a/c/d redirect scaffolding — remove after one release

**Discovered:** V-1a (April 20, 2026), extended by V-1c + V-1d
(April 20, 2026).

**Current state:** Old paths redirect to `/vault/*` via `<Navigate>`
and `RedirectPreserveParam`:
- V-1a: 16 entries under `/admin/documents/*` + `/admin/intelligence/*`.
- V-1c: 9 entries under `/crm/*`.
- V-1d: 1 entry at `/notifications` → `/vault/notifications`.

One-release grace period for bookmarks, documentation links, external
references. Notifications in particular has a long tail of external
links — any email template that hard-coded `/notifications?` as a deep
link, plus every browser bookmark users have built up. Keep the
redirect until at least one release has shipped after V-1d.

**Eventual fix:** Delete the ~26 redirect route entries in `App.tsx`
and the `RedirectPreserveParam` helper (only if no other V-1 phase
reuses it). Verify no internal link reintroduced an old path via
periodic grep on `/admin/documents`, `/admin/intelligence`, `/crm/`,
`/notifications` outside `App.tsx`.

**Threshold for action:** after V-1h documentation lands (which
exposes the new paths externally) + one release of user-facing grace.

---

### Notification category vocabulary — no central registry

**Discovered:** V-1d (April 20, 2026).

**Current state:** The `Notification.category` string is set at
each source site with a different literal string: `"safety_alert"`
(r29 migration + existing usage), `"share_granted"` (V-1d),
`"delivery_failed"` (V-1d), `"signature_requested"` (V-1d),
`"compliance_expiry"` (V-1d), `"account_at_risk"` (V-1d), plus the
pre-V-1d categories `"employee"`, `"order"`, `"invoice"`, and
others scattered through the code.

Frontend filtering, grouping, and per-category display rules (icon,
color, group header) are ad-hoc — NotificationsWidget colors by
`type` not `category`; the full page has no category filter.

**Eventual fix:** Add `app/services/notifications/categories.py`
with a typed enum or frozen dict mapping `category_key → {display_name,
icon, color, default_severity, group}`, migrate every call site to
reference the registry, and surface category-based filtering + visual
grouping on the Notifications page. Likely pairs with the
notification-preferences work below — both need the same registry.

**Impact:** low right now (categories work for filtering at the API
level), but as V-1d's 5 new sources start producing real volume the
lack of a single vocabulary will make UX polish (grouping,
per-category mute, digest emails) harder.

---

### Notification preferences — no per-category opt-out / digest

**Discovered:** V-1d (April 20, 2026).

**Current state:** Every notification fires in real time for every
eligible recipient. An admin in a manufacturing tenant receives
every compliance_expiry, delivery_failed, and share_granted the
moment the source event happens. No quiet-hours gate, no daily
digest, no per-category mute, no per-channel routing (email vs
in-app vs SMS). Noisy categories like compliance_expiry (weekly)
and delivery_failed (whenever Resend hiccups) can be felt as
spammy.

Rate-limiting is implicit only where it's easy — compliance_expiry
dedupes by `source_reference_id` so the same overdue item doesn't
re-fire on re-runs of `sync_compliance_expiries`. Everything else
has no rate limit.

**Eventual fix:** Ship a `user_notification_preferences` table keyed
on (user_id, category) with `enabled` + `delivery_mode` (realtime /
daily_digest / never) + `channel` (in_app / email / both). Gate
fan-out helpers on the preference check; collect daily_digest rows
for a scheduler job. Fan-out helpers should also expose a rate-limit
hint (e.g. "don't re-fire delivery_failed for same recipient within
5 minutes") for noisy categories.

**Impact:** low while V-1d sources are fresh, but will grow as
workflows + AI executions start driving secondary notification
cascades.

---

### CRM parallel contact models unification (post V-1c lift-and-shift)

**Discovered:** Vault audit § 3.2 + 3.6 (April 19, 2026); deferred
from V-1c (April 20, 2026).

**Current state:** The CRM `Contact` model (linked to
`CompanyEntity`) is NOT unified with three parallel contact tables:
- `CustomerContact` (`customer_contact.py`) — keyed on `customer_id`
- `VendorContact` (`vendor_contact.py`) — keyed on `vendor_id`
- `FHCaseContact` (`fh_case_contact.py`) — keyed on `fh_case_id`,
  carries portal-invitation fields (`portal_invite_sent_at`,
  `portal_last_login_at`) that no other contact model has

Same physical person can be four separate rows across these tables.
V-1c's audit explicitly scoped this out — lift-and-shift moves CRM
under Vault but does NOT reconcile contacts.

**Eventual fix:** This is Option B from the Vault audit (§7.4 CRM
absorption posture): make `CompanyEntity` a first-class VaultItem
(`item_type="account"`), make `Contact` the canonical contact table,
migrate `CustomerContact` / `VendorContact` / `FHCaseContact` rows to
`Contact` + a tag/role column, update all call sites. Audit
estimated 6-8 weeks. Portal-invitation fields need preservation
(probably via a `portal_settings` JSONB on the unified Contact or a
separate `ContactPortalAccess` table).

**Threshold for action:** after V-1h Vault documentation ships and
the Vault Hub has stabilized for at least one release. Low urgency —
duplicate contact rows are a UX annoyance, not a data-integrity
issue. Tenants can work around via the unified company detail page.

---

### Deprecated AccountingConnection model + OAuth code removal

**Discovered:** Per V-1a build context — QBO/Sage accounting
integration was deprecated when the native accounting engine took
over. `AccountingConnection` model + OAuth token encryption + sync
config + `accountant_email` invitation flow + related routes
(`accounting_connection.py`) still exist but are dormant.

**Current state:** Code compiles + database columns remain. No new
production integrations use this path. V-1e (April 20, 2026) added
the replacement admin surface under `/vault/accounting/*`, so the
path to removal is now unblocked.

**Eventual fix:** separate focused build — migration dropping the
unused columns, route file deletion, frontend `/settings/integrations/
accounting` cleanup, removal from `admin/accounting.tsx`. V-1e's
classification queue + COA templates + period admin cover every
surface the old integration UI provided (minus the QBO OAuth / Sage
CSV connection setup itself, which is the thing going away).

**Threshold for action:** next housekeeping pass — no product
feature blocks this.

---

### Accountant invitations surface not rebuilt in V-1e

**Discovered:** V-1e (April 20, 2026).

**Current state:** The old `accounting_connection.py` flow had an
"invite your accountant" feature — send a magic-link email granting
limited read access to QBO-synced data. With QBO/Sage integration
deprecated and the native accounting engine now owning the data, the
invitation flow no longer has a coherent target. V-1e's scope
explicitly excluded rebuilding it.

**Eventual fix:** If accountant collaboration becomes a real customer
ask, rebuild as a first-class feature — probably a tenant-scoped
read-only role + a token-based login landing page pointing at the
Vault hub's financials view. Would slot in alongside V-1e as a 7th
sub-tab or under Platform admin user settings.

**Impact:** zero customer reports of missing the feature to date.
Revisit only if demand materializes.

---

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

## Resolved debt

### ✅ Audit observation 4: Quote doesn't write VaultItem (2026-04-20)

**Originally discovered:** Bridgeable Vault audit (`backend/docs/vault_audit.md`, observation 4).

**Resolved in:** Phase V-1f+g (April 20, 2026).

`quote_service.create_quote` now dual-writes a VaultItem
(`item_type="quote"`, `source_entity_id=quote.id`); metadata carries
quote_number + customer_name + total + status + product_line so the
overview-widget and future timeline views have everything they need.
`convert_quote_to_order` + `update_quote_status` update the same row
— on conversion, VaultItem.status flips to "completed" with a
completed_at stamp, and metadata gets `converted_to_order_id` for
back-reference. Backfill of existing Quotes is forward-only +
tracked in DEBT.md.

---

### ✅ Delivery polymorphic attribution beyond document-only (2026-04-20)

**Originally discovered:** Delivery abstraction audit at D-7 shipdown
(April 2026).

**Resolved in:** Phase V-1f+g (April 20, 2026).

`document_deliveries.caller_vault_item_id` column added via migration
`r30_delivery_caller_vault_item`. `DeliveryService.SendParams` gains
the matching optional kwarg — sends triggered from a non-Document
surface (quote, compliance reminder, account-at-risk notification)
can now attribute to the source VaultItem instead of abusing the
existing `document_id` slot. Partial index keeps index size small
for the common document-attached path. Additive + nullable — zero
existing callers affected.

---

### ✅ Nav clutter: Documents + Intelligence admin entries buried in Settings → Platform (2026-04-20)

**Originally discovered:** Bridgeable Vault audit (`backend/docs/vault_audit.md`, §1).

**Resolved in:** Phase V-1a (April 20, 2026).

Documents (5 entries: Templates, Document Log, Inbox, Delivery Log,
Signing) + Intelligence (2 entries: Prompts, Experiments) moved out of
the `Settings → Platform` subgroup into a new top-level `Bridgeable
Vault` hub (`/vault/*`). Settings → Platform shrank to its original
intent — tenant-management (Billing, Extensions, Onboarding).

Foundation for V-1b-V-1h to add CRM, Notifications, Accounting admin
under the same hub.

---

### ✅ Three non-migrated WeasyPrint call sites — all migrated (2026-04-19)

**Originally discovered:** Documents Phase D-2 (April 2026).

**Resolved in:** Phase D-9 (April 19, 2026).

- `pdf_generation_service.generate_template_preview_pdf` now routes
  through `document_renderer.render_pdf_bytes` using the managed
  `invoice.{variant}` registry keys. Admin template previews reflect
  the same registry body the live invoice path renders.
- `quote_service.generate_quote_pdf` now wraps a new
  `generate_quote_document` that calls `document_renderer.render()`
  with `template_key="quote.standard"` and creates a canonical
  Document linked via `entity_type="quote"`. The legacy bytes API
  still works (fetches from R2 after the Document lands).
- `wilbert_utils.render_form_pdf` now routes through
  `document_renderer.render_pdf_bytes` with
  `template_key="urn.wilbert_engraving_form"`. Preserves the legacy
  HTML-fallback contract.

Both new templates were seeded by `r28_d9_quote_wilbert_templates`.
The ruff TID251 permanent allowlist collapsed to
`document_renderer.py` + `app/main.py` (diagnostic import). The
transitional allowlist is empty; `test_transitional_allowlist_is_empty`
enforces that invariant.

---

### ✅ EmailService fallback company_id safety net — removed (2026-04-19)

**Originally discovered:** Documents Phase D-7 (April 2026).

**Resolved in:** Phase D-9 (April 19, 2026).

`EmailService._fallback_company_id(db)` picked the first active
Company when a caller didn't thread `company_id`, silently attributing
the delivery to an arbitrary tenant. D-9 replaced it with
`_require_company_id(company_id)` which raises ValueError if missing.

All 10 callers now thread `company_id` explicitly:

1. `api/routes/sales.py` — invoice email (threads `current_user.company_id`)
2. `api/routes/agents.py` — collections email
3. `api/routes/accounting_connection.py` — accountant invitation
4. `services/agents/approval_gate.py` — approval review email (threads `tenant_id`)
5. `services/statement_service.py` — statement email (threads `tenant_id`)
6. `services/draft_invoice_service.py` — invoice send (threads `inv.company_id`)
7. `services/social_service_certificate_service.py` — SSC delivery email
8. `services/urn_engraving_service.py` (x2) — Wilbert submission + FH approval emails
9. `services/platform_email_service.py::send_tenant_email` — threads `tenant_id`
   (previously a silent bug — the method had `tenant_id` but didn't pass it)
10. `services/legacy_email_service.py` — already required; no change needed

---

### ✅ DocumentRenderer had two rendering code paths — unified (2026-04-19)

**Originally discovered:** Phase D-3 (April 2026) — the test-render
endpoint duplicated the Jinja + WeasyPrint + R2 + Document-insert
pipeline rather than delegating.

**Resolved in:** Phase D-9 (April 19, 2026).

`document_renderer.render()` now accepts either `template_key`
(current-active lookup) OR `template_version_id` (specific-version
lookup). The test-render endpoint is a thin adapter that calls
`render(template_version_id=version.id, is_test_render=True)` and
shapes the response. Single code path for all Document generation.

New helper: `template_loader.load_by_version_id()`.

---

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
