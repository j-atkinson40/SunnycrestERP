# MoC Task Triggers — Phase 0 Scoping Investigation (read-only)

**HEAD:** `8c88d94` (the MoC Task Editing 2b push) · **Date:** 2026-06-30 · **Read-only** — no code, no migration, no seed, no canon, no dispatch. The plan is the deliverable.

**Operator intent (scoped-against, not redesigned):** MoC tasks should carry **TRIGGERS** — *scheduled* (time-of-day + recurrence), *event-driven* (invoked by a domain event, e.g. "new order of type legacy"), plus implicit *manual*. **DESCRIPTIVE FIRST:** triggers are metadata now — legible + editable on the MoC (the 2b editing surface) — they do **NOT fire yet**. The execution path (the canvas↔runtime bridge) is a **later unified arc** that lights up triggers + the 18 workflow mirrors + AI-drafts at once. Multiple heterogeneous triggers per task (a collection, like the focus join). Event condition **FILTERED now** (event + one field/operator/value) but **MODELED to expand to RICH** (multiple/nested conditions) later.

**Method:** three parallel witnessed sweeps of `backend/` (event substrate, scheduler substrate, order-type + lifecycle fields) + first-hand reads of the scheduler dispatch, the workflow trigger model, and the MoC catalog/vocabulary models. Every substrate claim is grounded in cited code.

---

## TL;DR — the two verdicts that shape the arc

1. **NO general domain-event bus exists (witnessed).** Domain mutations (order created, invoice sent, case opened) do **not** emit events. `trigger_type="event"` on the workflows table is **dead code** — the scheduler dispatches only `time_of_day` / `time_after_event` / `scheduled`; nothing queries `trigger_type == "event"`. CLAUDE.md already states this plainly (Phase 8c: "The event dispatch system doesn't exist today — no event subscription registry, no publish-event hooks"). **Consequence:** the descriptive event-trigger is a **curated picklist now, real hook later**. The operator should hear this clearly: an event-trigger authored today is legible metadata pointing at a *named* event; the emission that makes it fire is part of the deferred execution-bridge arc. This is the bigger of the two findings.

2. **Frequency vs schedule-trigger is a genuine model overlap (surfaced, not defaulted).** The 2a `frequency` field ("End of Month", "On demand") and a schedule-trigger both express "when in time." The catalog model's own docstring says frequency is a free-form label because *"workflow templates carry no trigger columns to derive frequency from."* A schedule-trigger IS that missing structured spec. **Recommendation (a real call, below):** the schedule-trigger becomes the precise spec; **Frequency becomes a derived/display label** — but descriptively-now the two **coexist**, with the derivation a small follow-up inside this arc.

Everything else (schedule vocabulary, order-type filterability, the trigger schema) is clean and buildable descriptively without the execution bridge.

---

## Q1 — EVENT SUBSTRATE — verdict: **NO domain-event bus; curated vocabulary required**

### The witnessed verdict
No event bus / dispatcher / publish-subscribe for arbitrary domain mutations exists. Grepping `publish_event` / `emit` / `EventBus` / `domain_event` / `fire_event` surfaces only **scoped** mechanisms, never a general emitter.

**`trigger_type="event"` is stubbed dead code:**
- `default_workflows.py` seeds 6 workflows with `trigger_type="event"` (e.g. `wf_sys_legacy_print_proof` → `{"event": "legacy_order.submitted"}`).
- `workflow_scheduler.check_time_based_workflows()` (`workflow_scheduler.py:292–359`) dispatches **only** `time_of_day`, `time_after_event`, `scheduled`. The pre-filter query (`:264–265`) is `.in_(["time_of_day","time_after_event","scheduled"])` — `"event"` is excluded. **No code path checks `Workflow.trigger_type == "event"`.**
- CLAUDE.md confirms (Phase 8c): expense_categorization's seed was *changed away* from `trigger_type="event"` + `{"event":"expense.created"}` to `scheduled` cron `*/15` precisely because event dispatch doesn't exist.

### The three scoped event-LIKE mechanisms (what DOES exist — and why none is a general bus)
| Mechanism | File | Scope | Could a task-trigger hook it? |
|---|---|---|---|
| **Task-lifecycle subscriber registry** | `app/services/tasks/subscribers/registry.py` (7 event types × 6 subscribers; `emit_event` :108) | ONLY task state transitions (`task_created`, `task_completed`, …) | No — fires on *task* lifecycle, not domain mutations. (Note: `workflow_resumer` here IS the task→workflow resume hook — but scoped to task completion.) |
| **Intake classification cascade** | `app/services/classification/dispatch.py` (`classify_and_fire` / `_form` / `_file`) | ONLY inbound email/form/file → fires a workflow via `start_run(trigger_source="…_classification")` | No — only inbound-message-triggered, not "order created". This is the closest thing to a real event hook and it is intake-only (R-6.2a). |
| **Time-based workflow scheduler** | `app/services/workflow_scheduler.py` | Timer only (below, Q2) | This is the *schedule*-trigger's binding, not an event source. |
| **Onboarding hooks** | `app/services/onboarding_hooks.py` | Fire-and-forget direct calls from mutation sites (checklist progress only) | No — hardcoded call sites, no registry, checklist-scoped. |

**Note the shape:** `time_after_event` is *named* like an event but is actually a daily **poll-for-records** — `_matches_time_after_event` (`workflow_scheduler.py:109`) runs a SQL query for `funeral_cases` whose `service_date + offset_days == today`, hardcoded to a one-entry `table_map`. It is not an emission hook; it's a scheduled query. This reinforces: the platform has **no push-based domain events**, only pull-based polling.

### The dead-seed naming precedent (align to it)
The stubbed event workflows already carry event-name strings — a naming convention to inherit rather than invent:
`order.created` · `funeral_case.created` · `funeral_case.scribe_complete` · `legacy_order.submitted` · `legacy_proof.approved` · `scribe.audio_uploaded` (all in `default_workflows.py`, all inert). The curated vocabulary below extends this `entity.event` dotted convention.

### Proposed CURATED EVENT VOCABULARY (from real lifecycle columns)
Because there's no bus, the event-trigger dropdown is a **defined menu**, grounded in real status columns (witnessed), each carrying the fields a condition can filter on. Starter set (manufacturing-relevant first; the full menu is cross-vertical):

| Event key | Entity / table | Real basis (status column → value) | Filterable fields (for the condition) |
|---|---|---|---|
| `order.created` | `sales_orders` | row insert | **`order_type` ∈ {funeral, retail, wholesale}** (`sales_order.py:82`), `total`, `customer_id`, `cemetery_id`, `is_spring_burial` |
| `order.completed` | `sales_orders` | `status → completed` (`:41`) | `order_type`, `total` |
| `invoice.sent` | `invoices` | `status → sent` (`invoice.py:38`) | `total`, `customer_id`, `due_date` |
| `invoice.paid` | `invoices` | `status → paid` | `total`, `customer_id` |
| `delivery.completed` | `deliveries` | `status → completed` (`delivery.py:66`) | `driver_id`, `scheduled_date` |
| `case.opened` | `fh_cases` / `funeral_cases` | `status → first_call` (`fh_case.py:28`) | `vertical`, assigned director |
| `urn_order.proof_pending` | `urn_orders` | `status → proof_pending` (`urn_order.py:49`) | `engraving` fields |
| `certificate.approved` | `social_service_certificates` | `status → approved` (`social_service_certificate.py:39`) | `customer_id` |

**Storage recommendation:** a small **seeded, editable curated-event catalog** (mirrors the 2a vocabulary-store philosophy — configuration-over-code, add-a-row-not-code), because each event carries *structured* metadata (entity + the filterable-field list the condition builder needs), which a flat value-store can't hold. Detail in the schema section. A code-constant is the cheaper alternative if the operator prefers zero new tables for the event menu — flag as a sub-decision.

### The canonical example — "new order of type legacy"
- **The filterable field is real:** `sales_orders.order_type` = `'funeral' | 'retail' | 'wholesale'` (direct column, `sales_order.py:82`, used by end-of-day invoice batch). So `order.created WHERE order_type == 'funeral'` is a **real, buildable** descriptive event-trigger.
- **Nuance to surface:** **"legacy" is NOT an `order_type` value.** "Legacy" is a *product-line / personalization* concept — `products.product_line` (`product.py:49`, e.g. "Monticello"), `products.personalization_tier`, and `sales_orders.legacy_photo_pending` (a personalization flag). So "new order of type legacy" maps to one of: (a) the simple/real path — `order.created WHERE order_type == 'funeral'`; or (b) the "legacy" path — a condition on a *line's product's* `product_line`/`personalization_tier`, which requires the condition to traverse order→lines→product (a nested/relational field, not a flat order column). **Recommend for the descriptive phase:** model conditions against the **direct `sales_orders` columns** (order_type/total/status/customer) first; treat product-line/personalization conditions as a *known future field-path* the rich-condition expansion covers (dotted paths like `line.product.product_line`). This keeps the first condition vocabulary flat + real and defers relational-traversal conditions to the rich phase — no schema cost either way (see the conditions-list model).

---

## Q2 — SCHEDULER SUBSTRATE — verdict: **rich; a schedule-trigger's execution home already exists**

### The map
- **APScheduler** (`app/scheduler.py`, `BackgroundScheduler(timezone="America/New_York")`) runs ~20 registered jobs — daily/nightly/weekly/monthly `CronTrigger(...)` + several **15-min interval sweeps** (`minute="*/15"`).
- **The workflow schedule dispatch** is one of those sweeps: `_run_workflow_time_check()` (`scheduler.py:681`) → `workflow_scheduler.check_time_based_workflows()` every 15 min. For each `(workflow, tenant)` it checks the trigger and, on match, calls `workflow_engine.start_run(trigger_source="schedule", trigger_context={…})`.
- **Per-user sweep template** (Phase 6 briefings, `briefings/scheduler_integration.py`): a single 15-min global cron sweep queries users by a per-user time preference, resolves tenant-local time, idempotent via a DB unique-per-day. **This is the exact pattern a per-task schedule-trigger would follow** when it eventually fires — no per-task APScheduler registration.

### The concrete schedule vocabulary (what the platform can express TODAY)
This is the descriptive schedule-trigger's real vocabulary — model to it so the future bridge maps 1:1:

| Spec | `trigger_type` | `trigger_config` shape (witnessed) | Example |
|---|---|---|---|
| Time-of-day on weekdays | `time_of_day` | `{"time":"HH:MM","days":["mon",…]}` (3-letter days; 15-min-coarse) | `{"time":"23:30","days":["mon",…,"sun"]}` |
| Cron (weekly/monthly/arbitrary) | `scheduled` | `{"cron":"m h dom mon dow","timezone":"America/New_York"}` (POSIX 5-field via APScheduler `CronTrigger.from_crontab`; tenant-tz-aware) | `{"cron":"0 6 1 * *"}` (1st of month, 6am) |
| N-days-after a record's date | `time_after_event` | `{"record_type":"funeral_case","field":"service_date","offset_days":7}` (poll, hardcoded table_map) | aftercare 7-day |
| Manual | `manual` | `{}` / null | — |

**Recurrence expressible today:** time-of-day + day-of-week list · daily · weekly · monthly · arbitrary cron · N-days-after-a-date-field. **NOT expressible:** dynamic end-of-month (`L`), relative "next Tuesday"/"in 3 days". (Note the two known latent bugs: `time_of_day` fires at **UTC** wall-clock not tenant-local — Phase 8b.5; `scheduled` cron is the tenant-tz-correct path.)

### What a schedule-trigger BINDS to (execution — deferred)
When triggers eventually fire, a schedule-trigger's execution home is the existing `check_time_based_workflows()` sweep (or a sibling task-sweep following the briefings per-user pattern), reusing the established `trigger_context.intended_fire` idempotency. **Descriptively-now, none of this is touched** — the schedule-trigger is metadata whose `config` mirrors these exact shapes so the bridge is a wiring job, not a re-model.

---

## Q3 — THE FILTERABLE TYPE — verdict: **`sales_orders.order_type` is real + filterable**

Confirmed (Q1 table above): `order_type` is a direct `String(50)` column with a documented 3-value set. The canonical event-trigger is **real, not hypothetical** — with the "legacy" nuance surfaced (product-line/personalization, not order_type). The realistically-filterable direct order fields for the first (flat) condition vocabulary: `order_type`, `status`, `total`/`subtotal`, `customer_id`, `cemetery_id`, `scheduled_date`, `is_spring_burial`, `service_location`. Relational fields (`line.product.product_line`, `customer.customer_type`) are the rich-phase expansion.

---

## THE TRIGGER MODEL (descriptive, structured-for-the-future)

### `moc_task_trigger` — the trigger collection (mirrors the focus join)
One row per trigger; a task has 0..N, heterogeneous by kind — exactly like `moc_task_catalog_focuses` is a 0..N collection.

| col | type | note |
|---|---|---|
| `id` | VARCHAR(36) PK | uuid4 |
| `task_catalog_id` | VARCHAR(36) FK → `moc_task_catalog.id` **ON DELETE CASCADE** | the collection binding (mirrors the focus join's cascade) |
| `kind` | VARCHAR(16) | **CHECK IN ('schedule','event','manual')** — typed + queryable (like `moc_task_vocabulary.kind`) |
| `config` | JSONB | kind-specific shape (below). JSONB per the **workflows.trigger_config precedent** — heterogeneous kinds stay clean; the condition-as-list lives here so filtered→rich is data, not migration |
| `label` | VARCHAR(200) NULL | optional human summary override; else derived (e.g. "Monthly · 1st 6am", "On new funeral order") |
| `display_order` | INT | chip order |
| `is_active` | BOOL | soft-disable a trigger without deleting |
| `created_by`/`updated_by` | VARCHAR(36) NULL | **FK-less** (cross-realm actor, mirrors moc_task_catalog) |
| `created_at`/`updated_at` | timestamptz | |

**`config` per kind (the shapes — mirror the real workflow trigger_config so the future bridge maps 1:1):**

- **schedule:** one of the witnessed shapes, tagged by `spec_kind`:
  ```
  { "spec_kind": "time_of_day", "time": "HH:MM", "days": ["mon",…], "timezone": "tenant" }
  { "spec_kind": "cron",        "cron": "0 6 1 * *", "timezone": "America/New_York" }
  { "spec_kind": "after_record","record_type": "funeral_case", "field": "service_date", "offset_days": 7 }
  ```
- **event:** the event key (from the curated catalog) + a **conditions LIST** — the load-bearing expansion shape:
  ```
  { "event": "order.created",
    "conditions": [ { "field": "order_type", "operator": "eq", "value": "funeral" } ] }
  ```
  **CRITICAL — the conditions shape is a list from day one, holding one element.** Filtered→rich later is *adding array elements* (and, if nesting is wanted, a `logic: "and"|"or"` sibling + nested `conditions`), **NOT a schema migration.** The condition is a structured `{field, operator, value}` object — **never a flat string.** Operator vocabulary (starter): `eq`/`neq`/`in`/`gt`/`lt`/`gte`/`lte`/`contains`. `field` is a key from the event's catalog `filterable_fields` (flat now; dotted relational paths like `line.product.product_line` in the rich phase — same list shape, no migration).
- **manual:** `{}`. See the manual note below.

**One migration** (`rNNN_moc_task_trigger`) creates this table. (Optionally the same migration creates the curated-event catalog below — one migration total for the descriptive arc.)

### `moc_trigger_event_catalog` — the curated event menu (recommended; the "no bus" consequence)
Because events aren't emitted, the event-trigger picks from a **seeded, editable** catalog carrying each event's filterable-field metadata:

| col | type | note |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `event_key` | VARCHAR(120) | dotted `entity.event` (aligns with the dead-seed precedent) |
| `label` | VARCHAR(200) | "Order created" |
| `entity` | VARCHAR(64) | "sales_order" |
| `scope`/`vertical`/`tenant_id` | three-tier | mirrors `moc_task_vocabulary` (platform events + vertical events) |
| `filterable_fields` | JSONB | `[{field, type:"enum|number|string|date", values?:[…]}]` — feeds the condition builder |
| `is_active` / `display_order` | | soft-delete + order (vocabulary-store discipline) |

**Alternative (flag as sub-decision):** skip the table, ship the event menu as a **code constant** (a `TRIGGER_EVENT_CATALOG` list) — cheaper (no migration for the menu), but not operator-editable and not three-tier. **Recommend the table** for consistency with the 2a vocabulary-store philosophy (add-a-row-not-code) and because the filterable-field metadata benefits from being data. Either way, the events **do not fire** this phase — the catalog is honest metadata: *"the menu the execution bridge will wire."*

### Why JSONB config, not fully-normalized condition rows
A `moc_task_trigger_conditions` child table (one row per condition) would be *more* normalized but is **over-built for one condition** and fights the "expand without migration" goal less cleanly than a JSONB list. The platform precedent is JSONB (`workflows.trigger_config`, `focus_compositions.placements`, canvas_state). **Recommend JSONB `config` with the structured `conditions: [...]` array** — expand-ready, precedent-aligned, and the `{field,operator,value}` objects satisfy "structured, not a flat string." (If the rich phase ever needs to *query across* conditions, a child table can be introduced then — but that's a rich-phase call, not a descriptive-phase cost.)

### Manual kind — implicit + explicit
A task with **zero fire-able triggers is implicitly manual** (it's run by hand from the command bar / the task's focus). Recommend: **allow an explicit `manual` row** for legibility (a "Manual" chip that says "this is intentionally hand-run"), but the UI should also treat *absence of triggers* as manual-only (never render a task as "un-runnable"). Don't force a manual row; offer it.

---

## THE FREQUENCY RECONCILIATION (a decision — with a recommendation)

**The overlap:** `moc_task_catalog.frequency` (2a, a `moc_task_vocabulary` value like "End of Month" / "On demand") and a **schedule-trigger** both answer "when." Two sources of truth for timing is the smell.

**The options:**
- **(a) Supersede — Frequency becomes derived.** The schedule-trigger is the precise spec; `frequency` becomes a **display label auto-summarized from the primary schedule-trigger** (`humanize(schedule_config) → "Monthly · 1st"`), free-text only when no schedule-trigger exists. One source of truth for timing.
- **(b) Coexist — Frequency stays the human label, trigger is the spec.** Both persist; Frequency is the editorial/marketing phrase, the trigger is the machine spec. Risk: they can disagree.

**Recommendation: (a) with a phased landing.** The schedule-trigger is the structured truth; Frequency should become **derived-from-it**. But because triggers are **descriptive-only this arc**, land it in two steps *inside* this arc:
1. **Ship triggers alongside the existing 2a Frequency field (coexist) first** — no destabilization of 2a; the Frequency column keeps working.
2. **Add a small `humanize(schedule_trigger) → label` derivation** so that when a task has a schedule-trigger, its Frequency cell **shows the derived summary** (and the raw `frequency` string becomes a fallback for trigger-less tasks). This is a UI/service nicety, not a schema change — `frequency` stays a column; it's just *populated/overridden by* the trigger's summary when one exists.

**Net:** the 2a `frequency` vocabulary work is **not wasted** — it remains the label vocabulary + the fallback for tasks with no schedule-trigger. The schedule-trigger supersedes it *as the source of truth* without a destructive migration. **Surface this as the operator's call** (supersede-derived vs coexist-independent); the recommendation is supersede-via-derivation, staged.

---

## RENDERING / EDITING ON THE MoC (recommend, don't over-build)

Triggers are a **new editable facet** on the 2b task surface. Recommend:
- **Primary editing → the TaskEditorPanel** (the 2b SlideOver) gains a **"Triggers" section**: a list of trigger chips + "Add trigger" → pick `kind` → a small kind-specific editor:
  - *schedule* → a spec builder (spec_kind toggle → time+days | cron field | after-record fields). Keep it to the three real shapes.
  - *event* → event picker (from the curated catalog) → **one** condition row (field dropdown from the event's `filterable_fields` → operator → value), with a disabled/ghosted "+ add condition" affordance that visibly signals the rich-phase expansion **without building it**.
  - *manual* → no config (just adds the chip).
- **Table display → a compact "Triggers" cell or an expand-row** rendering trigger chips (schedule = clock glyph + summary; event = bolt glyph + "on order.created"; manual = hand glyph). Chips mirror the focus-pill treatment (the 2b visual language). **Recommend a Triggers cell showing chips** (consistent with Workflow/Focus cells) over a full expand-row — less new layout, same legibility. The panel is where the actual editing happens (triggers are as relational as focuses — awkward fully-inline).
- **Reuse the 2b silent-swallow guard:** a rejected trigger write surfaces the server reason + reverts.

**Do NOT** build inline schedule/condition builders in the table cells (over-build); the panel owns construction, the cells display.

---

## THE PHASED PLAN

### Phase T-1 — the DESCRIPTIVE trigger model (THIS arc; assembly-test-first)
**Migration (ONE):** `rNNN_moc_task_trigger` — the `moc_task_trigger` collection table (+ optionally `moc_trigger_event_catalog` in the same migration). The arc's only schema change.
**Seed:** the curated event catalog (from the Q1 vocabulary, grounded in real columns) + optionally example triggers on the two demo tasks (a schedule on "Funeral Home Billing", an `order.created`+`order_type==funeral` event on "New Legacy Order") so the surface renders non-empty. Idempotent, platform-canonical (the 2a seed discipline).
**Service layer** (realm-agnostic, `app/services/maps_of_content/`): trigger CRUD (create/patch/delete, mirroring 2a's `task_catalog` CRUD) + a validator (`kind` ∈ set; schedule `spec_kind` ∈ set with the right fields; event `event` resolves in the catalog + each condition `{field,operator,value}` has `field` ∈ the event's `filterable_fields` and `operator` ∈ the operator set) + the `humanize(schedule_config)` summarizer (the Frequency derivation).
**ASSEMBLY TEST FIRST (JCF-1 / the 2a discipline — before any UI):** a task round-trips a **schedule** trigger + an **event** trigger (with one structured condition) + a **manual** trigger through the real models; the event trigger's `conditions` persists as a **list of one** `{field,operator,value}`; the event resolves against the curated catalog; a bad condition field/operator is **rejected** (the referential guard, like 2a's `_validate_task_refs`); `humanize(schedule)` yields a legible label. This proves the structured-for-expansion shape **before rendering** — the part most likely to be got wrong.
**Write API** (`/api/platform/admin/moc/*`, platform-auth): `POST/PATCH/DELETE /tasks/{id}/triggers` + `GET /trigger-events` (the curated catalog for the picker) — mirrors the 2a task/vocabulary endpoints exactly.
**Editing UI (2b extension):** the panel Triggers section + the table Triggers cell + chips (above). Visual witness required (the 2b admin-tree witness path): author a schedule + an event trigger on a real task; witness the chips + the derived Frequency label; witness the condition builder reading real `order_type` values; a rejected condition surfaces + reverts.
**Frequency reconciliation:** ship coexist + the derivation (Frequency cell shows the schedule summary when a schedule-trigger exists; raw `frequency` is the fallback). No destructive change to 2a.
**Explicitly NOT in T-1:** any firing. The triggers are inert legible metadata.

### Phase T-2+ — the EXECUTION BRIDGE (DEFERRED — the unified arc, out of scope here)
The single later arc that makes triggers *fire*, alongside the workflow-mirror execution + AI-drafts:
- **Event emission substrate** — the missing bus: emit `entity.event` at real mutation sites (order create, invoice send, case open, …) + an event-subscription registry + an event dispatch that matches a task's event-triggers (evaluating the `conditions` list against the emitted payload) and runs the task's workflow. This is the CLAUDE.md-flagged "future event-infrastructure arc."
- **Schedule execution** — wire schedule-triggers into a task-sweep (the briefings per-user pattern) reusing `check_time_based_workflows`-style dispatch + `intended_fire` idempotency.
- **The canvas↔runtime bridge** — the workflow-mirror inert-snapshot problem (moc_workflow_backfill_investigation §3): the mirrors don't execute; the same bridge that makes a mirror runnable makes a triggered task's workflow runnable.
- **Rich conditions** — expand the `conditions` list (multiple + nested + relational dotted paths + `logic: and/or`) + the builder UI. **No schema migration** — the list shape already holds it.

**Sequencing note:** T-1 is fully buildable now (descriptive; one migration; no dependency on the bridge). T-2 is the big deferred arc the operator already knows is coming (it's where triggers + mirrors + AI-drafts all light up). Keeping them apart is the whole point — **T-1 makes triggers legible + editable; T-2 makes them fire.**

### Migrations — flagged plainly
- **T-1: exactly ONE** — `rNNN_moc_task_trigger` (+ the event catalog table, same migration). No other schema change.
- **T-2: unknown/large** — the event bus + emission is real infrastructure (not a MoC migration); the rich-conditions expansion needs **no** migration (the JSONB list already holds it).

---

## STOP-discipline answers
- **(a) NO event substrate — confirmed, stated plainly.** There is no domain-event bus; `trigger_type="event"` is dead code (witnessed). The descriptive event-trigger is therefore **"picklist now, real hook later"** — a curated, seeded event vocabulary (grounded in real status columns) that does not fire until T-2's execution bridge builds emission. The operator should hear this: authoring an event-trigger today is legible intent, not a live automation.
- **(b) Frequency-vs-schedule IS a genuine model overlap — surfaced, not defaulted.** Recommendation is supersede-via-derivation (Frequency becomes the schedule-trigger's human summary, with the raw 2a value as the trigger-less fallback), landed non-destructively inside T-1. Presented as the operator's call, with a recommendation, not a silent choice.
- **The canonical example is real** (`sales_orders.order_type`), with the **"legacy" nuance** surfaced (it's a product-line/personalization concept, not an `order_type` value — flat `order_type` conditions now, relational product-line conditions in the rich phase).
- **Structured-for-expansion is the load-bearing modeling call:** the event condition is a **list of `{field,operator,value}` objects from day one** (holding one), so filtered→rich is data, never a migration — exactly as the dispatch required.
- **No build, no migration, no seed performed.** The plan is the deliverable.

**STOP.**
