# Task Substrate v2a-β — Pre-Dispatch Rescoping Investigation

> Read-only Per-arc pre-dispatch rescoping deliverable per DECISIONS.md 2026-05-27 Entry 32. Operates against HEAD `cce834d` (Canon-update arc close: 35 DECISIONS.md entries + 10 canon-doc edits). Verifies v2a-β sub-arc scope against actual substrate state across 7 dimensions before v2a-β build dispatches.
>
> Persistent storage from start per Entry 4. Bounded decision per Entry 31: verify v2a-β scope; surface findings; surface operator-decision questions; lock NO Phase 5 §2.B revision content; lock NO build dispatch.

## Metadata

- **Arc context:** Pre-dispatch rescoping investigation for v2a-β sub-arc per Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs)
- **HEAD at investigation:** `cce834d`
- **Investigation date:** 2026-05-27
- **Bounded decision (Entry 31):** verify v2a-β scope per Phase 4 Adjudication 1 Option (b) + Phase 5 §2.B against then-current substrate state at HEAD `cce834d`; surface findings + operator-observable signal question; produce single investigation deliverable; no canon edits / no production code / no build dispatch / no Phase 4 re-adjudication / no Phase 5 revision drafting.
- **Canon ground:** Entries 1 (investigation-methodology / audit-first), 2 (operator-observable signals + anti-signals), 3 (deferral-tracking), 4 (persistent-storage), 5 (substrate-minimal-default), 13 (substrate-transition), 17 (substrate-prescience-meets-second-consumer), 23 (build-prompt-spec failure pattern), 24 (LOC calibration), 30 (sub-arc decomposition seams), 31 (bounded-decision explicit naming), 32 (per-arc pre-dispatch rescoping)
- **Lineage:** v2a-α revision lineage produced 8 findings across 6 iterations this session — 4 acknowledgement / 2 revision / 1 architectural / 1 material-divergence. v2a-α ultimately deferred per Entry 2 anti-signal discipline (no operator-observable signal warranted v2a-α dispatch). v2a-β is structurally similar (consumer-side `_dq_*` migration) and warrants pre-dispatch rescoping verification BEFORE any build dispatch.
- **Operator framing locks:** v2b family portal OUT-OF-SCOPE; September Wilbert demo schedule explicitly NOT a signal; building-correctness-over-schedule-pressure per Entry 2 anti-signal canon; Q-B1 boundary preserved per Entry 3.

---

## §A — v2a-β consumer-side verification (4 consumers)

Per Entry 1 audit-first discipline + Phase 0 audit Section B.2 + path (ii) investigation Section E. Each consumer handler verified at file:line precision against HEAD `cce834d`.

### A.1 `_dq_ss_cert_triage` (`engine.py:664`)

- **Legacy direct-query shape:** `db.query(SocialServiceCertificate).filter(SocialServiceCertificate.company_id == user.company_id, SocialServiceCertificate.status == "pending_approval")` (lines 678–686).
- **Joins:** per-row in-loop `db.query(SalesOrder).filter(SalesOrder.id == c.order_id).first()` (lines 689–693) — N+1 read pattern; then loops `getattr(order, "customer", None)` to denormalize funeral_home_name (line 698–700).
- **Cardinality at consumption:** per-cert (1 row per SocialServiceCertificate with `status == "pending_approval"`).
- **Filter dimensions:** (`company_id`, `status == "pending_approval"`).
- **Ordering:** `generated_at.asc().nulls_last()` (line 684) — longest-waiting first.
- **Return shape:** dict with 11 fields including `certificate_number`, `deceased_name`, `funeral_home_name`, `cemetery_name=None`, `generated_at`, `status`, `order_id`, `order_number`. Denormalization sourced from related `SalesOrder` + `Customer`.
- **Post-query refinement:** N+1 SalesOrder lookup per cert row in Python loop.

### A.2 `_dq_safety_program_triage` (`engine.py:1250`)

- **Legacy direct-query shape:** `db.query(SafetyProgramGeneration, SafetyTrainingTopic).outerjoin(SafetyTrainingTopic, SafetyTrainingTopic.id == SafetyProgramGeneration.topic_id).filter(SafetyProgramGeneration.tenant_id == user.company_id, SafetyProgramGeneration.status == "pending_review")` (lines 1274–1283).
- **Joins:** outerjoin `SafetyTrainingTopic` at SQL level (single SELECT — distinct from ss_cert's N+1 pattern).
- **Cardinality at consumption:** per-generation-run (1 row per SafetyProgramGeneration in `pending_review`).
- **Filter dimensions:** (`tenant_id`, `status == "pending_review"`). Note: `tenant_id` NOT `company_id` per domain-model naming.
- **Ordering:** `generated_at.desc().nulls_last()` (line 1284) — newest first (distinct from ss_cert's oldest-first).
- **Return shape:** dict with 17 fields including `topic_id`, `topic_title`, `osha_standard`, `osha_standard_label`, `year`, `month_number`, `year_month_label`, `generation_model`, `input_tokens`, `output_tokens`, `pdf_document_id`, `has_pdf`, `osha_scrape_status`, `status`. Denormalization sourced from `SafetyTrainingTopic` + `token_usage` JSONB.
- **Post-query refinement:** `token_usage = gen.generation_token_usage or {}` (defensive JSONB unwrap) and per-row dict assembly.

### A.3 `_dq_catalog_fetch_triage` (`engine.py:1320`)

- **Legacy direct-query shape:** `db.query(UrnCatalogSyncLog).filter(UrnCatalogSyncLog.tenant_id == user.company_id, UrnCatalogSyncLog.publication_state == "pending_review")` (lines 1335–1340).
- **Joins:** none.
- **Cardinality at consumption:** per-sync-log (1 row per UrnCatalogSyncLog in `publication_state == "pending_review"`).
- **Filter dimensions:** (`tenant_id`, `publication_state == "pending_review"`). Note: `tenant_id` again, plus `publication_state` distinct from `status`.
- **Ordering:** `started_at.desc()` (line 1341) — newest first.
- **Return shape:** dict with 8 fields including `sync_log_id`, `r2_key=log.pdf_filename`, `products_preview`, `started_at`, `sync_type`, `publication_state`, `has_r2_pdf`.
- **Post-query refinement:** simple dict assembly; supersede semantics live at producer side (`catalog_fetch_adapter.py` flips older pending rows BEFORE creating new task per line 261–264 inline comment).

### A.4 `_dq_email_unclassified_triage` (`engine.py:1363`)

- **Legacy direct-query shape:** ENTIRE BODY delegates to `from app.services.classification.dispatch import list_unclassified` → `return list_unclassified(db, tenant_id=user.company_id, limit=50)` (lines 1373–1375). 3-line consumer.
- **Joins:** opaque — query lives inside `classification.list_unclassified` helper (separate substrate boundary).
- **Cardinality at consumption:** per-classification-audit-row (1 row per WorkflowEmailClassification with cascade exhaustion; replay-deduped).
- **Filter dimensions:** opaque to engine.py; `list_unclassified` helper applies tenant scope + cascade-exhausted filter + replay dedup.
- **Ordering:** opaque; helper-internal.
- **Return shape:** opaque; helper-defined.
- **Post-query refinement:** none in engine.py; engine consumer is a pure delegate.

### §A summary

| Consumer | File:line | Cardinality | Filter | Ordering | Return-shape complexity | Post-query |
|---|---|---|---|---|---|---|
| ss_cert | engine.py:664 | per-cert | company_id + status="pending_approval" | generated_at asc | 11 fields, joins SalesOrder + Customer | N+1 per-row SalesOrder fetch |
| safety_program | engine.py:1250 | per-gen | tenant_id + status="pending_review" | generated_at desc | 17 fields, outerjoin Topic + JSONB unwrap | None at SQL altitude |
| catalog_fetch | engine.py:1320 | per-sync-log | tenant_id + publication_state="pending_review" | started_at desc | 8 fields, no join | None |
| email_unclassified | engine.py:1363 | per-classification | (delegated to helper) | (delegated) | (delegated) | Pure delegate — 3 lines |

All four consumers verified at clean file:line citations. NO Phase 0 audit citation drift surfaced in §A.

**§A finding:** Consumer-side shape varies across the cluster more than the "per-record + classification-cascade cluster" framing in Phase 4 §3.2 suggests:
- 3 of 4 consumers (ss_cert, safety_program, catalog_fetch) read directly from their domain table.
- 1 of 4 (email_unclassified) delegates entirely to a separate helper `classification.list_unclassified`.
- 2 of 4 use `tenant_id` column naming; 1 uses `company_id`; 1 is opaque.
- Filter dimensions vary across 3 distinct status-column names (`status` × 2, `publication_state`, opaque).
- Ordering varies (oldest-first × 1; newest-first × 3).
- Return shape complexity varies from 3-line delegate to 17-field denormalized record.

The cluster IS substrate-shape-coherent at the cardinality dimension (per-record-with-pre-existing-pending-state-column) verified in path (ii) Section E. But the consumer-side migration implementation will need per-consumer signature handling — the helper substrate question (§C) becomes load-bearing.

---

## §B — v2a-β producer-side verification (4 producers)

Per Phase 0 audit Section A.1 + Section B.2 (Phase 0 audit cited the start of inline comment blocks; actual `create_task_with_provenance` calls are within 5–10 lines).

### B.1 ss_cert producer — `social_service_certificate_service.py:169`

- **Actual call site:** `create_task_with_provenance(db, company_id=order.company_id, ...)` at lines 169–192.
- **Phase 0 audit citation:** line 162 (start of inline B2 comment block at line 162; actual call at line 169).
- **provenance_kind:** `"integration_event"`.
- **provenance_ref_type:** `"social_service_certificate"`.
- **provenance_ref_id:** `cert.id`.
- **event_kind:** `"ss_cert_pending_approval"`.
- **task_type_key:** `"review_approval_task"`.
- **Producer-supplied context (metadata):** `notification_permission_key="invoice.approve"`, `notification_category="ss_cert_pending_approval"`, `notification_link=f"/social-service-certificates/{cert.id}"`, `notification_source_reference_type="social_service_certificate"`, `notification_source_reference_id=cert.id`.
- **Producer cardinality:** per-cert (1 task per SS cert at pending-approval transition).
- **Producer-state captured:** ONLY notification routing metadata — NOT `certificate_number`, NOT `deceased_name`, NOT `funeral_home_name`, NOT `order_number`. Display fields the consumer needs are NOT in `task_details` or `vault_items.metadata_json`.

### B.2 safety_program producer — `safety_program_generation_service.py:189`

- **Actual call site:** `create_task_with_provenance(db, company_id=gen.tenant_id, ...)` at lines 189–209.
- **Phase 0 audit citation:** line 179 (start of inline B2 comment block); actual call at line 189.
- **provenance_kind:** `"workflow_step"`.
- **provenance_ref_type:** `"safety_program_generation"`.
- **provenance_ref_id:** `gen.id`.
- **event_kind:** `"safety_program_pending_review"`.
- **task_type_key:** `"review_approval_task"`.
- **Producer-supplied context (metadata):** `notification_permission_key="safety.trainer.approve"`, `notification_category="safety_program_pending_review"`, `notification_link=f"/safety/programs/{gen.id}"`, `notification_source_reference_type="safety_program_generation"`, `notification_source_reference_id=gen.id`. Also `title` interpolates topic_title at line 197.
- **Producer cardinality:** per-gen (1 task per SafetyProgramGeneration that transitions to `pending_review`; guarded by `if gen.status == "pending_review":` at line 183).
- **Producer-state captured:** ONLY notification routing metadata + `topic_title` interpolated into title — NOT `osha_standard`, NOT `year/month`, NOT `pdf_document_id`, NOT `osha_scrape_status`. 17-field consumer return shape requires display fields that are NOT in task substrate.
- **Phase 8d.1 AI-parity invariant context:** AI-generation-content invariants are preserved at the APPROVAL action altitude (`SafetyProgramGeneration.generated_content` + `generated_html` + `pdf_document_id` frozen at staging; approve writes deterministic `SafetyProgram` rows). The READ-path migration in v2a-β does NOT touch the approval mechanics — those already migrated at Phase 8d.1 via `safety_program_adapter`. v2a-β is read-side only.

### B.3 catalog_fetch producer — `workflows/catalog_fetch_adapter.py:268`

- **Actual call site:** `create_task_with_provenance(db, company_id=company_id, ...)` at lines 268–296.
- **Phase 0 audit citation:** line 258 (start of inline B2 comment block); actual call at line 268.
- **provenance_kind:** `"integration_event"`.
- **provenance_ref_type:** `"urn_catalog_sync_log"`.
- **provenance_ref_id:** `new_log.id`.
- **event_kind:** `"catalog_sync_pending_review"`.
- **task_type_key:** `"review_approval_task"`.
- **Producer-supplied context (metadata):** `notification_permission_key="invoice.approve"`, `notification_category="catalog_sync_pending_review"`, `notification_link="/triage/catalog_fetch_triage"`, `notification_source_reference_type="urn_catalog_sync_log"`, `notification_source_reference_id=new_log.id`. Title interpolates `products_preview`.
- **Producer cardinality:** per-sync-log. Critically: supersede semantics live at PRODUCER side (lines 260–264 inline comment confirms older pending rows flipped to superseded BEFORE this task creates). The supersede happens via `UrnCatalogSyncLog` updates, NOT via task substrate cancellation.
- **Producer-state captured:** ONLY notification metadata + products_preview in title. NOT `r2_key`, NOT `started_at`, NOT `sync_type`, NOT `publication_state`. 8-field consumer return needs display fields not in task substrate.

### B.4 email_unclassified producer — `classification/dispatch.py:390`

- **Actual call site:** `create_task_with_provenance(db, company_id=email_message.tenant_id, ...)` at lines 390–411.
- **Phase 0 audit citation:** line 379 (start of inline B2 comment block); actual call at line 390.
- **provenance_kind:** `"communication_inbound"`.
- **provenance_ref_type:** `"workflow_email_classification"`.
- **provenance_ref_id:** `row.id`.
- **event_kind:** `"email_unclassified_pending"`.
- **task_type_key:** `"anomaly_resolution_task"`.
- **Producer-supplied context (metadata):** `notification_permission_key="admin"`, `notification_category="email_unclassified_pending"`, `notification_link="/triage/email_unclassified_triage"`, `notification_type="warning"`, `notification_source_reference_type="workflow_email_classification"`, `notification_source_reference_id=row.id`. Title interpolates email subject (truncated 80ch).
- **Producer-fire condition:** `if not is_replay:` (line 386) — replay re-runs are explicitly skipped at producer side. This is a substrate-locked invariant.
- **Producer cardinality:** per-classification-audit-row (1 task per cascade-exhausted classification; replay-skipped).
- **Producer-state captured:** ONLY notification metadata + email subject (truncated) in title. NOT cascade-decision-trail, NOT tier1/tier2/tier3 match results, NOT email_message.body, NOT sender. Consumer return (delegated to helper) needs everything from the EmailMessage + WorkflowEmailClassification join.

### §B summary

| Producer | File:line | provenance_kind | provenance_ref_type | task_type_key | Phase 0 audit drift | Display-field capture |
|---|---|---|---|---|---|---|
| ss_cert | service.py:169 | integration_event | social_service_certificate | review_approval_task | 7-line offset (audit cited 162 vs actual 169) — comment-block-start citation pattern | NONE |
| safety_program | service.py:189 | workflow_step | safety_program_generation | review_approval_task | 10-line offset (179 vs 189) | topic_title in title only |
| catalog_fetch | adapter.py:268 | integration_event | urn_catalog_sync_log | review_approval_task | 10-line offset (258 vs 268) | products_preview in title only |
| email_unclassified | dispatch.py:390 | communication_inbound | workflow_email_classification | anomaly_resolution_task | 11-line offset (379 vs 390) | subject (truncated 80ch) in title only |

**§B finding 1 — Phase 0 audit citation drift (minor):** Audit Section A.1 + B.2 cited the START of inline B2 comment blocks (`# v1 task substrate B2 — producer site #N refactor.` lines) for "producer site" location. Actual `create_task_with_provenance` calls are 7–11 lines later. Drift is consistent — every Phase 0 audit cite for v2a-β producers shows the same comment-block-start citation pattern. Pattern is correctable per Entry 29 inline; not a substantive substrate-state divergence. **Class (a) stale citation, NOT material divergence per Entry 23.**

**§B finding 2 — display-field capture absent at producer side (MATERIAL):** The 4 v2a-β producers persist ONLY notification routing metadata (`notification_permission_key`, `notification_category`, `notification_link`, `notification_source_reference_*`). They do NOT persist domain display fields (deceased_name, funeral_home_name, certificate_number, osha_standard, products_preview, year_month_label, cascade_decision_trail, etc.). The consumer-side return shapes (per §A.1–A.4) consume 8–17 display fields each, all sourced from the legacy domain row + joined relations.

**A naive "swap query source from domain row to task substrate" migration would lose every display field.** The migration either (a) joins back to the original domain row from the task (defeating the substrate-canonical purpose), (b) expands producer-side metadata persistence to capture all display fields (writer-side scope expansion), or (c) accepts task-substrate-only minimal display + UI-side cross-fetch (consumer-side scope expansion).

This is material-divergence shaped — analogous to v2a-α path (ii) sixth-iteration finding (helper signature provenance-keyed vs Pulse/briefings assignee-keyed). See §C + §G for adjudication.

---

## §C — v2a-β helper signature adequacy

### C.1 Proposed helper signature recap

v2a-α build prompt §2.A.3 proposed `task_service.query_open_tasks_by_provenance(db, *, company_id, provenance_kind, provenance_ref_type=None, provenance_ref_id=None, lifecycle_states=None) -> list[TaskDetails]`. Substrate-minimal-default discipline per Entry 5. Helper does NOT exist at HEAD `cce834d` (v2a-α deferred per path (ii) — proposed helper never built).

Per path (ii) sixth-iteration finding, the provenance-keyed helper would not have served Pulse + briefings (assignee-keyed orthogonal signature). v2a-α deferred per anti-signal discipline (no operator signal warranted dispatch).

### C.2 v2a-β consumers and the provenance-keyed signature

v2a-β consumers are TRIAGE WORKSPACE consumers. They render work-items by what-needs-attention-now lifecycle — provenance is the natural key (cert pending approval; gen pending review; sync_log pending review; email cascade exhausted). This is structurally distinct from Pulse + briefings (which key on assignee).

The provenance-keyed signature WOULD fit the 4 v2a-β consumers' cardinality + filter pattern at one altitude:
- ss_cert: `provenance_kind="integration_event" + provenance_ref_type="social_service_certificate"`
- safety_program: `provenance_kind="workflow_step" + provenance_ref_type="safety_program_generation"`
- catalog_fetch: `provenance_kind="integration_event" + provenance_ref_type="urn_catalog_sync_log"`
- email_unclassified: `provenance_kind="communication_inbound" + provenance_ref_type="workflow_email_classification"`

All 4 share the substrate filter shape (provenance_kind + provenance_ref_type identify the work shape). At the cardinality/filter altitude, the provenance-keyed helper serves all 4.

### C.3 But the display-field gap (§B finding 2) breaks the migration

The helper returns `list[TaskDetails]`. `TaskDetails` carries:
- Lifecycle fields (current_state, lifecycle_shape, priority, assignee_user_id, etc.)
- Provenance fields (provenance_kind, provenance_ref_type, provenance_ref_id, event_kind)
- Audit fields (created_at, updated_at, completed_at, etc.)

`TaskDetails` does NOT carry the consumer display fields:
- ss_cert needs `certificate_number`, `deceased_name`, `funeral_home_name`, `order_number`, `generated_at` (from SocialServiceCertificate + SalesOrder + Customer)
- safety_program needs `topic_title`, `osha_standard`, `year_month_label`, `pdf_document_id`, `osha_scrape_status` + 12 more (from SafetyProgramGeneration + SafetyTrainingTopic + token_usage JSONB)
- catalog_fetch needs `r2_key`, `products_preview`, `started_at`, `sync_type`, `publication_state`, `has_r2_pdf` (from UrnCatalogSyncLog)
- email_unclassified needs cascade_decision_trail, tier1/tier2/tier3 match results, subject, body, sender (from WorkflowEmailClassification + EmailMessage)

`VaultItem.metadata_json` carries only the producer-supplied notification routing metadata, not the display fields. Producers do NOT denormalize display fields into task substrate at create time.

### C.4 Three substrate-shape adjudication paths

**Path A — provenance-keyed helper + dual-substrate consumer.** Consumer queries `query_open_tasks_by_provenance` for the lifecycle anchor (which provenance refs are open), then back-joins to the original domain row (`SocialServiceCertificate.id IN (...)` etc.) to assemble display fields. Consumer-side LOC similar to current shape (still queries 2 tables); but the "canonical read path is task substrate" claim weakens — the task substrate dictates which records to render, but the original substrate still dictates what to display. Cardinality preserved.

**Path B — producer-side display-field denormalization.** Producers expand their `metadata` payload to include all display fields. Adds writer-side LOC (~80–150 LOC across 4 producers; ~20–40 LOC each). Consumer reads exclusively from task substrate. Symmetry-audit risk per Entry 33 — display fields drift (e.g. SafetyProgramGeneration.generated_at updates after task creation) accumulate as substrate-staleness. Mitigation: subscriber-substrate refresh on domain-state transitions (substrate scope expansion at v2a-β; not currently in scope).

**Path C — TaskDetails-with-source-join helper extension.** Helper expands to return `list[(TaskDetails, source_row)]` tuples with per-provenance-ref-type SQL join. Helper substrate becomes per-consumer-shape-aware (joins SocialServiceCertificate when provenance_ref_type="social_service_certificate"; joins SafetyProgramGeneration when "safety_program_generation"; etc.). This collapses to path A at SQL altitude but moves the dual-substrate complexity into the substrate helper rather than the consumer.

### C.5 Helper signature adequacy verdict

**The provenance-keyed helper is signature-adequate at the cardinality/filter dimension; signature-INADEQUATE at the display-field dimension.** Honest verdict per Entry 23:

- The original v2a-α-style helper proposed in build prompt §2.A.3 returns `list[TaskDetails]`. This signature works for triage queue cardinality + lifecycle filtering, but does NOT serve consumer-side display rendering.
- Phase 5 §2.B doesn't currently surface this gap. §2.B.3 references `task_details.source_data` (which doesn't exist — see §B finding 2; only `VaultItem.metadata_json` exists, and it carries routing metadata, not display fields).
- Either path A (dual-substrate), path B (producer denormalization), or path C (helper extension) must adjudicate before v2a-β dispatches. None is locked at Phase 5 §2.B current shape.

This is structurally analogous to v2a-α path (ii) sixth-iteration finding (helper signature provenance-keyed; consumer needs orthogonal signature). The shape is different (display-field gap vs assignee-keyed gap) but the failure-mode is identical: investigation locked a substrate helper signature without verifying consumer-substrate fit. **Material-divergence trigger fires at §C.**

---

## §D — Cardinality fit at finer altitude

Path (ii) Section E verified v2a-β cardinality alignment at coarse altitude:

| Consumer | Producer cardinality | Consumer cardinality | Aligned? |
|---|---|---|---|
| ss_cert | per-cert (`provenance_ref_id=cert.id`) | per-cert (1 row per SocialServiceCertificate) | YES |
| safety_program | per-gen (`provenance_ref_id=gen.id`) | per-gen (1 row per SafetyProgramGeneration) | YES |
| catalog_fetch | per-sync-log (`provenance_ref_id=new_log.id`) | per-sync-log (1 row per UrnCatalogSyncLog) | YES |
| email_unclassified | per-classification (`provenance_ref_id=row.id`) | per-classification (via list_unclassified helper) | YES |

At finer altitude:

- **ss_cert:** producer fires once per SocialServiceCertificate created with `status="pending_approval"`. Consumer queries SocialServiceCertificate `status == "pending_approval"`. Producer fires ONLY at certificate generation moment (line 145 db.add + line 169 task create). If certificate status flips back to pending (no current path does this, but possible future), producer would NOT re-fire — task substrate may show "done" while domain shows "pending_approval" again. State-machine alignment risk: low (no current transition path flips back). Cardinality fit: clean.

- **safety_program:** producer fires guarded by `if gen.status == "pending_review":` (line 183). Producer fires exactly once per generation entering pending_review. Approval/rejection paths transition `status` AND should transition task `current_state` via Phase 8d.1 adapter (already migrated at Phase 8d.1). Cardinality fit: clean. Supersede-on-re-generation: each new generation gets its own `gen.id`, producing a fresh task; older pending_review generations would coexist as separate tasks. No supersede semantics at safety_program — distinct from catalog_fetch.

- **catalog_fetch:** producer's `catalog_fetch_adapter.py` runs supersede-of-older-pending-rows at the UrnCatalogSyncLog level BEFORE creating the new sync_log (per audit per file inline comment lines 200–216 referenced in adapter source). The supersede happens via `UrnCatalogSyncLog.publication_state` updates. Critically: **the supersede does NOT transition the older tasks at task-substrate altitude.** Older pending tasks at task substrate stay open; the consumer's read of task substrate would still see them. The legacy consumer (reading `UrnCatalogSyncLog.publication_state == "pending_review"`) hides them; the migrated consumer (reading task substrate via provenance-keyed helper) would SHOW them. **Cardinality fit at finer altitude: BROKEN at supersede semantics.** Migration must either (a) extend producer-side supersede to also cancel older tasks (subscriber-substrate change OR producer expansion), or (b) consumer-side filters by domain `publication_state` (dual-substrate per §C path A), or (c) accept the divergence.

- **email_unclassified:** producer's `if not is_replay:` guard (line 386) is the only supersede-like mechanism. Replays write new audit rows but skip task creation. Cardinality fit: clean for non-replay path. If a replay subsequently successfully classifies a previously-cascade-exhausted email, the OLD task should arguably transition to cancelled — but no current path does this. Migration inherits this latent state-machine gap. Cardinality fit at finer altitude: clean but with latent gap.

**§D finding — catalog_fetch supersede semantics at finer altitude:** The supersede happens at UrnCatalogSyncLog substrate altitude, not at task substrate altitude. Migration must adjudicate. Phase 5 §2.B.3 catalog_fetch row 2 "Downstream behavior" claims "supersede semantics preserved (newer fetch invalidates older pending tasks via task substrate state transition to `cancelled`)." This transition is NOT currently implemented at producer side — it must be added at v2a-β build time. Producer-side LOC expansion + subscriber-substrate-or-producer-direct task cancel needed. This is a substantive substrate-shape addition not currently scoped in §2.B.

§D surfaces a substrate-shape addition required at v2a-β build: catalog_fetch supersede-to-task-cancellation wiring. Not currently in Phase 5 §2.B explicit scope. Material divergence at the substrate-shape-addition altitude.

---

## §E — safety_program AI-parity verification shape

Per Phase 4 Adjudication 1 Option (b) + Phase 5 §2.B, safety_program ships own commit per Phase 8d.1 AI-parity gate.

### E.1 Phase 8d.1 AI-parity invariant (current state)

Phase 8d.1 (May 2026) shipped `safety_program_adapter` migrating the APPROVAL action from legacy `svc.approve_generation` to triage path. Parity test substrate exists at `backend/tests/test_safety_program_migration_parity.py` (756 LOC; 9 parity categories per docstring lines 22–47):
1. Approval field-identity parity (triage vs legacy produce identical SafetyProgramGeneration + SafetyProgram writes)
2. Version-increment identity
3. Rejection field-identity parity
4. Reject-without-reason error parity
5. Non-pending-review state rejection
6. No SafetyProgram write on reject
7. No Document re-render on approve
8. Cross-tenant isolation
9. Pipeline-scale equivalence (monkey-patched Claude)

**Parity claim is frozen-content parity, NOT byte-exact AI re-run parity.** Fixture seeds SafetyProgramGeneration directly with pre-populated `generated_content` + `generated_html` + `pdf_document_id`; tests assert byte-identical APPROVAL MECHANICS writes regardless of which path invokes.

### E.2 What v2a-β safety_program commit changes

Per Phase 5 §2.B.3 Consumer #5: v2a-β migrates `_dq_safety_program_triage` (engine.py:1250) from `db.query(SafetyProgramGeneration).filter(status='pending_review')` to task-substrate query. This is READ-PATH migration — consumer rendering only. **Approval mechanics are NOT touched at v2a-β** (they migrated at Phase 8d.1 already).

### E.3 Read-side parity test substrate required at v2a-β

The Phase 8d.1 parity substrate verifies APPROVAL writes. v2a-β needs READ parity verification:
- Legacy `_dq_safety_program_triage` returns N rows with 17 fields each
- Migrated `_dq_safety_program_triage` returns N rows; per-row 17 fields must match field-by-field

The legacy read path is essentially deterministic SQL — `db.query(SafetyProgramGeneration, SafetyTrainingTopic).outerjoin(...).filter(...).order_by(...)`. Read-side parity is SQL-deterministic; does NOT require frozen-content fixtures or Claude monkey-patching.

**Test pattern for v2a-β safety_program read parity:**
1. Seed N SafetyProgramGeneration rows with assorted `status` values (pending_review × 3, approved × 1, rejected × 1, draft × 2)
2. Seed corresponding SafetyTrainingTopic rows
3. Invoke producer path to create tasks for pending_review-state generations (3 tasks)
4. Invoke legacy `_dq_safety_program_triage` → capture N rows
5. Invoke migrated `_dq_safety_program_triage` → capture N rows
6. Assert per-row field-by-field equality on 17 fields

No Claude invocation needed. No frozen-content discipline needed at v2a-β. **Read-side parity is structurally simpler than Phase 8d.1 approval parity.**

### E.4 But §C display-field gap impacts safety_program read parity

If §C path A (dual-substrate) selected: migrated read path joins SafetyProgramGeneration + SafetyTrainingTopic at SQL level (same shape as legacy); display fields available. Read parity passes deterministically.

If §C path B (producer-side denormalization) selected: producer-side `metadata` payload expansion at v2a-β build; safety_program producer adds 14 fields to metadata at line 202–208. Read parity requires producer side to write ALL display fields task creation captures. State drift risk: `gen.generated_at` updates post-task-creation → metadata stale.

If §C path C (helper extension) selected: helper itself per-provenance-ref-type joins; behaves identically to path A but moves SQL complexity into substrate.

**§E finding:** Read-side parity at safety_program is simpler than approval-side parity per Phase 8d.1; deterministic SQL means no AI-parity special discipline needed at v2a-β. But the read-side parity SHAPE depends on §C adjudication. Without §C adjudication, v2a-β safety_program parity test cohort scope cannot lock.

### E.5 LOC envelope for safety_program parity tests at v2a-β

If §C path A: ~120–180 LOC parity tests (similar shape to ss_cert + catalog_fetch + email_unclassified parity).

If §C path B: ~180–280 LOC parity tests (additional producer-side state-write coverage + state-drift edge cases).

If §C path C: ~150–220 LOC parity tests (substrate helper exposes per-provenance-ref-type joins, tests verify helper joins).

Phase 5 §2.B.7 LOC envelope ~1,150–1,850 LOC. Safety_program upper-bound currently locks against Phase 8d.1 invariant work; per §E.3, that's the wrong anchor — Phase 8d.1 invariant is already shipped. v2a-β safety_program parity scope is closer to other §B per-record cluster members (~120–180 LOC).

---

## §F — LOC envelope verification

### F.1 Phase 5 §2.B LOC envelope recap

Phase 5 §2.B.7: **~1,150–1,850 LOC** across 4 consumer migrations + cross-queue parity test cohort. Phase 4 §3.3 + §7.1 anchor: safety_program upper-bound per Phase 8d.1 AI-parity discipline.

### F.2 Per-consumer migration LOC recalibration

Per §A (consumer shape) + §B (producer shape) + §C (helper signature gap) + §D (catalog_fetch supersede gap) + §E (safety_program parity recalibration):

| Consumer | Migration LOC | Parity test LOC | Total (low) | Total (high) | Notes |
|---|---|---|---|---|---|
| ss_cert | 80–120 | 100–140 | 180 | 260 | N+1 → batched join opportunity |
| safety_program | 80–120 | 120–180 | 200 | 300 | §E.3 — Phase 8d.1 anchor overscoped |
| catalog_fetch | 100–150 (incl. supersede wiring per §D) | 100–140 | 200 | 290 | §D — substrate-shape addition |
| email_unclassified | 60–100 (helper delegate path) | 100–140 | 160 | 240 | Opaque-helper path simplest |
| Helper substrate (if §C path A): | — | — | 0 | 0 | Path A keeps shape; no helper |
| Helper substrate (if §C path B): | 80–150 producer expansion | 60–100 | 140 | 250 | Path B writer-side scope |
| Helper substrate (if §C path C): | 150–220 substrate helper | 80–120 | 230 | 340 | Path C substrate-extension |
| Cross-queue test cohort | — | 60–100 | 60 | 100 | Integration regression |
| Symmetry audit per Entry 33 | 20–40 | — | 20 | 40 | TaskDetails Pydantic-TS check |

Path-dependent totals:
- **§C Path A (dual-substrate):** ~820 (low) – ~1,230 (high) LOC. **30% UNDER current §2.B envelope low-end.**
- **§C Path B (producer denormalization):** ~960 (low) – ~1,480 (high) LOC. WITHIN §2.B envelope (~83% of high-end).
- **§C Path C (helper extension):** ~1,050 (low) – ~1,570 (high) LOC. WITHIN §2.B envelope (~85% of high-end).

### F.3 §2.B envelope verdict

Phase 5 §2.B current envelope (~1,150–1,850 LOC) is **mildly overscoped** vs §F.2 recalibration for all three §C paths. The overscoping derives from:
1. Safety_program upper-bound anchor against Phase 8d.1 AI-parity discipline (per §E.3, that's the wrong anchor — Phase 8d.1 already shipped; read-side parity is simpler).
2. Implicit assumption that all 4 consumers carry uniform complexity (per §A, email_unclassified is 3-line delegate; catalog_fetch is 8-field flat read; ss_cert + safety_program are heavier with denormalized joins).

Recalibration narrows the band to ~820–1,570 LOC depending on §C adjudication. **Within Entry 24 calibration band (no >20% drift trigger fires from §F).**

The LOC envelope itself is acceptable per Entry 24. The substantive finding is §C — adjudication of helper signature shape is required before v2a-β dispatch, and the LOC envelope shifts ~250 LOC across paths. Operator decision in §C drives the LOC anchor.

---

## §G — v2a-β scope-lock + operator-observable signal question

### G.1 Scope-lock candidate at sub-arc altitude

Per §A–§F findings, the v2a-β sub-arc per Phase 4 Adjudication 1 Option (b) + Phase 5 §2.B HOLDS at the cluster-shape altitude (4 consumers, per-record + classification-cascade cluster, cardinality alignment per path (ii) §E) but REQUIRES THREE ADJUDICATIONS before build dispatch:

**Adjudication β1 — display-field gap (§C):** which of paths A / B / C resolves the display-field shape?
- Path A: dual-substrate consumer (cleanest LOC; weakens canonical-read claim).
- Path B: producer-side denormalization (canonical-read preserved; writer-side scope; state-drift risk).
- Path C: helper substrate per-provenance-ref-type join (canonical-read preserved; substrate-extension cost).

**Adjudication β2 — catalog_fetch supersede semantics (§D):** does v2a-β build extend producer-side supersede to cancel older task substrate rows, OR does consumer-side filter dual-substrate per path A inheritance?
- Producer extension: ~30–50 LOC at `catalog_fetch_adapter.py` (subscriber-substrate or direct task cancel).
- Consumer-side filter: covered if §C path A selected.

**Adjudication β3 — safety_program parity test substrate scope (§E):** Phase 5 §2.B locks safety_program against Phase 8d.1 AI-parity invariant. §E.3 finds that anchor wrong — Phase 8d.1 invariant is at APPROVAL-action altitude (already shipped); v2a-β is read-path altitude (deterministic SQL parity, no AI involvement needed).

### G.2 Sub-arc decomposition implications

The 3 adjudications do NOT trigger Phase 4 Adjudication 1 re-adjudication. The Option (b) cluster (per-record + classification-cascade) remains substrate-shape-coherent. Adjudications β1/β2/β3 land at v2a-β sub-arc altitude, not at cross-sub-arc altitude.

Cross-sub-arc impact:
- v2a-α: not yet dispatched (deferred per path (ii)). If/when v2a-α dispatches, the AgentAnomaly cluster faces the same display-field-gap pattern (consumer queries AgentAnomaly + AgentJob; task substrate lacks display fields). §C adjudication likely generalizes.
- v2a-γ: not yet dispatched. month_end_close (per-job) + workflow_review (per-review-item) — both have direct domain-row reads with display joins. §C adjudication likely generalizes.
- v2c-α: independent (substrate-extension at workflow-engine; no display-field issue).

**§C adjudication is potentially generalizing across all 3 v2a sub-arcs.** That elevates it above "v2a-β sub-arc decision" — it's a v2a-cluster substrate-shape decision. Operator may want to lock once across v2a (substrate-prescience per Entry 17) rather than per-sub-arc.

### G.3 Operator-observable signal question per Entry 2

**Critical question per Entry 2 anti-signal canon — what operator-observable signal warrants v2a-β dispatch at this time?**

Per Phase 4 §5.1 dispatch signals for v2a-β:
- "Sunnycrest production describes safety_program + catalog_fetch + ss_cert review queues as fragmented" (extending phasing §5.2)
- "Operators describe email classification cascade fall-throughs as 'I don't know where these landed' — surfaces email_unclassified into the same shape"

**Status at HEAD `cce834d`:** No operator surfacing of either signal has been logged in canon, STATE.md, or session transcripts available for this investigation. The signals are POSSIBLE dispatch triggers; whether they've SURFACED operationally is the operator's read.

Anti-signals per Entry 2:
- 4 v2a-β consumers exist at original-substrate read path — **architecture-observable count threshold; explicitly rejected.**
- Phase 0 audit + Phase 4 phasing + Phase 5 build prompt already drafted v2a-β — **architecture-observable design completion; explicitly rejected (Entry 2 sunk-cost anti-signal).**
- v2a-α deferred per path (ii) outcome; v2a-β is "next thing to ship" — **engineering preference anti-signal; explicitly rejected.**
- Phase A LOC envelope accumulated work to date — **LOC threshold anti-signal; explicitly rejected.**
- v2c-α / Phase B / Phase C downstream wants v2a stability — **time threshold + aesthetic-completeness; explicitly rejected.**

**Per Entry 2 + path (ii) precedent:** if no operator-observable signal surfaces for v2a-β dispatch at this time, the defer-per-anti-signal pattern (v2a-α path (ii) outcome) applies symmetrically. v2a-β defers until operator surfaces matching signal.

### G.4 Material-divergence triggers fired

Per Entry 23 iterative-STOP protocol:

| Trigger | Section | Status |
|---|---|---|
| Phase 0 audit citation drift | §B (7–11 line offsets) | **Class (a) stale citation — corrected inline per Entry 29; NOT material-divergence** |
| Substrate-state divergence from Phase 0 audit | §B (display-field capture absent) | **MATERIAL — display-field gap not surfaced in Phase 0 audit or Phase 5 §2.B** |
| Helper signature inadequacy at consumer fit | §C (display-field dimension) | **MATERIAL — analogous to v2a-α path (ii) sixth-iteration finding** |
| Cardinality fit at finer altitude | §D (catalog_fetch supersede gap) | **MATERIAL — substrate-shape addition needed at v2a-β build** |
| safety_program parity verification shape | §E (Phase 8d.1 anchor overscoped) | **NOT material — Phase 8d.1 invariant is at different altitude; read-side parity simpler** |
| LOC envelope >20% drift | §F (band within tolerance) | **NOT material — recalibration band within Entry 24 tolerance** |
| Operator-observable signal absence | §G.3 | **POTENTIAL material per Entry 2 anti-signal canon — operator-decision question** |

**Three material-divergence triggers fired** (§B finding 2, §C helper inadequacy, §D supersede gap). Per Entry 23 iterative-STOP protocol, surface to operator + revise lock before v2a-β build dispatch.

The deferral question (§G.3) lifts the material divergences to a higher-altitude question: even if §C/§D adjudicated cleanly, does an operator-observable signal warrant dispatch at this time? Path (ii) precedent suggests the answer may be "defer until signal surfaces" — analogous to v2a-α outcome.

### G.5 Surfaced findings summary

| # | Finding | Disposition |
|---|---|---|
| 1 | Phase 0 audit cited inline-comment-block-start lines; actual `create_task_with_provenance` calls 7–11 lines later | Citation correctable per Entry 29; not material |
| 2 | Producers persist ONLY notification routing metadata; display fields NOT captured | MATERIAL — Phase 5 §2.B unaware of gap |
| 3 | Proposed `query_open_tasks_by_provenance` helper signature does not serve display-field rendering | MATERIAL — analogous to path (ii) sixth-iteration |
| 4 | catalog_fetch supersede semantics live at domain-row altitude; do NOT cancel older tasks at task-substrate altitude | MATERIAL — substrate-shape addition needed at build |
| 5 | safety_program parity test anchor (Phase 8d.1) is at approval altitude; v2a-β is read-path altitude (simpler parity) | Recalibration item; not material |
| 6 | LOC envelope band shifts ~250 LOC across §C paths; all paths within Entry 24 calibration band | Not material |
| 7 | §C adjudication potentially generalizes to v2a-α + v2a-γ display-field-gap pattern | Sub-arc altitude consideration; surfaces cross-sub-arc lock opportunity per Entry 17 |
| 8 | No operator-observable signal logged in canon/STATE/transcripts for v2a-β dispatch at this time | Operator-decision question per Entry 2 anti-signal canon |

### G.6 Recommended operator decision sequencing

1. **First decision (Entry 2 anti-signal):** does operator-observable signal warrant v2a-β dispatch at this time? If NO → defer v2a-β per anti-signal discipline (path (ii) precedent applies symmetrically). Investigation outcome: deferred-with-explicit-revisit-trigger per Entry 3. If YES → proceed to next decisions.

2. **If dispatch warranted: §C Adjudication β1.** Path A / B / C? Recommend operator considers Path A (dual-substrate) as default — preserves canonical-substrate disposition per Entry 13 (substrate-transition discipline allows dual-write transitional state); lowest LOC; defers absolute "canonical task substrate read" claim to v2c-γ (dual-write unification) per Phase 4 §2.1 candidate 6. Operator may prefer Path B (canonical-read-preservation) or Path C (substrate-extension prescience per Entry 17) per signal-driven scope.

3. **§C path locked:** §D Adjudication β2 inherits. Path A inherits dual-substrate filter at consumer side (no supersede issue). Path B + C require producer-side supersede-to-task-cancel wiring (~30–50 LOC at `catalog_fetch_adapter.py`).

4. **§E recalibration acknowledged:** safety_program parity scope tightens from Phase 5 §2.B safety_program-upper-bound to per-record-cluster-uniform band. Phase 8d.1 AI-parity substrate is preserved unchanged at approval-action altitude.

5. **§G.2 cross-sub-arc decision:** does §C adjudication apply at v2a-β sub-arc altitude OR generalize to v2a-cluster-wide lock per Entry 17 (substrate-prescience-meets-second-consumer)? Operator decides whether to lock once or per-sub-arc.

### G.7 Phase A close criterion implications

If v2a-β defers (G.6 step 1 → NO): Phase A close criterion shifts. Phase 5 §1.3 currently requires "v2a stable across all 10 queues; consumer-side reads from task substrate; bit-for-bit parity verified per sub-arc." With v2a-α + v2a-β both deferred per anti-signal discipline, v2a stability scope reduces to v2a-γ (2 queues) only. Phase A close criterion would lock against v2a-γ + v2c-α only — substantially narrower than original Phase A scope.

If v2a-β dispatches (G.6 step 1 → YES with §C adjudication): Phase A scope holds; v2a-β closes at the 4 v2a-β consumer migrations + cross-queue parity green; v2a-α status remains deferred independently.

---

## §H — Closing

### H.1 Bounded-decision satisfaction (Entry 31)

Bounded decision per dispatch: "verify v2a-β scope per Phase 4 Adjudication 1 Option (b) + Phase 5 §2.B against then-current substrate state at HEAD `cce834d`; surface findings + operator-observable signal question; produce single investigation deliverable; no canon edits / no production code / no build dispatch / no Phase 4 re-adjudication / no Phase 5 revision drafting."

**Bounded decision satisfied:**
- 7 sections (§A–§G) cover the 7 verification dimensions enumerated in dispatch.
- 8 surfaced findings (§G.5 table) with disposition.
- 3 material-divergence triggers fired (§B finding 2, §C helper inadequacy, §D supersede gap) per Entry 23 iterative-STOP protocol.
- Operator-observable signal question surfaced honestly (§G.3) per Entry 2 anti-signal canon.
- 5 operator-decision sequences enumerated (§G.6).
- Phase A close criterion implications surfaced (§G.7).

### H.2 Investigation discipline locks (verified at close)

- No canon edits.
- No STATE.md changes.
- No production code.
- No `git add` / `git commit` / `git push`.
- No Phase 4 re-adjudication (Option (b) cluster shape held at coarse altitude; material divergences land at v2a-β sub-arc altitude).
- No Phase 5 §2.B revision drafting (revisions surface as operator-decision questions for future Phase 5 revision arc).
- No build dispatch.
- Persistent storage at this path per Entry 4.
- Citation discipline per Entry 1 throughout (every finding cites file:line / Phase 0 audit reference / DECISIONS.md entry).
- Q-B1 boundary preserved per Entry 3.
- Phase B/C boundaries preserved per Entry 32.
- September Wilbert demo schedule NOT a signal per Entry 2.
- 114 stale Playwright screenshot deletions untouched.

### H.3 Next-gate handoff

Operator reviews this investigation deliverable. Operator decides:

1. **Signal-trigger question (G.6 step 1):** does operator-observable signal warrant v2a-β dispatch at this time? Or does anti-signal discipline (per Entry 2 + path (ii) precedent) defer v2a-β until signal surfaces?

2. **If dispatch warranted:** confirm or revise §C / §D / §E adjudications per §G.6 sequencing. Phase 5 §2.B revision dispatches against confirmed direction (separate arc, not this investigation).

3. **If dispatch deferred:** v2a-β joins v2a-α in deferral-with-explicit-revisit-trigger per Entry 3. Phase A scope contracts to v2a-γ + v2c-α only (G.7). Signal-trigger documentation lands in updated phasing doc or STATE.md per separate arc.

4. **Cross-sub-arc consideration:** §C adjudication potentially generalizes to v2a-α + v2a-γ (G.2); operator may elect cross-sub-arc lock per Entry 17 substrate-prescience-meets-second-consumer, OR per-sub-arc lock per Entry 30 sub-arc decomposition seams.

Investigation closes. No build dispatch this turn.
