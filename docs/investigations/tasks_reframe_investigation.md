# The Tasks/Automations Reframe — Investigation / Scoping

**Date:** 2026-07-17 · **HEAD:** `ab5e32f2` (the Map Home campaign, landed + deployed) · **Read-only — no build.**

**The operator's reframe:** TASKS = the jobs ("bank reconciliation") — the unit a business
owner thinks in. The current catalog rows (`moc_task_catalog`) = AUTOMATIONS — the means.
Banked calls: tasks LEAD area pages with automations in a collapsed secondary section;
v1 tasks link automations AND human-work surfaces (triage queues, focuses) with deriving,
deep-linking beats; the rename rides the reframe.

---

## 1. THE REFERENCE MODEL (the structural heart)

### The Task (job) entity

A new table — working name `moc_job` in code, displayed as **Task** (see §3 for why the
code name diverges):

| Field | Notes |
|---|---|
| `id`, `name`, `icon` | identity |
| `description` | the story field (the card's essence, the ponder's ground) |
| `task_type` | the AREA (the same vocabulary engine — jobs live in areas exactly as automations do; the sections/spine derivation transfers verbatim) |
| `display_order` | ordering within the area |
| `scope`, `vertical`, `tenant_id` | the three-tier identity (§1b) |
| `ponder` JSONB | authored captions (the task-ponder caption pattern, again) |
| `is_active`, audit stamps | the house pattern |

### The links: ONE polymorphic reference table — **recommended**

```
moc_job_ref:
  id, job_id FK,
  ref_kind   CHECK ('automation' | 'triage_queue' | 'focus')   -- extensible
  ref_key    String   -- automation: moc_task_catalog.id
                      -- triage_queue: TriageQueueConfig queue_id ("cash_receipts_matching_triage")
                      -- focus: focus_template slug (lineage-stable, like the MoC cards)
  label      String?  -- optional authored override; resolver labels win when absent
  display_order
```

**Why polymorphic over typed join tables (the fork is NOT close — recommending firmly):**

1. **The precedent is already load-bearing twice.** `artifact_update_offers` ships
   `artifact_type` + `target_kind`+`target_slug` (level-generic, verified in prod);
   `ponder_engagement` ships the prefix keyspace (`task:` / `area:` / `onboarding:`).
   The platform's reference grammar is already kind+key; a typed-join-per-kind Task
   model would be the odd one out.
2. **The future is the argument.** The dispatch's own framing: this reference model IS
   the capability-ponder architecture's spine. Documents (`template_key`), capability
   refs, report refs all slot into `ref_kind`+`ref_key` with zero migrations. Typed
   joins mean one migration + one resolver + one join model per future kind.
3. **The cost of polymorphism is one dispatch table** — a `REF_RESOLVERS[ref_kind]`
   dict (the `BUILDERS` / `_DIRECT_QUERIES` / `PEEK_BUILDERS` house pattern, four
   precedents strong). Referential integrity is resolver-checked (exists/available
   honesty flags), not FK-checked — exactly how the MoC card rows already work, with
   the same ref-decay/rebind semantics available where a kind needs them.
4. **The one thing typed joins buy — DB-level FK cascade — the platform already
   deliberately trades away** for cross-kind reference tables (the MoC pages' rows,
   the offers table). Consistency wins.

**Keys, not row-ids, where lineage matters:** focus refs use `template_slug` (the
version-bump rebind lesson — row ids decay); queue refs use the stable `queue_id`
string; automation refs use the catalog row id (automations don't version-bump — but
note the fleet-reseed hazard, §3 landmine list).

### 1b. Tier/variation scoping — the honest sizing

The full variation stack on jobs = scope tiers + fork (`forked_from_task_id`-equivalent)
+ merged-view yield + offers + coherence guard + isolation pins. Extending it is
**mechanical but not free** — the Workshop + P2/P3 shipped ~1.5 sessions of exactly this
for automations, and jobs would replay it plus ref-list merge semantics (does a tenant
fork of a job copy its refs? yes — refs copy like triggers, born identical).

**Options:**

| Option | Ships | Cost | Risk |
|---|---|---|---|
| **A — platform+vertical only (RECOMMENDED for v1)** | Jobs are shared pedagogy; tenants view + ponder; no job forking. Tenant-added AUTOMATIONS still appear (they ride the automation layer, listed in their area's engine-room section + attachable to jobs by the platform admin) | ~0.25 session inside phase 1 | A tenant wanting "their own version of bank reconciliation" waits for v2 — honest gap, small: the job is a STORY; what tenants customize (schedules, params, captions on automations) already forks at the automation layer |
| B — full stack now | Fork + yield + offers on jobs | +1 session, +offer-kind (`moc_job` joins `artifact_update_offers.artifact_type` cleanly — the table is ready) | Builds variation machinery before any tenant has asked to vary a job |
| C — tenant ADD without fork | Tenants can author their OWN jobs (scope-forced tenant_override, the coherence-guard pattern) but shared jobs don't fork | +0.25 session | The middle path; pairs well with A as "A+" if the operator wants tenant job authorship day one |

The offers table needs **zero migration** for any option (`artifact_type='moc_job'` is a
new value in an existing String column).

---

## 2. THE TASK PONDER (the whole job's story, on the landed deriver)

The Map Home campaign built exactly the right substrate: `area_ponder.py` proved the
composition deriver (authored beats + derived beats + closing link, same overlay, new
beat kinds, caption overlay on a store row). The job ponder is the third composition
kind on the same rails:

```
opening        — AUTHORED job framing (the operator's voice; derived-honest
                 placeholder: "«name» — N automations + M review surfaces work
                 this job.")
automation:*   — ONE beat per automation ref: name · essence · honest WHEN
                 (derived_frequency / runtime_schedule_summary — the T-0
                 authority truth carries verbatim from resolve_task) ·
                 DEEP-LINK "walk this automation" → its full ponder
                 (overlay-in-overlay NOT needed: the link closes + reopens the
                 overlay with the automation's taskId — the useMapOverlays
                 ponderKeyed path already does exactly this for suggestions)
queue:*        — the HUMAN-WORK beat: queue label · LIVE pending count ·
                 deep-link into the real triage
focus:*        — the resolved miniature (the exhibit grammar reused)
closing        — authored connective/closing + the area-page deep link
```

### Per-link-kind derivability, TODAY vs needs

| Kind | Derivable today | Gap |
|---|---|---|
| **automation** | Everything — `resolve_task` carries name/description/derived_frequency/authority truth/live chips; the deep-link is the overlay-id convention | None. Zero new machinery |
| **triage_queue** | `TriageQueueConfig` (platform_defaults) has label + icon; `triage.engine.queue_count(queue_id, user)` gives the LIVE pending count permission-aware (the spaces pin resolver already consumes it — precedent); deep link `/triage/{queue_id}` exists | **The generalization is FREE**: `QUEUE_REGISTRY` (5 workflows, ponder.py) maps *workflow→queue* for the automation ponder's downstream beat — job refs don't need it, they reference the queue_id DIRECTLY (kind+key). The registry stays what it is (the automation ponder's downstream inference); job refs bypass it. No generalization work |
| **focus** | `_focus_beats` (ponder.py) already derives the resolved miniature from a template slug via `resolve_focus` — lift the helper to take a slug instead of a task join (~20 lines) | Near-none |

**Tenant-side count honesty:** `queue_count` is user-scoped (permission-aware) — a
tenant viewer without queue access sees the beat WITHOUT the count (the pin-resolver's
`unavailable` fallback precedent), never a lie or a 403.

### The area ponder RE-POINTS (spec)

Once jobs exist, `build_area_ponder_script`'s middle section changes unit: one short
beat per **JOB** (name · essence · "N automations, M review surfaces" glance), the
cluster cap unchanged, the closing unchanged. Automations WITHOUT a job (unmapped, or
tenant-added) get one honest tail beat: "…and N automations not yet part of a task —
the engine room holds them." Mechanically: the deriver's task loop swaps its source
list; captions keep their keys (`task:<id>` beat keys become `job:<id>` — the orphan
mechanism catches authored captions on retired keys, reclaimable — pinned behavior,
already shipped). ~0.25 session inside phase 2.

---

## 3. THE RENAME PASS (display-first, collision-honest)

### Display inventory ("task" → "Automation" where it means the current rows)

Tenant surface: home header copy + spine card counts ("N tasks") + "Add a task"
button/dialog (AddTaskDialog title, placeholder copy) + area page header ("Every
{area} task…") + TaskSections headers/counts + the exemplar onboarding beats
("Every automated task lives here" — a SEED content edit, preserve-aware: the seed
only creates-if-missing, so the exemplar needs a one-time content migration OR the
operator re-authors; recommend a tiny idempotent seed-update keyed on the unchanged
default text, the Option-A prompt-seed precedent). Admin surface: "Tasks" heading +
tabs + "+ Add task" + TaskEditorPanel ("Edit task") + MoCTenantPage copy. Ponder
copy: the fork prompt ("Make this task yours?"), the adopt confirm ("This task will
now fire…"), the T-0 blocked card, the go-live confirm. Suggestions why-lines:
unaffected (they name changes, not the word).

Roughly **~40 display strings across ~14 files** — a half-day pass, mechanical,
vitest copy-pins updated alongside.

### The code collision — recommendation: **display-first everywhere; the NEW entity's code name diverges, stated honestly**

The old entity's code surface is deep and load-bearing: `moc_task_catalog` +
`moc_task_trigger` tables; `MoCTaskCatalog` model; `task_catalog.py`, `task_fork.py`,
`task_offers.py` services; `/moc/tasks*` + `/moc/ponder/{task_id}*` routes (tenant AND
admin); `ponder_key='task:<id>'` engagement rows (DATA, not just code); the offers
table's `artifact_type='moc_task'` values (DATA); ~30 test files' fixtures. A full
code rename is a 2-session mechanical churn with two DATA migrations (engagement keys,
offer artifact_types) — all risk, no user-visible gain.

**So the new entity does NOT take `task` in code.** Code name `moc_job` /
`MoCJob` / `job_*` routes — displayed everywhere as **Task**. The divergence is
stated in the model docstring + CLAUDE.md (the platform already lives with
display≠code in places — "Automation" itself will display over `moc_task_catalog`).
Opportunistic code renames ride natural touches only (the build-discipline canon:
pages migrate when next touched).

### API surface — the honest window

The tenant routes are young (P2, weeks old, one real tenant + testco). **Clean-break
is affordable NOW and won't be later**: new `/moc/jobs*` routes for the new entity;
existing `/moc/tasks*` routes KEEP their paths (they serve automations; the path noun
goes quietly stale like the DB table — comment-honest, not user-visible). No aliases
needed because nothing breaks: old routes keep serving the old entity. The only
rename-adjacent break worth taking in the same window: **none required.**

### Landmines (surfaced per stop-discipline; none blocks)

1. **Engagement keyspace collision:** `ponder_key='task:<id>'` today means AUTOMATION
   ponders. The new entity must use `job:<id>` keys — if it took `task:`, recency
   suggestions and dismissals would cross-wire. (Handled by the code-name divergence:
   the overlay-id prefix follows the code name.)
2. **The fleet-reseed hazard:** `test_moc_workflow_mirrors`' teardown recreates
   automation rows with NEW ids (the T-1 trigger-preservation fix). Job→automation
   refs by row id would dangle on dev after that suite. The same teardown must learn
   to re-attach `moc_job_ref` rows by name (the trigger-preservation pattern,
   ~10 lines) — flagged as part of phase 1's test work, not a design change.
3. **`seed_moc_manufacturing` upserts** preserve row ids (verified in the Workshop) —
   boot seeds are safe for refs; only the test teardown needs the fix.

---

## 4. THE MAP RE-UNIT + THE ACCOUNTING SKELETON

### The re-unit spec

- **Area pages:** JOB cards LEAD (the TaskCard grammar with a "N automations ·
  M surfaces" glance line replacing the single-automation footer). Below, a
  **collapsed-by-default section "The engine room"** (name subject to the operator's
  taste) holding the shipped automation cards unchanged — collapse state per-user
  (the TaskSections localStorage mechanism, reused). Automations unmapped to any job
  simply appear there; nothing is hidden.
- **The home spine:** area cards' glance becomes "N tasks" (jobs) with the live-fleet
  count still derived from the underlying automations (live is an automation truth).
- **Yours:** tenant-added AUTOMATIONS stay in Yours (they're theirs); under option C,
  tenant jobs join. The area link on yours-cards unchanged.
- **Suggestions/engagement:** job ponders join the keyspace as `job:<id>`; the
  role-area and onboarding rules unchanged; recency extends to jobs free
  (`updated_at` vs `viewed_at`, same rule).
- **Deliberate room preserved:** capability cards were promised a slot — under the
  reframe they become refs (`ref_kind='capability'`) on jobs AND/OR cards in the
  engine-room section; the polymorphic model is why this stays a no-migration future.

### The accounting skeleton (PROPOSAL — the operator refines and authors)

| Job (Task) | Automation refs (current catalog rows) | Human-work refs | Notes |
|---|---|---|---|
| **Bank reconciliation** | Cash Receipts Matching | `cash_receipts_matching_triage` | The dispatch's own exemplar; the D-3 matching + its review queue |
| **Month-end close** | Month-End Close · Monthly Statement Run | `month_end_close_triage` | Month-End Close is ALREADY job-shaped (manual, human-initiated, a story) — it may *become* the job row's identity with its automation ref pointing at the runnable |
| **Collections** | AR Collections | `ar_collections_triage` | Clean 1+1 |
| **Customer billing & statements** | Monthly Statement Run · Funeral Home Billing | `month_end_close_triage` (statement review) | Statement Run serves TWO jobs (close + billing) — the many-to-many earning its keep on day one |
| **Expense management** | Expense Categorization | `expense_categorization_triage` | Expense Categorization is automation-shaped; the JOB is "keep expenses categorized and reviewed" |
| **Compliance & records upkeep** *(or per-area later)* | Compliance Sync · Document Review Reminder · Training Expiry Monitor | — | The grouped mirrors want a home; possibly outside Accounting (their area vocab today varies) — the operator's call |

Job-shaped today: Month-End Close. Automation-shaped serving an unnamed job: everything
else. Focus refs (e.g. Decision Triage focus on close/billing) attach where the operator
wants exhibits.

---

## Phased plan + honest sizing (~3–4 sessions)

| Phase | Contents | Size | Migrations |
|---|---|---|---|
| **R-1 — entity + refs + rename** | `moc_job` + `moc_job_ref` (ONE migration, reversible) · REF_RESOLVERS dispatch · platform+vertical tiers (option A) · admin CRUD (the task-editing panel pattern) · the display rename pass + copy pins · the fleet-reseed ref-preservation | 1–1.25 sessions | **r132** (`moc_job` + `moc_job_ref`) |
| **R-2 — the job ponder + the re-unit** | The job composition deriver (on the landed mechanism) · queue/focus beat derivers (count + miniature) · area pages re-unit (jobs lead, engine room collapses) · home glances · engagement `job:` keys · the area ponder re-point | 1–1.25 sessions | none |
| **R-3 — the accounting authoring pass (WITH the operator)** | Seed the skeleton table as PROPOSED rows (preserve-aware) · the operator refines mappings + authors the job framings in-ponder · suggestions extended to jobs · staging walk | 0.75–1 session, operator-paced | none |
| *(later, on signal)* R-4 | Tenant job authorship/forking (options B/C) · capability refs · document refs | sized then | offers: none (String column); possibly none at all |

**STOP-discipline verdicts:** the reference-model fork is NOT close (polymorphic,
firmly — four in-house precedents and the capability future); tier scoping surfaced as
options with A recommended; rename landmines are the three listed, all handled by the
code-name divergence + one test-teardown patch — none load-bearing-breaking. The map
is the deliverable; nothing was built.
