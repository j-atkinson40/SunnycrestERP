# Bridgeable Vault — Pre-V-1 Audit

_Ground-truth survey of the Vault-adjacent platform surfaces before the V-1 Vault Hub build._

**Date:** 2026-04-19
**Audit only** — no code changes, no migrations, no implementation. Output is this document.
**Scope:** The platform as of commit `310c109` (post Documents Phase D-9).

---

## Executive summary

Bridgeable has most of the Vault infrastructure already built — it's just scattered across nav entries that accreted over time. The `document_*` fabric (D-1 → D-9) gave us a canonical Document model + template registry + native signing + cross-tenant sharing + channel-agnostic delivery. The `VaultItem` polymorphic model (Vault Phase 1-2) gave us a universal "things-in-the-vault" row type with 11 item_types. The widget framework (WidgetGrid + `OperationsBoardRegistry`) gave us a registry-based hub-composition pattern. The Notification model + service + sidebar dropdown + `/notifications` page gave us an in-app inbox. What doesn't exist is the **consolidation**: there's no Vault Hub that ties these together into one admin surface.

The V-1 build is primarily a nav restructure + hub composition, not net-new infrastructure. Three concrete surprises from the audit: (1) the CRM is substantially more mature than expected — 47 endpoints, 9 pages, AI classification, health scoring — and is a complete architectural island with zero VaultItem / FHCase / SalesOrder integration, so consolidating it under Vault is a thoughtful schema decision not a greenfield build; (2) of the 11 VaultItem item_types, only 5 are actively dual-written (document, event, order, compliance_item, production_record) — 3 are vault-only (communication, reminder, contact) and 3 have focused models that don't dual-write (quote, case, asset); (3) of the four cross-cutting capabilities, Delivery is already structurally generalized (`document_id` is nullable) but Sharing and Signing are hard document-coupled (NOT NULL FK), meaning V-1 can lift Delivery for free and must defer Sharing + Signing to V-2.

This audit is the input for V-1 scoping. It does not propose V-1 itself — that comes next, informed by these findings plus the open questions in §9.

---

## Table of contents

1. [Nav inventory](#1-nav-inventory) — 79 entries across 4 verticals + platform admin
2. [VaultItem item_type coverage](#2-vaultitem-item_type-coverage) — what has focused models vs. vault-only
3. [CRM deep dive](#3-crm-deep-dive) — models, routes, pages, services, consolidation readiness
3A. [Accounting deep dive](#3a-accounting-deep-dive) — native engine, 12 agents, platform-admin vs tenant-workflow split _(extension audit)_
3B. [Quoting deep dive](#3b-quoting-deep-dive) — Quoting Hub, D-9 Document integration, V-1 gaps _(extension audit)_
4. [Notifications / reminders surface](#4-notifications--reminders-surface) — what exists, what's missing
5. [Widget infrastructure](#5-widget-infrastructure) — frameworks, registries, reuse assessment
6. [Cross-cutting capabilities](#6-cross-cutting-capabilities) — sharing / delivery / signing / notifications generalization
7. [Vertical vs. platform distinctions](#7-vertical-vs-platform-distinctions) — per-item_type consolidation recommendation
8. [Overview dashboard data sources](#8-overview-dashboard-data-sources) — widget-by-widget backing endpoint
9. [Synthesis + V-1 scope sketch + open questions](#9-synthesis--v-1-scope-sketch--open-questions)
10. [Appendix A — Full nav catalog](#appendix-a--full-nav-catalog)
11. [Appendix B — CRM model summary table](#appendix-b--crm-model-summary-table)
12. [Appendix C — Widget components inventory](#appendix-c--widget-components-inventory)
13. [Appendix D — Accounting subsystem catalog](#appendix-d--accounting-subsystem-catalog) _(extension)_
14. [Appendix E — Quoting subsystem catalog](#appendix-e--quoting-subsystem-catalog) _(extension)_

---

## 1. Nav inventory

### How nav works

Navigation is declared in `frontend/src/services/navigation-service.ts` via vertical-preset dispatcher functions: `getManufacturingNav`, `getFuneralHomeNav`, `getCemeteryNav`, `getCrematoryNav`. Each returns an array of `NavItem` objects that the sidebar (`frontend/src/components/layout/sidebar.tsx`) renders.

Filtering is applied by `filterByPermission()` at `navigation-service.ts:724-750` in this order:

1. **`adminOnly`** — non-admin users filtered out (line 734).
2. **`requiresModule`** — tenant must have the module enabled (line 736).
3. **`requiresExtension`** — tenant extension must be active (line 738).
4. **`permission`** string — admins bypass; non-admins checked against flat permissions Set (line 740).
5. **`functionalArea`** — applied only when areas configured; `full_admin` bypasses (lines 742-746).

Structural features:

- **Sub-nav** (`children` array) renders as nested, collapsible groups. Legacy Studio has 4 children (lines 191-221).
- **`settingsGroup`** — the Settings section subdivides into Business / People / Communication / Integrations / Operations / Network / Platform groups (`sidebar.tsx:331-429`).
- **`isHub: true`** — hub items get visual emphasis (dividers, accent styling).
- **Platform admin** uses a separate sidebar — `frontend/src/components/layout/admin-sidebar.tsx` — with its own nav tree for super-admin tasks.

### Numbers

- **79 total nav entries** across the four tenant verticals plus the platform admin sidebar.
- **Manufacturing: 44 entries** (largest preset).
- **Funeral Home: 12.**
- **Cemetery: 7.**
- **Crematory: 8.**
- **Platform admin: 16** (separate sidebar).

### Vault-adjacency summary

Counting the `Settings → Platform` subgroup alone (lines 380-448 of `navigation-service.ts`), **5 nav entries are explicitly Documents-adjacent** today:

| Entry | Path | File:line |
|---|---|---|
| Documents | `/admin/documents/templates` | nav:415-420 |
| Document Log | `/admin/documents/documents` | nav:422-427 |
| Inbox | `/admin/documents/inbox` | nav:429-434 |
| Delivery Log | `/admin/documents/deliveries` | nav:436-441 |
| Signing | `/admin/documents/signing/envelopes` | nav:443-448 |

Plus 3 more Intelligence entries (Intelligence, Experiments, Workflows) and Notifications (FH only, `nav:572`). That's the nascent Vault today — tucked inside `Settings → Platform`.

### Full Vault-adjacency categorization

See [Appendix A](#appendix-a--full-nav-catalog) for the complete 79-entry table. Summary counts by category:

| Category | Count | Examples |
|---|---|---|
| `vault-adjacent` | 18 | Documents, Templates, Inbox, Delivery Log, Signing, Intelligence, Experiments, CRM, Quoting, Financials, Agents, Notifications, Knowledge Base, Training, Legacy Studio, Compliance, FTC Compliance, Chain of Custody |
| `vertical-workflow` | 28 | Order Station, Operations Board, Scheduling Board, Production Hub, Resale, Active Cases, Interments, Plot Map, Deeds, Crematory Cases/Schedule, Price List (FH), Obituaries |
| `platform-admin` | 22 | Company Profile, Branding, Team Dashboard, Employees, Users & Roles, Permissions, Email settings, Workflows, Programs & Products, Compliance Config, Locations, Billing, Extensions, Onboarding, all 16 admin-sidebar entries |
| `boundary-candidate` | 11 | Quoting, Financials, CRM (visible as hub in multiple verticals), Call Intelligence, Accounting integration, Disinterment settings, Union Rotations, Home dashboards |

The boundary-candidates are worth calling out: **Quoting, Financials, and CRM appear as hub-marked top-level items in both the Manufacturing and Funeral Home verticals** (`nav:128-156` for mfg; `nav:510-520` for FH). That's existing evidence the platform already treats these as cross-vertical. They're prime candidates to become Vault views — or to remain standalone hubs with Vault-like widget compositions.

### Existing groupings that already suggest Vault

1. **`Settings → Platform` subgroup** (nav:380-448) — already holds Documents, Document Log, Inbox, Delivery Log, Signing, Intelligence, Experiments, plus Extensions / Onboarding / Billing. This subgroup is the nascent Vault.
2. **Hub items** (manufacturing nav:126-187) — `isHub: true` marks Quoting, Financials, Agents, CRM, Production, Resale, Compliance. Financials + CRM appear in _all_ verticals' hub rows.
3. **`Resources` section** (nav:227-256) — Knowledge Base, Training, Legacy Studio grouped together. Cross-cutting knowledge / content.
4. **Per-vertical Compliance** — manufacturing has `/compliance`, FH has `/funeral-home/compliance`, crematory has `/crematory/custody`. Three separate compliance entry points with conceptually-unified backing data.

### Permission strings (sample)

- `ar.view` — AR / Quoting / Order Station (nav:97, 133).
- `customers.view` — CRM hub, visible across verticals (nav:155, 513).
- `operations_board.view` — Operations Board (nav:104).
- `safety.view` — Compliance hub (nav:177).
- `training.view`, `legacy_studio.view`, `users.view`, `settings.users.manage`, `fh_cases.view/create`, `fh_compliance.view`, `fh_price_list.view`.
- Extension gates: `urn_sales`, `disinterment_management`.
- Module gates: `sales`, `driver_delivery`, `safety_management`, `ai_obituary_builder`.

See Appendix A for the per-entry gating.

---

## 2. VaultItem item_type coverage

### Model shape

`backend/app/models/vault_item.py:12-132` defines the polymorphic row type:

- **`item_type`** (String(30), indexed, `line 28-30`) — the 11-value discriminator: `document | event | communication | reminder | order | quote | case | contact | asset | compliance_item | production_record`.
- **`event_type`** (String(50), indexed, `line 51-53`) — sub-discriminator for events: `delivery | route | driver_assignment | production_pour | production_strip | work_order | safety_training | compliance_expiry | maintenance`.
- **`event_type_sub`** (String(50), `line 54-56`) — compliance sub-type: `cdl | dot | hut | osha_300a | equipment_inspection | forklift_cert | npca`.
- **`document_type`** (String(50), `line 39-41`) — document sub-type: `delivery_confirmation | mold_config | batch_record | qc_photo | training_completion | training_material | inspection_cert | repair_record | asset_photo | asset_purchase | po | po_confirmation | coi | vendor_contract | payment_confirmation`.
- **`metadata_json`** (JSONB, `line 116-117`) — per-item-type flexible fields.
- **`source_entity_id`** (`line 99-101`) — back-reference to the originating focused-model row (e.g., `delivery.id` when `event_type="delivery"`).
- **`shared_with_company_ids`** (JSONB, `line 72-74`) — cross-tenant visibility array, predates D-6's canonical sharing.
- **`company_id`** (FK to companies) — tenant scope.

### Coverage matrix

| item_type | Focused model | Admin surfaces | Backend route prefix | Dual-write service(s) | Category | Notes |
|---|---|---|---|---|---|---|
| `document` | `Document` (D-1 canonical, `canonical_document.py:42`) + `DocumentVersion` | DocumentLog, DocumentDetail, DocumentTemplateLibrary, DocumentInbox at `/admin/documents/*` | `/api/v1/documents-v2/*` | `delivery_service` (media → delivery_confirmation), `safety_service` (training cert), also owner-scoped `document_renderer` writes | **vault-adjacent** | Mature. Canonical post-D-1. Legacy `Document` model backs `documents_legacy` for old-API compat. |
| `event` | `DeliveryEvent`, `PourEvent`, and 5+ focused event models | `/production/production-board`, `/delivery-detail`, `/operations-board` | `/api/v1/deliveries/*`, `/api/v1/production/*` | `delivery_service` (dual-writes route + delivery events), `work_order_service` (pour events), `operations_board_service` (production log), `safety_service` (training events), `vault_compliance_sync` (compliance expiry) | **vertical-workflow** (today) but Vault-adjacent via calendar | The workhorse item_type — 5 services dual-write to it. Many event_type sub-values. |
| `communication` | **none** | **none** | **none** | none | **vault-only** | No focused model, no admin surface. Reserved for future inbound email / SMS / call logs. |
| `reminder` | **none** | **none** | **none** | none | **vault-only** | No focused model. `notify_before_minutes` field on VaultItem suggests it was designed for this, but nothing writes it today. |
| `order` | `SalesOrder` (`sales_order.py`), `UrnOrder` (`urn_order.py`) | `/sales-orders.tsx`, `/order-station`, `/urns/orders.tsx` | `/api/v1/sales-orders/*`, `/api/v1/urns/*` | **none** (VaultItem not written on order creation) | **vertical-workflow** | Focused model exists; no dual-write. Orders are fundamentally vertical today. |
| `quote` | `Quote` (`quote.py:20`) + `QuoteLine` | `/quotes.tsx`, `/quote-detail` | `/api/v1/quotes/*` | **none** (Quote does NOT dual-write) | **vertical-workflow** | Canonical model; no VaultItem integration. D-9 gave Quote first-class Document status via `quote.standard` template. |
| `case` | `FHCase` (`fh_case.py`), `DisintermentCase` (`disinterment_case.py`), `CrematoryCase` | `/funeral-home/case-list`, `/funeral-home/case-detail`, `/disinterments/*` | `/api/v1/cases/*`, `/api/v1/disinterments/*` | **none** (no dual-write observed) | **vertical-workflow** | Despite being major domain entities, no VaultItem dual-write. Cases stay in FH vertical. |
| `contact` | `Contact` (`contact.py:17`) linked to `CompanyEntity` | Embedded in CRM `/crm/companies/:id` — no dedicated admin list | (via `/api/v1/company-entities/{id}/contacts`) | **none** | **vault-only** for the item_type; CRM has its own focused model | CRM Contact model exists but doesn't write VaultItem. Parallel CustomerContact / VendorContact / FHCaseContact models exist — see §3. |
| `asset` | **none** | **none** | **none** | none | **vault-only** (unimplemented) | Reserved; nothing writes it. |
| `compliance_item` | Implicit — handled via `VaultItem(item_type="event", event_type="compliance_expiry")` | `/hubs/compliance-hub`, `/settings/compliance`, `/safety/*` | `/api/v1/safety/*` | `vault_compliance_sync` writes compliance events, not compliance_item rows directly | **vault-adjacent** | Interesting: the `compliance_item` item_type is rarely used; compliance surfaces through `event` with `event_type="compliance_expiry"` + `event_type_sub` instead. |
| `production_record` | `PourEvent`, `ProductionLogEntry` | `/hubs/production-hub`, `/production-log`, `/console/production-console` | `/api/v1/production-log/*` | `operations_board_service` (dual-write) | **vertical-workflow** | Unique mix: `item_type="production_record"` with `event_type="production_pour"` — only item_type that layers both discriminators for the same entity. |

### Dual-write paths — verified

- **Delivery → VaultItem** — `delivery_service._sync_delivery_to_vault()` writes `item_type="event", event_type="delivery", source_entity_id=delivery.id`. ✓
- **Safety training → VaultItem** — `safety_service.create_training_event()` writes `item_type="event", event_type="safety_training", source_entity_id=event.id` with metadata including `osha_standard_code` and `trainer_name`. ✓
- **Pour events → VaultItem** — `work_order_service` writes `item_type="event", event_type="production_pour"`. ✓
- **Delivery media (photos/signatures) → VaultItem(document)** — `delivery_service._sync_media_to_vault()` creates `item_type="document", document_type="delivery_confirmation|delivery_media"` rows per upload. ✓
- **Compliance expiry** — `vault_compliance_sync` writes `item_type="event", event_type="compliance_expiry"` with `event_type_sub` set to the specific cert type. ✓

### Unexpected findings

1. **5 of 11 item_types are actively dual-written.** `document`, `event`, `production_record` — plus `compliance_item` indirectly (via `event`). `communication`, `reminder`, `asset` have zero code paths writing them.
2. **Focused models exist without dual-write for 3 item_types.** `order` (SalesOrder + UrnOrder), `quote` (Quote), `case` (FHCase, DisintermentCase, CrematoryCase) — all have mature models but none write to VaultItem on creation.
3. **Compliance uses events, not compliance_item.** The `compliance_item` item_type is vestigial; compliance flows all use `event` with `event_type="compliance_expiry"`. This is a schema cleanup candidate for V-1 or later.
4. **Routes become first-class VaultItems.** A delivery route isn't a sub-event of the delivery — it's its own `item_type="event", event_type="route"` row. That's notable for a Vault calendar widget that wants to group.
5. **Production records uniquely layer both discriminators.** It's the only case where `item_type` and `event_type` are both set non-trivially for the same entity. Likely accidental but worth noting.

---

## 3. CRM deep dive

The CRM predates the Bridgeable Vault architecture. It's substantially more mature than expected — a complete customer-relationship stack centered on `CompanyEntity` as the B2B hub. It's also a complete architectural island: **zero VaultItem integration, zero FHCase integration, and zero SalesOrder write-back**. Consolidating it under Vault is a thoughtful schema decision.

### 3.1 Summary

Scope of what a tenant admin can do today:

- Manage B2B companies the tenant interacts with (customers, vendors, cemeteries, funeral homes, licensees, crematories, print shops, contractors).
- Maintain contacts per company (with flags: primary, receives_invoices, receives_legacy_proofs, linked_user_id).
- Log manual activities (calls, notes, visits, complaints) with follow-up assignment.
- Auto-ingest system activities (invoice sent, legacy proof approved, etc.) as tagged references.
- Run AI classification (Claude + Google Places) to categorize unclassified companies and apply role flags.
- Track sales pipeline opportunities (prospect → closed stages).
- View account health score (healthy / watch / at-risk / unknown) based on order recency and payment trend.
- Configure CRM settings (pipeline enabled, health scoring enabled, risk thresholds).
- Review and resolve duplicate / merge candidate companies.
- Manage billing group hierarchies (parent ↔ child company relationships).

Tenant scoping is strict (`company_id` on every row); **no cross-tenant CRM** — each tenant sees only its own contacts, activities, opportunities.

### 3.2 Models

**`Contact`** (`backend/app/models/contact.py:17-56`)
- CRM person-level record linked to `master_company_id` → CompanyEntity.
- Fields: `name`, `title`, `phone`, `mobile`, `email`, `role`, `is_primary`, `is_active`, `receives_invoices`, `receives_legacy_proofs`, `linked_user_id`, `linked_auto` (AI-suggested flag), `notes`.
- Tenant: `company_id`.
- **No VaultItem dual-write.**

**`CrmOpportunity`** (`backend/app/models/crm_opportunity.py:1-40`)
- Sales pipeline opportunity.
- Fields: `prospect_name`, `prospect_city/state`, `title`, `stage` (default "prospect"), `estimated_annual_value`, `assigned_to`, `expected_close_date`, `notes`, `lost_reason`.
- Optional link to `master_company_id` (pre-existing company) or free-form prospect name.

**`ActivityLog`** (`backend/app/models/activity_log.py:1-44`)
- System + manual event log against companies.
- Fields: `activity_type` (call/note/visit/complaint/etc.), `is_system_generated`, `title`, `body`, `outcome`, `follow_up_date`, `follow_up_assigned_to`, `follow_up_completed`, `related_order_id`, `related_invoice_id`, `related_legacy_proof_id`, `source`, `transcript`.
- **`related_*_id` fields are informational tags, not enforced FKs** — they're String columns so any service can reference without lock-step schema changes.

**`CrmSettings`** (`backend/app/models/crm_settings.py:1-28`)
- Per-tenant CRM toggles + health-scoring thresholds.
- Fields: `pipeline_enabled`, `health_scoring_enabled`, `activity_log_enabled`, `at_risk_days_multiplier`, `at_risk_payment_trend_days`, `at_risk_payment_threshold_days`.

**`CompanyEntity`** (`backend/app/models/company_entity.py`)
- The CRM hub. One row = one real-world B2B company the tenant interacts with.
- Fields: `name`, `legal_name`, `phone`, `email`, `website`, address (5 fields), 7 role flags (`is_customer`, `is_vendor`, `is_cemetery`, `is_funeral_home`, `is_licensee`, `is_crematory`, `is_print_shop`), `is_active`, `customer_type` (9 values), `contractor_type` (5 values), `is_aggregate`, classification fields (`classification_confidence`, `classification_source`, `classification_reasons`, `original_name`, `name_cleanup_actions`, `classification_reviewed_by`), `google_places_id`, `google_places_type`, `parent_company_id` (self-ref for billing groups), `is_billing_group`, `billing_preference`, `fulfilling_location_id`.
- Relationships: `Customer.master_company_id` and `Vendor.master_company_id` link INTO CompanyEntity.
- **Role flag + customer_type combination drives CRM visibility** — see `crm_visibility_service`.

**`CustomerContact`** (`backend/app/models/customer_contact.py`), **`VendorContact`** (`backend/app/models/vendor_contact.py`), **`FHCaseContact`** (`backend/app/models/fh_case_contact.py`) — three **parallel contact models** exist outside the CRM Contact model. Each is scoped to its own parent (Customer / Vendor / FHCase). Not unified with CRM Contact. This is the single biggest schema friction point for Vault consolidation.

### 3.3 Routes

**File: `backend/app/api/routes/company_entities.py`** (1959 lines) — 47 endpoints. Detailed enumeration:

**Company CRUD (5 endpoints)**

- `GET /` — list CRM-visible companies (applies `CrmVisibilityFilter`, paginated, search, role-flag filters).
- `GET /search?q=` — free-text name search.
- `GET /{id}` — one CompanyEntity, full detail.
- `POST /` — create new CompanyEntity; creates `CrmSettings` row if missing for the tenant.
- `PATCH /{id}` — update company (name, address, contact, role flags, notes).

**Contacts (6 endpoints)**

- `GET /{id}/contacts` — confirmed + AI-suggested contacts for a company (partitioned by `linked_auto`).
- `POST /{id}/contacts` — create contact; clears previous primary if `is_primary=true` supplied.
- `PATCH /{id}/contacts/{cid}` — update contact (name, title, phone, email, role, invoice/proof flags, primary).
- `DELETE /{id}/contacts/{cid}` — soft-delete (is_active=false, clear primary).
- `POST /{id}/contacts/{cid}/confirm` — convert auto-suggested to confirmed (`linked_auto=false`).
- `POST /{id}/contacts/{cid}/dismiss` — hard-delete for dismissed suggestions.

**Activity log (5 endpoints)**

- `GET /{id}/activity` — paginated activity feed for company.
- `POST /{id}/activity` — log manual activity (call/note/visit/complaint; optional follow-up assignment).
- `PATCH /{id}/activity/{aid}` — update activity (title, body, outcome, follow-up).
- `POST /{id}/activity/{aid}/complete-followup` — mark follow-up completed (sets timestamp).
- `DELETE /{id}/activity/{aid}` — remove activity record.

**Health scoring (3 endpoints)**

- `GET /health-summary` — counts of companies by health score (healthy/watch/at_risk/unknown).
- `GET /{id}/health` — calculated health score for one company.
- `POST /{id}/health/recalculate` — trigger recalc for one company.

**Opportunities (4 endpoints)**

- `GET /opportunities` — paginated list, filterable by stage/assignee.
- `POST /opportunities` — create opportunity (prospect name, stage, value, close date).
- `PATCH /opportunities/{oid}` — update (stage, value, assignee, lost_reason).
- `DELETE /opportunities/{oid}` — remove.

**Classification — AI-driven (10 endpoints)**

- `GET /classify/run-bulk` — trigger AI classification job on unclassified companies (Claude via Intelligence + Google Places).
- `GET /classify/review-queue` — list companies pending human classification review.
- `POST /{id}/classify/confirm` — accept AI-proposed classification and apply role flags.
- `POST /classify/confirm-bulk` — confirm multiple classifications at once.
- `POST /classify/reclassify-bulk` — reclassify a batch of companies via AI.
- `POST /classify/delete-bulk` — mark companies as inactive/aggregate (data-quality cleanup).
- `POST /classify/confirm-all` — accept all pending AI classifications.
- `GET /classify/fix-role-flags` — repair role flags for companies with out-of-sync state.
- `GET /{id}/classify/reclassify` — trigger AI reclassification for one company.
- `GET /classify/summary` — stats (classified, pending review, unclassified, aggregates, inactive).

**Settings + visibility (4 endpoints)**

- `GET /crm-settings` — tenant's CRM feature toggles + health thresholds.
- `PATCH /crm-settings` — update `pipeline_enabled`, `health_scoring_enabled`, thresholds.
- `GET /crm-hidden-count` — counts of companies hidden from CRM by reason.
- `GET /crm-hidden-companies` — actual hidden companies grouped by reason + labels.

**Merge review + name cleanup (3 endpoints)**

- `GET /migration-reviews` — pending customer-vendor merge reviews.
- `POST /merge-review/{rid}` — confirm or skip merge decision.
- `POST /{id}/revert-name` — revert cleaned company name to original.

**Related data (4 endpoints)**

- `GET /{id}/invoices` — invoices for company (via Customer linked to master_company_id).
- `GET /{id}/bills` — bills for company (via Vendor).
- `GET /{id}/legacy-proofs` — legacy proof documents.
- `GET /{id}/relationships` — network relationships (cemetery–location mappings, customer–vendor links).

**Funeral homes shortcut (1 endpoint)**

- `GET /funeral-homes` — list all active FH companies (`is_funeral_home=true`, `is_active=true`).

**Total: 45 endpoints** (the earlier count of 47 included 2 summary endpoints not in the file; the file itself exposes 45).

All tenant-scoped (filters by `current_user.company_id`). **No role-based gates observed** — any user of a tenant can access any CRM endpoint. This is a simplification that V-1 may want to tighten. Future work: introduce `crm.view` / `crm.edit` / `crm.classify` permissions.

### 3.4 Frontend pages

**Directory: `frontend/src/pages/crm/`** — 9 pages:

| Page file | Route | Feature | Desktop/Mobile |
|---|---|---|---|
| `companies.tsx` | `/crm/companies` | CRM hub list (filter by type/role, health badges, quick actions) | Desktop |
| `companies-list-mobile.tsx` | `/crm/companies` (mobile) | Mobile-optimized list (card layout, swipe actions) | Mobile |
| `company-detail.tsx` | `/crm/companies/:id` | Full profile w/ tabs: overview, activity, orders, contacts, invoices, bills, legacy proofs; embedded AI chat, voice memo | Desktop |
| `company-detail-mobile.tsx` | `/crm/companies/:id` (mobile) | Stacked-card single-column layout | Mobile |
| `crm-settings.tsx` | `/crm/crm-settings` | Configure pipeline / health-scoring / thresholds | Both |
| `pipeline.tsx` | `/crm/pipeline` | Kanban sales-pipeline view, drag between stages | Both |
| `funeral-homes.tsx` | `/crm/funeral-homes` | Dedicated list of FH customers | Both |
| `contractors.tsx` | `/crm/contractors` | Extension-gated contractor list (wastewater / redi_rock / general) | Both |
| `duplicates.tsx` | `/crm/duplicates` | Resolve duplicates, pending classifications, hidden companies | Both |
| `billing-groups.tsx` | `/crm/billing-groups` | Manage billing-group hierarchies | Both |
| `billing-group-detail.tsx` | `/crm/billing-groups/:id` | Billing group detail, child locations, billing preference | Both |

Nav integration: **`CRM` is a hub-marked top-level entry** visible in both Manufacturing (`nav:151-156`) and Funeral Home (`nav:513`) presets with `permission: customers.view`.

### 3.5 Services

**`backend/app/services/crm/`** — 6 service files:

- **`contact_service.py`** (145 lines) — CRUD + role management for Contact. Methods: `get_contacts` (partitions confirmed + AI-suggested), `create_contact`, `update_contact`, `soft_delete_contact`, `hard_delete_contact` (dismissed suggestions), `confirm_contact` (suggested → confirmed), `set_primary`, `get_proof_recipients`, `get_invoice_recipients`.
- **`activity_log_service.py`** (155 lines) — System + manual event logging. Methods: `log_system_event` (called by services on invoice send / legacy proof / etc.), `log_manual_activity` (with optional follow-up), `get_feed` (paginated), `complete_followup`.
- **`crm_visibility_service.py`** (475 lines) — Visibility filtering. The gnarliest service. Extension-gated: contractors hidden unless wastewater / redi_rock / general_precast extension active. Methods: `get_crm_visible_filter` (SQLAlchemy filter), `is_crm_visible`, `get_hidden_count`, `get_hidden_companies`, `check_extension_crm_unlock`.
- **`health_score_service.py`** (275 lines) — Account health scoring. Reads SalesOrder + CustomerPayment to compute healthy / watch / at_risk / unknown. Writes reasons to `ManufacturerCompanyProfile`.
- **`classification_service.py`** (600+ lines) — AI-powered company classification using Claude (via Intelligence service) + Google Places. Includes name-cleanup logic, inactive-pattern detection, aggregate-pattern detection, bulk coordination.
- **`billing_group_service.py`** (300+ lines) — Billing hierarchy management (parent_company_id, billing_preference = single_payer vs split_payment).

### 3.6 Cross-cutting integration — reality check

| Integration | Status | Evidence |
|---|---|---|
| **VaultItem dual-write** | **None.** CRM does not write VaultItem rows. | No `create_vault_item` calls in any CRM service. |
| **FHCase linkage** | **None.** CRM Contact ≠ FHCaseContact. Case contacts are case-centric, not company-centric. | `fh_case_contact.py` is a separate model with no FK to Contact. |
| **SalesOrder linkage** | **Read-only.** `ActivityLog.related_order_id` is informational tag (String, not FK). `health_score_service` reads SalesOrder to compute health but doesn't write back. | `activity_log.py` `related_order_id: Mapped[str | None]` — not a FK. |
| **Customer / Vendor linkage** | `Customer.master_company_id` + `Vendor.master_company_id` both → CompanyEntity. | Hierarchical; unifies a CompanyEntity with its AR + AP rows. |
| **Parallel contact models** | Yes — CustomerContact, VendorContact, FHCaseContact not unified with CRM Contact. | 3 separate tables exist; same person could be 4 separate rows across them. |
| **Cross-tenant visibility** | **None.** Tenant-scoped only. No shared contacts between licensee + FH. | All queries filter by `company_id`. |
| **Permission model** | Tenant membership only. No role-based gates within CRM. | Routes check `current_user.company_id`, no `require_permission(...)` calls. |

### 3.7 Consolidation readiness: moderate

**What migrates cleanly to Vault:**
- `CompanyEntity` → Vault view of `item_type="contact"` rows (or a richer `item_type="account"` if we add one).
- `Contact` → straightforward lift.
- `ActivityLog` → Vault activity feed; `related_*_id` tags become Vault-item linkage.
- `CrmOpportunity` → Vault pipeline view.
- Health scoring — read-only, already pulls from SalesOrder + CustomerPayment; no schema change.
- Classification — already uses the Intelligence managed prompt service; only the UI changes.

**What's awkward:**
- **Parallel contact models.** CustomerContact / VendorContact / FHCaseContact are _not_ CRM contacts. If Vault unifies them, data migration + multiple schema reconciliations. If it doesn't, tenant admins see the same person 4 times across 4 surfaces. This is the single biggest design decision in the CRM consolidation.
- **Extension-gated visibility.** `crm_visibility_service.get_crm_visible_filter()` is 475 lines of business rules (role flags + customer_type + extension + explicit hides). Vault will need this visibility layer in place — it's not something V-1 can rewrite without losing business logic.
- **Billing groups.** Self-referential parent_company_id hierarchy for consolidated billing. Maps fine to Vault but the UI needs hierarchical drill-down.
- **AI classification workflow.** The "review-queue" for AI classifications is a CRM-specific UI. If Vault has a generic "items needing review" list, classification could consolidate; otherwise stays CRM-specific.

**Bottom line:** the CRM is ready to be absorbed **conceptually** into Vault, but V-1 scope choices will determine whether it's a lift-and-shift (9 pages moved under /vault/crm/*) or a true absorption (VaultItem becomes the canonical contact model, parallel contact tables reconciled). I recommend the former for V-1 and deferring the deeper absorption to V-2+.

---

## 3A. Accounting deep dive

_Audit extension added after the initial audit. Confirms the Accounting subsystem is mature, native (QBO/Sage deprecated but still configurable), and has both platform-admin and tenant-workflow surfaces that must be separated during V-1 consolidation._

### 3A.1 Summary

The platform has built a **comprehensive native double-entry accounting engine** that supersedes the earlier QuickBooks Online / Sage 100 integration abstraction. The `AccountingConnection` model (`backend/app/models/accounting_connection.py`) still tracks provider selection (`quickbooks_online | quickbooks_desktop | sage_100 | native`) + OAuth tokens + sync state for tenants that haven't cut over, but the native engine is the production path. All accounting data is tenant-scoped (`company_id` FK) except platform-level infrastructure (COA templates, tax defaults, standard GL category definitions).

Scope: full GL + COA, journal entries (with recurring templates, reversals, corrections), AR (invoices, payments, statements, finance charges), AP (bills, purchase orders, vendor payments), reconciliation (CSV imports, AI-suggested matching), tax (jurisdiction resolution, multi-rate), period locks (platform-admin enforced), financial reporting (13 report types), cross-tenant statements (manufacturer → funeral home), and **12 proactive accounting agents** for month-end close, collections, cash receipts, 1099 prep, year-end close, tax package, annual budget, budget-vs-actual, inventory reconciliation, expense categorization, estimated tax prep, and unbilled orders.

The **platform-admin vs tenant-workflow split** is explicit in code (`require_admin`, `require_permission` guards) and configuration (navigation-service permission gates). Platform admin surfaces are what V-1 consolidates under Vault Hub; tenant workflow stays in the `Financials` hub + vertical nav.

### 3A.2 Models (28+ models)

**GL + Journal core:**

- **`JournalEntry`** (`backend/app/models/journal_entry.py:14-42`) — `tenant_id`-scoped. Fields: `entry_number` (unique per tenant), `entry_type`, `status` (draft | posted), `entry_date`, `period_month`/`period_year`, `description`, `reference_number`, `is_reversal`, `reversal_of_entry_id`, `recurring_template_id`, `corrects_record_type`/`corrects_record_id`, `total_debits`, `total_credits`, `created_by`, `posted_by`, `posted_at`. One-to-many with `JournalEntryLine`. **Role: tenant workflow.**
- **`JournalEntryLine`** (`journal_entry.py:46-61`) — `tenant_id`-scoped. `line_number`, `gl_account_id`, `gl_account_number`, `gl_account_name`, `description`, `debit_amount`, `credit_amount`. Double-entry enforced by service layer. **Tenant workflow.**
- **`JournalEntryTemplate`** (`journal_entry.py:64-84`) — `tenant_id`-scoped. `template_name`, `frequency`, `day_of_month`, `months_of_year` (JSONB), `next_run_date`, `is_active`, `auto_post`, `auto_reverse`, `reverse_days_after`, `template_lines` (JSONB). Recurring JE scheduler. **Tenant workflow.**
- **`AccountingPeriod`** (`journal_entry.py:87-98`) — `tenant_id`-scoped, unique on `(tenant_id, period_year, period_month)`. Fields: `status` (open | closed), `closed_by`, `closed_at`. Gates invoice / bill / JE / payment writes via period-lock enforcement. **Platform admin.**

**AR side:**

- **`Invoice`** (`invoice.py:20+`) — `company_id`-scoped. Fields: `number` (INV-YYYY-####), `customer_id`, `sales_order_id`, `status` (draft | sent | paid | partial | overdue | void | write_off), `invoice_date`, `due_date`, `payment_terms`, `subtotal`, `tax_rate`, `tax_amount`, `total`, `amount_paid`, `discount_amount`, `discount_deadline`, `discounted_total`, `deceased_name`, `sent_at`, `requires_review`, `review_due_date`, `auto_generated`, `generation_reason`, `has_exceptions`, `sage_invoice_id`, `qbo_id`. **Tenant workflow.**
- **`CustomerPayment`** (`customer_payment.py:17-75`) — `company_id`-scoped. `payment_date`, `total_amount`, `payment_method` (check | ach | credit_card | cash | wire), `reference_number`, `sage_payment_id`, `qbo_id`. One-to-many `CustomerPaymentApplication`. **Tenant workflow.**
- **`CustomerPaymentApplication`** (`customer_payment.py:77-85`) — maps payment → invoice with `amount_applied`. **Tenant workflow.**

**AP side:**

- **`VendorBill`** (`vendor_bill.py:17-100`) — `company_id`-scoped. Fields: `number` (BILL-YYYY-####), `vendor_id`, `po_id`, `status` (draft | pending | approved | paid | partial | void), `bill_date`, `due_date`, `subtotal`, `tax_amount`, `total`, `amount_paid`, `source` (manual | received_statement), `received_statement_id`, `attachment_url`, `qbo_id`, `approved_by`, `approved_at`. **Tenant workflow.**
- **`VendorBillLine`** (`vendor_bill_line.py`) — `line_number`, `product_id`, `description`, `quantity`, `unit_price`, `line_amount`, `tax_amount`, `gl_account_id`, `po_line_id`. **Tenant workflow.**
- **`VendorPayment`** (`vendor_payment.py:17-80`) + **`VendorPaymentApplication`** (`vendor_payment_application.py:16-37`) — symmetric to customer side. **Tenant workflow.**
- **`PurchaseOrder`** (`purchase_order.py:22+`) — `company_id`-scoped. Fields: `number` (PO-YYYY-####), `vendor_id`, `status` (draft | sent | partial | received | closed | cancelled), `order_date`, `expected_date`, `shipping_amount`, `requires_approval`, `approval_status`, `approved_by`, `approved_at`. **Tenant workflow.**
- **`PurchaseOrderLine`** (`purchase_order_line.py`) — tracks `received_quantity` for three-way match. **Tenant workflow.**

**Tax configuration:**

- **`TaxRate`** (`tax.py:14-27`) — `tenant_id`-scoped, unique on `(tenant_id, rate_name)`. `rate_percentage` (Numeric 6,4), `is_default`, `gl_account_id`. **Platform admin.**
- **`TaxJurisdiction`** (`tax.py:30-45`) — `tenant_id`-scoped, unique on `(tenant_id, state, county)`. `state`, `county`, `zip_codes` (ARRAY), `tax_rate_id`. Used by `tax_service.get_jurisdiction_for_order()` to resolve line-item tax. **Platform admin.**

**Finance charges (AR late fees):**

- **`FinanceChargeRun`** (`finance_charge.py:14-46`) — `tenant_id`-scoped, unique on `(tenant_id, charge_year, charge_month)`. Fields: `run_number`, `status` (calculated | posted), `calculation_date`, `rate_applied`, `balance_basis`, `compound`, `grace_days`, `minimum_amount`, `minimum_balance`, counters (`total_customers_evaluated`, `total_customers_charged`, etc.), `calculated_by` (agent | manual). One-to-many `FinanceChargeItem`. **Tenant workflow.**
- **`FinanceChargeItem`** (`finance_charge.py:49-74`) — per-customer charge row. `eligible_balance`, `rate_applied`, `calculated_amount`, `minimum_applied`, `final_amount`, `aging_snapshot` (JSONB), `review_status` (pending | approved | rejected), `forgiveness_note`, `posted`, `invoice_id`, `journal_entry_id`. **Tenant workflow.**

**Statements:**

- **`StatementTemplate`** (`statement.py:14-31`) — `tenant_id` nullable (platform seeds defaults). Fields: `template_key`, `template_name`, `customer_type` (all | specific), `is_default_for_type`, `sections` (JSONB array), `logo_enabled`, `show_aging_summary`, `show_account_number`, `show_payment_instructions`, `remittance_address`, `payment_instructions`. **Hybrid: platform admin seeds + tenant customization.**
- **`StatementRun`** (`statement.py:34-68`) — `tenant_id`-scoped, unique on `(tenant_id, statement_period_month, statement_period_year)`. Fields: `status` (draft | generated | sent | complete), counters (total / flagged / sent / failed / digital / mail / none), `initiated_by`, `custom_message`, `zip_file_url`. One-to-many `CustomerStatement`. **Tenant workflow.**
- **`CustomerStatement`** (`statement.py:71+`) — per-customer statement from a run. `aging` breakdown, `balance`, `invoice list`. **Tenant workflow.**

**Reconciliation:**

- **`FinancialAccount`** (`financial_account.py:13-39`) — `tenant_id`-scoped. `account_type` (bank | credit_card), `account_name`, `institution_name`, `last_four`, `gl_account_id`, `last_reconciled_date`, `last_reconciled_balance`, `credit_limit`, `statement_closing_day`, CSV-column mapping (`csv_date_column`, `csv_description_column`, etc.). **Tenant workflow.**
- **`ReconciliationRun`** (`financial_account.py:42-73`) — `tenant_id`-scoped. `status` (importing | in_progress | complete | error), `statement_date`, `statement_closing_balance`, counters (`auto_cleared_count`, `suggested_count`, `unmatched_count`), computed totals (`platform_cleared_balance`, `outstanding_checks_total`, `adjustments_total`, `difference`), `confirmed_by`, `confirmed_at`, `csv_file_path`. **Tenant workflow.**
- **`ReconciliationTransaction`** (`financial_account.py:76-99`) — one bank CSV row. `match_status` (unmatched | suggested | confirmed | rejected), `match_confidence` (0-1), `matched_record_type` (invoice | payment | bill | journal_entry), `matched_record_id`, `match_notes`. **Tenant workflow.**

**Cross-tenant billing (manufacturer → funeral home):**

- **`ReceivedStatement`** (`received_statement.py:13-36`) — `tenant_id` + `from_tenant_id` (cross-tenant). Fields: `relationship_type`, `customer_statement_id`, `statement_period_month/year`, `previous_balance`, `new_charges`, `payments_received`, `balance_due`, `invoice_count`, `statement_pdf_url`, `status` (unread | read | disputed | paid). **Tenant workflow** but explicitly cross-tenant.
- **`StatementPayment`** (`received_statement.py:41-60`) — payment submitted by recipient tenant against a ReceivedStatement. `amount`, `payment_method`, `submitted_by`, `acknowledged_by_manufacturer`. **Tenant workflow.**

**COA classification + GL mapping (platform infrastructure):**

- **`TenantAccountingImportStaging`** (`accounting_analysis.py:13-24`) — `tenant_id`-scoped. Staging for imported GL records (`qbo_import | sage_import | csv_import`). **Platform admin** (pre-processing before confirmation).
- **`TenantAccountingAnalysis`** (`accounting_analysis.py:27-45`) — AI-classified accounting items. `platform_category` (Sales, COGS, Expense, etc.), `confidence`, `reasoning`, `alternative`, `status` (pending | confirmed | rejected). **Platform admin.**
- **`TenantGLMapping`** (`accounting_analysis.py:48-59`) — maps tenant COA → platform's 100+ standard GL categories. `platform_category`, `account_number`, `account_name`, `provider_account_id`, `is_active`. **Platform infrastructure** (enables cross-tenant financial reporting).
- **`TenantAlert`** (`accounting_analysis.py:62-76`) — accounting anomalies (duplicate invoice, unmatched payment, period-lock violation). `severity`, `action_label`, `action_url`, `resolved`, `resolved_by`. Agent-generated. **Tenant workflow** (the anomaly itself) but **platform admin** (the rules that produce them).

**Connection + sync (legacy but still referenced):**

- **`AccountingConnection`** (`accounting_connection.py:1-100+`) — `company_id`-scoped. Fields: `provider` (quickbooks_online | quickbooks_desktop | sage_100), `status`, `setup_stage`, OAuth token storage (`qbo_access_token_encrypted`, `qbo_refresh_token_encrypted`, `sage_api_key_encrypted`), `sync_config` (JSONB), `account_mappings` (JSONB), `last_sync_at`, `last_sync_status`, `accountant_email`, `accountant_token`, `skip_count`. **Platform admin** (tenant-specific integration config).

**Accounting agents:**

The 12 agents under `backend/app/services/agents/` each have their own state in `AgentJob` + `AgentAnomaly` + `AgentSchedule` tables (tenant-scoped). Each agent writes rows; the admin dashboard reads them. Agents themselves are platform code; their config + output is tenant data.

### 3A.3 Routes — with platform-admin vs tenant-workflow labels

**`accounting.py`** — provider abstraction
- `GET /providers` — list available providers. **Platform admin.**
- `GET /status` — current provider connection health. **Both.**
- `POST /test` — test provider connection. **Platform admin.**
- `PATCH /provider` — switch provider. **Platform admin.**

**`accounting_connection.py`** — OAuth + accountant invitations. **Platform admin setup.**

**`journal_entries.py`** — JE CRUD + templates + periods
- `GET /entries`, `POST /entries`, `POST /entries/parse` (AI-assisted), `POST /entries/:id/post`, `POST /entries/:id/reverse` — **Tenant workflow.**
- `GET/POST /templates` — recurring JE templates. **Tenant workflow.**
- `POST /periods/open`, `POST /periods/close` — **Platform admin.**

**`vendor_bills.py`**, **`vendor_payments.py`** — AP. **All tenant workflow.**

**`reconciliation.py`** — bank reconciliation. **All tenant workflow.**

**`tax.py`** — tax config + resolution
- `GET/POST /rates`, `GET/POST /jurisdictions` — **Platform admin.**
- `POST /resolve-line`, `POST /resolve-invoice` — **Tenant workflow.**

**`statements.py`** — statement run + templates
- `POST /runs`, `GET /runs/:id`, `POST /runs/:id/generate`, `POST /runs/:id/send` — **Tenant workflow.**
- `GET /templates`, `POST /templates` — **Platform admin + tenant customization.**

**`finance_charges.py`** — monthly charge calc + posting. **Tenant workflow.**

**`purchase_orders.py`** — PO lifecycle. **Tenant workflow.**

**`agents.py`**
- `POST /jobs/trigger`, `GET /alerts`, `POST /alerts/:id/resolve`, `GET /collections/sequence`, `POST /collections/pause`, `GET /jobs` — **Tenant workflow.**
- `POST /period/lock`, `POST /period/unlock` — **Platform admin.**

**`financial_health.py`**, **`financials_board.py`** — dashboards. **Tenant workflow.**

### 3A.4 Services catalog (20+ services)

- **`financial_report_service.py`** — 13+ report types: `get_income_statement`, `get_ar_aging_report`, `get_ap_aging_report`, `get_sales_by_customer`, `get_invoice_register`, `get_tax_summary`, `run_health_check`. **Tenant workflow.**
- **`report_intelligence_service.py`** — AI-assisted commentary + anomaly detection. **Tenant workflow.**
- **`tax_service.py`** — `get_jurisdiction_for_order`, `compute_tax`, `get_tax_preview`. **Tenant workflow** (uses platform-admin tax config).
- **`invoice_settings_service.py`** — per-company invoice config (numbering, terms, auto-email, approval). **Tenant workflow** (read) + **platform admin** (initial setup).
- **`draft_invoice_service.py`** — auto-invoice from sales orders. **Tenant workflow.**
- **`fh_invoice_service.py`** — funeral-home-specific invoicing. **Tenant workflow (FH vertical).**
- **`vendor_bill_service.py`** — bill CRUD + approval + posting. **Tenant workflow.**
- **`vendor_payment_service.py`** — payment recording + application + batch runs. **Tenant workflow.**
- **`early_payment_discount_service.py`** — discount calculation on invoices. **Tenant workflow.**
- **`finance_charge_service.py`** — monthly finance charge calc + post. **Tenant workflow.**
- **`statement_generation_service.py`** — statement aggregation (aging, invoices, payment instructions). **Tenant workflow.**
- **`statement_pdf_service.py`** — renders statement PDFs via `DocumentRenderer` (D-2 migrated). **Tenant workflow.**
- **`cross_tenant_statement_service.py`** — B2B statement delivery (includes Vault share, D-6). **Tenant workflow** (with cross-tenant semantics).
- **`statement_service.py`** — statement run orchestration; sends via `DeliveryService` (D-7 migrated). **Tenant workflow.**
- **`purchase_order_service.py`** — PO lifecycle + three-way match. **Tenant workflow.**
- **`accounting_analysis_service.py`** — Claude Haiku COA classification; writes `TenantAccountingAnalysis` → `TenantGLMapping`. **Platform admin.**
- **`financial_health_service.py`** — key metrics (cash, DSO, DPO, expense ratio). **Tenant workflow.**

**12 accounting agents** under `backend/app/services/agents/`:

| Agent | Module | Purpose | Scope |
|---|---|---|---|
| AR Collections | `ar_collections_agent.py` | Monitors aging, drafts collection emails, tracks sequence | Tenant workflow |
| Cash Receipts Matching | `cash_receipts_agent.py` | Auto-matches customer payments to invoices | Tenant workflow |
| Unbilled Orders | `unbilled_orders_agent.py` | Identifies orders ready for invoicing, auto-drafts | Tenant workflow |
| Month-End Close | `month_end_close_agent.py` | 8-step close + statement run + period lock | Tenant workflow (triggers platform-admin period lock) |
| Year-End Close | `year_end_close_agent.py` | Extends month-end with full-year summary + depreciation + retained earnings | Tenant workflow (+ platform period lock) |
| Estimated Tax Prep | `estimated_tax_prep_agent.py` | Quarterly estimated-tax liability (federal + state) | Tenant workflow |
| 1099 Prep | `prep_1099_agent.py` | Aggregates 1099-reportable vendor payments | Tenant workflow |
| Tax Package Compilation | `tax_package_agent.py` | Packages GL + schedules for tax prep | Tenant workflow |
| Annual Budget | `annual_budget_agent.py` | Creates annual budget from prior year + assumptions | Tenant workflow |
| Budget vs Actual | `budget_vs_actual_agent.py` | Monthly variance report | Tenant workflow |
| Inventory Reconciliation | `inventory_reconciliation_agent.py` | Reconciles inventory GL to physical count | Tenant workflow |
| Expense Categorization | `expense_categorization_agent.py` | Classifies bills/expenses via Intelligence | Tenant workflow |

All agents extend `BaseAgent` (`agents/base_agent.py`); month-end uses the full approval path (statement run + period lock); weekly agents use simple approval.

### 3A.5 Frontend pages

| Page | Route | Platform / Tenant | Notes |
|---|---|---|---|
| `/admin/accounting.tsx` | `/admin/accounting` | **Platform admin** | Provider connection status, sync config, COA setup, GL mapping review |
| `/financials` hub | `/financials` | **Tenant workflow** | Dashboard with cash, AR, AP, P&L summary, quick links |
| `financials-board.tsx` | `/financials-board` | **Tenant workflow** | 6-zone widget board (briefing / ar / ap / cashflow / reconciliation / agent_activity) |
| `/ar/ar-aging.tsx` | `/ar/aging` | **Tenant workflow** | Aging by customer |
| `/ar/customer-payments.tsx` | `/ar/payments` | **Tenant workflow** | Customer payment history + application |
| `/ar/invoices.tsx` | `/ar/invoices` | **Tenant workflow** | Invoice list with filters + bulk actions |
| `/ar/invoice-detail.tsx` | `/ar/invoices/:id` | **Tenant workflow** | Single invoice detail |
| `/ar/statements.tsx` | `/ar/statements` | **Tenant workflow** | Statement run init + batch generation + delivery |
| AP pages (bills, payments) | `/ap/*` | **Tenant workflow** | — |
| `journal-entries.tsx` | `/journal-entries` | **Tenant workflow** | Manual JE creation + templates + period-specific list |
| `purchase_orders.tsx` | `/purchase-orders` | **Tenant workflow** | PO list + lifecycle |
| `finance_charges.tsx` | `/finance-charges` | **Tenant workflow** | Monthly run config + per-customer breakdown |
| reconciliation pages | `/reconciliation/*` | **Tenant workflow** | Bank account list + CSV upload + matching |
| `/agents/AgentDashboard.tsx` | `/agents` | **Tenant workflow** | Run agents + view history + manage period locks |
| `/agents/ApprovalReview.tsx` | `/agents/:id/review` | **Tenant workflow** (token-auth) | Review anomalies + approve / reject with period lock |
| `/settings/integrations/accounting` | `/settings/integrations/accounting` | **Platform admin** | Provider setup + sync config |

### 3A.6 Nav integration

- Manufacturing: `Financials` hub (`nav:137-143`), `Agents` hub (`nav:145-149`), `Accounting` under `Settings → Integrations` (`nav:322-327`, badge-enabled if sync error).
- Funeral Home: `Financials` hub (`nav:512`), `Integrations` (`nav:570`).
- Cemetery: `Financials` hub (`nav:622`).
- Crematory: `Financials` hub (`nav:690`).
- All functionalArea-gated on `invoicing_ar`; settings entries `adminOnly`.

### 3A.7 Integration with existing Vault capabilities

**VaultItem dual-write:** ✓ posted invoices, bills, JEs, statements write VaultItems (see vault_compliance_sync + accounting_analysis paths). Reconciliation is excluded by design (internal GL housekeeping).

**DocumentRenderer:** ✓ invoice PDFs (D-1), statement PDFs (D-2), finance-charge notices (D-2 email path), received-statement notifications. All cross-checked against `test_documents_d2_lint.py` — no direct `weasyprint.HTML(...)` calls outside the managed renderer.

**DeliveryService (D-7):** ✓ invoice emails, statement emails, collections emails, accountant invitation emails — all route through DeliveryService. `D-9 removed the _fallback_company_id safety net` — every accounting email now threads tenant company_id explicitly.

**Intelligence:** ✓ COA classification (Claude Haiku, confidence ≥ 0.85 auto-approve), expense auto-categorization, report commentary (stub, pending implementation). Uses managed prompt library (not direct SDK).

**Cross-tenant sharing (D-6):** ✓ manufacturer statements delivered to funeral homes write `DocumentShare` rows via `cross_tenant_statement_service.deliver_statement_cross_tenant()`; funeral home sees them in `/admin/documents/inbox`.

**Period locks:** the platform-admin period-lock system integrates with every tenant-workflow write path — `sales_service.py` calls `PeriodLockService.check_date_in_locked_period()` before writing invoices/payments; raises `PeriodLockedError` (HTTP 409) on violation.

### 3A.8 Platform admin vs tenant workflow — consolidated

| Surface | Platform admin | Tenant workflow | Notes |
|---|---|---|---|
| Chart of accounts templates / 100+ standard GL categories | ✓ | — | V-1 Vault candidate; tenant customizes via TenantGLMapping |
| Provider connection (QBO / Sage / native) | ✓ | — | V-1 Vault candidate; tenant can view connection status but can't switch |
| Accountant invitations | ✓ | — | Currently `/admin/accounting`; V-1 Vault candidate |
| Tax rates + jurisdictions | ✓ | — | V-1 Vault candidate; tenant-scoped but configured once |
| Accounting periods (open / close) | ✓ | — | V-1 Vault candidate; period-lock enforcement |
| Period locks | ✓ | — | V-1 Vault candidate |
| Agent schedules | ✓ | — | V-1 Vault candidate |
| Agent anomaly review | — | ✓ | Tenant workflow — agents surface anomalies for tenant review |
| GL classification review queue (AI) | ✓ | (review actions) | V-1 Vault candidate; tenant confirms AI suggestions |
| Statement templates | ✓ | (customize) | V-1 Vault candidate (seeds); tenant can fork per-customer-type |
| Invoice settings (numbering, terms, approval) | (initial setup) | ✓ | Tenant workflow (daily use); platform admin seeds defaults |
| Invoice CRUD | — | ✓ | Tenant workflow; stays in `/financials` |
| Bill CRUD | — | ✓ | Tenant workflow |
| Journal entry CRUD | — | ✓ | Tenant workflow; except period transitions |
| Recurring JE templates | — | ✓ | Tenant workflow |
| Customer / vendor payment application | — | ✓ | Tenant workflow |
| Finance charge config + runs | — | ✓ | Tenant workflow |
| Reconciliation | — | ✓ | Tenant workflow |
| Statement runs | — | ✓ | Tenant workflow |
| Purchase orders | — | ✓ | Tenant workflow |
| Financial reports (13+ types) | — | ✓ | Tenant workflow |
| AR / AP aging | — | ✓ | Tenant workflow |
| Cross-tenant statements (received) | — | ✓ | Tenant workflow (cross-tenant receipt) |

**The platform-admin rows above are what V-1 Vault consolidates.** In practice: COA templates, tax config, periods, period locks, agent schedules, GL mapping review, statement templates, provider connection, accountant invitations. These live in Vault Hub under an "Accounting administration" section. Everything else stays in the `Financials` hub + vertical nav.

---

## 3B. Quoting deep dive

_Audit extension. Confirms the Quoting Hub is a pure tenant workflow surface; the platform-admin hooks are through the Documents template registry (`quote.standard`) rather than a dedicated quoting admin page._

### 3B.1 Summary

Quoting is a tenant-facing product-line sales flow across manufacturing / funeral home / cemetery verticals. Two distinct surfaces: the **Order Entry Station** (quick-quote slide-over for rapid quote/order creation from a template library) and the **Quoting Hub** (pipeline tracking, pipeline dashboard, quote management, conversion to sales orders). Both are **tenant workflow** — they stay in vertical nav under `/quoting/*` with permission `ar.view`.

The platform-admin surfaces for Quoting are minimal and mostly indirect:
- `quote.standard` template management lives in the D-9-registered Documents template registry (edited at `/admin/documents/templates`).
- Quick Quote template CRUD is tenant UI only, not platform admin.
- Quote pipeline stage config + expiry rules are **not yet exposed** as admin surfaces — they're hardcoded defaults in `quote_service.py` (e.g., 30-day expiry). **V-1 gap.**

Post-D-9 integration: every quote PDF creates a canonical `Document` row (document_type="quote", entity_type="quote", linked via `entity_id=quote.id`). Quote does **not** dual-write VaultItem — confirmed by grep of `quote_service.py`, `sales_service.py`, and the Quote model.

### 3B.2 Models

- **`Quote`** (`backend/app/models/quote.py:20`) — `company_id`-scoped. Fields: `number` (QTE-YYYY-####), `status` (draft | sent | accepted | rejected | expired | converted), `quote_date`, `expiry_date` (default 30 days), `subtotal`, `tax_amount`, `total`, `payment_terms`, `notes`, plus Order-Station fields: `product_line` (wastewater | redi_rock | rosetta | funeral_vaults), `template_id`, `cemetery_id`, `cemetery_name`, `permit_number`, `installation_address`, `contact_name`, `contact_phone`, `deceased_name`, `legacy_photo_pending`. Relationships: `customer` (optional), `company`, `cemetery`, `created_by` (User), `lines` (QuoteLine), `converted_to_order_id`. **Tenant workflow.**
- **`QuoteLine`** (`quote.py:131`) — `quote_id`-scoped. Fields: `description`, `quantity` (Numeric 12,4), `unit_price`, `line_total`, `sort_order`, `product_id` (optional), `is_auto_added`, `auto_add_reason`, `personalization_data` (JSONB). **Tenant workflow.**
- **`QuickQuoteTemplate`** (`backend/app/models/quick_quote_template.py:13`) — `tenant_id` nullable (`is_system_template` when NULL). Fields: `template_name`, `display_label`, `display_description`, `icon`, `product_line`, `sort_order`, `is_active`, `seasonal_only`, `line_items` (JSON), `variable_fields` (JSON), `slide_over_width`, `primary_action` (quote | order | split), `quote_template_key`. **Mixed: system templates are platform admin; tenant templates are tenant workflow.**
- **`SavedOrder`** (`backend/app/models/saved_order.py:18`) — `company_id`-scoped + `created_by_user_id` (nullable for company-scope templates). Fields: `name`, `workflow_id` (FK to Workflow), `trigger_keywords` (JSON), `product_type`, `entry_intent` (order | quote), `saved_fields` (JSONB), `scope` (user | company), `use_count`, `last_used_at`, `last_used_by_user_id`. **Tenant workflow** (named compose templates for NL overlay).

### 3B.3 Routes

**`backend/app/api/routes/sales.py`** — Quoting Hub tenant workflow:

- `GET /quotes` — list (paginated). Permission `ar.view`. **Tenant workflow.**
- `POST /quotes` — create quote. Permission `ar.create_quote`. **Tenant workflow.**
- `GET /quotes/summary` — pipeline summary (4 widgets). **Tenant workflow.**
- `GET /quotes/badge-count` — nav badge (sent awaiting response). **Tenant workflow.**
- `GET /quotes/{id}` — get quote. **Tenant workflow.**
- `PATCH /quotes/{id}` — update fields. **Tenant workflow.**
- `POST /quotes/{id}/convert` — convert to sales order. Permission `ar.create_order`. **Tenant workflow.**
- `POST /quotes/{id}/duplicate` — clone to draft. **Tenant workflow.**
- `PATCH /quotes/{id}/status` — quick status change (send / reject / expire). **Tenant workflow.**
- `GET /quotes/{id}/pdf` — download PDF (routes through D-9 Document path). Permission `ar.view_quote`. **Tenant workflow.**

**`backend/app/api/routes/order_station.py`** — Order Entry Station (quick quote):

- `GET /templates` — list QuickQuoteTemplates. **Tenant workflow** (templates can be system-scope though).
- `GET /quotes` — list pending quick quotes (14-day window). **Tenant workflow.**
- `POST /quotes` — create quick quote from slide-over. **Tenant workflow.**
- `GET /quotes/{id}`, `POST /quotes/{id}/convert`, `PATCH /quotes/{id}` — quote lifecycle from order-station context. **Tenant workflow.**

**No dedicated platform admin routes exist** for:
- Quote template management (uses `/documents-v2/admin/templates` with `template_key="quote.standard"`).
- Quick Quote template CRUD (tenant admin only, no platform route exists).
- Quote pipeline stage config (not yet exposed).
- Quote expiry rules (hardcoded in service).

### 3B.4 Services

**`backend/app/services/quote_service.py`** — quick-quote creation + D-9 Document integration:

- `create_quote(db, tenant_id, user_id, *, customer_name, product_line, line_items, ...)` — creates Quote + QuoteLines, auto-computes totals, applies tax via `tax_service.get_jurisdiction_for_order`, records cemetery usage, applies placer auto-add rules (funeral home preferences), generates `QTE-YYYY-####` number. **Tenant workflow.**
- `convert_quote_to_order(db, tenant_id, user_id, quote_id)` — creates SalesOrder + copies lines (preserves auto_add metadata), marks quote `status="converted"`, logs audit. **Tenant workflow.**
- `list_pending_quotes(db, tenant_id, *, days=14)` — returns draft/sent in window. **Tenant workflow.**
- `update_quote_status(db, tenant_id, user_id, quote_id, new_status)` — state transitions. **Tenant workflow.**
- **D-9 Document integration:**
  - `generate_quote_document(db, tenant_id, quote_id)` — calls `document_renderer.render(template_key="quote.standard", entity_type="quote", entity_id=quote_id)` → creates canonical Document row linked to Quote.
  - `generate_quote_pdf(db, tenant_id, quote_id)` — legacy bytes API; routes through `generate_quote_document()` then `document_renderer.download_bytes(doc)`. Existing caller at `/quotes/{id}/pdf` unchanged.
  - `_build_quote_render_context(db, tenant_id, quote_id)` — prepares context dict.

**`backend/app/services/sales_service.py`** — Quoting Hub accounting-layer CRUD:

- `create_quote`, `get_quote`, `update_quote`, `convert_quote_to_order`, `duplicate_quote`, `set_quote_status` — core operations. **Tenant workflow.**
- `get_quote_summary(db, company_id)` — Quoting Hub widget data (`pipeline_value`, `awaiting_response`, `expiring_soon`, `won_this_month`, `won_value_this_month`). **Tenant workflow.**
- `get_quote_badge_count(db, company_id)` — sent-awaiting-response count. **Tenant workflow.**

**`backend/app/services/saved_order_service.py`** — compose template matching:

- `find_match(db, *, company_id, user_id, input_text)` — fuzzy match SavedOrder by `trigger_keywords`; user scope beats company scope; longest keyword-first; ties broken by `use_count`.
- `record_use(db, *, saved_order, user_id)` — increment `use_count`, record `last_used_at/by`.
- `create_from_workflow_run(db, *, company_id, user_id, workflow_run_id, name, trigger_keywords, scope)` — extract compose fields from `WorkflowRun`, create SavedOrder.

**Related services:** `tax_service.get_jurisdiction_for_order`, `cemetery_service.record_funeral_home_cemetery_usage`, `funeral_home_preference_service.apply_placer_to_quote_lines`.

### 3B.5 Frontend pages

| Path | Component | Scope | Features |
|---|---|---|---|
| `/quoting` | `quoting-hub.tsx` | **Tenant workflow** | Hub dashboard — 4 stat cards, filterable quote table, quick actions (send, convert, duplicate), sort |
| `/quoting/:id` | `quote-detail.tsx` | **Tenant workflow** | Edit mode — customer, quote date, expiry, payment terms, line items, notes, status badge, action buttons |
| `/ar/quotes/new` | `quote-detail.tsx` (new form) | **Tenant workflow** | Form-only create (backup to command bar) |
| `/ar/quotes/:id` | `quote-detail.tsx` (detail) | **Tenant workflow** | View + edit existing quote |
| Order Entry Station slide-over | (embedded in Order Station) | **Tenant workflow** | Quick-quote creation from template library |

### 3B.6 Quoting Hub structure

The Quoting Hub is a **pure tenant workflow surface**. Static layout (not registry-driven):

- Header: "Quoting" title + "New Quote" button (permission `ar.create_quote`).
- 4 stat cards (grid layout, not widgets in the OperationsBoardRegistry sense):
  1. **Pipeline Value** (DollarSign, blue) — sum of draft + sent quote totals.
  2. **Awaiting Response** (Clock, amber) — count of sent quotes not yet accepted/converted.
  3. **Expiring Soon** (AlertTriangle, rose) — count of sent quotes with expiry within 7 days.
  4. **Won This Month** (Trophy, emerald) — converted this month count + total value.
- Quote table: columns = Quote #, Customer, Date, Expiry, Status badge, Total $, Actions.
- Filters: search, status dropdown, sort dropdown.
- Row actions: conditional on status + permission (Send / Convert to order / Duplicate).

**No admin widget configuration.** The hub is static — V-1 could migrate it to `OperationsBoardRegistry` pattern to enable extension-contributed widgets, but that's polish, not requirement.

Data source: `/sales/quotes/summary` endpoint → `sales_service.get_quote_summary()`.

### 3B.7 Nav integration

```typescript
// frontend/src/services/navigation-service.ts:128-135 (Manufacturing preset)
{
  label: "Quoting",
  href: "/quoting",
  icon: "FileText",
  isHub: true,
  isDividerBefore: true,
  permission: "ar.view",
  requiresModule: "sales",
}
```

Hub-marked, tenant-facing. No cross-vertical variant today, but funeral homes / cemeteries could add Quoting to their nav if the `sales` module is enabled.

### 3B.8 Integration surfaces

**Documents / template registry (D-9):**

- `quote.standard` registered by seed migration `r28_d9_quote_wilbert_templates` (via `_template_seeds._d9_seeds()`).
- Production wiring: `/quotes/{id}/pdf` → `quote_service.generate_quote_pdf()` → `generate_quote_document()` → `document_renderer.render(template_key="quote.standard", ...)`. Creates canonical Document per quote.
- **Tenant customization path:** tenants fork-to-tenant via `/admin/documents/templates` (Documents admin page). Forked templates override for the tenant; platform template stays for all other tenants.
- **Missing discoverability:** no "Customize quote template" link in the Quoting Hub. Tenants have to know to go to Documents admin. V-1 gap.

**VaultItem dual-write:** **Confirmed NONE.** Quote model has no VaultItem relationship; `quote_service.py` contains zero `create_vault_item` calls; D-9 Document path creates Document rows, not VaultItem. Conversion to SalesOrder also doesn't write VaultItem.

**Intelligence:** compose-overlay voice parsing calls `intelligence_service.execute(prompt_key="orderstation.parse_voice_order")` for order entry, not quote-specific. `SavedOrder` matching is pure SQL + Python fuzzy match (no AI). **No Intelligence integration for quote generation today.**

**SalesOrder conversion:** `quote_service.convert_quote_to_order()` creates SalesOrder with `quote_id` FK back to Quote, copies lines (preserving auto_add metadata), marks Quote as converted. **No VaultItem event created.**

**DeliveryService:** **Not integrated.** The "Send" status transition on a quote doesn't email the PDF automatically. Future V-1 work: wire "Send to customer" button through `DeliveryService.send(...)` with the quote PDF as attachment.

### 3B.9 Platform admin vs tenant workflow table

| Surface | Platform admin | Tenant workflow | Notes |
|---|---|---|---|
| Quoting Hub dashboard | — | ✓ | Stays in vertical nav |
| Quote CRUD | — | ✓ | Stays in vertical nav |
| Quote → Order conversion | — | ✓ | Stays in vertical nav |
| Quote PDF generation (D-9 path) | — | ✓ | Tenant action |
| `quote.standard` template | ✓ | (customize via fork) | Platform admin; edited via `/admin/documents/templates` — V-1 Vault candidate |
| Quick Quote templates | — | ✓ | Tenant admin only (UI-managed) — no platform admin surface exists |
| Quote pipeline stage config | (Gap) | — | Not exposed today — V-1 gap |
| Quote expiry default (hardcoded 30 days) | (Gap) | — | Hardcoded in `quote_service.py` — V-1 gap |
| SavedOrder compose templates | — | ✓ | User / company scope, tenant workflow |
| Quote delivery / email | — | (Future) | Not automated today — V-1 should wire through DeliveryService |

**Critical gaps for V-1 migration:**

1. **Platform admin quote template surface.** No dedicated UI. Either add "Customize quote template" from the Quoting Hub → deep-link to Documents admin with template_key filter, or build a dedicated page.
2. **Quote expiry default configuration.** Hardcoded 30 days; should be tenant-configurable.
3. **Quote pipeline stage definitions.** Status enum is hardcoded (draft | sent | accepted | rejected | expired | converted) with no admin-overridable config.
4. **Quick Quote template admin.** No platform admin surface; tenants manage templates via UI.
5. **Quote delivery automation.** "Send quote" doesn't email PDF today.
6. **Quoting Hub widget registration.** Static page; should migrate to OperationsBoardRegistry pattern so extensions can contribute widgets.

These are V-2 or later — V-1 scope should focus on consolidating what already exists, not building new quoting admin surfaces.

---

## 4. Notifications / reminders surface

**Short answer:** notifications infrastructure exists. It was a pleasant surprise — not a gap.

### 4.1 Models

**`Notification`** (`backend/app/models/notification.py:10-44`)
- Fields: `id`, `company_id`, `user_id`, `title`, `message`, `type` (`info|success|warning|error`), `category`, `link`, `is_read`, `actor_id`, `created_at`.
- Tenant-scoped (`company_id`), per-user (`user_id`).
- Indexes on `(company_id, user_id, is_read)` and `(user_id, created_at)` — both supporting the "unread count" + "recent N" queries.
- **Already entity-agnostic** — no document/order/case FK; uses `category` string + `link` URL for routing.

**`SafetyAlert`** (`backend/app/models/safety_alert.py:12-38`)
- Compliance-specific alert surface separate from the Notification table.
- Fields: `alert_type`, `severity`, `reference_id`, `reference_type`, `message`, `due_date`, `acknowledged_by/at`, `resolved_at`.
- **Not unified with Notifications today.** A V-1 question is whether to fold SafetyAlert into Notification as a `category="safety_alert"` instance, or keep it separate.

**`UserAction`** (`backend/app/models/user_action.py:12-25`) — unrelated: command-bar action history.

### 4.2 Services

- **`NotificationService`** (`backend/app/services/notification_service.py`)
  - `create_notification(db, company_id, user_id, title, message, type, category, link, actor_id)` — creates a row atomically in the caller's transaction (no commit).
  - `get_notifications(db, user_id, include_read, page, per_page)` — returns `{items, total, page, per_page, unread_count}`.
  - `get_unread_count(db, user_id)` — used by the sidebar badge polling.
- **`BriefingService`** (`backend/app/services/briefing_service.py`) — role-aware morning briefings via Claude Haiku. Cached per-day in `EmployeeBriefing`. Separate surface from notifications. Areas: `funeral_scheduling`, `precast_scheduling`, `invoicing_ar`, `safety_compliance`, `full_admin`.
- **`DeliveryNotificationService`** — referenced elsewhere, likely for delivery-specific event notifications.

### 4.3 UI surfaces

| Surface | File | Summary |
|---|---|---|
| **Full Notifications page** | `frontend/src/pages/notifications.tsx` (296 lines) | `/notifications` — paginated list, All / Unread filter tabs, mark-as-read per-item, mark-all-as-read, type badges (info/success/warning/error). |
| **Sidebar notification dropdown** | `frontend/src/components/layout/notification-dropdown.tsx` (260 lines) | Popover in app header. Bell icon + unread badge. Shows latest 10. 60-second polling. "View all" → `/notifications`. |
| **Morning briefing (mobile)** | `frontend/src/components/morning-briefing-mobile.tsx` | Swipeable carousel of briefing items + announcements. Mark done / snooze. |
| **Morning briefing (desktop widget)** | `frontend/src/components/widgets/ops-board/BriefingSummaryWidget.tsx` | Renders narrative + action-item count on Operations Board. |
| **Accounting reminder banner** | `frontend/src/components/accounting-reminder-banner.tsx` | Session-dismissible banner above main content when accounting setup is pending. Hardcoded rule, not a general Notification. |

### 4.4 API routes

`backend/app/api/routes/notifications.py` — 4 endpoints:

- `GET /notifications` — paginated list.
- `GET /notifications/unread-count` — badge count.
- `PATCH /notifications/{id}/read` — mark one read.
- `PATCH /notifications/read-all` — bulk mark.

### 4.5 Gap assessment

**What exists:**
- A complete in-app notifications inbox (page + sidebar dropdown + unread count).
- Morning briefings (narrative format, role-aware).
- A separate SafetyAlert surface (compliance deadlines).
- An accounting-reminder banner (one hardcoded rule).

**What's missing for V-1:**

1. **Unified action inbox** — if a user wants to see "everything that needs my attention today," they today check 3 surfaces (notifications, morning briefing, SafetyAlert via safety hub). A Vault overview widget should consolidate.
2. **Notification-triggering across new item_types.** Only a handful of flows call `create_notification()`. Vault events (shares granted, deliveries failed, signatures pending) should be notification-worthy — most aren't wired.
3. **Email notification channel.** Notification is in-app only today. Critical notifications should also deliver via DeliveryService (email channel). The infrastructure exists; the wiring doesn't.
4. **Dismiss / snooze.** Only mark-read exists.
5. **Notification preferences.** No per-user "subscribe to delivery failures" toggle.
6. **SafetyAlert unification.** Compliance alerts live in a parallel table; a user has to know to check the safety hub separately.

The good news: the Notification model is already entity-agnostic, so extending it to cover all Vault events is a wiring exercise, not a schema change.

---

## 5. Widget infrastructure

Widget infrastructure is the most pleasant surprise of the audit. The framework is mature, generic, and reusable. V-1 Vault's overview dashboard can ride on it directly with minimal new work.

### 5.1 Framework

**Types** (`frontend/src/components/widgets/types.ts:3-39`)

```ts
WidgetDefinition {
  widget_id, title, description, icon, category,
  default_size, min_size, max_size, supported_sizes[],
  default_enabled, default_position,
  required_extension?, required_permission?,
  is_available, unavailable_reason
}

WidgetLayoutItem {
  widget_id, enabled, position, size, config
  // enriched with definition metadata on read
}

WidgetLayout {
  page_context, widgets[]
  // persisted per user × per page_context
}
```

**Core components:**

- `WidgetGrid.tsx` — drag-drop reorderable grid (dnd-kit), 4-column, span-based sizing.
- `WidgetWrapper.tsx` — standard chrome: header with grip / refresh / size menu / remove button.
- `WidgetSkeleton.tsx`, `WidgetErrorBoundary.tsx`, `WidgetPicker.tsx`.

**State management:** `useDashboard.ts` hook (160 lines) — loads layout + available widgets for a `page_context`, provides mutations (`addWidget`, `removeWidget`, `reorderWidgets`, `resizeWidget`, `resetLayout`), 500ms debounced save to `/widgets/layout` endpoint.

**Customization scope:** per-user, per-page. Two users on the same tenant see independent layouts on the same hub.

### 5.2 Registry pattern

`OperationsBoardRegistry` (`frontend/src/services/operations-board-registry.ts`, 148 lines) — singleton. Contributors register on app init; extensions contribute extra widgets/buttons/panels; deduplication with extension override.

```ts
registerContributor({
  contributor_key,
  requires_extension?,
  buttons?, overview_panels?, eod_sections?,
  production_log_columns?, settings_items?,
})
```

Methods: `getActiveContributors`, `getButtons`, `getOverviewPanels`, `getEODSections`, `getProductionLogColumns`, `getAllSettingsItems`.

`FinancialsBoardRegistry` — similar pattern but simpler (hardcoded zones: briefing / ar / ap / cashflow / reconciliation / agent_activity; toggleable visibility per zone).

### 5.3 Existing hubs

| Hub | URL | Vertical | Widget approach | Registry | Customization |
|---|---|---|---|---|---|
| **Operations Board** | `/console/operations`, `/operations` | Manufacturing | `WidgetGrid` + 17 widgets | `OperationsBoardRegistry` | Full (add/remove/reorder/resize) |
| **Financials Board** | `/financials-board` | AR/AP | Zone-based, not widget-based | `FinancialsBoardRegistry` | Zone visibility toggles |
| **Funeral Home Dashboard** | `/funeral-home/dashboard` | FH | Static cards, no widgets | None | None |
| **Manufacturing Dashboard** | `/dashboard` (mfg preset) | Manufacturing | Static cards | None | None |
| **QC Dashboard** | `/qc/qc-dashboard` | QC | Static | None | None |
| **Safety Dashboard** | `/safety/safety-dashboard` | Safety | Static | None | None |
| **Admin Dashboard** | `/admin/admin-dashboard` | Tenant admin | Static | None | None |
| **Quoting Hub** | `/quoting/quoting-hub` | Sales | TBD | TBD | TBD |

### 5.4 Widget inventory (Operations Board)

17 widgets under `frontend/src/components/widgets/ops-board/`:

- **Operations:** `TodaysServicesWidget`, `OpenOrdersWidget`, `LegacyQueueWidget`, `InventoryWidget`, `DriverStatusWidget`, `ProductionStatusWidget`
- **Briefing:** `BriefingSummaryWidget`, `ActivityFeedWidget`
- **Financials/Risk:** `AtRiskAccountsWidget`
- **Safety/Compliance:** `QCStatusWidget`, `SafetyWidget`, `ComplianceUpcomingWidget`, `TeamCertificationsWidget`, `MyCertificationsWidget`
- **Personal:** `TimeClockWidget`, `MyTrainingWidget`, `KbRecentWidget`

See [Appendix C](#appendix-c--widget-components-inventory) for a full breakdown.

### 5.5 Reuse assessment for V-1 Vault

**High-reuse (V-1 can consume directly):**

- `WidgetGrid` + `WidgetWrapper` + `useDashboard` — the whole framework is generic. Just instantiate with `page_context="vault_overview"`.
- The `OperationsBoardRegistry` pattern — V-1 Vault should introduce a `VaultHubRegistry` with the same shape.
- `ActivityFeedWidget` — generic enough to reuse for Vault recent-activity.
- `WidgetPicker` flow — add/remove widget UX is already built.

**Medium-reuse (generalize the pattern, not the widget):**

- `BriefingSummaryWidget` — tightly coupled to morning-briefing data, but the "summary + action-item count + link" pattern generalizes.
- `ComplianceUpcomingWidget` — generalizes to "upcoming calendar events" if Vault surfaces events.
- `AtRiskAccountsWidget` — generalizes to "attention-needed items" for Vault.

**No reuse (widget-specific data model):**

- `DriverStatusWidget`, `ProductionStatusWidget`, `TodaysServicesWidget`, `TimeClockWidget` — domain-specific.
- `KbRecentWidget`, `MyCertificationsWidget` — user/knowledge-specific, but Vault might want its own "recent Vault items I touched" flavor.

**What V-1 Vault needs to build fresh:**

- `RecentDocumentsWidget` (Document Log preview).
- `PendingSignaturesWidget` (envelope counts by status).
- `UnreadInboxWidget` (cross-tenant shares awaiting review).
- `RecentDeliveriesWidget` (DeliveryLog preview with failure highlight).
- `CrmRecentActivityWidget` (ActivityLog tail, all companies).

All five are thin API wrappers — the backend data already exists (see §8).

---

## 6. Cross-cutting capabilities

Four capabilities built during the Documents arc. Each asked: how document-coupled is it, and how hard would it be to generalize to other Vault item_types?

### 6.1 Sharing

**Model:** `document_shares.document_id` is **NOT NULL** FK (`document_share.py:48-52`).

```python
# backend/app/models/document_share.py:46-52
class DocumentShare(Base):
    __tablename__ = "document_shares"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,   # ← hard coupling
    )
```

No polymorphic escape hatch. Every share row hangs off one canonical Document.

**Service:** `document_sharing_service.grant_share()` (function signature lives at `backend/app/services/documents/document_sharing_service.py`) takes a `Document` object, validates `document.company_id`, uses `document.id` as the immutable key. List/query operations filter by `document_id`. The `Document.visible_to()` class method (D-6) encodes the "owned + shared" visibility logic as a SQL expression — that logic is Document-coupled too.

**Generalization cost: HIGH.** To share contacts or events would require either:

1. A new `entity_type` column on DocumentShare + a polymorphic lookup at grant/revoke time (join vs. direct FK), rewriting 19+ allowlisted Document.visible_to() call sites;
2. A parallel sharing table per item_type (one of `contact_shares`, `event_shares`, etc.);
3. Making Vault items always-Documents (every shared contact IS a Document whose content is the contact JSON).

Option 3 is interesting architecturally but loses the benefit of focused models. Option 2 duplicates the audit / event / permission machinery. Option 1 is the right approach but intrusive. None fit in V-1.

**V-1 posture:** Keep document-scoped. Do NOT attempt to generalize in V-1. Plan a dedicated "Vault Sharing" phase in V-2+ once the data model for other Vault items stabilizes.

### 6.2 Delivery

**Model:** `document_deliveries.document_id` is **NULLABLE** (`document_delivery.py:63-66`). The table already supports sends without a document:

```python
# backend/app/models/document_delivery.py:63-67
document_id: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("documents.id", ondelete="SET NULL"),
    nullable=True,   # ← soft coupling
)
```

**Service:** `SendParams.document_id: str | None = None` (`delivery_service.py` SendParams dataclass):

```python
# backend/app/services/delivery/delivery_service.py (SendParams, simplified)
@dataclass
class SendParams:
    company_id: str                         # REQUIRED (D-9)
    channel: str                            # "email" | "sms" | ...
    recipient: RecipientInput               # REQUIRED
    # Content — one of:
    template_key: str | None = None
    template_context: dict | None = None
    body: str | None = None
    subject: str | None = None
    # Optional attachment
    document_id: str | None = None          # ← optional
    attachments: list[AttachmentInput] = field(default_factory=list)
    # Caller linkage (polymorphic already)
    caller_module: str | None = None
    caller_workflow_run_id: str | None = None
    caller_workflow_step_id: str | None = None
    caller_intelligence_execution_id: str | None = None
    caller_signature_envelope_id: str | None = None
```

`send()` resolves the document if present, continues gracefully if absent. Attachments only auto-attach if `document is not None`. Content resolution works purely from `template_key` or `body`. The already-polymorphic caller_* column pattern is exactly the extension point V-1 needs.

**Channel abstraction:** `DeliveryChannel` is a `@runtime_checkable` Protocol (`backend/app/services/delivery/channels/base.py`):

```python
@runtime_checkable
class DeliveryChannel(Protocol):
    channel_type: str   # "email" | "sms" | future
    provider: str       # "resend" | "stub_sms" | ...

    def send(self, request: ChannelSendRequest) -> ChannelSendResult: ...
    def supports_attachments(self) -> bool: ...
    def supports_html_body(self) -> bool: ...
```

Zero Document coupling in the channel layer — the ChannelSendRequest carries recipient + rendered body + realized attachments as bytes. Channels never touch the Document model.

**Generalization cost: LOW.** A notification service could call `DeliveryService.send(SendParams(..., document_id=None, caller_module="notification_service"))` today. The only change needed for V-1 Vault is adding `caller_vault_item_id: str | None` to SendParams + the `document_deliveries` table, plus whatever FK column maps to it.

**V-1 posture:** Lift to "Vault Delivery." The table rename is cosmetic and optional; what matters is:

1. Add `caller_vault_item_id` column to `document_deliveries` (migration).
2. Add it to SendParams.
3. DeliveryLog UI filters by caller_vault_item_id alongside existing caller_* filters.
4. Zero changes to channel implementations.

This is a small migration + service tweak; V-1 can do it cheaply.

### 6.3 Signing

**Model:** `signature_envelopes.document_id` is **NOT NULL** (`signature.py:80`):

```python
# backend/app/models/signature.py:80-84, 109
class SignatureEnvelope(Base):
    __tablename__ = "signature_envelopes"
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,   # ← hard coupling
    )
    # ... envelope fields (subject, routing, expiry) ...
    certificate_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,    # the signed certificate is also a Document
    )
```

The envelope AND its completion certificate are both anchored to canonical Documents.

**Service:** `signature_service.create_envelope()` takes `document_id` required, fetches the Document for SHA-256 hash computation (tamper-detection), passes `document.company_id` for tenant scope. `send_envelope()` and `complete_envelope()` assume document immutability. The PyMuPDF overlay engine (`backend/app/services/signing/_overlay_engine.py`) reads PDF bytes from the Document's R2 `storage_key` to place signatures on anchor-matched positions.

**Abstraction seam:** None. Signing is fundamentally about a document artifact + parties + fields — the Document coupling is structural, not incidental. Every signed thing produces a new DocumentVersion with signatures overlaid; that pipeline assumes "there is a PDF to sign".

**Generalization cost: HIGH.** To sign a non-Document would require either:

1. A parallel SignatureEnvelopeItem with polymorphic item references + abstracted hash computation + abstracted storage fetch (new R2 path conventions per item type).
2. Forcing every signable artifact through the Document model first. This is arguably correct — things you sign should be canonical, versioned, hashed Documents.

Option 2 aligns with the "Document as canonical artifact" architecture. It doesn't require generalizing signing — it requires that future signable things (contracts, authorizations, etc.) get Document'd first. That's probably the right answer.

**V-1 posture:** Keep document-scoped. This is the right architectural answer — if you want to sign it, give it a Document first. No V-1 work needed on signing itself.

### 6.4 Notifications

**Already entity-agnostic.** `Notification` has no document/order/case FK:

```python
# backend/app/models/notification.py:10-44 (simplified)
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str]
    message: Mapped[str]
    type: Mapped[str]        # info | success | warning | error
    category: Mapped[str | None]     # ← free-form source tag
    link: Mapped[str | None]         # ← routing URL
    is_read: Mapped[bool] = mapped_column(default=False)
    actor_id: Mapped[str | None]     # who / what triggered it
    created_at: Mapped[datetime]
```

Uses `category: str` + `link: str` for routing. A delivery failure becomes `category="delivery_failed", link="/vault/deliveries/{id}"` — no schema change needed. Every notification source picks its own category string; the inbox and dropdown just render them.

**Generalization cost: MINIMAL.** Just call `notification_service.create_notification(db, company_id=..., user_id=..., category=..., link=...)` with whatever category and link make sense.

**V-1 posture:** Use as-is. The only schema change V-1 might want: add `item_type: str | None` + `item_id: str | None` columns for stricter audit trails and to enable "all notifications for this Vault item" queries. But this is additive and can be done later without data migration.

### 6.5 Synthesis

| Capability | Document-coupled today? | Polymorphic escape? | Cost to generalize | V-1 posture |
|---|---|---|---|---|
| Sharing | Yes (NOT NULL FK) | No | **HIGH** | Keep document-scoped |
| Delivery | Soft (NULL FK allowed) | Implicit (SendParams accepts None) | **LOW** | Lift to generic |
| Signing | Yes (NOT NULL FK) | No | **HIGH** | Keep document-scoped (correct by design) |
| Notifications | No (entity-agnostic) | Yes | **MINIMAL** | Use as-is |

**Recommendation:** V-1 should assume Delivery is already Vault-generic (because it is), keep Sharing + Signing as document-scoped capabilities, and extend Notifications by wiring more sources through `notification_service.create_notification()`.

---

## 7. Vertical vs. platform distinctions

_§7-§9 are synthesis — my judgment based on §1-§6._

The stated philosophy: Vault consolidates cross-cutting platform infrastructure. Vertical-specific pages stay in vertical nav. The trick is that several surfaces are both — the same concept has a platform representation AND a vertical-specific workflow.

### 7.1 Clear-cut categorizations

**Pure platform infrastructure** (lift under Vault):

- Documents (templates, doc log, inbox, detail) — already `Settings → Platform`.
- Delivery Log + Delivery Detail.
- Signing (envelopes, detail, create).
- Notifications (inbox + dropdown).
- Intelligence admin (prompts, versions, experiments, executions).
- Knowledge Base (cross-cutting knowledge, already vertical-agnostic in implementation).
- Training (cross-cutting — applies to every vertical).

**Pure vertical workflow** (stays in vertical nav):

- Manufacturing: Order Station, Operations Board, Scheduling Board, Production Hub, Resale, Urn Catalog, Legacy Studio, Disinterments.
- Funeral Home: Active Cases, New Case, Obituaries, FTC Compliance, Price List.
- Cemetery: Interments, Plot Map, Deeds.
- Crematory: Cases, Schedule, Chain of Custody.

These are business-specific; no Vault view makes sense.

**Pure platform admin** (stays in Settings):

- Company Profile, Branding, Email settings.
- Users & Roles, Permissions, Team Dashboard, Employees.
- Extensions, Onboarding, Billing, Locations.
- Accounting connection, API Keys.

### 7.2 The boundary cases — per-item_type recommendations

For each VaultItem item_type, a concrete recommendation on where it lives:

| item_type | Recommendation | Rationale |
|---|---|---|
| **document** | **Vault** (primary) | Already there. Documents surface is platform infrastructure. |
| **event** | **Both** | Vault calendar view for cross-vertical scanning; event-creation stays in the vertical that owns the source (deliveries, pour events, training). |
| **communication** | **Vault** | If/when implemented, cross-cutting (email/SMS/call logs against any entity). |
| **reminder** | **Vault** | Cross-cutting by nature. |
| **order** | **Stays vertical** | Orders are fundamentally vertical (vault/urn/funeral-service). No Vault "orders" view. However, _recent orders_ might appear in a CRM company detail (already does). |
| **quote** | **Stays vertical** | Same reasoning. D-9 made quotes first-class Documents, so they show up in Document Log naturally. |
| **case** | **Stays vertical** (FH, Crematory) | Case is the FH vertical's central primitive. No Vault case-list makes sense. Disinterment cases similar. |
| **contact** | **Vault** | CRM is platform infrastructure (cross-vertical — funeral homes AND manufacturers need CRM). Contacts + companies move under Vault. |
| **asset** | **Both** — defer | Currently unimplemented; when built, likely Vault view with vertical-specific detail pages. |
| **compliance_item** | **Vault** | Compliance is fundamentally cross-vertical. Already shares a unified surface via `event_type="compliance_expiry"`. |
| **production_record** | **Stays vertical (manufacturing)** | Production is manufacturing-specific. |

### 7.3 The Orders question specifically

`order` is a VaultItem item_type, and one could imagine a Vault "recent orders" view. But practically: every order has vertical context (a funeral service order is shaped very differently from a vault order), and admins looking for an order know which vertical they're in. The existing Order Station / Sales Orders page per vertical serves this well. The `order` item_type is likely vestigial — a CRM company detail already shows related orders via `GET /company-entities/{id}/invoices`, which is the right Vault-adjacent surface.

**Recommendation:** Don't build a Vault "all orders" view in V-1. Revisit if a cross-vertical need emerges (unlikely).

### 7.4 CRM specifically — Vault absorption posture

**Option A — Lift-and-shift:** Move `/crm/*` to `/vault/crm/*`. Add CRM tab to the Vault Hub. Keep all 9 pages + 47 endpoints + 4 models as-is. Pros: low risk, no data migration, users get a reorganized nav with same functionality. Cons: parallel contact models (Customer/Vendor/FHCase) stay unreconciled; AI classification review remains a separate UI surface.

**Option B — True absorption:** CompanyEntity becomes a first-class VaultItem (`item_type="account"`). Contact becomes `item_type="contact"` with active dual-write. Parallel contact models unified. Health scoring + classification become Vault-wide capabilities. Pros: clean architecture, no duplicate contact records. Cons: ~6-8 weeks of data migration + service rewrite, high risk of regression, parallel contact tables have divergent schemas (CustomerContact has `is_primary`, FHCaseContact has `portal_invite_sent_at`) that need reconciliation.

**Recommendation for V-1:** Option A. Defer Option B to V-2+ once the Vault Hub is stable and the CRM consolidation has a proven UX pattern.

### 7.5 Accounting specifically — Vault absorption posture

Accounting is the largest subsystem audited (28+ models, 15+ route files, 20+ services, 12 agents). The consolidation posture is **partial absorption — platform admin surfaces move to Vault; tenant workflow stays in `Financials` hub**.

**What moves to Vault Hub (platform admin):**

- Chart of accounts templates + standard GL category definitions.
- Provider connection config (QBO / Sage / native) — `AccountingConnection` management, accountant invitations.
- Tax rates + jurisdictions (`TaxRate`, `TaxJurisdiction`).
- Accounting periods + period locks (platform-admin enforced; gate every tenant write).
- Agent schedules (`AgentSchedule` — which agents run when).
- Statement template seeds (`StatementTemplate` with `tenant_id=NULL`).
- GL classification review queue (`TenantAccountingAnalysis`) — AI suggestions awaiting confirmation.

**What stays in `Financials` hub (tenant workflow):**

- Invoice CRUD, bill CRUD, payment recording / application.
- Journal entry CRUD + recurring JE templates.
- Reconciliation (bank / credit-card accounts, CSV upload, transaction matching).
- Finance charge runs.
- Statement runs (`StatementRun`, `CustomerStatement`).
- Purchase orders + three-way match.
- AR / AP aging reports, 13+ financial reports.
- Agent manual triggering + anomaly review (tenant acts on agent output).
- Cross-tenant received statements (funeral home receiving from manufacturer).

**Recommendation for V-1:** Add an "Accounting administration" section to Vault Hub containing the 7 platform-admin surfaces above. Leave `Financials` hub + vertical accounting pages unchanged. Rename `Settings → Integrations → Accounting` to `Vault → Accounting → Provider Connection` to match the new home.

One nuance: **period locks** are platform-admin (who locks) but tenant-workflow (who triggers them — the month-end-close agent). V-1 shouldn't split these — keep the period-lock admin UI and the month-end-close agent results together in Vault, since the admin needs both to approve a close.

### 7.6 Quoting specifically — Vault absorption posture

Quoting is smaller and cleaner than CRM or Accounting. The consolidation posture is **stays in vertical, with one admin surface pulled up**.

**What stays in vertical (Quoting Hub + vertical nav):**

- Everything the Quoting Hub does today — pipeline dashboard, quote CRUD, quote → SalesOrder conversion, quote PDF download, status transitions, Quick Quote templates.
- Order Entry Station quick-quote slide-over.
- SavedOrder compose templates.

**What moves to Vault Hub (platform admin):**

- `quote.standard` template management — already lives at `/admin/documents/templates` (post-D-9). V-1 just needs a "Customize quote template" deep-link from the Quoting Hub to surface this.
- Future: Quick Quote template platform admin (currently tenant-UI only; not a V-1 blocker).
- Future: Quote pipeline stage definitions + expiry rules (currently hardcoded; not a V-1 blocker).

**Recommendation for V-1:** No Quoting-specific Vault Hub section in V-1. The `quote.standard` template is already served by the Documents admin surface. Add a "Customize quote template" shortcut from Quoting Hub → `/vault/documents/templates?template_key=quote.standard` — one line of UX, zero backend work. Defer quote pipeline stage admin + expiry rules to V-2+.

### 7.7 Updated per-subsystem table

Putting the four subsystems side-by-side:

| Subsystem | Platform admin surfaces | Tenant workflow surfaces | V-1 posture |
|---|---|---|---|
| Documents | templates, doc log, inbox, deliveries, signing | (mostly N/A — Documents IS platform infra) | Move all under Vault Hub |
| CRM | classification rules (implicit), extension-gated visibility | 9 pages + 47 endpoints | Lift-and-shift to `/vault/crm/*` |
| Accounting | COA templates, tax config, periods / locks, agent schedules, provider connection, GL classification queue, statement templates | Invoices, bills, JEs, payments, reconciliation, finance charges, statement runs, POs, reports, agent triggers | Split — admin to Vault, workflow stays in `Financials` |
| Quoting | `quote.standard` template (via Documents) | Quoting Hub + Order Entry Station + quote CRUD + conversion | Stays in vertical; add deep-link to Documents template admin |

---

## 8. Overview dashboard data sources

V-1 will have a Vault Hub overview dashboard with widgets. For each candidate widget, this section asks: does the backend data source already exist?

| Widget | Data source | Existing endpoint? | Notes |
|---|---|---|---|
| **Recent Documents** | `Document` table | ✅ `GET /documents-v2/log` (D-2) | Returns last 7 days of Documents with template/status/entity. Just slice top-N. |
| **Pending Signatures** | `SignatureEnvelope` | ✅ `GET /admin/signing/envelopes?status=out_for_signature` (D-4) | Already filter-aware. |
| **Unread Inbox Items** | `DocumentShare` + `DocumentShareRead` | ✅ `GET /documents-v2/inbox` (D-6 + D-8 unread tracking) | Response includes `is_read` per current user. |
| **Recent Deliveries** | `DocumentDelivery` | ✅ `GET /documents-v2/deliveries` (D-7) | Default 7-day window; can filter on failures. |
| **CRM Recent Activity** | `ActivityLog` across all companies | ❌ **missing** | Existing endpoint is per-company (`GET /company-entities/{id}/activity`). Needs a tenant-wide tail endpoint. **Flag for V-1.** |
| **Upcoming Calendar Events** | `VaultItem` where `item_type="event"` and `event_start` future | ✅ `GET /vault/upcoming-events` (Vault Phase 1) | Already tenant-scoped with role-filtering. Can restrict to N days. |
| **Reminders Due** | `VaultItem` where `item_type="reminder"` | ⚠️ endpoint exists but no data | `reminder` item_type has no writer today. V-1 must decide: wire some, or hide the widget. |
| **Notifications** | `Notification` | ✅ `GET /notifications?include_read=false` | Already used by sidebar dropdown. Just embed. |
| **Attention-Needed / At-Risk** | mixed | ⚠️ multiple sources | At-risk CRM health, failed deliveries, pending approvals — needs a new aggregation endpoint or just renders 3 sub-lists. |
| **Briefing Summary** | `EmployeeBriefing` | ✅ `GET /briefings/today` (existing morning-briefing) | Already a widget on Operations Board. Reuse directly. |
| **Template Changes** | `DocumentTemplateAuditLog` | ✅ `GET /documents-v2/admin/templates/{id}/audit` | Per-template; tenant-wide tail endpoint is possible but not critical for V-1. |
| **Recent CRM Contacts** | `Contact` | ⚠️ not a tail endpoint | New companies / contacts added recently — would need new endpoint. |

### Endpoints V-1 needs to build

- **CRM tenant-wide activity tail** — `GET /vault/activity?limit=50` — aggregates ActivityLog across all companies for the current user's tenant. Uses existing `ActivityLog` model; just removes the per-company filter.
- **Attention summary** — `GET /vault/overview/attention` — rolls up at-risk accounts (from `health_score_service.get_health_summary`), failed deliveries (DeliveryLog status=failed in last 24h), pending envelope signatures (where current user is a signer and is_my_turn), critical safety alerts (SafetyAlert severity=critical, acknowledged=false). Mostly service composition — no new queries, just orchestration.
- **New contacts** — `GET /vault/recent-contacts?limit=10` — simple tail endpoint on Contact ordered by created_at. 5 lines.
- **Reminders (if we're wiring reminders)** — depends on which source service becomes the reminder writer. Open Question #7.

Everything else works with existing endpoints. V-1's overview dashboard is mostly composition, not new backend build.

### Sample widget → data contract

Illustrative for `PendingSignaturesWidget` to show the pattern V-1 follows:

```typescript
// frontend/src/components/widgets/vault/PendingSignaturesWidget.tsx
export function PendingSignaturesWidget() {
  const { data } = useQuery({
    queryKey: ['vault', 'signing', 'pending'],
    queryFn: () => signingService.listEnvelopes({
      status: 'out_for_signature',
      limit: 10,
    }),
  });
  return (
    <WidgetWrapper title="Pending signatures" icon="FileCheck">
      {data?.length === 0 ? (
        <EmptyState message="No envelopes awaiting signature." />
      ) : (
        <EnvelopeList envelopes={data} />
      )}
    </WidgetWrapper>
  );
}
```

Every other Vault widget follows this shape: `useQuery` → existing endpoint → render list in a WidgetWrapper. Low per-widget LOC; the surface is made of many small wrappers.

---

## 9. Synthesis + V-1 scope sketch + open questions

### 9.1 Current state assessment

**How much is already built toward Vault:**

- Canonical document fabric (D-1 → D-9): ✅ mature.
- VaultItem polymorphic model: ✅ schema there, 5/11 item_types actively used.
- Notification model + inbox: ✅ already entity-agnostic.
- Widget framework + registry pattern: ✅ mature, reusable.
- Sharing + Delivery + Signing services: ✅ mature; Delivery already generalized, Sharing + Signing hard-coupled (by design).
- CRM: ✅ mature + complete architectural island.
- Admin pages for Documents / Delivery / Signing / Inbox: ✅ exist at `/admin/documents/*` (5 entries).

**What's scattered across nav that should consolidate:**

- `Settings → Platform` subgroup (5 Documents entries).
- `CRM` hub.
- `Intelligence` and `Experiments` admin entries (currently in `Settings → Platform`).
- `Notifications` (currently FH-only nav; should be every vertical).
- `Knowledge Base` and `Training` (in `Resources` section).

**User experience today (click distance to common tasks):**

- Recent documents → `Settings → Platform → Document Log` (3 clicks).
- Pending signatures → `Settings → Platform → Signing` → filter (4 clicks).
- Failed deliveries → `Settings → Platform → Delivery Log` → filter (4 clicks).
- Unread inbox items → `Settings → Platform → Inbox` (3 clicks) — but nothing surfaces the unread count outside the page.
- CRM recent activity → `CRM` → click a company → activity tab (3-4 clicks).
- Cross-tenant attention summary ("what needs my attention across tenants") — **doesn't exist**.

**Overlap between surfaces:**

- A signed document lives in: DocumentLog, Signing Envelope detail, potentially a CRM company's activity feed (via `related_legacy_proof_id` tag). Three views of one artifact.
- A failed delivery lives in: DeliveryLog, the source Document's detail (via caller linkage), potentially the source Intelligence execution.
- A compliance expiry lives in: safety hub, Vault calendar (via `event_type="compliance_expiry"`), SafetyAlert (separate table), morning briefing narrative.

### 9.2 Consolidation recommendation

**Nav entries that consolidate under `/vault`:**

| Current path | Proposed path |
|---|---|
| `/admin/documents/templates` | `/vault/templates` |
| `/admin/documents/documents` | `/vault/documents` |
| `/admin/documents/inbox` | `/vault/inbox` |
| `/admin/documents/deliveries` | `/vault/deliveries` |
| `/admin/documents/signing/envelopes` | `/vault/signing` |
| `/notifications` | `/vault/notifications` |
| `/crm/*` | `/vault/crm/*` (lift-and-shift per §7.4) |
| `/admin/intelligence/*` | `/vault/intelligence/*` |

All of the above become tabs / sections under a single Vault Hub sidebar. The top-level `Vault` nav entry replaces `Settings → Platform` + `CRM` + `Notifications`.

**Nav entries that stay separate:**

- **Vertical workflows** (Order Station, Active Cases, Production Hub, etc.) — stay in their vertical preset nav.
- **Settings proper** (Company Profile, Branding, Users & Roles, Extensions, Billing, etc.) — stay in `Settings`. The _Platform_ subgroup in Settings dissolves; its entries move to Vault.
- **Knowledge Base + Training** — judgment call. Arguable they're Vault-adjacent but currently live under `Resources` (separate from Settings/Platform). Defer the decision to the user — this is Open Question #3.
- **Admin sidebar** (super-admin / platform admin) — unchanged; stays separate.

**Proposed Vault Hub structure:**

```
/vault/
├── /vault                    — Overview (landing page, widget dashboard)
├── /vault/documents          — Document Log + detail
├── /vault/templates          — Template library + editor
├── /vault/inbox              — Incoming shares (D-6 inbox)
├── /vault/deliveries         — Delivery Log + detail
├── /vault/signing            — Envelope library + create wizard + detail
├── /vault/notifications      — Notifications inbox
├── /vault/crm/               — CRM (companies, contacts, pipeline, etc.)
│   ├── /vault/crm/companies
│   ├── /vault/crm/companies/:id
│   ├── /vault/crm/pipeline
│   ├── /vault/crm/funeral-homes
│   ├── /vault/crm/contractors
│   ├── /vault/crm/duplicates
│   └── /vault/crm/billing-groups
├── /vault/intelligence       — AI admin (prompts, executions, experiments)
└── /vault/calendar           — NEW — cross-cutting event calendar (reads VaultItem item_type="event")
```

The landing page `/vault` is a widget dashboard (see §8 for widget sources). Default layout: 3 columns × 2-3 rows with the most-used widgets (recent docs, pending signatures, unread inbox, notifications, CRM attention, upcoming events). Customizable per-user via the existing `useDashboard` hook with `page_context="vault_overview"`.

### 9.3 V-1 scope sketch

This is a _sketch_, not a plan. V-1 itself will be scoped separately. Estimates are rough and assume a single implementer with access to existing frameworks.

**Phase V-1a — Vault Hub frame + nav restructure (~1-2 weeks)**

Frontend work:

- Create `/vault/*` route prefix in `App.tsx`.
- Create `VaultHub.tsx` layout with secondary sidebar (replaces the mini-nav-inside-Settings pattern). Tabs/sections:
  - Overview (landing page with widgets)
  - Documents (Templates, Doc Log, Inbox, Deliveries, Signing — 5 sub-tabs)
  - CRM (7 sub-tabs — see Phase V-1c)
  - Notifications
  - Intelligence (optional — see Open Question #10)
  - Calendar (optional — Phase V-1e)
- Move existing admin pages to new paths:
  - `/admin/documents/templates` → `/vault/documents/templates`
  - `/admin/documents/documents` → `/vault/documents`
  - `/admin/documents/inbox` → `/vault/documents/inbox`
  - `/admin/documents/deliveries` → `/vault/documents/deliveries`
  - `/admin/documents/signing/envelopes` → `/vault/documents/signing`
  - Signer portal at `/sign/:token` stays as-is (public route, not admin).
- Add redirects from old paths (301 or client-side navigate).
- Update `navigation-service.ts` — add `Vault` top-level entry with `isHub: true`, remove `Settings → Platform` subgroup (or reduce it to Billing / Extensions / Onboarding only).

Backend work (minimal):

- No route moves — backend routes stay at `/api/v1/documents-v2/*` etc. Frontend-only URL change.
- Optional: introduce `/api/v1/vault/*` router as an alias / dispatch for eventual consolidation. Not required for V-1.

**Phase V-1b — Vault overview dashboard (~1 week)**

Frontend:

- Create `frontend/src/services/vault-hub-registry.ts` mirroring `operations-board-registry.ts` structure.
- Register core contributors (documents, CRM, notifications).
- Create `VaultOverview.tsx` using `WidgetGrid` + `useDashboard(page_context="vault_overview")`.
- Build 5 Vault-specific widgets under `frontend/src/components/widgets/vault/`:
  - `RecentDocumentsWidget` — calls `GET /documents-v2/log?limit=10`.
  - `PendingSignaturesWidget` — calls `GET /admin/signing/envelopes?status=out_for_signature&limit=10`.
  - `UnreadInboxWidget` — calls `GET /documents-v2/inbox?limit=10` (leverages D-8 unread count).
  - `RecentDeliveriesWidget` — calls `GET /documents-v2/deliveries?limit=10` with a status=failed filter toggle.
  - `NotificationsWidget` — calls `GET /notifications?limit=10` (reuses dropdown data).
- Default layout: 3 columns × 2 rows showing the five widgets above + an empty slot for user customization.

Backend:

- No new endpoints required for V-1b — all widgets read existing endpoints.

**Phase V-1c — CRM absorption (lift-and-shift) (~1 week)**

Frontend:

- Move `/crm/*` to `/vault/crm/*`. 9 pages × 2 (desktop + mobile) = move path constants in one file.
- Update all `<Link to="/crm/...">` references (grep + replace — should be ~30-50 refs).
- Update `navigation-service.ts` CRM entries (mfg nav:151-156, fh nav:513).

Backend additions:

- **NEW endpoint:** `GET /api/v1/vault/activity/recent?limit=50` — tenant-wide ActivityLog tail aggregated across all companies. Needed for the `CrmRecentActivityWidget`.
- **NEW endpoint (optional):** `GET /api/v1/vault/recent-contacts?limit=10` — recently-created contacts across all companies.

Widgets added to Vault overview:

- `CrmRecentActivityWidget` — uses new activity tail endpoint.
- `AtRiskAccountsWidget` — reuses existing Operations Board implementation; just add to Vault overview layout.

**Phase V-1d — Notifications enrichment (~0.5-1 week)**

Frontend:

- Migrate `/notifications` route to `/vault/notifications` (page component stays the same file, just re-routed).

Backend:

- Decide SafetyAlert handling (Open Question #2):
  - If merge: write a one-off migration inserting a Notification row per SafetyAlert, keep SafetyAlert table for schema-compat but stop writing to it.
  - If keep separate: add a `GET /api/v1/vault/attention` aggregation endpoint that reads both tables.
- Wire 3-5 additional notification sources via `notification_service.create_notification()`:
  - Document share granted → notify target tenant admins.
  - Delivery failed → notify original caller.
  - Signature envelope awaiting current user → notify.
  - Compliance expiry within N days → notify safety-role admins.
  - At-risk account transition → notify assigned sales.

**Phase V-1e — Vault calendar (~1 week) [optional for V-1]**

- New page `/vault/calendar` reading `GET /api/v1/vault/items?item_type=event&event_start_from=...&event_start_to=...` (endpoint exists from VaultItem Phase 1-2).
- Month / week / day views (FullCalendar or similar).
- Filters by event_type, event_type_sub, source vertical.
- Defer to V-2 if V-1 scope is tight; I lean _defer_.

**Phase V-1f — Accounting admin consolidation (~1.5-2 weeks) [added by extension audit]**

Platform-admin accounting surfaces move to Vault Hub. Tenant `Financials` stays in vertical nav.

Frontend:

- New Vault Hub section: `/vault/accounting/*`. Sub-tabs:
  - Provider Connection (migrate from `/admin/accounting` + `/settings/integrations/accounting`)
  - Periods + Locks (surface `AccountingPeriod` + period-lock tools)
  - Agent Schedules (surface `AgentSchedule` admin)
  - GL Classification Queue (surface `TenantAccountingAnalysis` review)
  - Tax Config (surface `TaxRate` + `TaxJurisdiction` CRUD)
  - Statement Templates (surface `StatementTemplate` with tenant_id=NULL — platform-seeded)
  - COA Templates (surface 100+ platform GL category definitions)
- Update nav — move `Settings → Integrations → Accounting` reference to `Vault → Accounting → Provider Connection` deep-link.

Backend:

- No new endpoints required — all admin endpoints exist today under `/api/v1/accounting/*`, `/api/v1/agents/*`, `/api/v1/tax/*`, `/api/v1/journal-entries/periods/*`.
- Optional: introduce `/api/v1/vault/accounting/*` router as unified admin namespace. Non-blocking.

Widgets added to Vault overview:

- `PendingPeriodCloseWidget` — shows months ready to close, flagged by month-end-close agent.
- `GlClassificationReviewWidget` — shows `TenantAccountingAnalysis.status="pending"` count + link.
- `AgentRecentActivityWidget` — shows last N agent jobs with status badges (reuses existing AgentDashboard data).

Estimate: 1.5-2 weeks. Scope risk: period-lock admin UX needs care (destructive, cross-tenant implications). De-risk with a confirmation step + audit trail on every lock/unlock.

**Phase V-1g — Quoting shortcut (~0.25 week) [added by extension audit]**

No Quoting admin section in Vault Hub — Quoting Hub stays in vertical nav. Just:

- Add "Customize quote template" link in Quoting Hub that deep-links to `/vault/documents/templates?template_key=quote.standard` (or the pre-Vault path `/admin/documents/templates`).
- 1 UX tweak, zero backend work.

**Phase V-1h — Documentation (~0.5 week)**

- Update CLAUDE.md with V-1 "Recent Changes" entry + Vault architecture section.
- Vault README: `backend/docs/vault_README.md` (mirrors `documents_README.md`).
- User guides:
  - `how_to_use_vault_overview.md` — tenant admin guide.
  - `vault_hub_architecture.md` — internal developer docs (registry pattern, widget composition, adding a new Vault view).
  - `accounting_admin_in_vault.md` — platform admin guide for new accounting admin surfaces.

**Total V-1 estimate: 6-8 weeks** including the audit-extension phases (previously 4-6 weeks for the narrower scope). Ranges:

- Base V-1 (V-1a through V-1d + V-1h): 4-5 weeks.
- With Accounting admin (V-1f): +1.5-2 weeks.
- With Quoting shortcut (V-1g): +0.25 week.
- With Calendar (V-1e, optional): +1 week.
- CRM Option B instead of A (Open Question #1): +3-5 weeks.

Risk items:

- CRM Option A vs B decision (Open Question #1) dominates the timeline.
- Accounting period-lock admin UX is the highest-risk new UI in V-1 — destructive, hard to undo.
- Notifications schema merge (Open Question #2) touches 2 tables + 5-10 callers.
- Widget framework is mature, so V-1b is actually the lowest-risk phase despite being new UI.

### 9.4 Open questions for human decision

Before V-1 is scope-locked, these need answers:

1. **CRM absorption depth.** Option A (lift-and-shift, ~1 week) vs Option B (true absorption with parallel-contact-model reconciliation, ~6-8 weeks). I recommend A for V-1; asking for confirmation.

2. **Notifications unification with SafetyAlert.** Currently parallel. Merge into one Notification.category="safety_alert" row, or keep separate? Merging makes the inbox complete; keeping separate preserves the specialized SafetyAlert fields (severity, due_date, acknowledged_by). Probably merge, keeping those fields on Notification or a joined row.

3. **Knowledge Base + Training.** Stay under `Resources` (current), move to Vault (as informational repositories), or split (KB to Vault, Training stays as its own thing since it has per-user assignments)? My lean: stay under Resources for V-1, revisit in a later phase.

4. **Orders / Quotes / Cases — confirm vertical-only.** §7.2 recommends these stay vertical. Confirm this is the right call, or do we want a minimal Vault view ("recent orders across all verticals")? I think not, but worth explicit.

5. **Vault overview: all-tenant data or user-filtered?** When an admin opens Vault, do they see all company data (admin view) or only items they authored / are assigned to? Documents inbox per-user read state suggests per-user; CRM suggests all-tenant. My recommendation: widgets default to tenant-scoped with a "My items" filter toggle per widget.

6. **Calendar: V-1 or V-2?** Phase V-1e is optional. Building it in V-1 makes the hub feel more complete; deferring means a tighter V-1. My lean: defer.

7. **Reminders: wire or hide?** The `reminder` item_type has no writer. V-1 options: (a) wire some sources (signature envelope expiry, delivery retry due, compliance expiry); (b) hide the reminders widget until V-2. Lean: (a), wire ~3 sources in V-1d, deliver real value.

8. **URL migration breakage.** With no production users, we can do clean breaks. Old `/admin/documents/*` URLs either 404 or 301 to `/vault/*`. Probably 301-then-deprecate: redirect for one release, remove in the next.

9. **Delivery generalization: rename to VaultItemDelivery now or defer?** The infrastructure is ready (§6.2). Should V-1 do the rename + caller_item_* column addition, or stay `DocumentDelivery` in name? Lean: stay as `DocumentDelivery` in name for V-1 (minimize churn), add `caller_vault_item_id` column, revisit naming in V-2.

10. **Intelligence admin: under Vault or stand-alone?** Intelligence is cross-cutting (AI admin is platform infrastructure), but it's also a distinct enough domain that "AI management" could be its own top-level nav. I lean toward "under Vault" for V-1 (fewer top-level entries), but either is defensible.

_Questions 11-17 added by the Accounting / Quoting extension audit._

11. **Which accounting admin surfaces belong in Vault Hub vs. stay in Settings?** §7.5 recommends 7 surfaces move (provider connection, periods, period locks, agent schedules, GL classification queue, tax config, statement templates, COA templates). Confirm this list. Specifically: accountant invitations — currently under `/admin/accounting` — should they live in Vault's Provider Connection tab or stay in Settings? I lean Vault (they're platform-admin actions on tenant accounting config). Same question for the QBO/Sage OAuth flow itself — if we keep legacy provider connection alive, is that a Vault responsibility?

12. **Period-lock UI: fully admin-controlled, or expose tenant-triggered requests?** The month-end-close agent produces candidate closes; a platform admin locks. Should tenants see a "request period close" button that the admin reviews in Vault, or is that too much coordination? I lean: tenants see agent progress + anomalies via the existing AgentDashboard; admin sees the "ready to lock" queue in Vault. Don't add a tenant-triggered request flow.

13. **GL classification review queue: AI-only workflow, or extend to manual mapping?** `TenantAccountingAnalysis` today surfaces AI-suggested mappings. Should V-1 also expose manual "change this mapping" from the review queue, or keep that in the dedicated TenantGLMapping UI? I lean: review queue is AI-confidence-driven; manual changes stay in the mapping UI. Don't combine.

14. **Is the Quoting Hub tenant workflow (stays in vertical nav) or platform admin (moves to Vault)?** §7.6 recommends **stays in vertical** — the hub is a tenant surface (pipeline dashboard, CRUD, conversion). Confirm this. Specifically: the platform admin hook (`quote.standard` template) is served by `/admin/documents/templates` (D-9) — no dedicated quoting admin page needed. This keeps V-1 scope tight.

15. **Does Quote need VaultItem dual-write in V-1, or is Document dual-write (via `quote.standard` template) sufficient?** Confirmed in audit: Quote has no VaultItem dual-write. D-9 gave quotes first-class Document status. VaultItem dual-write would enable a cross-subsystem "recent quotes" view alongside orders / invoices / deliveries, but there's no user requirement driving it today. I lean: skip VaultItem dual-write for V-1; revisit if a unified "recent sales activity" view becomes a requirement.

16. **If Accounting writes VaultItems (already confirmed for posted invoices / bills / JEs / statements), does the Vault calendar surface journal entries too?** The calendar widget reads `VaultItem` where `item_type="event"`. Posted JEs write as `item_type="event"` with `event_type="journal_entry"`? Or do they write as `item_type="document"` instead? Audit is ambiguous here — worth verifying early in V-1b. If JEs show up on the calendar, that's a lot of rows; we may want to filter them out by default.

17. **Accounting agent anomaly review: Vault Hub or `Agents` hub?** The existing `Agents` hub in manufacturing nav is tenant workflow (tenants review anomalies, approve period closes). Agents are both tenant action surfaces AND platform admin (agent schedules, configuration). Split or combine? I lean: keep `Agents` hub where it is for tenant-workflow usage (manual triggering, anomaly review, approval flow) and add a separate "Agent Schedules" admin surface under Vault Hub for the platform-admin configuration slice. Two surfaces, one per audience.

### 9.5 Unexpected observations

Things that surprised me during the audit and should be called out before V-1 starts:

1. **Notifications are already entity-agnostic.** I expected this to be a gap. It's not. The model has `category: str` + `link: str` and no entity FKs — textbook generic inbox. The work is wiring more sources through `create_notification`, not building infrastructure.

2. **Widget framework is mature AND generic.** The `useDashboard` / `WidgetGrid` / `WidgetWrapper` stack takes a `page_context` string and persists layouts per-user. V-1 Vault overview isn't a framework build; it's 5 widgets in a registered page_context.

3. **The `Settings → Platform` subgroup is already the nascent Vault.** 5 Documents entries + Intelligence + Experiments all live there today. The V-1 job is promoting this to a top-level nav with better framing, not inventing from scratch.

4. **Quote became first-class Document in D-9, but doesn't write VaultItem.** The D-9 migration gave quotes canonical document status (via the `quote.standard` template + Document row per quote), but VaultItem dual-write wasn't added. Low-priority inconsistency; V-1 could wire it or leave it.

5. **Compliance uses `event` item_type, not `compliance_item`.** The `compliance_item` item_type is vestigial — the real compliance flow is `event` + `event_type="compliance_expiry"` + `event_type_sub=...`. Schema cleanup opportunity: deprecate `compliance_item` in V-2+.

6. **CRM has 600+ lines of AI classification logic.** That's a substantial service surface not obvious from the nav. Any Vault consolidation has to decide whether the classification review-queue stays a CRM-specific page or generalizes into "items needing review" (for other AI-classified entities in the future). V-1 should keep it CRM-scoped.

7. **FHCaseContact has portal-invitation fields that no other contact model has.** `portal_invite_sent_at`, `portal_last_login_at` — these imply a next-of-kin portal. If that portal exists or is planned, Vault consolidation needs to account for a "portal user contact" concept separate from internal CRM contacts. Worth asking the user about.

8. **The `VaultItem.event_type` enum has more values than documented.** The model comment lists 9 event_types; in practice the services write more (e.g. `route` is writeable but not in the comment). Someone touched the enum without updating the comment. Low-priority docs cleanup.

9. **Admin sidebar is a completely separate nav tree.** Platform admins (super-admins viewing `admin.*` subdomain) get `admin-sidebar.tsx` — 16 entries, none of them Vault-related. V-1 should leave this alone. The Vault Hub is for tenant admins, not platform admins.

10. **No existing widget surfaces a "recent cross-tenant activity" view.** The inbox page shows incoming shares, but there's no widget that mixes "share-received + share-granted + doc-I-authored-appeared-elsewhere". If V-1 wants a "recent cross-tenant activity" widget, it's a new endpoint query that unions 2-3 tables.

---

## Appendix A — Full nav catalog

_Complete `navigation-service.ts` inventory with Vault-adjacency classification. 79 entries total._

### Manufacturing (44 entries — `navigation-service.ts:90-456`)

Top-level / hub row:

| Label | Path | Icon | Gating | Category |
|---|---|---|---|---|
| Home | `/dashboard` | Home | — | vertical-workflow |
| Order Station | `/order-station` | Zap | `ar.view` + `sales` module | vertical-workflow |
| Operations Board | `/console/operations` | LayoutDashboard | `operations_board.view` + `production_log` area | vertical-workflow |
| Scheduling Board | `/scheduling` | Kanban | `scheduling_board.view` + `driver_delivery` module + `funeral_scheduling` area | vertical-workflow |
| Quoting | `/quoting` | FileText | `ar.view` + `sales` module | vault-adjacent (boundary) |
| Financials | `/financials` | BarChart3 | `invoicing_ar` area | vault-adjacent (boundary) |
| Agents | `/agents` | Bot | `invoicing_ar` area | vault-adjacent |
| CRM | `/crm` | Building2 | `customers.view` | vault-adjacent |
| Production | `/production-hub` | Factory | `production_log` area | vertical-workflow |
| Resale | `/resale` | Store | `urn_sales` extension | vertical-workflow |
| Compliance | `/compliance` | ShieldCheck | `safety.view` + `safety_management` module | vault-adjacent |

Resources section:

| Label | Path | Category |
|---|---|---|
| Knowledge Base | `/knowledge-base` | vault-adjacent (boundary) |
| Training | `/training` | vault-adjacent (boundary) |
| Legacy Studio (+ 4 children) | `/legacy/generator` | vault-adjacent |

Settings → Business:

| Label | Path | Category |
|---|---|---|
| Company Profile | `/admin/settings` | platform-admin |
| Branding | `/settings/branding` | platform-admin |

Settings → People:

| Label | Path | Category |
|---|---|---|
| Team Dashboard | `/team` | platform-admin |
| Employees | `/admin/users` | platform-admin |
| Users & Roles | `/admin/roles` | platform-admin |
| Permissions | `/admin/permissions` | platform-admin |

Settings → Communication:

| Label | Path | Category |
|---|---|---|
| Email | `/settings/email` | platform-admin |

Settings → Integrations:

| Label | Path | Category |
|---|---|---|
| Call Intelligence | `/settings/call-intelligence` | boundary-candidate |
| Accounting | `/settings/integrations/accounting` | platform-admin |
| API Keys | `/admin/accounting` | platform-admin |
| Disinterment | `/settings/disinterment` | boundary-candidate |
| Union Rotations | `/settings/union-rotations` | boundary-candidate |

Settings → Operations:

| Label | Path | Category |
|---|---|---|
| Programs & Products | `/settings/programs` | platform-admin |
| Compliance Config | `/settings/compliance` | platform-admin |
| Workflows | `/settings/workflows` | vault-adjacent (boundary) |

Settings → Network:

| Label | Path | Category |
|---|---|---|
| Locations | `/settings/locations` | platform-admin |

Settings → Platform (5 Vault-adjacent entries):

| Label | Path | Category |
|---|---|---|
| Billing | `/settings/billing` | platform-admin |
| Extensions | `/extensions` | platform-admin |
| Onboarding | `/onboarding` | platform-admin |
| Intelligence | `/admin/intelligence/prompts` | **vault-adjacent** |
| Experiments | `/admin/intelligence/experiments` | **vault-adjacent** |
| **Documents** | `/admin/documents/templates` | **vault-adjacent** |
| **Document Log** | `/admin/documents/documents` | **vault-adjacent** |
| **Inbox** | `/admin/documents/inbox` | **vault-adjacent** |
| **Delivery Log** | `/admin/documents/deliveries` | **vault-adjacent** |
| **Signing** | `/admin/documents/signing/envelopes` | **vault-adjacent** |

### Funeral Home (12 entries — `navigation-service.ts:484-572`)

| Label | Path | Category |
|---|---|---|
| Home | `/dashboard` | vertical-workflow |
| Active Cases | `/cases` | vertical-workflow |
| New Case | `/cases/new` | vertical-workflow |
| Obituaries | `/funeral-home/obituaries` | vertical-workflow |
| Financials | `/financials` | vault-adjacent (boundary) |
| CRM | `/crm` | vault-adjacent |
| FTC Compliance | `/funeral-home/compliance` | vertical-workflow |
| Directors & Staff | `/admin/users` | platform-admin |
| Company Profile | `/admin/settings` | platform-admin |
| Price List | `/funeral-home/price-list` | vertical-workflow |
| Integrations | `/admin/accounting` | platform-admin |
| Extensions | `/extensions` | platform-admin |
| **Notifications** | `/notifications` | **vault-adjacent** |

### Cemetery (7 entries — `navigation-service.ts:610-633`)

| Label | Path | Category |
|---|---|---|
| Home | `/dashboard` | vertical-workflow |
| Interments | `/interments` | vertical-workflow |
| Plot Map | `/plots` | vertical-workflow |
| Deeds | `/deeds` | vertical-workflow |
| Financials | `/financials` | vault-adjacent (boundary) |
| Company Profile | `/admin/settings` | platform-admin |
| Extensions | `/extensions` | platform-admin |

### Crematory (8 entries — `navigation-service.ts:668-701`)

| Label | Path | Category |
|---|---|---|
| Home | `/dashboard` | vertical-workflow |
| Cases | `/crematory/cases` | vertical-workflow |
| Schedule | `/crematory/schedule` | vertical-workflow |
| Chain of Custody | `/crematory/custody` | vault-adjacent (boundary) |
| Financials | `/financials` | vault-adjacent (boundary) |
| Company Profile | `/admin/settings` | platform-admin |
| Extensions | `/extensions` | platform-admin |

### Platform admin (16 entries — `admin-sidebar.tsx:52-94`)

All are super-admin only and remain in the dedicated admin sidebar (not the Vault hub):

| Group | Entries |
|---|---|
| Platform | Dashboard, Tenants, Network |
| Product | Extension Catalog, Demand Signals, Onboarding Templates, Training Content |
| Operations | White-Glove Imports, Check-in Calls, Support Notes |
| Platform Health | Platform Health, Integration Monitor, Sync Jobs, Error Log |
| Billing | Revenue Dashboard, Subscriptions |
| Settings | Platform Settings, Admin Users |

All 16 are **platform-admin** category; none become Vault tabs.

### Category totals

- **vault-adjacent:** 18
- **vault-adjacent (boundary):** 11
- **vertical-workflow:** 28
- **platform-admin:** 22

---

## Appendix B — CRM model summary table

| Model | File | Tenant | Primary link | VaultItem dual-write | FHCase link | SalesOrder link |
|---|---|---|---|---|---|---|
| Contact | `contact.py` | `company_id` | `master_company_id` → CompanyEntity | None | None | None |
| CrmOpportunity | `crm_opportunity.py` | `company_id` | `master_company_id` → CompanyEntity (optional) | None | None | None |
| ActivityLog | `activity_log.py` | `tenant_id` | `master_company_id` → CompanyEntity, `contact_id` → Contact | None | None | Tag only (`related_order_id` string) |
| CrmSettings | `crm_settings.py` | `company_id` (unique) | — | None | None | None |
| CompanyEntity | `company_entity.py` | `company_id` | `parent_company_id` (self-ref); linked FROM Customer / Vendor.master_company_id | None | None | Via `health_score_service` (read-only) |
| CustomerContact | `customer_contact.py` | `company_id` | `customer_id` → Customer | None | None | None |
| VendorContact | `vendor_contact.py` | `company_id` | `vendor_id` → Vendor | None | None | None |
| FHCaseContact | `fh_case_contact.py` | `company_id` | `case_id` → FHCase | None | Direct | None |

### Endpoint categories (47 total)

- Company CRUD: 4
- Contacts: 6
- Activity log: 5
- Health scoring: 3
- Opportunities: 4
- Classification (AI): 10
- Settings + visibility: 4
- Merge review + name cleanup: 3
- Related data (invoices / bills / legacy proofs / relationships): 4
- Funeral homes shortcut: 1
- Others: 3

---

## Appendix C — Widget components inventory

_All components under `frontend/src/components/widgets/`._

### Framework (reusable)

- `WidgetGrid.tsx` — drag-drop 4-column grid.
- `WidgetWrapper.tsx` — standard chrome.
- `WidgetSkeleton.tsx` — loading placeholder.
- `WidgetErrorBoundary.tsx` — error boundary.
- `WidgetPicker.tsx` — add/remove widget UX.
- `types.ts` — `WidgetDefinition`, `WidgetLayoutItem`, `WidgetLayout`.
- `useDashboard.ts` — state hook.

### Operations Board widgets (`ops-board/`, 17 total)

**Operations** (6): `TodaysServicesWidget`, `OpenOrdersWidget`, `LegacyQueueWidget`, `InventoryWidget`, `DriverStatusWidget`, `ProductionStatusWidget`.

**Briefing** (2): `BriefingSummaryWidget`, `ActivityFeedWidget`.

**Financials/Risk** (1): `AtRiskAccountsWidget`.

**Safety/Compliance** (5): `QCStatusWidget`, `SafetyWidget`, `ComplianceUpcomingWidget`, `TeamCertificationsWidget`, `MyCertificationsWidget`.

**Personal** (3): `TimeClockWidget`, `MyTrainingWidget`, `KbRecentWidget`.

### Registry files

- `frontend/src/services/operations-board-registry.ts` (148 lines) — contributor-based.
- `frontend/src/services/financials-board-registry.ts` (~150 lines) — zone-based.
- `frontend/src/services/board-contributors/index.ts` — registers core contributors on app init.

### Reuse assessment for V-1 Vault

**Consume directly:** `WidgetGrid`, `WidgetWrapper`, `WidgetPicker`, `useDashboard`, the registry pattern.

**Adapt:** `ActivityFeedWidget` (generic enough), `BriefingSummaryWidget` pattern (summary + count + link), `AtRiskAccountsWidget` pattern (attention item list).

**Build new for V-1:** `RecentDocumentsWidget`, `PendingSignaturesWidget`, `UnreadInboxWidget`, `RecentDeliveriesWidget`, `NotificationsWidget`, `CrmRecentActivityWidget`. All are thin API wrappers.

---

## Appendix D — Accounting subsystem catalog

_Added by extension audit._

### D.1 Model summary table

| Model | File | Tenant | Role | V-1 consolidation |
|---|---|---|---|---|
| AccountingConnection | `accounting_connection.py` | `company_id` | Platform admin (provider config) | Vault |
| JournalEntry | `journal_entry.py:14-42` | `tenant_id` | Tenant workflow | `Financials` |
| JournalEntryLine | `journal_entry.py:46-61` | `tenant_id` | Tenant workflow | `Financials` |
| JournalEntryTemplate | `journal_entry.py:64-84` | `tenant_id` | Tenant workflow (recurring) | `Financials` |
| AccountingPeriod | `journal_entry.py:87-98` | `tenant_id` | Platform admin (gate writes) | Vault |
| Invoice | `invoice.py:20+` | `company_id` | Tenant workflow | `Financials` |
| InvoiceLine | `invoice_line.py` | `company_id` | Tenant workflow | `Financials` |
| CustomerPayment | `customer_payment.py:17-75` | `company_id` | Tenant workflow | `Financials` |
| CustomerPaymentApplication | `customer_payment.py:77-85` | (implicit) | Tenant workflow | `Financials` |
| VendorBill | `vendor_bill.py:17-100` | `company_id` | Tenant workflow | `Financials` |
| VendorBillLine | `vendor_bill_line.py` | `company_id` | Tenant workflow | `Financials` |
| VendorPayment | `vendor_payment.py:17-80` | `company_id` | Tenant workflow | `Financials` |
| VendorPaymentApplication | `vendor_payment_application.py:16-37` | (implicit) | Tenant workflow | `Financials` |
| PurchaseOrder | `purchase_order.py:22+` | `company_id` | Tenant workflow | `Financials` |
| PurchaseOrderLine | `purchase_order_line.py` | `company_id` | Tenant workflow | `Financials` |
| TaxRate | `tax.py:14-27` | `tenant_id` | Platform admin | Vault |
| TaxJurisdiction | `tax.py:30-45` | `tenant_id` | Platform admin | Vault |
| FinanceChargeRun | `finance_charge.py:14-46` | `tenant_id` | Tenant workflow | `Financials` |
| FinanceChargeItem | `finance_charge.py:49-74` | `tenant_id` | Tenant workflow | `Financials` |
| StatementTemplate | `statement.py:14-31` | nullable | Platform admin (seed) + tenant customization | Vault (seeds) |
| StatementRun | `statement.py:34-68` | `tenant_id` | Tenant workflow | `Financials` |
| CustomerStatement | `statement.py:71+` | `tenant_id` | Tenant workflow | `Financials` |
| FinancialAccount | `financial_account.py:13-39` | `tenant_id` | Tenant workflow | `Financials` |
| ReconciliationRun | `financial_account.py:42-73` | `tenant_id` | Tenant workflow | `Financials` |
| ReconciliationTransaction | `financial_account.py:76-99` | `tenant_id` | Tenant workflow | `Financials` |
| ReceivedStatement | `received_statement.py:13-36` | `tenant_id` + `from_tenant_id` | Tenant workflow (cross-tenant) | `Financials` |
| StatementPayment | `received_statement.py:41-60` | `tenant_id` | Tenant workflow | `Financials` |
| TenantAccountingImportStaging | `accounting_analysis.py:13-24` | `tenant_id` | Platform admin | Vault |
| TenantAccountingAnalysis | `accounting_analysis.py:27-45` | `tenant_id` | Platform admin (AI review queue) | Vault |
| TenantGLMapping | `accounting_analysis.py:48-59` | `tenant_id` | Platform infra (cross-tenant reporting) | Vault |
| TenantAlert | `accounting_analysis.py:62-76` | `tenant_id` | Tenant workflow | `Financials` (agent anomaly) |
| AgentJob | `agent.py` | `tenant_id` | Tenant workflow (agent runs) | `Financials` / `Agents` hub |
| AgentAnomaly | `agent_anomaly.py` | `tenant_id` | Tenant workflow | `Agents` hub |
| AgentSchedule | `agent_schedule.py` | `tenant_id` | Platform admin (schedule config) | Vault |

### D.2 Route summary (platform-admin vs tenant-workflow counts)

| Route file | Platform admin | Tenant workflow |
|---|---|---|
| `accounting.py` | 3 | 1 |
| `accounting_connection.py` | ~5 (OAuth flows) | 0 |
| `journal_entries.py` | 2 (period open/close) | 7 (JE CRUD + templates) |
| `vendor_bills.py` | 0 | ~7 |
| `vendor_payments.py` | 0 | ~5 |
| `reconciliation.py` | 0 | ~7 |
| `tax.py` | 4 (rates + jurisdictions CRUD) | 2 (resolve) |
| `statements.py` | ~2 (templates) | ~5 (runs) |
| `finance_charges.py` | 0 | ~4 |
| `purchase_orders.py` | 0 | ~7 |
| `agents.py` | 2 (period lock/unlock) | ~6 |
| `financial_health.py` | 0 | ~5 |
| `financials_board.py` | 0 | ~3 |

Rough total: ~15 platform-admin endpoints vs. ~60 tenant-workflow endpoints. V-1 Vault consolidates the 15.

### D.3 Service summary

Platform admin services (move to Vault Hub consumption):

- `accounting_analysis_service.py` — AI GL classification, writes `TenantAccountingAnalysis` → `TenantGLMapping`.
- `period_lock_service.py` — gate writes to locked periods.
- Invoice / bill / statement template services (platform-scope seeds).

Tenant workflow services (stay in `Financials`):

- `financial_report_service.py` — 13 report types.
- `tax_service.py`, `invoice_settings_service.py`, `draft_invoice_service.py`, `fh_invoice_service.py`.
- `vendor_bill_service.py`, `vendor_payment_service.py`, `purchase_order_service.py`.
- `early_payment_discount_service.py`, `finance_charge_service.py`.
- `statement_generation_service.py`, `statement_pdf_service.py`, `cross_tenant_statement_service.py`, `statement_service.py`.
- `financial_health_service.py`, `report_intelligence_service.py`.

Plus 12 accounting agents (`backend/app/services/agents/*`) — tenant workflow with platform-admin schedule config.

### D.4 Vault integration coverage

- **VaultItem dual-write:** ✓ posted invoices, bills, JEs, statements.
- **DocumentRenderer (D-1/D-2):** ✓ invoice, statement, finance-charge PDFs.
- **DeliveryService (D-7):** ✓ invoice, statement, collections, accountant-invitation emails.
- **Intelligence service:** ✓ COA classification (Haiku), expense categorization (agent).
- **Cross-tenant sharing (D-6):** ✓ manufacturer → funeral home statements.

---

## Appendix E — Quoting subsystem catalog

_Added by extension audit._

### E.1 Model summary table

| Model | File | Tenant | Role | V-1 consolidation |
|---|---|---|---|---|
| Quote | `quote.py:20` | `company_id` | Tenant workflow | Vertical (Quoting Hub) |
| QuoteLine | `quote.py:131` | (via quote_id) | Tenant workflow | Vertical |
| QuickQuoteTemplate | `quick_quote_template.py:13` | `tenant_id` nullable | Mixed (system + tenant) | Vertical (tenant); potentially Vault for system templates |
| SavedOrder | `saved_order.py:18` | `company_id` + user | Tenant workflow (compose) | Vertical |

### E.2 Route summary

| Route file | Platform admin | Tenant workflow |
|---|---|---|
| `sales.py` (quote endpoints) | 0 | ~10 |
| `order_station.py` (quick-quote endpoints) | 0 | ~6 |

Zero platform admin routes specific to Quoting. The `quote.standard` template is served by the Documents admin routes (`/documents-v2/admin/templates/*`).

### E.3 Service summary

- `quote_service.py` — quote creation, conversion, D-9 Document integration.
- `sales_service.py` — Quoting Hub accounting layer (summary, badge count, CRUD).
- `saved_order_service.py` — compose template matching.
- Supporting: `tax_service`, `cemetery_service`, `funeral_home_preference_service`.

All tenant workflow.

### E.4 Vault integration coverage

- **VaultItem dual-write:** ✗ **No dual-write**. Quote does not write VaultItem rows.
- **DocumentRenderer (D-9):** ✓ `quote.standard` template creates canonical Document per quote.
- **DeliveryService:** ✗ Not integrated today (send-quote-email not automated).
- **Intelligence service:** ✗ No quote-specific prompts (SavedOrder matching is pure SQL).
- **Cross-tenant sharing:** ✗ Not applicable.
- **SalesOrder conversion:** ✓ quote_service.convert_quote_to_order() writes SalesOrder with `quote_id` FK back.

### E.5 V-1 consolidation summary

- Quoting Hub: **stays in vertical nav**.
- `quote.standard` template: **managed via Documents admin in Vault** (already post-D-9).
- Quick Quote templates, expiry rules, pipeline stage config: **gaps** — not exposed as admin today. Defer to V-2.
- Single V-1 UX tweak: add "Customize quote template" deep-link in Quoting Hub → `/vault/documents/templates?template_key=quote.standard`.

---

_End of audit. Next deliverable: V-1 scope document informed by §9 recommendations + decisions on the 17 open questions (10 original + 7 audit-extension)._
