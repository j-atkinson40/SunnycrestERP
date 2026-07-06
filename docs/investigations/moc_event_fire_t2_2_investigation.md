# Canvas↔Runtime Bridge T-2.2 — Event Firing: Scoping (read-only)

**Date:** 2026-07-06 · **HEAD at investigation:** `a29a997` ·
**Scope:** the last and largest execution crossing — event-triggered MoC tasks
that FIRE when a domain event matches. T-2.1 proved schedule-firing end-to-end
(sweep → dry-run-safe engine → is_live promotion → real fire — all live on
staging). T-2.2 is the same crossing for EVENT triggers, but the substrate is
NET-NEW: **verified again this read — there is NO domain-event bus, no outbox,
no emission anywhere** (the only grep hit for "outbox" in the backend is a
docstring word in documents_v2). The descriptive event-trigger layer is done;
the execution substrate under it is the build.

**Honest sizing up front: 3 core sessions + 1 deferred wiring pass** (per-event
emission for the scattered mutations). Phasing mirrors T-2.1's proven
choreography exactly (substrate → dry-run sweep → live conversion + witnessed
first fire).

---

## 1. The four-layer decomposition — exists vs net-new vs risk

### 1.1 EMISSION — net-new; the hook-point decision (STOP finding (a): REAL, and MIXED)

Nothing emits today. Three candidate hook points, evaluated:

| Hook | Verdict | Why |
|---|---|---|
| **Explicit `emit_event()` at mutation sites, same transaction (transactional outbox)** | **RECOMMENDED** | The event row commits IFF the mutation commits — no lost events (mutation committed, event lost), no phantom events (event recorded, mutation rolled back). This is the only option that closes the "silent-swallow at emission scale" flag by construction. The cost is honest: every mutation site must call it (see the per-event audit below). |
| SQLAlchemy `after_commit` / session events | REJECTED | Fires after the transaction — a crash between commit and hook = a lost event (exactly the silent-swallow). Also blind to the codebase's raw-SQL mutation paths (the workflow engine's `_handle_create_record` INSERTs `sales_orders` via `sql_text` — ORM events never see it). |
| Mapper/attribute events (observe status-column flips) | REJECTED | Column changes aren't business semantics (`invoice.sent` is an act, not a column write); same raw-SQL blindness; and debugging "why did this fire" through implicit ORM hooks is the wrong legibility trade for a firing system. |

**The task-subscriber registry (canon's closest prototype) — a pattern, not a bus.**
Read at `app/services/tasks/subscribers/registry.py`: an in-memory registry, 7
task-lifecycle event types, sync dispatch inside the task transaction,
try/except per subscriber. Its *shape* generalizes (explicit emit at the
substrate's own chokepoint + registered handlers); its *mechanism* does not —
it is domain-scoped to tasks, in-memory (no durability), and dispatches
synchronously in-transaction, which is precisely what T-2.2 must NOT do for
firing (§1.3). Verdict: borrow the explicit-emit + registry pattern; the
durable outbox + async matcher are net-new.

**The per-event chokepoint audit (the finding that shapes the phasing).** The 8
cataloged events (`trigger_events.py::_SEED`) split cleanly:

| Event | Mutation site(s) | Emission difficulty |
|---|---|---|
| `case.opened` | `fh/case_service.create_case` — the single canonical path (even the workflow engine delegates to it) | **CLEAN — 1 call** |
| `delivery.completed` | `delivery_service` status flip (~1 site) | **CLEAN** |
| `certificate.approved` | `social_service_certificate_service` approval path | **CLEAN** |
| `urn_order.proof_pending` | `urn_engraving_service` (the two-gate proof flow) | **CLEAN** |
| `invoice.paid` | 2 writers: `sales_service` payment application + `cash_receipts_adapter` (which deliberately replicates the write pattern — both must emit) | MODERATE — 2 calls |
| `invoice.sent` | statement/delivery paths — needs a site audit | MODERATE |
| `order.created` | **≥6 `SalesOrder(` construction sites**: sales_service ×2, vault_order_service, call_extraction_service, quote_service, legacy_studio route — PLUS the engine's raw-SQL `_handle_create_record` | **SCATTERED — the hard one** |
| `order.completed` | status flips across services | SCATTERED |

**Recommendation:** T-2.2a wires emission for the four CLEAN events only (+
`invoice.paid`'s two sites if the session has room). The `order.*` events get a
**dedicated wiring pass** (its own session, with a per-site audit + a checklist
like the WORKFLOW_MIGRATION_TEMPLATE discipline) — wiring 6+ scattered sites
under time pressure is how one gets missed, and a missed emit site is the
silent-never-fires failure. Until wired, an event-trigger on an unwired event
is honestly DESCRIPTIVE-ONLY — the catalog row should carry a `wired: bool`
(or the investigation's matcher logs an unwired-event warning) so the UI can
eventually say "this event isn't firing yet" instead of silence. Flag this
as a T-2.2b observability item.

### 1.2 DURABILITY — the outbox (net-new; the hardest design piece — STOP finding (b): resolved by recommendation)

**Table: `moc_domain_event` (migration r119).** One row per emitted event:

```
id            String(36) PK
company_id    FK companies — events are tenant-scoped (load-bearing: fan-out §1.3)
event_key     String — the catalog key ("case.opened")
entity_type   String nullable — the catalog's entity ("fh_case")
entity_id     String nullable — attribution
payload       JSONB — the filterable-field VALUES, snapshotted at emit
emitted_at    timestamptz
processed_at  timestamptz NULL — the matcher's claim mark
[partial index on processed_at IS NULL — the matcher's work queue]
[index on (company_id, event_key)]
```

**Payload = emit-time snapshot, caller-provided.** The mutation site passes
`payload={"order_type": "funeral", "status": "confirmed"}` — the fields the
catalog's `filterable_fields` declares. Conditions then evaluate against the
state *at the moment the event happened* (correct semantics: "order created
WHERE type==funeral" means at creation), and the matcher never re-reads domain
entities (no N+1, no evaluated-against-later-state bugs). A condition
referencing a field absent from the payload is a NO-MATCH + a logged warning —
never a guess.

**Reliability model: at-least-once + idempotent firing.** At-most-once is
rejected — lossy delivery on a firing substrate is the silent-swallow again.
At-least-once is safe because firing dedup is already a solved pattern here:
T-2.1a's re-keyed idempotency (`WorkflowRun.trigger_context`) extends verbatim —
the event fire's dedup key is **(moc_task_trigger_id, event_id)** in
trigger_context, queried exactly like `_already_fired` queries
(trigger_id, intended_fire) today. A redelivered/reprocessed event finds the
existing run and skips. No new table, same audit-trail-based self-healing.

**Ordering: NOT load-bearing — document, don't build.** Each event matches its
triggers independently; MoC task fires are independent workflow runs. No
cross-event ordering guarantee is needed (and none should be promised).

**Retention:** processed rows accumulate. Recommendation: keep it out of the
core arc — a `processed_at < now()-30d` prune (a tiny sweep or manual SQL) as a
deferred hygiene item, flagged in T-2.2a's close note. Not load-bearing for
correctness (the partial index keeps the matcher's queue scan cheap regardless).

### 1.3 MATCHING — the matcher sweep (net-new logic; the STRUCTURE is T-2.1a's — STOP finding (c): resolved)

**Sweep over the outbox, NOT match-at-emit.** Match-at-emit (synchronous, in
the mutation's request path) is rejected on blast radius: it couples domain
mutations to MoC firing — a matcher bug breaks order creation; a LIVE fire's
effects would execute inside (or racing) the source transaction; there is no
retry. The sweep decouples completely: emit is a cheap same-transaction INSERT;
match+fire is async, retryable, isolated (its own APScheduler job with its own
try/except, exactly like `moc_schedule_sweep`). The cost is latency, bounded by
the interval — recommend **1-minute** (events deserve tighter latency than the
schedule sweep's 15-min, which exists because schedule windows are 15-min; an
APScheduler 1-min interval job is cheap given the partial-index queue scan).

**The matcher's per-event loop** (mirrors `check_moc_task_schedules`'s shape):

```
for event in unprocessed(moc_domain_event, cap=500/sweep):
    for trig in active event-kind triggers where config.event == event.event_key:
        task = trig.task; if inactive/unrunnable: continue
        # TENANT SCOPING — the event's company must be in the task's fan-out set
        #   platform_default → yes | vertical_default → company.vertical == task.vertical
        #   tenant_override → task.tenant_id == event.company_id
        # (the INVERSE of _fanout_companies: membership test, not enumeration)
        if not fanout_includes(task, event.company): continue
        if not conditions_match(trig.config.conditions, event.payload): continue
        if already_fired(trigger_id=trig.id, event_id=event.id): continue   # idempotency
        _fire(trig, task, company, event)   # ← T-2.1's fire path, verbatim shape
    event.processed_at = now()
```

**Condition evaluation:** a small pure evaluator (~30 LOC) over
`conditions:[{field, operator, value}]` with the shipped `OPERATORS` set
(`== != in > < >= <= contains`), type-aware via the catalog's
`filterable_fields[].type` (number coercion for comparisons; enum/string
equality; `in` over lists). The structured-for-rich condition shape (T-1a's
load-bearing guard) pays off here: list-of-one evaluates as AND-of-list with
zero model change when rich conditions land.

**Blast radius bounding (the mis-match question):** an over-broad condition
(e.g. `order.created` with no conditions) fires once per matching event per
trigger — bounded by (a) dry-run default (a mis-match is a visible dry-run
preview, not an effect), (b) per-trigger is_live (going live is deliberate,
per-trigger, evidence-confirmed via the T-2.1c dialog), (c) §6 compiled-only,
(d) the per-sweep event cap (a runaway emitter backlogs visibly rather than
firing unboundedly), (e) the run-log (every fire attributable to its event).
The T-2.1c confirm's "latest dry-run preview" evidence works UNCHANGED for
event triggers — an operator sees real matched dry-run fires before promoting.

### 1.4 FIRING — exists; ZERO net-new (the reuse credit, confirmed)

Firing reuses T-2.1's spine verbatim — this is the whole point of the unified
bridge, and it holds:

- `execute_template(allow_run=True, go_live=_resolve_go_live(trig, template))`
  — the SAME single-source derivation; **`is_live` (r117) is a kind-agnostic
  column on `moc_task_trigger`** (confirmed) — event triggers reuse it, NO new
  promotion migration, and the §6 mirror guard applies unchanged (a mirror-task
  event-trigger fires dry-run even promoted).
- The compiled-workflow cache (r116), the engine dry-run mode (T-2.0b), loud
  failure recording, `_surface_run_failures` — all inherited untouched.
- `trigger_source="moc_task_event"` (parallel to `"moc_task_schedule"`) with
  `trigger_context={moc_task_trigger_id, event_id, event_key, entity_id, …}` —
  which gives idempotency (§1.2) + observability (§3) for free from the
  existing patterns.
- **Precedent proof it works:** the intake classification dispatch
  (`classification/dispatch.py::classify_and_fire`) already does
  event-shaped→`start_run` firing in production (inbound email → match → fire
  with trigger_source + trigger_context + a denormalized per-row audit
  outcome). Its structure — durable source row, cascade match, fire, per-row
  outcome — is T-2.2's shape with the outbox playing the email-row's role.

## 2. What the descriptive layer already gives (confirmed — no rebuild)

- `moc_task_trigger` kind="event" + structured `conditions` + the validator
  (field ∈ filterable_fields, operator ∈ OPERATORS, value present) — shipped
  (T-1a), tested, and its referential validation means the matcher can trust
  condition shapes.
- `moc_trigger_event_catalog` with `filterable_fields` — shipped + seeded
  (8 platform events) + API-extendable. The catalog is the matcher's field/type
  authority AND the payload contract for emit sites.
- The T-1b editing UI (kind-switched form, event picker, condition builder) —
  done; authoring needs NOTHING for T-2.2.
- The T-2.1c Live toggle + evidence-backed confirm — the MECHANISM is
  kind-agnostic, but **one small UI gap found: the Live badge/toggle renders
  for `kind === "schedule"` chips only** (TriggerChips.tsx:148). T-2.2c extends
  it to event chips (a condition change + the §6/capability wiring already
  passed in) — small, but it must be on the plan or event triggers can't be
  promoted from the UI.

## 3. The safety surface

**Inherited (nothing to rebuild):** engine dry-run default (deny-by-default at
the step executor) · per-trigger `is_live` promotion + the T-2.1c confirm ·
`_resolve_go_live` single source + §6 mirror guard · loud failure (status=failed
+ error_message) · the state-immunity test discipline (the matcher's tests
scope to fixture event/trigger ids from DAY ONE — the sweep-test lesson,
already canonized in `test_moc_schedule_sweep.py`'s docstring).

**Event-specific, net-new:**
- **Redelivery idempotency:** dedup on (trigger_id, event_id) via
  trigger_context (§1.2) — the event-scale version of the schedule-window dedup.
- **Blast radius:** §1.3's five bounds; plus the choreography guard below.
- **The T-2.2b choreography guard (important):** because `is_live` already
  exists, the moment the matcher lands, a promoted event-trigger would fire
  LIVE. T-2.2b must therefore ship with a **forced-dry-run constant** in the
  matcher (the exact `_SWEEP_GO_LIVE = False` pattern T-2.1a used), converted
  to `_resolve_go_live` in T-2.2c — so the dry-run-observation phase exists
  for events as it did for schedules, regardless of what's promoted.
- **Observability:** event fires appear in the run-log with their provenance.
  Recommend ONE log surface: extend `list_schedule_runs` to
  `trigger_source IN (moc_task_schedule, moc_task_event)` with a `source` +
  `event_key`/`event_id` fields (rename the endpoint concept to "MoC fires" in
  the response, keep the route for compat) — an operator sees ALL MoC firing in
  one place, schedule and event alike. Unprocessed-backlog count + unwired-event
  warnings belong here too.

## 4. The phased plan (mirrors T-2.1's proven choreography)

| Phase | Content | Net-new | Session |
|---|---|---|---|
| **T-2.2a — the emission substrate** | Migration **r119 `moc_domain_event`** (reversible) + `emit_event()` (same-transaction insert) + wiring the 4 CLEAN-chokepoint events (`case.opened`, `delivery.completed`, `certificate.approved`, `urn_order.proof_pending`; + `invoice.paid`'s 2 sites if room). Assembly-tested at the transactionality boundary: mutation commits → event row exists with the right payload; mutation rolls back → NO row; emission failure fails the mutation loudly (never a swallowed emit). NOTHING consumes the rows yet — inert, like r115's descriptive triggers. | outbox + emit + 4-6 call sites | 1 |
| **T-2.2b — the dry-run matcher sweep** | The matcher (isolated APScheduler job, ~1-min interval, per-sweep cap) + the condition evaluator + fan-out membership + (trigger_id, event_id) idempotency + `processed_at` marking + the run-log extension (one MoC-fires surface). **Every fire forced dry-run** (`_MATCH_GO_LIVE = False` — the T-2.1a pattern), regardless of is_live. Assembly: an emitted matching event fires dry-run once (spy never called), a non-matching condition doesn't, another tenant's event doesn't, redelivery doesn't double-fire, the backlog cap holds. Tests fixture-scoped (state-immunity from day one). | matcher + evaluator + log | 1 |
| **T-2.2c — the live conversion + the witnessed first real event-fire** | Convert the constant to `_resolve_go_live` (the T-2.1b move — one source, §6 inherited); extend the Live badge/toggle to event chips (TriggerChips kind gate) — the T-2.1c confirm works unchanged; then the WITNESS, isolated exactly like T-2.1b-WITNESS: an event-trigger on the **existing benign witness marker-task** (r118 substrate reused — e.g. condition-matched on a benign seeded event), promoted, a real emit → match → **live fire → marker row**, exactly once, then de-promoted. Reversibility on screen. | go_live flip + chip UI + witness | 1 |
| **T-2.2d (deferred) — the scattered-event wiring pass** | `order.created` (≥6 sites + the engine's raw-SQL path) + `order.completed` + `invoice.sent`, each with a per-site audit checklist. Until then those catalog events are honestly unwired (matcher logs a warning when a trigger references an unwired event — shipped in 2.2b). | ~10 call sites, audited | 1 (own session) |

**Migrations:** r119 (outbox) only. **No promotion migration** — `is_live`
(r117) is reused, confirmed kind-agnostic. **No new frontend authoring** — only
the chip's badge-kind extension in 2.2c.

**Explicitly out of scope for the arc:** outbox pruning (hygiene follow-up);
rich (multi-condition AND/OR) evaluation beyond AND-of-list; event catalog UI
for wired-status; mirror-task live-scheduling (§6 dedupe — still its own arc);
the failure→escalation polling hook (still cataloged).

## 5. STOP findings — status

- **(a) Emission chokepoints — REAL and MIXED**, the reshaping finding: 4 of 8
  events have clean single-service chokepoints; `order.*` is scattered across
  ≥6 ORM sites + one raw-SQL path. Resolved by phasing: clean events in 2.2a,
  scattered in a dedicated audited pass (2.2d), unwired-event warnings in the
  matcher so the gap is visible, never silent.
- **(b) Outbox reliability fork — resolved:** transactional outbox +
  at-least-once + idempotent firing. The idempotency mechanism is not new
  design — it is T-2.1a's trigger_context dedup re-keyed on (trigger, event).
  At-most-once rejected as silent-swallow-by-design.
- **(c) Match-at-emit vs sweep — resolved: sweep.** Decoupling (a matcher bug
  must not break order creation), retryability, and keeping live effects out
  of the source transaction outweigh the ≤1-min latency cost. The sweep is
  also the shape the whole T-2.1 pattern, the scheduler, and the intake
  cascade already use — one operational model, not two.

**Sizing, honestly: 3 core sessions (2.2a/b/c) + 1 deferred (2.2d), each with
its own assembly gate; the first REAL event-fire is its own witnessed step on
the existing benign marker substrate.** The fire path, the safety model, the
promotion mechanism, the confirm UI, and the witness target all already exist —
T-2.2 builds exactly the three missing layers (emit, outbox, match) and
nothing else.
