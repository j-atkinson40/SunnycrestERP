# Accounting — User Guide

_Admin-facing guide for the Accounting service in the Vault hub._

## What this service does

Accounting in the Vault hub is the **platform-admin surface** for the
native accounting engine. It's where you lock a period, tell the
12 accounting agents when to run, review what the AI classified in
your GL, see your tax config, inspect statement templates, and look
up the platform's standard GL category list.

**Explicitly NOT in scope:** the tenant-facing Financials Hub. All
the day-to-day work — invoices, bills, JEs, payments, statements,
reports — stays in the vertical preset nav under Financials. V-1e
is the **configuration** of the accounting engine; the engine itself
is where it's always been.

Six sub-tabs under `/vault/accounting`:

1. Periods & Locks
2. Agent Schedules
3. GL Classification Queue
4. Tax Config
5. Statement Templates
6. COA Templates

**Admin-only.** Every route enforces `require_admin`; non-admin
users don't see the sidebar entry and hit 403 on direct URLs.

## Where it lives in the nav

**Vault hub sidebar → Accounting** (`/vault/accounting`).

Index page redirects to `/vault/accounting/periods` — the most
common landing.

## Key admin surfaces (6 tabs)

| Tab | Path | Purpose |
|---|---|---|
| **Periods & Locks** | `/vault/accounting/periods` | `AccountingPeriod` CRUD + type-to-confirm lock/unlock + recent-activity feed |
| **Agent Schedules** | `/vault/accounting/agents` | `AgentSchedule` config for the 12 accounting agents + recent-jobs feed |
| **GL Classification** | `/vault/accounting/classification` | `TenantAccountingAnalysis` review queue + confirm / reject / bulk-confirm |
| **Tax Config** | `/vault/accounting/tax` | Tax rates + jurisdictions (read-only; CRUD on `/settings/tax`) |
| **Statement Templates** | `/vault/accounting/statements` | Platform defaults vs tenant customizations split view (read-only in V-1e) |
| **COA Templates** | `/vault/accounting/coa` | Platform standard GL categories — filter / search |

## Common workflows

### Close a period (lock)

Periods are locked to prevent retroactive writes once month-end is
signed off. Friction matches stakes: locking requires typing the
exact period name to confirm.

1. `/vault/accounting/periods`.
2. Select the year (defaults to current). If no periods exist for
   that year, the 12 months auto-seed on first view.
3. Find the open period you want to close. Click **"Close period"**.
4. A confirmation modal appears:
   > This will prevent any writes to this period. Invoices, bills,
   > journal entries, and payments dated in March 2026 will be
   > rejected until this period is unlocked.
   >
   > Type **March 2026** to confirm.
5. Type the exact period name. The **"Close period"** button stays
   disabled until the input matches exactly.
6. Click to lock. The period's status flips to `closed`. An
   `AuditLog` row writes with `action="period_locked"`.
7. Surfaced in the Recent Activity section below the table +
   visible at `/vault/accounting/period-audit`.

**Idempotent.** Trying to lock an already-closed period returns 409.
Trying to unlock an already-open period returns 409.

### Unlock a period

Unlocking restores write capability. Simple confirm — cheap to
reverse.

1. Find a `closed` period. Click **"Unlock"**.
2. A confirmation modal asks:
   > Unlock period: March 2026?
   > This will allow writes to this period again.
3. Click **"Unlock"**. Status flips to `open`. `closed_by` and
   `closed_at` clear. `AuditLog` row writes with
   `action="period_unlocked"`.

### Configure an agent schedule

Agent Schedules is about *when* the 12 accounting agents run — not
about running them now (that's the tenant Agents Hub).

1. `/vault/accounting/agents`.
2. The top table lists all configured schedules (may be empty on a
   fresh tenant). Each row shows:
   - Agent name
   - Human-readable schedule ("day 3 of month, at 03:00 America/New_York")
     or "Disabled"
   - Last run timestamp
   - Enabled toggle
3. **Toggle on/off:** click the status button. Fires
   `POST /api/v1/agents/schedules/{job_type}/toggle`.
4. **Edit schedule details (cron, day, hour, timezone):** not in V-1e
   UI. Call `POST /api/v1/agents/schedules` via API with the full
   config, or wait for the cron-editor UI (tracked in DEBT.md).

The bottom section shows **Recent Jobs** — last 20 jobs across all
12 agents, color-coded by status (complete / running /
awaiting_approval / failed). Click a row (V-1e exposes as a UI
affordance) jumps to the agent run detail in the tenant Agents Hub.

The 12 agents:

| job_type | Display name |
|---|---|
| `month_end_close` | Month-End Close |
| `ar_collections` | AR Collections |
| `unbilled_orders` | Unbilled Orders |
| `cash_receipts_matching` | Cash Receipts Matching |
| `expense_categorization` | Expense Categorization |
| `estimated_tax_prep` | Estimated Tax Prep |
| `inventory_reconciliation` | Inventory Reconciliation |
| `budget_vs_actual` | Budget vs. Actual |
| `1099_prep` | 1099 Prep |
| `year_end_close` | Year-End Close |
| `tax_package` | Tax Package |
| `annual_budget` | Annual Budget |

### Review AI GL classifications

When a tenant onboards, the Intelligence layer classifies their
imported GL accounts against `PLATFORM_CATEGORIES`. High-confidence
suggestions (confidence ≥ 0.85) auto-apply; lower-confidence rows
land in the review queue.

1. `/vault/accounting/classification`.
2. Filter by mapping_type if needed (gl_account / customer / vendor
   / product).
3. Each row shows:
   - The imported account (name + source ID)
   - AI's suggested platform_category
   - Confidence %
   - Reasoning (one-sentence AI explanation)
   - Actions: Confirm / Reject
4. **Confirm.** Creates a `TenantGLMapping` row so the 12 agents can
   resolve the mapping at runtime. Marks the analysis row as
   `confirmed`.
5. **Reject.** Marks analysis `rejected` — no TenantGLMapping
   created. The row drops out of the queue. Manual mapping via a
   separate flow if needed (not in V-1e scope).

**Bulk confirm.** When the queue has high-confidence rows (≥0.9),
a **"Confirm N high-confidence"** button appears at the top. One
click confirms all of them. Useful for the first pass after a
tenant onboarding.

### Read tax config

Tax Config is read-only in V-1e. CRUD lives in the existing
`/settings/tax` page.

1. `/vault/accounting/tax`.
2. Tax Rates table: rate name, percentage, default flag, active
   flag.
3. Tax Jurisdictions table: jurisdiction name, state, county, ZIPs
   (truncated), active flag.
4. Click **"Open Tax settings"** to deep-link into the CRUD surface.

### Inspect statement templates

Also read-only in V-1e. Shows platform defaults and tenant
customizations side-by-side.

1. `/vault/accounting/statements`.
2. Left column: platform defaults (`tenant_id IS NULL`).
3. Right column: tenant customizations (`tenant_id = current_tenant`).
4. Each entry shows template_name, template_key, customer_type,
   default-for-type flag.
5. **Editing is not wired in V-1e** — tracked in DEBT.md as
   "Statement-template editor deferred." Tenants who need
   customization today work via direct SQL or a backend utility.

### Look up a platform GL category

1. `/vault/accounting/coa`.
2. Search or filter by category type (revenue / ar / cogs / ap /
   expenses).
3. Each row shows the `platform_category` identifier (e.g.
   `vault_sales`, `ar_funeral_homes`, `accounts_payable`,
   `rent`) plus its type tag.
4. Read-only: platform categories are platform config. Tenant
   overrides happen via TenantGLMapping on the Classification tab,
   not here.

**Current source of truth.** `PLATFORM_CATEGORIES` constant in
`app/services/accounting_analysis_service.py`. 5 types × ~27
categories.

## Type-to-confirm UX — why asymmetric?

Locking a period blocks writes. If you lock by mistake, every
subsequent invoice / bill / JE / payment dated in that period
bounces with an error. People will notice, ops will ping you, work
backs up.

Unlocking restores the prior state. If you unlock by mistake, the
worst case is that your period is writable for the 30 seconds it
takes someone to say "wait, that was supposed to stay closed."

Friction matches stakes. Type-to-confirm for lock; simple confirm
for unlock.

The asymmetry is encoded in the `AccountingPeriodsTab.tsx`
component — lock modal has an input that gates the destructive
button, unlock modal just has a Cancel / Unlock pair.

## Relationship to tenant Financials Hub

**Platform admin here.** **Tenant workflow there.**

The Financials Hub lives under the vertical preset nav (Manufacturing:
`/financials`, FH: similar). It's where tenant users:

- Create invoices / bills / JEs / payments
- Run statement generation
- Reconcile bank accounts
- View AR aging / AP aging
- Generate reports (income statement, balance sheet, etc.)
- Run the 12 accounting agents (via Agents Hub)

All that stays untouched by V-1e. Your tenant users have zero
visibility into `/vault/accounting` unless they're also admins.

The split is intentional: admins occasionally need to lock a period
or review a classification; tenant accountants work day-to-day in
Financials. Vault is not the financial engine.

## Permission model

- **Every endpoint requires `require_admin`.** No sub-gradient.
- **Sidebar entry hidden from non-admin users.** Enforced by the
  service's `required_permission="admin"` on its Vault hub
  descriptor.
- **Cross-tenant isolation on every query.** Periods, schedules,
  analyses, tax config, templates — all filter by
  `current_user.company_id`.
- **Period-lock audit writes attributed to the acting admin.**
  `AuditLog.user_id = current_user.id`. Admins can see who locked
  what via the Recent Activity feed.

## Related services

- **Documents.** Statement templates are Document templates (same
  registry). Statement runs produce statement Documents via the
  Document template registry. Invoice PDFs go through
  `document_renderer`.
- **Intelligence.** GL classification, customer classification,
  vendor classification all route through Intelligence. Every
  `TenantAccountingAnalysis` row has a `caller_intelligence_execution_id`
  pointing to the AI call that produced it.
- **Notifications.** `compliance_expiry` + future audit-trail
  surfacing. Period-lock events don't fire notifications today
  (could be added — would be useful for multi-admin tenants).
- **CRM.** Health scoring uses payment behavior; payment data lives
  in the accounting engine. When a period is locked mid-month it
  doesn't affect health scoring queries (scoring reads from
  `sales_orders` + `invoices` + `customer_payments`, not from
  `accounting_periods`).

## Known limitations

### No cron editor in V-1e

Agent schedules can be toggled on/off in the UI but the schedule
itself (cron expression, run_day_of_month, run_hour, timezone,
notify_emails, auto_approve) is edited via the backend API today.
Modal editor tracked in DEBT.md as "Cron-editor for agent
schedules deferred from V-1e."

### Statement template editor not built

The Statement Templates tab is read-only split view. Admins who
need customization work around it via direct DB edit or a backend
utility. Full editor tracked in DEBT.md as "Statement-template
editor deferred from V-1e."

### Tax Config is read-only

CRUD works at `/settings/tax`. V-1e added a read-only view in the
Vault hub for visibility + deep-link back to the editor. Full
CRUD surface inside Vault is future polish.

### COA Templates has 27 categories, not 100+

The spec for V-1e anticipated 100+ categories. Real source of truth
(`PLATFORM_CATEGORIES` in `accounting_analysis_service.py`) has 27
across 5 types. The guide lists what exists today. Expanding the
set is a product decision, not infrastructure work.

### Accountant invitation flow not rebuilt

Pre-V-1e, the deprecated QBO/Sage integration had an "invite your
accountant" feature (magic-link email granting limited read access
to synced data). That flow died when the integration was deprecated.
If accountant collaboration becomes a customer ask, rebuild as a
first-class feature — probably a tenant-scoped read-only role +
token-based landing page. Tracked in DEBT.md as "Accountant
invitations surface not rebuilt in V-1e."

### Widget seed coordination

The three V-1e widgets (`vault_pending_period_close`,
`vault_gl_classification_review`, `vault_agent_recent_activity`)
require `seed_widget_definitions(db)` to run before they appear in
the Vault Overview. On fresh deploys this runs on app startup. Test
environments using `TestClient(app)` need to seed explicitly.
Tracked in DEBT.md.

See [`../DEBT.md`](../DEBT.md) for the full list of deferred items.
