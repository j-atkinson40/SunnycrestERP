# MoC Demo Artifacts (option-3) — Phase 0 Scoping (read-only)

**Date:** 2026-06-29 · **HEAD:** `93d3923` · **Read-only** — no build, no migration, no seed.
**Target:** the 4 artifacts the manufacturing MoC task table + cards reference by name but which don't exist — workflows "Invoice and Statement Run" + "Legacy Order"; focuses "Decision Triage" + "Legacy Generation". Build them REAL/demo-grade. The MoC seed names them by name+vertical, so the resolver AUTO-POPULATES the MoC cells the moment they exist (no MoC code change).
**Method:** witnessed `bridgeable_dev` introspection (seeded workflow node types, focus-instance tables, invoice/statement substrate) + two source-mapping Explore agents (focus substrate; workflow node vocabulary + step composition).

---

## HEADLINE — mostly CONFIG/COMPOSITION, with TWO honest "bigger-than-a-seed" flags

The platform already has the primitives. **None of the four needs net-new substrate at the primitive level** (no new Focus core to write, no new triage type, no new schema). But two items have a real implementation tail beyond seeding rows:

1. **`notify_via_contact_preference` is a genuine NET-NEW workflow node type** (Legacy Order step 5). `preferred_contact_method` exists on the model but **no workflow node consumes it** — only raw `send_email`/`send_document`. This is a small *feature*, not a seed. **Operator decides: build the node type (a real ~half-day step) or demo-substitute `send_document` (email) and flag preference-routing as a follow-up.**
2. **`TriageQueueCore` is a registered STUB** (renders placeholder rows, per its own comment). "Decision Triage" can *seed* as config over it with zero core work — but a *demo-grade* triage queue surfacing real items may need the stub fleshed out. **Flag: is the placeholder acceptable for the demo, or does the core need real rendering?**

Everything else is config (seed rows) + thin composition wiring (adapter wrappers, a headless dispatch entry). **No migrations anywhere** — these are artifact rows + code constants + workflow canvas JSON.

---

## PER-ARTIFACT VERDICT

### 1. "Decision Triage" (focus) — **CONFIG (seed rows); core is a stub (flag)**
- **Reuses:** the mature triage substrate (`app/services/triage/platform_defaults.py` — 4 shipped queue configs; `triage_sessions` 2227 rows witnessed) + the **already-registered** `TriageQueueCore` React component (mode `"triageQueue"` wired in `focus-registry.ts` / `mode-dispatcher.tsx`) + the "decision" Focus type (`focus-types.ts`, full configurable props).
- **Needs:** seed a `focus_cores` row (`triage-queue` → `TriageQueueCore`) + a `focus_templates` row (`decision-triage`, vertical_default, manufacturing). **No React core to build.**
- **FLAG (net-new tail):** `TriageQueueCore` is a *stub* — it renders placeholder rows today. Pure-config seeding makes the focus *exist* (and lights up the MoC), but a demo where the focus surfaces a *real* triage queue of pending decisions may require fleshing the stub. Operator call: placeholder-OK vs flesh-the-core (the latter is a small UI build, not config).

### 2. "Legacy Generation" (focus) — **CONFIG + thin headless wrapper (~100 lines), no new core**
- **Reuses:** the canonical "generation" Focus type with `operationalMode: ["interactive","headless"]` (`focus-types.ts`); the `generation_focus_instances` substrate (witnessed **2634 rows**, with a built-in `family_approval_status` flow); the **extensible** `HEADLESS_DISPATCH` registry (`generation_focus/headless_dispatch.py`); and the existing `legacy_compositor.py` proof-generation logic. The generation Focus UI already ships.
- **Needs:** (a) add `"legacy_proof_generation"` to the generation `template_type` discriminator (a code constant — NOT schema); (b) one `HEADLESS_DISPATCH` entry wrapping `legacy_compositor` (~100 lines); (c) seed `focus_cores` + `focus_templates` rows. **No new React core** (reuses the generation focus surface).
- **Verdict:** config + a thin service wrapper. Small.

### 3. "Invoice and Statement Run" (workflow) — **COMPOSITION (2 adapters + registry), no focus**
- **Reuses:** `draft_invoice_service.py` + `statement_generation_service.py` (both exist as functions); `invoices` + `statement_runs` tables (witnessed). The workflow node vocabulary (`call_service_method` + `_SERVICE_METHOD_REGISTRY`).
- **Needs:** 2 thin adapter wrappers (`invoice_generation_adapter.py`, `statement_generation_adapter.py`) + their `_SERVICE_METHOD_REGISTRY` entries, then seed the `workflow_template` (canvas_state composing the two `call_service_method` steps). **Pure backend — no focus needed for execution.**
- **Cross-ref note:** the MoC *task* "Funeral Home Billing" pairs this workflow with the Decision Triage *focus*, but that's the TASK's pairing, not a hard workflow dependency. **Design choice:** the workflow MAY add an approval step (`create_task`/`invoke_review_focus` → the Decision Triage queue) to match the pairing — if so it gains a soft dependency on #1. Recommend including it (consistent with the task + the real-world "review before send").

### 4. "Legacy Order" (workflow) — **COMPOSITION + the one net-new node type; depends on #1 + #2**
- **Flow → node-type map (witnessed):**
  | Step | Node type | Status |
  |---|---|---|
  | create legacy proof (headless) | `invoke_generation_focus` (focus_id=legacy_proof_generation) | **EXISTS** — node + handler wired; the legacy focus_id is registered by **#2's** headless dispatch entry |
  | add to triage for approval | `create_task` (stages into triage) + `invoke_review_focus` (→ approval gate / review queue) | **EXISTS** |
  | email to print shop | `send_email` / `send_document` (email channel) | **EXISTS** |
  | alert FH via preferred method | `notify_via_contact_preference` | **MISSING — NET-NEW node type** (the flagged gap) |
- **Reuses:** the rich node vocabulary (`invoke_generation_focus`, `invoke_review_focus`, `create_task`, `send_document`, `call_service_method`, …).
- **Needs:** seed the `workflow_template` (canvas_state composing the above); **#2's** headless dispatch entry (shared work — registering the legacy generator IS part of building Legacy Generation); and a decision on the notify gap (build the node type or substitute).
- **Depends on:** #2 (Legacy Generation focus — for `invoke_generation_focus`) AND #1 (Decision Triage — the queue the approval step stages into).

---

## THE DEPENDENCY DAG (build order)

```
  #1 Decision Triage (focus, config) ───┐
                                         ├──►  #4 Legacy Order (workflow) ──► [#4 needs notify decision]
  #2 Legacy Generation (focus,          │
     config + headless wrapper) ────────┘     (#4's invoke_generation_focus uses #2's
                                               headless registration; #4's approval step
                                               stages into #1's triage queue)

  #3 Invoke and Statement Run (workflow, composition) — INDEPENDENT
     (optionally adds an approval step → soft dep on #1)
```

**Order:** focuses #1 + #2 first (no interdeps — parallelizable). #3 is independent (any time). #4 last (hard-needs #1 + #2). Cross-ref confirmed: only #4 has hard deps; #3's link to #1 is an optional design choice.

---

## WHAT EXISTS TO REUSE (don't rebuild)
- **Triage:** `app/services/triage/` (4 queue configs, `triage_sessions` substrate, `TriageQueueCore` registered).
- **Generation focus:** the "generation" Focus type (interactive+headless), `generation_focus_instances` (2634 rows), `HEADLESS_DISPATCH` registry, `legacy_compositor.py`.
- **Workflow nodes:** `invoke_generation_focus`, `invoke_review_focus`, `create_task`, `wait_for_task_completion`, `route_on_task_outcome`, `send_email`, `send_document`, `generate_document`, `call_service_method` (+ `_SERVICE_METHOD_REGISTRY`).
- **Accounting:** `draft_invoice_service`, `statement_generation_service`, `invoices`/`statement_runs` tables.

---

## PHASED BUILD PLAN (assembly-test-first where there's real composition)

**Phase 3a — Decision Triage focus (config).** Seed `focus_cores` (triage-queue→TriageQueueCore) + `focus_templates` (decision-triage, manufacturing). **Witness:** the focus resolves; the MoC Focuses card + both task-table "Decision Triage" pills auto-populate (the resolver lights them up). **DECISION GATE:** placeholder core OK for demo, or flesh `TriageQueueCore` (small UI build — surface as a sub-phase 3a.1 if yes). No migration.

**Phase 3b — Legacy Generation focus (config + thin headless wrapper).** Add `legacy_proof_generation` to the generation discriminator + a `HEADLESS_DISPATCH` entry wrapping `legacy_compositor` + seed `focus_cores`/`focus_templates`. **Assembly test (real composition):** invoke the headless dispatch → it generates a legacy proof from a real sales_order → assert the output/instance, BEFORE wiring it into #4. **Witness:** the MoC "Legacy Generation" pill auto-populates. No migration.

**Phase 3c — Invoice and Statement Run workflow (composition).** 2 adapter wrappers + `_SERVICE_METHOD_REGISTRY` entries + seed the `workflow_template`. **Assembly test:** run the workflow end-to-end against a tenant with eligible orders → asserts invoices + a statement_run are produced (prove it RUNS before demo-ready — the cash-receipts/JCF discipline). **Witness:** the MoC Workflows card + "Funeral Home Billing" task workflow cell auto-populate. Optionally add the Decision-Triage approval step. No migration.

**Phase 3d — Legacy Order workflow (composition + the notify decision). Depends on 3a + 3b.** Seed the `workflow_template` composing `invoke_generation_focus`(legacy) → `create_task`/`invoke_review_focus`(Decision Triage) → `send_document`(print shop) → notify. **THE NOTIFY DECISION (operator):** build `notify_via_contact_preference` as a real node type (3d.1 — a small feature: read `preferred_contact_method`, dispatch SMS/email) OR demo-substitute `send_document`(email) + flag preference-routing as a follow-up. **Assembly test:** run end-to-end — generates proof → stages to triage → on approval emails the print shop → notifies the FH — proving the full chain runs. **Witness:** "New Legacy Order" task's workflow cell + BOTH focus pills (Legacy Generation + Decision Triage) auto-populate. No migration.

---

## FLAGS — stated plainly (per STOP discipline)
- **`notify_via_contact_preference` node type = NET-NEW (a feature, not a seed).** The one item that "turns a seed into a feature." Operator decides build-vs-substitute in 3d.
- **`TriageQueueCore` is a stub.** Config-seeds fine + lights up the MoC, but a real triage-queue render for the demo may need the stub fleshed (3a.1). Operator decides placeholder-OK.
- **Everything else is config + thin composition** — no new primitives, no migrations. The "demo-grade = real and works" bar is met by seeding artifacts + the two small wiring tasks (the Legacy Generation headless wrapper, the invoice/statement adapters), assembly-tested for the workflows.

**STOP.** Read-only; not committed. No build, migration, or seed performed — the plan is the deliverable. The only two decisions that gate scope (the notify node type; the triage core stub) are the operator's.

---

## KNOWN DESIGN NOTES / FRAGILITIES (surfaced during 3a/3b-seed — flag, not fix)

**1. The MoC is dynamic at the CELL, authored at the CARD.** Seeding an artifact auto-fills the task-table *relational cell* purely via the dynamic resolver (zero change — the pure keystone). But the *type-CARD* does NOT auto-gain it: the cards render the **authored `moc_pages` refs**, not all of a vertical's artifacts. So lighting up the card requires an authoring step (adding the artifact to the page's section refs — done in `seed_moc_manufacturing` for the two focuses). This is the design (table = derived, card = curated), not a bug — but hold it clearly: **"seed an artifact → everything lights up" is fully true for cells, semi-true for cards (cards need the ref-authoring).** Applies to 3c/3d: the Workflow *cells* will auto-fill, but the Workflows *card* needs the same page-ref authoring to show the new workflows.

**2. `_resolve_focus_ids` (and the workflow resolver) bind by `display_name`, `LIMIT 1` — name-fragile.** `seed_moc_manufacturing` resolves its focus/workflow refs by display_name (focuses: name-only; workflows: name, vertical-preferred). Once an artifact is seeded persistently, **anything else with the same display_name is ambiguous** — `LIMIT 1` picks one arbitrarily. The 2a auto-populate test hit exactly this (it created a second "Decision Triage") and was re-pointed to workflow-only to dodge it. Fine for the demo (controlled, unique names) — but a real coupling at scale: two verticals each with a "Decision Triage", or a tenant-override sharing a name, would collide. **Flag, don't fix** — the demo doesn't need it; tighten to (name, vertical, scope) binding when the catalog grows.
