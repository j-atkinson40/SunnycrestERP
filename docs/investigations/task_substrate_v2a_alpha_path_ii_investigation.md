# v2a-α path (ii) reframe — investigation deliverable

**Investigation altitude.** Path (ii) reframe scope verified against HEAD `cce834d`. Read-only investigation per Entry 1 audit-first discipline. No canon edits, no STATE.md edits, no production code, no Phase 4 re-adjudication, no Phase 5 §2.A revision drafting, no build dispatch. Bounded decision per Entry 31: deliverable shipped at this path.

**Context.** Fifth-iteration build STOP per Entry 23 surfaced producer-vs-consumer cardinality mismatch at v2a-α dispatch attempt. Original v2a-α scope ("migrate 4 AgentAnomaly cluster `_dq_*` consumer-side read paths to task substrate" per phasing §3.4) is incompatible with verified producer cardinality. Path (ii) reframe candidate: defer `_dq_*` migration; ship a query helper + extend Pulse + briefings consumers as v2a-α's bounded deliverable; the deferred `_dq_*` work moves to a future arc with its own operator-observable signal trigger per Entry 3.

This investigation verifies path (ii) reframe scope against actual substrate state across 7 sections.

---

## §A — Pulse Personal layer current query pattern verification

### Audit target
- `backend/app/services/pulse/personal_layer_service.py::_build_tasks_item` — line **95** (Phase 0 audit cited line 111; precision drift; investigation uses verified line 95)
- `_build_approvals_item` — line 201 (deferred to Phase W-4b per `return None` at line 225; not in v2a-α scope)
- `compose_for_user` — line 276 (entry point; calls both builders)

### Consumption pattern (file:line precision)

`_build_tasks_item` at lines 95–198 performs **a direct `VaultItem JOIN TaskDetails` query inlined into the builder**. It does NOT call any `task_service` export. Specifically (lines 136–164):

```python
rows: list[tuple[VaultItem, TaskDetails]] = (
    db.query(VaultItem, TaskDetails)
    .join(TaskDetails, TaskDetails.vault_item_id == VaultItem.id)
    .filter(VaultItem.company_id == user.company_id)
    .filter(VaultItem.item_type == "task")
    .filter(VaultItem.is_active.is_(True))
    .filter(TaskDetails.assignee_user_id == user.id)
    .filter(
        TaskDetails.visibility.in_(
            ("operator_internal", "operator_assigned")
        )
    )
    .filter(
        TaskDetails.current_state.in_(
            ("created", "assigned", "in_progress", "blocked",
             "informational",)
        )
    )
    .order_by(priority_rank.desc(), TaskDetails.due_date.asc().nullslast())
    .limit(20)
    .all()
)
```

### Filter dimensions consumed

| Dimension | Pulse value | Notes |
|---|---|---|
| `company_id` | `user.company_id` | Tenant isolation |
| `item_type` | `"task"` | Substrate discriminator |
| `is_active` | `True` | Soft-delete filter |
| `assignee_user_id` | `user.id` | **Per-user scope (Personal layer)** |
| `visibility` | `("operator_internal", "operator_assigned")` | Operator-only enforcement |
| `current_state` | non-terminal set across both lifecycle shapes (5 values) | Excludes terminal action + reminder |
| Order | `priority_rank DESC`, `due_date ASC NULLS LAST` | Pre-computed CASE rank (urgent>high>normal>low) |
| Limit | 20 | Brief-variant envelope |

### Cardinality at consumption

**Per-row** at the substrate altitude — Pulse reads `TaskDetails` rows 1:1 with `VaultItem` rows. The query returns up to 20 task rows assigned to this user; each row renders independently in the top-3 inline list (lines 171–182) with the remaining surfaced as `total_count`.

The query does NOT collapse on `provenance_ref_id` or any cohort dimension. Pulse simply renders **whatever rows the substrate hands it** — including the rollup-per-job rows that producers currently emit (`base_agent.py:376-397` + `aftercare_adapter.py:214-239`). When a rollup task surfaces, its title reads "N items need review" or "Aftercare follow-up due: N cases" — Pulse renders the aggregate title verbatim, click-through goes to the linked triage URL (`metadata.notification_link` carried in the rollup task).

### Other Pulse direct task substrate queries

Grep confirms `_build_tasks_item` (line 95) is the only Pulse task substrate query path. `_build_approvals_item` (line 201) is gated `return None` at line 225 pending Phase W-4b migration; its body queries `AgentJob` directly, not the substrate.

### §A outcome

Pulse consumes task substrate via **direct inline `VaultItem JOIN TaskDetails` query** with 8 filter dimensions (tenant + substrate + assignee + visibility + state + active + ordering + limit), at **per-task-row cardinality**, rendering rollup-task aggregate titles directly. The function does NOT route through any `task_service` export.

---

## §B — Briefings current query pattern verification

### Audit target
- Phase 0 audit cited `task_summary_builder.py:43`
- Initial grep at investigation pre-flight returned no occurrences at that path
- Re-grep across `backend/app/services/briefings/` located the actual consumer

### Actual file path

`backend/app/services/briefings/data_sources.py` — **three** task substrate consumer helpers:

| Helper | Line | Cardinality | Limit |
|---|---|---|---|
| `_collect_pending_tasks_summary` | 293 | per-task-row | 25 |
| `_collect_recent_completions_summary` | 366 | per-task-row | 25 |
| `_collect_upcoming_deadlines_summary` | 416 | per-task-row | 25 |

Phase 0 audit citation of `task_summary_builder.py:43` is **a Phase 0 audit citation drift** — the file does not exist; consumption lives in `data_sources.py` at three call sites. This is a Phase 0 audit citation gap, NOT a substrate-state divergence (substrate IS operationally consumed by briefings; just at a different file path than Phase 0 cited). No material-divergence STOP trigger fires per Entry 23 — the consumption is real and behaviorally as Phase 0 framed.

### Consumption pattern (file:line precision)

Each helper performs a **direct `VaultItem JOIN TaskDetails` query inlined into the helper** — same pattern as Pulse `_build_tasks_item`. Lazy imports of `TaskDetails` + `VaultItem` inside `try/except ImportError` for substrate-not-yet-shipped tolerance (lines 309–311, 375–377, 424–426).

`_collect_pending_tasks_summary` body (lines 320–347):

```python
rows = (
    db.query(VaultItem, TaskDetails)
    .join(TaskDetails, TaskDetails.vault_item_id == VaultItem.id)
    .filter(VaultItem.company_id == user.company_id)
    .filter(VaultItem.item_type == "task")
    .filter(VaultItem.is_active.is_(True))
    .filter(TaskDetails.assignee_user_id == user.id)
    .filter(TaskDetails.visibility.in_(("operator_internal", "operator_assigned")))
    .filter(TaskDetails.current_state.in_(
        ("created", "assigned", "in_progress", "blocked", "informational",)
    ))
    .order_by(priority_rank.desc(), TaskDetails.due_date.asc().nullslast())
    .limit(25)
    .all()
)
```

### Filter dimensions per helper

`_collect_pending_tasks_summary` (line 293) — identical to Pulse `_build_tasks_item` modulo limit (25 vs 20).

`_collect_recent_completions_summary` (line 366) — variant filter set:
- Same tenant + item_type + assignee + visibility
- `current_state == "done"` (terminal action state)
- `completed_at >= since` + `completed_at.isnot(None)`
- Order: `completed_at.desc()`
- Limit 25

`_collect_upcoming_deadlines_summary` (line 416) — variant filter set:
- Same tenant + item_type + assignee + visibility + active + non-terminal-states
- `due_date >= today` + `due_date <= today + days_ahead`
- Order: `due_date.asc()`
- Limit 25

### Cardinality + rollup rendering

All three helpers return at **per-task-row cardinality** (max 25 rows each). Briefings renders aggregate rollup titles directly (same as Pulse) — no cohort expansion, no per-row item synthesis. Each row carries `title` from the VaultItem; if that title is "N items need review", briefings shows that string verbatim.

### `task_service` export consumption

NONE. Briefings does NOT call any `task_service` export. The three helpers query the substrate tables directly via SQLAlchemy ORM, matching the Pulse pattern verbatim.

### §B outcome

Briefings consumes task substrate via **three direct inline `VaultItem JOIN TaskDetails` queries** at three distinct lifecycle slices (pending / recently-completed / upcoming-deadline), at per-task-row cardinality, rendering aggregate rollup titles directly. The function does NOT route through any `task_service` export.

Phase 0 audit citation `task_summary_builder.py:43` is a **citation drift** (file does not exist); actual consumption at `data_sources.py:293/366/416`. Surface as Phase 0 audit citation gap; NOT a material-divergence STOP trigger because substrate IS operationally consumed.

---

## §C — Helper signature adequacy for Pulse + briefings consumers

### Proposed helper signature (from prompt)

```python
def query_open_tasks_by_provenance(
    db: Session,
    *,
    company_id: str,
    provenance_kind: str,
    provenance_ref_type: str | None = None,
    provenance_ref_id: str | None = None,
    lifecycle_states: list[str] | None = None,
) -> list[TaskDetails]:
```

### Adequacy check against Pulse + briefings consumption

| Consumer | Required dimensions | In helper sig? | Gap |
|---|---|---|---|
| Pulse `_build_tasks_item` | tenant, item_type, is_active, assignee, visibility, state set, priority/due_date order, limit | tenant ✓ / state set ✓ / **assignee ✗** / **visibility ✗** / **ordering ✗** / **limit ✗** / **item_type+active implicit ✗** | Substantial |
| Briefings `_collect_pending_tasks_summary` | same as Pulse modulo limit (25) | same gaps | Substantial |
| Briefings `_collect_recent_completions_summary` | tenant, item_type, assignee, visibility, `current_state=="done"`, `completed_at >= since`, completion-time order, limit | gap + **completed_at filter ✗** | Substantial + extension |
| Briefings `_collect_upcoming_deadlines_summary` | tenant, item_type, assignee, visibility, non-terminal states, **due_date range ✗**, due-date order, limit | gap + **due_date range filter ✗** | Substantial + extension |

### Fundamental signature mismatch

The proposed `query_open_tasks_by_provenance` signature is **provenance-keyed** (provenance_kind + provenance_ref_type + provenance_ref_id). Pulse + briefings consumption is **assignee-keyed** (assignee_user_id + visibility + lifecycle state). The two query shapes are orthogonal:

- **Provenance-keyed**: "Find all tasks that came from this AgentJob / SafetyProgramGeneration / SocialServiceCertificate / etc." Use case: a `_dq_*` consumer wanting to look up the task substrate row for a domain entity it already has. This is the `_dq_*` migration path that path (ii) defers.
- **Assignee-keyed**: "Find all open tasks assigned to this user." Use case: Pulse + briefings rendering a per-user task list. This is what Pulse + briefings ACTUALLY do.

The proposed helper signature serves the **deferred** consumer pattern (`_dq_*` migration), not the **path (ii) v2a-α** consumer pattern (Pulse + briefings). Shipping `query_open_tasks_by_provenance` at v2a-α path (ii) creates a helper with no v2a-α consumer.

### Two material-divergence framings

**Framing 1 — STOP per Entry 23 (signature inadequate without substantial expansion).** The signature requires substantial expansion (assignee filter, visibility filter, state-set filter, ordering, limit, item_type+active implicit, plus extension filters for completed_at + due_date range) to cover Pulse + briefings consumption. Per Entry 5 substrate-minimal-default + Entry 17 substrate-prescience-meets-second-consumer, signature expansion at first-consumer altitude is canonical, but the expansion here is large enough that the resulting helper becomes a per-user-task-list query, not a provenance-keyed query.

**Framing 2 — different helper for path (ii) altitude.** Path (ii) v2a-α may want a different helper signature entirely. Candidate:

```python
def list_open_tasks_assigned_to_user(
    db: Session,
    *,
    user: User,
    lifecycle_states: tuple[str, ...] | None = None,  # default: non-terminal
    due_date_window: tuple[date | None, date | None] | None = None,
    completed_since: datetime | None = None,
    limit: int = 25,
    order_by: Literal["priority_then_due", "due_date", "completed_at"] = "priority_then_due",
) -> list[tuple[VaultItem, TaskDetails]]:
```

This signature serves Pulse + 3 briefings helpers uniformly. The existing `task_service.list_task_details_for_company` at `service.py:453` is close — it already handles tenant + item_type + active + visibility + assignee + state-set + terminal-exclusion. Path (ii) v2a-α candidate work: **extend `list_task_details_for_company`** with the missing dimensions (completed_at filter, due_date range filter, ordering option, return-with-VaultItem-tuple option) rather than ship a new helper.

### §C outcome — material-divergence trigger fires per Entry 23

Helper signature substantially inadequate for path (ii) v2a-α actual consumer needs. Two paths surface for operator decision:

- **Path C1 — extend existing `task_service.list_task_details_for_company`** with ordering + due_date range + completed_at filter + VaultItem-tuple return. Minimal new surface; consumers replace inline queries with helper calls. Preserves Entry 5 substrate-minimal-default.
- **Path C2 — ship new `list_open_tasks_assigned_to_user` helper** explicitly per-user-task-list shape; deprecate `list_task_details_for_company` over time (Entry 13 substrate-transition discipline). More surface; clearer naming.

The proposed `query_open_tasks_by_provenance` signature should NOT ship at v2a-α path (ii) — it has no v2a-α consumer. It belongs at the deferred `_dq_*` migration arc per §F.

Operator decision required before path (ii) v2a-α dispatch drafts.

---

## §D — Path (ii) v2a-α close criterion candidate

### Reframed scope per §C outcome

Path (ii) v2a-α ships a **helper-extension-and-consumer-rewire** deliverable:

1. Extend `task_service.list_task_details_for_company` (or ship sibling helper per §C operator decision) with missing dimensions: ordering option, due_date range filter, completed_at filter, VaultItem-tuple return.
2. Rewire Pulse `_build_tasks_item` (1 site) to consume helper.
3. Rewire briefings `_collect_pending_tasks_summary` + `_collect_recent_completions_summary` + `_collect_upcoming_deadlines_summary` (3 sites) to consume helper.
4. Helper unit tests + parity tests asserting bit-for-bit identical query output to current inline implementations.
5. 8-Task-consumer regression suite green (per v1 task substrate canon).

### Parity discipline

Current inline implementations are **already operational at v1**. Path (ii) v2a-α is **pure refactor**: substitute inline query body with helper call producing identical SQL. Parity assertion shape:

- **Bit-for-bit output equivalence** — for a fixed substrate state, helper-mediated query returns identical row sequence as current inline query.
- **Test cohort** — fixture-seed N tasks across lifecycle states + visibility values + completion timestamps + due dates; call current-inline-query-path + helper-mediated-path; assert tuple-equality.
- **No behavior change**, no UX shift, no rendered-output change. Pulse + briefings users see identical content pre- and post-refactor.

### Close criterion

Path (ii) v2a-α closes when:
- Helper extension (or new helper per §C operator decision) shipped + unit-tested.
- 4 consumer sites (Pulse ×1 + briefings ×3) rewired to helper.
- Parity test cohort green (4 sites × N seeded states).
- 8-Task-consumer regression suite green.
- Type checks + import discipline green.
- STATE.md note added per Entry 4.

### Cardinality posture under path (ii)

Path (ii) v2a-α does **NOT** address producer-vs-consumer cardinality mismatch. Pulse + briefings continue to render rollup-task aggregate titles ("N items need review") verbatim because that IS what the substrate currently produces. Cardinality discussion defers to the deferred `_dq_*` migration arc per §F where it is the central architectural question.

### §D outcome

Path (ii) v2a-α close criterion **locked at investigation altitude** as helper-extension-and-consumer-rewire with bit-for-bit parity discipline. Operator confirms close criterion + §C operator decision (helper signature shape) before path (ii) dispatch drafts.

---

## §E — Cross-sub-arc dependency check (v2a-β / v2a-γ / v2c-α impact)

### Method

For each downstream sub-arc consumer cited in the prompt, verify: (1) does the consumer query the **task substrate** or the **legacy domain table**?; (2) does the producer ship rollup-per-job or per-record?; (3) does cardinality-mismatch generalize?

### v2a-β consumers

#### `_dq_ss_cert_triage` (`engine.py:664`)
**Substrate consumed:** `SocialServiceCertificate` direct query, NOT task substrate (lines 678–686). Filter: `company_id == user.company_id` AND `status == "pending_approval"`. Order: `generated_at.asc()`. Cardinality: **per-cert-row**.

**Producer:** `social_service_certificate_service.py:165–175` creates task with `provenance_ref_type="social_service_certificate"`, `provenance_ref_id=cert.id` — **per-cert** task (1 task per SS cert).

**Generalization:** Producer (per-cert) ALIGNS with consumer (per-cert-domain-row). Migration to task substrate would replace `db.query(SocialServiceCertificate)` with task-substrate query keyed by `provenance_kind` + `provenance_ref_type="social_service_certificate"`. Cardinality preserved 1:1. NO cardinality-mismatch in v2a-β for SS cert.

#### `_dq_safety_program_triage` (`engine.py:1250`)
**Substrate consumed:** `SafetyProgramGeneration` direct query (lines 1273–1275). Filter: `status == "pending_review"`. Cardinality: **per-generation-row**.

**Producer:** `safety_program_generation_service.py:185–199` creates task with `provenance_ref_type="safety_program_generation"`, `provenance_ref_id=gen.id` — **per-gen** task.

**Generalization:** Producer ALIGNS with consumer. NO cardinality-mismatch.

#### `_dq_catalog_fetch_triage` (`engine.py:1320`)
**Substrate consumed:** `UrnCatalogSyncLog` direct query (lines 1334–1340). Filter: `publication_state == "pending_review"`. Cardinality: **per-sync-log-row**.

**Producer:** `catalog_fetch_adapter.py:263–273` creates task with `provenance_ref_type="urn_catalog_sync_log"`, `provenance_ref_id=new_log.id` — **per-sync-log** task.

**Generalization:** Producer ALIGNS with consumer. NO cardinality-mismatch.

#### `_dq_email_unclassified_triage` (`engine.py:1363`)
**Substrate consumed:** delegates to `classification.list_unclassified` helper (line 1373); queries `email_messages` table indirectly via that helper. NOT task substrate.

**Producer:** `classification/dispatch.py:388–395` creates task with `provenance_ref_type="workflow_email_classification"`, `provenance_ref_id=row.id` — **per-classification-row** task (1 task per unclassified email cascade exhaustion).

**Generalization:** Producer per-row. Consumer per-email-message-row. If consumer migrated to task substrate, producer's per-classification-row cardinality matches. NO cardinality-mismatch.

### v2a-γ consumers

#### `_dq_month_end_close_triage` (`engine.py:839`)
**Substrate consumed:** `AgentJob` direct query (lines 853–861). Filter: `job_type == "month_end_close"` AND `status == "awaiting_approval"`. Cardinality: **per-job** (explicitly documented in docstring lines 843–847: "ONE-ITEM-PER-JOB: the whole AgentJob in awaiting_approval is the decision").

**Producer:** `base_agent.py:376–397` creates rollup task with `provenance_ref_type="agent_job"`, `provenance_ref_id=self.job_id` — **per-job** rollup task.

**Generalization:** Producer ALIGNS with consumer. month_end_close is the ONE AgentJob queue where the rollup shape is canonical because per-anomaly review is explicitly out of scope (anomalies are sub-context, not triageable). NO cardinality-mismatch for month_end_close.

#### `_dq_workflow_review` (`engine.py:1378`)
**Substrate consumed:** `WorkflowReviewItem` direct query (lines 1392–1399). Filter: `company_id == user.company_id` AND `decision IS NULL`. Cardinality: **per-review-item-row**.

**Producer:** `workflow_engine.py:835` creates task with `provenance_ref_type="workflow_review_item"`, `provenance_ref_id=item.id` — **per-review-item** task.

**Generalization:** Producer ALIGNS with consumer. NO cardinality-mismatch.

### v2c-α (workflow-engine-adjacent refinement)

v2c-α extends `task_routing_rule` substrate (escalation routing mode) + `workflow_engine` action handler registry (3 new node handlers: cancel_task, update_task, query_tasks per phasing §3.4). Substrate extension, NOT consumer migration. Cardinality framing does not apply at v2c-α altitude — escalation routing is about WHICH user a task is assigned to, not how many tasks are created. Workflow nodes operate on existing tasks (cancel/update/query) at task-id altitude.

**Verification:** `workflow_engine.py:1219–1226` shows existing workflow-step task creation pattern with `provenance_ref_type="workflow_run"`, `provenance_ref_id=run.id` — per-run task. v2c-α's 3 new node handlers consume this substrate; they don't create new cardinality patterns.

### Cross-sub-arc summary

| Sub-arc | Producer cardinality | Consumer cardinality | Mismatch? |
|---|---|---|---|
| **v2a-α (cash_receipts)** | per-job (rollup) | per-anomaly | **YES** |
| **v2a-α (ar_collections)** | per-job (rollup) | per-customer | **YES** |
| **v2a-α (expense_categorization)** | per-job (rollup) | per-vendor-bill-line | **YES** |
| **v2a-α (aftercare)** | per-job (rollup) | per-case | **YES** |
| v2a-β (ss_cert) | per-cert | per-cert | NO |
| v2a-β (safety_program) | per-gen | per-gen | NO |
| v2a-β (catalog_fetch) | per-sync-log | per-sync-log | NO |
| v2a-β (email_unclassified) | per-classification | per-classification | NO |
| v2a-γ (month_end_close) | per-job (rollup) | per-job | NO |
| v2a-γ (workflow_review) | per-review-item | per-review-item | NO |
| v2c-α | substrate-extension, not consumer-migration | n/a | n/a |

### Phase 4 re-adjudication trigger status

**Cardinality-mismatch is LIMITED to v2a-α cluster (4 queues), DOES NOT generalize to v2a-β/γ.** The mismatch is exclusively at the **AgentAnomaly cohort producer pattern** (`base_agent.py:_create_substrate_task` lines 376–397) — that producer emits 1 rollup task per AgentJob regardless of anomaly count. The aftercare producer mirrors this rollup shape independently.

v2a-β/γ producers all ship per-record tasks aligned with their `_dq_*` consumer cardinality. The Phase 4 Adjudication 1 Option (b) sub-arc grouping (AgentAnomaly cluster as v2a-α) **already cleanly isolates** the cardinality-mismatch problem to one sub-arc. The grouping itself does NOT need re-adjudication.

**§E outcome: Phase 4 re-adjudication trigger does NOT fire.** Cardinality-mismatch is sub-arc-local to v2a-α. v2a-β and v2a-γ retain their original Phase 4 scope. v2c-α retains its original Phase 4 scope. Phase A close criterion shape requires revision (§G) but NOT because of cross-sub-arc cardinality generalization.

---

## §F — Deferred `_dq_*` migration arc identity per Entry 3

### Entry 3 framing

Per DECISIONS.md 2026-05-27 Entry 3 (Deferral-tracking meta-pattern): deferred work needs **explicit naming + signal-trigger framing**. Anti-signals per Entry 2 (LOC / count / time / preference / aesthetic-completeness / sunk-cost) explicitly rejected.

The deferred work: migrate the 4 AgentAnomaly-cluster `_dq_*` consumer-side read paths from their current legacy-domain-query implementations (querying `AgentAnomaly` / `AgentJob` directly) to the task substrate. This requires either (a) producer-side refactor from rollup-per-job to per-anomaly task creation, OR (b) consumer-side adaptation to read rollup tasks + denormalize anomaly sub-data, OR (c) a different architectural approach surfaced during the deferred arc's own investigation.

Path (ii) v2a-α explicitly does NOT close this work; the cardinality-mismatch problem is the central architectural question of the deferred arc, not path (ii).

### Candidate identifiers

#### Candidate F1 — `v2a-δ` (new sibling sub-arc under v2a)

**Rationale:** Sibling of v2a-α/β/γ at same altitude. Names the AgentAnomaly cohort `_dq_*` migration as its own sub-arc.

**Phase 4 sequencing implication:** Phase 4 §3.3 sub-arc decomposition table grows from 4 sub-arcs to 5. Phase A total: 5 sub-arc identities (3 v2a + v2a-δ + 1 v2c). Or Phase A excludes v2a-δ (per default-recommendation of substrate-stability-before-refinement); v2a-δ becomes the FIRST post-Phase-A sub-arc.

**Operator-observable signal:** "Sunnycrest accounting describes the cash-receipts / ar-collections / expense-categorization / aftercare triage queues as separate places to check rather than one unified work surface" (extends phasing §5.2 anchor) — when this signal fires post-Phase-A, v2a-δ dispatches with its own pre-arc investigation tackling the cardinality-mismatch architecture decision.

#### Candidate F2 — `v2a-α-completion` (suffix-naming preserving v2a-α identity)

**Rationale:** Names the deferred work as completion of v2a-α's originally-framed scope. Preserves the lineage that path (ii) is a partial v2a-α delivery, with the rest scheduled for completion later.

**Phase 4 sequencing implication:** No new sub-arc identity. v2a-α ships as path (ii) at v2a-α dispatch; v2a-α-completion ships later with its own signal trigger. Operator-confirm gate frequency unchanged from Phase 4 §3.2 Option (b) recommendation (6 sub-arcs total).

**Operator-observable signal:** Same as Candidate F1.

**Caveat:** Risks operator confusion ("did v2a-α ship or not?"). The suffix implies same-arc-shape, but v2a-α-completion needs its own investigation per Entry 23 (the cardinality decision is architectural-altitude, not refactor-altitude).

#### Candidate F3 — `v2c-β` (folds into v2c refinement scope)

**Rationale:** v2c is workflow-engine-adjacent refinement; the AgentAnomaly producer pattern (`base_agent.py:_create_substrate_task`) is workflow-engine-adjacent. Folding the deferred work into v2c places it in the right substrate-shape cluster.

**Phase 4 sequencing implication:** Phase 4 §2.2 Phase A v2c subset (candidates 1 + 2: escalation_chain + workflow nodes) excludes v2c-β by design. Phase A close shape unchanged. v2c-β dispatches post-Phase-A.

**Caveat:** v2c's existing identity is "workflow-engine-adjacent refinement (escalation routing + workflow node handlers)" per phasing §2.2. The deferred work is consumer-side `_dq_*` migration + producer-side cardinality decision — substrate-shape is closer to v2a than v2c. Folding into v2c dilutes v2c's coherence.

#### Candidate F4 — `v2e` (new top-level Phase B sibling)

**Rationale:** Defers entirely outside Phase A. Names the deferred work as its own Phase A successor / Phase B sibling.

**Phase 4 sequencing implication:** Phase A unchanged. Phase B framing per phasing §4.1 is Workflow Builder rebuild — a different architectural decision. v2e becomes a third Phase-altitude work-stream alongside Phase B + Phase C.

**Caveat:** Phase A/B/C structure per phasing §4 is operator-observable workflow-shape arcs (Workflow Builder, Document Builder). v2e is substrate-consumer-migration, not workflow-shape rebuild. Phase-altitude naming dilutes the Phase A/B/C semantic.

### §F outcome — 2 candidates surfaced with operator-decision pivot

**Recommendation tier:** Candidate F1 (`v2a-δ`) + Candidate F2 (`v2a-α-completion`) are the cleanest fits per Entry 3 explicit-naming discipline.

- **F1 (`v2a-δ`)** — preserves sub-arc-altitude clarity; each sub-arc has distinct scope; operator-observable signal frames "when does this dispatch" cleanly.
- **F2 (`v2a-α-completion`)** — preserves v2a-α lineage; signals that path (ii) is partial delivery of original v2a-α intent.

F3 (`v2c-β`) and F4 (`v2e`) surfaced for completeness but carry coherence-dilution caveats.

**Operator decides at investigation review gate.** The arc identity selection affects how Phase 4 §3.3 sub-arc table updates, how STATE.md narrative refers to the deferred work, and how the dispatched arc's investigation framing references its predecessor.

---

## §G — Phase A close criterion revision implications

### Original Phase A close criterion (phasing §3.3 + §6)

> 4 sub-arc commits land + v2a stable across 10 queues + v2c-α stable + 8-Task-consumer regression green + STATE.md close note

### Revision per path (ii) v2a-α reframe

**v2a-α scope narrows** from "migrate 4 AgentAnomaly-cluster consumer `_dq_*` to task substrate" to "ship helper + extend Pulse/briefings consumers". The "stable across 10 queues" claim no longer applies — v2a-α's 4 queues remain on legacy domain queries; only 6 queues (v2a-β's 4 + v2a-γ's 2) migrate during Phase A. The deferred 4 (v2a-δ or chosen identity per §F) close their own arc post-Phase-A.

### Revised Phase A close criterion candidate

> 4 sub-arc commits land + v2a-α (helper-and-consumer-extension) stable + v2a-β stable (4 queues migrated to task substrate) + v2a-γ stable (2 queues migrated) + v2c-α stable (escalation routing + 3 workflow nodes) + 8-Task-consumer regression green + Pulse + briefings parity tests green + STATE.md close note + deferred AgentAnomaly-cluster `_dq_*` migration arc identity documented per Entry 3

### Phase A scope reduction

| Sub-arc | Original phasing §3.3 scope | Path (ii) revised scope |
|---|---|---|
| v2a-α | 4 queue `_dq_*` migrations | helper + Pulse(1) + briefings(3) rewires |
| v2a-β | 4 queue `_dq_*` migrations | unchanged |
| v2a-γ | 2 queue `_dq_*` migrations | unchanged |
| v2c-α | escalation_chain + 3 workflow nodes | unchanged |
| **Phase A** | 10 `_dq_*` migrations + 4 refinement | **6 `_dq_*` migrations + helper-and-extensions + 4 refinement** |

### Phase B/C boundaries

Phase B (Workflow Builder rebuild) + Phase C (Document Builder rebuild) per phasing §4 are forward-reference framings; their dispatch signals (phasing §5.2 + §4.3) are unaffected by path (ii) reframe. Q-B1 boundary preserved.

### Sub-arc sequencing

Phase 4 §3.5 default-recommendation (α → β → γ → v2c-α; substrate-shape complexity ascending) is **revised under path (ii)** because v2a-α path (ii) is now LOWER complexity than v2a-β/γ (pure refactor with parity discipline vs `_dq_*` migration with cardinality preservation). Path (ii) v2a-α may now ship FIRST as the warm-up arc, OR be deferred AFTER v2a-β/γ as a consolidation pass once consumer-extension shape is more clearly informed by v2a-β/γ migrations. Operator decision.

### §G outcome

Phase A close criterion revision shape surfaced. Operator confirms revised shape at investigation review gate. Phase B / Phase C boundaries unchanged. Sub-arc sequencing within Phase A optionally revisitable per path (ii) reframe.

---

## Investigation closing summary

### Audit-shape signals fired
- Phase 0 audit citation drift at `task_summary_builder.py:43` (actual: `data_sources.py:293/366/416`). Substrate IS operationally consumed; NOT a STOP-trigger material divergence.
- Original prompt cited `_build_tasks_item` at `personal_layer_service.py:111`; actual line 95. Citation precision drift only.
- Producer cardinality (rollup-per-job at AgentAnomaly cohort + aftercare) verified against producer code (`base_agent.py:376-397` + `aftercare_adapter.py:214-239`).
- Cross-sub-arc cardinality verification confirms mismatch is sub-arc-local to v2a-α; v2a-β/γ producers + consumers ALIGN per-record.

### Material-divergence triggers fired
- **§C helper signature substantively inadequate** — proposed `query_open_tasks_by_provenance` signature is provenance-keyed; Pulse + briefings consumption is assignee-keyed. The two signatures are orthogonal. Two paths surfaced (extend existing `list_task_details_for_company` vs new sibling helper); operator decision required before path (ii) dispatch drafts.

### Triggers that did NOT fire
- Phase 0 audit gap on Pulse consumption (substrate IS consumed at verified line 95).
- Phase 4 re-adjudication trigger (cardinality-mismatch sub-arc-local).
- Investigation word count over-synthesis ceiling (this deliverable ≈ 3,800 words, within 2,500-4,000 expected band).

### Path forward
1. Operator reviews investigation.
2. Operator decides §C helper-signature path (C1 extend existing vs C2 new sibling).
3. Operator decides §F deferred arc identity (F1 v2a-δ vs F2 v2a-α-completion vs others).
4. Operator confirms revised §G Phase A close criterion shape.
5. Operator confirms sub-arc sequencing within Phase A (path (ii) v2a-α first vs last).
6. Path (ii) v2a-α build prompt drafts post-operator-confirm.

### Locked disciplines confirmed
- No canon edits.
- No STATE.md edits.
- No production code touched.
- No git operations.
- No Phase 4 re-adjudication (Section E surfaced trigger status only; trigger did NOT fire).
- No Phase 5 §2.A revision drafting.
- No build dispatch.
- Persistent storage at this path per Entry 4.
- Citation discipline per Entry 1 throughout.
- 114 stale Playwright screenshot deletions untouched.
- Q-B1 boundary preserved.
- Phase B/C boundaries preserved.
- All Phase 4 adjudications preserved at sub-arc altitude.
- Verification-altitude grounding throughout.

### Path to deliverable

`docs/investigations/task_substrate_v2a_alpha_path_ii_investigation.md`

### Next-gate handoff

Operator reviews investigation + confirms §C operator decision + §F arc identity + §G revised Phase A close criterion shape + sub-arc sequencing decision before revised v2a-α path (ii) dispatch drafts.
