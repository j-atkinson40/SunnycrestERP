# Bridgeable Workflow Arc

Parallel to the completed UI/UX Arc. The Workflow Arc completes the workflow layer of the platform:

1. Classify every workflow into a scope (Core / Vertical / Tenant) + treat workflows as a first-class customization surface
2. Migrate accounting agents from their separate `AgentRunner` system into real workflow definitions
3. Build space + default-view infrastructure so role-based UX suggestions become user-composable templates rather than forced seeds
4. Ship a grid-based dashboard surface backed by saved views

Runs in parallel with the separate Aesthetic Arc (design system refresh: sunny-patio light mode, cocktail-lounge dark mode). Aesthetic tokens land mid-arc; later Workflow Arc phases inherit them.

---

## Umbrella Principle — Opinionated but Configurable

See `CLAUDE.md § 1a-pre` for the full treatment. Every Workflow Arc phase is evaluable against this principle:

- **Opinionated:** the platform ships working defaults so a new tenant has a working Monday morning without configuring a thing. Role-based seeds run at registration. Settings is pinned in the dot nav when the user is admin. Accounting agents are registered in the core scope tab out of the box.
- **Configurable:** nothing is forced thereafter. Role CHANGES don't force UX content. Platform workflow updates don't propagate to tenant forks. System spaces can be renamed and recolored. Every seeded default is a starting point, not a destination.

When the two conflict: bias toward opinionated for first-run, configurable thereafter.

---

## Phase-by-Phase Plan

### Phase 8a — Foundation Infrastructure (April 2026)

**Shipped.** Establishes the architectural commitments all subsequent phases build on.

- Workflow `scope` field (Core / Vertical / Tenant) via migration `r36_workflow_scope`
- Tenant fork mechanism (Option A — independent copies) alongside the existing enrollment-override path (Option B — soft customization). Both paths preserved intentionally.
- Settings registered as a platform space via `SYSTEM_SPACE_TEMPLATES` — admin-only, non-deletable (can be renamed + recolored)
- DotNav — horizontal dots at the bottom of the left sidebar, replaces Phase 3's top-bar SpaceSwitcher
- Role decoupling preparation — `ROLE_CHANGE_RESEED_ENABLED=False` gates role-change re-seeds; registration-time seeds preserved; `reapply_role_defaults_for_user()` helper available for opt-in UI in Phase 8e
- Agent-backed workflow stubs get a "Built-in implementation" badge + read-only click-through; badge clears per row as agents migrate in 8b-8f
- BLOCKING CI gates: workflow-scope-core p50<100ms/p99<300ms, workflow-fork p50<200ms/p99<500ms, spaces-with-system p50<100ms/p99<300ms

No migration of existing workflows yet. The 13 accounting agents stay in `AgentRunner.AGENT_REGISTRY`.

### Phase 8b — Reconnaissance Migration: Cash Receipts Matching

**Shipped.** First accounting agent migrated into a real workflow definition. Patterns documented in `WORKFLOW_MIGRATION_TEMPLATE.md` at project root (primary deliverable, the checklist 8c–8f compare against).

- Parity adapter (`backend/app/services/workflows/cash_receipts_adapter.py`) — thin bridge preserving side effects via service reuse (`approve_match` / `reject_match` / `override_match` / `request_review` + `run_match_pipeline`). Zero logic duplication; `run_match_pipeline` delegates end-to-end to `AgentRunner.run_job`.
- New workflow engine action subtype `call_service_method` with a whitelisted dispatch registry (`_SERVICE_METHOD_REGISTRY`). Built once in 8b, reused for every 8c–8f migration.
- New workflow row `wf_sys_cash_receipts` in `TIER_1_WORKFLOWS` with `trigger_type="time_of_day"` at 23:30 ET daily. `agent_registry_key=NULL` (8b-beta state of the badge choreography — never had a row before). Existing `workflow_scheduler.check_time_based_workflows` sweep fires it — no `backend/app/scheduler.py` changes.
- New triage queue `cash_receipts_matching_triage` in `platform_defaults.py` (cross-vertical, `invoice.approve` permission). 4 action handlers under `cash_receipts.*` keys. Direct query builder + related-entity builder + AI question prompt (`triage.cash_receipts_context_question`).
- BLOCKING parity test `test_cash_receipts_migration_parity.py` — 9 tests across 5 categories (PaymentApplication identity, reject no-write, anomaly resolution, negative PeriodLock, pipeline-scale equivalence + tenant isolation + triage engine integration).
- BLOCKING latency gates `test_cash_receipts_triage_latency.py` — next_item p50=18.7ms/p99=20.1ms (budget 100/300) + apply_action p50=15.7ms/p99=22.5ms (budget 200/500).
- Unit tests (18) cover queue registration, `_DIRECT_QUERIES` dispatch, `_RELATED_ENTITY_BUILDERS` dispatch, handler registration, workflow engine registry, workflow seed shape, adapter edge cases.
- 5 Playwright E2E scenarios verify queue registration, workflow visibility + badge state, legacy coexistence (/agents + /agents/:id/review still mount).
- Legacy `POST /api/v1/agents/accounting` + `AgentDashboard.tsx` + `ApprovalReview.tsx` preserved for ad-hoc forensic re-runs. Operational coexistence contract documented in both CLAUDE.md and the migration template. Legacy retirement deferred to Phase 8h+.

Latent bugs surfaced + flagged for separate sessions:
- `wf_sys_ar_collections` `trigger_type="scheduled"` not dispatched by `workflow_scheduler` today (latent bug predating 8b).
- Approval-gate email body is hardcoded HTML, predating D-7 delivery abstraction. Parity requires preserving verbatim.

### Phase 8c — Core Accounting Migrations (Batch 1)

**Not started.** Migrate the next batch of accounting agents (month-end close, AR collections, expense categorization — the three with existing wf_sys_* stubs carrying `agent_registry_key`) into real workflow definitions. Per migrated agent, the stub row's `agent_registry_key` clears and the "Built-in implementation" badge disappears.

This phase also includes the fork-vs-override UX polish deferred from 8a per finding G.

### Phase 8d — Vertical Workflow Migrations

**Not started.** Work through the remaining Tier 2 / Tier 3 vertical workflows (manufacturing, funeral_home). Surface any patterns that the Core migrations missed. Expected to be substantially lighter than 8c because vertical workflows are already stored as real workflow rows — this phase is mostly about evolving the builder UX for vertical-specific needs.

### Phase 8e — Spaces + Default Views

**Not started.** Template-per-responsibility-domain system + inferred topical affinity ranking in command bar. Builds the UI surface for the `reapply_role_defaults_for_user()` helper shipped in 8a. Roles fully decouple from UX content; "starting suggestions" are composable templates rather than role-tuple lookups.

### Phase 8f — Remaining Accounting Migrations

**Not started.** The final accounting agents (unbilled_orders, cash_receipts_matching if not covered in 8b, estimated_tax_prep, inventory_reconciliation, budget_vs_actual, 1099_prep, year_end_close, tax_package, annual_budget). `AgentRunner.AGENT_REGISTRY` becomes empty; the agent system becomes a thin compatibility layer or is retired entirely.

### Phase 8g — Dashboard Rework

**Not started.** Grid-based flexible dashboard surface backed by saved views (leverages the Phase 2 executor + the Phase 3 grid primitives).

### Phase 8h — Arc Finale

**Not started.** Closing polish + documentation. Notification UI for "base workflow updated — review differences" on forks. Migration of the remaining ~25 settings pages from the legacy left-nav Settings sub-section into the Settings space.

---

## Architectural Principles

### 1. Workflow scope as platform pattern

`workflows.scope` is the canonical classification. `Core` is platform-wide. `Vertical` is tenant-matched. `Tenant` is tenant-owned. Future: `user` scope for per-user workflows (post-arc).

Tier field stays — now orthogonal to scope ("default-on vs default-off within scope"). Tier 1 → core. Tier 2/3 → vertical. Tier 4 → tenant.

### 2. Dual customization — Option A + Option B

Tenants have two paths when they want to customize a platform workflow:

- **Soft:** enroll + parameter-override. `WorkflowEnrollment` row + `WorkflowStepParam` rows with `company_id` set. Platform updates DO propagate (new steps appear; base defaults update).
- **Hard:** fork into independent tenant copy. `POST /api/v1/workflows/{id}/fork`. `forked_from_workflow_id` + `forked_at` stamped. Platform updates do NOT propagate.

Both paths are deliberate. The UX of "when to use which" lands in Phase 8c.

### 3. Settings as first-class space

Settings is a registered platform space, not a separate area with different UX. Admin users get it seeded in their dot nav. It pins pages like any other space. The user learns the platform's primitives once and they work in Settings too.

### 4. DotNav — horizontal dots at the bottom of the left sidebar

Replaces the Phase 3 top-bar SpaceSwitcher. System spaces (Settings) sort leftmost. Plus button creates a new space. Per-space icons replace the colored dot when mapped. Phase 3 keyboard shortcuts preserved (`Cmd+[` / `Cmd+]` / `Cmd+Shift+1..5`).

### 5. Roles decouple from UX defaults

Roles grant permissions. They do NOT force UX content on role changes. Registration-time seeds still bootstrap new users; role changes stop auto-re-seeding. `ROLE_CHANGE_RESEED_ENABLED: bool = False` is the gate; `reapply_role_defaults_for_user()` is the opt-in path for future UI in 8e.

### 6. Opinionated but Configurable

See Umbrella Principle above + `CLAUDE.md § 1a-pre`.

---

## Cross-Arc Integration with Aesthetic Arc

The Aesthetic Arc ships in parallel:
- Light mode: "sunny patio morning" — warm neutrals, high legibility, soft shadows
- Dark mode: "high-end cocktail lounge" — muted blues and greens, dim with focal points

Aesthetic tokens land mid-Workflow-Arc. Phases 8a-8c use current tokens. Phases 8d+ inherit the new tokens. No Workflow Arc phase is blocked on the Aesthetic Arc; they compose.

---

## Post-Arc Backlog

- **User-scope workflows** (`scope="user"` — personal automations owned by a single user within a tenant). Deferred to post-arc.
- **"Base updated" notification** on forks. The data model ships in 8a (`forked_from_workflow_id` + `forked_at`); UI lands in 8h or later.
- **Base-to-fork diff + selective absorb.** "Copy these N step changes from the source into my fork." Extension of the fork model. Post-arc unless customer signal is strong.
- **Complete settings-page migration** into the Settings space. 8a pins 4 pages; 8h+ progressively migrates the rest. 30+ pages total in the existing sidebar sub-section.
- **Orphan migrations r34_order_service_fields through r39_legacy_proof_fields** — pre-existing feature-branch files that never reconciled with the UI/UX Arc chain. Flagged in the Phase 8a audit. Needs a dedicated cleanup session; out of scope for Phase 8a.

---

## Phase 8a — Final State

**Migration head:** `r36_workflow_scope`
**New backend tests:** 30 (16 workflow scope/fork + 14 system space / role decoupling)
**BLOCKING latency gates:** 5 new (workflow scope filter, scope+used_by, vertical filter, spaces with system, workflow fork) + 7 from the UI/UX arc = 12 total
**New vitest:** 6 (DotNav)
**Playwright scenarios:** 6 (dot nav render, switch spaces, Settings for admin, scope cards + agent badge, fork flow, SpaceSwitcher regression)
**Tables added/modified:** `workflows` gains 4 columns (`scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`) + CHECK + index. No new tables.

**Workflow scope distribution** (on seeded dev tenant after r36):
- 16 core (wf_sys_*) — 3 with `agent_registry_key` populated
- 21 vertical — manufacturing + funeral_home specific
- 0 tenant — reserved for tenant-created
