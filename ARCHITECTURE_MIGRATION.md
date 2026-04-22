# ARCHITECTURE_MIGRATION.md

Canonical sequencing guide for the transition from the current (April 2026, post-aesthetics-arc) Bridgeable build to the **Monitor / Act / Decide** three-primitive architecture defined in [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md).

Companion docs: [CLAUDE.md](CLAUDE.md), [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md), [BRIDGEABLE_MASTER.md](BRIDGEABLE_MASTER.md), [FUNERAL_HOME_VERTICAL.md](FUNERAL_HOME_VERTICAL.md), [SPACES_ARCHITECTURE.md](SPACES_ARCHITECTURE.md), [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md), [FEATURE_SESSIONS.md](FEATURE_SESSIONS.md), [AESTHETIC_ARC.md](AESTHETIC_ARC.md).

**Status:** Approved. Target: September 2026 Wilbert demo.

**Key premise:** Aesthetic arc is done. Intelligence backbone is unified. No production users exist — build correct for everyone, no migration paths. Spaces taxonomy deferred to its own session (Phase 0 below). Minimum viable Spaces state for every user: Home + Settings.

---

## Part 1 — Current State Inventory

### 1.1 Pages (271 files across 40+ directories)

Grouped by functional role and classified for Part 2. Counts and paths from `frontend/src/pages/`.

#### Admin / super-admin surfaces (27 pages)
`admin/*` — accounting, admin-dashboard, admin-tenant-*, api-keys, audit-logs, billing, company-classification, company-migration-review, company-settings, data-quality, delivery-settings, driver-portal-preview, employee-profile, feature-flags, modules, network-*, org-hierarchy, platform-fees, role-management, scheduling-settings, super-dashboard, sync-*, training-content, user-management. Role: admin/super-admin. Entity: tenant config, users, networks, tenant-level settings.

#### Platform admin (10 pages)
`platform/*` — dashboard, extension-catalog, extension-demand, feature-flags, impersonation-log, login, platform-health, platform-users, system-health, tenants, tenant-detail, tenant-modules, tenant-onboarding. Role: platform admin (admin.getbridgeable.com). Survives as pages.

#### Onboarding (20 pages)
`onboarding/*` — accounting-review, accounting-setup, catalog-builder, cemetery-setup, charge-*, company-branding, data-migration, funeral-home-customers, historical-order-import, import-*, integration-setup, network-preferences, onboarding-*, product-library, quick-orders, safety-training-setup, scenario-player, scheduling-setup, tax-jurisdictions, team-*, unified-import, vault-*, website-suggestions-review. Role: admin during onboarding. Survives as pages — onboarding is linear + one-time.

#### Settings (25 pages)
`settings/*` — BriefingPreferences, ExternalAccounts, Locations, PortalBrandingSettings, PortalUsersSettings, ProductLines, SavedOrders, SpacesSettings, WorkflowBuilder, Workflows, ai-settings, call-intelligence-settings, cemeteries, cemetery-profile, compliance-config, customer-types, disinterment-settings, invoice-settings, programs-settings, seasonal-templates, tax-settings, union-rotations, vault-mold-settings, vault-supplier-settings. Role: admin. Survives — per PA, Settings is a Space whose contents ARE configuration pages.

#### Agent / briefing / triage / AI surfaces (7 pages)
`agents/AgentDashboard`, `agents/ApprovalReview`, `briefings/BriefingPage`, `triage/TriageIndex`, `triage/TriagePage`, `calls/call-log`, `tasks/*` (3 pages). Role: office/director/accountant. Intelligence-driven surfaces shipped during UI/UX arc — most BECOME Pulse components.

#### Hubs (6 pages)
`hubs/compliance-hub`, `hubs/crm-hub`, `hubs/financials-hub`, `hubs/production-hub`, `quoting/quoting-hub`, `resale/resale-hub`. Role: admin + specialized. All are composed dashboards — **all BECOME Pulse surfaces on their respective Spaces** (or Pulse components on Home for cross-cutting).

#### Dashboards (3 pages)
`dashboard/admin-dashboard`, `dashboard/employee-dashboard`, `team/team-dashboard`. All BECOME Pulse compositions (or absorbed into Home Space Pulse per role).

#### Operations / production surfaces (13 pages)
`operations/operations-board-desktop`, `console/operations-board`, `console/production-console`, `console/delivery-console`, `console/console-select`, `orders/order-station`, `production-entry`, `production-log/*` (3), `production/*` (4). Mixed: Operations Board → Pulse on Production Space. order-station → Focus (edit canvas). Console pages → role-based default Pulse for production/delivery staff.

#### Delivery & scheduling (8 pages)
`delivery/carriers`, `delivery/delivery-detail`, `delivery/dispatch`, `delivery/funeral-scheduling`, `delivery/history`, `delivery/operations`, `delivery/route-detail`, `delivery/scheduling-board`. Mixed: scheduling-board → Schedule Space Pulse. funeral-scheduling → **Funeral Scheduling Focus (demo hero)**. Detail pages survive.

#### CRM (12 pages)
`crm/*` — billing-group-*, companies*, company-detail*, contractors, crm-settings, duplicates, funeral-homes, new-contact, pipeline. Entity detail pages survive. List pages → Pulse components (saved views).

#### Financial / AR / AP (11 pages)
`ar/collections-review`, `ar/invoice-review-queue`, `ap-aging`, `ar-aging`, `billing/*` (3), `customer-payments`, `customers`, `customer-detail`, `invoices`, `invoice-detail`, `journal-entries`, `payment-detail`, `price-management*` (4), `quotes`, `quote-detail`. Mixed: Review queues → Focus (triage). Boards → Pulse. Detail pages survive.

#### Funeral home specific (7 pages)
`funeral-home/case-detail`, `case-list`, `dashboard`, `first-call`, `ftc-compliance`, `portal`, `price-list`. case-detail → Focus candidate (arrangement conference). dashboard → Home Space Pulse (FH director composition).

#### Safety / compliance (13 pages)
`safety/*` — safety-chemicals, safety-dashboard, safety-incidents, safety-inspect, safety-loto, safety-notices, safety-osha300*, safety-programs, safety-toolbox-talks, safety-training*, compliance/npca-audit-prep. Most → Pulse components + drill-down pages. `safety-programs` triage flow already exists as Focus-equivalent via Phase 8d.1.

#### Legacy / personalization (7 pages)
`legacy/*` — legacy-detail, legacy-proof-review, legacy-settings, library, proof-generator*, template-upload. `legacy-proof-review` → **Proof Review Focus (second demo Focus, cross-tenant)**.

#### Products & catalogs (7 pages)
`products`, `product-detail`, `inventory`, `inventory-detail`, `products/bundle-manager`, `products/urn-catalog`, `products/urn-import-wizard`, `urns/*` (5). Detail pages survive. Inventory page → Pulse with drill; rebalancing → Focus (matrix core).

#### Disinterment (2 pages) + intake
`disinterments/disinterment-list`, `disinterments/disinterment-detail`, `intake/disinterment-intake`. List page → Pulse saved view. Scheduling → **Disinterment Scheduling Focus**.

#### Driver / portal (5 + 6 pages)
`driver/*` (5), `portal/*` (6). Portal UX. Does NOT absorb into Focus/Pulse; portal stays portal per SPACES_ARCHITECTURE §10.

#### Vault (10 pages)
`vault/VaultHubLayout`, `VaultOverview`, `vault/accounting/*` (7). Admin surfaces. Accounting tabs → stay as pages (specialized admin forms). VaultOverview → absorbed into admin Home Pulse.

#### Miscellaneous (25+ pages)
Spring-burials, BOM, QC, projects, urns subrouting, knowledge-base, announcements, reports, locations, spaces, sign, notifications, saved-views (3 pages), tasks (3 pages), triage (2 pages), training. Case-by-case.

### 1.2 Hub structures (registries and composability patterns present)

| Registry | Location | Contributors | Extension-aware |
|---|---|---|---|
| OperationsBoardRegistry | `frontend/src/services/operations-board-registry.ts` + `board-contributors/index.ts` | core_incident, core_safety_observation, core_qc, core_product_entry, core_delivery, core_team_presence + extensions (wastewater, redi-rock, rosetta, npca_audit_prep, urn_sales) | Yes |
| FinancialsBoardRegistry | `frontend/src/services/financials-board-registry.ts` | Similar pattern — 5 zones (cash, AR, AP, GL, tax) | Yes |
| VaultHubRegistry | `frontend/src/services/vault-hub-registry.ts` (mirror of backend `app/services/vault/hub_registry.py`) | documents, crm, intelligence, notifications, accounting | Permission-gated |

These three registries are **the composability pattern Pulse inherits.** Same registry discipline, different composition target (board → Pulse surface).

### 1.3 Decision-heavy workflows (Focus candidates)

Each passes the bounded-decision test (PA §5.14: "What decision does this close out? When does the user exit?"):

| Workflow | Current location | Decision | Exit condition |
|---|---|---|---|
| Arrangement conference | `funeral-home/case-detail` + Scribe | Populate case file | Complete staircase step |
| Funeral scheduling | `delivery/funeral-scheduling` + `scheduling-board` | Assign services to days × drivers × vehicles | Week committed |
| Quote building | `quote-detail` (edit view) | Commit quote pricing + send | Quote sent / accepted / rejected |
| PO review | (scattered — no dedicated Focus surface) | Approve or reject each PO | Queue exhausted |
| Disinterment scheduling | `disinterments/disinterment-list` | Schedule specific case | Case committed to date |
| Proof review (manufacturer) | `legacy/legacy-proof-review` | Approve / revise | Decision recorded |
| Proof revision (manufacturer) | `legacy/proof-generator` | Submit new proof version | Version sent |
| Inventory rebalancing (cross-location) | `locations/LocationsOverview` + transfers | Move N items from A → B | Transfer committed |
| Personalization request processing | (manufacturer side of legacy) | Approve / revise batch | Batch cleared |
| Delivery coordination (cross-tenant) | (not yet built as decision surface) | Commit delivery to service date | Delivery confirmed |
| Order entry | `orders/order-station` | Commit order details + pricing | Order submitted |
| Compliance gap resolution | `hubs/compliance-hub` | Close each gap item | All critical items cleared |
| Production scheduling | `production/production-board` | Assign pours to molds/dates/crew | Schedule committed |

### 1.4 Navigation structure (current Spaces seeding)

From `backend/app/services/spaces/registry.py` — 13 combinations + 1 fallback + 1 system:

| Vertical | Role | Spaces (default first) |
|---|---|---|
| funeral_home | director | Arrangement · Administrative · Ownership |
| funeral_home | admin | Arrangement · Administrative |
| funeral_home | office | Administrative |
| funeral_home | accountant | Books · Reports |
| manufacturing | admin | Production · Sales · Ownership |
| manufacturing | office | Administrative · Operational |
| manufacturing | production | Production · Operations |
| manufacturing | accountant | Books · Reports · Compliance |
| manufacturing | safety_trainer | Compliance · Training |
| cemetery | admin | Operations · Administrative · Ownership |
| cemetery | office | Administrative · Operational |
| crematory | admin | Operations · Administrative |
| crematory | office | Operations · Administrative |
| (any) | (unmapped) | General (fallback) |
| (admin) | system | Settings |
| manufacturing | driver | MFG driver portal (portal_partner access_mode) |

**All these templates become targets for Pulse composition work** — each is a Space that needs a role-appropriate Pulse defined in Phase 0 (Spaces planning).

### 1.5 Cross-tenant relationships

- **Migration `fh_02_cross_tenant`** — platform_tenant_relationships table. Live.
- **FH ↔ Manufacturer** — `case_merchandise.vault_manufacturer_company_id` FK, `vault_order_id` → `sales_orders`. Order auto-flows. Live.
- **FH ↔ Cemetery** — `case_cemetery.cemetery_company_id` FK. Plot reservation schema defined, interactive plot map deferred.
- **FH ↔ Crematory** — `case_cremation.crematory_company_id` FK. Job flow schema defined, live.
- **Manufacturer ↔ FH personalization** — legacy (personalization compositor) + proof approval flows. Live for token-based FH approval; cross-tenant Space/Focus to wrap these is NEW architecture work.
- **Network inventory sharing** — discussed, not built.
- **Compliance benchmarking** — anonymized aggregates — discussed, not built.
- **Multi-party disinterments** — pain point documented, not wrapped in Focus.
- **Cross-tenant delivery coordination** — painful today via phone + Excel, not in platform.

**Takeaway:** Infrastructure exists; wrap-in-Focus work is Phase E.

### 1.6 Intelligence backbone (what's available to consume)

Unified via `app.services.intelligence.intelligence_service.execute(prompt_key, variables, company_id, caller_module, ...)`. 73+ active platform prompts. Every call audit-logged in `intelligence_executions` with typed caller linkage. Capabilities new architecture WILL consume:

- **Command bar parsing** — `command_bar.intent_classification`, entity-extract per type
- **NL creation extraction** — `nl_creation.extract.{case,event,contact,task,sales_order}`
- **Scribe** — arrangement conference transcript → case file fields
- **Triage AI questions** — per-queue `triage.{queue}_context_question` prompts
- **Briefings** — morning/evening narrative + structured sections
- **Anomaly surfacing** — per-agent anomaly classification
- **Vision** — check scanning, COA extraction, legacy vault print form
- **KB retrieval** — mid-call price lookup, contextual answers
- **Pattern detection (observe-and-offer)** — infrastructure for behavioral analytics exists; observe-and-offer consumer hook needs building

**Intelligence is ready.** New primitives (Focus pins, Monitor anomaly cards, interpretation chips, pause sensor adaptive learning) all consume the same backbone.

---

## Part 2 — Architecture Mapping

### 2.1 SURVIVES (as page)

These remain destinations. Most drilled into from Pulse or Focus.

| Category | Rationale |
|---|---|
| Settings (all 25 settings pages) | PA: Settings IS a Space whose "pins" are config pages |
| Admin / platform admin (37 pages) | Administrative surfaces, drill-down from admin Pulse |
| Onboarding (20 pages) | Linear flow, one-time per tenant |
| Entity detail pages — case-detail, company-detail, customer-detail, invoice-detail, order/quote-detail, product-detail, purchase-order-detail, payment-detail, inventory-detail, delivery-detail, route-detail, disinterment-detail, work-order-detail, bom-detail, qc-inspection-detail, legacy-detail, project-detail | Destinations from Monitor + Act |
| Knowledge Base, Training (training-hub, procedure-library, vault-order-lifecycle) | Reference destinations |
| Legacy Studio (legacy/library, settings, template-upload) | Specialized admin surface |
| Authentication (login, register, company-register, landing) | Bootstrap surfaces |
| Saved view surfaces (SavedViewsIndex, SavedViewCreatePage, SavedViewPage) | Power-user config |
| Portal pages (driver portal + signer portal) | Portal architecture is its own pattern |
| Reports, announcements, notifications, my-profile | Leaf destinations |
| Spring burials, BOM list, QC dashboard, projects | Specialized drill-downs; individual pages mostly reachable from Pulse widgets |

**Total survives-as-page: ~140 pages.**

### 2.2 BECOMES PULSE COMPONENT

Current dashboards, lists, and widget-style surfaces compose into the per-Space Pulse surface. Following PA §3.3–§3.4 (Personal / Operational / Anomaly / Activity layers).

| Current surface | Pulse layer | Space(s) it lands in |
|---|---|---|
| morning-briefing-card | Personal | Home (every Space) |
| BriefingPage | Activity / detail | Administrative, Arrangement, Books |
| AgentDashboard → anomaly tiles + status | Anomaly + Activity | Administrative, Books, Ownership |
| ApprovalReview | Personal (pending decisions) | Administrative, Books |
| Operations Board contributors (incident, safety, QC, product entry, delivery, team presence) | Operational | Production, Operations, MFG Administrative |
| Financials Board contributors (AR zone, AP zone, cash, GL, tax) | Operational + Anomaly | Administrative (MFG + FH), Books, Ownership |
| compliance-hub | Operational + Personal | Compliance (new Space for safety_trainer + mfg admin) |
| crm-hub | Operational | Home of every cross-cutting Space |
| financials-hub | Operational | Administrative, Books, Ownership |
| production-hub | Operational | Production |
| quoting-hub | Operational | Sales, Administrative |
| resale-hub | Operational | Resale (new Space) OR Sales (fold-in) |
| team-dashboard | Activity + Personal | Production (MFG), Home (owner) |
| manufacturing-dashboard | Composed Home | MFG admin Home |
| funeral-home/dashboard | Composed Home | FH director Home |
| LocationsOverview | Operational | Home of admin with multi-location |
| ar-aging, ap-aging | Operational (sub-layer of Financials) | Books |
| customers, customer-payments, invoices, products, inventory | Operational (saved-view-composable) | Various |
| ar/invoice-review-queue, ar/collections-review | **Borderline — review queues → Focus (triage); high-level counts → Pulse** | Books |
| disinterment-list | Operational saved view | Operations, Arrangement |
| safety-dashboard, safety-programs, safety-incidents, safety-osha300 | Operational + Anomaly | Compliance, Training |
| spring-burial-list | Operational saved view | Arrangement, Administrative (seasonal) |
| VaultOverview | Composed Home (admin) | Admin Home Pulse |
| TriageIndex | Personal (pending decisions) | Home (every Space), Compliance, Production |
| TasksList | Personal | Every Space (role-filtered) |
| tasks/TaskDetail | Survives as page (entity detail) | — |
| Announcements (widget) | Activity | Home |
| Alerts (unread widget) | Anomaly | Home |
| Reports (saved-view equivalent landing) | Pulse component (link-out) | Administrative, Books |
| SavedViews results | Component (rendered inline) | Any Space |

**Total becomes-Pulse-component: ~60 current surfaces reshape into ~30 Pulse components** (deduplication via saved views + widget consolidation).

### 2.3 BECOMES FOCUS

Each passes bounded-decision test. Ordered by September priority.

| # | Focus | Core mode | Space it launches from | Demo priority |
|---|---|---|---|---|
| 1 | **Funeral Scheduling Focus** | Kanban | Schedule (new) / Operations | **September HERO** |
| 2 | **Proof Review Focus** (FH side) | Single-record (proof image + approve/revise) | Arrangement, Legacy | **September (second demo)** |
| 3 | **Proof Revision Focus** (MFG side) | Edit canvas (compositor) | Sales, Production, Legacy | **September (cross-tenant pair)** |
| 4 | Arrangement Conference Focus | Single-record (case file + Scribe + live completion panel) | Arrangement | Post-September (FH vertical not live) |
| 5 | Disinterment Scheduling Focus | Kanban / calendar | Operations, Arrangement | Post-September |
| 6 | Quote Building Focus | Edit canvas | Sales, Administrative | Post-September (nice-to-have) |
| 7 | PO Review Focus | Triage queue | Books, Administrative | Post-September |
| 8 | Inventory Rebalancing Focus | Multi-location matrix | Operations | Post-September |
| 9 | Cross-tenant Delivery Coordination Focus | Calendar + shared canvas | Cross-tenant Space (Sunnycrest↔Hopkins) | **September (MOCKED preview only)** per PA §8.1 |
| 10 | Timing Conflict Focus | Calendar | Cross-tenant Space | Post-September |
| 11 | Personalization Request Processing | Triage queue | Production, Sales | Post-September |
| 12 | Order Entry Focus | Edit canvas | Sales, Administrative | Post-September |
| 13 | Compliance Gap Resolution Focus | Triage queue | Compliance | Post-September |
| 14 | Production Scheduling Focus | Kanban | Production | Post-September (production-board can survive as Pulse until rebuilt as Focus) |

**Bounded-decision audit — every entry passes.** E.g. #9 "Cross-tenant Delivery Coordination" closes out "what time does this delivery happen on this service date" — commits to delivery time = exits. Not a dashboard.

### 2.4 DEPRECATED

Deleted outright rather than migrated.

| Path | Rationale |
|---|---|
| `console/console-select` | Console pattern collapses — role defaults land users on role-appropriate Space Pulse directly |
| `dashboard/admin-dashboard` + `dashboard/employee-dashboard` | Replaced by per-Space Pulse composition; "admin dashboard" isn't a destination, it's whatever Space the admin lands in |
| `operations/operations-board-desktop` | Absorbs into Operations Space Pulse composition |
| `financials-board` | Absorbs into Administrative / Books Space Pulse |
| `hubs/*` (6 hub pages) | All become Pulse surfaces on their respective Spaces |
| `production/production-board` | Absorbs into Production Space Pulse + future Production Scheduling Focus |
| `production/ProductionBoardDashboard` | Same as above |
| `delivery/dispatch`, `delivery/operations` | Absorb into Operations Pulse; scheduling-board → Schedule Space |
| `team/team-dashboard` | Absorbs into Home Pulse for owner/director roles |
| `driver-portal-preview` | Preview/dev surface; retire once portal is production-verified |
| `compliance/npca-audit-prep` | Placeholder, extension-gated; rebuild as Compliance Pulse anomaly card + optional Focus when actually built |
| Aesthetic Arc Batches 1c-i, 1c-ii, 2, 3, 4, 5 | Phase II aesthetic batches that target pages that don't survive migration. See Part 5. |

**Total deprecated: ~20 pages.** Additional deprecations emerge during Phase D as Pulse composition clarifies what's redundant.

### 2.5 AMBIGUOUS — my recommendations (user confirms or overrides)

| Item | Recommendation | Rationale |
|---|---|---|
| **Agents page** | Becomes Pulse component (anomaly tiles + recent runs summary on Books/Admin Home) + ApprovalReview becomes **triage queue** (already exists as triage pattern). Individual agent-run detail survives as page. | "Agents" as a page was itself a composed dashboard; current state is closer to a board than a destination |
| **Resale Hub** | Becomes **Resale Space** (new Space for MFG admin/sales when `urn_sales` extension enabled) with composed Pulse. Catalog management stays as page. | Extension-gated; when active, resale work merits its own Space |
| **Compliance Hub + compliance pages** | Compliance Hub → Pulse composition on **Compliance Space** (MFG admin + safety_trainer have it; Phase 8e already seeds this). Individual compliance pages (safety-osha300, safety-training, etc.) stay as drill-down destinations. Compliance Gap Resolution becomes Focus post-September. | Compliance is ongoing monitoring + specific decisions — fits the dashboard-with-quick-edit + Focus-for-real-decisions pattern (PA §3.10) |
| **Operations Board** | Contributors registry survives; **same registry API, new composition target**. Contributors render as Pulse components on Production/Operations Spaces. Extension contributors continue to register. | Registry is the composability contract; the board is the old rendering. Keep registry, change rendering. |
| **Financials Board** | Same pattern as Operations Board. Five zones become Pulse components on Administrative/Books/Ownership Spaces. Registry survives. | Same rationale. |
| **Production page** | Same. Current `production/production-board` contents → Production Space Pulse. Work-order detail stays as page. Pour-event-create → inline widget. | Scheduling Board precedent from PA §3.9 — it's recast, not killed. |
| **Bridgeable Vault user-facing surfaces** | Backend infrastructure survives unchanged. `VaultOverview` user-facing page → **becomes admin Home Pulse.** Vault accounting tabs → survive as admin settings pages (specialized forms). | Vault was the chassis for cross-service composition — Pulse IS that chassis now at the user surface; backend chassis is unchanged. |
| **Scheduling Board** | **ABSORBS into Schedule Space** (per PA §3.9 worked example). Old page renamed + recast as Pulse component "Today's Schedule" / "This Week". Funeral Scheduling Focus is the decision surface launched from it. | Canonical PA example. |
| **Legacy Studio** | Pages survive as admin library. `legacy-proof-review` becomes **Proof Review Focus**; `proof-generator` becomes **Proof Revision Focus** (edit canvas). Library/templates/settings stay as pages. | Reviewing-and-revising is decision-heavy; library is reference. |
| **Order-station** | Becomes **Order Entry Focus** (edit canvas core). Post-September. Pulse component "Active orders needing attention" on Production/Administrative in the meantime. | Fits edit-canvas mode perfectly. |
| **Driver console** | Portal UX, stays as portal. Not subject to Focus/Pulse. Per SPACES_ARCHITECTURE §10. | Different primitive. |

**No remaining genuinely ambiguous items.** If user disagrees with any recommendation above, flag in review.

---

## Part 3 — September Demo Critical Path

Target: Wilbert licensee meeting, September 2026. Demo runs on Sunnycrest + Hopkins seed data.

### 3.1 Must ship (demo blocks without these)

1. **Focus primitive** (PA §5.1) — full-screen overlay, blurred + scaled backdrop, anchored core (supports Kanban + single-record modes for Sep), free-form canvas, 8px grid snap, return pill with 15s countdown.
2. **Funeral Scheduling Focus** (Kanban core) with canonical pin set: cemeteries-with-orders, drive-time matrix, staff availability. Selection-as-query: shift+select 2+ services → route map.
3. **Command Bar entity portal** (PA §4.2) — type entity name, see entity card + action affordances + relational pivots.
4. **Command Bar chip conversation** (PA §4.7) — commitment chips, shift+tab walks back, 150–200ms unpack animation.
5. **Command Bar pause sensor + interpretation chips** (PA §4.8) — 500–700ms pause threshold, interpretation chip appears at ~70% confidence, contextual surfaces fade in on pause.
6. **Disambiguation cards** (PA §4.6) — keyboard-numbered (1–9), Intelligence-driven field choice, escape hatch at bottom. Universal pattern.
7. **Home Space** with composed Pulse (minimum one working Space per role) — Personal / Operational / Anomaly / Activity layers rendering.
8. **Settings Space** (stays functional — Phase 8a already ships it as system space, no regression).
9. **Demo seed data for the canonical flow** — 8 seconds typed action: Hopkins family → schedule Tuesday delivery.
10. **Role-defaulted Pulse composition** for at least FH director, MFG admin, MFG production.
11. **Proof Review Focus + Proof Revision Focus** (cross-tenant, single-record + edit canvas cores) — Sunnycrest + Hopkins seed data supports this end-to-end. PA §7.3 canonical example. **Or mock preview as fallback** only if Phase E is running late mid-August.
12. **Shared Sunnycrest↔Hopkins Space** — cross-tenant Space with shared Pulse dashboards. First concrete cross-tenant surface. **Or mock preview as fallback** per item 11.

### 3.2 Should ship (significant value, possible to cut)

1. **Mocked preview of Cross-tenant Delivery Coordination Focus** — PA §8.1 calls this out as "powerful in the Wilbert room" if mocked. Cheap to stub.
2. **System-suggested pins** in Focus (Intelligence-driven from data shape).
3. **Selection-as-query** in Focus (shift+click 2+ items → contextual widget appears).
4. **Basic observe-and-offer** — at least Monitor flavor ("I notice you check X every Monday — want it pinned?").

### 3.3 Nice to ship (post-September acceptable)

1. Live presence / cursors / locks in Focus (PA §5.8) — Liveblocks/Yjs integration is ~2 weeks; defer.
2. Activity feed in Focus (PA §5.10) — COD-killfeed pattern.
3. Inline chat in Focus (PA §5.9).
4. Async catch-up summaries (PA §5.8).
5. Full observe-and-offer maturity across all primitives (PA §6.1).
6. Per-space color shift via `--surface-base` chroma nudge (PA §3.8) — subtler execution preferred.
7. Spaces Overview "peek" page (PA §3.7).
8. Cross-tenant Spaces beyond the mocked preview — full N-way, not just 1:1 FH↔mfr.

### 3.4 Hard post-September

1. Full Focus library (arrangement conference, quote building, PO review, inventory rebalancing, etc.)
2. Marketing page publishing three-primitive framing
3. Full Space taxonomy polish beyond Phase 0 outputs
4. Cross-tenant compliance benchmarking
5. Network inventory sharing Focus
6. Multi-party disinterment Focus
7. Observe-and-offer pruning loop maturity

### 3.5 Dependencies between items

```
Focus primitive (A)
  ↓
  ├─→ Funeral Scheduling Focus (B)      ← demo hero
  ├─→ Proof Review / Revision Focus (E) ← second demo (must ship)
  └─→ Cross-tenant Space infra (E prereq for shared Space)

Command Bar v2 (C) — independent of A/B/E on frontend
  ↓ (consumes Intelligence backbone, already unified)
  └─→ Entity portal, chips, pause sensor, interpretation chips

Home Pulse (D)
  ↓ depends on
  Phase 0 Spaces taxonomy  ← gated
  Pulse composition engine + component registry
  Role-defaulted composition
```

**A, C can run in parallel.** B depends on A. D depends on Phase 0 + new Pulse engine. E depends on A + cross-tenant Space infra (which is a new primitive atop `fh_02_cross_tenant`).

---

## Part 4 — Build Phase Sequencing

### Phase 0 — Spaces Planning Session (required before Phase D)

- **Sessions:** 1
- **Deliverable:** `SPACES_PLAN.md` at project root
- **Contents:** canonical Space list per vertical × role, Pulse composition plan per Space, role-based layer defaults (Personal/Operational/Anomaly/Activity composition), per-space color palette selection (8–12 curated swatches), Spaces Overview design (PA §3.7), shared cross-tenant Space shape for Sunnycrest↔Hopkins
- **Depends on:** This scope reconciliation complete
- **Blocks:** Phase D
- **Does NOT block:** Phases A, B, C (Focus primitive, Funeral Scheduling Focus, Command Bar)

### Phase A — Focus Primitive Foundation

- **Sessions:** 4–6
- **Deliverables:** React Focus primitive, backdrop (blur + scale + darken), anchored core container (mode-dispatching: Kanban, single-record, edit canvas, triage queue, matrix), free-form canvas (drag + 8px grid snap + soft-cap overflow rail), return pill + 15s countdown + re-arm-on-state-change, exit/entry animations, smart positioning engine, 3-tier layout state (tenant default / per-user / per-session), widget chrome (ghosted by default, hover-reveal)
- **Depends on:** Design language (complete), Spaces infrastructure (complete)
- **Exit criteria:** Open a Focus programmatically with any core mode, dismiss cleanly, re-enter via pill or Cmd+K history

### Phase B — Funeral Scheduling Focus (hero workflow)

- **Sessions:** 4–5
- **Deliverables:** Kanban core mode fully implemented, canonical pin set (cemeteries-with-orders, drive-time matrix, staff availability, vehicle availability), saved pins CRUD, context-aware pins parameterized from Focus scope, selection-as-query (shift+click → route map widget for multi-select), integration with existing scheduling data model
- **Depends on:** Phase A complete
- **Exit criteria:** Open from Schedule Space (or wherever Phase 0 decides), Kanban renders this week's services, drag-drop reschedules, context pins update with canvas state, multi-select surfaces route map

### Phase C — Command Bar Upgrade (v2)

- **Sessions:** 4–6
- **Deliverables:**
  - Entity portal — type name, see entity card composition (customer, case, order, product, cemetery, staff, equipment, vendor, invoice/PO)
  - Floating contextual surfaces (capture confirmation, disambiguation/safety, reference-for-answer)
  - Disambiguation cards (PA §4.6) with Intelligence-driven field selection + keyboard 1–9 + escape hatch
  - Chip conversation (PA §4.7) — commitment chips, shift+tab walk-back, 150–200ms unpack motion
  - Interpretation chips (PA §4.8.1) — outlined/muted treatment, click to inspect alternatives, Cmd+I shortcut
  - Pause sensor (PA §4.8.2) — 500–700ms threshold, adaptive per-user via observe-and-offer, minimum 1s visibility
  - Recognition-and-escalation (PA §4.5) — "this sounds like more than one action — open a Focus?"
  - Discipline enforcement (PA §4.4) — time-bound-by-action, no persistent state, no "open" affordance
- **Depends on:** Intelligence backbone (complete); existing command bar from UI/UX arc (refactor, not greenfield)
- **Exit criteria:** `Hopkins [pick from disambig] schedule delivery Tuesday 10am` demo sequence runs in under 8 seconds end-to-end

### Phase D — Space + Pulse Foundation

- **Sessions:** 3–5
- **Deliverables:**
  - Pulse composition engine (React component that renders composed Pulse from a layout config)
  - Component registry (saved views, briefing card, anomaly cards, pending-decisions, activity stream, action shortcuts, people presence, live-data widgets) — **inherits the board-contributor registry pattern**
  - Per-Space layer composition (Personal / Operational / Anomaly / Activity) with role-defaulted placements
  - Intelligence-driven adaptive composition (time of day, day of week, user behavior)
  - Editability (rearrange, hide, resize, add saved view) with per-user-per-Space persistence
  - Home Space minimum-viable baseline: Pulse renders for FH director, MFG admin, MFG production
  - Migrate OperationsBoardRegistry + FinancialsBoardRegistry contributors to Pulse components
- **Depends on:** Phase 0 (Spaces taxonomy), Intelligence backbone (complete), Spaces infrastructure (complete)
- **Exit criteria:** Navigate to Home Space, see composed Pulse with at least 4 layers rendering, drill into any item, rearrange a component

### Phase E — Second Focus Workflow (cross-tenant personalization) — MUST SHIP

- **Sessions:** 4–5
- **Deliverables:**
  - Proof Review Focus (single-record core: proof image + engraving rules pin + original order + past proofs + service timing context)
  - Proof Revision Focus (edit canvas core: compositor + change request + prior revisions)
  - Timing Conflict Focus (calendar core: production schedule + urgency + alternate dates)
  - **Cross-tenant Space infrastructure** atop `fh_02_cross_tenant` — "Sunnycrest↔Hopkins" shared Space with shared dashboards
  - Shared Space Pulse composition (personalization items by proof status, timing pipeline, historical proofs, relationship notes)
  - Decision-bounded invitation flavor (PA §5.12) — auto-expires on decision
  - Mocked preview of Cross-tenant Delivery Coordination Focus (if time permits)
- **Depends on:** Phase A complete, `fh_02_cross_tenant` infra (live)
- **Exit criteria:** Sunnycrest and Hopkins (two tenants) can collaborate on a proof review in a shared Focus; manufacturer submits revision; FH approves; audit trail clean; cross-realm permission respected
- **Fallback:** If Phase E is running late mid-August, downgrade to mocked preview only per PA §8.1 — demo shows the vision but doesn't drive real cross-tenant data

### Phase F — Demo Polish

- **Sessions:** 2–3
- **Deliverables:** Motion tuning on all new primitives (enter/exit/pause-sensor-fade-in), demo seed data polish (Sunnycrest/Hopkins roster complete, realistic case/proof/delivery data), Wilbert demo script walkthrough with director narrative, aesthetic refinement on Focus/Pulse/new command-bar surfaces
- **Depends on:** Phases A, B, C, D, E (whatever's in for September)
- **Exit criteria:** 15-minute demo runs flawlessly on staging with Sunnycrest + Hopkins data

### Phase G — Latent Bug Cleanup

- **Sessions:** 2
- **Deliverables:** Items from CLAUDE.md latent bug list — `drivers.employee_id` column drop, invite/recovery token split, `pdf_document_id` FK pointer (r15 → canonical), UTC-vs-tenant-local time_of_day scheduler, statement-run failure rollback gap, PortalBrandProvider BT.601 → WCAG luminance alignment, etc.
- **Depends on:** None critical
- **Exit criteria:** Known latent bugs resolved

### Phase H — Phase 8f/g/h (accounting + dashboard + arc finale)

- **Sessions:** 4–6
- **Deliverables:** Remaining accounting migrations (unbilled_orders, estimated_tax_prep, inventory_reconciliation, budget_vs_actual, 1099_prep, year_end_close, tax_package, annual_budget per Workflow Arc template), Pulse-ification of financial surfaces (Financials Board contributors → Pulse components), workflow arc finale
- **Depends on:** Phase D (Pulse infrastructure exists)
- **Exit criteria:** Business Pulse components render financial state correctly across all tenant types; Workflow Arc complete

**Total estimate: 25–35 sessions.**

**Parallelization:** Phases A, B, C execute in parallel for the first 4–5 sessions each (no inter-dependencies until B's scheduling-specific work needs A's primitive; C is entirely independent until demo rehearsal). Phase 0 runs in parallel with Phase A session 1 (Spaces planning doesn't need Focus to exist).

---

## Part 5 — What Dies

### 5.1 Pages to delete

After Phase D, the following are deleted (assuming replacements in place):

| Path | Rationale |
|---|---|
| `console/console-select.tsx` | Role-default Space landing replaces console picker |
| `dashboard/admin-dashboard.tsx` | Replaced by admin role Home Space Pulse |
| `dashboard/employee-dashboard.tsx` | Replaced by non-admin role Home Space Pulse |
| `operations/operations-board-desktop.tsx` | Replaced by Operations/Production Space Pulse |
| `financials-board.tsx` | Replaced by Administrative/Books Space Pulse |
| `hubs/compliance-hub.tsx` | Replaced by Compliance Space Pulse |
| `hubs/crm-hub.tsx` | Replaced by Pulse composition across Spaces |
| `hubs/financials-hub.tsx` | Replaced by Administrative Pulse |
| `hubs/production-hub.tsx` | Replaced by Production Space Pulse |
| `quoting/quoting-hub.tsx` | Replaced by Sales Space Pulse |
| `resale/resale-hub.tsx` | Replaced by Resale Space Pulse (when extension active) |
| `production/production-board.tsx` | Replaced by Production Pulse + Production Scheduling Focus |
| `production/ProductionBoardDashboard.tsx` | Same |
| `delivery/dispatch.tsx` | Absorbs into Operations Pulse |
| `delivery/operations.tsx` | Absorbs into Operations Pulse |
| `team/team-dashboard.tsx` | Absorbs into Home Pulse for owner/director |
| `admin/driver-portal-preview.tsx` | Dev preview surface; retire when portal production-verified |
| `compliance/npca-audit-prep.tsx` | Placeholder; rebuild as Pulse anomaly card when real |
| `console/operations-board.tsx` | Absorbs into Operations Pulse |

**Total: ~19 top-level pages to delete.** Sub-components in these files (widget-style rendering logic) either migrate into Pulse components or get reused.

### 5.2 Components to delete (to be inventoried in Phase D)

- Legacy board-rendering chrome (Operations Board desktop layout wrapper, Financials Board 5-zone wrapper) — contributors survive; rendering wrappers don't
- `WidgetGrid` home-context rendering — replaced by Pulse composition engine
- Console shell wrappers (`console-select` navigation, console-specific layouts)
- Dashboard chrome wrappers (`manufacturing-dashboard`, `funeral-home/dashboard` composition shells)

### 5.3 Code to retain as infrastructure

- Data fetching layers (`lib/api-client`, all axios service modules)
- API routes feeding widgets + saved views (all v1 routes survive)
- Database models (entire data layer unchanged; CaseVault, VaultItem, CompanyEntity, all domain models)
- Board-contributor registry pattern — **adopt as Pulse component registry**
- Saved-view infrastructure (Phase 2 of UI/UX arc)
- Intelligence backbone (entire unified layer)
- Triage infrastructure (Phase 5 of UI/UX arc; some current triage queues become Focus triage cores)
- Briefing infrastructure (Phase 6 of UI/UX arc; briefing-card becomes Pulse component)
- Spaces primitive (Phase 3, 8e, 8e.1, 8e.2 of UI/UX + Workflow arcs; Spaces are the Monitor primitive)
- NL Creation (Phase 4 of UI/UX arc; integrates into Command Bar v2)
- Onboarding touch infrastructure (Phase 7 of UI/UX arc)

### 5.4 Phase II aesthetic batches that don't ship

| Batch | Status | Outcome |
|---|---|---|
| Batch 1a (Infrastructure + user-reported + agents family) | ✅ Shipped | Keep — refreshed surfaces provide good baseline for transition |
| Batch 1b (Scheduling Board Family) | ✅ Shipped | Keep — scheduling-board is recast as Pulse component, refreshed state carries over |
| Batch 1c-i (order-station refresh) | **Does not ship** | order-station becomes Order Entry Focus (Phase H or later); aesthetic built into Focus construction |
| Batch 1c-ii (financials-board + team-dashboard) | **Does not ship** | Both become Pulse surfaces; rebuild, don't refresh |
| Batch 2 (inventory + production + ~page-chrome migration) | **Partial — page-chrome migration stays, page-specific batches drop** | Page-chrome = shadcn default aliasing (Batch 0 already shipped); remaining page-specific aesthetic becomes Pulse composition styling work |
| Batch 3 (CRM + financials detail pages) | **Drop** | Detail pages get touched in passing when any of Phases A–H touches them; no dedicated aesthetic batch |
| Batch 4 (settings pages) | **Drop** | Settings pages receive polish via Phase 8e.1-style natural-refactor, not a batch |
| Batch 5 (leftover long-tail) | **Drop** | Natural refactor as touched |

**User's "aesthetic polish happens after architecture" decision preserved.** Phase F (Demo Polish) handles the new-primitive aesthetic refinement. Everything else happens in passing or post-September.

---

## Part 6 — Open Questions Requiring Decisions

### 6.1 Naming

**Pulse surface name: "Pulse"** (decision made; canonical).

Reasoning: every user has a "Home Space" per the scope-reconciliation user premise (minimum viable Spaces state = Home + Settings). Using "Home" for both the Space and its primary surface creates naming collision — "Home Space's Home" is awkward. "Home Space's Pulse" is clear. "Pulse" is also the canonical name in [PLATFORM_ARCHITECTURE.md §3](PLATFORM_ARCHITECTURE.md) (§3.3 "The Pulse Surface (per Space)"); this decision preserves consistency with the canonical spec. Alternatives considered and rejected: "Home" (collision), "Live View" (descriptive but flat), "The Surface" (too abstract).

### 6.2 Architecture

- **Spaces Overview vs Cross-Space Overview.** PA §8.3. **Recommendation: siblings.** Spaces Overview (§3.7) = management/edit surface for nav structures ("peek"); Cross-Space Overview (§3.6) = leadership Pulse composing across Spaces. Different users, different purposes, different real estate.
- **Empty command bar behavior.** PA §8.5. **Recommendation: yes with restraint** — after entity chip is created, show common actions as keyboard-numbered options. Disappear on typing. Serves new users without slowing power users.
- **Database schema for Focus state persistence.** **Recommendation: new `focus_sessions` table** (user_id, focus_type, layout_state JSONB, pin_overrides JSONB, is_active, opened_at, closed_at, last_interacted_at). Plus tenant-default layout in `focus_layout_defaults` (tenant_id, focus_type, layout_state JSONB). Mirrors Saved-View + Space persistence patterns.

### 6.3 Migration

- **Transition strategy — gradual or immediate.** **Recommendation: gradual replacement during build, aggressive cleanup once each Focus/Pulse lands.** Focus primitive coexists with current pages during Phase A/B; as each Focus goes live, the page it replaces gets deleted in the same commit. Avoids dual-maintenance periods.
- **Real-time infrastructure — Liveblocks/Yjs vs defer.** **Recommendation: defer live collaboration post-September.** Focus primitive ships without cursors/presence/chat for v1. Single-user Focus is enough for demo. Liveblocks integration becomes Phase I (post-September).

### 6.4 Scope

- **Cross-tenant personalization Focus — ships or mocked?** **Decision: target ship for September.** Sunnycrest↔Hopkins seed data supports it end-to-end; PA §7.3 is the canonical worked example. Mock preview is fallback only if Phase E is running late mid-August. Phase E is in-scope for the September demo.
- **Number of Spaces with composed Pulse at September.** **Recommendation: depends on Phase 0 outcome — minimum Home across every role, plus Settings.** Phase 0's Spaces Plan determines whether Production, Administrative, Books each ship with distinct Pulse compositions or all share Home baseline.
- **Mobile / iPad support for Focus.** **Recommendation: desktop only for September.** PA §5.7 notes touch uses preset zones. iPad support is post-September.
- **Accessibility baseline.** **Recommendation: maintain WCAG 2.4.7 / 2.2 AA baseline.** Focus primitive needs keyboard navigation (Esc close, Tab through pins, Enter commits decisions), screen reader semantics (focus traps, dialog role), brass focus ring continues (DESIGN_LANGUAGE §9 discipline).

### 6.5 Out-of-scope for this session (flagged for future sessions)

- Marketing page publishing three-primitive framing (post-September)
- Full platform-level urgent activity channel (PA §8.6)
- Behavioral analytics privacy surface (PA §8.7)
- Naming sweep opportunity (PA §8.8)

---

## Part 7 — Session-by-Session Schedule (First 10 Sessions)

### Session 1 — Phase 0: Spaces Planning

- **Goal:** Produce `SPACES_PLAN.md` defining Space taxonomy for migration
- **Input:** PLATFORM_ARCHITECTURE.md, SPACES_ARCHITECTURE.md, FUNERAL_HOME_VERTICAL.md, current seed templates in registry.py, user discussion
- **Output:** Canonical Space list (likely Home + Administrative + Production + Operations + Arrangement + Books + Compliance + Ownership + Settings + cross-tenant shared Spaces), per-Space Pulse composition plan, role-based defaults, per-Space color palette (8–12 curated swatches), Spaces Overview design
- **Blocks Phase D**; does not block Phase A, B, C

### Session 2 — Phase A: Focus primitive scaffolding

- **Goal:** Base Focus component with backdrop + dismiss + animation
- **Tasks:** FocusProvider context, Focus component with blurred backdrop, framer-motion enter/exit, placeholder core container, backdrop-click dismiss, return-pill scaffolding
- **Output:** Can open Focus programmatically with a placeholder core, dismiss, see return pill

### Session 3 — Phase A: Focus anchored core + canvas foundation

- **Goal:** Core mode dispatcher + canvas infrastructure
- **Tasks:** Core component mode-variants (Kanban / single-record / edit canvas / triage queue / matrix), canvas positioning (8px grid snap, free-form drag), widget chrome (drag handle / resize / dismiss X) ghosted by default, layout-state persistence scaffold (per-session + per-user + tenant-default)
- **Output:** Focus can render any core mode + canvas with placeholder widgets

### Session 4 — Phase A: Return pill + re-entry

- **Goal:** Exit/re-entry UX with restraint
- **Tasks:** Return pill UI with 15s countdown, hover pauses countdown, re-arm logic on Focus state change, Cmd+K history integration (only most recent Focus gets pill; older via Cmd+K search)
- **Output:** User exits Focus, sees pill, hovers to pause, re-enters via pill or Cmd+K

### Session 5 — Phase A: Pin system (saved pins + storage)

- **Goal:** Pin infrastructure — saved pins persist per user/tenant
- **Tasks:** Pin database schema, pin rendering on canvas, smart positioning (open regions, prefer edges), saved pin management UI (add/remove/rename), Vault-view and parameterized-widget pin types
- **Output:** User can pin a saved view or widget, see it render, reposition it, persist across sessions

### Session 6 — Phase A: Pin system (context-aware + system-suggested)

- **Goal:** Intelligence-driven pins
- **Tasks:** Context binding from Focus scope (pin parameters resolve at render time from Focus state), Intelligence backbone integration for pin suggestions (data-shape inference — if items have location, suggest map; if items have staff refs, suggest availability), system-suggested pin UI treatment (dismissible, brass sparkle, observe-and-offer accept/decline)
- **Output:** Opening a Focus surfaces suggested pins based on data shape; user can accept/decline

### Session 7 — Phase B: Funeral Scheduling Focus — Kanban core

- **Goal:** Scheduling Kanban in Focus
- **Tasks:** Kanban core component (days × services with drag-drop between day columns), integration with existing `delivery/scheduling-board` data model, drag-drop updates backing data
- **Output:** Open funeral scheduling Focus, see this week's services in Kanban, drag-drop reschedules

### Session 8 — Phase B: Funeral Scheduling Focus — canonical pin set

- **Goal:** The three canonical scheduling pins
- **Tasks:** Cemeteries-with-orders pin (Vault view filtered by `cemetery_id IN (cemeteries on canvas)`), drive-time matrix pin (computed widget over Maps API), staff availability pin (Vault view filtered by date × role)
- **Output:** Scheduling Focus renders Kanban + all three context-aware pins updating with canvas state

### Session 9 — Phase B: Funeral Scheduling Focus — selection-as-query

- **Goal:** Multi-select drives contextual widgets (PA §5.5)
- **Tasks:** Shift+click multi-select UI, selection-bound widget rendering (replaces standing pins while selection active), route map for multi-select (TSP-style optimized ordering), conflict indicator widget (time-gap vs drive-time)
- **Output:** Shift-select 2+ services → route map + conflict indicator appear; deselect → revert

### Session 10 — Phase C: Command Bar — entity portal

- **Goal:** Type entity, see surfaces (PA §4.2)
- **Tasks:** Entity recognition via Intelligence backbone (extend beyond existing command bar entity resolution), entity card rendering per type (customer/case/order/product/cemetery/staff/equipment/vendor/invoice), relational pivots (click an order on customer's card → order's card appears), action affordances (click-to-call, text, email, note, common actions)
- **Output:** Type "Hopkins" in command bar → Hopkins FH entity card appears with action affordances; click a related case → case card replaces customer card

### Coarse planning for sessions 11–35

Sessions 11–15: Phase C continues (chips, pause sensor, interpretation chips, disambiguation, recognition-and-escalation). Phase A should be finishing; Phase B solid.

Sessions 16–20: Phase D (Space + Pulse foundation) begins once Phase 0 complete. Pulse composition engine, component registry, migrate board contributors.

Sessions 21–25: Phase E (cross-tenant personalization — must ship) in flight. Mid-August checkpoint: if E is behind, downgrade to mocked preview.

Sessions 26–30: Phase F (demo polish) + Phase G (latent bugs).

Sessions 31–35: Phase H (accounting migrations + arc finale).

Detailed sessions emerge as execution provides feedback.

---

## Appendix A — Bounded-decision discipline audit

Every proposed Focus (Part 2.3) confirmed nameable-in-one-sentence per PA §5.14:

- Funeral Scheduling: "Commit this week's service schedule."
- Proof Review: "Approve or request revision on this proof."
- Proof Revision: "Submit a new proof version for this change request."
- Arrangement Conference: "Populate the case file completely enough to advance the staircase."
- Disinterment Scheduling: "Commit a date and crew to this disinterment."
- Quote Building: "Commit and send this quote."
- PO Review: "Approve or reject each PO in the queue."
- Inventory Rebalancing: "Move N items from location A to location B."
- Personalization Request Processing: "Clear this batch of personalization requests."
- Cross-tenant Delivery Coordination: "Commit delivery time for this service."
- Timing Conflict: "Commit new delivery date."
- Order Entry: "Commit order details and pricing."
- Compliance Gap Resolution: "Close each critical compliance item."
- Production Scheduling: "Commit pour schedule for this week."

All exit when the decision commits. No dashboards in disguise.

---

## Appendix B — "Would a good coach do this?" test

Every proposed primitive and flow passes PA §1:

- **Focus** — pulls up materials, spreads them out, decides together, steps back: coach-shaped ✓
- **Pulse Home** — shows what's on your plate without making you hunt: coach-shaped ✓
- **Command Bar v2 with pause sensor** — waits for you to think before interrupting: coach-shaped ✓
- **Interpretation chips** — shows what it thinks, invites correction: coach-shaped ✓
- **Disambiguation cards** — doesn't pretend, asks: coach-shaped ✓
- **Observe-and-offer** — notices patterns, proposes adjustments, respects no: coach-shaped ✓
- **Cross-tenant shared Space** — brings both sides' relevant context to the conversation: coach-shaped ✓

---

## Appendix C — Vault-as-foundation preservation

All data architecture unchanged:

- `vaults`, `vault_items` — foundation layer untouched
- Case model (14 tables from FUNERAL_HOME_VERTICAL.md) — schema unchanged when FH vertical ships
- Cross-tenant FKs (`fh_02_cross_tenant`) — unchanged
- Intelligence execution audit (`intelligence_executions` + caller_* linkage) — unchanged
- Saved views, spaces, briefings, triage, tasks — Phase 1–7 UI/UX arc storage unchanged
- Documents, deliveries, signing — Phases D-1 through D-9 storage unchanged

**No database migrations required for Phases A, B, C.** Phase D introduces `focus_sessions` + `focus_layout_defaults` tables. Phase E may introduce a `cross_tenant_spaces` table or reuse the existing `platform_tenant_relationships`.

---

_End of ARCHITECTURE_MIGRATION.md_
