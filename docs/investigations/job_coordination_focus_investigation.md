# Job Coordination Focus — Scoping Investigation (Phase 0)

**Date:** 2026-06-10 · **HEAD:** `0613ff9` · **Read-only** — no code, no canon, no commit, no dispatch.
**Scope:** the canonical demo scenario ONLY (Hopkins case commits → vault order lands at Sunnycrest → a Job Coordination Focus for THAT job: production-schedule view + joint cross-tenant calendar event + embedded comms thread + the Hopkins director as a decision-bounded cross-tenant participant → auto-expire on delivery). The generalized war-room (sub-Focuses, unified inbox, every lifecycle template) is out of scope, filed forward.
**Method:** four parallel read-only sweeps (Focus runtime deep · cross-tenant substrate deep · comms+access survey · canon-spec extraction) + direct verification of the two load-bearing services. Depth note: A+B went deep per the STOP discipline; C+D are surveys — honest gaps marked `[verify in Phase 1 pre-flight]`.

---

## HEADLINE VERDICT (Lens E up front)

**The canonical scenario is an ASSEMBLY, not a primitive build.** The two scariest-sounding pieces — "a real cross-tenant order" and "a joint cross-tenant calendar event" — are **already built at the service layer** (the dispatch's hypotheses under-estimated the substrate, in the good direction, twice). The genuinely net-new work is bounded: a **FocusShare grant** (~DocumentShare clone + service check), a **thin coordination core + composition template + 2–3 widgets**, the **tenant-side composition resolver wiring** (a known deferred follow-up), the **comms-tier choice** (the only real product decision), and **demo choreography**. No new top-tier primitive (no channel system, no guest auth, no presence infra) is required for the demo slice.

**JCF is a contained composition arc** — multi-session, but every session is composition/extension on proven substrate, not foundation-pouring. The September answer: **viable**, with the comms tier and the entry-surface decision as the two calls that shape the schedule.

### Dispatch corrections (epistemic-warning findings — hypotheses vs code)

| Dispatch claim | Reality (file:line) |
|---|---|
| "funeral_cascade already emits cross_tenant_order/cross_tenant_request nodes" | TRUE in the seed canvas — but they are **pure canvas stubs**: `canvas_validator.py:109-111` declares them; `workflow_engine.py:635-693` has **no executor** (they'd return `unknown_action_type`). The REAL order path is services, not these nodes. |
| (implied) cross-tenant order needs building | **Built twice over**: `fh/cross_tenant_vault_service.py::create_vault_order` writes a **real `sales_orders` row at the manufacturer tenant** when the family approves a vault (wired into `story_thread_service` — the Story step), + `sync_order_status` back-syncs status to the case. Separately `licensee_transfer_service.py:88-148` (LicenseeTransfer + cross-tenant notification + billing chain) covers licensee↔licensee. |
| "Calendar… can it represent a JOINT event, or net-new?" | **Mostly built**: `CalendarEvent.is_cross_tenant` (`calendar_primitive.py:372`) + `CrossTenantEventPairing` (`:631-672`) + **the full runtime lifecycle** `calendar/cross_tenant_pairing_service.py` — `propose_pairing / finalize_pairing / revoke_pairing / list_pairings_for_tenant / list_participants_for_tenant_side`, bilateral acceptance state machine per §3.26.16.14, API-exposed via `calendar_actions.py` + `widget_data.py`. Thin spot: dedicated frontend acceptance UI appears absent `[verify in Phase 1 pre-flight]`. |
| "the Focus inline-chat rail is spec-only" | **Confirmed** — §5.9/§14.13/§14.15 canon, zero code. The platform has NO in-platform messaging substrate (the `communication_thread` triage panel stub explicitly waits on one). |

---

## A. FOCUS RUNTIME TODAY (deep)

**Cores actually runnable: ONE.** `SchedulingKanbanCore` (1,714 LOC) wrapped by `SchedulingFocusWithAccessories` → registered as `funeral-scheduling` via `registerFocus(...)` (`dispatch/scheduling-focus/register.ts:90-151`). Five mode stubs exist (`focus/cores/`: KanbanCore, SingleRecordCore, EditCanvasCore, TriageQueueCore, MatrixCore — placeholders, not production). The generation Focus is **backend-headless only** (`workflow_engine.py::_handle_invoke_generation_focus`). §14.13/§14.15 (Messaging/Coordination visual canons) have **zero code** behind them.

**Composition layer: built (3-tier).** FocusCore (Tier 1, platform registry; the core is CODE) → FocusTemplate (Tier 2, rows of placements incl. one `is_core=true`) → FocusComposition (Tier 3, tenant deltas). Resolver + renderer + editor + seeds all exist. **Gap:** `useResolvedComposition` hits the **admin-scoped** endpoint only — the production tenant-side resolve endpoint is the known deferred follow-up (CLAUDE.md r84 note) and is a hard prerequisite for any composed Focus at runtime.

**Placements at runtime = widgets only.** `CompositionRenderer` runtime path dispatches `component_kind="widget"` via `getWidgetRenderer(name)`; other kinds render "unavailable". Registered renderers already include `vault_schedule`, `calendar_summary`, `calendar_glance`, `email_glance`, `saved_view`, etc.

**Per-instance binding: no framework, but a proven pattern.** Placements carry static `prop_overrides` only. Operational scoping flows through **feature-owned React context** (AncillaryPoolPin ← `SchedulingFocusContext`). A job-scoped Focus = thin core reads `jobId` from focus-open params and broadcasts via a `CoordinationJobContext`; widgets subscribe. **No new data-binding layer needed.**

**Lifecycle: built.** `focus_sessions` (company_id + user_id + focus_type + layout_state + is_active + `task_id` FK from r108), open/close/layout endpoints, command-bar + URL + return-pill invocation. The task substrate's `focus_closer` subscriber closes sessions on task completion — the **auto-close-on-decision hook already exists** (bind the Focus to the job's task; transfer-fulfilled completes the task → session closes). Frontend push-notification of the close is unverified `[Phase 1 pre-flight]`.

**Core-vs-composition verdict: COMPOSITION with a thin core.** All four content pieces are widget-placeable (two exist: `vault_schedule`, `calendar_summary`; two are new cheap widgets: `coordination_thread`, `participant_list`). The core is a scoping container (`{jobId}` → context), not an operational machine like the kanban. A new heavyweight core type is unjustified; the thin-core+composition pattern is also the reusable shape for future coordination Focuses.

---

## B. CROSS-TENANT SUBSTRATE (deep)

**The order lands at Sunnycrest: 0 LOC.** Two built paths: (1) `cross_tenant_vault_service.create_vault_order` — FH vault approval → **raw INSERT into the manufacturer's `sales_orders`** (appears in Order Station like any order; customer = the FH; `already_ordered` idempotency; `manual` fallback when no connection) + `sync_order_status` back-sync; (2) `LicenseeTransfer` (model `:14-89`, service `:88-148`) with notification + acceptance + billing chain. The demo's trigger is REAL today. The seeded Hopkins↔Sunnycrest `PlatformTenantRelationship` (`platform_tenant_relationship.py:12-106`) is the connection substrate — it carries **bilateral consent state machines** (`calendar_freebusy_consent`, `personalization_studio_cross_tenant_sharing_consent`) but no granular RBAC.

**DocumentShare = the grant template.** `document_share.py:44-125`: owner_company_id + target_company_id + document_id + permission("read") + granted/revoked lifecycle + `DocumentShareEvent` append-only audit (`:127-175`), preconditioned on an active PlatformTenantRelationship (`document_sharing_service.py:58-80` has the canonical `has_active_relationship()` helper). **Not extended to Focus/VaultItem** (the V-2 "Vault Sharing generalization" remains unbuilt — confirmed). A **FocusShare** clone (+ `target_user_id` for person-scoping, + decision-bounded revoke) is the smallest access extension: ~1 migration + ~80-120 LOC service/guard + grant endpoint.

**Cross-tenant Space/dashboards: zero substrate.** Canon specs it (§7.2: shared Space + shared dashboards + decision Focuses); spaces live in `User.preferences` JSONB per-user — nothing cross-tenant. **Not demo-critical** (see Type-B call 5) — the Focus can open from the Sunnycrest order/notification.

**Joint calendar event: service-layer DONE, UI thin.** Models + the full propose/finalize/revoke service + per-tenant participant routing + API exposure exist (above). Remaining: the workflow/service call that creates the pairing for THIS job's delivery, the Focus-side rendering (a `calendar_summary`-family widget bound to the pairing), and whatever acceptance UI the demo needs (or auto-finalize between consenting demo tenants — see Type-B call 4).

**Isolation: enforced by construction; the read-path extension is structural.** `focus_session_service.py:30-31` ("cross-tenant reads impossible by construction"), `vault_service.py:175-193` shows the existing allowlist pattern (`shared_with_company_ids @> [requesting]`). A FocusShare check at the coordination-Focus read mirrors `vault_service.py:188` + the DocumentShare precondition — proven pattern, no auth-model invention.

---

## C. COMMS (survey — honest depth)

**Exists:** (1) outbound — `delivery_service.send_email_with_template()` (D-7, full audit row per send; note: agent found **no `send-communication` workflow node executor** — sends are service calls); (2) inbound — the R-6.x email primitive is REAL substrate: `email_threads` + `email_messages` + `EmailThreadLinkage` (cross-entity association — job/case linkable) + the 3-tier classification cascade + replay; **caveat: live inbound depends on provider OAuth sync configured — staging has none by design**; (3) in-platform messaging — **nothing** (visual canon only); (4) the dispatch DeliveryCard "chat" — `[not deep-dived; survey scope]`.

**Tier costing for the embedded thread:**

| Tier | What | Cost vs exists | Demo risk |
|---|---|---|---|
| (a) Real two-way in-platform channel | the §14.13 Messaging primitive | ~1,500+ LOC + async/presence infra — **net-new top-tier substrate** | Out of demo scope |
| (b) Email-send + captured replies | reuse delivery_service + email_threads/Linkage + cascade; new: thread↔job linkage + thread-widget rendering (~200 LOC) | small | **Inbound needs a configured provider** — fragile ON STAGE unless a demo account is wired |
| (c) Cross-tenant activity/notes stream on the job | new small `coordination_messages`-style table (or VaultItem notes) + the thread widget; both sides POST through their own tenant auth + the FocusShare grant (~100-150 LOC) | smallest | Fully self-contained; renders as the §14.15.2 thread chrome; no external dependency |

A hybrid is natural: **(c) as the demo-reliable backbone, with (b)'s outbound email send as a thread action** ("also email this to Hopkins") — and tier (a) stays the filed-forward Messaging primitive that later replaces the backbone.

## D. PARTICIPANTS + ACCESS (survey)

**The collapse is real.** The Hopkins director is an authenticated first-class user of tenant A; no guest auth, no magic links, no portal infra needed for the demo. The smallest path is **(a) a FocusShare grant row checked at the Focus read** (DocumentShare pattern + PTR-active precondition). Magic-link/external-guest infra exists only in portal/approval forms (PortalUser invite tokens, family-approval token view, proof-approval) — none of it is "join a Focus," and none of it is needed for September.

**Decision-bounded = revoke-on-completion, and the hook exists.** Canon's invitation flavors (§5.12) include decision-bounded auto-revoke. Implementation: FocusShare carries the job reference; the transfer-fulfilled / task-completed event (the existing `focus_closer` subscriber path) also revokes the grant. No expiry scheduler needed for the demo (event-driven revoke).

**Presence: nothing built** (no websockets, no polling presence, no participant model on focus_sessions). The demo's "participants" = a static catalog rendered from the grants + per-tenant section grouping per §14.15.5. Live cursors/presence are filed forward explicitly — canon itself treats presence as a distinct later channel.

---

## E. ASSEMBLY TEST — itemized

| Piece | Status | What it costs |
|---|---|---|
| Real order at Sunnycrest from the Hopkins case | **EXISTS** (`create_vault_order` wired into the Story step; LicenseeTransfer alt path) | 0 (demo-flow verification only) |
| Joint calendar event (bilateral pairing) | **EXISTS (service)** / thin UI | EXTEND: pairing creation for the delivery + Focus widget rendering + acceptance choreography (~200-400 LOC) |
| Focus composition runtime (tenant-side) | EXISTS (admin) / deferred tenant endpoint | EXTEND: wire the tenant-side resolve endpoint (the known follow-up; unblocks composed Focuses generally) |
| Coordination Focus | composition pattern EXISTS | NET-NEW (small): thin scoping core + `CoordinationJobContext` + FocusTemplate seed + 2 new widgets (thread, participants); reuse `vault_schedule` + calendar widget (~500-800 LOC FE total) |
| Cross-tenant Focus access | DocumentShare pattern EXISTS | NET-NEW (small): FocusShare table + read-guard + grant endpoint + revoke-on-completion (~150-300 LOC) |
| Embedded thread | email substrate EXISTS; in-platform channel does NOT | NET-NEW (small, tier c) ~100-150 LOC + optional tier-b outbound action; tier (a) filed forward |
| Decision-bounded participation | task-completion close hook EXISTS | EXTEND: grant-revoke on the same event (~30 LOC) |
| Presence / sub-Focuses / unified inbox / shared cross-tenant Space | NOT built | FILED FORWARD — none demo-critical |

**Total genuinely net-new ≈ 1,000–1,600 LOC across backend grants/choreography + 3 widgets + a thin core — composition-arc scale, not primitive-build scale.**

## F. TYPE-B CALLS (surfaced, not decided) + PHASING

1. **Core vs composition** — evidence says composition + thin scoping core (context-broadcast binding; no new binding framework). The alternative (a bespoke CoordinationCore like the kanban) buys nothing the widgets don't.
2. **Access model** — FocusShare (DocumentShare-pattern, person-scoped, decision-bounded revoke) vs a `focus_sharing_consent` column on PlatformTenantRelationship (tenant-wide, persistent). Lean FocusShare: per-instance, auditable, auto-revocable; the PTR stays the precondition.
3. **Comms tier** — (c) self-contained job thread as the demo backbone + (b) outbound email action, vs (b) end-to-end with a configured inbound account (real but stage-fragile), vs (a) filed forward. The on-stage reliability question decides this.
4. **Joint-event choreography for the demo** — full bilateral propose→partner-accepts UI vs auto-finalize between consenting demo tenants (the PTR consent + the service's `finalize_pairing` permit it). Auto-finalize is honest (consent is pre-established) and removes a demo step; the acceptance UI can still be shown if the narrative wants the Hopkins-side moment.
5. **The entry surface** — canon says shared cross-tenant Space + dashboards + Focuses (§7.2); the demo slice can open the Focus from the Sunnycrest order/notification (zero Space substrate needed) vs building a minimal shared-Space surface. Lean order-launched for September; the Space is the post-demo arc.
6. **The workflow nodes** — make `cross_tenant_order` REAL (an engine executor delegating to the existing services, ~50-100 LOC; the seeded funeral_cascade then truly "emits" the order) vs leave the Story-step service path as the demo trigger. Cheap either way; the executor also retires a known canvas-stub debt.
7. **Demo-critical vs filed-forward** — proposed line: IN = the single Job Focus, order-launched, 4 placements, FocusShare'd Hopkins director, joint delivery event, tier-c/b thread, auto-close+revoke on fulfillment. OUT (filed) = sub-Focuses, presence/cursors, the Messaging primitive, unified inbox, threshold-watch templates, magic-link externals, the shared cross-tenant Space, cross-tenant masking depth.

### Proposed phasing (de-risk-then-render; substrate proofs before UI)

- **JCF-1 — substrate proofs (backend, API-level tests, no UI):** FocusShare model + read-guard + grant/revoke (incl. revoke-on-task-completion) · the tenant-side composition resolve endpoint · the job-thread table + endpoints (tier c) · joint-event creation for a delivery (reusing pairing service) + the demo-flow integration test: Hopkins case → vault order at Sunnycrest → grant → pairing → revoke-on-fulfillment, all asserted end-to-end against seeds. *This phase IS the assembly test in code.*
- **JCF-2 — the Focus, single-tenant render:** thin coordination core + `CoordinationJobContext` + FocusTemplate seed + the 2 new widgets + reuse of schedule/calendar widgets; opened from the Sunnycrest order; §14.15 chrome (the visual canon is pre-written — design cost is low).
- **JCF-3 — the cross-tenant moment:** Hopkins-side open via the grant (attribution chrome, per-tenant participant sections, consent chips per §14.15.5) + the thread live across both sides + auto-close/auto-revoke demo choreography + Playwright cross-tenant gate (two-session test).
- **JCF-4 — demo polish + the optional workflow-node executor (call 6) + filed-forward log.**

---

**STOP.** Read-only; not committed (operator reviews; lands as a doc-only commit with the Phase 1 deliberation).
