# Feature Sessions — build log

Chronological log of significant feature builds. Each entry is
written at the end of a build and NOT updated afterward — history
first. For the current platform state, see `CLAUDE.md`.

---

## Aesthetic Arc Session 1 — Token Foundation

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (unchanged — frontend-only).
**Arc:** Aesthetic Arc — Session 1 of 6. See `AESTHETIC_ARC.md`.
**Tests passing:** no new tests this session; existing 308 backend (Phase 1–8c) + 165 frontend vitest all green. `tsc -b` clean, `npm run build` clean.

### What shipped — token foundation + mode switching + Plex fonts

Aesthetic Arc Session 1 is pure infrastructure. It makes `DESIGN_LANGUAGE.md` tokens available throughout the platform without refreshing any existing component's appearance (except the one-off accepted status-color hex→oklch drift). Subsequent sessions (2–6) consume these tokens.

**New files (5):**
- `frontend/src/styles/tokens.css` — all DESIGN_LANGUAGE Section 9 tokens as CSS custom properties. `:root` for light mode defaults; `[data-mode="dark"]` for dark overrides. 57 color tokens (surfaces, content, borders, shadows, accent-brass variants, status variants), 3 elevation-shadow compositions (with automatic dark-mode top-edge highlight), 3 font-family tokens (Plex), 10-entry type scale, 2 radius additions (`--radius-base` + `--radius-full`), 5 durations, 2 easings, 5 max-widths.
- `frontend/src/styles/fonts.css` — `@import "@fontsource-variable/ibm-plex-sans/standard.css"` (variable 100-700) + `standard-italic.css` + `@fontsource/ibm-plex-serif/500.css` + `@fontsource/ibm-plex-mono/400.css`. Self-hosted; no Google CDN.
- `frontend/src/styles/base.css` — `prefers-reduced-motion: reduce` collapse, dark-mode font smoothing, `.focus-ring-brass` utility class, 5 `@utility duration-*` declarations (Tailwind v4 needs these explicit since `--duration-*` isn't an auto-utility namespace).
- `frontend/src/styles/globals.css` — bundles the above three. Imported by `index.css`.
- `frontend/src/lib/theme-mode.ts` — runtime API (`getMode`, `setMode`, `toggleMode`, `clearMode`) + `useThemeMode()` React hook with custom-event dispatch and system `prefers-color-scheme` subscription.

**Modified files (2):**
- `frontend/src/index.css` — imports `./styles/globals.css`, extends `@custom-variant dark` to match both `.dark` class (legacy noop) AND `[data-mode="dark"]` attribute (canonical), adds DESIGN_LANGUAGE utility bindings to the `@theme inline` block (every Section 9 token exposed to Tailwind utilities), migrates existing `--status-{success,warning,info,danger}` values from hex (shadcn defaults) to DESIGN_LANGUAGE oklch per approval decision 3.
- `frontend/index.html` — adds synchronous inline `<script>` in `<head>` for flash-of-wrong-mode prevention (reads `localStorage['bridgeable-mode']` + `prefers-color-scheme` fallback; sets `data-mode="dark"` on `<html>` before any CSS parses).

**Installed packages:** `@fontsource-variable/ibm-plex-sans@5.2.8`, `@fontsource/ibm-plex-serif@5.2.7`, `@fontsource/ibm-plex-mono@5.2.7`. Variable font variants don't exist for Plex Serif / Mono on npm (only Plex Sans has variable). Existing `@fontsource-variable/geist` stays as the platform default until Sessions 2-3 migrate per-component.

### Approved deviations from DESIGN_LANGUAGE.md Section 9

DESIGN_LANGUAGE.md Section 9 is written assuming a Tailwind v3-style `tailwind.config.js`. The Bridgeable frontend uses **Tailwind v4 via `@tailwindcss/vite`** where theme config lives inline in CSS via `@theme inline { ... }`. Session 1 translates each Section 9 JS config entry to `@theme inline` lines:

| Section 9 (Tailwind v3 JS config) | Session 1 (Tailwind v4 `@theme inline` line) |
|---|---|
| `colors.surface.base = 'var(...)'` | `--color-surface-base: var(--surface-base);` |
| `colors.brass.DEFAULT = 'var(...)'` | `--color-brass: var(--accent-brass);` |
| `fontSize['display-lg'] = [size, { lineHeight, fontWeight }]` | `--text-display-lg: var(--text-display-lg);` + `--text-display-lg--line-height: 1.1;` + `--text-display-lg--font-weight: 500;` |
| `boxShadow['level-1'] = 'var(...)'` | `--shadow-level-1: var(--shadow-level-1);` |
| `transitionDuration.quick = 'var(...)'` | `@utility duration-quick { transition-duration: var(--duration-quick); }` (v4's `--duration-*` is not an auto-namespace; needs explicit `@utility`) |
| `transitionTimingFunction.settle = 'var(...)'` | `--ease-settle: var(--ease-settle);` (v4 `--ease-*` IS an auto-namespace) |
| `maxWidth.reading = 'var(...)'` | `--container-reading: var(--max-w-reading);` (v4's `--container-*` generates both `max-w-*` and `@container` utilities) |
| `fontFamily.sans = ['IBM Plex Sans', ...]` | `--font-plex-sans: var(--font-plex-sans);` (new name; `--font-sans` stays Geist) |

DESIGN_LANGUAGE.md Section 9 gets a v4-clarification note added alongside the JS config example pointing at `frontend/src/index.css` as the live mapping — per approval decision 7.

### Other architectural decisions recorded

1. **shadcn token coexistence** (approval decision 8): existing shadcn CSS variables (`--background`, `--foreground`, `--card`, `--popover`, `--primary`, `--muted`, `--destructive`, `--border`, `--input`, `--ring`, `--sidebar*`, `--chart-*`, `--radius`, `--accent`) untouched. DESIGN_LANGUAGE tokens live alongside. Sessions 2-3 migrate component references; final cleanup retires shadcn layer.
2. **`--font-sans` untouched** (approval decision 1): Plex loaded under `--font-plex-{sans,serif,mono}`. Geist continues as platform default.
3. **`--radius-xl` +2px drift** (approval decision 2): existing calc-based value stays at 14px; DESIGN_LANGUAGE would be 16px. Sub-perceptual. Added `--radius-base: 6px` + `--radius-full: 9999px` as new names.
4. **Status-color hex→oklch drift** (approval decision 3 override): `--status-{success,warning,info,danger}` migrated from generic hex to DESIGN_LANGUAGE oklch. The one accepted one-time visual change in Session 1. Small surface area + correct colors > parallel-system mental overhead.
5. **Dark-mode selector coexistence** (approval decision 4): `@custom-variant dark (&:is(.dark *, [data-mode="dark"] *))` matches both.
6. **No visible mode toggle UI** (approval decision 5 + Session 2 scope): Session 1 ships runtime API only. Verification via devtools console.
7. **Tailwind v4 `@theme inline` over JS config** (approval decision 6).
8. **Plex Sans variable, Serif/Mono non-variable** (approval decision 10).
9. **Phase 3 Spaces accent system orthogonal** (approval decision 9): `--space-accent*` and `--accent-brass*` coexist cleanly by name. Conceptual relationship is Phase 8e/9 scope.
10. **Brass focus ring as opt-in utility** (not global replacement): `.focus-ring-brass` class scoped to refreshed components. Existing global `* { outline-ring/50 }` rule stays active so non-refreshed components retain their current focus treatment during the transition window.

### Tailwind utilities now available

Verified in the build output (checked compiled CSS for class-selector presence):

- **Surfaces** — `bg-surface-{base,elevated,raised,sunken}`
- **Content** — `text-content-{strong,base,muted,subtle,on-brass}`
- **Borders** — `border-border-{subtle,base,strong,brass}`
- **Brass** — `bg-brass`, `bg-brass-{hover,active,muted,subtle}` (+ `text-`, `border-`, `ring-` prefixes)
- **Status** — `text-status-{error,warning,success,info}`, `bg-status-{error,warning,success,info}-muted`
- **Fonts** — `font-plex-{sans,serif,mono}`
- **Type scale** — `text-{display-lg,display,h1,h2,h3,h4,body,body-sm,caption,micro}` (each with paired line-height + font-weight)
- **Radii** — `rounded-{base,full}` added; existing `rounded-{sm,md,lg,xl,2xl,3xl,4xl}` preserved
- **Shadows** — `shadow-level-{1,2,3}` (dark-mode top-edge highlight automatic)
- **Durations** — `duration-{instant,quick,settle,arrive,considered}` (100/200/300/400/600 ms)
- **Easings** — `ease-{settle,gentle}`
- **Max-widths** — `max-w-{reading,form,content,wide,dashboard}` (34/40/56/72/96 rem)
- **Utility class** — `.focus-ring-brass`

### Verification results (per the checklist)

- ✅ **Build:** `npm run build` succeeds in ~5s. CSS bundle 200 kB (gzip 31 kB).
- ✅ **TypeScript:** `tsc -b` clean.
- ✅ **Frontend tests:** 11 test files, 165/165 vitest green.
- ✅ **Backend tests:** 308/308 Phase 1-8c green (unchanged; frontend-only session).
- ✅ **Token resolution:** production CSS contains 134 `[data-mode=dark]` selectors + both light + dark `--surface-base` values.
- ✅ **Font loading:** 16 Plex `.woff2` files bundled alongside 1 Geist `.woff2`. No external CDN requests.
- ✅ **Tailwind utility generation:** probe file temporarily added, verified every new class compiled into the CSS bundle, probe file removed before commit.
- ✅ **Dev server:** starts clean; Vite HMR unaffected.
- ✅ **Visual regression spot check:** existing pages look identical to pre-Session-1 except status colors (expected — the accepted drift).

### Latent items deferred to future sessions

- **No mode toggle UI yet.** Session 2's settings refresh adds a toggle component consuming `useThemeMode()`.
- **Component visual refresh** — Sessions 2-3.
- **Dark mode visual verification across refreshed components** — Session 4.
- **Motion pass applying `ease-settle` / `duration-*` consistently** — Session 5.
- **WCAG 2.2 AA audit** — Session 6.
- **shadcn token retirement** — post-Session-6 cleanup.
- **Phase 3 Spaces accent vs. brass accent conceptual question** — Phase 8e/9 design scope.

Next: **Session 2 — Core component refresh** (buttons, inputs, cards, modals, dropdowns, navigation). First session that creates observable visual change.

---

## Workflow Arc Phase 8c — Core Accounting Migrations Batch 1

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (unchanged — no schema changes in 8c).
**Arc:** Workflow Arc — Phase 8c of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 25 BLOCKING parity (8+8+9) + 6 BLOCKING latency gates + 20 unit + 9 Playwright scenarios = **60 new this phase**. Phase 1–8b.5 regression: green. Phase 8b cash receipts parity: 9/9 unchanged.

### Primary deliverable: WORKFLOW_MIGRATION_TEMPLATE.md v2

Phase 8c ships three migrations alongside a major template bump — because the 8c targets had meaningfully different shapes than cash receipts (Phase 8b) and exercised patterns the v1 template didn't yet cover. Template v2 adds:

- **§5.5 — Extended parity test patterns** (four new patterns):
  - 5.5.1 pre-approval zero-write assertion (all three 8c targets are deferred-write).
  - 5.5.2 positive PeriodLock assertion (month_end_close — first full-approval migration).
  - 5.5.3 fan-out fidelity (ar_collections — per-customer items).
  - 5.5.4 override-action pattern (expense_categorization — `category_override` backend capability).
- **§7.6 — Event trigger not dispatched today — use scheduled fallback.** Documents the workaround for any migration declaring `trigger_type="event"` until real event infrastructure ships.
- **NEW §10 — Queue Cardinality Matrix.** Four shapes: per-anomaly (cash_receipts, expense_categorization) / per-entity (ar_collections) / per-job (month_end_close) / per-record (future 8f). Drives direct-query shape + adapter signature + parity test structure.
- **NEW §11 — Rollback-Gap Documentation Convention.** When a pre-existing approval path has partial-failure modes that don't cleanly roll back, the migration preserves verbatim + flags in three places. Month-end close statement-run-failure is the working example.
- **§1 deepening:** §1.3 (scheduler invocation) now lists 5 shapes including the event-fallback. §1.4 (approval type) now lists 4 SIMPLE/FULL variants with a rollback-gap sub-question. §1.5 (email template) updated to reflect Phase 8b.5's shared `email.approval_gate_review` managed template.
- **§14 appendix + §15 latent bugs + §16 changelog:** all updated with Phase 8c artifacts.

### Migrations shipped

**1. `month_end_close`** — FULL approval with period lock + deferred statement-run writes.
- Adapter (`backend/app/services/workflows/month_end_close_adapter.py`, ~290 lines): three public functions (`run_close_pipeline`, `approve_close`, `reject_close`) + `request_review_close` helper. 100% delegation to `AgentRunner.run_job` + `ApprovalGateService._process_approve`/`_process_reject`.
- Triage queue `month_end_close_triage`: **per-job cardinality** (item_entity_type="month_end_close_job"). Actions: approve (confirmation_required, invoice.approve permission), reject (requires_reason), request_review.
- Direct query + related-entities builder: return AgentJob + executive_summary + top-5 flagged customers + prior-month-close link for comparison context.
- Parity test (`test_month_end_close_migration_parity.py`, 8 tests): pre-approval zero-write × 2, reject no-write × 1, approve-writes-PeriodLock × 1 (positive assertion), legacy-vs-triage identity × 1, triage engine dispatch × 2, cross-tenant isolation × 1.
- **Rollback gap preserved verbatim** (statement-run-failure leaves partial rows + locked period). Template §11 documents. CLAUDE.md latent-bug tracking adds dedicated-cleanup-session target.
- Trigger: `manual` (user-invoked via UI or API).

**2. `ar_collections`** — SIMPLE approval with per-customer fan-out + new email-dispatch capability.
- Adapter (`backend/app/services/workflows/ar_collections_adapter.py`, ~330 lines): `run_collections_pipeline`, `send_customer_email`, `skip_customer`, `request_review_customer`. **Closes pre-existing Phase 3b TODO** — legacy `approval_gate._process_approve` for `ar_collections` was a no-op; triage `send` action now actually dispatches the email via `email_service.send_collections_email` → `delivery_service.send_email_with_template("email.collections")`.
- Triage queue `ar_collections_triage`: **per-customer cardinality** (item_entity_type="ar_collections_draft"). Actions: send (invoice.approve), skip (requires_reason), request_review.
- Direct query denormalizes: customer_name, billing_email, tier, draft_subject, draft_body_preview (first 300 chars). Sorted CRITICAL→ESCALATE→FOLLOW_UP then by total_outstanding desc.
- Related-entities builder: Customer + top-5 open invoices + past 3 collection emails via document_deliveries.
- Parity test (`test_ar_collections_migration_parity.py`, 8 tests): pre-approval zero-email × 1, send creates DocumentDelivery × 2, skip no-delivery × 1, **fan-out fidelity × 1 (3 customers × 3 actions)**, missing-email error-guard × 1, triage engine dispatch × 2.
- **Operational coexistence note:** tenants who've been "approving" drafts (which was a no-op) will see first real email sends from this deploy. Discontinue any manual email dispatching. Documented in release notes.
- Trigger: `scheduled` cron `0 23 * * *` (preserved from 8b.5 fix).

**3. `expense_categorization`** — SIMPLE approval with per-line review + AI-suggestion override.
- Adapter (`backend/app/services/workflows/expense_categorization_adapter.py`, ~340 lines): `run_categorization_pipeline`, `approve_line` (with optional `category_override`), `reject_line`, `request_review_line`.
- Triage queue `expense_categorization_triage`: **per-anomaly cardinality** (item_entity_type="expense_line_review"). Actions: approve (optional category_override payload), reject (requires_reason), request_review.
- Direct query denormalizes: vendor_name, VendorBillLine.description, amount, proposed_category (from report_payload.map_to_gl_accounts.mappings), current_category.
- Related-entities builder: VendorBillLine + parent VendorBill + Vendor + past 3 categorized lines for the same vendor (pattern-matching aid).
- Parity test (`test_expense_categorization_migration_parity.py`, 9 tests): pre-approval null-category × 1, approve-writes-AI-suggestion × 1, **override-replaces-suggestion × 1**, reject-no-write × 1, legacy-vs-triage parity × 1, triage engine dispatch × 3 (including override payload), cross-tenant isolation × 1.
- **Trigger-type change — explicit deviation, NOT a bug fix:** seed changed from `trigger_type="event"` + `trigger_config.event="expense.created"` to `trigger_type="scheduled"` + `cron="*/15 * * * *"`. Event dispatch doesn't exist today (no event subscription registry, no `expense.created` publish hook). Documented in `default_workflows.py` seed comment, commit message, session log (this entry), `WORKFLOW_MIGRATION_TEMPLATE.md` §7.6, and CLAUDE.md latent-bug tracking.
- **Override UI deferred to Phase 8e:** backend ships `category_override` kwarg + handler-payload plumbing. Frontend category-dropdown UI for operators designed alongside Phase 8e triage work.

### Shared infrastructure additions

- `workflow_engine._SERVICE_METHOD_REGISTRY`: 3 new entries (one per adapter pipeline).
- `triage.engine._DIRECT_QUERIES`: 3 new direct-query builders.
- `triage.ai_question._RELATED_ENTITY_BUILDERS`: 3 new related-entity builders.
- `triage.action_handlers.HANDLERS`: 9 new handlers (3 per migration).
- `triage.platform_defaults`: 3 new queue configs.
- `default_workflows.TIER_1_WORKFLOWS`: 3 migrated seeds (agent_registry_key cleared, real `call_service_method` steps).
- `scripts/seed_triage_phase8c.py`: 3 AI prompts seeded via Option A idempotent pattern.

### BLOCKING latency numbers (dev hardware)

All 6 gates pass with substantial headroom. Consolidated in `test_phase8c_triage_latency.py`:

| Gate | p50 | p99 | Budget (p50/p99) | Headroom |
|---|---|---|---|---|
| month-end-close next_item | 5.6 ms | 29.9 ms | 100 / 300 ms | 18× / 10× |
| month-end-close apply_action | 14.1 ms | 24.6 ms | 200 / 500 ms | 14× / 20× |
| ar-collections next_item | 14.0 ms | 19.8 ms | 100 / 300 ms | 7× / 15× |
| ar-collections apply_action | 15.8 ms | 45.5 ms | 200 / 500 ms | 13× / 11× |
| expense-categorization next_item | 48.0 ms | 80.3 ms | 100 / 300 ms | 2× / 4× |
| expense-categorization apply_action | 32.9 ms | 91.2 ms | 200 / 500 ms | 6× / 5× |

expense_categorization's next_item is the slowest due to per-anomaly joins into VendorBill + Vendor + proposed_category lookup from report_payload. Still well within budget. Future optimization: denormalize proposed_category onto AgentAnomaly row, or cache vendor lookups per sweep.

### Audit answers to the 9 questions (per migration)

**month_end_close:**
1. Write timing: **deferred** (all writes on approval via `_trigger_statement_run` + `PeriodLockService.lock_period`).
2. Anomaly types: 16 (across agent + statement_generation_service.detect_flags).
3. Scheduler: **manual** (user-invoked; no cron).
4. Approval type: **FULL** with period lock. POSITIVE PeriodLock assertion in parity test.
5. Email: `email.approval_gate_review` (Phase 8b.5 shared managed template).
6. Related entities: AgentJob exec summary + flagged customers + prior-month close.
7. AI prompt: `triage.month_end_close_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

**ar_collections:**
1. Write timing: **deferred** — drafts during pipeline, email dispatch on approval (NEW capability).
2. Anomaly types: 3 (collections_follow_up INFO, collections_escalate WARNING, collections_critical CRITICAL).
3. Scheduler: **scheduled** cron `0 23 * * *` tenant-local (8b.5 fix).
4. Approval type: **SIMPLE dispatch-on-approval** (closes Phase 3b TODO).
5. Email: `email.approval_gate_review` for the approval email + `email.collections` for the drafted collection emails.
6. Related entities: Customer + open invoices + past collection emails.
7. AI prompt: `triage.ar_collections_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

**expense_categorization:**
1. Write timing: **deferred** (VendorBillLine.expense_category on approval only).
2. Anomaly types: 3 (expense_low_confidence WARNING, expense_no_gl_mapping INFO, expense_classification_failed CRITICAL).
3. Scheduler: **scheduled** cron `*/15 * * * *` (**WORKAROUND — event trigger declared but not dispatched**).
4. Approval type: **SIMPLE writes-on-approval** (delegates to existing `_apply_expense_categories`).
5. Email: `email.approval_gate_review` (shared managed template).
6. Related entities: VendorBillLine + VendorBill + Vendor + past categorized lines for same vendor.
7. AI prompt: `triage.expense_categorization_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

### Legacy coexistence verified

- `/agents` dashboard still lists all 3 job types as runnable.
- `/agents/:id/review` page resolves for all 3 job types (ApprovalReview.tsx unchanged).
- `POST /api/v1/agents/accounting` endpoint still accepts all 3 `job_type` values.
- Email approval token flow still works for all 3 job types via the shared `email.approval_gate_review` template.

### Latent bugs surfaced (or inherited) — tracked for future cleanup

1. **Month-end close statement-run rollback gap** (surfaced in 8c audit). `_trigger_statement_run` catches exceptions but still proceeds to period lock, potentially leaving partial statement rows + locked period. Preserved verbatim for parity. Template §11 documents the pattern; dedicated cleanup session pending.
2. **Event trigger type declared but not dispatched** (surfaced in 8c audit). `trigger_type="event"` workflows never fire; no event subscription registry exists. Expense_categorization uses scheduled fallback (§7.6). Real fix is future event-infrastructure arc.
3. **Existing flags still open:** `time_of_day` UTC bug (8b.5); orphan migrations r34–r39 (8a); hardcoded legacy vault-print emails (pre-arc).

### Phase 8c readiness for downstream phases

- **Phase 8d** (vertical migrations): can proceed. Template v2 accommodates all observed shapes. Queue cardinality matrix guides vertical-workflow queue design.
- **Phase 8e** (spaces + default views): can proceed. Triage queues registered as platform defaults; spaces integration comes later.
- **Phase 8f** (remaining 8 accounting migrations): **unblocked.** Template v2 is the comparison checklist. Each of the 8 remaining agents answers the 9 questions from §1 + applies patterns from §5.5 / §10 / §11.

### What Phase 8c did NOT ship (per approved scope)

- Migration of remaining 8 accounting agents (Phase 8f).
- Vertical workflow migrations (Phase 8d).
- Dashboard surfaces showing accounting data as saved views (Phase 8g).
- Deletion of legacy bespoke UI (deferred to Phase 8h or later).
- Frontend override-dropdown UI for expense_categorization (Phase 8e).
- Event infrastructure (future horizontal arc).
- Rollback-gap correctness fixes (dedicated cleanup session).

Next: **Phase 8d or Phase 8e** depending on sequencing preference. Both are independently achievable from 8c's foundation.

---

## Workflow Arc Phase 8b.5 — Pre-8c Cleanup (Scheduler + Approval Emails)

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (advances from `r36_workflow_scope`)
**Arc:** Workflow Arc — narrow cleanup between 8b and 8c.
**Tests passing:** 10 scheduler + 8 email migration = **18 new this phase**. Adjacent regression: Phase 1–8b tests all green; Phase 8b cash receipts parity (9/9) unchanged — the email migration is a pure refactor from the parity-test perspective (audit finding #8).

### What shipped — two latent-bug fixes before Phase 8c starts

Phase 8b's reconnaissance audit surfaced two pre-existing latent bugs that 8c migrations would otherwise trip over. Fixing them as a deliberate standalone phase keeps 8c clean:

1. **Scheduler `scheduled` trigger type now dispatches.** Eight Tier-1 `wf_sys_*` workflows declared `trigger_type="scheduled"` + `trigger_config.cron` but were NOT being fired — `workflow_scheduler.check_time_based_workflows()` filtered only `["time_of_day", "time_after_event"]`. All 8 now fire correctly per tenant-local cron.
2. **Approval gate email migrated from hardcoded HTML to D-7 managed template.** `ApprovalGateService._build_review_email_html()` inlined ~85 lines of HTML-builder Python. Replaced with `email.approval_gate_review` managed template dispatched via `delivery_service.send_email_with_template`. All 12 agent job types share one template.

### Approved deviations from the audit recommendation

1. **Scheduler fix** (approved §1): APScheduler's `CronTrigger.from_crontab(cron, timezone=tenant_tz)` — no new dep. Tenant TZ via `_resolve_tenant_tz` helper mirroring Phase 6 briefings (`Company.timezone` with `America/New_York` fallback). Invalid cron: catch `ValueError`, log warning, skip that workflow, continue. New `_already_fired_scheduled` idempotency helper queries `trigger_context.intended_fire` JSONB field (canonical audit trail — not `started_at` wall-clock).
2. **Email migration** (approved §2): migration `r37_approval_gate_email_template` seeds `email.approval_gate_review` template. `ApprovalGateService._build_review_email_html()` deleted. Refactored to `delivery_service.send_email_with_template` with `caller_module="approval_gate.send_review_email"`. Semantic equivalence accepted (audit finding #8: Phase 8b parity test doesn't assert anything about email).
3. **No new migration for scheduler fix** (approved §6): all code changes, no schema change. One migration `r37` for the email template seed.

### Deploy-day operational implications (approved §3A)

**Eight previously-dormant workflows begin firing post-deploy:**

| ID | Cron | Impact |
|---|---|---|
| `wf_sys_ar_collections` | `0 23 * * *` daily | **Most impactful** — AR collection emails resume nightly |
| `wf_sys_safety_program_gen` | `0 6 1 * *` monthly | **Most impactful** — OSHA program auto-generation resumes |
| `wf_sys_statement_run` | `0 6 1 * *` monthly | Monthly consolidated statements resume |
| `wf_sys_compliance_sync` | `0 3 * * *` daily | OSHA deadlines + training expiry scan resumes |
| `wf_sys_training_expiry` | `0 7 * * 1` Mondays | Certification expiry alerts resume |
| `wf_sys_document_review_reminder` | `0 8 * * 1` Mondays | 11-month program review flags resume |
| `wf_sys_auto_delivery` | `0 6 * * *` daily | Auto-delivery eligibility scan resumes |
| `wf_sys_catalog_fetch` | `0 3 * * 1` Mondays | Wilbert catalog hash check resumes |

All 8 are **read-and-notify patterns** — no data corruption risk on first firing. Tenants who've been manually compensating (e.g., running AR collections ad-hoc to cover the silent skip) should **discontinue manual runs to avoid double-fires**. Document in release notes for deploy coordination.

### time_of_day TZ inconsistency flag (approved §3B)

Phase 8b.5 implements `scheduled` dispatch with **tenant TZ** (correct from the start). Existing `time_of_day` dispatch remains **UTC wall-clock** — a latent TZ bug. `wf_sys_cash_receipts` (Phase 8b) currently fires at 23:30 UTC for all tenants rather than 23:30 tenant-local. **Flagged for follow-on cleanup session.** `WORKFLOW_MIGRATION_TEMPLATE.md` §7.5 documents the inconsistency; 8c migrations that need tenant-local sub-daily timing should use `trigger_type="scheduled"` which already respects tenant TZ.

### Backend additions

- `backend/app/services/workflow_scheduler.py`:
  - New `_resolve_tenant_tz(name)` helper (mirrors briefings `_resolve_tz` pattern).
  - New `_intended_scheduled_fire(cron, tz, now)` — returns the cron tick datetime if it fell in the trailing 15-min window, else None. Raises `ValueError` on malformed cron (caller catches).
  - New `_already_fired_scheduled(db, workflow_id, company_id, intended_fire)` — audit-trail-based idempotency via `trigger_context.intended_fire` JSONB lookup. Self-healing across system restarts.
  - Extended `check_time_based_workflows()` query filter to include `"scheduled"` alongside existing two trigger types.
  - New `elif w.trigger_type == "scheduled"` dispatch branch: parses cron with tenant TZ, checks window + idempotency, fires via `workflow_engine.start_run` with `trigger_context={fired_at, intended_fire, cron}`.
  - Return shape extended: `{time_of_day_fired, time_after_fired, scheduled_fired, scheduled_skipped_invalid_cron}`.
- `backend/app/services/documents/_template_seeds.py`:
  - New `_approval_gate_seeds()` function returning the `email.approval_gate_review` template definition.
  - New `EMAIL_APPROVAL_GATE_REVIEW` + `EMAIL_APPROVAL_GATE_REVIEW_SUBJECT` Jinja templates — visual structure preserved from the previous hardcoded HTML.
- `backend/alembic/versions/r37_approval_gate_email_template.py`:
  - New migration. Seeds `email.approval_gate_review` via `_approval_gate_seeds()`. Idempotent guard at top of `upgrade()` — skips if template already exists (lets migration re-run cleanly). Downgrade removes the template + its versions.
- `backend/app/services/agents/approval_gate.py`:
  - `send_review_email()` refactored to use `delivery_service.send_email_with_template("email.approval_gate_review", template_context=...)` with `caller_module="approval_gate.send_review_email"`. Recipient fan-out loop unchanged. Subject override carries the fallback subject for any delivery-service code path that needs it.
  - **`_build_review_email_html()` DELETED** — no fallback to hardcoded HTML.

### Tests

- `backend/tests/test_workflow_scheduler_scheduled_dispatch.py` (10 tests):
  - `TestIntendedScheduledFire` × 4 — cron-window matching: matches in window / returns None outside window / respects timezone (NY vs LA) / invalid cron raises ValueError.
  - `TestAlreadyFiredScheduled` × 2 — audit-trail idempotency: detects prior run with matching intended_fire / different intended_fire doesn't block.
  - `TestSchedulerSweepIntegration` × 4 — end-to-end `check_time_based_workflows()`: scheduled workflow fires and records context, idempotency within window, invalid cron skipped gracefully (sibling still fires), time_of_day dispatch unchanged (regression).
  - Module-level autouse fixture cleans up `wf_sched_*` + `wf_tod_*` workflows + runs after suite completes — prevents DB accumulation on shared dev environments.
- `backend/tests/test_approval_email_managed_template.py` (8 tests):
  - `TestApprovalEmailManagedTemplate` × 4 — template exists in registry / renders with context / no-anomalies variant / dry-run banner variant.
  - `TestSendReviewEmailMigration` × 2 — full send_review_email path creates `DocumentDelivery` row with correct `template_key` + `caller_module` + subject references `job_type_label`.
  - `TestInlineHtmlRemoved` × 1 — regression: `_build_review_email_html` is gone.
  - `TestSeedIdempotent` × 1 — seed function returns single template entry with required shape.

### Regression

- **Phase 8b cash receipts parity (9 tests):** GREEN — the email migration is a pure refactor from the parity-test perspective (audit finding #8 confirmed no email assertions exist).
- **Phase 8a workflow scope (16 tests):** GREEN after fixing test-fixture tier assignment. Original test runs produced stale `wf_sched_*` + `wf_tod_*` workflows with `tier=1` + `scope="tenant"` — tripped the Phase 8a invariant "tier=1 IMPLIES scope=core". Fixed by using `tier=4` + `scope="tenant"` on test fixtures (semantically correct) + adding module-level cleanup. 43K accumulated stale WorkflowRun rows from earlier runs also purged.
- **Phase 5 triage + Phase 8b cash receipts unit + latency gates:** GREEN — no regressions.

### Post-deploy readiness check

Admin can verify the scheduler fix is live via:
```sql
-- How many WorkflowRun rows for scheduled triggers in the last 24h?
SELECT trigger_source, COUNT(*)
FROM workflow_runs
WHERE trigger_source = 'schedule'
  AND started_at >= NOW() - INTERVAL '24 hours'
GROUP BY trigger_source;
```
And for the email migration:
```sql
-- Approval emails now flow through the managed template:
SELECT COUNT(*) FROM document_deliveries
WHERE template_key = 'email.approval_gate_review'
  AND created_at >= NOW() - INTERVAL '7 days';
```

### Phase 8c readiness

After Phase 8b.5 completes, Phase 8c migrations of ar_collections / month_end_close / expense_categorization can proceed with:

- **Clean scheduler** that dispatches `trigger_type="scheduled"` correctly per tenant TZ.
- **Managed template approval emails** — 8c parity tests can assert `DocumentDelivery.template_key="email.approval_gate_review"` + `caller_module="approval_gate.send_review_email"` presence rather than byte-identical HTML matching.
- **time_of_day TZ issue still latent** but flagged in the template at §7.5. 8c migrations that want tenant-local timing should prefer `trigger_type="scheduled"` (which works correctly) over `time_of_day` (UTC-only).
- **`call_service_method` action subtype** (from Phase 8b) reused for every 8c adapter pipeline entry. One entry per agent added to `_SERVICE_METHOD_REGISTRY`.

### Open items remaining (deferred to future sessions)

1. **`time_of_day` TZ bug** — existing time_of_day workflows (`wf_mfg_eod_delivery_reminder`, `wf_sys_cash_receipts`) fire at UTC wall-clock, not tenant-local. Cleanup session: extend `_matches_time_of_day` to resolve tenant TZ before the window check.
2. **Orphan migrations `r34_order_service_fields` → `r39_legacy_proof_fields`** — still unreconciled (tracked since Phase 8a audit).
3. **Legacy `ApprovalReview.tsx` retirement** — when all 13 agents are migrated + admin comfort is proven, retire the bespoke page. Revisit at Phase 8h.

---

## Workflow Arc Phase 8b — Reconnaissance Migration (Cash Receipts Matching)

**Date:** 2026-04-21
**Migration head:** `r36_workflow_scope` (unchanged — no new tables, no migration)
**Arc:** Workflow Arc — Phase 8b of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 9 BLOCKING parity + 2 BLOCKING latency gates + 18 unit + 5 Playwright = **34 new this phase**. Adjacent regression: Phase 1–8a tests all green (UI/UX Arc + Phase 8a foundation).

### Primary deliverable: WORKFLOW_MIGRATION_TEMPLATE.md

This phase ships TWO things, not one:

1. **The cash receipts migration** — one accounting agent migrated end-to-end through the workflow engine + triage queue, with parity preserved via a thin service-reuse adapter.
2. **The migration template** — `WORKFLOW_MIGRATION_TEMPLATE.md` at project root, documenting the patterns discovered. It's the checklist 8c–8f migration audits compare their target agent against.

Cash receipts was chosen as the reconnaissance vehicle for specific reasons: cross-vertical (not vertical-scoped), SIMPLE approval (no period lock — less risky than month-end close), no existing scheduler entry (net-new insertion, no transition to wrangle), mid-complexity anomaly taxonomy (4 types — enough to exercise per-entity and tenant-aggregate patterns).

### Approved deviations from the audit recommendation

1. **Scheduler from-scratch** (approved §1): cash receipts had no APScheduler entry today. Phase 8b adds `trigger_type="time_of_day"` at 23:30 ET daily on the `wf_sys_cash_receipts` workflow row. Existing `workflow_scheduler.check_time_based_workflows` 15-min sweep fires it. **The migration template accommodates both "add from scratch" (cash receipts) and "reuse existing" (for 8c agents that have scheduler entries).**
2. **Agent_registry_key is informational-only** (approved §2): confirmed via code audit — nothing in `workflow_engine.py` reads it. It's a badge flag in the workflow row, not a dispatch switch. Parity test ensures both paths produce identical side effects when either runs.
3. **Two-step badge choreography** (approved §3): the migration template documents both (a) "8b-alpha: insert with agent_registry_key + placeholder steps; 8b-beta: real steps + clear field" and (b) "8b-beta from birth" (cash receipts didn't have a prior row, so we jumped straight to the beta state). For 8c's existing stubs (`wf_sys_month_end_close` etc.), the alpha→beta transition is the concrete path — they already have rows with `agent_registry_key` set by r36's backfill.
4. **`call_service_method` as new action subtype** (approved §4): single workflow engine extension. Whitelisted dispatch table (`_SERVICE_METHOD_REGISTRY`) mapping `"{agent}.{method}"` keys to importable callables with allowed-kwargs safelists. Auto-injected kwargs: `db`, `company_id`, `triggered_by_user_id`. Reused for every 8c–8f migration — zero further engine changes needed there.
5. **`time_of_day` trigger, Path A** (approved §5): reused the existing `time_of_day` dispatch path. Path B (extending scheduler to honor `trigger_type="scheduled"` with cron config) flagged as latent cleanup for `wf_sys_ar_collections` — deferred to a separate session.
6. **Operational coexistence contract** (approved §6): documented in both CLAUDE.md and §9 of the migration template. Triage queue = routine daily processing. Legacy `POST /api/v1/agents/accounting` = ad-hoc forensic re-runs only. Do not run both paths simultaneously on the same unresolved-item set. Phase 8c+ inherits this contract.
7. **Parity test categories** (approved §7): all 5 categories implemented in `test_cash_receipts_migration_parity.py` — PaymentApplication row identity, reject no-write, anomaly resolution shape, negative PeriodLock assertion, pipeline-scale equivalence. Plus triage engine integration + cross-tenant isolation. 9 tests total.
8. **Hardcoded approval email HTML** (approved §8): preserved verbatim for parity. Flagged for future cleanup in a separate session (platform-wide D-7 migration of approval-gate emails).
9. **Template as comparison checklist, not copy-paste** (approved §9): `WORKFLOW_MIGRATION_TEMPLATE.md` structured around nine audit questions each 8c–8f migration must answer. Cash receipts is the working example throughout.
10. **AI question prompt with 4 suggested questions** (approved §10): seeded via Option A idempotent pattern in `backend/scripts/seed_triage_phase8b.py`. Variables match the shared 4-field schema (`item_json`, `user_question`, `tenant_context`, `related_entities_json`).
11. **wf_sys_ar_collections latent bug** (approved §11): its `trigger_type="scheduled"` isn't dispatched by `workflow_scheduler` today. Workflow isn't actually firing on schedule. Flagged for separate cleanup session.
12. **Open questions** (approved §12): documented in §11 of the migration template — ApprovalReview.tsx future, start_run log when both paths present, period_lock discipline for 8c+, triage_approval step type vs input.

### Backend additions

- `backend/app/services/workflows/__init__.py` — new package.
- `backend/app/services/workflows/cash_receipts_adapter.py` (~340 lines) — the parity adapter. Five public functions: `run_match_pipeline` (workflow-step surface) + `approve_match` / `reject_match` / `override_match` / `request_review` (per-item triage actions). Private helpers for tenant-scoped entity loading + the PaymentApplication write pattern. Zero-duplication discipline via delegation to `AgentRunner.run_job` for the pipeline path + independent replication of the agent's CONFIDENT_MATCH branch write logic for per-item approves (covered by parity test).
- `backend/app/services/workflow_engine.py` — new `call_service_method` action subtype. Added to `_execute_action` dispatch chain at line 528. New `_handle_call_service_method` handler (~60 lines) with kwarg-allowlist filtering + dynamic callable import via `module:attr` paths. New `_SERVICE_METHOD_REGISTRY` global (one entry for Phase 8b).
- `backend/app/data/default_workflows.py` — `wf_sys_cash_receipts` appended to `TIER_1_WORKFLOWS`. `trigger_type="time_of_day"` + `trigger_config.time="23:30"` + `source_service="workflows/cash_receipts_adapter.py"`. Single step with `action_type="call_service_method"`. Parameterized via `dry_run` config entry for tenant overrides.
- `backend/app/services/triage/engine.py` — new `_dq_cash_receipts_matching_triage` function. Queries unresolved `AgentAnomaly` rows for `cash_receipts_matching` jobs. Denormalizes payment + customer info at query time. Returns rows sorted by severity (CRITICAL→WARNING→INFO) then amount desc. Registered in `_DIRECT_QUERIES` dict.
- `backend/app/services/triage/ai_question.py` — new `_build_cash_receipts_matching_related` function. Returns payment + customer + top-5 candidate invoices (ranked by |balance − payment_amount| proximity) + past 3 applied payment/invoice pairs (pattern-matching aid). Registered in `_RELATED_ENTITY_BUILDERS` dict.
- `backend/app/services/triage/action_handlers.py` — four new handlers (`_handle_cash_receipts_approve` / `_reject` / `_override` / `_request_review`) + 4 new registrations in `HANDLERS` dict under `cash_receipts.*` keys. Each handler validates payload kwargs (payment_id, invoice_id, reason/note) + delegates to the adapter; errors surface as `{"status": "errored", "message": "..."}` for engine-level handling.
- `backend/app/services/triage/platform_defaults.py` — new `_cash_receipts_triage` `TriageQueueConfig` + `register_platform_config` call at module bottom. 5-action palette (approve/reject/override/request_review/skip), 2 context panels (related_entities + ai_question), `invoice.approve` permission gate, cross-vertical, snooze enabled, schema_version="1.0".
- `backend/scripts/seed_triage_phase8b.py` (~165 lines) — Option A idempotent seed for `triage.cash_receipts_context_question` Intelligence prompt. Handles fresh-install / matching-content-noop / differing-content-update / multi-version-skip-with-warning cases. Uses shared 4-field variable schema + standard JSON response schema.

### Tests

- `backend/tests/test_cash_receipts_migration_parity.py` (~450 lines, 9 tests) — **BLOCKING**. Six test classes: TestApproveParity × 2 (PaymentApplication identity + anomaly resolution shape), TestRejectParity × 2 (no-write + reason required), TestNoPeriodLock × 1 (negative assertion), TestPipelineEquivalence × 1 (agent-run vs. adapter-run produce same shape), TestTriageEngineParity × 2 (engine dispatch + reason enforcement), TestTenantIsolation × 1 (cross-tenant anomaly rejection).
- `backend/tests/test_cash_receipts_triage_latency.py` (~235 lines, 2 tests) — **BLOCKING**. `test_cash_receipts_triage_next_item_latency_gate` (p50<100/p99<300) and `test_cash_receipts_triage_apply_action_latency_gate` (p50<200/p99<500). 30 samples + 3 warmups each. Seeds 40 pending anomalies with matching payment/invoice triples.
- `backend/tests/test_cash_receipts_phase8b_unit.py` (~330 lines, 18 tests) — 6 test classes: TestTriageRegistration × 2 (platform default + config shape), TestDirectQueryDispatch × 3 (key registered + empty new tenant + severity+amount ordering), TestRelatedEntitiesBuilder × 3 (registered + shape + empty on missing payment), TestHandlerRegistration × 2 (all 4 keys registered + graceful error on missing payload), TestWorkflowEngineRegistry × 4 (method in registry + unknown method errored + missing method_name errored + kwargs filtered by allowlist), TestCashReceiptsWorkflowSeed × 2 (entry present + expected shape with NULL agent_registry_key), TestAdapterEdgeCases × 2 (override without reason + request_review without note raise ValueError).
- `frontend/tests/e2e/workflow-arc-phase-8b.spec.ts` (~200 lines, 5 scenarios) — Playwright. Queue registration via /triage/queues API, wf_sys_cash_receipts visible on Platform tab without agent badge, queue config endpoint returns context panels + AI prompt key, legacy /agents dashboard still mounts (coexistence), legacy /agents/:id/review route still resolves.

### Performance

- **cash_receipts_triage_next_item:** p50=18.7ms, p99=20.1ms (budget 100/300) — **5× headroom on p50, 15× on p99**.
- **cash_receipts_triage_apply_action:** p50=15.7ms, p99=22.5ms (budget 200/500) — **13× headroom on p50, 22× on p99**.

apply_action carries three writes per call (PaymentApplication insert + Invoice mutation + anomaly resolve) + commit. That 3-write pattern is representative of what 8c–8f migrations' hot paths will look like, so 13× p50 headroom is a reassuring floor.

### Migration patterns extracted to template

Documented in `WORKFLOW_MIGRATION_TEMPLATE.md` §§1–12:

1. **Nine audit questions** every migration answers: write timing, anomaly structure, existing scheduler invocation, approval type, email template status, related entities, AI prompt shape, permission gate, vertical scoping.
2. **Parity adapter pattern**: thin module at `backend/app/services/workflows/{agent}_adapter.py`. Pipeline entry (`run_match_pipeline` et al.) for workflow-step surface + per-item helpers for triage actions. Zero-duplication via delegation where possible + parity-tested replication where not. Tenant isolation via `_load_*_scoped` helpers.
3. **Workflow definition structure**: seed entry in `TIER_1_WORKFLOWS` + `call_service_method` dispatch registration + two-step badge choreography (alpha→beta) for agent_registry_key transitions.
4. **Triage queue configuration**: three files (engine.py direct query, ai_question.py related builder, action_handlers.py handlers) + platform_defaults.py config + 4 decision-oriented AI question chips.
5. **Parity test requirements**: 5 categories of assertions, shared fixture pattern with per-test seeding (to avoid cross-test contamination from tenant-wide agent sweeps), BLOCKING classification convention.
6. **Latency gate requirements**: two gates per migration (next_item + apply_action), 30 samples + 3 warmups, seeded-fixture methodology.
7. **Scheduler transition patterns**: three paths documented (add-from-scratch, reuse-existing-agent-cron, reuse-existing-workflow-cron).
8. **Agent badge clearing**: informational-only field; no cache clear or app restart needed — just clear the column and frontend re-renders without the badge.
9. **Coexist-with-legacy contract**: four commitments (canonical routine path via triage, legacy endpoint for forensics, no concurrent processing, retirement deferred).
10. **Post-migration verification checklist**: 13 items to check before closing a migration PR.

### Patterns specific to cash receipts (WON'T generalize to 8c–8f)

Documented in §1.1 / §1.4 / §1.5 of the template so 8c audits don't copy blindly:

- Immediate-write pattern (writes during agent step 2) — month-end close is deferred-write; AR collections is none-write.
- SIMPLE approval (no period lock) — month-end close is full approval with lock discipline.
- Hardcoded approval email HTML — other agents may have different approval-email shapes or no approval email at all.
- 4-rule matching ladder (CONFIDENT/POSSIBLE-any/POSSIBLE-subset/UNRESOLVABLE) — each agent has its own decision topology.

### Legacy coexistence verified

Post-8b, these still work (verified by tests + manual audit):

- **`POST /api/v1/agents/accounting`** with `job_type="cash_receipts_matching"` — the Phase 1 accounting agent endpoint. Admin can still ad-hoc-run cash receipts via `/agents` hub.
- **`/agents` dashboard** — AgentDashboard.tsx mounts, lists cash_receipts_matching as runnable.
- **`/agents/:jobId/review`** — ApprovalReview.tsx route resolves.
- **`/agents/approve/{token}`** — email-token approval path unchanged; existing inbox tokens still work.
- **Vault accounting admin tab** `/vault/accounting/agents` — schedule + recent-jobs surfaces unaffected.

### Surprises worth flagging for 8c–8f scoping

1. **`agent_registry_key` is purely informational** — confirmed via full `grep` audit. Nothing in `workflow_engine.py` reads it. This simplifies the migration: no dispatch-routing code to change; clearing the field is a pure UI signal. 8c inherits this simplification.
2. **No wf_sys_cash_receipts existed pre-8b** — the 16 `wf_sys_*` count from Phase 8a did NOT include cash receipts. Phase 8b had to insert the row from scratch. 8c's targets (month_end_close, ar_collections, expense_categorization) DO have existing rows with `agent_registry_key` set — their transition is the alpha→beta path, not birth-as-beta.
3. **Agent sweeps are tenant-wide** — CashReceiptsAgent processes ALL unmatched payments, not just a specific subset. Fixture setup in parity tests must seed "path A" rows, run the agent, THEN seed "path B" rows to avoid cross-test contamination. Applies to other sweeping agents (expense categorization, AR collections).
4. **`trigger_type="scheduled"` declared on wf_sys_ar_collections is dead** — `workflow_scheduler.check_time_based_workflows()` only dispatches `time_of_day` and `time_after_event`. AR collections isn't actually firing on schedule today. Flagged as latent cleanup (separate session).
5. **Hardcoded approval email HTML predates D-7** — `ApprovalGateService._build_review_email_html()` builds the body inline in Python. Parity discipline requires preserving verbatim. Platform-wide migration to managed templates is future cleanup work.
6. **Option B (enrollment + override) path untouched by Phase 8b** — cash receipts workflow seed includes a `params` block (dry_run override) demonstrating compatibility. Actual enrollment-override UX is still Phase 8c's polish item.

### Latent bug flags (NOT fixed in 8b)

These surfaced during the 8b audit but are explicitly out of scope. Each is tracked as a separate future session:

1. `wf_sys_ar_collections` scheduled-trigger bug (§11 above).
2. Hardcoded approval email HTML in `ApprovalGateService` (§11 above).
3. Orphan migrations `r34_order_service_fields` → `r39_legacy_proof_fields` (pre-existing from Phase 8a audit, still unreconciled).

### What Phase 8b did NOT ship (per approved scope)

- Migration of any other accounting agent — that's 8c–8f systematically.
- Deletion of legacy bespoke cash receipts UI — later phase.
- Visual refresh of cash receipts triage surface — Aesthetic Arc.
- Month-end close migration — Phase 8c with period lock discipline.
- Dashboards showing cash receipts data as saved views — Phase 8g.
- Tenant customization UX for cash receipts workflow — design work, later phase.
- Fork-vs-override UX polish — deferred from 8a to 8c.
- Triage queue customization admin UI — Phase 7 deferred, still out of scope.

Next up: **Phase 8c — Core accounting migrations batch 1** (month_end_close + ar_collections + expense_categorization). Uses the migration template as the audit checklist. Each agent's audit answers the 9 questions documented in §1 of `WORKFLOW_MIGRATION_TEMPLATE.md`.

---

## Workflow Arc Phase 8a — Foundation Infrastructure

**Date:** 2026-04-21
**Migration head:** `r36_workflow_scope` (advances from `r35_briefings_table`)
**Arc:** Workflow Arc (new) — see `WORKFLOW_ARC.md` at project root for the full 8a–8h plan.
**Tests passing:** 30 backend (16 workflow scope/fork + 14 system space / role decoupling) + 5 BLOCKING latency gates + 6 vitest (DotNav) + 6 Playwright scenarios = **47 new this phase**. Adjacent regression: UI/UX Arc Phase 1–7 tests + all follow-ups passing; frontend vitest full run 165/165; `tsc -b` clean.

### What shipped — groundwork for Phase 8b–8h

Phase 8a is the foundation the remaining Workflow Arc phases build on. No workflow migrations yet, no agent retirement yet. What it establishes:

1. **Workflow scope field** — `core` / `vertical` / `tenant` classification as a first-class workflow attribute. All 37 existing workflows backfilled: 16 `wf_sys_*` rows → `core`, 21 vertical (manufacturing + funeral_home) → `vertical`, 0 tenant on the seeded dev tenant.
2. **Tenant fork mechanism** — `POST /api/v1/workflows/{id}/fork` creates an independent tenant copy with fresh IDs, remapped DAG edges, and copied platform-default step params. `forked_from_workflow_id` + `forked_at` stamped. Coexists with the existing `WorkflowEnrollment` + `WorkflowStepParam` soft-customization path — both are deliberate per the approved spec.
3. **Settings as a platform space** — registered via new `SYSTEM_SPACE_TEMPLATES` mechanism. Seeded for admins at registration. Non-deletable (can be renamed, recolored, and have pins reordered). Stable space ID `sys_settings`.
4. **DotNav** — horizontal dots at the bottom of the left sidebar. Replaces the Phase 3 top-bar `SpaceSwitcher`. System spaces sort leftmost regardless of display_order. Phase 3 keyboard shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) preserved. Old `SpaceSwitcher` component left in the repo for a one-release grace window; the mount is removed.
5. **Role decoupling preparation** — `ROLE_CHANGE_RESEED_ENABLED: bool = False` module constant in `user_service.py` gates the role-change reseed block. Registration-time seeds preserved. Spaces seed still runs on role change (idempotent + permission recheck — needed so new permissions surface Settings in the dot nav promptly). Public helper `reapply_role_defaults_for_user(db, user)` available for the opt-in UI landing in Phase 8e.
6. **Agent-backed workflow stubs** — three `wf_sys_*` rows (`wf_sys_month_end_close`, `wf_sys_ar_collections`, `wf_sys_expense_categorization`) get `agent_registry_key` populated, corresponding to existing entries in `AgentRunner.AGENT_REGISTRY`. Frontend renders a "Built-in implementation" badge on those cards; click routes read-only to `/view` rather than `/edit`. Badges clear per row as agents migrate to real workflow definitions in 8b–8f.

### Approved deviations from the spec

1. **Both customization paths preserved** (audit A) — the existing enrollment + override (Option B) path stays unchanged; fork (Option A) adds alongside. The UX for "when to use which" lands in Phase 8c.
2. **System space re-seed runs unconditionally on role change** (audit D) — even with `ROLE_CHANGE_RESEED_ENABLED=False`, the spaces seed block still runs because the Settings system space is permission-gated and needs to appear in the dot nav when a user is promoted to admin. The seed is idempotent: existing user spaces are untouched; only the Settings dot is added if the permission grant just happened.
3. **Latency gates adjusted for Phase 8a data sizes** (audit F) — the five new BLOCKING gates (workflow-scope-core, workflow-scope-core+used_by, workflow-scope-vertical, spaces-with-system, workflow-fork) run against the seeded dev tenant (~40 workflow rows). Budgets chosen to match UI/UX Arc conventions: scope filters at p50<100ms/p99<300ms, fork at p50<200ms/p99<500ms (wider because it's a multi-table write path).
4. **Agent badge shipped in 8a** (audit G1) — rather than deferred. The "Built-in implementation" badge + read-only routing for agent-backed rows is minimal and lets Phase 8b's migration template work against a representative UI the whole time.
5. **Fork-vs-override UX polish deferred to 8c** (audit G2) — the fork API + button ships in 8a so the infrastructure is proven; the decision-tree UI ("when to use fork vs enrollment override") is Phase 8c work alongside the first real migration.

### Backend additions

- `backend/alembic/versions/r36_workflow_scope.py` — new migration. Adds `workflows.scope` (String 16, NOT NULL, server_default `"tenant"`), `workflows.forked_from_workflow_id` (FK → workflows.id ON DELETE SET NULL, nullable), `workflows.forked_at` (DateTime tz, nullable), `workflows.agent_registry_key` (String 100, nullable). CHECK constraint `scope IN ('core','vertical','tenant')`. Indexes on `(company_id, scope)` + partial on `forked_from_workflow_id WHERE NOT NULL`. Data backfill: scope derived from tier (tier 1 → core, tier 2/3 → vertical, tier 4 → tenant); agent_registry_key populated for the three existing agent-backed stubs. Idempotent-safe via the `env.py` op wrappers.
- `backend/app/models/workflow.py` — 4 new Mapped columns (`scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`).
- `backend/app/services/workflow_fork.py` — new service (~230 lines). `fork_workflow_to_tenant(db, *, user, source_workflow_id, new_name=None) -> Workflow` copies source with fresh UUIDs, two-pass ID map to remap DAG edges, copies platform-default `WorkflowStepParam` rows (those with `company_id IS NULL`), stamps `forked_from_workflow_id` + `forked_at`, clears `agent_registry_key` on the copy. Raises typed `ForkNotAllowed` / `SourceNotFound` / `AlreadyForked`. Also exports `count_tenants_using_workflow()` aggregating distinct active enrollments (for the `include_used_by=true` query path).
- `backend/app/api/routes/workflows.py` — `_serialize_workflow` extended with `scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`, `company_id`, `used_by_count`. `list_workflows` gains `scope` + `include_used_by` query params with regex validation on scope. New `POST /{workflow_id}/fork` endpoint with `_ForkRequest` Pydantic body.
- `backend/app/services/spaces/registry.py` — new `SystemSpaceTemplate` dataclass with `required_permission` + `SYSTEM_SPACE_TEMPLATES: list[SystemSpaceTemplate]` containing the Settings template (stable id `sys_settings`, icon `"settings"`, accent `"neutral"`, 4 seed pins: `/settings/workflows`, `/saved-views`, `/admin/users`, `/admin/roles`). `get_system_space_templates_for_user(db, user)` filters by `user_has_permission`.
- `backend/app/services/spaces/types.py` — `SpaceConfig` gains `is_system: bool = False`; `ResolvedSpace` propagates it. to_dict / from_dict roundtrip.
- `backend/app/services/spaces/seed.py` — new `_apply_system_spaces(db, user)` seeds system spaces the user has permission for; tracks via `user.preferences["system_spaces_seeded"]: list[str]`; appended to `created_total` return. Called from both `register_user` path and `update_user` role-change path (idempotent).
- `backend/app/services/spaces/crud.py` — `delete_space` raises `SpaceError("System spaces can be hidden but not deleted. Rename, recolor, or reorder pins to customize it.")` when target is `is_system=True`. `_resolve_space` propagates is_system into the response.
- `backend/app/api/routes/spaces.py` — `_SpaceResponse` gains `is_system: bool = False`; `_resolved_to_response` propagates.
- `backend/app/services/user_service.py` — module-level constant `ROLE_CHANGE_RESEED_ENABLED: bool = False`. New public `reapply_role_defaults_for_user(db, user) -> dict[str, int]` helper calling saved_views + spaces + briefings seeds. The role-change hook in `update_user` now: (a) skips saved_views + briefings seeds when flag is False, (b) still runs spaces seed unconditionally (permission recheck for system spaces).

### Frontend additions

- `frontend/src/components/layout/DotNav.tsx` — new ~260-line component. Horizontal dot row rendered at the bottom of the existing sidebar (between `OnboardingSidebarWidget` and the preset label). System spaces sort leftmost regardless of display_order. `_DOT_NAV_ICON_MAP` for lucide icons (exported for vitest); falls back to a colored dot in `space.accent` when no icon maps. Active dot gets `aria-pressed="true"` + `data-active="true"`. Keyboard shortcuts: `Cmd+[` / `Cmd+]` prev/next, `Cmd+Shift+1..5` direct access (ignores inputs/textareas/contenteditables). Shift+click on a dot opens `SpaceEditorDialog`; plus button opens `NewSpaceDialog`. `data-testid`s: `dot-nav`, `dot-nav-dot`, `dot-nav-add`. Null-renders when no spaces exist (matches Phase 3 behavior).
- `frontend/src/components/layout/sidebar.tsx` — mounts `<DotNav />` between `OnboardingSidebarWidget` and the preset label.
- `frontend/src/components/layout/app-layout.tsx` — `SpaceSwitcher` import + mount removed from the header. Comment notes the component stays in-repo for a one-release grace window; future cleanup removes the file.
- `frontend/src/types/spaces.ts` — `Space` interface gains optional `is_system?: boolean`.
- `frontend/src/pages/settings/Workflows.tsx` — `WorkflowCard` extended with `scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`. New `isAgentBacked` guard routes agent-backed rows to `/view` instead of `/edit`. `forkWorkflow(id)` async handler calls `POST /api/v1/workflows/{id}/fork` and navigates to the new fork's edit page. "Built-in implementation" badge (indigo) renders when `agent_registry_key` is set; "Fork" badge (emerald) renders when `forked_from_workflow_id` is set. Fork button appears on Core/Vertical rows (`canFork && !isAgentBacked`).

### Tests

- `backend/tests/test_workflow_scope_phase8a.py` — 16 tests across 3 classes:
  - `TestScopeFiltering` (5): Core tab returns core only, Vertical tab returns vertical only, Tenant tab returns tenant only, unknown scope → 400, no scope param returns all.
  - `TestForkEndpoint` (8): creates independent copy, clears agent_registry_key, stamps forked_from + forked_at, two-pass DAG remap correctness, platform-default step params copied, AlreadyForked rejection, SourceNotFound → 404, non-admin → 403.
  - `TestCountTenantsUsingWorkflow` (3): counts distinct enrollments, excludes inactive, returns zero when no enrollments.
- `backend/tests/test_system_spaces_phase8a.py` — 14 tests across 4 classes:
  - `TestSystemSpaceTemplates` (3): Settings template exists + has required_permission, get_system_space_templates_for_user filters by permission, unknown permission hides template.
  - `TestSystemSpaceSeeding` (4): admin user gets Settings seeded at registration, non-admin doesn't, idempotent re-seed, tracks via preferences.system_spaces_seeded array.
  - `TestSystemSpaceNonDeletion` (3): delete_space raises SpaceError for is_system=True, allows rename + accent change + pin reorder.
  - `TestRoleDecouplingFlag` (4): flag default False, saved_views seed skipped when False, briefings seed skipped when False, spaces seed runs unconditionally (permission recheck for new grants).
- `backend/tests/test_workflow_scope_latency_phase8a.py` — 5 BLOCKING latency gates (20 samples each, 3 warmups):
  - `workflow-scope-core` (budget p50<100ms/p99<300ms): **p50=15.4ms, p99=38.4ms** (6×/8× headroom).
  - `workflow-scope-core+used_by` (same budget): **p50=24.8ms, p99=26.0ms** (4×/12× headroom).
  - `workflow-scope-vertical` (same budget): **p50=5.0ms, p99=6.3ms** (20×/48× headroom).
  - `spaces-with-system` (same budget): **p50=2.1ms, p99=2.1ms** (48×/143× headroom).
  - `workflow-fork` (budget p50<200ms/p99<500ms): **p50=5.1ms, p99=5.3ms** (39×/94× headroom).
- `frontend/src/components/layout/DotNav.test.tsx` — 6 vitest: null-renders with no spaces, renders one dot per space + plus button, active dot aria-pressed, system space sorts leftmost regardless of display_order, click invokes switchSpace, icon map contains expected entries.
- `frontend/tests/e2e/workflow-arc-phase-8a.spec.ts` — 6 Playwright scenarios: dot_nav_renders_at_bottom, dot_nav_switches_spaces (with aria-pressed update), settings_dot_visible_for_admin (skips cleanly when staging data is older), workflows_page_shows_scope_cards (agent badge on wf_sys_month_end_close), fork_core_workflow_flow (mocked fork endpoint), old_top_space_switcher_gone (regression).

### Orphan migration flag

During the Phase 8a audit, a chain of six orphan migration files surfaced — `r34_order_service_fields.py` through `r39_legacy_proof_fields.py` — branching off from `r33_lifecycle_gaps` which isn't on the main chain. `alembic heads` still shows a single head (`r35_briefings_table` before this phase, now `r36_workflow_scope`), confirming the orphans aren't reachable. They appear to be pre-existing feature-branch artifacts that never reconciled with the UI/UX Arc chain. Per the approved audit clarification E, **do NOT touch these in Phase 8a** — flagged in `WORKFLOW_ARC.md` → Post-Arc Backlog so a future cleanup session picks them up with a dedicated review.

### Phase 8a Final State

- **Migration head:** `r36_workflow_scope`
- **Tables modified:** `workflows` gains 4 columns + CHECK + 2 indexes. No new tables.
- **Workflow scope distribution on seeded dev tenant:** 16 core / 21 vertical / 0 tenant (after r36 backfill).
- **Agent-backed workflows surfaced:** 3 (`month_end_close`, `ar_collections`, `expense_categorization`) — each shows the "Built-in implementation" badge + read-only click-through until migrated in 8b–8f.
- **BLOCKING CI gates total:** 12 (5 new + 7 from the UI/UX Arc).
- **Infrastructure ready for:** Phase 8b reconnaissance migration (Cash Receipts Matching), 8c–8f accounting + vertical migrations, 8e spaces + default views expansion, 8g dashboard rework, 8h arc finale.

Next up: **Phase 8b — Reconnaissance Migration: Cash Receipts Matching**. Deliberate one-agent learning phase. Output is a reusable migration template for 8c–8f.

---

## Peek Panels (UI/UX Arc Follow-up 4 — Arc Finale)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 21 backend (14 peek API + 6 triage related + 1 BLOCKING latency gate) + 25 frontend vitest (8 PeekContext + 5 adapter + 12 renderers) + 8 Playwright scenarios = **54 new this follow-up**. Adjacent regression: 184 saved-views + spaces + triage + ai_question + briefings + command_bar + nl_creation tests passing — no regressions. Frontend full vitest: 159 across 10 files. Frontend `tsc -b` clean; `npm run build` clean.

### What shipped — final follow-up of the UI/UX arc

Lightweight entity previews without navigation. Two interaction modes — **hover** (transient, info-only) and **click** (pinned, can include actions). Six entity types: `fh_case`, `invoice`, `sales_order`, `task`, `contact`, `saved_view`. Wired across four trigger surfaces:

1. **Command bar RECORD/VIEW tiles** — hover-reveal eye icon on tile (opacity 0 → 60 on row hover), click → click-mode peek. Primary tile click still navigates.
2. **Briefing `pending_decisions`** — title-click on each decision row opens click-mode peek when the `link_type` matches the known peek-entity whitelist. "Open →" link untouched.
3. **Saved view builder preview rows** — title-cell click opens click-mode peek (List/Table renderers). Detail page + widget callers don't pass `onPeek` so click-to-navigate behavior preserved.
4. **Triage related-entities panel** — closes the third Phase 5 stub. Tiles render via the new `/related` endpoint that exposes follow-up 2's `_RELATED_ENTITY_BUILDERS`. Each tile is click-to-peek.

### Approved deviations from the spec

1. **New endpoint** `GET /api/v1/peek/{entity_type}/{entity_id}` + `PEEK_BUILDERS` dict (6 builders). Reuse-existing-detail-endpoints option rejected per audit because detail responses average ~30 fields.
2. **`peek_fetch`** as 7th `arc_telemetry` `TRACKED_ENDPOINTS` key.
3. **BLOCKING CI gate** at `tests/test_peek_latency.py` — p50 < 100 ms, p99 < 300 ms across 24 mixed-shape samples (6 entity types × 4 rotations). **Actual: p50 = 3.7 ms, p99 = 7.4 ms** (27×/40× headroom).
4. **Briefing peek path uses structured `pending_decisions`** (no prompt v3 narrative-token bump per audit recommendation A).
5. **Command bar peek icon, NOT click-semantic swap** (per audit recommendation B). Affordance matches dominant intent: command bar = action-style (navigate on click), other surfaces = browse-style (peek on click).
6. **Triage related_entities wired** in this follow-up (per audit recommendation C). Closes the third Phase 5 stub; uses follow-up 2's `_RELATED_ENTITY_BUILDERS` infrastructure verbatim.

### Implementation deviation worth flagging

**Item 10 audit-approved spec said "base-ui Tooltip for hover, base-ui Popover for click."** The shipped `PeekHost.tsx` is a single floating-host component with controlled state from PeekContext. ARIA semantics are equivalent (`role="dialog" aria-modal="true"` for click; `role="tooltip"` for hover); Esc handling, click-outside backdrop, and focus return are manually wired (~30 lines total). Trade-off: the hover→click promotion is a state mutation rather than a component remount → no flash; single render path → simpler testing. The base-ui Popover/Tooltip migration is filed in the post-arc backlog under "Architectural debt" if the controlled-mode API ever becomes ergonomic for our context-driven peek state.

### Backend additions

- `backend/app/services/peek/types.py` — `PeekResponse` envelope + `PeekError` / `UnknownEntityType` / `EntityNotFound` / `PeekPermissionDenied` typed errors.
- `backend/app/services/peek/builders.py` — six per-entity builder functions + `PEEK_BUILDERS` dispatch dict + `build_peek()` public dispatcher. Mirrors Phase 5 `_DIRECT_QUERIES` + follow-up 2 `_RELATED_ENTITY_BUILDERS` shape. ~330 lines total (~30 per builder + helpers).
- `backend/app/services/peek/__init__.py` — public exports.
- `backend/app/api/routes/peek.py` — single route handler, telemetry-wrapped via try/finally.
- `backend/app/api/v1.py` — registers peek router under `/peek` prefix.
- `backend/app/services/arc_telemetry.py` — `TRACKED_ENDPOINTS` extended with `peek_fetch`.
- `backend/app/services/triage/ai_question.py` — new `list_related_entities()` public function (reuses `_RELATED_ENTITY_BUILDERS`); exported in `__all__`.
- `backend/app/api/routes/triage.py` — new `GET /sessions/{id}/items/{item_id}/related` route + `_RelatedEntityResponse` Pydantic shape.

### Frontend additions

- `frontend/src/types/peek.ts` — `PeekEntityType`, `PeekTriggerType`, `PeekPayload` discriminated union (6 entity types), `PeekResponse` generic envelope, `PeekResponseBase`.
- `frontend/src/services/peek-service.ts` — `fetchPeek(entityType, entityId, {signal})` with AbortSignal pass-through.
- `frontend/src/services/triage-service.ts` — `fetchRelatedEntities(sessionId, itemId)` + `TriageRelatedEntity` shape.
- `frontend/src/contexts/peek-context.tsx` — `PeekProvider`, `usePeek` (throws when absent), `usePeekOptional` (null-safe). Holds the single active-peek state, the session-scoped `Map<"{type}:{id}", {data, fetchedAt}>` cache (5-min TTL), AbortController for cancellation, hover debounce (200ms), `promoteToClick`. Cleared on provider unmount.
- `frontend/src/components/peek/PeekHost.tsx` — single floating-panel renderer. `useLayoutEffect` positions it relative to `current.anchorElement` via `getBoundingClientRect()`; flips above when not enough room below. Auto-focuses panel on click open + restores focus to anchor on close. Esc handler. Hover-mouse-leave-with-grace-period dismiss. Renders one of 6 per-entity renderers based on `data.entity_type`. Footer "Open full detail →" navigates + closes.
- `frontend/src/components/peek/PeekTrigger.tsx` — `<PeekTrigger>` wrapper for any element + `IconOnlyPeekTrigger` variant. Coarse-pointer detection collapses hover triggers to click on touch devices. Keyboard: Tab focuses, Enter/Space opens.
- `frontend/src/components/peek/renderers/` — 6 per-entity renderers (CasePeek, InvoicePeek, SalesOrderPeek, TaskPeek, ContactPeek, SavedViewPeek) + shared `_shared.tsx` (PeekField, fmtDate, fmtCurrency, StatusBadge).
- `frontend/src/components/triage/RelatedEntitiesPanel.tsx` — wires the Phase 5 stub. Tiles are click-to-peek (when entity type is peek-supported) or non-peekable display only.
- `frontend/src/components/triage/TriageContextPanel.tsx` — dispatcher swap: `case "related_entities"` now renders `RelatedEntitiesPanel` instead of the EmptyState stub.
- `frontend/src/components/saved-views/SavedViewRenderer.tsx` — optional `onPeek` prop threaded through to `ListRenderer` + `TableRenderer`.
- `frontend/src/components/saved-views/renderers/ListRenderer.tsx` + `TableRenderer.tsx` — title cell becomes click-to-peek button when `onPeek` provided + the row has an id.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.tsx` — passes peek handler to renderer when PeekProvider is in scope.
- `frontend/src/pages/briefings/BriefingPage.tsx` — `PendingDecisionsCard` converts title to click-peek button when `_BRIEFING_LINK_TYPE_TO_PEEK` whitelist matches.
- `frontend/src/components/core/CommandBar.tsx` — peek-icon affordance on RECORD/VIEW tiles when `peek && action.peekEntityType && action.peekEntityId`. Span+role=button to nest inside the outer button. `stopPropagation` so primary tile click is unaffected.
- `frontend/src/core/commandBarQueryAdapter.ts` — propagates backend `result_entity_type` into `peekEntityType` for the 6 supported types + saved_view; sets undefined for non-peekable types.
- `frontend/src/services/actions/registry.ts` — `CommandAction` interface gains optional `peekEntityType` + `peekEntityId`.
- `frontend/src/App.tsx` — mounts `<PeekProvider>` + `<PeekHost />` inside the authenticated tenant tree (after `SpaceProvider`). Platform admin / login routes unaffected.

### Tests

- `backend/tests/test_peek_api.py` — 14 tests across 4 classes: happy path × 6 entity types, errors (unknown type, not found, tenant isolation, auth), telemetry registration + wrap on success/error.
- `backend/tests/test_peek_latency.py` — 1 BLOCKING latency gate (24 samples mixed across 6 types).
- `backend/tests/test_triage_related_endpoint.py` — 6 tests: happy-path with siblings, empty list when no builder/no siblings, session/item 404s, cross-user isolation, auth required.
- `frontend/src/contexts/peek-context.test.tsx` — 8 tests: click-mode happy path, close+abort race, hover debounce + cancel, hover fires after 200ms, session cache hit on repeat open, different entity bypasses cache, promoteToClick state mutation, error path surfaces detail.
- `frontend/src/core/commandBarQueryAdapter.peek.test.ts` — 5 tests: 5 peek-supported types map correctly + saved_view, non-peekable types skip mapping, navigate/create skip mapping, null entity_type skips.
- `frontend/src/components/peek/renderers/renderers.test.tsx` — 12 tests: each of 6 renderers checks required-field rendering + null-field omission + format helpers + status badge.
- `frontend/tests/e2e/peek-panels.spec.ts` — 8 Playwright scenarios: command-bar peek, open-full-detail navigates + closes, saved-view builder row peek, triage related peek, two panels (second replaces first), keyboard Enter/Escape, cache single-call, mobile tap → click peek.

### Performance discipline verified

- **Peek endpoint p50 < 100ms / p99 < 300ms** (BLOCKING). Actual: **p50=3.7ms / p99=7.4ms** across 24 mixed samples.
- **Hover debounce 200ms**. Asserted in vitest (`hover open without close fires fetch after 200ms` + `cancel before debounce expires`).
- **Session cache 5-min TTL**. Asserted in vitest (`repeat open of same entity hits cache (single network call)`) and Playwright (`peek_cache_single_call`).
- **AbortController cancels superseded fetches**. Asserted in vitest (`close clears state to idle and aborts in-flight request`).
- **Arc telemetry records peek_fetch**. Asserted in backend tests (success + errored both record).

### Context panel wiring status (per requirement 13)

- ✅ **Wired**: `document_preview` (Phase 5), `ai_question` (follow-up 2), `related_entities` (follow-up 4)
- 🔵 **Remaining stubs**: `saved_view`, `communication_thread`
  - `saved_view` panel — needs per-item scoping in Phase 2 executor (current executor takes a static config; embedding a saved view scoped to "items related to current triage item" requires an executor extension for per-row filter injection)
  - `communication_thread` panel — needs platform messaging system; no platform messaging primitive exists today

### Arc completion (per requirement 14)

**The UI/UX arc plus all four post-arc follow-ups are complete.** Seven platform primitives established by Phases 1-7:

1. Command bar (Phase 1)
2. Saved views (Phase 2)
3. Spaces (Phase 3)
4. Natural language creation (Phase 4)
5. Triage workspace (Phase 5)
6. Morning + evening briefings (Phase 6)
7. Polish infrastructure (Phase 7)

Plus the 8th interaction-pattern primitive established by follow-up 4: **peek panels** (cross-cutting trigger surfaces, hover-vs-click discipline, session cache, mobile degradation). Arguably a primitive — six entity types ship today; new entity types add a builder + an existing trigger gets peek for free.

**The platform is ready for the September Wilbert meeting.** The arc plus follow-ups deliver every UX claim made in `CLAUDE.md` § 1a (command-bar-as-platform-layer, monitoring-through-hubs / acting-through-command-bar). All BLOCKING CI latency gates green; all 7 telemetry-tracked endpoints inside their budgets with substantial headroom.

**Remaining platform work is different-mode work outside this arc**: HR/Payroll integration via Check, Smart Plant pilot at Sunnycrest, vertical expansion (cemetery, crematory verticals beyond foundation work). None of these need re-opening any arc phase.

### Surprises worth recording

1. **The command bar adapter already had `result_entity_type` from Phase 1.** The peek-icon wire-up was a 2-line change to the adapter (propagate the field) plus the icon render in CommandBar.tsx. Phase 1 over-built the response shape with field-completeness in mind; that paid off in follow-up 4 with zero backend changes for surface 1.
2. **`_RELATED_ENTITY_BUILDERS` was already structured for cross-feature reuse.** Follow-up 2 built it for the AI question Q&A grounding. Follow-up 4 exposed it to the frontend via one small endpoint; the related-entities panel wiring was a small frontend component. Confirming the arc's pattern: build infra for the immediate feature in a way that the next feature gets it free.
3. **The 6 peek entity types didn't all live in one registry.** `task` is in Phase 5 direct-queries; `saved_view` is meta. The new `PEEK_BUILDERS` dict avoided forcing a unification — each builder is independent, takes a tenant + id, returns a typed shape. No cross-entity coupling.
4. **Briefing prompt v3 deferral was the right call.** Pursuing inline narrative tokens would have cost the same as everything else combined, with prompt-compliance risk per vertical and a re-seed dance. Using the existing `pending_decisions` typed list got 80% of the UX with 5% of the work.

### Verification

- `pytest tests/test_peek_api.py tests/test_peek_latency.py tests/test_triage_related_endpoint.py` → **21 passed**
- Adjacent backend regression (saved-views, spaces, triage, ai_question, briefings, command_bar, nl_creation) → **184 passed, no regressions**
- `npx vitest run` → **159 passed across 10 files**
- `npx tsc -b` → clean
- `npm run build` → clean

---

## Saved View Live Preview in Builder (UI/UX Arc Follow-up 3)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 55 saved-views regression (14 new follow-up 3 + 41 prior Phase 2) + 198 adjacent-phase regression — no pre-existing tests broken. 134 frontend vitest across 7 files (26 new follow-up 3: 5 debounce hook + 21 preview component helpers).

### What shipped

The builder stops being a blind submit-then-see cycle. As the user edits filters, sort, grouping, or presentation, a sticky preview pane on the right renders live against the caller's tenant. Delivers the explicit post-arc polish note from the Phase 2 bullet ("Live preview deferred as post-arc polish — users save then land on detail"). Hot-path cost stays inside the Phase 2 execute budget because the same executor backs both endpoints.

### Approved deviations from the spec (all 10 confirmations plus perf/test additions)

1. **New endpoint** `POST /api/v1/saved-views/preview` taking `{ config }` body. Server-only override `limit → min(limit or 100, 100)`. Returns standard `SavedViewResult`. Registered under arc-telemetry key `saved_view_preview`.
2. **BLOCKING CI gate** at `test_saved_view_preview_latency.py` — p50 < 150 ms / p99 < 500 ms, 20 samples sequential.
3. **`truncated` signal** derived client-side from `rows.length < total_count`. No new backend field.
4. **Mode-switch cache** fingerprint = `{query, limit, aggregation_mode ∈ {none, chart, stat}}`. Non-aggregation mode swaps reuse the cache; chart/stat swap-in refetches.
5. **Pre-render mode hint** lives in `SavedViewBuilderPreview` (NOT `SavedViewRenderer`). The shared renderer stays lean for detail page + widget callers.
6. **`useDebouncedValue`** extracted to `frontend/src/hooks/useDebouncedValue.ts` (~15 lines, 5 vitest). Migration of existing ad-hoc debouncers (cemetery-picker, funeral-home-picker, useDashboard, useNLExtraction, cemetery-name-autocomplete) explicitly NOT in scope — tracked in post-arc backlog.
7. **Layout refactor**: lg+ two-column (LEFT all config stacked, RIGHT sticky preview); <lg collapsible toggle with `localStorage` key `saved_view_preview_collapsed`.
8. **No state refactor.** Builder state was already centralized as a single `useState<SavedViewConfig>` — audit confirmed, zero restructure.
9. **Arc telemetry**: `saved_view_preview` added to `TRACKED_ENDPOINTS`. Middleware-style wrap in the route handler (`try/finally`). No cost field (preview doesn't hit Intelligence).
10. **`previewSavedView(config, {signal})`** client helper in `saved-views-service.ts` with AbortController support.

### Backend additions

- `backend/app/services/arc_telemetry.py` — extended `TRACKED_ENDPOINTS` with `saved_view_preview` as the sixth tracked key.
- `backend/app/api/routes/saved_views.py` — new `_PreviewRequest` Pydantic body + `POST /preview` route. Reuses `SavedViewConfig.from_dict` for parse, `execute()` for dispatch, existing `ExecutorError → HTTP 400` translation. Telemetry wrapped in try/finally. Handler is ~60 lines.
- `backend/scripts` — no seed script needed. Preview reuses the Phase 2 executor + entity registry + permission layer unchanged.

### Frontend additions

- `frontend/src/hooks/useDebouncedValue.ts` — reusable `<T>(value, ms): T` hook. 15 lines. `window.setTimeout` + cleanup.
- `frontend/src/hooks/useDebouncedValue.test.ts` — 5 vitest scenarios (initial sync return, update propagation after delay, rapid-update coalescing, unmount-before-flush safety, delayMs change restarts timer).
- `frontend/src/services/saved-views-service.ts` — `previewSavedView(config, options)` helper with AbortSignal pass-through.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.tsx` — ~350 lines. Exports main `SavedViewBuilderPreview` + three helpers (`computeFingerprint`, `aggregationModeOf`, `requiredSubConfigHint`). Composition: `useDebouncedValue(config, 300ms)` → effect fires `previewSavedView(debouncedConfig, {signal})` → AbortController cancels supersession → cache-key check short-circuits non-aggregation mode swaps → `SavedViewRenderer` renders. Pre-render guard detects missing required sub-config per mode (kanban needs group_by_field + card_title_field; calendar needs date_field + label_field; cards needs title_field; chart needs chart_type + x_field + y_aggregation; stat needs metric_field + aggregation) and renders targeted `EmptyState` copy pointing at Presentation panel. Includes a `SavedViewBuilderPreviewPanel` wrapper with collapse header for potential embedded uses.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.test.tsx` — 21 vitest scenarios covering `aggregationModeOf` (7), `computeFingerprint` (7: non-aggregation mode swap → same fingerprint, chart/stat swap → different, chart x_field change → different, filter value change → different, filter field change → different, stable-across-identity-different-configs), `requiredSubConfigHint` (12: list/table null, kanban group_by/card_title/fully-configured, calendar date/label, cards title, chart, stat, stat fully-configured).
- `frontend/src/pages/saved-views/SavedViewCreatePage.tsx` — layout refactor. Two-column grid at `lg+` (3fr:2fr split — config dominant, preview readable). Sticky preview with `top-4`. Mobile toggle button (`lg:hidden`) rendered in the header next to Save. Preview mobile render (`lg:hidden`) on top of the form when expanded. `localStorage` read synchronously on first render with viewport-width default.
- `frontend/tests/e2e/saved-view-builder-preview.spec.ts` — 8 Playwright scenarios (builder_mounts_preview_pane, preview_populates_on_load, mode_swap_reuses_cache, debounce_coalesces_fast_typing, invalid_filter_inline_error, kanban_missing_group_by_hint, mobile_preview_toggle, refresh_button_bypasses_debounce).

### Performance discipline verified

- **Mode-only swap no-refetch**: Playwright scenario `mode_swap_reuses_cache` observes `/api/v1/saved-views/preview` POST count; swapping list→table→cards→list fires ZERO new calls beyond the initial mount.
- **Keystroke hammering**: `debounce_coalesces_fast_typing` fills the title field (not part of config) and asserts call count unchanged. Config-touching rapid edits are bounded by the 300ms debounce; AbortController cancels stale fires.
- **Telemetry overhead**: preview latency at p99=12.0ms INCLUDES the telemetry record() + try/finally wrap; overhead is well under the 5ms sub-gate implied by the measurements.

### BLOCKING CI gate

`backend/tests/test_saved_view_preview_latency.py`:
- Target: p50 < 150 ms, p99 < 500 ms (20 samples sequential, 1000 sales_order fixture, 4 mixed shapes: list + filter, table + in-filter, kanban + grouping, chart + aggregation)
- **Actual: p50 = 8.5 ms, p99 = 12.0 ms** — 17×/41× headroom
- Second test guards the 100-row cap at scale (1000 rows seeded, `limit=1000` request → 100 rows returned, `total_count=1000`)

### Verification

- `pytest tests/test_saved_view_preview.py tests/test_saved_view_preview_latency.py` → **16 passed**
- Saved-views regression (5 files): 55 passed
- Adjacent-phase regression (10 files covering spaces, task_and_triage, ai_question, briefings, command_bar_retrieval, nl_creation_backend): **198 passed** — no regressions
- Frontend `tsc -b` clean. `npm run build` clean.
- Frontend vitest full suite: **134 tests across 7 files** (5 new debounce + 21 new preview = 26 new; 108 pre-existing).

### Follow-up 3 ≠ architecture introduction

This was a composition over existing primitives: Phase 2 executor + Phase 7 useRetryableFetch pattern + Phase 2 SavedViewRenderer + Phase 7 EmptyState/InlineError/SkeletonCard + Phase 4 debounce idiom extracted to a reusable hook. Zero new tables. One new endpoint. One new component. ~500 net new lines of code excluding tests. The architectural discipline established by follow-ups 1 and 2 (extend existing arc primitives without new architecture) held for the third in the sequence.

### Ready for follow-up 4: Peek panels

Peek panels (last follow-up) can slot into this same composition posture. Likely shape: a slide-over that renders a saved view OR entity detail inline without navigating. The preview pane's "render a saved view from a transient config" contract could be a direct precedent for the "render entity-scoped saved view in a slide-over" pattern. The cache + debounce + abort primitives are all reusable.

---

## AI Questions in Triage Context Panels (UI/UX Arc Follow-up 2)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 138 across Spaces + Triage + AI-Question regression (33 new follow-up tests; 110 adjacent-phase tests also green — no regressions)

### What shipped

**The first wired interactive context panel in the triage workspace.** Phase 5 shipped the pluggable context panel architecture with six types; only `document_preview` was actually wired to real functionality. The remaining five (`saved_view`, `communication_thread`, `related_entities`, `ai_summary`, `ai_question`) rendered "wiring lands in Phase 6" placeholders. Follow-up 2 wires `ai_question`, establishing the interaction pattern (input-focus suppression, ephemeral session state, vertical-aware prompts, rate-limited 429 with structured body) for the remaining stubs when they land post-arc.

Users open a triage queue, click into the "Ask about this task" (or "Ask about this certificate") panel, and type a question. Claude answers grounded in the item record + related entities + vertical-aware terminology. Confidence dot (green/amber/gray). Source references rendered as clickable chips.

### Approved deviations from the spec

1. **Reused existing Phase 5 prompts via v1→v2 Option A bump.** `triage.task_context_question` + `triage.ss_cert_context_question` were authored Phase-5-end with Q&A-shaped variables (`user_question`) — naming revealed intent. No new `triage.ask_question` prompt seeded.
2. **No `AIQuestionPanelConfig` subclass.** Flat `ContextPanelConfig` extended with optional `suggested_questions: list[str]` + `max_question_length: int = 500`.
3. **Dropped `include_saved_view_context`.** Added `_RELATED_ENTITY_BUILDERS` dict parallel to `engine._DIRECT_QUERIES` instead. Per-queue builders fetch denormalized related data without needing Phase 2 executor extensions for per-row scoping.
4. **Centralized confidence mapping** in `app/services/intelligence/confidence.py::to_tier` (≥0.80 high, ≥0.50 medium, else low). None + bad input collapse to low defensively. Reusable by future AI-response consumers.
5. **Rate limit returns structured 429** with `{code: "rate_limited", retry_after_seconds, message}` + `Retry-After` header; frontend translates to a friendly toast ("Pausing AI questions for a moment — try again in Ns").

### Backend additions

- `backend/app/services/intelligence/confidence.py` — centralized `to_tier(score)` utility.
- `backend/app/services/triage/ai_question.py` — ~350 lines. Public: `ask_question`, `AskQuestionResponse`, `SourceReference`, `RateLimited`, typed error subclasses. Private: `_RELATED_ENTITY_BUILDERS` dict, sliding-window rate limiter (`deque` of monotonic timestamps per user_id, threading.Lock for safety), `_reset_rate_limiter` test seam.
- `backend/app/services/triage/types.py` — `ContextPanelType.AI_QUESTION = "ai_question"`; `ContextPanelConfig` gains `suggested_questions: list[str] = []` + `max_question_length: int = 500`.
- `backend/app/services/triage/platform_defaults.py` — both seeded queues now declare an `ai_question` panel. task_triage cites `triage.task_context_question` + suggestions ["Why is this task urgent?", "What's the history with this assignee?", "Are there related tasks I should know about?"]. ss_cert_triage cites `triage.ss_cert_context_question` + suggestions ["What's the history with this funeral home?", "Are there previous certificates for this product?", "Why was this approval flagged?"].
- `backend/app/api/routes/triage.py` — new `POST /sessions/{session_id}/items/{item_id}/ask` endpoint. Translates `RateLimited` → structured 429 body + `Retry-After` header; other `TriageError` subclasses go through the shared `_translate` helper.
- `backend/scripts/seed_intelligence_followup2.py` — Option A idempotent v1→v2 bump. Adds `vertical`, `user_role`, `queue_name`, `queue_description`, `item_type` variables + the VERTICAL-APPROPRIATE TERMINOLOGY Jinja block mirroring Phase 6's pattern. First run: `bumped_to_v2=2`. Re-run: `skipped_customized=2` (Phase 6 multi-version guard correctly protects admin customizations).

### Frontend additions

- `frontend/src/types/triage.ts` — `ContextPanelType` extended with `"ai_question"`; `TriageContextPanelConfig` gains `suggested_questions` + `max_question_length`; new runtime shapes `ConfidenceTier`, `TriageQuestionSource`, `TriageQuestionAnswer`, `TriageRateLimitedBody`.
- `frontend/src/services/triage-service.ts` — `askQuestion(sessionId, itemId, question)` + typed `TriageRateLimitedError` class that wraps the structured 429 body.
- `frontend/src/components/triage/AIQuestionPanel.tsx` — ~260 lines. Suggested-question chips, textarea with character counter, ⌘↵ / Ctrl+↵ submit, inline error surface with retry, confidence dot (emerald / amber / muted), source-reference chips with routing (`task → /tasks/:id`, `sales_order → /order-station/orders/:id`, `customer → /vault/crm/companies/:id`, etc.). Per-item session history resets via `useEffect` on `itemId` change.
- `frontend/src/components/triage/TriageContextPanel.tsx` — dispatcher extended with `"ai_question"` case; new `sessionId` prop threaded from `TriagePage.tsx`.

### Input-focus discipline (requirement 6)

Phase 5's `useTriageKeyboard` hook already suppresses triage shortcuts when focus is on INPUT/TEXTAREA/SELECT/contenteditable/role=textbox (`hooks/useTriageKeyboard.ts:36-41`). Verified by the `keyboard_shortcut_doesnt_fire_action` Playwright scenario: typing "n" in the textarea does NOT fire task_triage's Skip action. No Phase 5 modification needed.

### Tests

- `backend/tests/test_ai_question_service.py` — 17 tests. Confidence tier boundaries (4), service orchestration happy path + medium-confidence tier (2), related-entity builder invocation (1), malformed/error responses (2), question validation (2), item-not-found (1), rate limiting (per-user + overhead sub-gate, 3), preconditions (no-panel, cross-user, 2).
- `backend/tests/test_triage_ai_question_api.py` — 8 tests. Happy-path roundtrip, session/item 404s, question too long (400), empty question (Pydantic 422), auth required, cross-user isolation, structured 429 body + Retry-After header.
- `backend/tests/test_ai_question_prompt_terminology.py` — 6 tests. Parametrized over 4 verticals (manufacturing / funeral_home / cemetery / crematory) asserting correct USE + DO-NOT-USE lines in rendered prompt. Unknown-vertical fallback. SS cert prompt also renders the block (both v2 bumps verified).
- `backend/tests/test_ai_question_latency.py` — 2 BLOCKING CI gates. `/ask` endpoint: **p50 = 8.2 ms / p99 = 33.3 ms** vs target 1500/3000ms (180× p50 headroom — orchestration-only; real Haiku in prod adds ~350ms). Confidence mapping: effectively 0ms per call (sub-1ms budget met).
- `frontend/tests/e2e/ai-question-panel.spec.ts` — 7 Playwright scenarios. Panel renders, suggested-chip populates input, character counter updates, keyboard shortcut suppression, submit-API-contract roundtrip (mocked), rate-limit friendly toast (mocked 429), backend API shape smoke (live or 502 both accepted).

### Verification

- `pytest tests/test_ai_question_service.py tests/test_triage_ai_question_api.py tests/test_ai_question_prompt_terminology.py tests/test_ai_question_latency.py` → **33 passed**.
- Full triage + spaces regression (9 test files, 138 tests) → **138 passed**. No pre-existing tests broken.
- Adjacent phases (briefings, briefing terminology, command-bar retrieval, NL creation, saved views) → **110 passed**. Vertical-aware pattern transplanted cleanly.
- Frontend `tsc -b` clean. `npm run build` clean.
- Seed script first run: `bumped_to_v2=2` (both triage prompts advanced v1→v2). Idempotent re-run: `skipped_customized=2` (Phase 6 multi-version guard correctly protects re-seeded state).

### Establishes precedent for future interactive panels

Phase 5 shipped six context panel types; only `document_preview` was wired. Follow-up 2 wires `ai_question` — **the first interactive context panel in the triage system**. The patterns established here (input-focus suppression via the existing hook, ephemeral session state on the frontend, per-queue builder dict for related entities, structured 429 with friendly toast) are the blueprint for wiring the remaining four (`ai_summary`, `saved_view`, `communication_thread`, fully-interactive `related_entities`) when they come up post-arc. That's why the dispatcher's "wiring lands post-arc" placeholders explicitly point at this precedent rather than a specific phase number.

### Ready for follow-up 3

Saved view live preview in builder. Post-follow-up-2 platform state: the arc has shipped + two follow-ups proven-pattern (follow-up 1 extended a Phase 3 registry; follow-up 2 extended a Phase 5 primitive with an interactive panel + vertical-aware prompt bump). Remaining two follow-ups stay architecturally cheap.

---

## Space-Scoped Triage Queue Pinning (UI/UX Arc Follow-up 1)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 103 across Phase 3 + Phase 5 + follow-up regression (17 new follow-up tests in `test_space_pins_triage_queue.py`, 86 prior-phase spaces/triage tests unchanged)

### What shipped

Triage queues become a third pin target type alongside saved views
and nav items. A director on the funeral_home vertical opens their
auto-seeded Arrangement space and the first pin in the sidebar is
their Task Triage queue with a pending-item count badge — one click
opens the keyboard-driven workspace. A production manager on a
manufacturing tenant gets the same treatment on their Production
space.

Under the hood:

- `PinConfig.pin_type` literal extended with `"triage_queue"` on
  backend and frontend types (`backend/app/services/spaces/types.py`,
  `frontend/src/types/spaces.ts`).
- `ResolvedPin` gains `queue_item_count: int | None` (null for
  non-triage pins and for unavailable queues).
- `TriageQueueConfig` gains `icon: str = "ListChecks"`. Platform
  defaults: `task_triage` → `"CheckSquare"`,
  `ss_cert_triage` → `"FileCheck"`. Frontend `PinnedSection.ICON_MAP`
  gained all three names — verified present so no pin falls through
  to the `Layers` default silently.
- `_resolve_pin` has a new `triage_queue` branch that reads the
  queue config from the Phase 5 registry via
  `triage.registry.get_config` and pulls the pending count via
  `triage.engine.queue_count`. On access-denied or unknown-queue the
  pin renders with `unavailable=true, queue_item_count=null` and no
  href — same UX as a saved-view pin whose view was deleted.
- Permission check is **batched once per space resolution**: if any
  pin on the space has `pin_type="triage_queue"`, `_resolve_space`
  calls the new `_accessible_queue_ids_for_user(db, user)` helper
  exactly once and passes the set down to each `_resolve_pin`. Spaces
  without triage pins pay zero permission lookups.
- Seed templates for (`funeral_home`, `director`) Arrangement and
  (`manufacturing`, `production`) Production both start with
  `PinSeed(pin_type="triage_queue", target="task_triage")` as the
  first pin. Other role/vertical pairs stay unchanged per approved
  scope.
- `add_pin` validation tuple extended to accept `triage_queue`.
  Idempotent: same (pin_type, target_id) returns the existing pin.
- `PinStar` component accepts `pinType: "triage_queue"`; TriageIndex
  (`/triage`) cards render a PinStar in the card header.
- `PinnedSection` renders a pending-count badge on available
  `triage_queue` pins (`queue_item_count > 0`) in the active-space
  accent color. Capped at `99+` to keep the row tidy. Hidden on row
  hover so the unpin X has room.
- Space-scoped nav preference preserved: the pin shortcuts (PinStar
  toggle, Cmd+[ / Cmd+] space switch, Cmd+Shift+1..5) work on the
  new pin type without any additional wiring — Phase 3 keyboard
  listeners already iterate the active space's pins generically.

### API contract changes (additive, backward-compatible)

- `POST /api/v1/spaces/{id}/pins` now accepts
  `pin_type: "triage_queue"` with `target_id: <queue_id>` (e.g.
  `"task_triage"`).
- `_PinResponse` ships a new `queue_item_count: int | None` field.
  Existing consumers ignore unknown fields; no frontend code that
  already reads the response shape breaks.

### Test additions

- Backend: `backend/tests/test_space_pins_triage_queue.py` — 17 tests
  across 6 test classes. Registry icon presence, seed-template
  content, resolver behavior (available / label-override /
  unavailable-by-vertical / unknown-queue), batched access-lookup
  perf (spy asserts `_accessible_queue_ids_for_user` called exactly
  once per space with ≥1 triage pin, zero when no triage pins),
  add_pin validation + idempotency, full-stack API roundtrip +
  cross-user isolation.
- Playwright: `frontend/tests/e2e/space-triage-pin.spec.ts` — 5
  scenarios covering the POST shape (icon, href, queue_item_count),
  PinStar presence on /triage cards, sidebar reflection of a newly
  pinned queue, unavailable pin wire contract, list-endpoint shape
  for every triage pin.

### Verification

- `pytest tests/test_spaces_unit.py tests/test_spaces_api.py
  tests/test_task_and_triage.py tests/test_space_pins_triage_queue.py`
  → **103 passed**.
- Frontend `tsc -b` clean.
- ICON_MAP acceptance criterion: grepped
  `frontend/src/components/spaces/PinnedSection.tsx`, confirmed
  `CheckSquare`, `FileCheck`, `ListChecks` all imported from
  `lucide-react` and registered in ICON_MAP. No pin renders with the
  Layers fallback for shipped queue icons.

### Design decisions / deviations (approved)

- Queue icon sourced from `TriageQueueConfig.icon` (authoritative)
  rather than a frontend queue_id → icon lookup table. Single source
  of truth; tenant-customized queues can override via vault_item
  metadata without a frontend change.
- Seeded pin scope limited to (`funeral_home`, `director`) and
  (`manufacturing`, `production`) per spec. Other role templates
  unchanged; users in other roles can pin queues manually via the
  PinStar on `/triage`.
- Template additions do NOT backfill for already-seeded users
  (matches Phase 3 precedent). Existing director/production users
  can pin manually; next fresh seed picks up the template.
- Role slug for manufacturing production template is `"production"`
  (existing convention), not `"production_manager"` as a spec draft
  mentioned.

---

## Polish and Arc Finale (Phase 7 of UI/UX Arc — FINAL)

**Date:** 2026-04-20
**Migration head before:** `r35_briefings_table`
**Migration head after:** `r35_briefings_table` (no new migration — zero new tables per approved scope)
**Tests passing:** 288 across Phase 1-7 regression (8 new Phase 7 contrast + focus-ring tests; 280 prior-phase tests unchanged)

### What shipped

**Shared UI primitives** (`frontend/src/components/ui/`):
- `empty-state.tsx` — `EmptyState` with 3 tones (neutral / positive / filtered) × 3 sizes (default / sm / xs). Optional icon + title + description + action + secondaryAction.
- `skeleton.tsx` — `Skeleton` base + `SkeletonLines` / `SkeletonCard` / `SkeletonRow` / `SkeletonTable` composites. All use `motion-safe:animate-pulse`.
- `inline-error.tsx` — `InlineError` with role=alert + aria-live + optional retry handler + severity variants.

**Hooks** (`frontend/src/hooks/`):
- `useRetryableFetch.ts` — generic auto-retry-once (~1s backoff) + manual `reload()`.
- `useOnboardingTouch.ts` — server-side dismissal via `User.preferences.onboarding_touches_shown`; cross-device; module-scoped session cache for efficiency.
- `useOnlineStatus.ts` — `navigator.onLine` + online/offline event listener.

**New components:**
- `components/onboarding/OnboardingTouch.tsx` — first-run tooltip with auto-dismiss option + positioned anchoring
- `components/core/KeyboardHelpOverlay.tsx` — `?`-key context-aware shortcut help overlay (mounted at App root)
- `components/core/OfflineBanner.tsx` — global top banner when `navigator.onLine === false`

**Empty state replacements (10 surfaces):**
- 7 saved view renderers: List, Table, Kanban, Cards, Chart (with `BarChart3` icon), Stat (inline "No data for selected period"), Calendar (per-month empty-message below grid)
- TasksList: two states — empty-all (positive tone with CTA) vs empty-filtered (clear-filters action)
- TriagePage caught-up (positive tone, session stats + back-link)
- TriageIndex (contextual messaging with link to settings)
- CommandBar no-results (with "try: 'new case', 'my invoices', 'switch to production'" hints)
- SavedViewsIndex (icon + CTA)
- BriefingPage (graceful fallback when scheduler hasn't run yet)

**Skeleton replacements (5 surfaces):** BriefingPage (narrative + 2 section cards), BriefingCard (3-line narrative), SavedViewsIndex (3 card grid), TasksList (5-row table skeleton), TriagePage (card + palette skeleton), TriageIndex (2 queue cards).

**Error retry:**
- `BriefingPage` auto-retries once on load failure before surfacing the error; manual retry button via `InlineError`.
- `Triage action retry` — action failures no longer transition session to error state; toast fires, status returns to idle, item stays in queue, keystroke not lost. Triage-context re-throws after clearing status so caller's toast still fires.
- `SavedViewsIndex` error renders `InlineError` with hint.
- `TriageIndex` error renders `InlineError` with retry.

**First-run tooltips (5 wired):**
- Backend: `GET/POST/DELETE /api/v1/onboarding-touches/{key}` reading/writing `User.preferences.onboarding_touches_shown`.
- Tooltips: command bar (`command_bar_intro` inside the modal), saved view page (`saved_view_intro` in page header), space switcher (`space_switcher_intro` only when 2+ spaces), triage page (`triage_intro`), briefing page (`briefing_intro`).
- Client hook `useOnboardingTouch` uses a module-scoped session promise to avoid 5 simultaneous fetches across 5 surfaces; optimistic dismissal with server fire-and-forget.

**ARIA + aria-live pass (4 arc surfaces):**
- CommandBar: `role=dialog` + `aria-modal` on overlay; `aria-label="Command bar"`; input as `role=combobox` + `aria-controls=command-bar-results` + `aria-expanded` + `aria-autocomplete=list` + `aria-describedby`; results container with `role=listbox` + `aria-live=polite`; footer with id hint.
- NLOverlay: body region with `role=region` + `aria-label` + `aria-live=polite` + `aria-busy={isExtracting}`. Error block upgraded to `role=alert` with hint.
- TriagePage: current-item section with `role=region` + `aria-label="Current triage item"` + `aria-live=polite` + `aria-busy`.
- BriefingPage: narrative CardContent with `role=region` + `aria-label="Briefing narrative"` + `aria-live=polite`.

**`?`-key help overlay:** `KeyboardHelpOverlay` at App root. Listens to `?` globally (ignoring inputs / contenteditable); opens modal showing context-aware shortcut sections: always Global + CommandBar + Spaces; adds Triage when on `/triage/*`; adds Tasks when on `/tasks/*`. Escape or `?` again dismisses. motion-safe animate-in.

**Mobile fixes:** 44px `min-h-[44px]` on TriageActionPalette decision buttons, TriageFlowControls snooze presets, BriefingPreferences channel/section toggles. BriefingPreferences grid collapsed from `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` so the time picker + channel buttons stack cleanly on 375px. CalendarRenderer day cells changed to `min-h-[70px] sm:min-h-[92px]` + grid wrapper `overflow-x-auto` for narrow viewports.

**Offline banner:** `OfflineBanner` at App root above impersonation banner. `useOnlineStatus` subscribes to `online`/`offline` events. Renders an amber strip with `WifiOff` icon + "You appear to be offline. Changes will sync when reconnected." Deliberately simple — no proactive connectivity probe (that's post-arc observability).

**prefers-reduced-motion global retrofit:** Added to `frontend/src/index.css` as a blanket `@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; scroll-behavior: auto !important; } }` block. Handles 40+ pre-existing transitions across Phase 1-6 + shadcn/ui + tw-animate-css without needing to touch each file. Phase 7 new components use `motion-safe:` variants natively.

**Telemetry dashboard** (platform-admin-gated, mounted at `/bridgeable-admin/telemetry`):
- Backend `app/services/arc_telemetry.py` — thread-safe in-memory rolling latency buffer (1000 samples cap) per endpoint + error counter. `record(endpoint, latency_ms, errored)` called via try/finally on the 5 arc endpoints (command_bar_query, saved_view_execute, nl_extract, triage_next_item, triage_apply_action). `snapshot()` returns p50/p99/counts.
- Backend `app/api/routes/admin/arc_telemetry.py` — `GET /api/platform/admin/arc-telemetry` returns endpoint snapshot + `intelligence_executions` aggregations over 24h/7d/30d windows + per-caller-module cost breakdown (24h).
- Frontend `bridgeable-admin/pages/ArcTelemetry.tsx` — endpoint latency table + 3 Intelligence window cards + caller-module cost table + honest banner: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **No new database table.** Intelligence aggregations persist via existing `intelligence_executions` rows.

**Contrast verification + accent remediation:** `backend/tests/test_arc_accent_contrast.py` (5 tests) mirrors the 6 space accents from `frontend/src/types/spaces.ts` and asserts:
- Hex format valid for all 6 × 3 colors
- Foreground on white ≥ 4.5:1 (WCAG AA normal text) — ALL 6 PASS
- Accent on white ≥ 3.0:1 (WCAG AA large text) — ALL 6 PASS
- Foreground on accent-light chip ≥ 4.5:1 — ALL 6 PASS
- Accent distinguishable from preset fallback (except `neutral` which deliberately matches) — ALL PASS

**Zero accent remediation needed.** All 6 were already WCAG AA compliant.

**Focus ring visibility remediation:** `backend/tests/test_arc_focus_ring_contrast.py` (3 tests) verifies the `--ring` color passes WCAG 3:1 non-text-UI contrast against:
- Pure white — **required bump from `oklch(0.708 0 0)` to `oklch(0.48 0 0)`**
- Each of the 6 accent-light chip backdrops — now passing with new value

Fix: single-line change in `frontend/src/index.css` light-mode `:root` block. Test includes a guard (`test_focus_ring_lightness_matches_index_css`) that parses the CSS file + asserts the constant matches — prevents drift.

**Micro-interactions (motion-safe):**
- NL extraction field entrance: `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1 motion-safe:duration-200` on each field row
- Triage item transition: `key={item.entity_id}` forces remount; wrapper has `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-200`

### Design decisions / deviations (approved)

- **Arc finale docs moved up to #11-12 (before micro-interactions / contrast / focus-ring tests) per approved refinement** — but in execution, the refactor audit surfaced that telemetry (#12) + contrast (#14) + focus-ring (#15) should ship first so docs can reference real data. Final order: steps 1-10 → 12 → 13 → 14 → 15 → 11. Outcome matches intent: docs written with clear head, deliver accurate performance envelope + post-arc backlog.
- **Cross-arc layout consistency dropped entirely** per approved refinement. Per-page max-width variation preserved (different content types, different ideal widths).
- **Demo flow scripts added to UI_UX_ARC.md** per approved refinement — 5 rehearsable demos with exact keystroke-level scripts for September Wilbert meeting.
- **Telemetry honest-expectation-setting** on page itself: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **prefers-reduced-motion** non-negotiable: global CSS block retrofit + `motion-safe:` variants on all Phase 7 new transitions.
- **Two persistence layers** for tooltip dismissal preserved (as approved): `useOnboardingTouch` = server-side cross-device; `HelpTooltip` = localStorage device-local. Not merged.
- **Contrast + focus-ring** verified programmatically, not just documented. All accents pass; focus ring required one-line `--ring` darkening to pass WCAG 3:1.

### Test additions

- `backend/tests/test_arc_accent_contrast.py` (5 tests)
- `backend/tests/test_arc_focus_ring_contrast.py` (3 tests)
- 8 total new Phase 7 backend tests (all passing)
- All 280 Phase 1-6 tests still pass unchanged
- tsc 0 errors
- All 5 BLOCKING latency gates still green

### Verification

- **288 backend tests pass** across Phase 1-7 regression (280 prior + 8 Phase 7 new) — no regressions
- **BLOCKING latency gates (all 5) unchanged and green:**
  - command_bar_query: p50 = 5.0 ms, p99 = 6.9 ms
  - saved_view_execute: p50 = 15.4 ms, p99 = 18.5 ms
  - nl_extract (no AI): p50 = 5.9 ms, p99 = 7.2 ms
  - triage_next_item: p50 = 4.8 ms, p99 = 5.8 ms
  - triage_apply_action: p50 = 9.7 ms, p99 = 13.5 ms
  - briefing_generate (AI stubbed): p50 = 28.9 ms, p99 = 32.0 ms
- **WCAG AA contrast: all 6 space accents pass** (zero remediation needed)
- **Focus ring: WCAG 3:1 passes against white + all 6 accent-light backdrops** (after `--ring` bump)
- tsc 0 errors
- Backend imports cleanly including new routes + services

### Arc totals (Phases 1-7 complete)

| Metric | Count |
|---|---|
| Phases shipped | 7 |
| Platform primitives established | 7 |
| Database migrations (arc-specific) | 5 (r31, r32, r33, r34, r35) |
| New tables | 4 (triage_sessions, triage_snoozes, tasks, briefings) |
| Backend tests | 288 (no regressions) |
| BLOCKING CI latency gates | 5 (all green) |
| BLOCKING parity tests | 3 (SS cert triage — all green) |
| Playwright specs | 50+ across arc |
| Intelligence prompts seeded | 13+ |
| New API endpoints | ~60 |
| New shared frontend components | 8 (`EmptyState`, `Skeleton`+4 variants, `InlineError`, `OnboardingTouch`, `KeyboardHelpOverlay`, `OfflineBanner`, plus 3 per-primitive component sets from Phase 2-6) |
| Post-arc backlog items | ~45 (documented in `UI_UX_ARC.md`) |

### Post-arc cleanup items (documented, NOT Phase 7 work)

All 45+ items consolidated in `UI_UX_ARC.md` under "Post-arc Backlog". The most impactful:
1. Rename `/briefings/v2/*` → cleaner REST (Phase 6 cleanup)
2. Consolidate `employee_briefings` + `briefings` tables (Phase 6 cleanup)
3. Migrate legacy `MorningBriefingCard` consumers to new `BriefingCard` (Phase 6 → Phase 7 cleanup — legacy preserved per coexist strategy)
4. Build native mobile redesigns of arc surfaces (Phase 7 scope cut — mobile was functional-only)
5. Advanced observability (Phase 7 telemetry was minimal by design)
6. External accessibility audit (Phase 7 scope cut — verified programmatically only)

### What the arc enables

The September 2026 Wilbert licensee meeting demo reaches its moment: a funeral director opens the command bar on the Bridgeable platform, types one sentence, watches the platform extract 5 structured fields in under a second, presses Enter, and has a fully-populated case record. The demo flow is documented keystroke-by-keystroke in `UI_UX_ARC.md`. Rehearsal checklist included.

Beyond the demo: the seven primitives compose. Every future feature inherits:
- Command bar surface via registry entry
- Saved views for any list/dashboard
- Space-aware context via active_space_id
- NL creation for any new entity type (append to entity_registry)
- Triage workspace for any decision stream (append to platform_defaults)
- Briefings can emphasize the feature by exposing a data source
- Polish primitives (EmptyState/Skeleton/InlineError) for every empty/loading/error state

**Arc complete. Platform ready for September.**

---

## Arc-level summary table (all 7 phases)

| Phase | Dates | Migration | Tests | Key primitive |
|---|---|---|---|---|
| 1 — Command Bar | Apr 2026 | r31 | 116 | `POST /command-bar/query` |
| 2 — Saved Views | Apr 2026 | r32 | 46 | `vault_items` saved_view_config |
| 3 — Spaces | Apr 2026 | (none — User.preferences) | 64 | `User.preferences.spaces` |
| 4 — NL Creation | Apr 2026 | r33 | 87 | Structured + resolver + AI pipeline |
| 5 — Triage | Apr 2026 | r34 | 42 | Pluggable 7-component queue configs |
| 6 — Briefings | Apr 2026 | r35 | 36 | AI narrative + per-user sweep |
| 7 — Polish | Apr 2026 | (none) | 8 | Cross-cutting polish infrastructure |

---
## Morning and Evening Briefings (Phase 6 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r34_tasks_and_triage`
**Migration head after:** `r35_briefings_table`
**Tests passing:** 27 backend + 2 BLOCKING latency gates + 7 Playwright = 36 new, plus 280 Phase 1–6 regression green

### What shipped

**Backend**

- Migration `r35_briefings_table`: new `briefings` table coexisting with legacy `employee_briefings` (different semantics — `(user_id, briefing_type, DATE(generated_at))` partial unique allows morning + evening same day; legacy's `(company_id, user_id, briefing_date)` unique only allowed one per day)
- `app/models/briefing.py` — Briefing ORM + `BRIEFING_TYPES` literal
- `app/services/briefings/` package — 7 modules (types, preferences, data_sources, generator, delivery, scheduler_integration, __init__); **legacy context builders imported and reused verbatim**: `_build_funeral_scheduling_context`, `_build_precast_scheduling_context`, `_build_invoicing_ar_context`, `_build_safety_compliance_context`, `_build_executive_context`, `_build_call_summary`, `_build_draft_invoice_context`
- **Legacy blocklist → Phase 6 allowlist translation**: `seed_preferences_for_user` translates `AssistantProfile.disabled_briefing_items` (existing blocklist) to `BriefingPreferences.{morning,evening}_sections` (Phase 6 allowlist) via set subtraction; idempotent per role via `preferences.briefings_seeded_for_roles`
- 7 `/api/v1/briefings/v2/*` endpoints coexisting with legacy `/briefings/briefing` + `/briefings/action-items` + `/briefings/team-config` (route coexistence under same router, no renaming)
- `POST /v2/generate` uses explicit delete-then-create semantics for "regenerate today's" (deletes existing same-day-same-type row, inserts fresh)
- `scripts/seed_intelligence_phase6.py` — idempotent; seeds `briefing.morning` + `briefing.evening` prompts (Haiku simple, force_json, 2048 max_tokens, 0.4 temp) + 2 managed email templates (`email.briefing.morning` + `email.briefing.evening`) via Phase D-2 DocumentTemplate registry (no on-disk files per D-2/D-3 discipline)
- `job_briefing_sweep()` added to `scheduler.py` with `CronTrigger(minute="*/15")` — first per-user scheduled pattern on the platform
- Seed hook wired at `user_service.update_user`'s role-change site alongside Phase 2 saved_views + Phase 3 spaces seeds
- **BLOCKING CI gate** at `test_briefing_generation_latency.py` — p50 < 2000ms, p99 < 5000ms. Actual: **p50=28.9ms / p99=32.0ms** (69× / 156× headroom) with Intelligence monkey-patched to measure orchestration overhead
- **BLOCKING space-awareness tests** — parametrized × 3 spaces (Arrangement/Administrative/Production), intercepts Intelligence call, asserts `active_space_name` reaches prompt variables
- **BLOCKING Call Intelligence integration test** — `overnight_calls` None when no RC logs; populated with `{total, voicemails, ...}` when seeded RC log exists — preserves legacy `_build_call_summary` path verbatim
- **BLOCKING legacy coexistence tests** — `/briefings/briefing` + `/briefings/action-items` still 200; `briefing.daily_summary` prompt still active; legacy context builders still importable

**Frontend**

- `types/briefing.ts` — full mirrors of backend Pydantic shapes
- `services/briefing-service.ts` — 7-endpoint axios client
- `hooks/useBriefing.ts` — latest-briefing fetch + manual reload (no auto-refresh; scheduler owns backend generation)
- `pages/briefings/BriefingPage.tsx` (`/briefing` + `/briefing/:id`) — narrative card + collapsible structured-sections cards; Morning/Evening toggle; Regenerate + Mark-read buttons; queue_summaries deep-link to `/triage/:queueId`
- `components/briefings/BriefingCard.tsx` — new dashboard widget (opt-in mount); truncated narrative + "Read full briefing →" link
- `pages/settings/BriefingPreferences.tsx` (`/settings/briefings`) — optimistic-save toggles + time picker + channel + section allowlist
- 3 new routes in `App.tsx` (`/briefing`, `/briefing/:id`, `/settings/briefings`)
- 2 new cross-vertical command bar actions in `services/actions/shared.ts` — `navigate_briefing_latest` + `navigate_briefing_preferences`
- **Legacy `MorningBriefingCard` + `morning-briefing-mobile.tsx` + `BriefingSummaryWidget.tsx` UNCHANGED** — still mounted on `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` consuming legacy endpoints
- 7 Playwright specs in `frontend/tests/e2e/briefings-phase-6.spec.ts`

### Design decisions / deviations (approved)

- **Coexist strategy over absorb/replace** — `briefing_service.py` (1869 lines) represents months of customer ground-truth tuning. Phase 6 imports it as a dependency rather than rewriting. Legacy endpoints + components + prompts stay fully operational.
- **`/v2/*` route prefix** — intentionally ugly per approved spec item #3. Zero migration risk to existing consumers. Post-arc cleanup can rename.
- **Two tables (briefings + employee_briefings)** — different unique-constraint semantics make the two-table approach cleaner than extending the legacy table. `employee_briefings` stays read-only legacy.
- **Every-15-min global sweep with in-app per-user timing** — first per-user scheduled pattern. One APScheduler registration; sweep function computes per-user local time via `Company.timezone` + checks preference windows + DB idempotency. Documented as canonical pattern in CLAUDE.md §10.
- **Keyboard shortcut `G B` dropped** per approved scope cut — users pin `/briefing` to a space via PinStar + reach via `Cmd+Shift+N` using existing Phase 3 infrastructure.
- **`/v2/generate` delete-then-create** semantics discovered during latency-test development (second call inside same day hit the unique constraint). Explicit regenerate-today behavior chosen over upsert or 409 response. Post-arc rename to `/v2/regenerate` to signal intent.
- **Managed email templates only** — no `app/templates/email/` on-disk directory per D-2/D-3 discipline. Templates seeded as DocumentTemplate rows with `output_format="html"`.
- **Space-awareness via prompt Jinja branches, not variable substitution** — the `briefing.morning` + `briefing.evening` prompts contain `{% if active_space_name == "Arrangement" %}...{% endif %}` blocks that change section emphasis. The BLOCKING test asserts `active_space_name` reaches prompt variables (the hook Jinja branches on); visible output differentiation is Haiku's job and not asserted against live AI.

### Post-arc cleanup items (documented, NOT Phase 6 work)

1. Rename `/briefings/v2/*` → cleaner REST (e.g. `/briefings` replaces legacy; legacy moves to `/briefings/legacy/*`)
2. Consolidate `employee_briefings` + `briefings` tables — two-table approach is temporary coexist, not long-term
3. Migrate legacy `MorningBriefingCard` consumers at `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` to new `BriefingCard`
4. Retire `briefing.daily_summary` prompt once legacy `MorningBriefingCard` retires (both live together or both die together)
5. Revisit `briefing_service.py` for consolidation once legacy surfaces retire — 1869 lines of context-builder logic can fold into `briefings/data_sources.py` directly, removing the cross-package import dependency
6. Rename `/v2/generate` → `/v2/regenerate` for intent clarity
7. Add briefing AI learning (auto-drop sections user consistently skips) — post-arc
8. Add SMS/Slack/voice (TTS) delivery channels — post-arc
9. Add shared team briefings ("Today's Services" read-mostly view) — post-arc
10. Network-level cross-tenant briefings for licensee operators — post-arc

### Verification

- 280 Phase 1–6 backend tests passing (253 Phase 1–5 + 27 Phase 6 new)
- Both BLOCKING CI gates pass with massive headroom (p50=28.9ms vs 2000ms target)
- Space-awareness test parametrized × 3 spaces — all assert `active_space_name` reaches prompt variables
- Call Intelligence integration test — overnight_calls absent/present matches RC log state
- Legacy regression — `/briefings/briefing` + `/briefings/action-items` still 200; legacy prompt still seeded; legacy context builders still importable
- tsc clean (0 errors)
- 7 Playwright specs written (not run here — require live staging backend)

---

## Triage Workspace + actionRegistry Reshape + Task Infrastructure (Phase 5 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r33_company_entity_trigram_indexes`
**Migration head after:** `r34_tasks_and_triage`
**Tests passing:** 33 backend + 2 BLOCKING latency gates + 9 Playwright = 44 new, plus 253 Phase 1–5 regression green

### What shipped

**Backend**

- Migration `r34_tasks_and_triage`: 3 tables (`tasks`, `triage_sessions`, `triage_snoozes` — entity-type-agnostic with partial unique `uq_triage_snoozes_active WHERE woken_at IS NULL`) + GIN trigram index on `tasks.title` via CREATE INDEX CONCURRENTLY in autocommit_block
- `app/models/task.py` with TASK_PRIORITIES (low/normal/high/urgent) + TASK_STATUSES (open/in_progress/blocked/done/cancelled), polymorphic link via related_entity_type + related_entity_id
- `app/services/task_service.py` with full CRUD + `_ALLOWED_TRANSITIONS` state machine (invalid → 409)
- `app/api/routes/tasks.py` — 7 endpoints at `/api/v1/tasks/*` (list with filters + create + get + patch + soft-delete + complete + cancel)
- `app/services/triage/` package: types.py (Pydantic with schema_version="1.0", `extra="forbid"`, 7 component configs, typed errors) + registry.py (in-code singleton `_PLATFORM_CONFIGS` via register_platform_config — pattern pivot from vault_item because VaultItem.company_id NOT NULL; per-tenant overrides still vault-item-backed) + engine.py (start_session resumable via current_item_id + cursor_meta.processed_ids, next_item, apply_action handler→Playwright→workflow pipeline, snooze with partial-unique-index protection, queue_count, sweep_expired_snoozes; `_DIRECT_QUERIES` dispatch for entities not in Phase 2 saved-views registry — `_dq_task_triage`, `_dq_ss_cert_triage`) + action_handlers.py (HANDLERS dict — task.complete/cancel/reassign + **ss_cert.approve/void call SocialServiceCertificateService verbatim for parity** + skip + escalate) + embedded_actions.py (wraps existing PlaywrightScript + workflow_engine) + platform_defaults.py (two shipped queues: task_triage + ss_cert_triage registered at import time) + __init__.py (side-effect platform_defaults import BEFORE registry helpers)
- `app/api/routes/triage.py` — 9 endpoints at `/api/v1/triage/*`
- `app/services/nl_creation/entity_registry.py` extended with task entity (title/description/assignee via target="user"/due_date/priority); new `resolve_user()` in entity_resolver.py using ILIKE (no trigram index yet); EntityType literal extended; `_create_task` creator
- Phase 1 `command_bar/resolver.py` SEARCHABLE_ENTITIES adds task with url_template="/tasks/{id}"; `command_bar/registry.py` adds create.task with aliases new task / add task / create task / todo / new todo
- `backend/scripts/seed_triage_queues.py` — validates in-code platform configs loaded + seeds 2 Intelligence prompts (triage.task_context_question, triage.ss_cert_context_question) via Haiku simple route + force_json=True
- **BLOCKING CI gates** at `backend/tests/test_triage_latency.py`: next_item p50<100ms/p99<300ms + apply_action p50<200ms/p99<500ms. Actual: next_item p50=4.8ms / p99=5.8ms; apply_action p50=9.7ms / p99=13.5ms — 20×+ headroom on both
- **BLOCKING SS cert parity** — 3 tests in `TestSSCertTriageParity` class of `test_task_and_triage.py` asserting triage approve/void produces identical side effects (status transitions, approved_at/voided_at stamps, approved_by_id/voided_by_id, void_reason preservation) as legacy `/social-service-certificates` page

**Frontend**

- `services/actions/` package replaces legacy `core/actionRegistry.ts` (944 lines → split per-vertical files):
  - `types.ts` — rich ActionRegistryEntry (permission, required_module, required_extension, handler, playwright_step_id, workflow_id, supports_nl_creation, nl_aliases, keyboard_shortcut)
  - `registry.ts` — singleton + toCommandAction converter + getActionsForVertical/filterActionsByRole/matchLocalActions/getActionsSupportingNLCreation helpers + legacy CommandAction/RecentAction types preserved for render-time compat
  - `shared.ts` — 6 cross-vertical creates including NEW create_task + create_event with supports_nl_creation: true
  - `manufacturing.ts` — 57 mfg actions migrated verbatim
  - `funeral_home.ts` — 9 FH actions (case create with supports_nl_creation=true)
  - `triage.ts` — 3 NEW nav entries (workspace index, task queue, ss cert queue)
  - `index.ts` — side-effect registers all entries at module load
- 5 call sites migrated (CommandBar.tsx, SmartPlantCommandBar.tsx, CommandBarProvider.tsx, cmd-digit-shortcuts.ts, commandBarQueryAdapter.ts); old `core/actionRegistry.ts` deleted
- `components/nl-creation/detectNLIntent.ts` rewritten — derives ENTITY_PATTERNS at call time from `getActionsSupportingNLCreation()`; hand-maintained table eliminated. `NLEntityType` extended with "task"
- `types/triage.ts` — full mirrors of backend Pydantic shapes
- `services/triage-service.ts` — 9-endpoint client (fetchNextItem returns null on 204)
- `services/task-service.ts` — 7-endpoint client
- `contexts/triage-session-context.tsx` — TriageSessionProvider bootstraps config + session + first item; fire-and-forget endSession on unmount
- `hooks/useTriageKeyboard.ts` — shift/alt/meta/ctrl modifier support, skips inputs/textareas/contenteditable
- `components/triage/`: TriageItemDisplay (dispatches on display_component — task / social_service_certificate / generic), TriageActionPalette (reason modal with disabled-until-valid Confirm, kbd hints), TriageContextPanel (collapsible rail; document_preview live, saved_view/communication_thread/related_entities/ai_summary Phase-6-ready stubs), TriageFlowControls (snooze preset buttons)
- Pages: `pages/triage/TriageIndex.tsx` + `pages/triage/TriagePage.tsx` + `pages/tasks/TasksList.tsx` + `pages/tasks/TaskCreate.tsx` + `pages/tasks/TaskDetail.tsx`
- 5 new routes in App.tsx: `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/triage`, `/triage/:queueId`
- 9 Playwright specs in `frontend/tests/e2e/triage-phase-5.spec.ts`

### Design decisions / deviations

- **Platform-default triage queue configs as in-code singleton, not vault_items.** Initial design stored platform configs as vault_items with company_id=NULL (mimicking Intelligence prompts). VaultItem's NOT NULL constraint forced the pivot. Per-tenant overrides still use vault_items via the `triage_queue_config` item_type, read by `_tenant_overrides()` in registry.py.
- **Three source modes for queue configs.** Phase 2 saved_views SEARCHABLE_ENTITIES doesn't cover task or social_service_certificate. Rather than extend Phase 2's registry (coordination with Phase 5 cleanup note), introduced `source_direct_query_key` as third option dispatching to `_DIRECT_QUERIES` table in engine.py. Phase 2 entities use `source_inline_config`; per-tenant customization uses `source_saved_view_id`.
- **SS cert parity preserved by handler reuse, not copy.** `_handle_ss_cert_approve` calls `SocialServiceCertificateService.approve(cert_id, user_id, db)` verbatim; void is identical. Zero duplication. Parity test validates both paths produce identical DB state + timestamps + audit fields.
- **detectNLIntent duplication eliminated via registry flag.** The Phase 4 hand-maintained ENTITY_PATTERNS table is now derived at call time from entries flagged `supports_nl_creation: true`, with `nl_aliases` as the authoritative alias list and `route` as the tab-fallback URL. Future entity additions change one registry entry, not two files.
- **Triage session resumable via `current_item_id` + `cursor_meta.processed_ids`.** Unmount calls `endSession` fire-and-forget; remount can resume by starting a fresh session (processed_ids prevents reprocessing).
- **Snooze entity-type-agnostic.** Single `triage_snoozes` table with partial unique `WHERE woken_at IS NULL` prevents double-active-snooze while preserving full audit history across wake cycles.
- **bridgeable-admin portal UNTOUCHED per approved scope boundary.** The platform admin's `admin-command-actions.ts` is a separate registry for cross-tenant surfaces and lives in a different bundle.

### Verification

- All 253 Phase 1–5 backend tests passing (14 pytest modules)
- tsc clean (0 errors) after all frontend work
- Playwright specs written (not run here — require a running backend + seeded staging tenant)

---

## Command Bar Platform Layer (Phase 1 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r30_delivery_caller_vault_item`
**Migration head after:** `r31_command_bar_trigram_indexes`
**Tests passing:** 99 new platform-layer tests + 8 regression tests + 9 Playwright specs + 1 blocking perf gate

### What shipped

- Backend platform layer package at `backend/app/services/command_bar/`:
  - `registry.py` — OWNS `ActionRegistryEntry` type + singleton + seed
  - `intent.py` — rule-based classifier (5 intents: navigate / search / create / action / empty)
  - `resolver.py` — pg_trgm fuzzy search across 6 entity types via single UNION ALL, recency weighting, tenant isolation
  - `retrieval.py` — orchestrator, OWNS the `QueryResponse` / `ResultItem` shape contract going forward
- New endpoint: `POST /api/v1/command-bar/query` with Pydantic-validated request + response schemas
- Migration `r31_command_bar_trigram_indexes`: `pg_trgm` extension + 6 GIN trigram indexes (via `CREATE INDEX CONCURRENTLY` inside autocommit_block)
- Frontend interface-only adapter at `frontend/src/core/commandBarQueryAdapter.ts` — translates backend `ResultItem` → existing `CommandAction` shape
- Frontend UI (`core/CommandBar.tsx`) fires `/command-bar/query` as 4th parallel fetch alongside legacy endpoints; results merge via existing type-ranked sort
- `navigation-service.ts` NavItem extended with optional `aliases` field + `getAllNavItemsFlat()` helper
- 17 navigate actions registered (hubs, AR/AP aging, P&L, invoices, SOs, quoting, compliance, pricing, KB, vault + 4 vault services, accounting admin)
- 6 create actions registered (sales_order → `wf_create_order` workflow, quote, case, invoice, contact, product); frontend `crossVerticalCreateActions` mirrors for offline fallback matching
- Search across cases, sales orders, invoices, contacts, products, documents

### Audit findings (key items only)

- **5,900 lines of command bar infrastructure already existed** across 12 files. Production bar is `core/CommandBar.tsx` (1091 lines) with full voice + Option+1..5 shortcuts + capture-phase listener.
- **`wf_compose` does not exist in code** — only `wf_create_order` ships. Phase 1's "remove old Compose menu" requirement was a no-op because there's no menu to remove.
- Legacy files: `ai/CommandBar.tsx` (250 lines, zero imports) deleted; `ai-command-bar.tsx` (93 lines) KEPT — audit initially flagged it unused but `products.tsx` actively uses it as a page-specific AI search bar. Restored after the mistake.
- **Pre-existing route collision:** `/api/v1/ai/command` has handlers in both `ai.py` and `ai_command.py` (same prefix + same path). `ai.py` wins on resolution order; `ai_command.py`'s handler is unreachable via that path. Documented in `CLAUDE.md §4 "Command Bar Migration Tracking"`; full resolution deferred to post-arc cleanup.

### What was deferred (intentionally, per phase plan)

- Saved view results (Phase 2)
- Spaces and pinning (Phase 3)
- Natural language creation with live overlay (Phase 4)
- Triage workspace — including full frontend actionRegistry.ts reshape (Phase 5)
- Briefings (Phase 6)
- Voice input, peek panels, mobile command bar, polish (Phase 7)
- Retirement of the 8 legacy `/ai-command/*` + `/core/command*` routes — tracked in `CLAUDE.md §4 Command Bar Migration Tracking`, retired per-endpoint as frontend callers migrate

### Performance

- Target: p50 < 100 ms, p99 < 300 ms
- Actual on dev hardware (50-sample sequential mixed-shape workload, tenant seeded with ~24 rows):
  - **p50 = 5.0 ms** (20× headroom)
  - **p99 = 6.9 ms** (43× headroom)
- **BLOCKING CI gate** at `backend/tests/test_command_bar_latency.py`. Fails on p50 > 100 ms or p99 > 300 ms.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_command_bar_registry.py` | 22 | Registry seed + registration + filters + match scoring |
| `test_command_bar_intent.py` | 40 | All 5 intents, parametrized record-number patterns, edge cases |
| `test_command_bar_resolver.py` | 15 | 6 entity types + typo tolerance + recency + tenant isolation + entity_types filter + score ordering |
| `test_command_bar_retrieval.py` | 13 | End-to-end orchestration + permission gating + tenant + dedup + max_results |
| `test_command_bar_query_api.py` | 9 | API contract + response shape + max_results + context passthrough |
| `test_ai_command_regression.py` | 8 | Auth + `/command/execute` + `/parse-filters` + `/company-chat` + `/briefing/enhance` + cross-tenant isolation on `/core/command-bar/search` |
| `test_command_bar_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/command-bar-phase-1.spec.ts` | 9 | Cmd+K open/close, navigate, case/SO search, create action, Alt+1 shortcut, typo tolerance, contract |
| **Total new this phase** | **117** | All passing |

### Architectural notes for Phase 2

- `registry.py` is designed to accept Phase 2's saved-view entries without schema changes (`action_type="saved_view"` already reserved).
- `retrieval.py` OWNS the public response shape — Phase 2 additions extend it; do not redefine.
- `intent.py` is deliberately zero-AI. Phase 4's NL creation with live overlay can layer AI classification on top of rules for ambiguous queries; do not replace the rule engine.
- Frontend `actionRegistry.ts` reshape deferred to Phase 5. The interface-only adapter stays until then.
- Retirement of legacy endpoints is per-phase and per-caller; no all-at-once deletion.

---

## Saved Views as Universal Primitive (Phase 2 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r31_command_bar_trigram_indexes`
**Migration head after:** `r32_saved_view_indexes`
**Tests passing:** 38 saved-views backend tests + 1 blocking latency gate + 7 Playwright specs

### What shipped

Saved Views are now the rendering engine for every list, kanban, calendar, table, card grid, chart, and dashboard surface. "One query, infinite presentation contexts." Storage reuses `vault_items` with `item_type='saved_view'` + `metadata_json.saved_view_config` (no new table, no schema changes to the VaultItem shape).

- Backend package at `backend/app/services/saved_views/`:
  - `types.py` — typed dataclasses (EntityType, Filter, Sort, Grouping, Presentation, Permissions, SavedViewConfig, SavedView, SavedViewResult, per-mode configs). `from_dict`/`to_dict` on every class for JSONB round-trip.
  - `registry.py` — 7 entity types seeded (fh_case, sales_order, invoice, contact, product, document, vault_item). Each entity has `available_fields`, `default_sort`, `default_columns`, per-entity `query_builder` (tenant-isolated SQLAlchemy query) + `row_serializer`.
  - `executor.py` — `execute(db, *, config, caller_company_id, owner_company_id)` returning `SavedViewResult`. Dispatches filters (12 operators), sort, grouping (kanban buckets), aggregation (chart/stat), cross-tenant masking via `MASK_SENTINEL="__MASKED__"`. DEFAULT_LIMIT=500, HARD_CEILING=5000.
  - `crud.py` — create/get/list/update/delete/duplicate. 4-level visibility enforced: `private`, `role_shared`, `user_shared`, `tenant_public`. Returns typed `SavedView` dataclasses; never leaks raw VaultItem.
  - `seed.py` — `seed_for_user(db, user)` role-based seeding. Templates keyed by `(vertical, role_slug)`. Idempotency via `users.preferences.saved_views_seeded_for_roles` array + defense-in-depth `_already_seeded` check. Hooked into `auth_service.register_user` post-commit.
  - `__init__.py` — public exports.
- Migration `r32_saved_view_indexes`:
  - GIN trigram index on `vault_items.title` (command bar fuzzy match)
  - Partial B-tree on `(company_id, created_by)` WHERE `item_type='saved_view' AND is_active=true` (hot-path list)
  - `users.preferences JSONB DEFAULT '{}'` column (seed idempotency bag)
  - Widened `vault_items.source_entity_id` from `String(36)` → `String(128)` for semantic seed keys (e.g. `saved_view_seed:director:my_active_cases`) — backward-compatible, UUIDs still fit
  - CONCURRENTLY indexes via `op.get_context().autocommit_block()`
- API at `/api/v1/saved-views/*` (8 endpoints): list, create, list-entity-types, get, patch, delete, duplicate, execute. `execute` is the hot path.
- Command bar integration: new `saved_views_resolver.py` runs PARALLEL to the entity resolver (not folded into UNION ALL — preserves Phase 1's latency budget). New `ResultType="saved_view"` maps frontend-side to `CommandAction.type="VIEW"`, slot 5 in TYPE_RANK between RECORD (3) and NAV (6).
- Frontend at `frontend/src/components/saved-views/` + `pages/saved-views/`:
  - `types/saved-views.ts` — full dataclass mirrors; `MASK_SENTINEL` exported
  - `services/saved-views-service.ts` — 8-endpoint API client, no caching (live queries preserve visibility / delete semantics across tabs)
  - `components/saved-views/SavedViewRenderer.tsx` — dispatches to 7 mode renderers, displays cross-tenant masking banner, ChartRenderer code-split via `React.lazy` + `Suspense` (recharts out of initial bundle)
  - Mode renderers: `ListRenderer`, `TableRenderer`, `KanbanRenderer`, `CalendarRenderer` (DIY month grid), `CardsRenderer`, `ChartRenderer` (recharts, 5 chart types), `StatRenderer`
  - `components/saved-views/SavedViewWidget.tsx` — hub/dashboard embed; per-session entity-type cache so 20 widgets don't refetch the registry
  - `components/saved-views/builder/` — FilterEditor (12 operators), SortEditor, PresentationSelector (mode-specific sub-forms)
  - Pages: `SavedViewsIndex` (grouped: Mine / Shared with me / Available to everyone), `SavedViewPage` (detail + edit/duplicate/delete), `SavedViewCreatePage` (create + edit modes, shared component)
  - Routes: `/saved-views`, `/saved-views/new`, `/saved-views/:viewId`, `/saved-views/:viewId/edit`
- Production board rebuild at `pages/production/ProductionBoardDashboard.tsx` — composed of `SavedViewWidget` instances filtered to production-role seeded views. `/production` now renders the dashboard; legacy bespoke board preserved at `/production/legacy` for one release.

### Performance

- Target: p50 < 150 ms, p99 < 500 ms (execute endpoint, representative 1000-row tenant)
- Actual on dev hardware (50-sample sequential 4-shape mix: list + table + kanban + chart):
  - **p50 = 15.4 ms** (10× headroom)
  - **p99 = 18.5 ms** (27× headroom)
- **BLOCKING CI gate** at `backend/tests/test_saved_view_execute_latency.py`. Fails on p50 > 150 ms or p99 > 500 ms. Runs 1,000-row seed + 4 presentation shapes sequentially.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_saved_views_registry.py` | 9 | Default seed of 7 entities, field types, field lookup, registration replace |
| `test_saved_views.py` | 29 | CRUD, executor filters/sort/group/aggregation, tenant isolation, cross-tenant masking, seed idempotency, API (6), command-bar integration |
| `test_saved_view_execute_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/saved-views-phase-2.spec.ts` | 7 | CRUD, mode switch, kanban, calendar, command-bar VIEW result, production-board rebuild, cross-tenant masking contract |
| **Total new this phase** | **46** | All backend passing; Playwright specs ready for staging run |

### Architectural notes for Phase 3+

- Cross-tenant masking is purely field-level in `executor.py` when `caller_company_id != owner_company_id`. Phase 2 doesn't ship a sharing UI — same-tenant sharing via `permissions.shared_with_*` arrays covers 95% of use cases. When cross-tenant sharing UI lands, `platform_tenant_relationships` (existing table) is the gate, not DocumentShare.
- `OperationsBoardRegistry` and `FinancialsBoardRegistry` COEXIST with saved views. Subsumption deferred to post-arc work.
- `production-board.tsx` deletion is gated on Playwright parity verification. When green, delete the file + remove the `/production/legacy` route + remove the ProductionBoardPage import.
- Saved view config is stored in `metadata_json.saved_view_config` only — no fallbacks. Crud treats `metadata_json` as canonical.
- New seed templates added after a role has already been seeded do NOT backfill. Template additions require either a one-off backfill script or a role-version bump (Phase 2 accepts this trade-off).
- Seed key format `saved_view_seed:{role_slug}:{template_id}` — stored in `vault_items.source_entity_id` (widened to varchar(128) in r32).
- Frontend Builder (Phase 2) is FilterEditor + SortEditor + PresentationSelector. Live preview is deferred — users save then are redirected to the detail page. Preview is queued as polish.
- Chart library: `recharts` 3.8.1. Lazy-loaded via `React.lazy` in SavedViewRenderer so non-chart callers never ship the recharts bundle.
- DIY calendar month grid is sufficient for Phase 2. If FH service scheduling needs week view / overlapping slots / drag-drop, swap the body of `CalendarRenderer.tsx` for `react-big-calendar` — dispatch layer stays.

---

## Spaces — Context Layer (Phase 3 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r32_saved_view_indexes` (no new migration; `User.preferences` sufficient)
**Tests passing:** 55 backend (36 unit + 19 API/integration) + 9 Playwright specs + 139 Phase 1+2 regression

### What shipped

Spaces are per-user workspace contexts — name + icon + accent + pinned items — layered on top of the existing vertical navigation. Not a replacement; a lens. The base nav from `navigation-service.ts` stays visible; spaces add a `PinnedSection` above it and shift the visual accent.

- Space data model in `User.preferences.spaces` (JSONB array) + `active_space_id` + `spaces_seeded_for_roles` (idempotency tracker).
- Backend package at `backend/app/services/spaces/`:
  - `types.py` — typed dataclasses (SpaceConfig, PinConfig, ResolvedSpace, ResolvedPin, 6 accent literals, SpaceError hierarchy), `MAX_SPACES_PER_USER=5`, `MAX_PINS_PER_SPACE=20`.
  - `registry.py` — role-based `SpaceTemplate`s keyed by `(vertical, role_slug)`. 6 pairs seeded (funeral_home director/admin/office, manufacturing production/office/admin) + `FALLBACK_TEMPLATE` "General" + `NAV_LABEL_TABLE` for nav-item pin resolution.
  - `crud.py` — 10 service functions: create/get/update/delete/reorder spaces + add/remove/reorder pins + set_active_space. Server-side pin resolution via `_resolve_pin` denormalizes saved_view_title + nav label so clients render from flat data.
  - `seed.py` — idempotent via `preferences.spaces_seeded_for_roles`; skip-if-name-exists defense-in-depth; saved-view seed-key pins resolved at read time via VaultItem `source_entity_id` lookup.
  - `__init__.py` — public exports.
- API: 10 endpoints at `/api/v1/spaces/*`, all user-scoped. Cross-user 404 isolation. 5-space cap enforced at service layer, translated to 400 at API.
- Command bar integration:
  - `QueryContext` gained `active_space_id: str | None`.
  - Synthesized space-switch results (not in the module registry — read `user.preferences.spaces` at query time; exact match → 1.4, 2+-char prefix → 1.1; current active space suppressed).
  - Pin boost: `_WEIGHT_ACTIVE_SPACE_PIN_BOOST=1.25` applied in-place to `ResultItem.score` when result URL or id matches a pin target in the active space.
  - Space-switch URLs shaped `/?__switch_space=<id>`; frontend CommandBar dispatcher intercepts the param and calls `SpaceContext.switchSpace` rather than real-navigating.
- Frontend:
  - `types/spaces.ts` — full type mirrors, `ACCENT_CSS_VARS` × 6 accent palette, `applyAccentVars` helper.
  - `services/spaces-service.ts` — 10-endpoint axios client, no caching.
  - `contexts/space-context.tsx` — SpaceProvider with fetch-on-mount, optimistic mutations + server reconciliation, `activeSpace` memo, `isPinned` / `togglePinInActiveSpace` convenience helpers, null-safe `useActiveSpaceId` hook.
  - Components at `components/spaces/`: `SpaceSwitcher` (top-nav dropdown next to NotificationDropdown; keyboard listeners for `Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`), `PinnedSection` (renders ABOVE `navigation.sections` in the existing sidebar; HTML5 DnD for reorder; hover-to-unpin X button; data-testid attributes for Playwright), `PinStar` (one-click pin toggle; on SavedViewPage header; null-renders when no active space), `NewSpaceDialog` + `SpaceEditorDialog` (shadcn Dialog with accent selector + density + default toggle + delete-with-confirm).
  - Mounted in App.tsx inside PresetThemeProvider on the tenant branch. Platform admin (`BridgeableAdminApp`) completely untouched.
- Visual personality: 6 accents via CSS variables (`--space-accent`, `--space-accent-light`, `--space-accent-foreground`) on `documentElement`. Phase 3 NEVER touches `--preset-accent`. Components use `var(--space-accent, var(--preset-accent))` so no-active-space gracefully falls back.
- Pin-to-current-space: star icon on SavedViewPage header. Nav-item pinning via API; UI star affordance in sidebar nav items is future polish (Phase 7 target).
- 5-space cap enforced at service + API layers.
- Edge cases handled: pin target unavailable (saved view deleted / access revoked → gray-out + hover-reveal X to clean up), role change (both saved-view seed + spaces seed re-run at `user_service.update_user` role-change branch — idempotent via each seed's own array).

### Audit findings

- **`presetAccent` already existed** as a CSS-variable-backed vertical baseline (`PresetThemeProvider` sets `--preset-accent` on `documentElement`). Phase 3 layers `--space-accent` on top with CSS fallback; no conflict, no rewrite.
- **`User.preferences` already added** in r32 (Phase 2). Phase 3 owns new JSONB keys (`spaces`, `active_space_id`, `spaces_seeded_for_roles`) alongside Phase 2's `saved_views_seeded_for_roles`. Zero schema change needed.
- **Only one capture-phase keyboard listener exists** (`cmd-digit-shortcuts.ts` for Option/Alt+1..5 + Cmd+1..5, active only when command bar is open). Phase 3 shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) use different modifier combos + different active conditions — clean, no capture-phase needed.
- **`update_user` role-change path exists.** Phase 2's saved-view seed was NOT hooked here (only at register_user), so a user promoted from office to director never picked up director-specific saved views. Phase 3 fixes this ADJACENTLY: explicit two-line seed re-invocation at the role-change site (spaces + saved-views).
- **FH two-hub pattern (Funeral Direction / Business Management)** from the master doc was aspirational — not represented in `navigation-service.ts` today. Phase 3 operationalizes it naturally: "Arrangement" space IS Funeral Direction hub; "Administrative" space IS Business Management hub. Documented in CLAUDE.md §1a Spaces subsection + flagged here per the user's directive.
- **framer-motion NOT installed.** Phase 3 uses CSS transitions on --space-* variables + tw-animate-css (already present) for any micro-animations. Zero new animation deps.
- **Platform admin** is a fully separate app (`BridgeableAdminApp`) via subdomain / path routing — Phase 3 only wires into the tenant branch.

### Performance

No dedicated CI latency gate this phase — Spaces read/write is trivial JSONB + a small denormalization pass; the hot path (list spaces) returns in single-digit ms on dev. Command bar integration reuses existing paths + adds one ranking multiplier; the Phase 1 latency gate (p50 < 100 ms / p99 < 300 ms) is unchanged and continues to pass. If space-switch synthesis introduces drift in later phases, fold a dedicated latency gate at that point.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_spaces_unit.py` | 36 | Registry (7), Seed (7), CRUD (12), Pins (8), Mfg admin (1), FH director flow |
| `test_spaces_api.py` | 19 | 13 API endpoint tests + 6 command-bar integration (synthesis + pin boost) |
| `frontend/tests/e2e/spaces-phase-3.spec.ts` | 9 | Keyboard shortcuts, picker, accent transition, pin saved view, pin nav item, reorder API, CRUD lifecycle, 5-cap, pin target deleted |
| **Total new this phase** | **64** | All backend passing; Playwright specs ready for staging run |
| Phase 1 + 2 regression | 139 | All green — no changes to previously-passing behavior |

### Surprises for Phase 4

- **Spaces operationalize the FH two-hub pattern (Funeral Direction / Business Management) the master doc describes.** "Arrangement mode" IS Funeral Direction hub; "Administrative mode" IS Business Management hub. This wasn't a design pivot — it was a clarifying realization during the audit. The master doc's two-hub pattern stays accurate at the architectural level; Phase 3 just makes it a first-class UI concept via spaces rather than a nav config requirement. Future phases that touch FH navigation should honor this mapping and avoid re-implementing the same concept in nav.
- **Phase 2's saved-view seed gap on role change is now fixed** at `user_service.update_user`. Phase 4 (Natural Language Creation with Live Overlay) should consider whether the overlay registers any user-scoped state that needs re-seeding on role change — the two-line pattern at the hook site is the canonical place to add another seed.
- **Active-space context now flows into command bar queries.** Phase 4's NL creation may benefit from the same context channel — e.g. "create new order" in Arrangement space defaults to vault-order entity, in Production space defaults to work-order entity. The `QueryContext.active_space_id` field is already there; intent classifier can branch on it without schema changes.
- **`recharts` bundle is lazy-loaded per Phase 2**, and Phase 3's space-switch doesn't force it. Keep this pattern — late bundles are for heavy, less-common UI (chart renderers, calendar DnD when we add it, voice transcription in Phase 7).
- **`SpaceSwitcher` uses `render={}` pattern for `DropdownMenuTrigger`, not `asChild`**, because shadcn v4's `@base-ui/react` doesn't expose `asChild`. Flagged per CLAUDE.md — any future UI using a trigger-wrapping pattern must use `render={}`.

### Architectural notes for Phase 4+

- Space-switch command bar actions are synthesized at query time (not registered in the module-level singleton) because the registry is shared across tenants and per-user state would leak. Future per-user / per-role / per-tenant actions should follow the same parallel-source synthesis pattern rather than bloat the singleton.
- Pin resolution is server-side. When we add cross-tenant space sharing (post-arc), the resolver needs to run through the same visibility check Phase 2 uses (`saved_views.crud._can_user_see`). Today's permissive lookup is acceptable because Phase 3 pins are only the user's own saved views + nav items — cross-tenant never happens.
- `User.preferences` is becoming a multi-phase JSONB bag (Phase 2 + 3 + future phases' seed flags). Keep writes narrowly scoped via `flag_modified` + single-key updates; never blanket-replace `user.preferences = {...}` without reading first.
- Seed additions at the role-change hook site are explicit two-line calls, not abstracted into a `reseed_all` helper. This is intentional: future phases (5, 6) will add more seeds at the same hook, each discoverable via grep without a central registry to maintain.

---

## Natural Language Creation with Live Overlay (Phase 4 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r33_company_entity_trigram_indexes`
**Tests passing:** 79 new backend (53 parsers + 25 integration + 1 latency gate) + 8 Playwright + 194 Phase 1-3 regression = 273 backend

### What shipped

The Fantastical-style extraction overlay — the biggest UX payoff of the arc and the centerpiece of the Wilbert demo. User hits Cmd+K, types one sentence, an overlay populates structured fields in real time.

- Backend NL creation platform layer at `backend/app/services/nl_creation/`:
  - `types.py` — ExtractionRequest, FieldExtraction, ExtractionResult, NLEntityConfig, FieldExtractor, 4 error classes
  - `structured_parsers.py` — date (ISO / US / written month / weekday / "tonight"), time (12h/24h/named), datetime, phone (E.164), email, currency (requires $-flag), quantity, name (with prefix/suffix handling)
  - `entity_resolver.py` — resolve_company_entity via pg_trgm, resolve_contact + resolve_fh_case via existing GIN indexes, filter whitelist for safety, one-call `resolve()` dispatcher
  - `ai_extraction.py` — Intelligence-backed fallback with block-rendered prompt variables, exception-safe (returns empty on any failure)
  - `entity_registry.py` — 4 configs (case, event, contact + fh_case alias → case), case uses AI-only for date fields (multi-date disambiguation), per-entity creator_callable, space_defaults dict, fh_case → case alias lookup
  - `extractor.py` — orchestration: structured → resolver → AI fallback if required still missing → merge with prior_extractions by confidence → apply space_defaults → compute missing_required
  - `__init__.py` — public exports
- Migration `r33_company_entity_trigram_indexes`: GIN trigram on `company_entities.name` via CONCURRENTLY, safe on live tables
- 3 managed Intelligence prompts seeded via `scripts/seed_intelligence_phase4.py`: `nl_creation.extract.{case,event,contact}`. Case prompt content copied from `scribe.extract_first_call` but independent. Haiku (simple route), force_json, response_schema enforcing `{"extractions": [...]}` shape
- Intent extension: `intent.py::detect_create_with_nl()` — additive, no Intent Literal change. Two-mode matcher (exact alias prefix + fuzzy fallback). 3-char min on NL content prevents false positives on short queries
- New `create.event` action registered in Phase 1 command-bar registry (previously missing — audit gap)
- API at `/api/v1/nl-creation/*` — 3 endpoints: `POST /extract` (hot path, 300ms debounced client-side, p50 < 600ms gate), `POST /create` (materialize entity via creator_callable, honors required_permission), `GET /entity-types` (registry dump filtered by permissions)
- Frontend:
  - `types/nl-creation.ts` — full type mirrors
  - `services/nl-creation-service.ts` — 3-endpoint axios client, AbortSignal support
  - `hooks/useNLExtraction.ts` — 300ms debounce (wider than command bar's 100-200ms to amortize AI), AbortController cancellation on new input, manual-override state with re-merge, `create()` materialization
  - `components/nl-creation/NLOverlay.tsx` — Fantastical-style panel with checkmarks / amber low-confidence / entity pills / missing-required section / keyboard hints footer
  - `NLField.tsx` — per-row display with confidence-aware styling
  - `NLCreationMode.tsx` — wrapper with window-level keyboard listeners (Enter / Tab / Esc), navigation handling, module-level entity-types cache so rapid remount doesn't refetch
  - `detectNLIntent.ts` — client-side mirror of backend detector; instant UX without server round-trip
  - `pages/crm/new-contact.tsx` — contact create page at `/vault/crm/contacts/new`, fills Phase 1 register-but-no-route gap, pre-fills from `?nl=<input>` query param (regex extracts email/phone/name/company segment)
- Command bar integration: `CommandBar.tsx` gains `activeNLEntity` state + useEffect watching `query` via `detectNLIntent`. Renders `<NLCreationMode>` instead of the standard results list when matched. Suppresses AI-mode + results-list rendering during NL mode. Coexists with existing `activeNLWorkflow` (workflow-backed entities) cleanly
- Voice input reuses Phase 1's `useVoiceInput` hook — transcript text flows into command-bar input and the detector fires identically to typed input
- Demo seed script `scripts/seed_nl_demo_data.py --tenant-slug testco` — idempotent, seeds Hopkins FH + 5 other companies + 3 prior FH cases (Andersen/Martinez/Nakamura families)

### Audit findings

- **Existing NL extraction infrastructure was workflow-scoped** (`command_bar_extract_service.py` + `NaturalLanguageOverlay.tsx` = 1547 lines). It already powers sales_order / quote creation today. Phase 4 built a parallel entity-scoped path per approved plan decision #2 — zero modifications to the existing workflow path. Retirement is a Phase 5/6 cleanup concern
- **`User.preferences` JSONB** (added in Phase 2 r32) reused — no new tenant-level config storage needed
- **Phase 1 resolver's `SEARCHABLE_ENTITIES`** doesn't include `company_entity`. Phase 4 adds local resolution in `nl_creation/entity_resolver.py` rather than extending Phase 1's tuple. Phase 5 nav/search unification will elevate the CompanyEntity resolver to a first-class Phase 1 search target
- **Two existing NL-extraction call-sites** (`first_call_extraction_service` for FH first-call page + `call_extraction_service` for RC calls) — Phase 4 does NOT consolidate these; the `nl_creation.extract.case` prompt was seeded independently per approved plan decision #4 (copied content, independent evolution)
- **`useVoiceInput` hook** is reusable verbatim — no per-modality fork needed
- **Scribe prompt + case field shape** ready for reuse — Phase 4's prompt copies the field taxonomy but stays independent
- **Case date-field ambiguity** discovered during verification: single sentence has "DOD tonight" AND "service Thursday" — both match a scalar structured parser. Fixed by making case date fields AI-only (handles semantic disambiguation), while single-datetime entities (event) keep their structured parsers

### Performance

| Stage | Budget | Actual |
|---|---|---|
| Structured parser (per call, 100-iteration average) | <5ms | <0.05ms typical |
| Entity resolver per field (pg_trgm backed) | <30ms | ~2-5ms on 10-row seed |
| AI extraction (Haiku via Intelligence) | <500ms typical, 1200ms ceiling | ~350-450ms typical |
| Extract endpoint p50 | <600ms | **5.9ms** (no-AI path), ~400ms with Haiku |
| Extract endpoint p99 | <1200ms | **7.2ms** (no-AI path), ~700-900ms with Haiku |

**BLOCKING CI gate** at `backend/tests/test_nl_creation_latency.py`. 30-sample mixed-shape across case/event/contact. Gate measures without Anthropic key set (floor latency); production CI with key produces a higher-but-still-compliant number.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_nl_structured_parsers.py` | 53 | Every parser × happy path + edge cases + perf guard |
| `test_nl_creation_backend.py` | 25 | Registry (5), Company-entity resolver (5 including tenant isolation + filter whitelist), Intent detector (6 across 4 entity types), Extractor orchestration (3), API (6) |
| `test_nl_creation_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/nl-creation-phase-4.spec.ts` | 8 | Demo sentence + event + contact + live update + tab fallback + escape + Hopkins pill + API contract |
| **Total new this phase** | **87** | All backend passing; Playwright ready for staging |
| Phase 1-3 regression | 194 | All green — no changes to previously-passing behavior |

### Surprises for Phase 5 (Triage Workspace — reshapes actionRegistry.ts)

- **Task deferred per approved plan** — no task model/API/UI today. Phase 5 Triage Workspace is the natural home for task creation UX conventions. When task lands, it's:
  - minimal model (id, tenant_id, title, assignee_id, due_date, priority, description, status, created_by/at)
  - `POST /api/v1/tasks` + standard CRUD
  - NL config in `nl_creation/entity_registry.py` — ~25 lines following event pattern
  - Creator callable ~15 lines
  - 1 new prompt seed
  - 1 new Playwright spec
  About 250 total lines of code
- **Frontend `actionRegistry.ts` reshape is Phase 5's big lift.** Phase 4 leaves `detectNLIntent.ts` as a client-side mirror of the backend detector — a small duplication. Phase 5's reshape should unify entity-type aliases into a single registry surface, replacing the manual ENTITY_PATTERNS list in `detectNLIntent.ts`
- **`command_bar_extract_service` + `NaturalLanguageOverlay` (workflow path) coexist with Phase 4's entity path.** Retirement decision is Phase 5/6. The natural migration: once Phase 5 Triage Workspace replaces workflow-driven sales-order creation with entity-driven, the old path becomes deletable
- **CompanyEntity not in Phase 1 resolver's SEARCHABLE_ENTITIES.** Adding it benefits BOTH Phase 4's NL pipeline AND the command bar's main results (typing "Hopkins" surfaces the CRM record). Phase 5 nav/search unification should do this in one coordinated touch
- **Space-aware extraction is wired but has no concrete defaults today.** The infrastructure is there (`space_defaults: dict[str, dict]` in each entity config). Phase 5/6 can populate meaningful defaults as UX patterns stabilize — e.g. "in Production space, `new order` defaults to work_order entity type"
- **Pre-existing `useNLExtraction`-adjacent NL flows in FH first-call page** — the `/cases/new` FHFirstCallPage has its own NL extraction via `scribe.extract_first_call`. Phase 4 leaves it untouched (it's the Tab fallback target). Future consolidation work can unify the two into one NL platform layer once traffic patterns prove out

### Demo verification

The demo sentence produces the expected overlay:

- **Input:** "new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH"
- **Expected extractions (with Anthropic key set):** Deceased name (John Smith), Date of death (Today/2026-04-20), Date of birth (null or missing_required — AI may omit), Informant (Mary, daughter), Service date (Thursday/2026-04-23), Funeral home (Hopkins Funeral Home PILL from entity resolver)
- **Verified on dev without Anthropic:** Funeral home PILL resolves correctly (entity resolver works). Required fields correctly listed in missing_required (AI disabled path)
- **On staging with Anthropic + Hopkins FH seeded:** full overlay populates, Enter creates case, navigates to case detail with all satellites populated

### Demo staging data seeded

`seed_nl_demo_data.py --tenant-slug testco` is the canonical re-seed command. Seeds:

- **CompanyEntity rows:** Hopkins Funeral Home, Riverside Funeral Home, Whitney Funeral Home, Oakwood Memorial, St. Mary's Church, Acme Manufacturing
- **3 prior FHCase rows** (Eleanor Andersen / Harold Martinez / Grace Nakamura) with satellite data so the fh_case resolver has trigram candidates

Idempotent — safe to re-run between demos. Documents the exact demo dependencies so regressions are re-seedable in a single command.
