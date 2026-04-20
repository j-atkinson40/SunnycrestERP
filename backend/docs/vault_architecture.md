# Bridgeable Vault — Architecture

_Internal developer reference. Audience: Bridgeable developers —
including future-you working on V-2. For admin-facing "how do I use
this" content, see the per-service guides under [`vault/`](./vault/)._

**Status as of V-1h (April 2026):** 5 services registered
(Documents, Intelligence, CRM, Notifications, Accounting). Migration
head `r30_delivery_caller_vault_item`. 109+ Vault backend tests
passing.

---

## Table of contents

1. [Overview](#1-overview)
2. [Service model](#2-service-model)
3. [Services currently registered](#3-services-currently-registered)
4. [Widget framework](#4-widget-framework)
5. [Cross-cutting capabilities](#5-cross-cutting-capabilities)
6. [Integration seams — adding a new service](#6-integration-seams--adding-a-new-service)
7. [Migration head history](#7-migration-head-history)

---

## 1. Overview

### What Bridgeable Vault is

Bridgeable Vault is the shared foundational infrastructure layer that
every tenant sees regardless of vertical. It's not a feature — it's
the platform chassis that the verticals configure views over.

A single tenant running manufacturing looks at the same Vault a
funeral home tenant does. The *surfaces* differ by vertical (manu
sees Operations Board, FH sees Case Log) but the *underlying rows*
live in Vault tables. Cross-subsystem queries ("show me everything
about this company in the last 30 days") resolve by joining Vault
primitives — documents, events, notifications, activity log,
signatures — rather than by chasing specialty tables.

The pre-V-1 audit (`vault_audit.md`) found that most of this
infrastructure already existed, scattered across nav entries that
accreted over time. The `document_*` fabric (D-1 → D-9) gave us a
canonical `Document` model plus template registry plus native signing
plus cross-tenant sharing plus channel-agnostic delivery. The
`VaultItem` polymorphic row gave us a universal "things-in-the-vault"
container with 11 discriminators (5 actively dual-written). The
widget framework gave us a registry-based hub composition pattern.
What didn't exist was the **consolidation** — nothing tied those
primitives into one admin surface.

V-1 was the consolidation. Eight phases shipped across three weeks:

| Phase | Ship date | Focus |
|---|---|---|
| V-1a | 2026-04-20 | Hub frame + nav restructure |
| V-1b | 2026-04-20 | Overview dashboard + 5 widgets |
| V-1c | 2026-04-20 | CRM absorption (lift-and-shift) |
| V-1d | 2026-04-20 | Notifications promoted + SafetyAlert merge + 5 notification sources |
| V-1e | 2026-04-20 | Accounting admin consolidation |
| V-1f+g | 2026-04-20 | Quote VaultItem dual-write + polymorphic delivery + JE Case A |
| (bug fix) | 2026-04-20 | `audit_service.log` → `log_action` typo in `quote_service` |
| V-1h | 2026-04-20 | Documentation consolidation (this doc + related) |

### The architectural principle

**Every tenant across every vertical has Vault as top-level nav.
Verticals configure views over Vault primitives.**

Operationally this means:

- Vault is not a module you enable. It's always on.
- The 5 current services (Documents, Intelligence, CRM,
  Notifications, Accounting) register descriptors that the hub
  renders without coordination from the vertical preset.
- Verticals can add their own services in future phases by calling
  `register_service(...)`. Nothing in the hub framework is
  manufacturing-specific.
- Per-service visibility is gated by permission / module / extension.
  The hub renders what the caller can see; it doesn't pretend the
  rest doesn't exist.

### What's Vault-native today vs. vertical workflow

| Vault-native (lives in Vault nav) | Vertical workflow (lives in preset nav) |
|---|---|
| Documents | Invoices, bills, JEs, payments (Financials Hub) |
| Intelligence (prompt library + execution log) | Orders, deliveries, production, inventory |
| CRM (companies, pipeline, activities, health) | Safety, compliance (tenant-edit surfaces) |
| Notifications (all categories, unified feed) | Agents Hub (tenant runs agents + approves) |
| Accounting **admin** (periods, GL, tax, templates) | Accounting **workflow** (every tenant-facing AR/AP page) |

The Accounting split is the clearest illustration of the principle.
The *engine* — invoices, bills, JEs, statements, 12 agents, 60+
endpoints — is tenant workflow and stays in the vertical Financials
Hub. The *configuration* of that engine — lock a period, set an
agent's cron, review AI GL classifications, customize tax rates,
fork a statement template — is platform admin and lives under
`/vault/accounting`.

### What's coming (V-2+)

Not scoped yet. Deferred candidates from the V-1 audit + DEBT.md:

- **Calendar.** Unified view over VaultItems with `event_type`.
  Pending the item_type cleanup (JE Case A: decision whether JEs
  should appear on the calendar or not).
- **Reminders.** Proactive surface for upcoming VaultItem events
  (compliance expiry, delivery follow-up, etc).
- **CRM true absorption.** V-1c was lift-and-shift. Option B from the
  audit — make `CompanyEntity` a first-class VaultItem and unify
  the four parallel contact models (Contact / CustomerContact /
  VendorContact / FHCaseContact) — remains deferred.
- **Vault Sharing generalization.** D-6 Sharing is hard-coupled to
  `Document.id`. Generalizing to any VaultItem lets quotes, events,
  reminders etc. be cross-tenant-shared without re-inventing the
  mechanism.
- **Notification preferences.** Per-user per-category opt-out +
  daily digest + rate limiting for noisy categories.

None blocking V-1; all captured in `DEBT.md`.

---

## 2. Service model

### VaultHubRegistry pattern

The registry is a thin singleton dict keyed by `service_key`. There
are **two copies of it** — one backend, one frontend — populated at
code level in lockstep:

- **Backend:** `backend/app/services/vault/hub_registry.py`. Source
  of truth for the `GET /api/v1/vault/services` response and the
  permission filter that decides which services a user sees.
- **Frontend:** `frontend/src/services/vault-hub-registry.ts`.
  Source of truth for the sidebar render (icon, display name,
  ordering) and for widget component mapping. Widgets register
  themselves against this registry via the barrel at
  `frontend/src/components/widgets/vault/index.ts`.

Why two copies? The backend decides what the user can *see*
(permission gating, widget-data queries). The frontend decides how
to *render* it (which React component backs which widget_id, which
icon matches "Calculator"). Syncing them is a code-review step, not
a runtime handshake.

### VaultServiceDescriptor fields

Defined in `hub_registry.py`:

```python
@dataclass
class VaultServiceDescriptor:
    service_key: str               # Unique key (e.g. "documents")
    display_name: str              # UI label (e.g. "Documents")
    icon: str                      # lucide-react name
    route_prefix: str              # Frontend path (e.g. "/vault/documents")
    required_permission: str | None = None   # Gate: user must have this perm
    required_module: str | None = None       # Gate: tenant must have module
    required_extension: str | None = None    # Gate: tenant extension active
    overview_widget_ids: list[str] = []      # Widgets this service owns
    sort_order: int = 100                    # Sidebar ordering
```

**Key semantics:**

- `service_key` is used as the dict key in the registry and as the
  service identifier in widget definitions (each widget belongs to a
  service). Change it and you've broken the linkage.
- `route_prefix` must match the `<Route path="...">` in `App.tsx`.
  The frontend helper `vaultHubRegistry.findServiceForPath(path)`
  does longest-prefix matching so deep-linked paths (e.g.
  `/vault/documents/templates/abc-123`) resolve back to the owning
  service for active-state highlighting.
- `sort_order` convention: 10=Documents, 15=CRM, 20=Intelligence,
  30=Notifications, 40=Accounting. Leave 5-unit gaps so a future
  service can slot in without renumbering.
- `overview_widget_ids` is an ordered list — the first widget in the
  list gets the lowest `default_position` when the hub computes a
  default layout. Positions are seeded in `widget_registry.py` and
  shared across all overview widgets (the registry picks them by
  `default_position`, not by their index in `overview_widget_ids`).

### Permission filtering model

Filters apply in `GET /api/v1/vault/services` and `GET
/api/v1/vault/overview/widgets` (see `backend/app/api/routes/vault.py`).
Same logic both places:

```python
if not current_user.is_super_admin:
    if desc.required_permission and not user_has_permission(...):
        continue
    if desc.required_module and not is_module_enabled(...):
        continue
    if desc.required_extension and not active:
        continue
```

**Admin short-circuit.** `user_has_permission()` short-circuits to
`True` for users whose `role.slug == "admin"` — so the magic string
`required_permission="admin"` works as "admins only" even though
"admin" isn't a normal permission code. V-1e's Accounting service
uses this pattern.

**No gate = visible to any authenticated tenant user.** Documents +
Intelligence + Notifications all have `required_permission=None`.
Their individual endpoints still enforce `require_admin` per-route.
The hub-level gate is about *sidebar visibility*, not endpoint
security.

### Per-subtree permission gating in App.tsx

The pattern V-1c established. The `/vault/*` parent route mounts
`<VaultHubLayout />` unconditionally; each child sub-tree gets its
own permission gate:

```tsx
<Route path="/vault" element={<VaultHubLayout />}>
  <Route index element={<VaultOverview />} />

  {/* Documents + Intelligence — admin-only */}
  <Route element={<ProtectedRoute adminOnly />}>
    <Route path="documents">...</Route>
    <Route path="intelligence">...</Route>
  </Route>

  {/* CRM — permission-gated */}
  <Route element={<ProtectedRoute requiredPermission="customers.view" />}>
    <Route path="crm">...</Route>
  </Route>

  {/* Accounting — admin-only */}
  <Route element={<ProtectedRoute adminOnly />}>
    <Route path="accounting" element={<AccountingAdminLayout />}>...</Route>
  </Route>
</Route>
```

The Overview (index) is deliberately gate-free — any authenticated
tenant user can land on `/vault`. The overview widgets themselves
filter by service access server-side, so non-admins see an empty
grid rather than a 403.

**Why not gate at the `/vault` root?** Because CRM's permission
(`customers.view`) is different from Documents' (admin). A root-level
gate would require the *union* of every sub-tree's permission to
enter the hub at all — wrong. Per-subtree gating lets the user see
every sub-tree they have access to.

---

## 3. Services currently registered

### Documents (`service_key: "documents"`)

- **Route prefix:** `/vault/documents`
- **Sort order:** 10
- **Permission:** None (admin-gated per-route)
- **Overview widgets:** `vault_recent_documents`,
  `vault_pending_signatures`, `vault_unread_inbox`,
  `vault_recent_deliveries`
- **Phases shipped:** D-1 through D-9
- **Migration:** `r20` through `r28`

**What it owns.** The canonical `Document` + `DocumentVersion`
model, the template registry (`document_templates` +
`document_template_versions` with tenant-scope overrides), native
signing (`signature_envelopes` + PyMuPDF anchor overlay + ESIGN
certificate), cross-tenant sharing (`document_shares`), and
channel-agnostic delivery (`document_deliveries` + `DeliveryService`
+ `DeliveryChannel` Protocol).

**Key routes.**

| Route | Purpose |
|---|---|
| `/vault/documents` | Document Log |
| `/vault/documents/templates` | Template library |
| `/vault/documents/templates/:id` | Template detail + draft editor |
| `/vault/documents/inbox` | Admin inbox (documents shared TO this tenant) |
| `/vault/documents/deliveries` | Delivery log |
| `/vault/documents/deliveries/:id` | Delivery detail + resend action |
| `/vault/documents/signing` | Signing envelope library |
| `/vault/documents/signing/new` | Create envelope wizard |
| `/vault/documents/signing/:envelopeId` | Envelope detail |

**Architecture docs.** This service has its own dedicated docs that
predate V-1h. See `documents_architecture.md`, `documents_README.md`,
`signing_architecture.md`, and `delivery_architecture.md` for the
full D-1 → D-9 context. The V-1 work just moved the admin URLs from
`/admin/documents/*` to `/vault/documents/*`.

**User guide.** [`vault/documents.md`](./vault/documents.md).

### Intelligence (`service_key: "intelligence"`)

- **Route prefix:** `/vault/intelligence`
- **Sort order:** 20
- **Permission:** None (admin-gated per-route)
- **Overview widgets:** _(none — possible future addition for
  execution-volume / experiment-status)_
- **Migration:** `r16` (backbone) + `r17` (linkage columns) + `r18`
  (vision support)

**What it owns.** The unified AI layer. Every AI call in the platform
routes through `app.services.intelligence.intelligence_service.execute()`.
73 active platform-global managed prompts cover Scribe, accounting
agents, briefings, command bar, NL Overlay, Ask Assistant, urn
pipeline, safety, CRM, KB, onboarding, training, compose, workflows,
and vision. Each call writes an `intelligence_executions` row with
prompt_id, model_used, token counts, cost, latency, and typed caller
linkage.

**Key routes.**

| Route | Purpose |
|---|---|
| `/vault/intelligence` | Prompt library |
| `/vault/intelligence/prompts/:id` | Prompt detail + version history + draft editor |
| `/vault/intelligence/executions` | Execution log |
| `/vault/intelligence/executions/:id` | Execution detail (prompt, context, output, cost) |
| `/vault/intelligence/model-routes` | Model routing rules |
| `/vault/intelligence/experiments` | Experiment library |

**Guardrail.** Direct `anthropic` SDK imports are forbidden outside
the Intelligence package — lint-enforced via `test_intelligence_*_lint.py`.
Any AI code path goes through `intelligence_service.execute()`.

**User guide.** [`vault/intelligence.md`](./vault/intelligence.md).

### CRM (`service_key: "crm"`)

- **Route prefix:** `/vault/crm`
- **Sort order:** 15
- **Permission:** `customers.view`
- **Overview widgets:** `vault_crm_recent_activity`,
  `at_risk_accounts`
- **Phase:** V-1c (lift-and-shift)
- **Migration:** (no schema changes in V-1c — CRM tables predate Vault)

**What it owns.** Post-V-1c, the CRM is a full Vault service. Before
V-1c it was a top-level nav entry with its own route prefix (`/crm/*`).
V-1c moved all 9 CRM pages under `VaultHubLayout` at `/vault/crm/*`,
left all data models untouched, and added a new tenant-wide activity
endpoint at `GET /api/v1/vault/activity/recent` for the CRM activity
widget.

**Important limitation (tracked in DEBT.md).** The CRM `Contact`
model is NOT unified with three parallel contact tables
(`CustomerContact`, `VendorContact`, `FHCaseContact`). The same
physical person can be four separate rows. V-1c scoped this out
explicitly. Option B from the V-1 audit (make `CompanyEntity` a
first-class `VaultItem` + unify contacts) is the deferred
true-absorption work.

**Key routes.**

| Route | Purpose |
|---|---|
| `/vault/crm` | CRM hub landing |
| `/vault/crm/companies` | Companies list |
| `/vault/crm/companies/:id` | Company detail |
| `/vault/crm/companies/duplicates` | Duplicate review queue |
| `/vault/crm/pipeline` | Sales pipeline |
| `/vault/crm/funeral-homes` | FH-scoped view |
| `/vault/crm/contractors` | Contractor-scoped view |
| `/vault/crm/billing-groups` | Billing groups CRUD |
| `/vault/crm/settings` | CRM settings |

**Legacy `/crm/*` paths redirect** to `/vault/crm/*` for one release
grace. Removal is tracked in DEBT.md under "Vault V-1a/c/d redirect
scaffolding."

**User guide.** [`vault/crm.md`](./vault/crm.md).

### Notifications (`service_key: "notifications"`)

- **Route prefix:** `/vault/notifications`
- **Sort order:** 30
- **Permission:** None
- **Overview widgets:** `vault_notifications`
- **Phase:** V-1b (proto-service) → V-1d (promoted to full service,
  SafetyAlert merged)
- **Migration:** `r29_notification_safety_merge`

**What it owns.** The in-app notification fabric. Single
`notifications` table with 6 alert-flavor columns added in V-1d
(`severity`, `due_date`, `acknowledged_by_user_id`,
`acknowledged_at`, `source_reference_type`, `source_reference_id`).
Pre-V-1d `SafetyAlert` rows were data-migrated into
`notifications` with `category='safety_alert'`; the `safety_alerts`
table was dropped.

**5 notification sources wired in V-1d:**

1. `share_granted` — `document_sharing_service.grant_share` fan-outs
   to target-tenant admins.
2. `delivery_failed` — `delivery_service` terminal-failure helper
   (doesn't fire on `rejected` status — non-actionable SMS-stub).
3. `signature_requested` — `signature_service._advance_after_party_signed`
   fires an in-app notification when the next party's email matches
   an internal User (external signers get the email invite only).
4. `compliance_expiry` — `vault_compliance_sync` with severity
   escalation (<=7 days → "high", else "medium") and
   `source_reference_id` dedup so re-runs don't spam.
5. `account_at_risk` — `health_score_service.calculate_health_score`
   fires only on transition *into* at_risk (captures `prior_score`
   before mutation).

**Fan-out pattern.** `notification_service.notify_tenant_admins(...)`
creates one `Notification` row per active admin user per tenant
(joined via `Role.slug == "admin"`). All V-1d sources except
signature_requested use this; signature_requested targets a specific
internal signer.

**Top-level `/notifications` redirects** to `/vault/notifications`
for one release grace.

**User guide.** [`vault/notifications.md`](./vault/notifications.md).

### Accounting (`service_key: "accounting"`)

- **Route prefix:** `/vault/accounting`
- **Sort order:** 40
- **Permission:** `admin`
- **Overview widgets:** `vault_pending_period_close`,
  `vault_gl_classification_review`, `vault_agent_recent_activity`
- **Phase:** V-1e
- **Migration:** (no schema changes in V-1e — endpoints read existing
  models)

**What it owns.** Platform-admin consolidation surface for the
accounting engine. Six sub-tabs under `AccountingAdminLayout`:

| Tab | Route | Purpose |
|---|---|---|
| Periods & Locks | `/vault/accounting/periods` | `AccountingPeriod` CRUD + type-to-confirm lock/unlock + recent-activity feed |
| Agent Schedules | `/vault/accounting/agents` | `AgentSchedule` config for the 12 accounting agents + recent-jobs feed |
| GL Classification | `/vault/accounting/classification` | `TenantAccountingAnalysis` review queue + confirm/reject + bulk-confirm high-confidence |
| Tax Config | `/vault/accounting/tax` | `TaxRate` + `TaxJurisdiction` read-only (CRUD stays on `/settings/tax`) |
| Statement Templates | `/vault/accounting/statements` | Platform/tenant `StatementTemplate` split view (read-only in V-1e) |
| COA Templates | `/vault/accounting/coa` | Read-only expose of `PLATFORM_CATEGORIES` (27 categories × 5 types) |

**NOT in scope.** Tenant-facing Financials Hub (invoices, bills, JEs,
statements, reports) stays in the vertical nav. V-1e is the
**admin** surface for the accounting engine, not the engine itself.

**Period-lock UX.** Locking requires typing the exact period name
("March 2026") to confirm — destructive action, friction matches
stakes. Unlocking is a simple confirm — restoring write capability
is cheap. Both actions write `AuditLog` rows with
`entity_type="accounting_period"` and `action="period_locked" |
"period_unlocked"`, visible via `GET /vault/accounting/period-audit`.

**User guide.** [`vault/accounting.md`](./vault/accounting.md).

---

## 4. Widget framework

### WidgetGrid + useDashboard + WidgetPicker

The hub Overview uses the same infra as the Operations Board and
Financials Board. Three pieces:

- **`WidgetGrid`** (`frontend/src/components/widgets/WidgetGrid.tsx`)
  — responsive CSS grid with drag-reorder and resize. Accepts a
  `componentMap` prop (widget_id → React component) built from the
  `vaultHubRegistry` frontend widget registrations.
- **`useDashboard`** hook — pulls per-user layout from
  `/api/v1/widgets/layout?page_context=vault_overview`, debounces
  writes back on reorder/resize/remove. Falls back to the server's
  default_layout if no user layout exists.
- **`WidgetPicker`** slide-in — lets users add widgets they removed.
  Populated from the `is_available` widgets not in the current
  layout.

### Widget registration (frontend)

Each widget file under `components/widgets/vault/` registers itself
in the shared barrel:

```ts
// frontend/src/components/widgets/vault/index.ts
import { vaultHubRegistry } from "@/services/vault-hub-registry";
import PendingPeriodCloseWidget from "./PendingPeriodCloseWidget";

vaultHubRegistry.registerWidget({
  widget_id: "vault_pending_period_close",
  service_key: "accounting",
  component: PendingPeriodCloseWidget,
});
```

Convention: `widget_id` must match the backend `WIDGET_DEFINITIONS`
entry; `service_key` must match an `overview_widget_ids` entry on a
`VaultServiceDescriptor`. Mismatches are silent — the widget is
registered but never rendered because the overview endpoint won't
return it.

### Widget seeding (backend)

`backend/app/services/widgets/widget_registry.py` holds a
module-level list `WIDGET_DEFINITIONS` of dicts, one per widget. The
`seed_widget_definitions(db)` function inserts-or-updates them on
app startup (see `app/main.py`).

```python
{
    "widget_id": "vault_pending_period_close",
    "title": "Pending period close",
    "description": "...",
    "page_contexts": ["vault_overview"],
    "default_size": "2x1",
    "supported_sizes": ["1x1", "2x1", "2x2"],
    "category": "accounting",
    "icon": "Calendar",
    "default_enabled": True,
    "default_position": 8,
    "required_permission": "admin",
}
```

### UPSERT pattern (V-1c)

The seed originally did `ON CONFLICT DO NOTHING` — safe but meant
changes to an existing widget's definition required a migration. V-1c
changed it to `ON CONFLICT DO UPDATE` on the system-owned columns
(title, description, page_contexts, default_size, supported_sizes,
category, icon, default_enabled, default_position,
required_extension, required_permission, required_preset). Per-user
layouts in `user_widget_layouts` stay untouched — only the definition
metadata refreshes.

Upshot: extending a widget's `page_contexts` (e.g. making
`at_risk_accounts` appear in both `ops_board` and `vault_overview`)
is a code-ship — no migration.

### page_contexts multi-context pattern

A single widget definition can appear in multiple page contexts. The
V-1c canonical example: `at_risk_accounts` has
`page_contexts=["home", "ops_board", "vault_overview"]`. One backend
definition, one frontend component registration per `widget_id` (the
key is `widget_id` — last writer wins for extension overrides), three
rendering contexts.

When the hub overview queries `widget_service.get_available_widgets(
..., page_context="vault_overview")`, it returns only widgets whose
`page_contexts` list includes that string. The widget's
`default_position` is *shared* across contexts (single column in the
seed), so placement in one context shifts placement in another — see
V-1c's deliberate `at_risk_accounts` bump from position 3 → 7 to
preserve ops_board ordering.

### Default layout positions (V-1 snapshot)

| Position | Widget | Service |
|---|---|---|
| 1 | `vault_recent_documents` | Documents |
| 2 | `vault_pending_signatures` | Documents |
| 3 | `vault_unread_inbox` | Documents |
| 4 | `vault_recent_deliveries` | Documents |
| 5 | `vault_notifications` | Notifications |
| 6 | `vault_crm_recent_activity` | CRM |
| 7 | `at_risk_accounts` | CRM |
| 8 | `vault_pending_period_close` | Accounting |
| 9 | `vault_gl_classification_review` | Accounting |
| 10 | `vault_agent_recent_activity` | Accounting |

Positions are unique across the overview page context. A future
phase adding more widgets should claim positions 11+.

### Cross-phase extension pattern

When a new phase adds a widget to an existing service, the pattern is:

1. Add the definition to `WIDGET_DEFINITIONS` (backend) with a fresh
   `default_position`.
2. Add the widget component file under `components/widgets/vault/`.
3. Register the component in the barrel (`index.ts`).
4. Add the `widget_id` to the owning service's `overview_widget_ids`
   in `hub_registry.py` (backend).
5. On deploy, `seed_widget_definitions` inserts the new row.
6. Admin-gated widgets are invisible to non-admins — the service
   filter in `/vault/overview/widgets` strips them server-side.

No migration needed. The widget framework is code-first.

---

## 5. Cross-cutting capabilities

### Documents fabric (D-1 through D-9)

The most mature Vault capability. The `canonical_document.Document`
model has 7 specialty FKs (sales_order_id, fh_case_id, invoice_id,
customer_statement_id, price_list_version_id, etc.) plus polymorphic
entity linkage (entity_type + entity_id) plus source linkage
(caller_module, caller_workflow_run_id, caller_workflow_step_id,
intelligence_execution_id). Every template-rendered or AI-generated
artifact flows through `document_renderer.render(...)` which returns
a `Document` row linked to a `DocumentVersion` in R2.

**Template registry.** Managed templates with versioning + tenant
overrides + draft-to-active lifecycle + changelog audit. Hybrid scope
(platform-global `tenant_id=NULL` vs tenant-scoped) with
tenant-first lookup. 18 platform templates seeded from a single
migration (`r21`).

**Native signing.** ESIGN-compliant `SignatureEnvelope` state
machine (draft → sent → in_progress → completed/declined/voided/expired)
with PyMuPDF anchor overlay (signatures render on the signature lines
of the source document, matching DocuSign visual quality) + certificate
of completion as a managed template render + token-based public signer
routes (`/sign/{token}`, no auth, rate limited).

**Cross-tenant sharing.** `document_shares` fabric unifies 4 ad-hoc
cross-tenant mechanisms (statements, delivery confirmations, cross-tenant
statement rows, implicit legacy-vault-print sharing) into one admin
inbox with `visible_to()` abstraction for queries. Grant requires
active `PlatformTenantRelationship`; revoke is timestamp-only.

**Delivery abstraction.** `DeliveryChannel` Protocol + registry.
`email_channel.py` is the only module allowed to import `resend`
(lint-enforced). `DeliveryService.send(params)` is the single entry
point — resolves content (template or raw body), fetches
attachments, dispatches with inline retry, writes `document_deliveries`
rows.

**Full details.** See `documents_architecture.md`,
`signing_architecture.md`, `delivery_architecture.md`.

### Delivery service polymorphic via `caller_vault_item_id` (V-1f)

Before V-1f, `document_deliveries` had a nullable `document_id` FK but
no way to attribute a send to a non-Document source. V-1f added
`caller_vault_item_id` — the Quote send, compliance reminder,
account-at-risk notification etc. can now attribute to the originating
VaultItem without needing a Document row.

- Partial index: `ix_document_deliveries_caller_vault_item_id
  WHERE caller_vault_item_id IS NOT NULL`. Most deliveries are
  document-attached; the partial keeps the index small.
- `DeliveryService.SendParams` gains `caller_vault_item_id: str | None
  = None`. Zero existing callers affected; new callers opt in.
- Use case: V-1d's `_notify_delivery_failed` fan-out pattern
  generalized to any VaultItem-linked outbound message.

### Notifications — entity-agnostic + category-based

The V-1d schema absorbed SafetyAlert into Notification with 6
alert-flavor columns. Every source writes with:

- `category` — a short string (`safety_alert`, `share_granted`,
  `delivery_failed`, `signature_requested`, `compliance_expiry`,
  `account_at_risk`, plus pre-V-1d categories)
- `severity` — `critical` / `high` / `medium` / `low` (optional)
- `source_reference_type` + `source_reference_id` — polymorphic
  linkage back to the source entity (document, delivery, envelope,
  compliance item, company entity, etc.)
- `link` — frontend path to open when the notification is clicked

**Dedup pattern.** `compliance_expiry` dedupes by
`(company_id, category, source_reference_id)` — re-runs of
`vault_compliance_sync` don't re-fire for the same item.
`account_at_risk` dedupes by capturing `prior_score` before mutation
— only fires on transition *into* at_risk.

**Category vocabulary is ad-hoc.** There's no central registry of
category strings today; each source site hardcodes its own. Tracked
in DEBT.md as a future-polish item.

### Intelligence backbone

Every AI call in the platform routes through
`intelligence_service.execute(prompt_key=..., variables=...,
company_id=..., caller_module=..., caller_entity_*=...)`. The function
resolves the active version of the managed prompt, renders the
templated user message, executes via Anthropic (or the configured
model route), and writes an `intelligence_executions` audit row.

**Typed caller linkage.** The execution row has FK columns for every
caller category that writes to Intelligence: `caller_fh_case_id`,
`caller_agent_job_id`, `caller_workflow_run_id`,
`caller_ringcentral_call_log_id`, `caller_kb_document_id`,
`caller_price_list_import_id`, `caller_accounting_analysis_run_id`,
`caller_command_bar_session_id`, `caller_conversation_id`,
`caller_import_session_id`, `caller_delivery_id` (D-7),
`caller_document_share_id` (D-6). The reverse link — "which AI calls
did this thing trigger?" — is a straight index scan.

**Guardrails.** TID251 ruff rule + pytest lint gates forbid direct
`anthropic` SDK or `call_anthropic` imports outside the Intelligence
package. See `intelligence_audit_v3.md` for the migration context.

### VaultItem dual-write patterns

The `VaultItem` polymorphic model has 11 `item_type` discriminators.
Not all are dual-written — some are vault-only.

**Dual-written (writer → VaultItem mirror):**

| item_type | Writer | Phase |
|---|---|---|
| `document` | `delivery_service._sync_media_to_vault` | Vault Core |
| `event` | delivery, work orders, ops board, safety | Vault Core |
| `event` (compliance_expiry sub-type) | `vault_compliance_sync` | Vault Core |
| `event` (production_record) | `operations_board_service` | Vault Core |
| `event` (safety_training) | `safety_service` | Vault Core |
| `quote` | `quote_service.create_quote / convert / update_status` | **V-1f** |

**Vault-only (no separate specialty model):**

`communication`, `reminder`, `contact` — these live exclusively as
VaultItem rows. V-2 Calendar/Reminders work will formalize these.

**Not dual-written today:**

`order`, `case`, `asset` have focused models but don't dual-write.
Lower priority — V-1 didn't touch them.

`journal_entry` — **Case A**. JEs have no VaultItem coupling
anywhere. V-1f+g investigated and shipped a lint-style regression
guard (`test_je_posts_do_not_write_vault_item_today`). Future
decision deferred to V-2 Calendar planning: should JEs surface in
Vault activity at all? If yes, correct `item_type` is `document`
(JEs are historical artifacts, not calendar events) — using `event`
would pollute the Calendar.

**Defensive pattern.** Every V-1 dual-write wraps in
`try/except + logger.exception`. VaultItem failures never block the
primary operation. Example: Quote creation persists the Quote and
its VaultItem fan-out failure is logged separately. Same pattern as
V-1d notification fan-outs.

---

## 6. Integration seams — adding a new service

Step-by-step for plugging a new service into Vault. Mirror the V-1e
Accounting phase as a reference.

### Backend

1. **Pick a `service_key`.** Singular, lowercase, no hyphens.
   Convention: match the nav label (e.g. "accounting" for
   "Accounting").

2. **Register the service** in `_seed_default_services()` at
   `backend/app/services/vault/hub_registry.py`:

   ```python
   register_service(
       VaultServiceDescriptor(
           service_key="my_service",
           display_name="My Service",
           icon="LucideIconName",  # must exist in VaultHubLayout icon map
           route_prefix="/vault/my-service",
           required_permission=None,  # or "admin" / "some.permission"
           overview_widget_ids=["vault_my_widget"],
           sort_order=50,  # leave gaps
       )
   )
   ```

3. **Add new endpoints** under
   `backend/app/api/routes/vault_my_service.py` (if the service
   needs new routes). Mount in `app/api/v1.py` with prefix
   `/vault/my-service`. All new endpoints should enforce
   `require_admin` or an appropriate permission dep per call.

4. **Tenant scoping on every query** — filter by
   `current_user.company_id` every time. No exceptions.

5. **Widget definitions** (if the service has overview widgets):
   add dicts to `WIDGET_DEFINITIONS` in
   `app/services/widgets/widget_registry.py` with
   `page_contexts=["vault_overview"]` and a unique
   `default_position`.

6. **Tests** — create `backend/tests/test_vault_v1X_my_service.py`
   mirroring the V-1e / V-1d test file structure:
   - Hub registry assertions (registered, correct fields)
   - `/vault/services` visibility admin + non-admin
   - Endpoint behavior (happy path + cross-tenant 404 + admin gate)
   - Widget visibility admin + non-admin

### Frontend

1. **Icon.** Add the lucide-react name to `VaultHubLayout`'s
   `VAULT_ICON_MAP` (`frontend/src/pages/vault/VaultHubLayout.tsx`)
   and sidebar's `ICON_MAP` if needed.

2. **Register the service** in
   `frontend/src/services/vault-hub-registry.ts`:

   ```ts
   vaultHubRegistry.register({
     service_key: "my_service",
     display_name: "My Service",
     icon: "LucideIconName",
     route_prefix: "/vault/my-service",
     sort_order: 50,
   });
   ```

   Must match the backend descriptor.

3. **Route tree** in `App.tsx` — add a child under the `/vault`
   parent with the appropriate permission gate:

   ```tsx
   <Route element={<ProtectedRoute adminOnly />}>
     <Route path="my-service" element={<MyServiceLayout />}>
       <Route index element={<MyServiceTab />} />
       {/* sub-routes */}
     </Route>
   </Route>
   ```

4. **Widget components** under `frontend/src/components/widgets/vault/`:
   one file per widget. Each registers in the barrel
   (`components/widgets/vault/index.ts`):

   ```ts
   vaultHubRegistry.registerWidget({
     widget_id: "vault_my_widget",
     service_key: "my_service",
     component: MyWidget,
   });
   ```

5. **Frontend API service** at
   `frontend/src/services/my-service.ts` if the service exposes more
   than a handful of endpoints. Mirror the `accounting-admin-service.ts`
   pattern.

### Navigation

**Don't add a top-level nav entry.** The Vault hub is the entry
point. If your service needs discoverability, the path is:

1. Ensure it's in the Vault sidebar (automatic via `register_service`).
2. Add an Overview widget pointing at the service's landing page.
3. Consider a deep-link from an adjacent service (V-1f's "Customize
   quote template" link from the Quoting Hub is the canonical
   pattern).

### Existing-service integration

When your service triggers cross-cutting capabilities, use the
existing seams:

- **Generate a PDF / HTML artifact** →
  `document_renderer.render(template_key=..., context=...)` →
  returns a `Document` row.
- **Send an email / SMS** → `DeliveryService.send(params)` →
  set `caller_vault_item_id` for non-Document-attached sends.
- **Notify tenant admins** → `notification_service.notify_tenant_admins()`
  with a `category` string.
- **Call an LLM** → `intelligence_service.execute(prompt_key=...)`
  with a managed prompt.
- **Share a document cross-tenant** →
  `document_sharing_service.grant_share(...)` (requires
  `PlatformTenantRelationship`) or `ensure_share(...)` for
  auto-share generator paths.
- **Write a VaultItem** → `vault_service.create_vault_item(...)`
  with the appropriate `item_type` and wrap in try/except +
  logger.exception so a VaultItem failure doesn't break the primary
  flow.

### Audit + tests

- Audit writes go through `audit_service.log_action(db, company_id,
  action, entity_type, entity_id, user_id=..., changes=...)`.
  Convention: past-participle verb for `action`
  (`created`/`updated`/`converted`/`status_changed`).
- Every new route needs at least one cross-tenant isolation test.
- Permission gates need admin + non-admin coverage.

---

## 7. Migration head history

Vault-adjacent migrations in order. Full list is in
`backend/alembic/versions/`; this table highlights the ones that
shaped V-1.

| Migration | Phase | What it did |
|---|---|---|
| `r16_intelligence_backbone` | Intelligence Phase 1 | `intelligence_*` tables |
| `r17_intelligence_linkage_columns` | Intelligence Phase 2c-0a | `caller_*` FKs on `intelligence_executions` |
| `r18_intelligence_vision_support` | Intelligence Phase 2c-0b | Content-block support for vision prompts |
| `r20_documents_backbone` | D-1 | Canonical `Document` + `DocumentVersion` |
| `r21_document_template_registry` | D-2 | `document_templates` + versions + seed |
| `r22_document_template_editing` | D-3 | Draft lifecycle + audit log |
| `r23_native_signing` | D-4 | `signature_envelopes` + state machine |
| `r24_disinterment_native_signing` | D-5 | Disinterment signing cutover |
| `r25_document_sharing` | D-6 | `document_shares` + events |
| `r26_delivery_abstraction` | D-7 | `document_deliveries` + linkage columns |
| `r27_inbox_read_tracking` | D-8 | Per-user inbox read state |
| `r28_d9_quote_wilbert_templates` | D-9 | Quote + Wilbert form templates seeded |
| `r29_notification_safety_merge` | **V-1d** | 6 alert-flavor columns on `notifications`, SafetyAlert merge, `safety_alerts` dropped |
| `r30_delivery_caller_vault_item` | **V-1f** | `document_deliveries.caller_vault_item_id` + partial index |

V-1a / V-1b / V-1c / V-1e / V-1g / V-1h were code-only (no schema
changes).

### Migration discipline

Two guardrails enforced across V-1:

- **Idempotent `op.add_column` / `op.create_table` / `op.create_index`.**
  Monkey-patched in `alembic/env.py`. Lets the same migration chain
  run on both fresh DBs and DBs where tables were created outside
  migrations (e.g. test fixtures that seed from `Base.metadata`).
- **`ON CONFLICT DO UPDATE` on seed rows** — widget definitions,
  platform templates, hub registry service descriptors. Definition
  metadata refreshes on every deploy without a migration per change.
  Per-user / per-tenant customization rows (user_widget_layouts,
  tenant template overrides) stay untouched.

---

## See also

- [`vault_README.md`](./vault_README.md) — developer entry point
  (short)
- [`vault_audit.md`](./vault_audit.md) — pre-V-1 retrospective
  (long — ground-truth survey of what existed before the V-1 build)
- [`documents_architecture.md`](./documents_architecture.md) — full
  Documents arc (D-1 → D-9)
- [`documents_README.md`](./documents_README.md) — Documents phase
  map + admin surfaces
- [`signing_architecture.md`](./signing_architecture.md) — D-4/D-5
  native signing
- [`delivery_architecture.md`](./delivery_architecture.md) — D-7
  delivery abstraction
- [`intelligence_audit_v3.md`](./intelligence_audit_v3.md) — full
  Intelligence migration (Phase 1 → Phase 3d)
- [`DEBT.md`](./DEBT.md) — deferred items, including V-2 candidates
- [`BUGS.md`](./BUGS.md) — pre-existing bugs (not caused by V-1)
- Per-service user guides under [`vault/`](./vault/)
