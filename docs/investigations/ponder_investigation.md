# THE PONDER — Investigation / Scoping (read-only)

**Date:** 2026-07-15 · **HEAD:** `99f26d86` · **Read-only** — no code, no build.
**Scope:** (A) the Create-mod-style "ponder" on MoC artifacts — staged, calm, scrubbable animated walkthrough of how an automation works; (B) the escalation hook (exceptions → Decision Triage → morning summary), in scope because the flagship ponder beat must be TRUE. Accounting group first.
**Method:** every derivability claim below was checked against dev-DB rows and source at HEAD (mirror canvases queried, trigger configs read, run/step models inspected, the triage + briefing pipelines traced). Nothing asserted from memory.

---

## HEADLINE — three findings that reshape the plan (all in the good direction)

1. **The escalation hook's back half ALREADY EXISTS.** `WorkflowReviewItem` (r92) is an insertable, run-linked triage item consumed by `workflow_review_triage` — which is **exactly the queue the `decision-triage` Focus binds to** (TriageQueueCore 3a.1-B docstring: "`decision-triage` binds to `workflow_review_triage`"). And the morning briefing **already collects per-queue pending counts** (`briefings/data_sources.py::_collect_queue_summaries` — iterates every queue visible to the user, `queue_count` each, feeds the prompt). So "exceptions land in Decision Triage… and in your morning summary" needs only the FRONT half built: **recording exceptions at the chokepoints**. The transport, the landing, and the summary surface all exist.
2. **Business exceptions for the accounting group are ~80% true TODAY.** The 8b/8c/8d migrations already record step-level business exceptions as `AgentAnomaly` rows ("3 payments couldn't match") and route them to per-workflow triage queues (`cash_receipts_matching_triage`, `month_end_close_triage`, `ar_collections_triage`, `expense_categorization_triage`). What is genuinely missing: (a) **run-level failures go nowhere** (`workflow_engine._fail_run` sets status+error_message — loud-recorded, never routed); (b) non-agent workflows have **no business-exception container** at all. The hook is smaller than the dispatch feared — STOP condition (a) does NOT trip for the accounting group.
3. **Derivability is strong, with the caption problem half-solving itself.** The MoC mirror canvases carry **semantic node slugs** (`identify_customers`, `generate_statements`, `approval_gate`, `send_statements`) with **per-node human descriptions** ("Find charge-account customers with activity") — authored once at the mirror backfill. Node slugs are the stable caption key; the node's own description is the built-in derived-caption fallback. STOP condition (b) does not trip.

---

## A1 — THE DERIVABILITY MAP (the operator's decision input)

### What each beat class derives from, generally

| Beat class | Source of truth | Derivable now? |
|---|---|---|
| **Trigger** ("at month-end, 6am, tenant-local") | `workflows.trigger_type` + `trigger_config` (cron + timezone) — mechanical cron→prose rendering | **YES** — pure function, ~50 lines |
| **Steps** (names, order, branches) | The MoC mirror canvas (`workflow_templates.canvas_state` nodes+edges): semantic ids, types (`action`/`input`/`branch`), edge order, per-node `description`/`prompt` | **YES** for the 4 mirrored artifacts |
| **Step semantics** ("orders become invoices") | Node `config.description` (authored at mirror time) — richer than node type alone | **YES** (already-authored one-liners) |
| **Branches** | Edge `label` + `branch` node type; the accounting mirrors are linear except month-end's approval gate (an `input` node — "the run pauses for you") | **YES**; the ponder shows a pause-beat, not a fork, for these |
| **Downstream: triage queue** | Convention (adapter → queue_id), not FK — the workflow→queue link is **not queryable** | **NO — needs a tiny authored registry** (5 entries: workflow → queue_id) or a `queue_id` key on the task-catalog row |
| **Downstream: morning summary** | `_collect_queue_summaries` covers every visible queue | **YES** (statement: "counts appear in your morning briefing" is true for any queue-landing exception) |
| **Downstream: focuses/tasks** | `moc_task_catalog_focuses` join + task rows | **YES** |
| **Real-run garnish** | See below | **YES, cheap** |

### The real-run garnish (assessed: cheap, gold)

Two sources, both queryable per tenant:
- **Domain artifacts** (richest): `StatementRun.total_customers / flagged_count / total_amount`, `AgentJob` + unresolved `AgentAnomaly` counts per job type. "Last month: 12 customers, 2 flagged, $41,300" is one indexed query each.
- **`workflow_runs` + `workflow_run_steps`**: per-step `output_data` (the adapters return `{total_customers, statement_run_id, ...}`), `status`, `started_at` — good for "last ran {date}" and per-step results where domain artifacts don't exist.

Staleness handling: render the garnish beat only when a completed run exists in the last N days; otherwise the beat degrades honestly to "hasn't run for you yet — here's what will happen" (arguably the BETTER coaching frame for a new tenant). Cheapness: ~1 query per beat, same class as existing MoC resolution. **Recommend: in v1.**

### Per-artifact honesty table (Accounting group)

| Artifact | Trigger beat | Step beats (mirror) | Step captions | Exceptions beat | Garnish | Gaps |
|---|---|---|---|---|---|---|
| **Monthly Statement Run** (operator's example) | ✅ derives: "the 1st, 6:00 AM, tenant-local" (cron `0 6 1 * *` + `America/New_York`) | ✅ 4 nodes: identify_customers → generate_statements → approval_gate (pause) → send_statements | ✅ node descriptions exist ("Find charge-account customers with activity"…) | ⚠️ flags land as `CustomerStatement.flagged` + month-end queue; **run-failure routing = hook phase 1** | ✅ StatementRun counts | queue-link registry entry |
| **Month-End Close** | ✅ "when you run it" (manual) — an honest beat | ✅ **10 nodes** incl. approval gate + 6 verification steps with descriptions — the richest story | ✅ | ✅ anomalies → `month_end_close_triage` TODAY | ✅ AgentJob/anomaly counts | none beyond hook phase 1 |
| **AR Collections** | ✅ "every night, 11 PM" | ✅ 5 nodes | ✅ | ✅ per-customer items → `ar_collections_triage` | ✅ | queue-link registry |
| **Expense Categorization** | ✅ "every 15 minutes" | ✅ 3 nodes | ✅ | ✅ per-line review → queue | ✅ | queue-link registry |
| **Cash Receipts Matching** | ✅ "nightly, 11:30 PM" | ❌ **NO MIRROR** (audit B-1 — excluded from the backfill `_CORE` list) | ❌ | ✅ anomalies → queue TODAY | ✅ | **prerequisite: add to `_CORE`, one line, self-deploys** |

**Bottom line for the operator's derived-vs-authored call:** the derived story is NOT thin — trigger, steps, step one-liners, pause-beats, downstream summary, and last-run numbers all derive. The authored layer is (1) an optional narrative polish pass per beat (the mirror descriptions are serviceable but terse), (2) the 5-entry workflow→queue registry, (3) nothing structural. STOP condition (c) does not trip. **Recommendation: derived-first with authored overrides** — ship v1 fully derived, add caption overrides where the operator wants warmer language.

## A2 — CAPTION KEYING (the ref-decay lesson, applied)

- **Key: `(workflow_type lineage, node_id)`** — the mirror node ids are semantic slugs, not row-UUIDs, and survive template version bumps (versioning deactivates+recreates the ROW; the canvas JSON's node ids persist verbatim unless an author renames a node). This is the C-2.1.2 slug-is-identity pattern already canonical for focus lineages.
- **Orphan handling (a node is renamed/deleted under an authored caption):** fall back to the node's own `config.description` — the derived caption IS the fallback, so orphaning degrades to "less warm," never to stale-teaching or blank. Log the orphaned key (the V-1 orphan-tolerant resolution pattern). Do NOT block workflow edits on caption existence.
- **Offered-updates pattern:** overkill for v1 (captions are platform-authored, not tenant-forked). Revisit only if tenants author captions on forked workflows.
- **Where authored:** a `ponder` JSONB block on the task-catalog row (per-beat overrides keyed by node id + the queue-link registry entry) — edited in the existing MoC task panel. No new table.

## A3 — PRESENTATION

- **Shape:** full-screen Focus-shell overlay (the platform already has the summon/dismiss vocabulary; Esc-to-dismiss; the ponder is a Focus-like *moment*, not a page). In-place expansion rejected: the calm, staged quality needs the room and the dimmed backdrop.
- **Create qualities to preserve:** SLOW (beats hold ~3-5s; `duration-considered` territory), staged (one idea per beat, minimal text — the caption + one visual), **scrubbable** (a beat timeline/dots rail; click any beat; arrow keys), replayable, and **interruptible without penalty** (Esc anywhere).
- **Motion substrate:** the DL two-curve system natively fits — entrances `ease-settle` ("things *arrive*"), exits `ease-gentle` ("recede quietly"), five named durations. Implementation is staged CSS transitions + SVG connector-line draw (stroke-dashoffset) in React — **no new animation library**; a small `usePonderTimeline` hook (beat index + autoplay timer + scrub) is the only net-new motion infrastructure. This must NOT be a baked video: it renders from live derivation (per-tenant garnish numbers, current steps), which is the whole point.
- **Affordance:** a "How this works" affordance on the task ROW (hover-reveal play glyph, the peek-eye pattern) + inside the task panel. **Recommend against the family icon** as the trigger — icons are lineage identity (r122), and overloading them teaches users icons are buttons everywhere.
- **Branch rendering:** for `input`/approval nodes, the ponder pauses its own timeline on the beat ("…and here, it waits for you") — the medium mirroring the message. True conditional forks (none in the accounting mirrors) render as a split beat with both labels; defer polish until an artifact needs it.

## B — THE ESCALATION HOOK (decomposed)

### B1 — What's an exception (options for the operator; don't decide here)

| Option | What it means | State today |
|---|---|---|
| **Run-level failure** | `WorkflowRun.status='failed'` | Exists, loud-recorded (`_fail_run`, engine:1726), routed NOWHERE — the gap |
| **Step-level business exception** | "3 orders couldn't invoice — missing pricing" | **EXISTS for the accounting group** as `AgentAnomaly` → per-workflow queues; NET-NEW for generic (non-agent) workflows — would need an exception container on `workflow_run_steps` or a generalized anomaly row |
| Recommendation | Phase 1 = run-level (universal, small); business-level rides the EXISTING anomaly pipeline for accounting; generic-workflow business exceptions deferred until a non-agent workflow needs them | |

### B2 — Transport: direct insert + domain event (both, cheaply)

At the `_fail_run` chokepoint (one function, engine:1725): (1) **insert a `WorkflowReviewItem`** in the same transaction (kind: escalation — needs a `kind` discriminator or a distinct decision vocabulary; the model's CHECK allows NULL decision, item shape fits), and (2) **`emit_event(run.failed)`** through the T-2.2 outbox (same-transaction, loud-by-design) for observability + future event-triggers. The matcher-as-transport alternative (event → matcher → workflow-that-inserts) is rejected: the matcher fires workflows, not arbitrary actions — routing through it adds a moving part to reach a table we can insert into directly at the chokepoint. The outbox EVENT still rides along for free, so nothing is lost.

### B3 — Triage landing: exists

`workflow_review_triage` is query-backed by `WorkflowReviewItem.decision IS NULL` (engine:1378). An escalation item needs: the insert at B2, a `kind`/label so reviewers distinguish "review this proof" from "this run failed," and the queue's display component tolerating escalation items (small frontend touch in the Phase 5 workspace). Per-workflow BUSINESS exceptions keep landing in their per-workflow queues (correct — they're domain decisions); run FAILURES land in Decision Triage (correct — they're operational). The ponder narrates both honestly: "exceptions land in your triage queues; failures land in Decision Triage."

### B4 — Morning summary: exists (verify visibility, don't build)

`_collect_queue_summaries` already surfaces every visible queue's pending count into the morning briefing prompt; briefings deliver per-user on the Phase 6 sweep. The only work: confirm `workflow_review_triage` is visible to the target roles (queue permission gate) and that the count includes escalation items (it will — same query). **The "smallest honest version" is zero new surface.** A richer "since you were last here" digest on the map is a REAL but separate idea — do not couple it to the hook; park it as a post-ponder candidate (own small arc, ~1-2 sessions, only if the briefing proves insufficient).

### B5 — Phasing (both pieces interleaved)

| Phase | Content | Size | Ships value alone? |
|---|---|---|---|
| **H1** | `_fail_run` → WorkflowReviewItem (+`kind`) + `run.failed` outbox event + queue display tolerance + briefing visibility check | **1 session** | YES — failed runs become visible work items; the flagship beat becomes TRUE |
| **P0** | Prerequisite riders: Cash Receipts mirror (one line in `_CORE`), the 5-entry workflow→queue registry | **hours** (rides H1) | — |
| **P1** | Ponder v1: beat compiler (trigger/steps/downstream/garnish from the derivability map), Focus-shell overlay, timeline + scrub, DL motion, task-row affordance — accounting group, derived captions | **2-3 sessions** | YES — the demo moment |
| **P2** | Authored caption overrides in the task panel (keyed per A2) + narrative polish pass on the five artifacts | **1 session** | polish |
| **P3 (optional, decoupled)** | "Since you were last here" map digest — only if the briefing beat proves insufficient in rehearsal | 1-2 sessions | separate call |

**Migrations flagged:** H1 likely needs one small migration (a `kind`/`item_type` column on `workflow_review_items` — or none, if the existing shape + a payload key suffices; decide at build). P0-P2: none.

**Total to the operator's full vision (H1+P0+P1+P2): ~4-5 sessions**, with the flagship beat true after the FIRST.

---

## HONEST CAVEATS

- **Mirror inertness:** the ponder narrates the MIRROR canvas; runs execute through the runtime workflow/agents. The mirrors are inert snapshots (T-2.0 provenance) — if runtime behavior changes and the mirror isn't updated, the ponder teaches the old story. This is the already-tracked §6 mirror-dedupe coupling, now with a user-facing consequence; the mirror pass should be re-run when an accounting adapter changes shape.
- **Month-end's manual trigger** makes its trigger beat different in kind ("when you run it") — fine, but the beat compiler needs the manual branch from day one.
- **The queue-link registry is authored** (5 entries) — the one place the "fully derived" story needs a human-maintained map. Keep it on the task-catalog row so it's visible where it's edited.

**STOP.** Read-only; the map is the deliverable. None of the three reshape-conditions tripped: business exceptions are NOT net-new for accounting (they exist as anomalies), caption keying HAS a stable identity (semantic node slugs with derived-description fallback), and the derivable story is RICH (the operator's Statement Run example derives end-to-end except the queue-link registry entry). The operator's decisions from here: derived-vs-authored weighting (recommend derived-first with overrides), the exception-semantics option (recommend run-level phase 1, ride the existing anomaly pipeline for business-level), and whether P3 exists at all.
