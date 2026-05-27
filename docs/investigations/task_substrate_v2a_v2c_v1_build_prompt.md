# Task Substrate v2a + v2c — Phase A v1 Build Prompt

> Read-only Phase 5 deliverable closing the v2a+v2c task substrate completion investigation. Dispatches against Phase 4 phasing recommendation at `docs/investigations/task_substrate_v2a_v2c_phasing.md` (HEAD `cce834d`, 2026-05-27) and Phase 0 audit at `docs/investigations/task_substrate_v2a_v2c_phase0_audit.md`. Locks per-sub-arc execution context for downstream build dispatch.
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables (Entry 4).

## Phase 5 metadata

- **Arc context:** v2a + v2c task substrate completion investigation, Phase 5 of 5 (Phase 0 audit closed → Phase 4 phasing closed + adjudications locked → Phase 5 build prompt drafting → per-sub-arc downstream build dispatch).
- **HEAD at drafting:** `cce834d` (Canon-update arc close — 35 DECISIONS.md entries + 10 canon-doc edits). 114 stale Playwright screenshot/video deletions in working tree stay UNTOUCHED throughout Phase A.
- **Drafting date:** 2026-05-27
- **Bounded decision (Entry 31):** produce Phase A v1 build prompt deliverable locking per-sub-arc execution context across the 4 sub-arc identities; surface material-divergence protocol; surface acknowledgement format; lock NO production code; lock NO canon edits; lock NO STATE.md edits; lock NO build dispatch (per-sub-arc downstream dispatch follows operator confirmation).
- **Adjudications locked at Phase 4 close:**
  - **Adjudication 1 (sub-arc decomposition):** Option (b) — collapse v2a-δ (email_unclassified) into v2a-β (per-record cluster). Phase A scopes 4 sub-arc identities: v2a-α / v2a-β / v2a-γ / v2c-α.
  - **Adjudication 2 (v2c subset):** Phase A includes candidates 1 (escalation routing) + 2 (additional workflow nodes); defers candidates 3 (6th plugin), 4 (subscriber persistent log), 5 (task templates), 6 (dual-write unification) to post-Phase-A signal-driven dispatch.
  - **Adjudication 3 (`description` field canonical-substrate):** original substrate (AgentAnomaly.description) authoritative at producer-side; task substrate (VaultItem.description) inherits at create-time verbatim; ongoing edits adjudicated per task lifecycle (operator edits via task surface land on task substrate; AgentAnomaly.description becomes legacy producer-side write column).
  - **Audit Q4 (forensic-fallback retirement timing):** original-substrate query paths persist as forensic-fallback indefinitely during v2a transition; retirement deferred until candidate 6 (dual-write unification) ships post-Phase-A per operator signal.
  - **Audit Q5 (task templates plugin contract impact):** deferred per investigation-first pattern; dispatches when "operators author same task creation pattern three+ times across workflows" signal surfaces post-Phase-A.
- **Operator framing locks preserved:** v2b family portal OUT-OF-SCOPE; September Wilbert demo schedule explicitly NOT a signal; building-correctness-over-schedule-pressure per Entry 2 anti-signal canon; Q-B1 boundary preserved per Entry 3.
- **Lineage reference:** Phase 0 audit + Phase 4 phasing are upstream deliverables; this build prompt is the downstream-dispatch substrate.

---

## §1. Phase A overview + sub-arc sequencing

### 1.1 Phase A bounded decision (Entry 31)

Phase A's bounded decision = **migrate consumer-side triage read paths across all 10 v2a queues to task substrate (10 `_dq_*` handler migrations) AND ship workflow-engine-adjacent refinement candidates 1 + 2 (escalation_chain routing mode + 3 workflow node action handlers).** Phase A closes when all 4 sub-arc commits land, v2a stable across 10 queues, v2c-α stable, 8-Task-consumer regression suite green at every sub-arc commit, STATE.md close note appends at v2c-α final commit.

### 1.2 Sub-arc dispatch sequence

Per Adjudication 1 Option (b) + Phase 4 §3.5 default-recommendation (substrate-stability-before-refinement per Entry 23 + Entry 30 substrate-shape grouping):

```
v2a-α  →  v2a-β  →  v2a-γ  →  v2c-α
```

Sequencing rationale:
- **v2a-α first** — AgentAnomaly cluster is the largest substrate-shape-coherent grouping (4 queues sharing producer shape + canonical mirror pattern per Phase 0 audit E.2). Migrating it first establishes the read-path migration pattern that v2a-β + v2a-γ inherit.
- **v2a-β second** — per-record + classification-cascade cluster (4 queues with pre-existing pending-state column or audit-row equivalent). Safety_program inside this cluster needs AI-generation-content-invariant parity per Phase 8d.1; v2a-α's pattern needs to be in hand before v2a-β's heaviest member ships.
- **v2a-γ third** — per-job + per-review-item cluster (2 queues with distinct cardinality from v2a-α/β). Smallest cluster; closes v2a's consumer-side read-path migration before v2c-α refinement opens.
- **v2c-α last** — workflow-engine-adjacent refinement benefits from full v2a stability for signal-driven scope adjustment per Entry 23 build-prompt-spec failure pattern. Refinement-shape after substrate-stability per Entry 30.

### 1.3 Phase A close criterion

- All 4 sub-arc commits land at HEAD (single-commit-at-arc-close for v2a-α + v2a-γ; multi-commit-within-arc-identity for v2a-β + v2c-α).
- v2a stable across all 10 queues: consumer-side reads from task substrate; bit-for-bit parity verified per sub-arc; cardinality preservation per queue; operationally-idempotent invariant preserved per Entry 35.
- v2c-α stable: escalation_chain routing operational; 3 workflow node action handlers operational; service-method-registry per Phase 8b service-method-registry canon.
- 8-Task-consumer regression suite green at every sub-arc commit (existing 8 producer sites verified unchanged per Phase 0 audit Section A).
- STATE.md update appends at v2c-α final commit (per Phase 4 §6.2 narrative discipline).
- Q4 forensic-fallback documented as indefinite-preservation pending candidate 6 dispatch (post-Phase-A signal-driven).
- Q5 task templates plugin contract investigation deferred per signal-driven post-Phase-A pattern.

### 1.4 Canon-anchor

HEAD `cce834d` at Phase 5 drafting. Per-sub-arc downstream builds anchor against their own dispatch HEAD (which may advance per intermediate sub-arc commits). Phase A operates entirely against the canon state at HEAD `cce834d` plus its own accumulating sub-arc commits.

---

## §2. Per-sub-arc execution context

### §2.A — Sub-arc v2a-α (AgentAnomaly cluster)

**Members (4 queues):** cash_receipts_matching_triage / ar_collections_triage / expense_categorization_triage / aftercare_triage

#### §2.A.1 Bounded decision (Entry 31)

**Migrate 4 AgentAnomaly-cluster consumer-side `_dq_*` read paths from `engine.py` to task substrate via new query helper; preserve cardinality semantics (per-anomaly for cash_receipts/expense_categorization, per-customer fan-out for ar_collections, per-case for aftercare); preserve canonical-substrate adjudications per Phase 0 audit E.2 (severity → priority mapping; resolved/resolved_at → task substrate authoritative going forward; AgentAnomaly stays authoritative for source-business-state semantics). v2a-α closes when AgentAnomaly cluster consumer-side reads migrate to task substrate via new query helper + dual-write transitional closure verified bit-for-bit parity across cash_receipts_matching / ar_collections / expense_categorization / aftercare.**

#### §2.A.2 Substrate scope

**What changes:**
- **NEW substrate helper:** `task_service.query_open_tasks_by_provenance` at `backend/app/services/tasks/service.py` — new function shipping BEFORE consumer migrations within single commit (substrate dependency for consumer-side queries). Consumer-side `_dq_*` handlers operate against the helper (no inline SQLAlchemy compose per consumer). Specification at §2.A.3 below.
- `_dq_cash_receipts_matching_triage` (`engine.py:720`) — migrate from `AgentAnomaly ⨝ AgentJob` (CRITICAL/WARNING/INFO sort) read to task substrate via the new helper, filtering with `provenance_kind='anomaly_detection'` + `provenance_ref_type='agent_job'` and scoping to cash_receipts AgentJob via post-query `job_type='cash_receipts_matching'` filter.
- `_dq_ar_collections_triage` (`engine.py:905`) — migrate from `AgentAnomaly ⨝ Customer` (per-customer fan-out) read to task substrate via the new helper, filtering with `provenance_kind='anomaly_detection'` + `provenance_ref_type='agent_job'` and scoping by AgentJob `job_type='ar_collections'`; preserve per-customer fan-out fidelity (each customer's anomaly = one task; Phase 8c canon for cardinality).
- `_dq_expense_categorization_triage` (`engine.py:1016`) — migrate from `AgentAnomaly` (quiet-run gating) read to task substrate via the new helper, filtering with `provenance_kind='anomaly_detection'` + `provenance_ref_type='agent_job'` and scoping by AgentJob `job_type='expense_categorization'`; preserve quiet-run + per-line cardinality.
- `_dq_aftercare_triage` (`engine.py:1134`) — migrate from `AgentAnomaly` (funeral cohort) read to task substrate via the new helper, filtering with `provenance_kind='workflow_step'` + `provenance_ref_type='agent_job'` and scoping by AgentJob `job_type='fh_aftercare_7day'`; producer-side `aftercare_adapter.py:217-218` already supplies `customer_communication_task` task_type_key per Phase 8d.

**What stays unchanged:**
- Producer-side task creation paths (8 producer sites including aftercare adapter at `workflows/aftercare_adapter.py:217-218`; cash_receipts/ar_collections/expense_categorization via `agents/base_agent.py:360,380` `job_type` discriminator).
- AgentAnomaly rows continue writing (producer-side dual-write per Phase 8b operational coexistence canon).
- Original-substrate query paths persist as forensic-fallback (no retirement at v2a-α per Adjudication Q4).
- 6 v1 subscribers fire on task creation events unchanged.
- 5 task type behavior plugins unchanged.
- Routing resolver (direct_user + round_robin) unchanged.
- Pulse Personal layer, briefings, Focus integration unchanged at substrate level (the rendered surfaces now consume task substrate via existing v1 wiring; no Pulse/briefings code changes required by v2a-α).

#### §2.A.3 Substrate helper specification (NEW)

Per DECISIONS.md 2026-05-27 — Substrate-minimal-default canon (helper signature stays minimal at v2a-α first-consumer needs) + DECISIONS.md 2026-05-27 — Substrate-prescience-meets-second-consumer pattern (helper extends as v2a-β/γ second-consumer needs surface at downstream sub-arcs).

**Signature** (canonical types verified against `create_task_with_provenance` at `backend/app/services/tasks/service.py:145-167` + CLAUDE.md §5 canonical schema: "All IDs are String(36) UUIDs"):

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
    """Query open tasks filtered by provenance and optional lifecycle state.

    Filters DB-side per provenance_kind (required) + optional provenance_ref_type +
    optional provenance_ref_id + optional lifecycle_states. Returns matching
    TaskDetails (full ORM hydration, not dicts).

    v2a-α first-consumer canonical use:
        - Filter by provenance_kind alone for cluster-wide queries
        - Filter by provenance_kind + provenance_ref_type for substrate-shape-coherent queries
        - Filter by all three for single-source queries

    Lifecycle states default: returns tasks NOT in terminal states (done/cancelled
    for action shape; acknowledged/dismissed for reminder shape). Explicit
    lifecycle_states parameter overrides default.
    """
```

**Behavior:**
- DB-side filter via SQLAlchemy compose (no Python-side post-filtering)
- Composite-key idempotency invariant preserved per DECISIONS.md 2026-05-27 — Test isolation discipline for idempotency-load-bearing substrate
- Returns `TaskDetails` instances (full ORM hydration; not dicts)
- Filter discipline: `provenance_kind` required; other args optional + filtered when present
- Type signatures match `create_task_with_provenance` canonical pattern (`company_id: str`, etc.)
- Visibility filter applied at operator level per existing `list_task_details_for_company` precedent (line 453)

**Test coverage:**
- Per-filter combination tests (provenance_kind alone; provenance_kind + provenance_ref_type; all three; with lifecycle_states override)
- Idempotency tests per DECISIONS.md 2026-05-27 — Test isolation (uuid-randomized provenance_ref_id per test)
- Cardinality verification (returns correct count per filter shape; matches expected row count from seeded test data)
- Symmetry audit per DECISIONS.md 2026-05-27 — Runtime-Pydantic-TypeScript symmetry audit for any new exported types

**LOC envelope:** helper implementation ~100-150 LOC + tests ~50-100 LOC.

**Substrate-minimal-default discipline:** v2a-α ships helper with current parameter set only. Future extensions per Entry 17 substrate-prescience-meets-second-consumer:
- v2a-β second-consumer signal may surface need for additional filter dimensions (e.g., by event_kind for cascade-classification consumers); extension is additive parameter with default behavior preserving first-consumer correctness
- v2a-γ signal may surface need for ordering parameters (per-job/per-review-item shapes); extension follows same discipline

The helper does NOT pre-emptively ship parameters anticipating future consumer needs. Substrate-prescience-meets-second-consumer canon: extension cost at second-consumer landing is acceptable; pre-emption produces drift-dormant substrate per Built-but-dormant canon.

#### §2.A.4 4-decision matrix per consumer surface (Entry 23)

**Consumer #1 — `cash_receipts_matching_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_cash_receipts_matching_triage` (`engine.py:720`) migrates from `db.query(AgentAnomaly).join(AgentJob).filter(job_type='cash_receipts_matching', resolved=False)` to `task_service.query_open_tasks_by_provenance(db, company_id=company_id, provenance_kind='anomaly_detection', provenance_ref_type='agent_job')` filtered post-query to scope by AgentJob `job_type='cash_receipts_matching'` (via the `provenance_ref_id` denormalized from agent_job_id at producer side). Returns `TaskDetails` ordered by `priority DESC, created_at ASC` (urgent/high/normal/low maps to CRITICAL/WARNING/INFO/INFO). |
| (2) Downstream behavior | Triage workspace renders 1 row per open task; Pulse Personal layer reads task substrate via v1 `_build_tasks_item` (already operational); briefings consume via v1 wiring. Read-shape preserved bit-for-bit at API response level. |
| (3) Producer-supplied context | Producer at `agents/base_agent.py:360` writes `provenance_kind="anomaly_detection"` + `provenance_ref_type="agent_job"` (line 380) + `provenance_ref_id=<agent_job_id>`. `task_details.source_data` JSONB carries AgentAnomaly columns verbatim at create time (severity, anomaly_type, description, amount, related_record_id) per Phase 8b discipline. |
| (4) Subscriber mechanics | `audit_writer` + `notification_dispatcher` + `briefings_invalidator` + `pulse_invalidator` fire on task creation (operational at v1 since B2 `a400d1b`). `workflow_resumer` + `focus_closer` no-op for this provenance shape. No new subscribers. |

**Consumer #2 — `ar_collections_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_ar_collections_triage` (`engine.py:905`) migrates from `db.query(AgentAnomaly).join(Customer).filter(job_type='ar_collections', resolved=False)` to `task_service.query_open_tasks_by_provenance(db, company_id=company_id, provenance_kind='anomaly_detection', provenance_ref_type='agent_job')` filtered post-query to scope by AgentJob `job_type='ar_collections'`. Per-customer fan-out preserved at producer side (one task per anomaly = one task per customer drafted-email pair per Phase 8c canon). |
| (2) Downstream behavior | Triage workspace renders 1 row per customer-with-pending-collection; `send_customer_email` / `skip_customer` / `request_review_customer` triage actions write to AgentAnomaly.resolved AND task `current_state='done'` during transition (canonical: task substrate going forward per Phase 0 audit E.3). |
| (3) Producer-supplied context | Producer at `agents/base_agent.py:360` writes `provenance_kind="anomaly_detection"` + `provenance_ref_type="agent_job"` (line 380) + `provenance_ref_id=<agent_job_id>`. `task_details.source_data` carries customer_id + draft_email_body + collection_anomaly metadata. Per Phase 8c fan-out fidelity discipline. |
| (4) Subscriber mechanics | Same as #1 (audit_writer + notification_dispatcher + briefings_invalidator + pulse_invalidator fire; workflow_resumer + focus_closer no-op). |

**Consumer #3 — `expense_categorization_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_expense_categorization_triage` (`engine.py:1016`) migrates from `db.query(AgentAnomaly).filter(job_type='expense_categorization', resolved=False)` to `task_service.query_open_tasks_by_provenance(db, company_id=company_id, provenance_kind='anomaly_detection', provenance_ref_type='agent_job')` filtered post-query to scope by AgentJob `job_type='expense_categorization'`. Quiet-run gating (anomalies created only on unresolved categorization) preserved at producer side. |
| (2) Downstream behavior | Triage workspace renders 1 row per uncategorized line; `approve_line(category_override=None)` / `reject_line` / `request_review_line` triage actions write categorization decision + transition task state. |
| (3) Producer-supplied context | Producer at `agents/base_agent.py:360` writes `provenance_kind="anomaly_detection"` + `provenance_ref_type="agent_job"` (line 380) + `provenance_ref_id=<agent_job_id>`. `task_details.source_data` carries expense_line_id + ai_suggested_category + confidence_score per Phase 8c. |
| (4) Subscriber mechanics | Same as #1. |

**Consumer #4 — `aftercare_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_aftercare_triage` (`engine.py:1134`) migrates from `db.query(AgentAnomaly).filter(job_type='aftercare')` to `task_service.query_open_tasks_by_provenance(db, company_id=company_id, provenance_kind='workflow_step', provenance_ref_type='agent_job')` filtered post-query to scope by AgentJob `job_type='fh_aftercare_7day'`. Producer-side `aftercare_adapter.py:214` already creates `customer_communication_task` task_type per Phase 8d. |
| (2) Downstream behavior | Triage workspace renders 1 row per eligible fh_case (service_date + 7 days == today); `send` / `skip` / `request_review` triage actions dispatch managed `email.fh_aftercare_7day` template + transition task state. |
| (3) Producer-supplied context | Producer at `aftercare_adapter.py:217` writes `provenance_kind="workflow_step"` + `provenance_ref_type="agent_job"` (line 218) + `provenance_ref_id=<agent_job_id>`. `task_details.source_data` carries fh_case_id + service_date + aftercare_template_key. `task_type_key='customer_communication_task'`; type behavior plugin already operational at v1. |
| (4) Subscriber mechanics | Same as #1 (audit_writer + notification_dispatcher + briefings_invalidator + pulse_invalidator). |

**Cluster-wide observation per Revision Finding 2:** All 4 v2a-α consumers share `provenance_ref_type='agent_job'` (AgentJob is canonical entity all 4 producers operate against); `provenance_kind` is the per-consumer discriminator within the cluster (3 use `'anomaly_detection'`; aftercare uses `'workflow_step'`). Per-consumer scoping within cluster happens at AgentJob `job_type` post-query filter.

#### §2.A.5 Parity discipline

Per Entry 13 (substrate-transition discipline) + Entry 24 (LOC calibration) + Entry 35 (test isolation):

- **Bit-for-bit parity** against legacy `_dq_*` read shape: per-consumer parity test asserts legacy original-substrate read AND new task-substrate read return functionally-equivalent result sets given identical pre-state (same row count, same ordering, same field values at API-response level).
- **Cardinality preservation per consumer:** per-anomaly (cash_receipts, expense_categorization), per-customer fan-out (ar_collections — Phase 8c canon), per-case (aftercare). Parity tests assert cardinality unchanged.
- **Forward-only discipline (Entry 13):** no backfill of pre-v1-B2 historical AgentAnomaly rows; pre-B2 rows remain readable only via forensic-fallback original-substrate paths.
- **Operationally-idempotent invariant (Entry 35):** parity tests use uuid-randomized provenance_ref_id per test; composite idempotency key `(provenance_kind + provenance_ref + event_kind)` partial-unique at schema layer; test isolation preserved.

#### §2.A.6 Locked disciplines

- No canon edits during build (Sonnet writes only to code/tests/migrations/STATE.md per CLAUDE.md §1 Documentation write permissions).
- Persistent storage for investigation findings if scope expansion surfaces (per Entry 4).
- 4-decision matrix verified upfront per consumer before migration begins.
- Runtime-Pydantic-TypeScript symmetry audit per Entry 33 for any evolving Pydantic schema touched (task_details emission shapes for cardinality preservation may evolve; verify symmetry).
- JSDOM-blind-spot discipline per Entry 34 for Pulse Personal layer / briefings rendering surfaces touched by v2a-α (rendering surfaces operational at v1; verify no JSDOM-only render path drift).
- 8-Task-consumer regression check at sub-arc commit (existing 8 producer sites stay unchanged per Phase 0 audit Section A).
- Forward-only discipline per Entry 13 (pre-v1-B2 historical state preserved as forensic-fallback per Q4).

#### §2.A.7 Commit shape (Entry 26 + Adjudication 1)

Single commit at sub-arc close. Template:

```
v2a-α: AgentAnomaly cluster consumer migration to task substrate

Migrate 4 _dq_* handlers (cash_receipts_matching / ar_collections /
expense_categorization / aftercare) from original-substrate AgentAnomaly
reads to task substrate via new query helper.

New substrate helper: task_service.query_open_tasks_by_provenance
(canonical signature: company_id: str + provenance_kind: str + optional
provenance_ref_type/provenance_ref_id/lifecycle_states; substrate-minimal
default per DECISIONS.md 2026-05-27 — Substrate-minimal-default canon).

Cluster-wide finding: 4 consumers share provenance_ref_type='agent_job';
provenance_kind discriminates per consumer (3 use 'anomaly_detection';
aftercare uses 'workflow_step').

- Per-consumer 4-decision matrix locked at Phase 5 §2.A.4
- Cardinality preserved (per-anomaly / per-customer fan-out / per-line / per-case)
- Canonical-substrate adjudications per Phase 0 audit E.2 (severity → priority;
  resolved/resolved_at → task substrate authoritative; AgentAnomaly stays
  authoritative for source-business-state semantics)
- Forensic-fallback original-substrate query paths preserved per Q4
- Helper test cohort + 4 consumer parity test cohort + idempotency tests
- 8-Task-consumer regression suite green; bit-for-bit parity verified per consumer

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

#### §2.A.8 LOC envelope

Per Phase 4 §3.3 + §7: **~1,200-1,950 LOC** across 4 consumer migrations + new substrate helper + cross-queue parity test cohort + helper test cohort. Within Entry 24 calibration band; modest band-edge overshoot canonically-acceptable per honest-cost discipline (substrate helper is required infrastructure not speculative scope). Phase A cumulative envelope shifts: ~3,950-6,450.

#### §2.A.9 Close criterion verification

- Helper passes per-filter combination tests (provenance_kind alone; provenance_kind + provenance_ref_type; all three; with lifecycle_states override).
- Helper passes idempotency tests per DECISIONS.md 2026-05-27 — Test isolation discipline.
- Helper passes symmetry audit per DECISIONS.md 2026-05-27 — Runtime-Pydantic-TypeScript symmetry audit.
- Backend pytest: 4 consumer-side parity test cohorts green; 8-Task-consumer regression suite green; idempotency tests green per Entry 35; Phase 0 audit Section A regression check green.
- Playwright E2E: each migrated consumer rendered from task substrate matches legacy rendering at API response level.
- Manual operator verification: 1 query per consumer surface (4 total) confirms operator-visible behavior unchanged in Pulse Personal layer + briefings.
- STATE.md update appends sub-arc completion note.

---

### §2.B — Sub-arc v2a-β (per-record + classification-cascade cluster)

**Members (4 queues):** safety_program_triage / catalog_fetch_triage / ss_cert_triage / email_unclassified_triage

#### §2.B.1 Bounded decision (Entry 31)

**Migrate 4 per-record + classification-cascade cluster consumer-side `_dq_*` read paths from `engine.py` to task substrate; preserve per-record cardinality semantics (per-run / per-sync-log / per-cert / per-classification-audit-row); preserve supersede semantics (catalog_fetch publication_state) AND AI-generation-content-invariant parity (safety_program per Phase 8d.1 canon — frozen-content parity, NOT byte-exact). Closes when 4 consumer handlers + per-queue parity tests + Playwright smoke green.**

#### §2.B.2 Substrate scope

**What changes:**
- `_dq_safety_program_triage` (`engine.py:1250`) — migrate from `SafetyProgramGeneration.status` enum read to task-substrate query; AI-generation-content-invariant parity per Phase 8d.1 (re-run AI = different bytes; same task lifecycle = parity).
- `_dq_catalog_fetch_triage` (`engine.py:1320`) — migrate from `UrnCatalogSyncLog.publication_state` enum read to task-substrate query; supersede semantics preserved (newer fetch marks older pending-review tasks as superseded).
- `_dq_ss_cert_triage` (`engine.py:664`) — migrate from `SocialServiceCertificate ⨝ SalesOrder/Customer` read to task-substrate query; producer at `social_service_certificate_service.py:162` already creates task per v1 substrate.
- `_dq_email_unclassified_triage` (`engine.py:1363`) — migrate from `WorkflowEmailClassification` audit-row read to task-substrate query; classification cascade exhaustion at `classification/dispatch.py:379` already creates task per v1.

**What stays unchanged:**
- Producer-side task creation paths (safety_program_generation_service.py:179; catalog_fetch_adapter.py:258; social_service_certificate_service.py:162; classification/dispatch.py:379).
- Original-substrate query paths persist as forensic-fallback.
- SafetyProgramGeneration.status / UrnCatalogSyncLog.publication_state / SocialServiceCertificate.status remain canonical for source-business-state semantics per audit E.3.
- 6 v1 subscribers unchanged.
- Workflow engine action handlers unchanged (catalog_fetch publish handler keeps signaling supersede via UrnCatalogSyncLog flag; mirror to task substrate).

#### §2.B.3 4-decision matrix per consumer surface (Entry 23)

**Consumer #5 — `safety_program_triage`** (AI-generation parity is heaviest in cluster)

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_safety_program_triage` migrates from `db.query(SafetyProgramGeneration).filter(status='pending_review')` to `task_service.query_open_tasks_by_provenance(db, company_id, provenance_kind='intelligence_observation', provenance_ref_prefix='safety_program_generation:')`. |
| (2) Downstream behavior | Triage workspace renders 1 row per pending_review SafetyProgramGeneration; `approve_generation` / `reject_generation` triage actions write to SafetyProgramGeneration.status (canonical for source-business-state per audit E.3) AND transition task state. AI question panel reads task substrate + related entities per Phase 8d.1. |
| (3) Producer-supplied context | `task_details.source_data` carries safety_program_generation_id + target_training_topic_id + osha_scrape_url + prior_safety_program_id (for year-over-year diff). PDF Document with presigned URL preserved per Phase 8d.1. |
| (4) Subscriber mechanics | audit_writer + notification_dispatcher + briefings_invalidator + pulse_invalidator fire on task creation. workflow_resumer + focus_closer no-op. |

**Consumer #7 — `catalog_fetch_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_catalog_fetch_triage` migrates from `db.query(UrnCatalogSyncLog).filter(publication_state='pending_review')` to task-substrate query; supersede semantics preserved (newer fetch invalidates older pending tasks via task substrate state transition to `cancelled`). |
| (2) Downstream behavior | Triage workspace renders 1 row per pending sync_log; `approve` triggers WilbertIngestionService.ingest_from_pdf (legacy service unchanged per Phase 8d); `reject` marks rejected. Task substrate mirrors publication_state transition. |
| (3) Producer-supplied context | `task_details.source_data` carries urn_catalog_sync_log_id + r2_archive_key + md5_hash + product_count. |
| (4) Subscriber mechanics | Same as #5. |

**Consumer #8 — `ss_cert_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_ss_cert_triage` migrates from `db.query(SocialServiceCertificate).join(SalesOrder).join(Customer)` to task-substrate query joined to cert + order + customer. |
| (2) Downstream behavior | Triage workspace renders 1 row per pending SS cert; existing approval/rejection paths preserved (canonical at SocialServiceCertificate.status per audit E.3); task substrate mirrors. |
| (3) Producer-supplied context | `task_details.source_data` carries ss_cert_id + sales_order_id + customer_id + funeral_home_id. |
| (4) Subscriber mechanics | Same as #5. |

**Consumer #10 — `email_unclassified_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_email_unclassified_triage` migrates from `db.query(WorkflowEmailClassification).filter(classification_tier='exhausted')` audit-row read to task-substrate query. Per Phase 0 audit Section E classification-cascade audit-row is the substrate; task is created on cascade exhaustion only. |
| (2) Downstream behavior | Triage workspace renders 1 row per unclassified email; manual classification actions transition task state + write classification decision to WorkflowEmailClassification (canonical for cascade audit). |
| (3) Producer-supplied context | `task_details.source_data` carries email_message_id + cascade_decision_trail + tier1_match + tier2_match + tier3_match (all NULL → cascade exhaustion). |
| (4) Subscriber mechanics | Same as #5. |

#### §2.B.4 Parity discipline

- **Bit-for-bit parity for #7 / #8 / #10** against legacy `_dq_*` read shape (per-record reads with pre-existing pending-state columns).
- **AI-generation-content-invariant parity for #5** per Phase 8d.1 canon: parity claim is "given the same frozen pre-approval staging state, both paths produce byte-identical field writes on the domain entities," NOT "AI re-runs produce identical bytes." Test pattern: seed SafetyProgramGeneration directly with pre-populated `generated_content` + `generated_html` + `pdf_document_id=NULL`; run approval through both paths; assert SafetyProgramGeneration + SafetyProgram writes match field-by-field. Never invoke Claude during parity test. Never assert on generated content bytes.
- **Supersede semantics for #7:** parity test asserts older pending sync_log tasks transition to cancelled when newer fetch arrives.
- **Cascade exhaustion semantics for #10:** parity test asserts task is created only when classification cascade truly exhausts (tier1 NULL AND tier2 NULL AND tier3 NULL).
- **Cardinality preservation per consumer:** per-run (#5), per-sync-log (#7), per-cert (#8), per-classification-audit-row (#10).

#### §2.B.5 Locked disciplines

- All disciplines from §2.A.5 inherited.
- **AI-generation-content-invariant parity discipline per Phase 8d.1** is the new addition for #5. Parity discipline is frozen-content parity per Phase 8d.1 §5.5.5; tests use seeded pre-populated content; never invoke Claude.
- Symmetry audit per Entry 33: task_details emission shape for #5 + #10 may carry novel JSONB fields (osha_scrape_url for #5; cascade_decision_trail for #10); verify runtime-Pydantic-TypeScript symmetry.
- JSDOM-blind-spot per Entry 34: AI question panel for #5 + classification UI for #10 are user-touched surfaces; verify no JSDOM-only render path drift.

#### §2.B.6 Commit shape (Entry 26 + Adjudication 1)

Multi-commit-within-arc-identity. Per Phase 8d.1 AI-parity discipline, safety_program ships as own commit before the other 3.

**Commit 1 — safety_program:**

```
v2a-β.1: safety_program consumer migration (AI-generation-content-invariant parity)

Migrate _dq_safety_program_triage (engine.py:1250) from
SafetyProgramGeneration.status enum read to task substrate.

- AI-generation-content-invariant parity per Phase 8d.1 §5.5.5:
  frozen-content parity, NOT byte-exact; tests seed pre-populated
  generated_content + generated_html; never invoke Claude
- SafetyProgramGeneration.status remains canonical for
  source-business-state semantics per audit E.3
- Forensic-fallback original-substrate query path preserved per Q4
- 8-Task-consumer regression suite green

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Commit 2 — per-record + classification-cascade trio:**

```
v2a-β.2: per-record + classification-cascade consumer migration

Migrate 3 _dq_* handlers (catalog_fetch / ss_cert / email_unclassified)
from original-substrate per-record reads to task substrate.

- Supersede semantics preserved for catalog_fetch (older pending tasks
  transition to cancelled on newer fetch)
- Cascade exhaustion semantics preserved for email_unclassified (task
  created only when tier1/tier2/tier3 all NULL)
- Source-business-state canonical at UrnCatalogSyncLog.publication_state /
  SocialServiceCertificate.status / WorkflowEmailClassification audit row
  per audit E.3
- Forensic-fallback original-substrate query paths preserved per Q4
- 8-Task-consumer regression suite green; bit-for-bit parity verified per consumer

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

#### §2.B.7 LOC envelope

Per Phase 4 §3.3 + §7: **~1,150–1,850 LOC** across 4 consumer migrations + cross-queue parity test cohort. Safety_program upper-bound per Phase 8d.1 AI-parity discipline. Within Entry 24 calibration band.

#### §2.B.8 Close criterion verification

- Backend pytest: 4 consumer-side parity test cohorts green (with #5 using frozen-content parity per Phase 8d.1); 8-Task-consumer regression suite green; idempotency tests green; Section A regression check green.
- Playwright E2E: each migrated consumer rendered from task substrate matches legacy rendering.
- Claude API E2E: #5 safety_program AI-generation-content-invariant parity verification (frozen-content path; never invokes Claude during parity test).
- Manual operator verification: 1 query per consumer surface (4 total).
- STATE.md updates append per-commit sub-arc completion notes.

---

### §2.C — Sub-arc v2a-γ (per-job + per-review-item cluster)

**Members (2 queues):** month_end_close_triage / workflow_review

#### §2.C.1 Bounded decision (Entry 31)

**Migrate 2 per-job + per-review-item cluster consumer-side `_dq_*` read paths from `engine.py` to task substrate; preserve period-lock semantics for month_end_close per Phase 8c canon AND admin permission cohort fallback for workflow_review. Closes when 2 consumer handlers + per-queue parity tests + Playwright smoke green.**

#### §2.C.2 Substrate scope

**What changes:**
- `_dq_month_end_close_triage` (`engine.py:839`) — migrate from `AgentJob.status='awaiting_approval' AND job_type='month_end_close'` read to task-substrate query; per-job cardinality (the AgentJob in awaiting_approval IS the decision per Phase 8c).
- `_dq_workflow_review` (`engine.py:1378`) — migrate from `WorkflowReviewItem` awaiting read to task-substrate query; admin permission cohort fallback preserved (when review_focus_id discriminator doesn't resolve to a specific user, falls back to admin permission cohort per `workflow_engine.py:828` producer).

**What stays unchanged:**
- Producer-side task creation paths (agents/base_agent.py:330 for month_end_close; workflow_engine.py:828 for workflow_review).
- AgentJob lifecycle + PeriodLock writes (period-lock semantics canonical per Phase 8c).
- WorkflowReviewItem.decision field canonical for source-business-state per audit E.3.
- 6 v1 subscribers unchanged.
- Permission cohort resolution at workflow_engine.py producer side unchanged.

#### §2.C.3 4-decision matrix per consumer surface (Entry 23)

**Consumer #4 — `month_end_close_triage`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_month_end_close_triage` migrates from `db.query(AgentJob).filter(job_type='month_end_close', status='awaiting_approval')` to task-substrate query; per-job cardinality (one task per awaiting_approval AgentJob; anomalies inside the job are sub-context in the panel per Phase 8c). |
| (2) Downstream behavior | Triage workspace renders 1 row per awaiting_approval close job; `approve_close` / `reject_close` triage actions write to AgentJob.status (canonical for source-business-state) + write PeriodLock row on approve (canonical per Phase 8c) + transition task state. Pre-existing statement-run-failure rollback gap preserved verbatim per Phase 8c §11. |
| (3) Producer-supplied context | `task_details.source_data` carries agent_job_id + close_period + anomaly_count + anomaly_severity_summary. Anomaly drill-down reads AgentAnomaly via related-entities builder (audit context). |
| (4) Subscriber mechanics | audit_writer + notification_dispatcher + briefings_invalidator + pulse_invalidator fire. workflow_resumer + focus_closer no-op. |

**Consumer #9 — `workflow_review`**

| Decision | Lock |
|---|---|
| (1) Call surface | `_dq_workflow_review` migrates from `db.query(WorkflowReviewItem).filter(status='awaiting')` to task-substrate query; per-review-item cardinality; admin permission cohort fallback preserved at routing layer (resolver still falls back to admin cohort when review_focus_id doesn't resolve). |
| (2) Downstream behavior | Triage workspace renders 1 row per awaiting WorkflowReviewItem; `approve` / `reject` / `request_changes` triage actions write to WorkflowReviewItem.decision (canonical for source-business-state per audit E.3) + transition task state + resume workflow via workflow_resumer subscriber. |
| (3) Producer-supplied context | `task_details.source_data` carries workflow_run_id + workflow_step_id + review_focus_id + review_context_payload. |
| (4) Subscriber mechanics | audit_writer + notification_dispatcher + briefings_invalidator + pulse_invalidator + **workflow_resumer** fire (workflow_resumer is load-bearing here — task `current_state='done'` triggers workflow continuation). focus_closer no-op. |

#### §2.C.4 Parity discipline

- **Bit-for-bit parity** against legacy `_dq_*` read shape for both consumers.
- **Period-lock semantics preserved for #4** per Phase 8c canon: parity test positively asserts PeriodLock row creation on approve_close; verifies pre-existing statement-run-failure rollback gap preserved verbatim (not fixed in v2a-γ).
- **Admin permission cohort fallback preserved for #9:** parity test asserts that when review_focus_id is NULL or doesn't resolve to a user, fallback routing returns admin cohort tasks.
- **Cardinality preservation:** per-job (#4), per-review-item (#9).
- **workflow_resumer subscriber fire verification for #9:** parity test asserts task transition to `done` triggers workflow continuation via workflow_resumer (operational at v1 since B3 `1c8dbbd`).

#### §2.C.5 Locked disciplines

- All disciplines from §2.A.5 inherited.
- **Pre-existing rollback gap preserved verbatim per Phase 8c §11** — month_end_close's statement-run-failure rollback gap is documented latent bug; do NOT fix in v2a-γ; flag in parity test docstring.
- workflow_resumer subscriber wiring verified (v1 operational; v2a-γ confirms it fires correctly on task-substrate-backed workflow_review transitions).

#### §2.C.6 Commit shape (Entry 26 + Adjudication 1)

Single commit at sub-arc close.

```
v2a-γ: per-job + per-review-item consumer migration

Migrate 2 _dq_* handlers (month_end_close / workflow_review) from
original-substrate reads to task substrate.

- Per-job cardinality preserved for month_end_close per Phase 8c
- Period-lock semantics preserved (PeriodLock row creation on approve)
- Pre-existing statement-run-failure rollback gap preserved verbatim
  per Phase 8c §11 (flagged latent; not fixed here)
- Per-review-item cardinality preserved for workflow_review
- Admin permission cohort fallback preserved at routing layer
- workflow_resumer subscriber fire verified for workflow_review transitions
- WorkflowReviewItem.decision / AgentJob.status remain canonical for
  source-business-state per audit E.3
- Forensic-fallback original-substrate query paths preserved per Q4
- 8-Task-consumer regression suite green

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

#### §2.C.7 LOC envelope

Per Phase 4 §3.3 + §7: **~600–950 LOC** across 2 consumer migrations + cross-queue parity test cohort. Within Entry 24 calibration band; smallest sub-arc.

#### §2.C.8 Close criterion verification

- Backend pytest: 2 consumer-side parity test cohorts green; period-lock parity green; admin-cohort-fallback parity green; workflow_resumer fire verified; 8-Task-consumer regression suite green; idempotency tests green; Section A regression check green.
- Playwright E2E: each migrated consumer rendered from task substrate matches legacy rendering.
- Manual operator verification: 1 query per consumer surface (2 total).
- STATE.md update appends sub-arc completion note.

---

### §2.D — Sub-arc v2c-α (workflow-engine-adjacent refinement)

**Members (4 separable units):** escalation_chain routing mode + cancel_task workflow node + update_task workflow node + query_tasks workflow node

#### §2.D.1 Bounded decision (Entry 31)

**Ship escalation_chain routing mode (extending `task_routing_rule` CHECK constraint + resolver in `backend/app/services/tasks/routing.py`) AND 3 workflow node action handlers (cancel_task / update_task / query_tasks) extending `workflow_engine.py` action substrate per Phase 8b service-method-registry canon. Closes when 4 refinement deliverables + per-unit parity tests green; migration r110 advances head for escalation_chain CHECK constraint extension.**

#### §2.D.2 Substrate scope

**What changes (4 separable units):**

**Unit 1 — escalation_chain routing mode:**
- New migration `r110_escalation_chain_routing.py` — extends `task_routing_rule.routing_mode` CHECK constraint to include `'escalation_chain'`.
- Resolver extension at `backend/app/services/tasks/routing.py` — new branch in resolver for escalation_chain mode; consumes `routing_config` JSONB shape `{chain: [user_id_1, user_id_2, ...], timeout_minutes: int}`.
- escalation_chain transitions task assignee through chain on timeout (assignee resolution happens at task surface or scheduled sweep — Phase 5 locks resolver substrate; timeout sweep dispatch surface is operator-decision at build dispatch).

**Unit 2 — cancel_task workflow node:**
- New action handler at `backend/app/services/workflow_engine.py` for `action_type='cancel_task'`.
- Service-method-registry per Phase 8b canon — handler reads `target_task_id` from step config (resolved from prior step output or workflow variable) and calls `task_service.cancel_task(db, company_id, task_id, reason)`.

**Unit 3 — update_task workflow node:**
- New action handler at `backend/app/services/workflow_engine.py` for `action_type='update_task'`.
- Service-method-registry — handler reads `target_task_id` + update payload (subset of mutable task fields: priority, due_at, description, assignee) from step config; calls `task_service.update_task(db, company_id, task_id, updates)`.

**Unit 4 — query_tasks workflow node:**
- New action handler at `backend/app/services/workflow_engine.py` for `action_type='query_tasks'`.
- Service-method-registry — handler reads query config (filters on provenance_kind, task_type_key, current_state, assignee, etc.) and returns a `list[task_id]` to workflow variable bindings for downstream step consumption.

**What stays unchanged:**
- v1 task substrate (12-value PROVENANCE_KINDS, 5 v1 plugins, 6 v1 subscribers, 8 producer sites, Pulse + briefings + Focus integration).
- v2a consumer-side migrations (orthogonal substrate layer; v2c-α extends workflow_engine runtime substrate, NOT task-substrate read layer).
- direct_user + round_robin routing modes (escalation_chain is additive third mode).
- create_task workflow node (operational at v1 since B3 `1c8dbbd`; precedent for cancel_task / update_task / query_tasks).
- **Workflow Builder authoring substrate** at `backend/app/services/workflow_templates/` + admin Studio editor (Phase B scope per Phase 4 §4.1; v2c-α extends runtime substrate only).

#### §2.D.3 4-decision matrix per separable unit (Entry 23)

**Unit 1 — escalation_chain routing mode**

| Decision | Lock |
|---|---|
| (1) Call surface | `task_service.resolve_assignee(db, task, routing_rule)` extended with new branch for `routing_mode='escalation_chain'`. Consumes `routing_config.chain` list + `routing_config.timeout_minutes`. Initial assignee = chain[0]; on timeout sweep, assignee advances to chain[next]. |
| (2) Downstream behavior | Task surface renders escalated assignee; briefings reflect current assignee; Pulse Personal layer shows task in current assignee's queue. Operator-named signal: "Sunnycrest manufactures describe wanting to delegate aftercare to specific staff (non-director)" per phasing §5.2. |
| (3) Producer-supplied context | Producer-side creates task with `routing_rule_id` pointing at an escalation_chain rule; resolver computes assignee at create-time + on timeout sweeps. No producer-site changes required (8 producer sites use routing_rule_id indirection). |
| (4) Subscriber mechanics | No new subscribers. Existing notification_dispatcher fires on assignee change (operational at v1 if assignee changes are events; if not, escalation sweep triggers re-dispatch via standard task-update path). |

**Unit 2 — cancel_task workflow node**

| Decision | Lock |
|---|---|
| (1) Call surface | `workflow_engine.execute_step` extended with `action_type='cancel_task'` branch. Handler signature: `_handle_cancel_task(db, company_id, step_config, workflow_run_context)`. Resolves `target_task_id` from step_config (workflow variable reference syntax `{{prior_step.output.task_id}}` per Phase 8b). |
| (2) Downstream behavior | Calls `task_service.cancel_task(db, company_id, task_id, reason='workflow_cancel')`; task transitions to `cancelled` state; subscribers fire (audit_writer + notification_dispatcher + pulse_invalidator + briefings_invalidator). |
| (3) Producer-supplied context | Workflow step config carries target_task_id + cancel_reason. Cancel reason flows through to AuditLog via audit_writer subscriber. |
| (4) Subscriber mechanics | Standard task-update subscriber fire on cancel transition. |

**Unit 3 — update_task workflow node**

| Decision | Lock |
|---|---|
| (1) Call surface | `workflow_engine.execute_step` extended with `action_type='update_task'` branch. Handler reads target_task_id + updates dict from step_config. Updates dict whitelist: priority / due_at / description / assignee / task_details.source_data merge. |
| (2) Downstream behavior | Calls `task_service.update_task(db, company_id, task_id, updates)`; task fields update; subscribers fire (audit_writer logs diff; notification_dispatcher fires if assignee changed; pulse/briefings invalidate). |
| (3) Producer-supplied context | Step config carries target_task_id + updates dict per whitelist. |
| (4) Subscriber mechanics | Standard task-update subscriber fire. |

**Unit 4 — query_tasks workflow node**

| Decision | Lock |
|---|---|
| (1) Call surface | `workflow_engine.execute_step` extended with `action_type='query_tasks'` branch. Handler reads query_config from step_config (filters: provenance_kind, task_type_key, current_state, assignee, age_days, limit). Returns `list[task_id]` (max 100 per call) to workflow variable bindings. |
| (2) Downstream behavior | Returned task_id list available as `{{step.output.task_ids}}` to downstream steps (notably cancel_task or update_task consumers). No state changes. |
| (3) Producer-supplied context | Step config carries filter shape. Filters scoped to company_id via workflow_run tenant context. |
| (4) Subscriber mechanics | No subscribers fire (read-only query). |

#### §2.D.4 Parity discipline

Per Phase 8b service-method-registry canon (one new entry per unit; allowed-kwargs safelists per unit):

- **Unit 1 parity:** escalation_chain resolver test cohort covering (a) initial assignee = chain[0]; (b) timeout sweep advances to chain[1]; (c) chain exhaustion behavior (last assignee stays — no further advance); (d) invalid chain (empty list, NULL chain) gracefully no-ops without crashing. Parity test against direct_user + round_robin modes — escalation_chain is purely additive; direct_user + round_robin behavior unchanged.
- **Unit 2 parity:** cancel_task handler test cohort covering (a) target_task_id resolves correctly from step config; (b) task transitions to cancelled state; (c) subscribers fire correctly; (d) cancel of already-cancelled task is idempotent. Parity against existing create_task handler precedent (Phase 8b service-method-registry).
- **Unit 3 parity:** update_task handler test cohort covering (a) whitelist enforcement (non-whitelisted fields rejected); (b) assignee change triggers notification; (c) audit diff logged; (d) idempotency of repeated updates.
- **Unit 4 parity:** query_tasks handler test cohort covering (a) filter shape correctness; (b) company_id scoping (cross-tenant isolation); (c) max-100 limit enforcement; (d) empty result set returned as empty list.

#### §2.D.5 Locked disciplines

- All disciplines from §2.A.5 inherited.
- **Phase B / Phase C scope-lock preservation per Entry 32:** v2c-α extends **workflow_engine runtime substrate**, NOT Workflow Builder authoring substrate. Workflow Builder UI at `frontend/src/lib/visual-editor/workflows/` + admin Studio editor + `backend/app/services/workflow_templates/` is **untouched** by v2c-α. The 3 new action types become *available* at Workflow Builder authoring time as new selectable options in the existing UI; the UI's enumeration is data-driven (reads action handler registry), so adding handlers exposes them automatically. No Workflow Builder UI work in v2c-α.
- **Plugin contracts v1-locked** per Phase 0 audit C.3 — v2c-α does NOT touch plugin contracts. Escalation_chain is a routing_mode value (not plugin extension); workflow nodes are action types in workflow_engine (not task-substrate plugin contracts).
- Symmetry audit per Entry 33: routing_config JSONB shape for escalation_chain + step config shapes for 3 workflow nodes evolve Pydantic schemas; verify runtime-Pydantic-TypeScript symmetry across affected admin Studio + workflow_engine consumer surfaces.
- JSDOM-blind-spot per Entry 34: task surface rendering for escalation_chain assignee changes is user-touched; verify no JSDOM-only render path drift.

#### §2.D.6 Commit shape (Entry 26 + Adjudication 1)

Multi-commit-within-arc-identity, 4 separable units per Phase 8b parity discipline.

**Commit 1 — escalation_chain routing:**

```
v2c-α.1: escalation_chain routing mode

Add escalation_chain as third routing_mode value (alongside direct_user
and round_robin); extend task_routing_rule CHECK constraint via migration
r110; extend resolver in backend/app/services/tasks/routing.py.

- routing_config JSONB shape: {chain: [user_ids], timeout_minutes: int}
- Initial assignee = chain[0]; timeout sweep advances to chain[next]
- direct_user + round_robin modes unchanged (purely additive)
- Migration head advances: cce834d HEAD → r110_escalation_chain_routing

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Commit 2 — cancel_task workflow node:**

```
v2c-α.2: cancel_task workflow node

Add cancel_task action handler to workflow_engine.py per Phase 8b
service-method-registry canon. Extends create_task handler precedent.

- step_config: {target_task_id, cancel_reason}
- Standard task-update subscriber fire on cancel transition
- Idempotency: cancel of already-cancelled task no-ops

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Commit 3 — update_task workflow node:**

```
v2c-α.3: update_task workflow node

Add update_task action handler to workflow_engine.py per Phase 8b
service-method-registry canon.

- step_config: {target_task_id, updates}
- Whitelist: priority / due_at / description / assignee / task_details merge
- Subscriber fire: audit_writer logs diff; notification_dispatcher on
  assignee change; pulse/briefings invalidate

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Commit 4 — query_tasks workflow node + Phase A close:**

```
v2c-α.4: query_tasks workflow node + Phase A close

Add query_tasks action handler to workflow_engine.py per Phase 8b
service-method-registry canon. Closes Phase A.

- step_config: {filters: {provenance_kind, task_type_key, current_state,
  assignee, age_days, limit}}
- Returns list[task_id] (max 100) to workflow variable bindings
- Read-only: no subscribers fire
- Tenant-scoped via workflow_run company_id

Phase A close:
- 4 sub-arcs landed: v2a-α / v2a-β / v2a-γ / v2c-α
- v2a stable across 10 queues
- v2c-α stable (escalation_chain + 3 workflow nodes)
- 8-Task-consumer regression suite green
- STATE.md updated with Phase A close note

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

#### §2.D.7 LOC envelope

Per Phase 4 §3.3 + §7: **~1,000–1,700 LOC** across 4 separable units (escalation_chain ~400–700; cancel_task ~150–250; update_task ~200–350; query_tasks ~250–400). Within Entry 24 calibration band. Migration r110 ~50 LOC included in escalation_chain envelope.

#### §2.D.8 Close criterion verification

- Backend pytest: 4 per-unit parity test cohorts green; 8-Task-consumer regression suite green; v2a sub-arc regression suites green (v2a-α + v2a-β + v2a-γ unchanged by v2c-α); Section A regression check green.
- Playwright E2E: escalation_chain assignee change renders correctly in task surface; workflow_engine integration tests cover cancel_task / update_task / query_tasks invocation from workflow steps.
- Manual operator verification: escalation chain advancement on timeout sweep; cancel/update/query nodes invokable from sample workflow.
- Migration verification: `alembic upgrade head` from `cce834d` applies r110 cleanly; downgrade tested.
- STATE.md update appends Phase A close note (migration head advance to r110; all 4 sub-arcs shipped; v2a stable; v2c-α stable; deferred candidates 3/4/5/6 await post-Phase-A signal).

---

## §3. Cross-sub-arc invariants

Phase A maintains these 8 invariants across all 4 sub-arcs:

1. **v1 substrate operational state preserved through Phase A close** per Phase 0 audit Section A shape. Verified at each sub-arc commit via 8-Task-consumer regression suite green. 8 producer sites unchanged; 6 v1 subscribers unchanged; 5 task type behavior plugins unchanged; 12-value PROVENANCE_KINDS tuple frozen.

2. **Q-B1 boundary preserved** per Entry 3 + Phase 0 audit F.3. No v2a + v2c work touches admin-realm Studio-builder boot-adapter substrate. Q-B1 carries forward to September-decision arc per Entry 3 deferral-tracking meta-pattern.

3. **Phase B / Phase C scope-locks deferred** per Entry 32. v2c-α extends `workflow_engine.py` **runtime substrate**, NOT Workflow Builder **authoring substrate** at `backend/app/services/workflow_templates/` + `frontend/src/lib/visual-editor/workflows/`. Workflow Builder UI rebuild ships at Phase B as its own investigation-first arc.

4. **`description` field canonical-substrate per Adjudication 3:** original substrate (AgentAnomaly.description) authoritative at producer-side creation time; task substrate (VaultItem.description) inherits at create-time verbatim; ongoing edits adjudicated per task lifecycle (operator edits via task surface land on task substrate; AgentAnomaly.description becomes legacy producer-side write column).

5. **8-Task-consumer regression check at every sub-arc commit** per substrate-additive discipline. Existing 8 producer sites verified unchanged. Regression suite from v1 substrate (audit A.5 anchor: 214 test functions at v1) remains green at every sub-arc commit.

6. **Test cohort accumulation discipline per Entry 24:** parity + idempotency + symmetry audit tests per sub-arc; cumulative ~329–399 task substrate test functions at Phase A close per Phase 4 §7.5 calibration. Per-sub-arc test budgets: v2a-α ~30–50; v2a-β ~35–55; v2a-γ ~20–35; v2c-α ~30–45.

7. **114 stale Playwright screenshot deletions stay UNTOUCHED throughout Phase A.** Pre-existing working tree state at HEAD `cce834d` (114 screenshot/video deletions documented in git status). No sub-arc touches these.

8. **STATE.md updates land per sub-arc commit** per Phase 4 §6.2 narrative discipline. Phase A close note appends at v2c-α sub-arc 4 final commit (migration head advance to r110; all 4 sub-arcs shipped; v2a stable across 10 queues; v2c-α stable across 4 units; deferred candidates 3/4/5/6 await post-Phase-A signal; Q-B1 boundary preserved; September Wilbert demo schedule explicitly NOT a signal).

---

## §4. Material-divergence protocol per Entry 23

Per Entry 23 build-prompt-spec failure pattern + Lock A revision precedent from v1 task substrate B1 (`2fba161`):

**Verbatim protocol:**

- If build agent surfaces material that the build prompt is wrong about during execution: **STOP immediately**.
- Surface to operator with explicit rationale (what was the substrate state expected; what was found; what's the divergence shape; what's the proposed revised lock).
- Await locked revision from operator.
- Proceed against revised lock only.
- Reference: Lock A revision pattern from v1 task substrate B1 commit `2fba161` is canonical example.

**Per-sub-arc material-divergence triggers:**

**v2a-α triggers (AgentAnomaly cluster):**
- 4-decision matrix incomplete or wrong-shape for any consumer (cash_receipts / ar_collections / expense_categorization / aftercare).
- Parity verification mechanics ambiguous for any consumer (especially per-customer fan-out for ar_collections — Phase 8c canon).
- LOC envelope wrong by >20% per Entry 24 calibration band.
- Cardinality preservation surfaces unexpected substrate interaction (per-customer fan-out semantics for ar_collections is the highest-risk).
- AgentAnomaly producer-side dual-write reveals unexpected drift from canonical-substrate adjudications per audit E.2.

**v2a-β triggers (per-record + classification-cascade cluster):**
- 4-decision matrix incomplete for any consumer (safety_program / catalog_fetch / ss_cert / email_unclassified).
- **AI-generation-content-invariant parity ambiguous for safety_program** — frozen-content parity semantics per Phase 8d.1 §5.5.5 unclear or test harness can't isolate AI invocation cleanly.
- Supersede semantics for catalog_fetch can't be cleanly preserved at task substrate (older tasks transitioning to cancelled on newer fetch reveals substrate gap).
- Cascade exhaustion semantics for email_unclassified reveals classification cascade audit-row producer drift.
- LOC envelope wrong by >20%.

**v2a-γ triggers (per-job + per-review-item cluster):**
- 4-decision matrix incomplete for month_end_close / workflow_review.
- Period-lock parity can't be cleanly preserved per Phase 8c (PeriodLock row creation invariant on approve_close).
- Pre-existing statement-run-failure rollback gap surfaces unexpectedly (it should remain preserved verbatim, NOT fixed — if fixing pressure surfaces, STOP).
- Admin permission cohort fallback can't be preserved at task-substrate layer for workflow_review.
- workflow_resumer subscriber fire on workflow_review transition reveals unexpected behavior.

**v2c-α triggers (workflow-engine-adjacent refinement):**
- **v2c-α 4-separable-units commit boundaries wrong shape** (e.g., 3 cleanly separable + 1 folds into another; or 2 cleanly separable + 2 entangled).
- escalation_chain routing config JSONB shape reveals substrate gap requiring schema change beyond CHECK constraint extension.
- Service-method-registry pattern per Phase 8b doesn't cleanly extend to cancel_task / update_task / query_tasks (e.g., create_task precedent doesn't generalize).
- Workflow Builder authoring UI surfaces as required scope (per Entry 32, this is Phase B scope; if surfaces here, STOP).
- Migration r110 surfaces unexpected migration sequencing conflict.

**General Phase A triggers:**
- Phase 5 work surfaces v1 substrate concerns (canon-discipline question; v1 operational + canon-filed; should not revisit).
- Any locked discipline would be violated.
- Phase A scope expansion surfaces (candidates 3 / 4 / 5 / 6 dispatching during Phase A rather than after).
- v2b family portal scope surfaces (explicitly out-of-scope).
- September Wilbert demo schedule surfaces as scoping pressure (explicitly NOT a signal).

If any trigger fires during build, STOP before committing the affected unit; surface to operator; do NOT proceed past trigger point.

---

## §5. Acknowledgement format

Build agent acknowledges per established pattern before each sub-arc dispatch. Per-sub-arc acknowledgement format:

**1. Read order completion verified:**
- Phase 4 phasing recommendation read (`docs/investigations/task_substrate_v2a_v2c_phasing.md` — full read).
- Phase 0 audit read (`docs/investigations/task_substrate_v2a_v2c_phase0_audit.md` — Section A + Section B per-queue findings for sub-arc members + Section E collision tables + Section F dependency findings).
- Canon entries read (DECISIONS.md 2026-05-27 Entries 13 / 22 / 23 / 24 / 26 / 29 / 30 / 31 / 33 / 34 / 35 verbatim).
- v1 substrate state grounded (CLAUDE.md §4 Task Substrate H3 subsection; PLUGIN_CONTRACTS.md §25-27; PLATFORM_ARCHITECTURE.md §3.3 + §5.13).
- Sub-arc-specific reads (per-sub-arc `_dq_*` handler current state at file:line per §2.X.2 substrate scope).

**2. Framing-matches confirmation:**
- Sub-arc bounded decision verbatim per §2.X.1.
- Sub-arc members enumerated.
- Sub-arc LOC envelope confirmed within Entry 24 calibration band.

**3. Per-sub-arc scope lock confirmation:**
- Substrate scope verified against current state at HEAD (latest sub-arc commit or HEAD `cce834d` at v2a-α dispatch).
- 4-decision matrix verified per consumer/unit (4 matrices for v2a-α; 4 for v2a-β; 2 for v2a-γ; 4 for v2c-α).
- LOC envelope confirmed.
- Commit shape locked per Adjudication 1 (single-commit-at-arc-close for v2a-α + v2a-γ; multi-commit for v2a-β + v2c-α).

**4. Material-divergence triggers explicit per sub-arc** per §4.

**5. Locked disciplines acknowledged** per §2.X.5 (sub-arc-specific) + cross-sub-arc invariants per §3.

**Operator confirms acknowledgement before build sub-agent dispatches against the sub-arc.**

---

## §6. Phase A → Phase B gate signal pattern

### 6.1 Phase A close criterion satisfied when:

- All 4 sub-arc commits land at HEAD (single-commit-at-arc-close for v2a-α + v2a-γ; multi-commit for v2a-β + v2c-α; total ~10 commits across Phase A close + interim per Phase 4 §7.6).
- v2a stable across all 10 queues: consumer-side reads from task substrate; bit-for-bit parity verified per sub-arc; cardinality preserved per queue; operationally-idempotent invariant preserved per Entry 35.
- v2c-α stable: escalation_chain routing + 3 workflow nodes operational; service-method-registry per Phase 8b canon; migration r110 advances head.
- 8-Task-consumer regression suite green (existing 8 producer sites unchanged).
- STATE.md updated with Phase A close note per Phase 4 §6.2 cross-version concerns.
- Q4 forensic-fallback documented as indefinite-preservation pending candidate 6 (post-Phase-A signal-driven dispatch).
- Q5 task templates plugin contract investigation deferred per signal-driven post-Phase-A pattern.

### 6.2 After Phase A close:

- **Phase B Workflow Builder rebuild investigation-first arc** dispatches per Entry 32 per-arc pre-dispatch rescoping when operator signals readiness.
- Phase B scope NOT locked at Phase 5; per-arc pre-dispatch rescoping governs.
- Phase B signal pattern per Phase 4 §4.3 anchor (operator-named workflow-builder-shape signal): "Sunnycrest operations describe needing to author workflow node sequences that exceed current Workflow Builder UI authoring shape" OR "Hopkins directors describe wanting multi-step approval chains that current pairing doesn't support."
- Anti-signal discipline per Entry 2 holds throughout: LOC threshold rejected; count threshold rejected; calendar elapsed time rejected; September Wilbert demo schedule rejected; engineering preference rejected; aesthetic-completeness rejected; sunk-cost rejected.

### 6.3 Post-Phase-A deferred-candidate dispatch:

Candidates 3 (6th plugin), 4 (subscriber persistent log), 5 (task templates), 6 (dual-write unification) sequence per their own signal patterns post-Phase-A close per Phase 4 §6.4:

- **Candidate 3:** in-cycle flag during Phase A build — if v2a sub-arcs surface audit-shape task patterns not fitting existing 5 plugins, surface for inline scope adjustment; otherwise dispatch post-Phase-A on signal.
- **Candidate 4:** in-cycle flag during Phase A build — if consumer-side migration surfaces subscriber timing questions, surface for inline scope; otherwise dispatch post-Phase-A on signal.
- **Candidate 5:** out-of-scope lock at Phase A; if signal surfaces during Phase A, defer to dedicated investigation arc per Entry 23 build-prompt-spec failure pattern.
- **Candidate 6:** v2a-dependency-lock; ships post-v2a stable only. Dual-write unification retires forensic-fallback original-substrate query paths at this dispatch.

---

## Phase 5 closing

Phase 5 build prompt drafting closes. Deliverable shipped at `docs/investigations/task_substrate_v2a_v2c_v1_build_prompt.md` per 6-section structure. Per Entry 31 bounded-decision-per-arc explicit naming, Phase 5 bounded decision = "produce Phase A v1 build prompt deliverable locking per-sub-arc execution context across the 4 sub-arc identities; surface material-divergence protocol; surface acknowledgement format; lock NO production code; lock NO canon edits; lock NO STATE.md edits; lock NO build dispatch" — bounded decision satisfied.

**Next-gate handoff:** operator reviews Phase 5 deliverable; confirms per-sub-arc execution context; v2a-α build sub-agent dispatches against locked sub-arc scope.

**No material-divergence triggers fired during Phase 5 drafting.** No canon edits. No STATE.md edits. No production code. No build dispatch. No v2b scope. No Phase B / Phase C scope-lock. No Q-B1 substrate decision. No v1 substrate revisiting. No plugin-field promotion.

**14 4-decision matrices locked** across 4 sub-arc identities: 4 (v2a-α) + 4 (v2a-β) + 2 (v2a-γ) + 4 (v2c-α) = 14.

**C42 carry-forward boundary preserved** per Entry 3. **September Wilbert demo schedule explicitly NOT a signal** per operator framing locks + Entry 2 anti-signal canon. **114 stale Playwright screenshot deletions stay UNTOUCHED.**
