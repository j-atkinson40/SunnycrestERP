# Canon-Update Arc — Phase 0 Candidate Aggregation

> Read-only deliverable at the close of Phase 0 of the canon-update arc.
> Phase 0 bounded decision: aggregate canon candidates from the accumulated
> lineage. Cull is Phase 1's bounded decision; entry drafting is Phase 2's
> bounded decision. Operator-confirm gate before Phase 1 dispatches.
>
> Persistent storage from start per the canon discipline established at
> v2 investigation Phase 3 close (see C7 below).

## Phase 0 metadata

- **Arc context:** Canon-update arc against ~71+ accumulated candidates from WB cycle + studio nav arc + task substrate v1 investigation + (c) build + v2 investigation + v1 build
- **HEAD at aggregation:** `7b00942`
- **DECISIONS.md entry count at aggregation:** 42 existing entries
- **Aggregation date:** 2026-05-26
- **Total candidates aggregated:** 92
- **Worthiness tag distribution:** strong 36 / moderate 32 / weak 14 / cull-likely 6 / needs-operator-decision 4
- **Altitude distribution:** substrate-decision 16 / meta-discipline 27 / lineage-fact 9 / dispatch-pattern 14 / build-pattern 17 / verification-pattern 9
- **Source distribution:** state doc §7 (12 auto-include) + completion artifact §4 (15 auto-include) + phasing doc §6.8 (6 explicit) + WB cycle commit bodies (~32) + studio nav arc (~6) + v1 build commit bodies (~12) + cross-arc lineage observations (~9)

---

## Candidates

### C1 — Investigation-first arc discipline at investigation altitude

- **Altitude:** meta-discipline
- **Surface source(s):** state doc `bc7c4ba` §7 entry 1; v1 investigation arc lineage (`57d8210`)
- **Substantive shape:** Audit-first phase within investigations; operator-observable upgrade signals over architecture-observable; sequenced not bundled candidate-move relationships; build-arc ownership partitioning of open questions. Applied recursively — investigations themselves benefit from the discipline they recommend for build arcs.
- **Relationship to existing canon:** orthogonal — extends investigation-first canon implied by 2026-05-19 (late PM) "Read-only investigation before fix-prompt drafting when staging contradicts expectation"
- **Relationship to other candidates:** overlaps C2; foundational for C8, C32, C42
- **Initial canon-worthiness assessment:** strong; load-bearing discipline that has been validated across at least 4 investigation arcs (v1 investigation, (c) investigation, v2 investigation, WB cycle umbrella).

### C2 — Investigation arcs nest cleanly when each closes its own bounded decision

- **Altitude:** meta-discipline
- **Surface source(s):** state doc §7 entry 2; completion artifact §4 entry 9
- **Substantive shape:** Sequence is `investigation-locks-hypothesis → next-investigation-locks-scope → build-arc-executes-against-locked-scope`. Resist absorbing later arcs' work into earlier arcs to save round-trips. Bounded-decision-per-arc preserves operator-decision moments; nested investigations validate at each gate before deepening.
- **Relationship to existing canon:** extends 2026-05-13 Studio shell arc decomposition pattern
- **Relationship to other candidates:** strong overlap with C1; consumed by C16 (v1 single-arc multi-phase pattern)
- **Initial canon-worthiness assessment:** strong; three-instance validation across v1 investigation → (c) investigation → v2 investigation → v1 build chain.

### C3 — Dynamic permission inheritance via subtraction-from-all-keys

- **Altitude:** build-pattern
- **Surface source(s):** state doc §7 entry 3; completion artifact §4 entry 10; (c) build arc commit `868fec3`
- **Substantive shape:** `MANAGER_DEFAULT_PERMISSIONS = get_all_permission_keys() - {users.delete, roles.delete}` in role_service lets new permission slugs (e.g. `fh_cases.aftercare`) land without per-permission role-seed updates. Director-shape roles automatically inherit.
- **Relationship to existing canon:** orthogonal — no existing entry; CLAUDE.md §RBAC is implementation-level
- **Relationship to other candidates:** none
- **Initial canon-worthiness assessment:** moderate; concrete code pattern with documented load-bearing test (aftercare end-to-end recipient resolution test). Borderline build-pattern vs implementation detail.

### C4 — Backfill scripts scale N×~50-60 LOC per substrate cohort

- **Altitude:** build-pattern
- **Surface source(s):** state doc §7 entry 4; completion artifact §4 entry 11; (c) backfill (`seed_pending_attention_backfill.py`)
- **Substantive shape:** Backfill scripts servicing N distinct substrates carry roughly N × ~50-60 LOC of handler scaffolding. Prefigure accordingly for substrate-additive arcs with multiple producer-cohort substrates. (c) shipped ~440 LOC across 7 cohorts; pre-flight envelope ~120-180 LOC misjudged due to mistaken-cohort-collapse assumption.
- **Relationship to existing canon:** none
- **Relationship to other candidates:** related to C49 (LOC calibration matures)
- **Initial canon-worthiness assessment:** moderate; concrete prefigurement guidance with two-instance support (could earn third instance at v2a adapter dispatch).

### C5 — CLAUDE.md task-centric statement

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 5; May 21-22 primary source ("a canonical articulation worth adding to CLAUDE.md")
- **Substantive shape:** "Bridgeable runs on tasks. Tasks are the connective tissue — events create tasks; tasks route to people; tasks unlock Focus work; tasks complete and trigger downstream tasks. Briefings draw from tasks. Coaching produces tasks. Communications cascade through tasks." A top-level CLAUDE.md statement that grounds future Claude sessions reading the file for the first time.
- **Relationship to existing canon:** extends CLAUDE.md §1a "Monitor through hubs. Act through the command bar." — adds task substrate as the third leg.
- **Relationship to other candidates:** foundational for C6, C9, C10, C11, C12, C13, C14
- **Initial canon-worthiness assessment:** strong; the May 21-22 conversation explicitly identified this as canon-worthy; v1 substrate now makes it operationally true.

### C6 — CLAUDE.md task substrate section

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 6
- **Substantive shape:** A new CLAUDE.md §X dedicated to task substrate explaining: VaultItem item_type='task' + task_details join table; dual lifecycle (action / reminder); subscriber registry with 7 event types; 3 plugin contracts (task creators / task surfaces / task type behaviors); 5 v1 task type plugins; how producer sites use `create_task_with_provenance`; the v1 → v2 → v3 sequenced extension. Section parallels existing CLAUDE.md §3.24 BRIDGEABLE_MASTER pointer + Vault architecture sections.
- **Relationship to existing canon:** extends CLAUDE.md
- **Relationship to other candidates:** consumed by C5; parallel to C8
- **Initial canon-worthiness assessment:** strong; v1 substrate has shipped and consumers exist; canon must catch up.

### C7 — Investigation deliverables ship to persistent storage

- **Altitude:** meta-discipline
- **Surface source(s):** state doc §7 entry 12; completion artifact §4 entry 12; state doc forward "loss event"
- **Substantive shape:** `/tmp/` is appropriate for transient computation; investigation deliverables (Phase outputs, gap analyses, design docs) that future arcs cite back to require git-tracked persistence at `docs/investigations/`. Established by the May 24 20:12 /tmp/ rotation loss event that wiped ~35,500 words across v1 investigation + (c) investigation + v2 investigation Phases 0-3.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct; foundational discipline that has held through v2 phasing, v1 build prompt, completion artifact
- **Initial canon-worthiness assessment:** strong; single-event-validated discipline that prevents future irrecoverable loss.

### C8 — Compressed-summary investigation inherits compression's lossiness

- **Altitude:** meta-discipline
- **Surface source(s):** state doc §3 retrospective; state doc §7 entry 13; completion artifact §4 entry 13
- **Substantive shape:** When an operator surfaces an architectural framing from a parallel chat, the originating chat is primary source material. Investigations dispatched against compressed summaries inherit the compression's lossiness; audit-completeness criterion should explicitly include "grep for existing substrate that the framing might assume doesn't exist." Surfaced from v1 investigation's audit-completeness failure (missed existing `Task` model, `task_service.py`, `task_triage` queue).
- **Relationship to existing canon:** extends 2026-05-19 (late PM) "Read-only investigation before fix-prompt drafting"
- **Relationship to other candidates:** C1, C2 foundational for application
- **Initial canon-worthiness assessment:** strong; concrete retrospective from a costly miss with operationally consequential downstream effects.

### C9 — PLUGIN_CONTRACTS.md: 3 new categories ratified

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 7
- **Substantive shape:** PLUGIN_CONTRACTS.md gains three canonical plugin category entries: **task creators** (input / output / guarantees / failure modes / registration mechanism + 12 provenance_kind values + composite idempotency contract), **task surfaces** (Visual Editor authoring surface for list / detail / creation / Pulse / briefings / future), **task type behaviors** (5 v1 plugins: generic_task, review_approval_task, scheduled_recurring_task, customer_communication_task, anomaly_resolution_task).
- **Relationship to existing canon:** extends PLUGIN_CONTRACTS.md
- **Relationship to other candidates:** consumed by C5, C6
- **Initial canon-worthiness assessment:** strong; substrate has shipped; canon must register the categories before v2 extensions land.

### C10 — BRIDGEABLE_MASTER.md §3.24: 12th item_type 'task' ratified

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 8; B1 commit `2fba161`
- **Substantive shape:** §3.24 unified-model section gains documented 12th item_type 'task'. Relationship to deferred 'reminder' item_type documented (reminder lifecycle folds into task substrate via lifecycle-shape; reminder item_type stays in enum but usage maps to task). Hybrid schema (VaultItem + task_details join table) documented as canonical.
- **Relationship to existing canon:** extends BRIDGEABLE_MASTER.md §3.24
- **Relationship to other candidates:** consumed by C6
- **Initial canon-worthiness assessment:** strong; live schema state.

### C11 — PLATFORM_ARCHITECTURE.md §3.4: task references in Pulse Personal layer

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 9; B3 commit `1c8dbbd`
- **Substantive shape:** §3.4 Pulse Personal layer documentation updated: `_build_tasks_item` is the canonical task-list-for-current-user surface; reads VaultItem item_type='task' JOIN task_details filtered by assignee + visibility + non-terminal lifecycle states; CASE-rank priority sort.
- **Relationship to existing canon:** extends PLATFORM_ARCHITECTURE.md §3.4
- **Relationship to other candidates:** consumed by C6
- **Initial canon-worthiness assessment:** strong; live state.

### C12 — PLATFORM_ARCHITECTURE.md §5: task→Focus relationship documented

- **Altitude:** substrate-decision
- **Surface source(s):** state doc §7 entry 10; B3 commit `1c8dbbd` (r108)
- **Substantive shape:** §5 Focus primitive documentation updated: `focus_sessions.task_id` FK → `vault_items.id` ON DELETE SET NULL; when Focus opens from task surface, linkage persists; focus_closer subscriber closes focus_sessions on task completion.
- **Relationship to existing canon:** extends PLATFORM_ARCHITECTURE.md §5
- **Relationship to other candidates:** consumed by C6
- **Initial canon-worthiness assessment:** strong; live state.

### C13 — DECISIONS.md hybrid-schema entry

- **Altitude:** lineage-fact
- **Surface source(s):** state doc §7 entry 11
- **Substantive shape:** New DECISIONS.md entry documenting the Q1 (d) hybrid schema decision: VaultItem with item_type='task' + task_details join table (vs Shape B rename or pure VaultItem). Rationale: existing `tasks` table has 8 consumers + active route surface; renaming introduces avoidable risk for façade contract; service-layer + Task façade preserves backward-compat. Existing tasks rows migrate via r107 + backfill at v1.0 close.
- **Relationship to existing canon:** new DECISIONS.md entry
- **Relationship to other candidates:** consumed by C5, C6, C10
- **Initial canon-worthiness assessment:** strong; standard architectural-decision documentation.

### C14 — Three-commit-per-substrate-arc pattern for substantively-larger arcs

- **Altitude:** dispatch-pattern
- **Surface source(s):** completion artifact §4 entry 1; B1 commit message ("Lock A revised this session from 'single commit at v1.5 close' to 'three commits within v1 arc'")
- **Substantive shape:** Lock A revision from single-commit-at-arc-close to three-commits-within-arc-identity is appropriate when arc scope exceeds ~3,000 LOC + parity-discipline work. Each commit independently shippable + Railway-deployable + verifiable; sub-arc commits reference parent arc identity in commit messages. Pattern: B1 (foundation) + B2 (parity-isolated refactor) + B3 (consumer integration).
- **Relationship to existing canon:** supersedes phasing doc §6.4 "single commit at v1 close" (specifically for substantively-larger arcs); does NOT supersede single-commit-at-arc-close for typical arcs
- **Relationship to other candidates:** related to C16 (single-arc multi-phase) — refines the original lock with execution-reality finding
- **Initial canon-worthiness assessment:** strong; load-bearing execution-reality correction with lineage-fact dimension (Lock A revision is part of v1's history).

### C15 — Dual-write transitional state during substrate-additive arcs

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §4 entry 2; B2 commit `a400d1b` (Decision A)
- **Substantive shape:** When substrate is added alongside existing implementation, dual-write keeps both write paths active during transition. Consolidation arc post-substrate-maturation unifies write paths. v1 ships dual-write at site #1 (legacy `task_service.create_task` keeps writing legacy Task row + calls `create_task_with_provenance` for substrate side); consolidation deferred to v2+.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C17 (metadata-based substrate extension transitional shape)
- **Initial canon-worthiness assessment:** strong; substrate migration pattern with consolidation-deferred discipline.

### C16 — Single-arc multi-phase internal-gate canon

- **Altitude:** dispatch-pattern
- **Surface source(s):** phasing doc §6.8 candidate 17; phasing doc §1.3 / §2.6
- **Substantive shape:** v1 ships single arc with v1.0 → v1.5 internal phase gate; commit at arc close. Pattern extensible to future multi-phase arcs where substrate validation needs to gate consumer integration. Gate is conversational; no git commit lands at internal phase close.
- **Relationship to existing canon:** related to / partially superseded by C14 (three-commit-per-substrate-arc for substantively-larger arcs); the operator-confirm-gate concept survives intact even where commit shape is revised
- **Relationship to other candidates:** refines C14
- **Initial canon-worthiness assessment:** moderate; tension with C14 needs operator resolution at Phase 1 cull (do both ship as canon? merge?).

### C17 — Metadata-based substrate extension as transitional shape

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §4 entry 3; B2 commit `a400d1b` (Decision B + D)
- **Substantive shape:** When substrate needs producer-supplied context but plugin contracts are locked, metadata path preserves substrate-locked discipline. Producer sites pass `metadata={"notification_permission_key": "...", ...}` to `create_task_with_provenance`. Phase A plugin contracts unchanged. Plugin-field promotion is consolidation target for v2+ arcs.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C15 (dual-write transitional); pattern-pair for substrate-extension arcs
- **Initial canon-worthiness assessment:** strong; concrete transitional pattern + named promotion path.

### C18 — Subscriber discrimination via metadata-presence + defensive assertion

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §4 entry 4; B2 commit `a400d1b` (Decision C)
- **Substantive shape:** When subscribers route between dispatch modes based on metadata (e.g. cohort vs direct-user dispatch), defensive assertion against task-type allowlist prevents failure-silent misconfigurations. Failure-loud is correct shape for substrate affecting user-observable behavior. Pattern: check `metadata.notification_permission_key`; if present → cohort dispatch; if absent → direct-user dispatch; defensive check against cohort-allowlist task_types; mismatch → log error + raise.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** consumed by C20 (deferred-handler-body pattern)
- **Initial canon-worthiness assessment:** strong; load-bearing-correctness pattern with rationale.

### C19 — Forward-only discipline for producer refactor arcs

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §2 closing
- **Substantive shape:** No backfill for B2 or B3 task-substrate refactor. Pre-B2 notifications remain historical fact; substrate represents go-forward operation. Pattern: when refactor changes upstream invocation path while preserving downstream behavior bit-for-bit (parity discipline), forward-only is correct discipline.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C15 (dual-write); pair: dual-write at additive substrate, forward-only at refactor.
- **Initial canon-worthiness assessment:** moderate; concrete forward-vs-backfill discipline for refactor work.

### C20 — Deferred-handler-body pattern for phased substrate

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §4 entry 5; B1/B2/B3 lineage
- **Substantive shape:** Substrate registration ships in foundation phase; handler bodies fill in at integration phase. Pattern works for any substrate with clear consumer/producer separation where consumers can be deferred without breaking producer-side correctness. Verified across 5 subscriber handler bodies: notification_dispatcher in B2; briefings_invalidator + pulse_invalidator + workflow_resumer + focus_closer in B3.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** consumed by C16 (single-arc multi-phase) + C14 (three-commit pattern)
- **Initial canon-worthiness assessment:** strong; concrete five-instance-verified pattern.

### C21 — Test isolation discipline for idempotency-load-bearing substrate

- **Altitude:** verification-pattern
- **Surface source(s):** completion artifact §4 entry 6; B3 commit `1c8dbbd` ("Test isolation: uuid-randomized provenance_ref_id per test")
- **Substantive shape:** Composite-key-enforced idempotency at substrate level changes test-isolation requirements at consumer level. Tests exercising task creation use uuid-randomized provenance_ref_id per test OR explicit per-test cleanup. Hardcoded IDs across test runs collide with substrate idempotency and produce false test fragility.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** strong; concrete pattern with documented load-bearing rationale; applies broadly to any composite-key-idempotent substrate.

### C22 — Forward-compat substrate ships when claim is real but implementation absent

- **Altitude:** build-pattern
- **Surface source(s):** completion artifact §4 entry 7; B3 commit `1c8dbbd` ("Intelligence task-creation refactor — material-divergence finding: build prompt §7.6 anticipated 3-5 Intelligence call sites; grep returned zero. Agent shipped the entry point as forward-compat substrate rather than refactoring nonexistent callers")
- **Substantive shape:** Build prompt §7.6 anticipated Intelligence refactor; grep revealed zero call sites to refactor; agent shipped canonical entry point as forward-compat substrate rather than absorbing scope changes silently. Capability-demand mapping should audit not just whether substrate consumes the conversation's claims, but whether substrate exists to refactor in the first place. Material-divergence handling: when refactor target empty, ship canonical entry point + flag in commit message.
- **Relationship to existing canon:** orthogonal — extends investigation-audit-completeness (C8) at build-time
- **Relationship to other candidates:** consumed by C8
- **Initial canon-worthiness assessment:** strong; concrete material-divergence handling pattern.

### C23 — Build-prompt-spec failure pattern (refactor scope hiding architectural decisions)

- **Altitude:** dispatch-pattern
- **Surface source(s):** completion artifact §4 entry 14; documented three instances (v1.0→v1.5 gate-spec correction, B2 (c)-refactor 4-decision correction, B3 Intelligence-refactor correction)
- **Substantive shape:** "X refactor" can hide architectural decisions when call sites use different helpers OR depend on producer-supplied context the substrate doesn't carry. Build prompts at refactor scope should specify subscriber/consumer-side mechanics, not just producer-side mapping. Pattern: refactor-shape arcs need 4-decision matrix (call surface, downstream behavior, producer-supplied context, subscriber mechanics) before dispatch.
- **Relationship to existing canon:** orthogonal — refines dispatch-discipline canon
- **Relationship to other candidates:** related to C14, C22
- **Initial canon-worthiness assessment:** strong; three-instance-validated pattern with explicit corrective shape.

### C24 — Build arc commit granularity scales with parity-discipline complexity

- **Altitude:** dispatch-pattern
- **Surface source(s):** completion artifact §4 entry 15
- **Substantive shape:** Sub-arcs deserving isolated commit boundaries are those where verification (parity, idempotency, migration safety) needs to be the sub-arc's primary success criterion rather than bundled with other substantive substrate changes. v1's B1 (foundation) + B2 ((c) refactor parity-isolated) + B3 (consumer integration) shape exemplifies. Pattern: parity-discipline-heavy work earns its own commit boundary so parity claims are reviewable in isolation.
- **Relationship to existing canon:** consumed by C14 (three-commit pattern); refinement of that pattern's "when to split" criterion
- **Relationship to other candidates:** consumed by C14
- **Initial canon-worthiness assessment:** strong; concrete split criterion.

### C25 — Operator-observable upgrade signal vocabulary canon

- **Altitude:** meta-discipline
- **Surface source(s):** phasing doc §6.8 candidate 14; phasing doc §5 detailed enumeration
- **Substantive shape:** Operator-observable workflow signals (not architecture-observable thresholds) trigger phase dispatches. Anti-signals enumerated explicitly: LOC threshold, count threshold, time threshold, engineering preference, aesthetic-completeness, sunk-cost. The signal-shape vs anti-signal-shape distinction is canon-worthy; future phasing recommendations should cite the vocabulary established at task substrate v2 phasing §5.
- **Relationship to existing canon:** extends v1 investigation's (d)-trigger discipline; canonizes the broader vocabulary
- **Relationship to other candidates:** consumed by C26 (phasing recommendation shape)
- **Initial canon-worthiness assessment:** strong; multiple-phase-validated vocabulary; load-bearing for any future multi-phase architecture sequencing.

### C26 — Phasing recommendation shape canon

- **Altitude:** dispatch-pattern
- **Surface source(s):** phasing doc §6.8 candidate 15
- **Substantive shape:** The 8-section structure of task substrate v2 Phase 4 phasing recommendation (substrate phase final-lock + integration phase final-lock + v2 sub-arc grouping + v3 arc shape + upgrade signals + cross-version + honest cost + open questions) is a canonical Phase 4 deliverable shape for any future multi-phase architecture sequencing.
- **Relationship to existing canon:** orthogonal — new dispatch-pattern entry
- **Relationship to other candidates:** consumes C25
- **Initial canon-worthiness assessment:** moderate; single-instance validation; could earn second instance at next multi-phase arc.

### C27 — Adapter-substrate vs absorbed-into-substrate decision canon

- **Altitude:** substrate-decision
- **Surface source(s):** phasing doc §6.8 candidate 16
- **Substantive shape:** Recommended pattern: adapter-substrate preserves operational continuity; absorbed-into-substrate (refactor each substrate to be task-driven internally) defers to consolidation arc when operator-validated. v2a is the first arc exercising this. Pattern: when adding canonical substrate alongside existing substrates, the absorption decision should default to adapter pattern for first-shipped iteration; absorption is later consolidation work.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C15 (dual-write transitional), C19 (forward-only)
- **Initial canon-worthiness assessment:** moderate; named pattern with explicit default; will earn additional instances as v2a / v2b / v2c ship.

### C28 — Test cohort accumulation across multi-arc lineage canon

- **Altitude:** dispatch-pattern
- **Surface source(s):** phasing doc §6.8 candidate 18
- **Substantive shape:** ~1,050-1,850 tests across the full task substrate vision (v1+v2+v3) is the order of magnitude. Future arc lineages can use as reference for envelope-setting on test-cohort scoping.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** weak; calibration data point more than canon shape; cull-likely unless second-arc-lineage validation surfaces.

### C29 — Customer-facing portal forward-compat canon

- **Altitude:** substrate-decision
- **Surface source(s):** phasing doc §6.8 candidate 19
- **Substantive shape:** Schema supports portal-shape from v1; visibility enforcement is operator-only in v1; portal query paths activate at v2/v3 per signals. Pattern extensible to future cross-realm substrate work: schema columns ship at v1 enabling forward-compat without requiring v1 implementation of all realms. `assignee_realm`/`assignee_portal_user_id` columns are the working example.
- **Relationship to existing canon:** extends SPACES_ARCHITECTURE §10 portal-as-space-with-modifiers canon
- **Relationship to other candidates:** consumes C25 (operator-observable signals dictate portal activation timing)
- **Initial canon-worthiness assessment:** strong; concrete cross-realm-substrate-extension pattern with operational rationale.

### C30 — Mirror-structurally in dispatch prompts implies more LOC than envelopes anticipate

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-cycle-followup-2 commit `33d5721` (canon candidate α: "Mirror structurally in dispatch prompts implies more LOC than investigation envelopes anticipate")
- **Substantive shape:** Structural-parity mirroring duplicates module surface area; envelope estimates need to account for full method surface count × per-method LOC + matching test coverage. WB-cycle-followup-2 shipped ~885 LOC vs ~230-380 envelope (2.3× overrun). Three-instance small-arc pattern: WB-cycle-followup-1 30% over, WB-cycle-followup-2 130% over.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C49 (LOC calibration matures)
- **Initial canon-worthiness assessment:** moderate; three-instance pattern at small-arc scale; concrete prefigurement guidance.

### C31 — Re-export shim pattern preserves consumer sites during module-internal substrate migration

- **Altitude:** build-pattern
- **Surface source(s):** WB-cycle-followup-2 commit `33d5721` (canon candidate β)
- **Substantive shape:** Re-export shim pattern preserves consumer sites with zero churn during module-internal substrate migration. Pattern: replace module internals with re-exports; consumers unchanged. WB-cycle-followup-2's `widget-builder-service.ts` became re-export shim from `visual-editor-widgets-service`; 5 existing consumers + 2 test mocks unchanged.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C32 (realm-agnostic service layer)
- **Initial canon-worthiness assessment:** strong; concrete pattern with documented zero-churn rationale.

### C32 — Realm-agnostic service layer enables realm-additive endpoint duplication

- **Altitude:** substrate-decision
- **Surface source(s):** WB-cycle-followup-2 commit `33d5721` (canon candidate γ); auth-realm investigation `1303de9`
- **Substantive shape:** When service layer takes no auth-realm dependency, parallel routes in different auth realms consume same service verbatim. Lowest-risk cross-realm substrate pattern. Widget Builder service layer realm-agnostic → consumed verbatim by both tenant and platform realms after WB-cycle-followup-2 fix.
- **Relationship to existing canon:** extends CLAUDE.md §4 admin platform architecture
- **Relationship to other candidates:** related to C31 (shim pattern)
- **Initial canon-worthiness assessment:** strong; concrete pattern for cross-realm work + lowest-risk discipline.

### C33 — `last_edit_session_actor_id` without FK to users.id avoids audit-attribution dance

- **Altitude:** build-pattern
- **Surface source(s):** WB-cycle-followup-2 commit `33d5721` (canon candidate δ)
- **Substantive shape:** Avoiding FK to users.id for actor tracking sidesteps the audit-attribution dance that other admin editors require (CLAUDE.md §4 PlatformUser vs User FK constraint discussion). Worth knowing for future platform-tier authoring substrate. Trade-off: looser referential integrity for cross-realm flexibility.
- **Relationship to existing canon:** extends CLAUDE.md §4 audit-attribution-limitation discussion
- **Relationship to other candidates:** related to C32
- **Initial canon-worthiness assessment:** moderate; concrete trade-off with cross-realm authoring rationale.

### C34 — Substrate-prescience-meets-second-consumer pattern

- **Altitude:** build-pattern
- **Surface source(s):** WB-cycle-followup-1 commit `537ebff` (canon candidate 1)
- **Substantive shape:** Substrate authored with future-consumer-in-mind produces clean consumption PLUS minimal disambiguator extension at the boundary the original author couldn't fully anticipate. F-1.1 overrideHref + WB-cycle-followup-1 (testIdSuffix per-entry disambiguator) is canonical example. Pattern: even prescient substrate accumulates one minimal extension per additional consumer.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C36 (substrate authored with future-consumer-in-mind)
- **Initial canon-worthiness assessment:** moderate; concrete two-consumer pattern; could earn third instance at Page Builder / Document Builder palette dispatch.

### C35 — Smaller arcs have larger percentage variance (LOC calibration)

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-cycle-followup-1 commit `537ebff` (canon candidate 2)
- **Substantive shape:** Smaller arcs have larger percentage variance because absolute LOC of "one substantive refinement" is fixed; smaller envelopes amplify impact. Worth knowing for future small-arc estimation. Refines WB cycle LOC calibration discipline (C49).
- **Relationship to existing canon:** consumes C49
- **Relationship to other candidates:** consumed by C49
- **Initial canon-worthiness assessment:** weak; consume into C49 at Phase 2 entry drafting.

### C36 — Operator-facing substrate must include entry-point wiring as deliverable

- **Altitude:** dispatch-pattern
- **Surface source(s):** studio nav investigation commit `3a019e1` (canon candidate 1)
- **Substantive shape:** Operator-facing substrate cycles must include entry-point wiring (nav/rail entries, route registrations) as substrate deliverable, not follow-up. WB-1..WB-8 collective omission mirrors F-1's same gap closed by F-1.1. Pattern: substrate that ships operator-ready end-to-end must explicitly include discoverability surface in cycle's scope.
- **Relationship to existing canon:** orthogonal — new dispatch-discipline canon
- **Relationship to other candidates:** related to C37 (operator-validation surfaces entry-point gaps)
- **Initial canon-worthiness assessment:** strong; load-bearing-discoverability discipline with two-cycle validation (F + WB).

### C37 — Operator-validation surfaces entry-point gaps substrate cycles miss

- **Altitude:** verification-pattern
- **Surface source(s):** studio nav investigation commit `3a019e1` (canon candidate 2)
- **Substantive shape:** Investigation-first arcs should explicitly model discoverability/nav auditing as a substrate Area. Substrate cycles consistently miss entry-point wiring (F, WB); operator-validation closes the gap reactively. Audit-checklist addition: "is the substrate operator-discoverable from the chrome it should appear in?"
- **Relationship to existing canon:** related to C36
- **Relationship to other candidates:** consumed by C36
- **Initial canon-worthiness assessment:** strong; concrete audit-checklist addition.

### C38 — Route-target changes without companion nav-entry updates produce silent operator-perception drift

- **Altitude:** build-pattern
- **Surface source(s):** studio nav investigation commit `3a019e1` (canon candidate 3 / Surprise A); auth-realm investigation `1303de9` (adjacent finding)
- **Substantive shape:** Future substrate work that rewires existing routes must audit rail/nav entries for whether label still accurately surfaces what route now does. WB-4b silently inherited rail label "Widgets" while rewiring route target; operator-perception drift surfaced months later. Pattern: route-touching arcs need explicit nav-label-audit step.
- **Relationship to existing canon:** related to C36, C37
- **Relationship to other candidates:** related to C39 (WB-cycle-followup-1 post-deploy verification)
- **Initial canon-worthiness assessment:** strong; concrete corrective discipline.

### C39 — Discoverability ≠ functional correctness (post-deploy verification)

- **Altitude:** verification-pattern
- **Surface source(s):** auth-realm investigation commit `1303de9` (Surprise E: "WB-cycle-followup-1's post-deploy verification claim conflated discoverability — rail entry renders — with functional correctness — page loads data")
- **Substantive shape:** Future build reports must separate the two claims: discoverability (entry point renders) vs functional correctness (the consumed substrate actually works end-to-end). Sharpest canon-worthy finding from entire WB cycle plus follow-ups. Pattern: post-deploy verification checklists must include explicit functional-exercise step beyond "page renders without error."
- **Relationship to existing canon:** related to C36, C37, C38
- **Relationship to other candidates:** related to C38
- **Initial canon-worthiness assessment:** strong; "sharpest canon-worthy finding from entire WB cycle" per the source.

### C40 — Auth-realm reachability checklist before locking "substrate end-to-end operator-ready"

- **Altitude:** verification-pattern
- **Surface source(s):** auth-realm investigation `1303de9` (canon candidate 1)
- **Substantive shape:** Operator-ready substrate claim requires auth-realm reachability verification: endpoint exists in expected realm, frontend service consumes correct realm client, cross-realm boundary returns expected status. Studio-authored substrates default to platform-realm endpoints; tenant-realm endpoints reachable only from tenant subdomain.
- **Relationship to existing canon:** related to C32, C36, C39
- **Relationship to other candidates:** consumed by C39
- **Initial canon-worthiness assessment:** strong; concrete checklist item with cross-realm rationale.

### C41 — Studio-authored substrates default to platform-realm endpoints

- **Altitude:** substrate-decision
- **Surface source(s):** auth-realm investigation `1303de9` (canon candidate 2)
- **Substantive shape:** Substrates authored via Studio (which mounts at admin.* host) should default to platform-realm endpoints (`/api/platform/admin/visual-editor/*` with `get_current_platform_user`). Widget Builder substrate originally shipped on tenant router; WB-cycle-followup-2 retrofit corrected. Pattern: future Studio-builder substrates ship platform-realm from foundation.
- **Relationship to existing canon:** related to C32, C40
- **Relationship to other candidates:** consumes C40
- **Initial canon-worthiness assessment:** strong; concrete default-realm decision for future builders.

### C42 — Shared runtime-library boot adapters take client as parameter

- **Altitude:** substrate-decision
- **Surface source(s):** auth-realm investigation `1303de9` (canon candidate 3)
- **Substantive shape:** Shared runtime-library boot bridges (e.g. `registerComposedWidgets`) take auth client as parameter rather than hardcoding tenant `apiClient` or admin `adminApi`. Enables cold-start palette population on both subdomains. WB-cycle-followup-2 deferred this per Q-B1 lock; flagged for September decision.
- **Relationship to existing canon:** related to C41
- **Relationship to other candidates:** needs-operator-decision (defer status)
- **Initial canon-worthiness assessment:** needs-operator-decision; substantive lock pending September decision.

### C43 — Substrate-cycle / entry-point follow-up / functional verification 3-step pattern

- **Altitude:** dispatch-pattern
- **Surface source(s):** auth-realm investigation `1303de9` (canon candidate 4)
- **Substantive shape:** Substrate cycles closing as operator-ready end-to-end consistently surface gaps in this 3-step shape: (1) substrate cycle ships → (2) entry-point/discoverability follow-up surfaces from operator validation → (3) functional verification follow-up surfaces from second-stage operator use. F-cycle + WB-cycle both exhibit this. Pattern: substrate-cycle close-out should explicitly plan for 2 follow-up arcs as part of cycle close, not as discovered defects.
- **Relationship to existing canon:** consumes C36, C37, C39
- **Relationship to other candidates:** consumes C36, C37, C39
- **Initial canon-worthiness assessment:** strong; named multi-stage close-out pattern.

### C44 — Canonical Studio-builders mapping table (frontend mount → backend router + realm)

- **Altitude:** substrate-decision
- **Surface source(s):** auth-realm investigation `1303de9` (canon candidate 5)
- **Substantive shape:** A canonical table documenting Studio-builder substrates: frontend mount → backend route prefix → realm → client. Theme editor / component editor / Focus Builder / Widget Builder / Document Builder / Workflow Builder each appear once. Prevents future "is this on platform or tenant?" investigations.
- **Relationship to existing canon:** extends CLAUDE.md §4 admin platform architecture
- **Relationship to other candidates:** consumes C41
- **Initial canon-worthiness assessment:** strong; concrete reference table preventing recurring investigation.

### C45 — Audit-vs-redo discipline during resume work

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-8 commit `5df25a1` (canon candidate α)
- **Substantive shape:** Type-system diagnostics (unused imports; missing prop receivers; orphan exports) are kill-experience signals during resume work. Audit-first reads these signals before assuming substrate is missing. ~170 LOC audit-then-fix vs ~1,990 LOC redo. Pattern: resume agents audit-first before assuming substrate is missing.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C2 (investigation-first discipline)
- **Initial canon-worthiness assessment:** strong; concrete resume-discipline + ~12× LOC saving validation.

### C46 — Forward-compat substrate posture (unknown defaults to allowed not rejected)

- **Altitude:** build-pattern
- **Surface source(s):** WB-8 commit `5df25a1` (canon candidate β)
- **Substantive shape:** `surface_mapping` and similar cross-vocabulary tables: unknown atom_kind/target_surface defaults to "allowed" rather than "rejected". Forward-compatible to future expansion without retroactive blocking. Pattern for cross-vocabulary mapping substrates.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C53 (cross-vocabulary mapping tables are substrate)
- **Initial canon-worthiness assessment:** moderate; concrete default-posture pattern.

### C47 — JSDOM gesture limitations shape UX implementation

- **Altitude:** verification-pattern
- **Surface source(s):** WB-8 commit `5df25a1` (canon candidate γ); WB-7 commit `7e45453` (canon candidate γ)
- **Substantive shape:** Test substrate constraints inform UX patterns at substrate boundary. JSDOM cannot exercise drag-handle reorder or base-ui Select open behavior; Chevron reorder + alternative affordances ship instead. Pattern: defer JSDOM-incompatible UX flows to Playwright + cover state machine via hook-level unit tests.
- **Relationship to existing canon:** related to 2026-05-21 "All pointer-event surfaces require Playwright coverage"
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete test-substrate-constraint-shapes-UX pattern.

### C48 — Resolution chain defensive substrate

- **Altitude:** build-pattern
- **Surface source(s):** WB-8 commit `5df25a1` (canon candidate δ)
- **Substantive shape:** Edge cases (empty-string default, null blob, non-object) require explicit handling for backward-compat in chain-resolution substrate (e.g. `default_variant_id` resolution chain). Pattern: chain-resolution substrate ships with defensive null-safe handling at each chain step.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete defensive-substrate guidance.

### C49 — LOC calibration discipline matures across substrate cycle

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-8 commit `5df25a1` (canon candidate ε); WB-7 commit `7e45453` (canon candidate ζ); B1 completion artifact §1 ("Calibration band: Phase 3 design estimated ~8,980 LOC for v1; Phase 4 phasing ~5,500 + ~3,500; execution landed at ~8,200 (~9% under estimate). Within calibration discipline (WB-8 ±5% pattern)")
- **Substantive shape:** Four-instance pattern across WB cycle: WB-6 3.3× → WB-5 0.5% → WB-7 18% → WB-8 ±5%. Investigation-locked + substrate-maturity-findings + restraint-discipline together produce predictable scoping. First-of-kind substrate inherits some irreducible variance; calibration matures as substrate cycle matures. v1 task substrate lands at WB-8-band.
- **Relationship to existing canon:** consumes C35
- **Relationship to other candidates:** consumes C35
- **Initial canon-worthiness assessment:** strong; four-instance + cross-arc validation of calibration discipline.

### C50 — Substrate-extending arcs with colliding field names

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-8 investigation commit `ea7ad24` (candidate ε)
- **Substantive shape:** Future substrate work that encounters parallel substrates with colliding field names should explicitly enumerate which substrate is canonical before extending either. The two-parallel-variant-substrates finding generalizes (widget_definitions.variants column vs composition_blob.variants[]).
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C51 (Phase 1 deferrals require explicit flagging)
- **Initial canon-worthiness assessment:** moderate; concrete pattern with one-instance validation.

### C51 — Phase 1 deferrals require explicit flagging

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-8 investigation commit `ea7ad24` (candidate ζ)
- **Substantive shape:** WB-4 step 8 silently deferred without flagging exposed substrate gap (variant authoring deferred to WB-8 without surface). Future sub-arcs deferring work must surface explicitly so end-of-cycle verification catches gaps. Pattern: deferral notes in commit message; deferred-with-reason list in investigation document.
- **Relationship to existing canon:** related to C50
- **Relationship to other candidates:** consumed by C50
- **Initial canon-worthiness assessment:** moderate; concrete corrective discipline.

### C52 — Built-but-dormant as third substrate state

- **Altitude:** substrate-decision
- **Surface source(s):** WB-6 investigation `5654671` (canon candidate 2); WB-8 investigation `ea7ad24` (candidate η — "third-instance elevation candidate")
- **Substantive shape:** Substrate audits should explicitly categorize: built + operator-facing; built + dormant (substrate exists in schema/storage layer but lacks UI exposure); missing. Three-instance pattern: WB-6 saved-view cross-tenant masking + WB-7 PeekContext + WB-8 default_variant_id column all built-but-dormant. Canon-update arc may elevate from candidate to canonical state classification.
- **Relationship to existing canon:** orthogonal — new substrate-classification vocabulary
- **Relationship to other candidates:** related to C50
- **Initial canon-worthiness assessment:** strong; three-instance elevation candidate explicitly flagged by source.

### C53 — Cross-vocabulary mapping tables are substrate, not derived

- **Altitude:** substrate-decision
- **Surface source(s):** WB-8 investigation `ea7ad24` (candidate θ)
- **Substantive shape:** Vocabulary mappings (e.g. WidgetSurface ↔ TargetSurface; module name → service path) ship as data substrate, not computed mappings. The `surface_mapping.py` module is a NEW module per WB-8 Area 3 lock; not derived from existing modules at runtime. Pattern: explicit mapping table for cross-vocabulary translations + tests over the table contents.
- **Relationship to existing canon:** related to C46
- **Relationship to other candidates:** related to C46
- **Initial canon-worthiness assessment:** moderate; concrete shape decision with rationale.

### C54 — Substrate-minimal default; substrate-additive when operator-validated need surfaces

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-8 investigation `ea7ad24` (refinement to prior arcs)
- **Substantive shape:** Generalizes from WB-7 verb-vocabulary asymmetry + WB-8 Area 4 widget-scoped lock. Default: ship narrow + canonical; expand additively when operator-validated need surfaces. Resist building shared substrate before second consumer exists (it tends to drift dormant per C52).
- **Relationship to existing canon:** related to C2 (resist absorbing later arc work)
- **Relationship to other candidates:** consumes C52
- **Initial canon-worthiness assessment:** strong; multi-arc-validated restraint discipline.

### C55 — Umbrella investigations don't catch parallel/dormant substrates

- **Altitude:** verification-pattern
- **Surface source(s):** WB-8 investigation `ea7ad24` (four-instance audit pattern)
- **Substantive shape:** Sub-arc audit-first phase consistently surfaces parallel/dormant substrates that umbrella investigations miss. Four-instance pattern: WB-6 (saved-view substrate mature), WB-5 (canvas preview plumbing in place), WB-7 (R-4.0 substrate existence), WB-8 (two parallel variant substrates). Worth canon-flagging: umbrella investigation lock + sub-arc audit-first checkpoint as paired discipline.
- **Relationship to existing canon:** related to C1 (audit-first phase) and C8 (compressed-summary lossiness)
- **Relationship to other candidates:** consumes C1, C8
- **Initial canon-worthiness assessment:** strong; four-instance-validated pattern.

### C56 — Atom file structure consolidation pattern

- **Altitude:** build-pattern
- **Surface source(s):** WB-7 commit `7e45453` (canon candidate α)
- **Substantive shape:** Atoms live in `runtime/atoms/index.tsx`, not per-atom dedicated files. Future atom-touching sub-arcs should read layout first per substrate-shape discovery discipline. Pattern: substrate-shape discovery is read-before-extend.
- **Relationship to existing canon:** related to C8 (audit-completeness criterion)
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** weak; narrowly WB-internal; cull-likely or merge into broader read-before-extend pattern.

### C57 — react-router useNavigate Router context requirement in atom tests

- **Altitude:** verification-pattern
- **Surface source(s):** WB-7 commit `7e45453` (canon candidate β)
- **Substantive shape:** First atom consuming routing established `renderWithContext` helper. Pattern for future routing-consuming atoms or runtime components: provide React Router context in test renders to avoid useNavigate-throws.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** weak; implementation-detail; cull-likely.

### C58 — Pydantic Annotated[Union, Discriminator] + strict validator pattern

- **Altitude:** build-pattern
- **Surface source(s):** WB-7 commit `7e45453` (canon candidate δ)
- **Substantive shape:** For discriminated-union schemas needing operator-friendly per-verb errors: Pydantic `Annotated[Union, Discriminator(...)]` + strict validator layer + per-discriminator config. Pattern generalizes for future discriminated-union schemas (workflow node configs, action specs).
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete schema pattern with rationale.

### C59 — Phase 1 Literal narrowing as bounded-state-flip substrate

- **Altitude:** build-pattern
- **Surface source(s):** WB-7 commit `7e45453` (canon candidate ε)
- **Substantive shape:** `mutate_kind = Literal['anomaly_acknowledge']` forces single-option Select with no-op onChange; future kinds expand additively. Pattern for §12.6a bounded-state-flip substrate Phase 1 narrowing: ship the discriminator infrastructure with single-value type; expand the discriminator literal additively.
- **Relationship to existing canon:** related to C54 (substrate-minimal default)
- **Relationship to other candidates:** related to C54
- **Initial canon-worthiness assessment:** moderate; concrete narrowing pattern.

### C60 — Verb-vocabulary asymmetry as architectural reflection

- **Altitude:** substrate-decision
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate B); WB-7 commit `7e45453`
- **Substantive shape:** R-4.0 page-level admin verbs vs widget-level row-context verbs differ structurally because authoring surfaces differ. Shared dispatcher infrastructure with per-surface verb sets is the canonical pattern (vs forcing identical verb vocabularies across surfaces). Future builders (Page Builder, Document Builder) will have their own verb vocabularies on shared dispatcher.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** related to C32, C44
- **Initial canon-worthiness assessment:** strong; substrate-decision-with-rationale.

### C61 — Substrate reuse > parallelism (R-4.0 consumption + extension)

- **Altitude:** substrate-decision
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate A)
- **Substantive shape:** Rather than build parallel substrate, extend existing substrate where verb-vocabulary asymmetry warrants. WB-7 consumed R-4.0 dispatcher + extended for 2 new verbs (open_peek + mutate) + extended ParameterBindingRef from 7 to 8 sources (current_row). Lowest-risk substrate-additive pattern.
- **Relationship to existing canon:** related to C32
- **Relationship to other candidates:** consumes C32
- **Initial canon-worthiness assessment:** strong; concrete reuse-discipline with multiple-verbs validation.

### C62 — Admin-preview non-dispatching as safety substrate

- **Altitude:** build-pattern
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate C)
- **Substantive shape:** Operator authoring sees what action would do without firing. Preview substrate (WB-6 BindingPreviewCard precedent + WB-7 ActionPreviewCard) extends to action verification. Pattern: admin-authored actions need non-dispatching preview substrate.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete UX substrate pattern.

### C63 — Single-dispatcher-multiple-authoring-surfaces

- **Altitude:** substrate-decision
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate D)
- **Substantive shape:** R-4 dispatcher serves R-4.0 page-level admin + WB-7 widget-level authoring + future builders. One dispatcher; multiple authoring surfaces; per-surface verb sets. Substrate pattern for dispatch-and-execute work.
- **Relationship to existing canon:** consumed by C60
- **Relationship to other candidates:** consumed by C60
- **Initial canon-worthiness assessment:** moderate; consume into C60 at Phase 2.

### C64 — current_row establishing 4 context categories (parameter binding expansion at sub-arc boundaries)

- **Altitude:** build-pattern
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate E)
- **Substantive shape:** R-4.0's 7-source parameter binding becomes 8-source with current_row addition. Pattern: parameter binding sources expand at sub-arc boundaries per consumer-surface needs. Each consumer-surface earns its own binding source as it lands.
- **Relationship to existing canon:** related to C60, C61
- **Relationship to other candidates:** consumes C61
- **Initial canon-worthiness assessment:** moderate; concrete substrate-expansion pattern.

### C65 — Mutate per-kind narrowing as §12.6a bounded-state-flip + restraint discipline

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-7 investigation `cfef35e` (candidate F)
- **Substantive shape:** Rather than ship generic mutate substrate that doesn't exist + would require substantial construction, WB-7 ships specific mutate verb that has substrate (anomaly_acknowledge) and surfaces gap for future operator-driven scope. Restraint discipline: ship what's needed against existing substrate; surface what's missing for future operator-driven scoping.
- **Relationship to existing canon:** related to C54, C59
- **Relationship to other candidates:** consumes C54, C59
- **Initial canon-worthiness assessment:** moderate; restraint-discipline instance.

### C66 — Operator-validation-driven reframes affect LOC calibration

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-6 investigation `5654671` (canon candidate 1); WB-6 commit `0ce41df`
- **Substantive shape:** Investigation-locked reframes (operator changes the framing mid-investigation) need separate LOC calibration step accounting for what the reframe implies at substrate level. WB-6 shipped 3.3× envelope partly due to operator-reframe-driven scope expansion that LOC envelope didn't recalibrate against.
- **Relationship to existing canon:** consumes C49
- **Relationship to other candidates:** consumes C49
- **Initial canon-worthiness assessment:** moderate; concrete recalibration-discipline; could merge into C49.

### C67 — Always-visible preview surfaces (operator-as-platform-builder)

- **Altitude:** substrate-decision
- **Surface source(s):** WB-6 investigation `5654671` (canon candidate 2)
- **Substantive shape:** Always-visible preview surfaces match operator-as-platform-builder framing better than hover-tooltips for substrate authoring. Substrate-level verification benefits from constant operator awareness; novice-operator-friendliness prefers peek-on-demand. Builder UX should default to always-visible preview.
- **Relationship to existing canon:** related to C62 (admin-preview non-dispatching)
- **Relationship to other candidates:** related to C62
- **Initial canon-worthiness assessment:** moderate; concrete UX substrate decision.

### C68 — BindingRef construction-site null↔undefined coercion

- **Altitude:** build-pattern
- **Surface source(s):** WB-6 investigation `5654671` (canon candidate 3)
- **Substantive shape:** BindingRef construction-site boundary requires null↔undefined coercion. Pydantic `Optional[str]` ↔ TypeScript `string | undefined` is clean at type level but emits differently at runtime. Pattern applies to all Pydantic Optional → TypeScript boundary construction sites.
- **Relationship to existing canon:** orthogonal — adds to Pydantic↔TS symmetry canon
- **Relationship to other candidates:** related to C77 (runtime-vs-Pydantic-vs-TypeScript triad symmetry)
- **Initial canon-worthiness assessment:** moderate; concrete cross-side coercion pattern.

### C69 — Runtime-tolerant substrate evolution

- **Altitude:** substrate-decision
- **Surface source(s):** WB-6 investigation `5654671` (canon candidate 4)
- **Substantive shape:** Substrate that evolves independently of consuming substrate (e.g. saved-view presentation_mode adds new vocabulary; widget runtime tolerates unknown values) should be designed for runtime-tolerance. Pattern: defensive null-safe + unknown-value-passthrough at consuming substrate boundary.
- **Relationship to existing canon:** related to C46 (forward-compat substrate posture)
- **Relationship to other candidates:** related to C46
- **Initial canon-worthiness assessment:** moderate; concrete evolution-tolerance pattern.

### C70 — In-inspector preview-value tooltip (smaller verification affordance)

- **Altitude:** substrate-decision
- **Surface source(s):** WB-6 investigation `5654671` (refinement)
- **Substantive shape:** When sub-arcs are sequenced and an intermediate operator-facing surface would help validation between them, build a smaller verification affordance into the current sub-arc rather than waiting for the next sub-arc's full substrate. WB-6 ships in-inspector preview-value tooltip; WB-5 ships full canvas preview.
- **Relationship to existing canon:** related to C20 (deferred-handler-body pattern)
- **Relationship to other candidates:** related to C20
- **Initial canon-worthiness assessment:** moderate; concrete inter-sub-arc verification-affordance pattern.

### C71 — Substrate audits enumerate cross-tier inheritance shape EVEN WHEN substrate exists

- **Altitude:** verification-pattern
- **Surface source(s):** WB-6 investigation `5654671` (process candidate 1)
- **Substantive shape:** The original WB investigation referenced "saved views" without auditing tier inheritance shape; WB-6 investigation surfaced the asymmetry (saved-views don't have Tier-1/2 inheritance; widget_definitions do). Audit must explicitly enumerate cross-tier inheritance shape per substrate even when substrate is known to exist.
- **Relationship to existing canon:** related to C8 (compressed-summary lossiness)
- **Relationship to other candidates:** consumes C8
- **Initial canon-worthiness assessment:** moderate; concrete audit-checklist addition.

### C72 — Sub-arc ordering revisions should update investigation documents

- **Altitude:** meta-discipline
- **Surface source(s):** WB-6 investigation `5654671` (process candidate 3)
- **Substantive shape:** Original WB investigation locked sub-arcs WB-5 → WB-8 in that order; operator reordered to WB-6 → WB-5. Investigation documents should be updated when sequencing inverts so future arcs read accurate order.
- **Relationship to existing canon:** related to C7 (persistent storage)
- **Relationship to other candidates:** consumes C7
- **Initial canon-worthiness assessment:** moderate; concrete document-hygiene discipline.

### C73 — Phase-1 OUT-OF-SCOPE decisions requiring substrate work to ship

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-6 investigation `5654671` (process candidate 4)
- **Substantive shape:** When investigation locks "X is Phase 1 OUT-OF-SCOPE", the locked-out work may still require some substrate to ship (e.g. references to the substrate in code, schema slots, etc.). Pattern: out-of-scope locks should specify which adjacent substrate ships to support the lockout, vs which adjacent substrate also defers.
- **Relationship to existing canon:** related to C51 (Phase 1 deferrals require explicit flagging)
- **Relationship to other candidates:** consumes C51
- **Initial canon-worthiness assessment:** moderate; concrete scope-locking-shape guidance.

### C74 — Stable substrate stays symmetric (refinement to WB-2/4b)

- **Altitude:** verification-pattern
- **Surface source(s):** WB-6 investigation `5654671` (refinement); WB-2 + WB-4b canon candidate lineage
- **Substantive shape:** Refinement to WB-2/WB-4b canon candidate: runtime-vs-Pydantic-vs-TypeScript triad symmetry audit applies most strongly to substrate that evolves across sub-arcs. Stable substrate (specified once; consumed without extension) stays symmetric. Symmetry drift is risk for evolving substrate; non-evolving substrate doesn't pay symmetry-audit cost.
- **Relationship to existing canon:** consumed by C77
- **Relationship to other candidates:** consumed by C77
- **Initial canon-worthiness assessment:** moderate; refinement-discipline; merge into C77 at Phase 2.

### C75 — Substrate-shape advice for async operator-facing surfaces

- **Altitude:** build-pattern
- **Surface source(s):** WB-5 commit `07b183b` (generalization of investigation candidate α)
- **Substantive shape:** Generalizes WB-5 investigation canon candidate α: not just dataContext-specific; substrate-shape advice for any async operator-facing surface (loading states; error states; race-condition cancellation via AbortController). Pattern: async substrate needs explicit loading-error-cancel state machine.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete async-substrate guidance.

### C76 — Substrate-vs-UX distinction maintained

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-5 commit `07b183b` (canon candidate γ — referenced in WB-8)
- **Substantive shape:** All seven locks at WB-5 close shipped substrate; revisits are UX refinements consuming existing data flow without rework cost. Substrate-vs-UX distinction: substrate decisions lock at investigation; UX decisions can be operator-validated and refined without substrate rework. Pattern: investigation-locks specify substrate shape; UX refinements ship later.
- **Relationship to existing canon:** related to C25 (operator-observable signals)
- **Relationship to other candidates:** consumed by C25
- **Initial canon-worthiness assessment:** moderate; concrete locks-vs-refinements distinction.

### C77 — Runtime-vs-Pydantic-vs-TypeScript triad symmetry audit at substrate boundaries

- **Altitude:** verification-pattern
- **Surface source(s):** WB-4a commit `3680950` (canon candidate 1); WB-4b commit `3d39598` (canon candidate 1, "two-instance pattern now"); WB-2 Surprise 1; WB-3 candidate 2; WB-6 refinement
- **Substantive shape:** Runtime-vs-Pydantic-vs-TypeScript triad symmetry audit must be structural to sub-arc execution, not optional. Multi-instance pattern: WB-2 Surprise 1 (canonical TypeScript interface drift), WB-4a Surprise 1 (runtime-vs-Pydantic drift), WB-4b (platform-wide Pydantic-runtime drift), WB-6 (stable substrate stays symmetric refinement). Symmetry not enforced at substrate boundary → reactive fix-arc work that could have been preventive investigation work.
- **Relationship to existing canon:** orthogonal — load-bearing cross-side substrate canon
- **Relationship to other candidates:** consumes C68, C74
- **Initial canon-worthiness assessment:** strong; four-instance pattern; load-bearing-correctness discipline.

### C78 — Async-data-arrival patterns require data-shape-change effects

- **Altitude:** build-pattern
- **Surface source(s):** WB-4a commit `3680950` (canon candidate 2); WB-4b commit `3d39598` (canon candidate 2)
- **Substantive shape:** Async-data-arrival patterns require effect that triggers on data shape change, distinct from URL parameter change effects. Conflating mount + URL change with async data arrival is a real bug class; symptom doesn't surface in JSDOM. Pattern: separate useEffect for data shape change vs URL change.
- **Relationship to existing canon:** related to C47, C75
- **Relationship to other candidates:** related to C75
- **Initial canon-worthiness assessment:** moderate; concrete React-effect-discipline + JSDOM-blind-spot warning.

### C79 — Studio routing substrate legacy editor-page catch-all + Spec-Override Discipline

- **Altitude:** build-pattern
- **Surface source(s):** WB-4b commit `3d39598` (canon candidate 3 / Surprise 3)
- **Substantive shape:** Studio routing substrate has legacy editor-page catch-all behavior that's load-bearing for legacy routes; new explicit routes mount above the catch-all via CLAUDE.md §12 Spec-Override Discipline. Pattern: when new explicit route needs to land before existing catch-all, mount above + flag in commit message.
- **Relationship to existing canon:** invokes CLAUDE.md §12 Spec-Override Discipline
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** moderate; concrete routing pattern.

### C80 — Shared-substrate auto-save vs per-instance auto-save distinction

- **Altitude:** substrate-decision
- **Surface source(s):** WB-4 investigation `7b9e19a` (canon candidate 1)
- **Substantive shape:** Auto-save is safe when substrate is cloned-per-instance (focus_templates → focus_compositions); auto-save is hazardous when substrate is rendered-shared (widget_definitions rendered directly). Substrate-clone-pattern analysis is load-bearing for save-semantics decisions. Pattern: investigation must audit clone-vs-shared shape before locking save semantics.
- **Relationship to existing canon:** orthogonal
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** strong; concrete substrate-classification with save-semantics implication.

### C81 — WYSIWYG discipline as canvas-layout-model constraint

- **Altitude:** substrate-decision
- **Surface source(s):** WB-4 investigation `7b9e19a` (canon candidate 2)
- **Substantive shape:** Authoring canvas layout model must match rendering layout model. Free-form-in-authoring → flex-at-runtime violates WYSIWYG. This constrains substrate choices in operator-facing builders. Pattern: builder substrate decisions are constrained by runtime rendering substrate.
- **Relationship to existing canon:** related to 2026-05-20 "Monitor canvas (grid model) and Decide canvas (free-form model) are architecturally distinct substrate concerns"
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** strong; concrete builder-vs-runtime substrate-coupling discipline.

### C82 — Sub-arc decomposition seam discovery during investigation

- **Altitude:** dispatch-pattern
- **Surface source(s):** WB-4 investigation `7b9e19a` (canon candidate 3)
- **Substantive shape:** WB-4a/WB-4b split surfaces during investigation, not during build. Decomposition is investigation work, not build-time refactoring. Pattern: investigation discovers seams; build executes against locked decomposition.
- **Relationship to existing canon:** related to 2026-05-13 (PM) Studio 1a-i sub-arc refinement
- **Relationship to other candidates:** related to C2
- **Initial canon-worthiness assessment:** strong; concrete investigation-shape-discipline.

### C83 — Investigation discipline + cross-arc audit absorption produces surprise-free sub-arcs

- **Altitude:** verification-pattern
- **Surface source(s):** WB-3 commit `4b6b173` (canon candidate 4: "FF-6 + WB-3 instances; rule-of-three pending third instance")
- **Substantive shape:** Investigation discipline + cross-arc audit absorption produces surprise-free sub-arcs. Two-instance pattern (FF-6 + WB-3); rule-of-three pending third instance. Pattern: investigation absorbs prior-arc surprises into upcoming-arc checklist; checklist execution → no new surprises.
- **Relationship to existing canon:** related to C8, C71, C83
- **Relationship to other candidates:** related to C55
- **Initial canon-worthiness assessment:** moderate; two-instance pattern; could merge into C55 (umbrella investigations don't catch parallel/dormant substrates) at Phase 2.

### C84 — Operator-conducted production audit between investigation and dispatch

- **Altitude:** verification-pattern
- **Surface source(s):** WB-3 commit `4b6b173` (canon candidate 3)
- **Substantive shape:** Operator-conducted production widget audit between investigation lock and sub-arc dispatch surfaces atom catalog calibration gaps (e.g. WB-3 added repeater_atom as 9th Phase 1 atom after operator audit). Pattern: investigation-lock → operator-conducted production audit → sub-arc-dispatch.
- **Relationship to existing canon:** related to C25 (operator-observable signals)
- **Relationship to other candidates:** related to C25
- **Initial canon-worthiness assessment:** moderate; concrete operator-audit checkpoint.

### C85 — Visual-editor metadata registry vs canvas widget-renderer registry are distinct

- **Altitude:** substrate-decision
- **Surface source(s):** WB-2 commit `95ddd16` (canon candidate); WB-3 commit `4b6b173` (canon candidate 1)
- **Substantive shape:** The visual-editor metadata registry and the canvas widget-renderer registry are distinct substrates; widget builder substrate must wire both, not just registerComponent. Two-layer widget registration (R-1.6.12) wires both; ComposedWidget runtime composes with both layers.
- **Relationship to existing canon:** extends CLAUDE.md §4 Component Registry
- **Relationship to other candidates:** none direct
- **Initial canon-worthiness assessment:** strong; concrete two-substrate-layer ratification with WB cycle implementation.

### C86 — Cross-side TypeScript symmetry locks must audit all consumption sites

- **Altitude:** verification-pattern
- **Surface source(s):** WB-2 commit `95ddd16` (canon candidate, Surprise 1); WB-3 commit `4b6b173` (canon candidate 2)
- **Substantive shape:** Cross-side TypeScript symmetry locks must audit all consumption sites, not just enumerate the canonical type file. WB-2 Surprise 1 caught canonical TypeScript interface drift via incomplete consumption-site audit. Pattern: symmetry audit includes consumption-site enumeration + per-site verification.
- **Relationship to existing canon:** consumed by C77 (triad symmetry); refinement of consumption-site dimension
- **Relationship to other candidates:** consumed by C77
- **Initial canon-worthiness assessment:** moderate; consume into C77 at Phase 2.

### C87 — Pre-flight investigation framing primary chat as authoritative source

- **Altitude:** meta-discipline
- **Surface source(s):** state doc §3 retrospective ("v1 investigation was dispatched from a compressed summary of the May 21-22 conversation rather than from the conversation itself")
- **Substantive shape:** When operator surfaces architectural insight from a parallel chat, the primary chat MUST be loaded as primary source material at investigation Phase 0, not compressed into structural summary. The compression collapsed forward-looking architectural claims into a structural restatement that lost depth. Cross-reference C8.
- **Relationship to existing canon:** related to / merges with C8 (compressed-summary lossiness)
- **Relationship to other candidates:** merge with C8
- **Initial canon-worthiness assessment:** weak; substantively the same as C8; merge at Phase 2 entry drafting.

### C88 — Bounded-decision-per-arc discipline (already canonical; lineage observation)

- **Altitude:** lineage-fact
- **Surface source(s):** Throughout v2 investigation lineage; explicit in state doc §2.5, phasing doc opening, v1 build prompt §1.2
- **Substantive shape:** Every arc opens with a stated bounded decision; arc closes when the bounded decision is closed. Pattern is already canonical (informally) — the lineage observation worth filing is the explicit naming pattern: "Bounded decision the v1 build arc closes: ..." Future arcs should adopt the explicit naming pattern.
- **Relationship to existing canon:** orthogonal; surfaces existing-but-unnamed discipline
- **Relationship to other candidates:** related to C1, C2
- **Initial canon-worthiness assessment:** moderate; existing discipline made explicit + naming-convention candidate.

### C89 — Honest-cost LOC-ceiling discipline + accept-envelope-flag-divergence pattern

- **Altitude:** dispatch-pattern
- **Surface source(s):** phasing doc §7.2 ("Phase 4 recommendation: accept the envelope but flag the divergence")
- **Substantive shape:** Total v1+v2+v3 LOC envelope ~22-31k exceeds 25k Phase 0 calibration ceiling. Two operator decisions: (1) accept 25k-31k envelope; (2) tighten v3 scope to ship under 25k. Phase 4 recommends accept + flag divergence honestly. Pattern: when calibration ceiling violation surfaces, agent flags + offers two paths + operator decides.
- **Relationship to existing canon:** consumes C25 (operator-observable signals)
- **Relationship to other candidates:** related to C25, C49
- **Initial canon-worthiness assessment:** strong; concrete calibration-ceiling-violation handling pattern.

### C90 — Per-arc pre-dispatch rescoping for distant-horizon arcs (v3)

- **Altitude:** dispatch-pattern
- **Surface source(s):** phasing doc §8.6
- **Substantive shape:** v3 arcs subject to per-arc pre-dispatch rescoping against then-current platform state and operator signal context. Distant-horizon arcs cannot be scope-locked at phasing time; rescoping discipline absorbs the temporal drift. Pattern: distant-horizon arcs ship with explicit "rescope at dispatch" lock.
- **Relationship to existing canon:** related to C25, C89
- **Relationship to other candidates:** consumes C25, C89
- **Initial canon-worthiness assessment:** strong; concrete temporal-drift-handling pattern.

### C91 — Lock A revision as canonical execution-reality-correction pattern

- **Altitude:** lineage-fact
- **Surface source(s):** B1 commit `2fba161` ("Lock A revised this session per execution-reality discipline correction (analogous to v1.0→v1.5 gate operational-reality correction earlier this session)")
- **Substantive shape:** Mid-arc execution-reality discipline correction is canonical when execution surfaces material the prompt is wrong about (per v1 build prompt §10.6). Lock A revised from "single commit at v1.5 close" to "three commits within v1 arc" mid-B1 dispatch. Pattern: when prompt wrong, STOP + surface to operator + revise lock + proceed.
- **Relationship to existing canon:** consumed by C14, C23
- **Relationship to other candidates:** consumes C14, C23
- **Initial canon-worthiness assessment:** moderate; concrete mid-arc-correction pattern with named instance.

### C92 — uuid-randomized provenance_ref_id discipline (test isolation convention)

- **Altitude:** verification-pattern
- **Surface source(s):** B3 commit `1c8dbbd` ("Test isolation: uuid-randomized provenance_ref_id per test")
- **Substantive shape:** Convention for test isolation against composite-key-idempotency: per-test `uuid.uuid4().hex` value for provenance_ref_id. Already absorbed into C21 substantively but worth distinct entry as concrete naming convention.
- **Relationship to existing canon:** consumed by C21
- **Relationship to other candidates:** merge with C21 at Phase 2
- **Initial canon-worthiness assessment:** weak; consume into C21.

---

## Phase 0 audit-shape notes

Three audit-shape signals worth surfacing to operator before Phase 1 dispatches:

1. **C36 / C37 / C39 / C43 cluster (discoverability discipline).** This cluster surfaces as four candidates with significant overlap. C43 (3-step pattern) explicitly consumes C36 + C37 + C39. Phase 1 cull should decide whether to ship as one merged entry or two-with-supersession (C43 supersedes the three; or C39 stands alone as "sharpest finding" with C36/C37 as discoverability discipline).

2. **C77 cluster (Pydantic↔TS↔Runtime symmetry).** C68, C74, C77, C86 all surface variants of the same cross-side symmetry concern. C77 is the load-bearing four-instance candidate; the other three are refinements that likely merge at Phase 2 entry drafting. Phase 1 cull may want to keep C77 only.

3. **C16 / C14 tension (commit-shape canon).** C14 (three-commit-per-substrate-arc) supersedes phasing doc §6.4 "single commit at v1 close" for substantively-larger arcs; C16 (single-arc multi-phase) preserves the operator-confirm-gate concept. The tension is real: do both ship, with C14 as exception case to C16's default? Operator decision needed at Phase 1 cull on whether canon expresses one entry with two regimes or two entries with explicit supersession reference.

4. **No candidates surface that suggest substrate redesign rather than canon filing.** All 92 candidates fit canon-update scope. No follow-on investigation-arc candidates flagged.

5. **C42 needs-operator-decision tag.** Shared runtime-library boot adapter for cold-start composed-definitions palette on admin subdomain — defer status was Q-B1 locked but operator may revisit at September demo planning. Phase 1 cull may want to flag for explicit defer-or-promote operator question.

6. **WB-cycle internal candidates C56 + C57 are narrowly WB-internal.** Cull-likely or merge at Phase 1; not load-bearing for future arcs outside the WB/atom-renderer substrate.

7. **C28 (test cohort accumulation) is calibration data, not canon shape.** Cull-likely at Phase 1.

---

*Phase 0 candidate aggregation complete. Awaiting operator review before Phase 1 cull dispatches.*
