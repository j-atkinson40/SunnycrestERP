# Task Substrate v2a + v2c — Phase 4 Phasing Recommendation

> Read-only Phase 4 deliverable closing the v2a+v2c task substrate completion investigation. Dispatches against Phase 0 audit findings at `docs/investigations/task_substrate_v2a_v2c_phase0_audit.md` (HEAD `cce834d`, 2026-05-27). Follows the canonical 8-section structure per DECISIONS.md 2026-05-27 — Phasing recommendation shape canon (Entry 27).
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables (Entry 4).

## Phase 4 metadata

- **Arc context:** v2a + v2c task substrate completion investigation, Phase 4 of 4 (Phase 0 audit closed → Phase 4 phasing recommendation → operator confirmation → Phase 5 build prompt drafting downstream)
- **HEAD at recommendation:** `cce834d` (Canon-update arc close)
- **Phasing date:** 2026-05-27
- **Canon ground:** 35 DECISIONS.md entries dated 2026-05-27; particularly Entry 1 (investigation-methodology), Entry 2 (operator-observable signals + anti-signals), Entry 13 (substrate-transition discipline), Entry 17 (substrate-prescience-meets-second-consumer), Entry 22 (discoverability canon), Entry 23 (build-prompt-spec failure pattern), Entry 24 (LOC calibration), Entry 25 (deferral-flagging), Entry 26 (arc-commit-granularity), Entry 27 (phasing recommendation shape canon), Entry 29 (substrate-extending arcs with colliding field names), Entry 30 (sub-arc decomposition seams), Entry 31 (bounded-decision-per-arc explicit naming), Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs).
- **Bounded decision:** produce phasing recommendation deliverable per Entry 27 8-section structure; surface adjudications for operator confirmation; lock NO Phase 5 build prompt content; lock NO scope outside Phase A (v2a + v2c).
- **Operator framing locks preserved:** v2b family portal OUT-OF-SCOPE; September Wilbert demo schedule explicitly NOT a signal; building-correctness-over-schedule-pressure per Entry 2 anti-signal canon; Q-B1 boundary preserved per Entry 3.

---

## §1. v2a final-lock — consumer-side read-path migration

### 1.1 Substrate-shape final-lock

Per Phase 0 audit Section B.1 reframe, the substantive scope-shape finding is that v2a is **consumer-side read-path migration**, not **producer-side adapter construction**. The producer-side dual-write substrate already shipped at v1 B2 (commit `a400d1b`) when (c) refactor wired 8 producer sites through `create_task_with_provenance` (audit A.1; B.1.1).

**What v2a changes:**
- The 10 `_DIRECT_QUERIES` handlers in `backend/app/services/triage/engine.py` (lines 1432–1450 registration; per-queue handlers at `engine.py:664/720/839/905/1016/1134/1250/1320/1363/1378` per audit B.2) migrate from reading original-substrate rows (AgentAnomaly / AgentJob / SafetyProgramGeneration / UrnCatalogSyncLog / SocialServiceCertificate / WorkflowReviewItem / WorkflowEmailClassification) to reading task substrate via `task_details` ⨝ `vault_items`.
- Per-queue denormalized display fields are preserved; cardinality semantics are preserved per queue.
- Original-substrate query paths persist as forensic-fallback during transition window per Phase 8b operational coexistence canon. Retirement timing is v2c-scope decision (see §2 candidate #6 and §8 open question 4).

**What v2a does NOT change:**
- Producer-side task creation paths (already operational; audit A.1).
- Subscriber registry (6 v1 subscribers unchanged; sync dispatch unchanged; persistent log deferred to v2c per audit C.1 #4).
- Provenance vocabulary (12-value PROVENANCE_KINDS tuple frozen at v1; audit A.1).
- Plugin contracts (v1-locked; plugin-field promotion out-of-scope per audit C.2 #7 and §6 below).
- Routing resolver (direct_user + round_robin only; escalation_chain deferred to v2c per audit C.1 #1).
- Pulse Personal layer / briefings / Focus integration (operational at v1 per audit A.4).

### 1.2 Per-consumer migration map

Each of the 10 v2a triage queues maps to one consumer-side `_dq_*` handler in `engine.py`. Producer-side task creation already supplies the substrate; v2a migrates the read path with cardinality semantics preserved.

| # | Queue | Consumer handler | Cardinality | Original-substrate read path | Audit B.2 ref |
|---|-------|------------------|-------------|------------------------------|---------------|
| 1 | `cash_receipts_matching_triage` | `_dq_cash_receipts_matching_triage` (engine.py:720) | per-anomaly | AgentAnomaly ⨝ AgentJob (CRITICAL/WARNING/INFO sort) | B.2 #1 |
| 2 | `ar_collections_triage` | `_dq_ar_collections_triage` (engine.py:905) | per-customer fan-out | AgentAnomaly ⨝ Customer | B.2 #2 |
| 3 | `expense_categorization_triage` | `_dq_expense_categorization_triage` (engine.py:1016) | per-line | AgentAnomaly (quiet-run gating) | B.2 #3 |
| 4 | `month_end_close_triage` | `_dq_month_end_close_triage` (engine.py:839) | per-job | AgentJob awaiting_approval | B.2 #4 |
| 5 | `safety_program_triage` | `_dq_safety_program_triage` (engine.py:1250) | per-run | SafetyProgramGeneration.status enum | B.2 #5 |
| 6 | `aftercare_triage` | `_dq_aftercare_triage` (engine.py:1134) | per-case | AgentAnomaly (funeral cohort) | B.2 #6 |
| 7 | `catalog_fetch_triage` | `_dq_catalog_fetch_triage` (engine.py:1320) | per-sync-log | UrnCatalogSyncLog.publication_state | B.2 #7 |
| 8 | `ss_cert_triage` | `_dq_ss_cert_triage` (engine.py:664) | per-cert | SocialServiceCertificate ⨝ SalesOrder/Customer | B.2 #8 |
| 9 | `workflow_review` | `_dq_workflow_review` (engine.py:1378) | per-review-item | WorkflowReviewItem awaiting | B.2 #9 |
| 10 | `email_unclassified` | `_dq_email_unclassified_triage` (engine.py:1363) | per-classification-audit-row | WorkflowEmailClassification audit row | B.2 #10 |

### 1.3 Dual-write transitional closure boundary

Per Entry 13 substrate-transition discipline. v2a closes the consumer-side read-path migration; original-substrate query paths persist post-v2a as forensic-fallback (Phase 8b operational coexistence canon). The decision to retire forensic-fallback paths is v2c-γ scope (audit C.2 #6) and surfaces as open question 4 in §8 for operator timing decision.

**Forward-only discipline (Entry 13):** no backfill of pre-v1-B2 historical state. Tasks created from v1 B2 forward become canonical read substrate. Pre-v1-B2 historical AgentAnomaly / SafetyProgramGeneration / UrnCatalogSyncLog rows remain readable via forensic-fallback original-substrate paths.

### 1.4 Per-queue canonical-substrate adjudications

Per audit Section E.3 pattern: **original substrate stays authoritative for source-business-state semantics; task substrate becomes authoritative for task-lifecycle semantics.** Adapter mirrors during transition window.

Concretely (audit E.2 collision tables):
- `severity` (AgentAnomaly) → mapped to task `priority` at creation time (CRITICAL→urgent, WARNING→high, INFO→normal); original-substrate field stays authoritative for source-business meaning.
- `status` (SafetyProgramGeneration, UrnCatalogSyncLog, SocialServiceCertificate) → original substrate stays authoritative for source-business-state semantics; task substrate's `current_state` mirrors approval-gate lifecycle.
- `resolved` (AgentAnomaly) → task substrate's `current_state="done"` authoritative going forward; adapter mirrors.
- `resolved_at` / `reviewed_at` → task substrate's `completed_at` authoritative going forward.
- `decision` (WorkflowReviewItem) → task substrate's `resolution_outcome` authoritative going forward.
- `description` (AgentAnomaly ↔ VaultItem.description) → latent risk; surfaces as open question 3 in §8.

### 1.5 LOC envelope

Per audit B.3 calibration:
- Per-queue range: ~250–500 LOC (consumer-side read-path migration + cardinality preservation + per-queue parity tests). Safety_program upper-bound due to Phase 8d.1 AI-generation-content-invariant parity discipline.
- v2a cumulative: **~2,800–4,400 LOC** across 10 queues + cross-queue test cohort.
- Within Entry 24 calibration band; substantially under the 6,000 single-phase ceiling.

### 1.6 Acceptance criteria for v2a close

- All 10 consumer-side `_dq_*` handlers migrated to task-substrate read path; per-queue parity tests green (legacy original-substrate read vs new task-substrate read return functionally-equivalent result sets given identical pre-state).
- Cardinality semantics preserved per queue (audit B.2 cardinality column; per-customer fan-out fidelity per Phase 8c canon for AR collections; per-run AI-parity preservation per Phase 8d.1 for safety program).
- Original-substrate query paths preserved as forensic-fallback (NOT retired); retirement timing deferred to v2c-γ or post-v2a operator decision (open question 4).
- Per-queue Playwright smoke green; triage workspace renders task-substrate-backed list across all 10 queues.
- No regressions in v1 substrate (audit A.5 test cohort + per-queue regression cohort).

### 1.7 Commit-shape per Entry 26

Default single-commit-at-arc-close per Entry 26. Per §3 below the sub-arc grouping recommends each sub-arc within v2a ships as its own arc-close commit; safety_program may earn multi-commit-within-arc-identity if AI-parity gate timing warrants (Phase 8d.1 precedent).

---

## §2. v2c final-lock — subset-selected per Adjudication 2

### 2.1 Candidate enumeration (6 v2c-shape candidates)

Per audit Section C.1 + C.2 + C.3 enumeration. 6 candidates evaluated against operator-observable signal patterns per Entry 2 + Entry 27 §5.

#### Candidate 1 — Escalation routing mode (`escalation_chain`)

- **Substrate:** `backend/app/services/tasks/routing.py` + CHECK constraint extension on `task_routing_rule` table (audit C.1 #1).
- **Signal pattern:** "Sunnycrest manufactures describe wanting to delegate aftercare to specific staff (non-director) and current permission shape doesn't support it" (phasing §5.2).
- **Plugin-contract impact:** none (routing_mode value, not plugin extension).
- **LOC envelope:** ~400–700 LOC.
- **Recommendation:** **ship in Phase A subset** — signal pattern is operator-named, plugin-impact-clean, modest LOC. Routing substrate is the most-likely-to-need v2c refinement based on phasing §5.2 anchor.

#### Candidate 2 — Additional workflow nodes (`cancel_task`, `update_task`, `query_tasks`)

- **Substrate:** `workflow_engine.py` action handlers (audit C.1 #2). Extends `create_task` handler precedent (line 1219).
- **Signal pattern:** workflow templates need task lifecycle manipulation post-creation (e.g., a cascade workflow needs to cancel downstream tasks if upstream rejected).
- **Plugin-contract impact:** none (action types in `workflow_engine`, not task-substrate plugin contracts).
- **LOC envelope:** ~600–1,000 LOC (3 handlers × ~150–250 LOC + parity tests).
- **Recommendation:** **ship in Phase A subset** — extends existing v1 `create_task` handler precedent; service-method-registry pattern per Phase 8b canon; modest scope. Signal pattern likely surfaces alongside escalation routing signal at the same operator-workflow gate.

#### Candidate 3 — 6th task type plugin (`scheduled_audit_task`)

- **Substrate:** `backend/app/services/tasks/plugins/types/scheduled_audit_task.py` (new file joining existing 5) per audit C.1 #3.
- **Signal pattern:** audit-shape tasks distinct from existing 5 plugin types — recurring scheduled audit pattern (e.g. monthly equipment safety audit, quarterly compliance review).
- **Plugin-contract impact:** none (contract consumer instance, not contract extension).
- **LOC envelope:** ~150–300 LOC.
- **Recommendation:** **defer to post-Phase-A** — signal not yet operator-validated; 5 v1 plugins cover current observed task shapes; adding 6th without signal is anti-signal aesthetic-completeness per Entry 2. If signal surfaces during v2a build (operators describe needing audit-shape tasks not fitting existing 5), ship as standalone refinement at that point.

#### Candidate 4 — Subscriber registry persistent log

- **Substrate:** new `task_subscriber_dispatches` table + service-layer log + replay path (audit C.1 #4). Migration r110 likely.
- **Signal pattern:** "Audit / debugging surfaces request 'what subscribers fired on this task and when'" (phasing §5.2).
- **Plugin-contract impact:** none (subscriber substrate is internal, not in plugin contracts directory).
- **LOC envelope:** ~400–600 LOC (table + service layer + replay + tests).
- **Recommendation:** **defer to post-Phase-A** — current sync dispatch + isolated try/except per subscriber is operational at v1; no audit / debugging friction signal surfaced yet. Signal likely surfaces during v2a build when consumer-side migration exposes subscriber timing questions. Defer until then.

#### Candidate 5 — Task templates via visual editor

- **Substrate:** new substrate altogether — `backend/app/services/visual_editor/task_templates/` + Studio admin UI (audit C.1 #5).
- **Signal pattern:** "Operators describe authoring same task creation pattern three or more times across workflows" (phasing §5.2).
- **Plugin-contract impact:** **POSSIBLE plugin contract extension or new plugin category** per audit C.1 #5 caveat. If contract extension required, that's consolidation work outside v2c scope (plugin contracts v1-locked).
- **LOC envelope:** ~1,200–1,800 LOC.
- **Recommendation:** **defer to post-Phase-A** — largest candidate; plugin-contract impact uncertainty per audit C.1 caveat is the canonical disqualifier for Phase A inclusion. Surfaces as open question 5 in §8 for operator confirmation. If task templates ship, they likely warrant a dedicated investigation arc per Entry 23 build-prompt-spec failure pattern (refactor scope hides architectural decisions).

#### Candidate 6 — Dual-write unification (audit-surfaced)

- **Substrate:** `engine.py` `_DIRECT_QUERIES` registrations + adjacent `_dq_*` functions (audit C.2 #6). Retires original-substrate query paths once v2a's task-substrate read paths stable.
- **Signal pattern:** **depends on v2a stable across all 10 queues** (Section F.2). Cleanup-shape rather than refinement-shape.
- **Plugin-contract impact:** none.
- **LOC envelope:** ~300–500 LOC.
- **Recommendation:** **defer to post-Phase-A** — explicit v2a dependency per audit F.2; premature if v2a transition window not stable. Forensic-fallback preservation per Phase 8b operational coexistence canon argues for non-trivial transition window. Surfaces as open question 4 in §8 for operator timing decision.

### 2.2 v2c Phase A subset selection

**Selected for Phase A inclusion: candidates 1 and 2** (escalation routing + additional workflow nodes).

**Deferred to post-Phase-A: candidates 3, 4, 5, 6** (6th plugin / subscriber log / task templates / dual-write unification).

**Subset selection rationale:**
- Candidates 1 + 2 share workflow-engine-adjacent substrate shape (audit D.2 v2c-α cluster). They cluster naturally per Entry 30 substrate-shape distinction.
- Candidates 1 + 2 have operator-named signal patterns from phasing §5.2 anchor; the other 4 don't have operator-validated signals.
- Candidate 3 is small enough to ship as standalone refinement at signal-surface time; bundling without signal is anti-signal per Entry 2.
- Candidate 4 likely signal surfaces during v2a build; deferring lets it ship with appropriate signal-driven scope.
- Candidate 5 has plugin-contract uncertainty disqualifying Phase A inclusion per Entry 23 build-prompt-spec failure pattern.
- Candidate 6 has v2a-stability dependency disqualifying Phase A inclusion.

**Phase A v2c LOC envelope:** ~1,000–1,700 LOC (candidates 1 + 2 combined per audit D.2 v2c-α).

### 2.3 v2c Phase A close criterion

- Candidates 1 + 2 substrate-shape final per Entry 30 (escalation_chain routing_mode value extends `routing_config` JSONB forward-compat; 3 workflow node action handlers extend `create_task` handler precedent).
- Per-candidate parity tests green; per-candidate Playwright smoke green where operator-facing surface exists.
- Plugin contracts unchanged (v1-locked per audit C.3).
- No regressions in v1 or v2a substrate.

### 2.4 Cross-candidate dependencies

- Candidate 6 depends on v2a stable (audit F.2); deferred until post-Phase-A.
- Candidate 5 has plugin-contract impact risk (audit F.2 caveat); deferred for separate investigation.
- Candidates 1, 2, 3, 4 are independent of each other and of v2a.

---

## §3. Sub-arc grouping with operator-observable signal triggers (Adjudication 1)

### 3.1 Audit Section D 4 collapse options recap

Per audit D.3 four collapse options:
- **(a)** collapse v2a-γ (per-job/per-review-item) into v2a-α (AgentAnomaly cluster) — both AgentJob-shape upstream → 3 v2a + 3 v2c = 6 total.
- **(b)** collapse v2a-δ (email_unclassified) into v2a-β (per-record) — both per-record cardinality, distinct producer-shape → 3 v2a + 3 v2c = 6 total.
- **(c)** preserve 4 v2a sub-arcs; collapse v2c-β into v2c-α (workflow nodes + routing + 6th plugin all engine-adjacent) → 4 v2a + 2 v2c = 6 total.
- **(d)** preserve 7 sub-arcs; defend on substrate-shape distinctness per Entry 30; commit to operator-confirm gate per sub-arc.

### 3.2 Recommendation: Option (b)

**Phase 4 recommends Option (b) — collapse v2a-δ into v2a-β.**

**Rationale:**

(1) **Substrate-shape grouping coherence per Entry 30.** Option (b) preserves the AgentAnomaly cluster (v2a-α, 4 queues with shared producer shape and shared mirror pattern in audit E.2) intact. The 4-queue cluster is the largest substrate-shape-coherent grouping; collapsing it (Option (a)) dilutes coherence. v2a-β post-collapse becomes "per-record-with-pending-state-column-or-classification-cascade-audit cluster" — 4 queues sharing the "non-AgentAnomaly producer + pre-existing pending-state column or audit-row equivalent" shape. email_unclassified's classification-cascade-audit-row shape is structurally adjacent to UrnCatalogSyncLog's publication_state + SafetyProgramGeneration's status + SocialServiceCertificate's status (all per-record domain rows with pre-existing lifecycle column).

(2) **Cardinality coherence within collapsed v2a-β.** Per-cert / per-sync-log / per-run / per-classification-audit-row all single-instance-per-record cardinality (no fan-out). Distinguishes cleanly from v2a-α's per-anomaly-with-per-customer-fan-out (#2 ar_collections) cardinality variance.

(3) **Commit-shape practicality per Entry 26.** v2a-β post-collapse spans 4 queues with the safety_program AI-parity upper-bound. Multi-commit-within-arc-identity for v2a-β remains defensible (safety_program ships as own commit). Option (a) would push v2a-α to 6 queues which is heavier than the substrate-shape coherence warrants.

(4) **Operator-confirm gate frequency.** Option (b) yields 6 total sub-arcs (3 v2a + 3 v2c). Option (d)'s 7-sub-arc preservation produces operator-confirm gate frequency that audit D.3 flags as over-decomposition risk. Option (a) and (c) also yield 6 but at the cost of substrate-shape coherence (a) or v2c clustering coherence (c).

(5) **Phase A subset selection alignment.** Phase A v2c per §2.2 selects candidates 1 + 2 (v2c-α cluster). Option (c) would collapse v2c-β into v2c-α — but Phase A excludes v2c-β anyway (6th plugin deferred). Option (c) is moot under §2.2 subset selection.

### 3.3 Recommended sub-arc decomposition

Phase A ships **5 sub-arcs** (3 v2a + 1 v2c = Phase A; the 2 in v2c-α counted as one cluster sub-arc per audit D.2).

Honest count revisited: per audit D.2 + §2.2 subset selection, Phase A scope under Option (b) is:

| Sub-arc | Cluster | Members | LOC | Commit-shape |
|---------|---------|---------|-----|--------------|
| **v2a-α** | AgentAnomaly cluster | 4 queues (#1 cash_receipts / #2 ar_collections / #3 expense_categorization / #6 aftercare) | ~1,050–1,650 | single-commit-at-arc-close |
| **v2a-β (collapsed)** | per-record + classification-cascade cluster | 4 queues (#5 safety_program / #7 catalog_fetch / #8 ss_cert / #10 email_unclassified) | ~1,150–1,850 | multi-commit-within-arc-identity (safety_program own commit per Phase 8d.1 AI-parity discipline) |
| **v2a-γ** | per-job / per-review-item cluster | 2 queues (#4 month_end_close / #9 workflow_review) | ~600–950 | single-commit-at-arc-close |
| **v2c-α** | workflow-engine-adjacent refinement | escalation_chain + 3 workflow nodes | ~1,000–1,700 | multi-commit-within-arc-identity (escalation_chain + each workflow node ship as separable units) |

**Phase A total: 4 sub-arc identities, 10 task substrate consumer migrations + 4 refinement deliverables.**

### 3.4 Per-sub-arc bounded decision (Entry 31 explicit naming)

- **v2a-α bounded decision:** migrate 4 AgentAnomaly-cluster consumer-side read paths to task substrate; preserve cardinality semantics; mirror canonical-substrate adjudications per audit E.2. Closes when 4 consumer handlers + parity tests + Playwright smoke green.
- **v2a-β bounded decision:** migrate 4 per-record + classification-cascade cluster consumer-side read paths to task substrate; preserve cardinality + supersede semantics (catalog_fetch); preserve AI-generation-content-invariant parity (safety_program per Phase 8d.1). Closes when 4 consumer handlers + parity tests + Playwright smoke green.
- **v2a-γ bounded decision:** migrate 2 per-job / per-review-item consumer-side read paths to task substrate; preserve period-lock semantics (month_end_close per Phase 8c canon) + admin permission cohort fallback (workflow_review). Closes when 2 consumer handlers + parity tests + Playwright smoke green.
- **v2c-α bounded decision:** ship escalation_chain routing mode + 3 workflow node action handlers (cancel_task, update_task, query_tasks); extend routing CHECK constraint; extend service-method-registry. Closes when 4 refinement deliverables + parity tests green.

### 3.5 Cross-sub-arc dependencies + sequencing constraints

- **v2a-α, v2a-β, v2a-γ independent of each other** at substrate level — each migrates distinct `_dq_*` handlers in `engine.py`. Sequencing operator-decision-based per signal pattern; default-recommendation is α → β → γ (substrate-shape complexity ascending).
- **v2c-α independent of v2a** at substrate level — escalation routing extends `task_routing_rule` substrate, workflow nodes extend `workflow_engine` action substrate. Neither touches v2a's consumer-read substrate.
- **v2c-α ships LAST in Phase A** by default-recommendation: the refinement shape benefits from v2a stability for signal-driven scope adjustment (Entry 23 build-prompt-spec failure pattern argues for substrate-stability-before-refinement).
- **Post-Phase-A deferred candidates** (3, 4, 5, 6) sequence per their own signal patterns post-Phase-A close.

### 3.6 Sub-arc commit-shape per Entry 26 summary

Per Entry 26 default single-commit-at-arc-close. Two sub-arcs earn multi-commit-within-arc-identity:
- **v2a-β** — safety_program AI-parity gate per Phase 8d.1 ships as own commit before the other 3 in the cluster.
- **v2c-α** — escalation_chain + 3 workflow node handlers ship as 4 separable units per parity-discipline alignment with Phase 8b canon.

The other 2 sub-arcs (v2a-α, v2a-γ) ship single-commit-at-arc-close.

---

## §4. Phase B / Phase C arc shape — forward-reference framing only

Per Entry 32 per-arc pre-dispatch rescoping for distant-horizon arcs. Phase 4 does NOT lock Phase B / Phase C scope; the framing here is forward-reference per Entry 27 §4 canonical structure.

### 4.1 Phase B — Workflow Builder rebuild (forward-reference)

**Out-of-scope for Phase 4 phasing recommendation.** Phase B dispatches as its own investigation-first arc when v2a + v2c (Phase A) close. Phase B scope decisions land at then-current Workflow Builder substrate state per Entry 32, not at Phase 4 time.

**Boundary preservation (audit F.4):** v2a + v2c work does NOT touch Workflow Builder authoring substrate. The action-handler-registry in `workflow_engine.py` (which v2c-α extends with 3 new handlers) is **runtime substrate**, distinct from Workflow Builder **authoring substrate** at `backend/app/services/workflow_templates/` + `frontend/src/lib/visual-editor/workflows/` + admin Studio editor. v2c-α's workflow nodes become *available* at Workflow Builder authoring time as new action types; the Workflow Builder UI that consumes them is unchanged by v2c-α and rebuilds at Phase B.

### 4.2 Phase C — Document Builder rebuild (forward-reference)

**Out-of-scope for Phase 4 phasing recommendation.** Phase C dispatches as its own investigation-first arc downstream of Phase B close. Phase C scope decisions land at then-current Document Builder substrate state per Entry 32.

**Boundary preservation (audit F.4):** v2a + v2c work does NOT touch document substrate at all. Document Builder substrate at `backend/app/services/documents/block_*` is structurally distinct from task substrate.

### 4.3 Phase A → Phase B transition signal

Phase B dispatches when operator names a workflow-builder-shape signal (e.g., "Sunnycrest operations describe needing to author workflow node sequences but the current Workflow Builder UI doesn't surface the new v2c-α action types cleanly" or "Hopkins directors describe wanting to author a multi-step approval chain and the existing workflow_engine + Workflow Builder pairing doesn't support it"). Signal sourcing per Entry 2 + phasing §5.2 anchor; anti-signals (LOC, count, time, engineering preference, aesthetic-completeness, sunk-cost) explicitly rejected.

---

## §5. Upgrade signals + explicit anti-signals

### 5.1 Per-sub-arc dispatch signals (operator-observable per Entry 2)

#### v2a-α dispatch signals (AgentAnomaly cluster)
- "Sunnycrest accounting describes the cash-receipts + ar-collections + expense-categorization triage trio as 'three separate places I have to check' rather than 'one place where my accounting decisions live'" (phasing §5.2 anchor).
- "Hopkins directors describe friction moving between aftercare and other triage queues" (phasing §5.2 anchor extended).

#### v2a-β dispatch signals (per-record + classification-cascade cluster)
- "Sunnycrest production describes safety_program + catalog_fetch + ss_cert review queues as fragmented" (extending phasing §5.2 anchor to per-record cluster).
- "Operators describe email classification cascade fall-throughs as 'I don't know where these landed' — surfaces email_unclassified into the same shape" (extending phasing §5.2).

#### v2a-γ dispatch signals (per-job / per-review-item cluster)
- "Sunnycrest accounting describes month-end-close approval gate as 'why is this in a different place than the other accounting work'" (extending phasing §5.2 to per-job cluster).
- "Hopkins directors describe workflow review pause-and-decide pattern as friction" (extending phasing §5.2).

#### v2c-α dispatch signals (workflow-engine-adjacent refinement)
- "Sunnycrest manufactures describe wanting to delegate aftercare to specific staff (non-director) and the current permission shape doesn't support it" (phasing §5.2 verbatim) — signals escalation routing.
- "Workflow templates need to cancel downstream tasks if upstream rejected" (workflow-engine-shape signal) — signals additional workflow nodes.

### 5.2 Phase A → Phase B transition signal
- "Sunnycrest operations describe needing to author workflow node sequences that exceed current Workflow Builder UI authoring shape" — signals Phase B Workflow Builder rebuild.
- "Hopkins directors describe wanting multi-step approval chains that current pairing doesn't support" — signals Phase B (extends from operator agency).

### 5.3 Explicit anti-signals per Entry 2

All anti-signals from phasing §5.2 + state doc §4.1 v1 investigation operator decision are inherited and reaffirmed. Phase 4 explicitly rejects:

- **LOC threshold:** "Phase A work has accumulated ~6,000 LOC" — architecture-observable; rejected.
- **Count threshold:** "10 v2a queues remain on consumer-side original-substrate read" — architecture-observable; rejected. The dual-write transitional state is the canonical operational state per Phase 8b coexistence canon; remaining count alone is not signal.
- **Time threshold:** "3 months since v1 shipped" — calendar elapsed time is not workflow signal; rejected.
- **September Wilbert demo schedule:** explicitly rejected. Demo schedule is calendar pressure; building-correctness-over-schedule-pressure per operator framing locks (audit Phase 0 metadata operator framing locks). Demo schedule is NOT a Phase A dispatch signal under ANY framing.
- **Engineering preference:** "team feels v2a is next thing to build" — engineering preference is not operator-observable workflow signal; rejected per Entry 2.
- **Aesthetic-completeness:** "task substrate feels incomplete with 10 queues outside" — architectural-aesthetic; rejected. v1 was deliberately scoped against operator-observable need, not architectural-completion. Phase A also scopes against operator signals.
- **Sunk-cost:** "Phase 0 audit + Phase 4 phasing already invested ~10k words; let's just ship Phase A" — design-completion; rejected. Phase A dispatches when Phase A's bounded decisions warrant per signal patterns above, not when investigation deliverables exist.

---

## §6. Cross-version concerns

### 6.1 Canon-update interleave timing per Entry 4

Next canon-update arc dispatches **post-Phase-A close** per Entry 4 + canon-update arc precedent (HEAD `cce834d` was the most recent canon-update close at v1 close). Phase A sub-arc closes accumulate DECISIONS.md entries + canon-doc surface candidates that the post-Phase-A canon-update arc consolidates.

Phase A in-flight does NOT block canon-update; in-flight canon hygiene per Entry 4 — anything that warrants immediate canon entry during Phase A ships inline (e.g. an unexpected substrate seam surfaced during v2a-β build warrants immediate DECISIONS.md entry, not deferral to post-Phase-A consolidation).

### 6.2 STATE.md narrative across Phase A → Phase B → Phase C

STATE.md narrative accretes per arc close per state-doc append-only discipline. Phase A close updates: migration head if changed (v2c-α may add r110 for escalation_chain CHECK constraint extension), arc-recently-shipped entries per sub-arc, active arc transitions to post-Phase-A signal-watching state.

Phase B / Phase C STATE.md narrative lands at those arcs' dispatch + close per their own scope-lock investigations.

### 6.3 C42 carry-forward boundary preserved per Entry 3

**Q-B1 (boot-adapter-takes-client substrate decision) boundary preserved per audit F.3.** Phase A work operates at tenant-realm task substrate layer; Q-B1 operates at admin-realm Studio-builder boot layer. v2a + v2c work does NOT lock or resolve Q-B1 substrate decision. Q-B1 carries forward to the September-decision arc per Entry 3 deferral-tracking meta-pattern.

### 6.4 Deferral-tracking meta-pattern application (Entry 3 + Entry 25)

Phase A defers candidates 3, 4, 5, 6 per §2.2 + §2.4. Per Entry 25 deferral-flagging discipline + Entry 3 deferral-tracking meta-pattern:

- **Candidate 3 (6th plugin):** in-cycle flag during Phase A build — if v2a-α/β/γ surface audit-shape task patterns not fitting existing 5 plugins, surface for inline scope adjustment.
- **Candidate 4 (subscriber persistent log):** in-cycle flag during Phase A build — if consumer-side migration surfaces subscriber timing questions, surface for inline scope.
- **Candidate 5 (task templates):** out-of-scope lock — Phase A explicitly locks task templates out; if signal surfaces during Phase A, defer to dedicated investigation arc per Entry 23 build-prompt-spec failure pattern.
- **Candidate 6 (dual-write unification):** v2a-dependency-lock — ships post-v2a stable only; not Phase A scope.
- **Plugin-field promotion (audit C.2 #7):** consolidation-lock — plugin contracts v1-locked; field promotion requires plugin contract version bump + consumer migration outside v2c scope. Defers to consolidation arc (v3-era or substrate-cleanup sub-arc).

### 6.5 Adjacent substrate disposition per Entry 25

Per Entry 25, out-of-scope locks specify adjacent substrate disposition:

- **Workflow Builder authoring substrate (Phase B scope):** v2c-α extends `workflow_engine.py` action handlers (runtime substrate); Workflow Builder authoring UI presents the new action types to authors but is NOT rebuilt in Phase A. The pairing rebuild ships at Phase B.
- **Document Builder substrate (Phase C scope):** untouched by Phase A.
- **Admin-realm Studio-builder boot adapter (Q-B1 substrate):** untouched by Phase A.

---

## §7. Honest cost

### 7.1 Per-sub-arc LOC envelope

| Sub-arc | LOC (low) | LOC (high) | Calibration band (Entry 24) |
|---------|-----------|------------|------------------------------|
| v2a-α | 1,050 | 1,650 | within band |
| v2a-β (collapsed) | 1,150 | 1,850 | within band; safety_program upper-bound per Phase 8d.1 |
| v2a-γ | 600 | 950 | within band |
| v2c-α | 1,000 | 1,700 | within band |
| **Phase A total** | **3,800** | **6,150** | **see §7.4 ceiling status** |

### 7.2 v2a cumulative

~2,800–4,400 LOC across 3 sub-arcs (audit B.3 anchor verified by per-sub-arc sum).

### 7.3 v2c Phase A subset cumulative

~1,000–1,700 LOC (candidates 1 + 2 only; candidates 3, 4, 5, 6 deferred per §2.2).

### 7.4 Ceiling-violation status per Entry 24

**Phase A high-end (~6,150 LOC) marginally exceeds the 6,000 single-phase trigger ceiling per Entry 24.** The low-end (~3,800 LOC) stays comfortably under.

**Recommendation:** accept the marginal high-end overshoot as the calibration band per Entry 24 — Phase A scope is substrate-shape coherent per Entry 30; sub-arc decomposition provides natural commit-granularity per Entry 26; per-sub-arc operator-confirm gates provide signal-driven scope adjustment opportunity. Phase 4 does NOT recommend tightening the subset further; subset is already minimal (Phase A v2c excludes 4 of 6 candidates).

**Operator decision pivot** per §8 open question 2: if operator chooses to ship v2c-α candidate 2 only (workflow nodes) and defer candidate 1 (escalation routing) on signal-pattern-strength reading, Phase A high-end drops to ~5,150 LOC and stays under ceiling. Alternative shapes surfaced for operator confirmation.

### 7.5 Test cohort accumulation

Per audit A.5 anchor (214 test functions at v1) + Phase A additions:
- v2a-α: ~30–50 new tests (4 consumer-side parity test cohorts + cross-queue regression).
- v2a-β: ~35–55 new tests (4 consumer-side parity + safety_program AI-content-invariant cohort per Phase 8d.1).
- v2a-γ: ~20–35 new tests (2 consumer-side parity + period-lock cohort).
- v2c-α: ~30–45 new tests (escalation_chain + 3 workflow node parity tests per Phase 8b adapter discipline).
- **Phase A total:** ~115–185 new tests, accumulating to ~329–399 task substrate test functions at Phase A close.

### 7.6 Per-sub-arc commit-shape evaluation summary

Per §3.6 + Entry 26:
- v2a-α: single-commit-at-arc-close.
- v2a-β: multi-commit-within-arc-identity (safety_program separable per Phase 8d.1 AI-parity discipline).
- v2a-γ: single-commit-at-arc-close.
- v2c-α: multi-commit-within-arc-identity (4 separable units per Phase 8b parity discipline).

Phase A commit count: ~4 single-commit + ~6 multi-commit = ~10 commits across Phase A close + interim.

### 7.7 Migration head

Phase A may advance migration head with r110 (escalation_chain CHECK constraint extension on `task_routing_rule`) per v2c-α. v2a sub-arcs do NOT advance migration head (consumer-side read-path migration is service-layer + frontend; no schema change). v2c-α candidate 1 advances head; v2c-α candidate 2 does not.

---

## §8. Open questions for operator resolution

Five open questions surface for operator decision before Phase 5 build prompt drafts. Three are explicitly enumerated upfront as adjudications; two are audit-surfaced additional items.

### 8.1 Adjudication 1 — Sub-arc decomposition

**Question:** which collapse option locks for Phase A sub-arc decomposition?

**Phase 4 recommendation:** Option (b) — collapse v2a-δ (email_unclassified) into v2a-β (per-record cluster). Yields 6 total sub-arcs (3 v2a + 3 v2c) of which Phase A scopes 4 (3 v2a + 1 v2c-α). Substrate-shape coherence per Entry 30; cardinality coherence within collapsed v2a-β; commit-shape practicality per Entry 26; operator-confirm gate frequency manageable.

**Alternative paths:**
- **Option (a)** — collapse v2a-γ into v2a-α. Trade-off: v2a-α swells to 6-queue cluster (mixes per-anomaly + per-job + per-review-item cardinality); substrate-shape coherence reduces.
- **Option (c)** — preserve 4 v2a sub-arcs; collapse v2c-β into v2c-α. Trade-off: Phase A v2c subset already excludes v2c-β per §2.2; option moot under §2.2 subset selection.
- **Option (d)** — preserve 7 sub-arcs. Trade-off: operator-confirm gate frequency higher; over-decomposition risk per audit D.3.

**Operator decision pivot:** does Phase A sub-arc count = 4 (Option b recommended) or = 5 (Option d preserving 7 minus 2 deferred = 5 in Phase A) hit the right granularity balance?

### 8.2 Adjudication 2 — v2c subset selection

**Question:** which v2c candidates ship in Phase A?

**Phase 4 recommendation:** candidates 1 (escalation routing) + 2 (additional workflow nodes). Defer candidates 3 (6th plugin), 4 (subscriber log), 5 (task templates), 6 (dual-write unification).

**Alternative paths:**
- **Ship candidate 2 only, defer candidate 1.** Trade-off: if operator reads escalation routing signal pattern from phasing §5.2 as weaker than workflow-node signal, defer escalation routing; drops Phase A high-end LOC under 6,000 ceiling cleanly.
- **Ship candidate 1 only, defer candidate 2.** Trade-off: workflow-node signal more uncertain than escalation routing signal from phasing §5.2 anchor; safer subset.
- **Defer all v2c candidates; Phase A is v2a-only.** Trade-off: cleanest scope; v2c-α dispatches as separate arc post-v2a. Conservative if operator wants v2a stability before refinement.
- **Include candidate 4 (subscriber log) in Phase A.** Trade-off: small LOC; potentially valuable for v2a debugging; but no operator-validated signal yet (anti-signal per Entry 2 risk).

**Operator decision pivot:** what's the strongest signal pattern reading from phasing §5.2 — escalation routing, workflow nodes, both, or neither yet?

### 8.3 Adjudication 3 — `description` field canonical-substrate

**Question:** when a task is created from an AgentAnomaly (producer side), and both `AgentAnomaly.description` (text) and `VaultItem.description` (text on the task row) carry the description text, which substrate is authoritative for ongoing edits?

**Phase 4 recommendation:** **original substrate (AgentAnomaly) authoritative at producer-side creation time; task substrate inherits at create-time via verbatim copy; ongoing edits adjudicated per task lifecycle.** Specifically: producer composes task description from anomaly description verbatim at create time (already the pattern per audit Section A producer site inspection); task substrate's description becomes the canonical source for task-lifecycle-related description edits (operator annotations, completion notes); AgentAnomaly.description remains canonical for source-business-state semantics (the original anomaly observation).

**Alternative paths:**
- **Task substrate fully authoritative post-create.** Trade-off: simpler ongoing-edit semantics; loses source-business-state immutability.
- **Original substrate fully authoritative; task substrate's description always reads through dual-write mirror.** Trade-off: preserves source-business-state immutability; complicates task-lifecycle edits.
- **Add `description_source` discriminator column to `task_details`.** Trade-off: substrate extension; per Entry 17 substrate-prescience-meets-second-consumer this is acceptable if signal surfaces; without signal it's premature.

**Operator decision pivot:** is task-lifecycle description editing an observed-or-anticipated use pattern, or do tasks read description as immutable post-create?

### 8.4 v2a operational coexistence retirement timing

**Question (audit-surfaced):** when do original-substrate query paths in `engine.py` retire?

**Phase 4 recommendation:** **forensic-fallback preservation window of one full Phase A duration (post-v2a close → post-v2c-α close).** Specifically: original-substrate query paths persist as forensic-fallback throughout Phase A; v2c-γ (post-Phase-A candidate 6) scopes retirement after Phase A stability validated. Retirement migration is the canonical home for dual-write unification per Entry 13 substrate-transition discipline.

**Alternative paths:**
- **Retire forensic-fallback at v2a sub-arc close.** Trade-off: cleaner substrate; loses operational coexistence safety net per Phase 8b canon.
- **Preserve forensic-fallback indefinitely (no retirement).** Trade-off: ongoing dual-write complexity; substrate hygiene degrades.
- **Retire forensic-fallback per-queue at each v2a sub-arc close.** Trade-off: per-sub-arc cleanup cost; per-queue parity tests already gate.

**Operator decision pivot:** how long does Phase 8b operational coexistence safety net need to persist post-task-substrate-canonical-read in operator's workflow-shape risk assessment?

### 8.5 Task templates plugin contract impact

**Question (audit-surfaced, §2.1 candidate 5):** if task templates ship (deferred from Phase A per §2.2), do they require plugin contract extension or new plugin category?

**Phase 4 recommendation:** **dedicate separate investigation arc when signal surfaces.** Per Entry 23 build-prompt-spec failure pattern, refactor scope hides architectural decisions — task templates may extend `task_creators` plugin contract (acceptable consolidation work) OR introduce a new plugin category (significant substrate work). The investigation arc surfaces which.

**Alternative paths:**
- **Lock task templates as `task_creators` contract extension.** Trade-off: pre-locks architectural decision; risks Entry 23 failure pattern.
- **Lock task templates as new plugin category.** Trade-off: pre-locks; risks unnecessary substrate complexity.
- **Defer indefinitely.** Trade-off: signal may surface during Phase A v2a build; deferring indefinitely risks reactive scope-expansion.

**Operator decision pivot:** does operator anticipate task template signal during Phase A v2a build, or post-Phase-A?

---

## Phase 4 closing

Phase 4 phasing recommendation closes. Deliverable shipped at `docs/investigations/task_substrate_v2a_v2c_phasing.md` per Entry 27 8-section structure. Per Entry 31 bounded-decision-per-arc explicit naming, Phase 4 bounded decision = "produce phasing recommendation deliverable per Entry 27 8-section structure; surface adjudications for operator confirmation; lock no Phase 5 build prompt content; lock no scope outside Phase A" — bounded decision satisfied.

**Next-gate handoff:** operator reviews Phase 4 deliverable; confirms or revises 3 adjudications + 2 audit-surfaced open questions in §8; Phase 5 build prompt drafting dispatches against confirmed Phase 4 scope.

**No material-divergence triggers fired during Phase 4 drafting.** No canon edits. No STATE.md edits. No production code. No Phase 5 build prompt content. No v2b scope. No Phase B / Phase C scope-lock. No Q-B1 substrate decision. No v1 substrate revisiting. No plugin-field promotion.

**C42 carry-forward boundary preserved** per Entry 3. **September Wilbert demo schedule explicitly NOT a signal** per operator framing locks + Entry 2 anti-signal canon.
