# CRM — User Guide

_Admin-facing guide for the CRM service in the Vault hub._

## What this service does

CRM is Bridgeable's customer relationship data layer. It tracks
every company the tenant interacts with (funeral home customers,
cemeteries, contractors, vendors, prospects), every person inside
those companies, every activity (calls, emails, notes, meetings),
sales pipeline stages, health scoring, and duplicate review.

The CRM absorbed into Vault in **Phase V-1c** (lift-and-shift —
URL moved from `/crm/*` to `/vault/crm/*`, all pages re-homed under
`VaultHubLayout`, data models unchanged). Pre-V-1c the CRM was a
top-level nav entry; post-V-1c it's the third full Vault service.

**Permission-gated, not admin-gated.** Unlike Documents,
Intelligence, and Accounting, CRM is visible to any tenant user
with `customers.view` permission — same gate the pre-V-1c top-level
nav entry enforced.

## Where it lives in the nav

**Vault hub sidebar → CRM** (`/vault/crm`).

Visible to any user with `customers.view`. Admins always have it.
Non-admin users with the permission explicitly granted also see it.

Legacy `/crm/*` URLs redirect to `/vault/crm/*` for one release
grace. Existing bookmarks still work.

## Key admin surfaces

| Surface | Path | Purpose |
|---|---|---|
| **CRM Hub** | `/vault/crm` | Landing — tiles link to companies / pipeline / FH view / etc. |
| **Companies List** | `/vault/crm/companies` | All `CompanyEntity` rows — filter by type, status, state, classification |
| **Company Detail** | `/vault/crm/companies/:id` | Per-company view: profile, contacts, activities, documents, health |
| **Duplicates** | `/vault/crm/companies/duplicates` | AI-flagged duplicate candidates for merge review |
| **Pipeline** | `/vault/crm/pipeline` | Kanban board across sales-pipeline stages |
| **Funeral Homes** | `/vault/crm/funeral-homes` | FH-scoped company view |
| **Contractors** | `/vault/crm/contractors` | Contractor-scoped company view |
| **Billing Groups** | `/vault/crm/billing-groups` | Multi-company billing group CRUD |
| **Billing Group Detail** | `/vault/crm/billing-groups/:id` | Member companies, consolidated AR view |
| **CRM Settings** | `/vault/crm/settings` | Scoring thresholds, duplicate auto-merge rules, etc. |

## Common workflows

### Find a company

1. `/vault/crm/companies`.
2. Start typing a name, phone, city, or tax-ID fragment in the
   search box. Matches return in ~100ms (indexed).
3. Results show customer type (funeral_home / cemetery / contractor
   / government / retail / vendor), classification confidence, last
   activity date, open-balance.
4. Click a row to open the company detail page.

### Review AI classification suggestions

Bridgeable classifies new companies using Intelligence (prompt
`crm.company_classification`). When confidence is below 0.85 the
row lands in the review queue.

1. `/vault/crm/companies` → filter by classification_source="ai" +
   classification_confidence < 0.85.
2. Click a row → Company Detail shows the AI's suggested type +
   reasoning.
3. Confirm or override the classification.
4. Confirmation updates `classification_reviewed_by` and
   `classification_reviewed_at`; overrides write the correction
   back as training feedback.

### Work the pipeline

1. `/vault/crm/pipeline` — Kanban columns per pipeline stage
   (typically: Lead / Qualified / Proposal / Won / Lost).
2. Drag-drop a company card to change stage. Stage changes write an
   activity log entry.
3. Click a card to open the company detail.
4. Click **"Add activity"** on any company card to log a call /
   email / note / meeting without leaving the pipeline.

### Review duplicates

1. `/vault/crm/companies/duplicates`.
2. The duplicate detector (AI-backed, Intelligence prompt
   `crm.duplicate_detection`) surfaces candidate pairs weekly.
3. Each row shows two companies + similarity score + per-field
   match details (name fuzzy-match, phone exact-match, address
   normalized-match).
4. Actions:
   - **Merge** — pick the winning record; the losing record's
     activity log, documents, and references migrate to the winner.
     Losing record is soft-deleted (`is_active=false`) but
     preserved for audit.
   - **Not a duplicate** — marks the pair as reviewed + dismisses
     from the queue. Future detector runs skip this pair.

### Monitor account health

The CRM Recent Activity widget + At-Risk Accounts widget on the
Vault Overview give a tenant-wide at-a-glance view. For per-company
detail:

1. `/vault/crm/companies/:id` → Health panel.
2. Shows current score (healthy / watch / at_risk / unknown) +
   reasons + history of recent score changes.
3. Score is recalculated nightly by
   `health_score_service.calculate_health_score()`. Signals include:
   - **Order recency** — "no order in N days where average is M
     days" beyond a multiplier threshold.
   - **Payment trend** — recent vs prior-period average days-to-pay
     trending longer.
4. Transition *into* `at_risk` fires an `account_at_risk`
   notification to tenant admins (V-1d source). Same-score nightly
   recalcs do NOT re-fire.

### Manage billing groups

A billing group consolidates multiple `CompanyEntity` rows under
one billing umbrella — useful when a multi-location FH chain bills
from one address.

1. `/vault/crm/billing-groups` → click **"Create group"**.
2. Name the group. Pick the billing address.
3. Add member companies via search + add button.
4. Each member's invoices route to the group's billing address;
   consolidated statements reference the group.

## Permission model

- **Sidebar entry requires `customers.view`.** Admins get this by
  default. Non-admin users need the permission explicitly granted.
- **Most CRUD operations require `customers.edit`.** Read-only
  users with `customers.view` see the pages but can't modify.
- **Duplicate merge requires `customers.admin`.** Destructive; only
  elevated roles can initiate.
- **Billing group CRUD requires `customers.admin`.** Changes flow
  to AR/billing downstream.

## Related services

- **Documents.** Contracts, statements, delivery confirmations
  attached to a company appear on Company Detail under the Documents
  tab. The shared-with-this-tenant inbox shows docs from counterparties.
- **Notifications.** Account-at-risk transitions fire notifications.
  Share-granted fires when a document is shared with the tenant
  (target-side admin fan-out).
- **Intelligence.** Classification, duplicate detection, and health
  scoring all call Intelligence. The Execution Log is the audit
  trail for those AI decisions.
- **Accounting.** Billing groups + charge accounts + AR aging tie
  back to companies. The CRM Companies list shows open balance
  per-company when the tenant has the accounting engine enabled.

## Known limitations

### CRM parallel contact models (Option B — deferred)

The CRM `Contact` model is NOT unified with three parallel contact
tables: `CustomerContact` (keyed on customer_id), `VendorContact`
(keyed on vendor_id), and `FHCaseContact` (keyed on fh_case_id,
carries portal-invitation fields). The same physical person can be
four separate rows.

V-1c (the lift-and-shift) scoped this out explicitly. Option B —
make `CompanyEntity` a first-class `VaultItem` with `item_type="account"`,
make `Contact` the canonical contact table, migrate the three
parallel tables to `Contact` + a role/tag column — remains deferred.

**Estimated effort from the V-1 audit: 6-8 weeks.** Blockers:
portal-invitation fields only exist on `FHCaseContact` today and
would need a JSONB `portal_settings` column on the unified contact
or a separate portal-settings table. Every CRUD call site across
backend + frontend needs to migrate.

Tracked in [`../DEBT.md`](../DEBT.md) as "CRM parallel contact
models unification."

### Pipeline stages hard-coded

The pipeline stages are defined in a constants file, not configurable
per tenant. Most tenants use the same stages; a future enhancement
could move this to `CrmSettings` for per-tenant customization.

### Duplicate detector is manual-trigger only today

Weekly batch scheduling works but there's no UI to "run duplicate
detection now" — for ad-hoc runs an admin calls the backend
endpoint directly or waits for the next scheduled run.

### No tenant-user CRM surface

Everything under `/vault/crm` is tenant-admin-visible. Tenant users
without `customers.view` don't see CRM at all. A tenant-facing
"my accounts" surface (e.g. for sales reps who should only see
companies they own) isn't built.

See [`../DEBT.md`](../DEBT.md) for the full list of deferred items.
