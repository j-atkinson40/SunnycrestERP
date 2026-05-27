# Canon-update arc — Phase 2 drafted entries

**Arc:** canon-update (May 26, 2026)
**Phase:** Phase 2 (drafted canon text; Opus-authored against Phase 1 cull lock)
**Predecessor deliverables:**
- `docs/investigations/canon_update_candidates.md` (Phase 0: 92 candidates)
- `docs/investigations/canon_update_cull.md` (Phase 1: 31 → 35 entries post-NEEDS-OPERATOR-DECISION resolution + 10 canon-doc EXTENDS)

**This deliverable:** Verbatim Opus-authored canon text for Phase 2.A (35 DECISIONS.md entries) + Phase 2.B (10 canon-doc edits across 5 canon docs). Staging consumes this artifact to apply canon additions; this artifact persists as durable record of what was filed.

**Filing surface accounting:**
- 77 DECISIONS.md candidates → 35 entries (cluster compression + standalone filings)
- 11 canon-doc EXTENDS candidate-IDs → 10 edits (C5+C6 merge)
- 3 CULL (C28, C56, C57)
- 1 carry-forward (C42 → September-decision arc)
- Total: 92 candidates accounted

**Permission boundary:** Phase 2 canon text is Opus-authored per CLAUDE.md "Documentation write permissions (STRICT)" rule. Sonnet's role at Phase 2 close is staging this drafted text into canon docs + writing STATE.md close note (Sonnet permission scope) + drafting commit message. This artifact preserves the Opus-authored content for staging consumption; Sonnet reads from this artifact at staging time rather than reconstructing canon text from sketches.

---

# Phase 2.A — 35 DECISIONS.md entries

**Append target:** `DECISIONS.md` (append-only chronologically per existing convention)
**Date stamp:** 2026-05-26 (canon-update arc commit date; verify at staging via `date` command; update if cross-day)
**Order:** Pass 1 → Pass 5 (altitude-organized as drafted)
**Cross-reference normalization:** Internal "Entry N" references normalize to "DECISIONS.md 2026-05-26 — `<title>`" at staging (~25-30 normalizations across Phase 2.A + Phase 2.B)

---

## Pass 1 — Meta-discipline (4 entries)

### Entry 1 — Investigation-methodology canon

**Date:** 2026-05-26
**Folds:** C1 (anchor), C2, C8, C55, C71, C83, C87
**Altitude:** meta-discipline

**Rule.** Investigations follow a structured methodology: audit-first phase before hypothesis adjudication; bounded-decision-per-arc with explicit operator-confirm gates; sequenced not bundled when hypothesis spans multiple decisions; primary-source-as-authoritative when operator surfaces architectural framing from a parallel chat; cross-tier inheritance shape audited explicitly per substrate even when substrate is known to exist. Sub-arc audit-first phase catches parallel/dormant substrates that umbrella investigations miss. Cross-arc audit absorption produces surprise-free sub-arcs.

**Rationale.** Investigation-first discipline emerged across the WB cycle + studio nav arc + task substrate v1/v2 lineages as the meta-discipline that prevents the most expensive failure mode: investigations dispatched against compressed summaries inherit the compression's lossiness. The v1 task substrate investigation's H2 verdict was empirically false at the time it was made because the 31-surface inventory didn't grep for existing `tasks`-related substrate that the May 21-22 conversation's framing might have assumed didn't exist. The v2 investigation existed to correct that gap forward-looking. The same audit-completeness failure mode recurs at sub-arc altitude: WB-6 saved-view substrate maturity, WB-5 canvas preview plumbing in place, WB-7 R-4.0 substrate existence, WB-8 two parallel variant substrates — four instances where sub-arc audit-first phase caught what umbrella investigation missed. The discipline applies recursively: investigations themselves benefit from the discipline they recommend for build arcs. Bounded-decision-per-arc preserves operator-decision moments; nested investigations validate at each gate before deepening. The sequence is `investigation-locks-hypothesis → next-investigation-locks-scope → build-arc-executes-against-locked-scope`. Resist absorbing later arcs' work into earlier arcs to save round-trips.

**Implementation.** Investigation arcs open with bounded-decision statement + audit-first phase that explicitly enumerates existing substrate (`grep` before assuming substrate doesn't exist) + cross-tier inheritance audit per substrate referenced. Operator-confirm gates between phases; gate review surfaces material-divergence triggers if audit findings diverge from investigation framing. When operator surfaces architectural framing from a parallel chat, the originating chat MUST be loaded as primary source material at Phase 0, not compressed into structural summary. Sub-arc audit-first checkpoint is paired discipline with umbrella investigation lock: umbrella locks hypothesis at investigation altitude; sub-arc audit-first verifies hypothesis against then-current substrate at sub-arc altitude. Investigation absorbs prior-arc surprises into upcoming-arc checklist; checklist execution → no new surprises. Reference instances: task substrate v2 investigation arc (`bc7c4ba` / `ca88f50` / `50a07ff`), WB-cycle sub-arc audit-first phases, v1 build arc Phase A.0 inline scoping pattern.

---

### Entry 2 — Operator-observable signals canon

**Date:** 2026-05-26
**Folds:** C25 (anchor), C76, C84
**Altitude:** meta-discipline

**Rule.** Phase dispatches between sub-arcs trigger on operator-observable workflow signals, not architecture-observable thresholds. Anti-signals explicitly rejected as triggers: LOC threshold, count threshold, time threshold, engineering preference, aesthetic-completeness, sunk-cost. The substrate-vs-UX distinction holds: substrate decisions lock at investigation; UX decisions can be operator-validated and refined without substrate rework. Operator-conducted production audits between investigation lock and sub-arc dispatch surface calibration gaps that investigation alone misses.

**Rationale.** Anti-signal enumeration is canon-worthy because the temptation to dispatch on architecture-observable triggers is strong: a phasing recommendation that hits its LOC anchor "wants" to dispatch the next phase; a substrate that "looks complete" wants closure. Both fail at the operational-correctness layer because they substitute architect intuition for operator-validated need. Task substrate v2 phasing §5 enumerated anti-signals explicitly; subsequent v1 build arc dispatch decisions held the discipline (B1 → B2 → B3 each dispatched on operator confirmation of substrate validation, not on B1 LOC landing within envelope). The substrate-vs-UX distinction emerged from WB-5 close: all seven locks shipped substrate; revisits were UX refinements consuming existing data flow without rework cost. Substrate decisions lock at investigation; UX decisions ship later. Operator-conducted production audits (WB-3 added repeater_atom as 9th Phase 1 atom after operator audit of production widgets) catch calibration gaps that investigation alone misses — investigation models what the audit pool expects; production audit verifies against what actually exists.

**Implementation.** Phasing recommendations specify operator-observable signal patterns per phase boundary with concrete workflow descriptions ("Sunnycrest staff describe their Monday-morning workflow as X"). Explicit anti-signal enumeration accompanies signal specification so future readers can verify dispatch logic against the discipline. Sub-arcs dispatch on operator surfacing matching signal, not on architecture-observable counters reaching thresholds. Substrate work locks at investigation phase; UX refinement work ships post-substrate against operator-validated UX needs. Operator-conducted production audit between investigation lock and sub-arc dispatch is a canonical checkpoint pattern for substrate-cycle work that consumes production data. Reference instances: task substrate v2 phasing doc §5 + §8, WB-3 atom catalog calibration, WB-5 substrate-vs-UX lock disposition.

---

### Entry 3 — Deferral-tracking meta-pattern

**Date:** 2026-05-26
**Folds:** operator-added (no Phase 0 candidate ID; surfaced from C42 carry-forward decision at Phase 1 → Phase 2 gate)
**Altitude:** meta-discipline

**Rule.** Architectural decisions deferred during build arcs surface as canon candidates during subsequent canon-update arcs; deferral status preserved; canon entry doesn't land until decision is settled against then-current state. Deferred candidates carry forward to dedicated future arcs with explicit defer-reason + revisit-trigger + substrate context that the future arc inherits.

**Rationale.** Canon is for settled architectural commitments, not pending decisions. Filing a deferred decision as canon would lock the deferred shape forward without the future arc having reckoned with then-current state — substituting architect intuition for operator-validated context. The pattern emerged from C42 (boot-adapter-takes-client substrate decision deferred during WB-cycle-followup-2 per Q-B1 lock) surfacing as needs-operator-decision at canon-update Phase 1 cull. The honest resolution carries C42 forward to a dedicated September-decision arc against then-current Studio + admin realm state, with the candidate staying in the candidate pool as a record of the deferred decision rather than filing as canon entry. The orthogonal discipline to "deferrals must be surfaced explicitly so end-of-cycle verification catches gaps" (cluster 13 / Entry 25) is "deferred candidates carry forward to dedicated arcs with explicit defer-reason + revisit-trigger documentation, not as floating questions" — this entry captures the latter.

**Implementation.** When an arc closes with a candidate flagged for a future-arc decision rather than absorbed into the closing arc's canon, the close-note + carry-forward artifact captures (a) the defer reason (why the decision wasn't settled in the closing arc), (b) the revisit-trigger (operator-observable signal that warrants dispatching the future arc), (c) the substrate context the future arc inherits (what substrate exists today that the future decision interacts with). The deferred candidate stays in `docs/investigations/canon_update_candidates.md` (or equivalent persistent candidate pool) tagged with deferral status and revisit-arc reference. Canon-update arcs encountering deferred candidates in subsequent cycles re-surface them at gate review for operator decision (settle-now-as-canon vs continue-deferring vs carry-forward-to-different-future-arc). Reference instance: C42 boot-adapter-takes-client decision deferred from WB-cycle-followup-2 (`33d5721`) per Q-B1 lock; carry-forward to September-decision arc documented in canon-update arc STATE.md close note (this arc).

---

### Entry 4 — Persistent-storage discipline for investigation deliverables

**Date:** 2026-05-26
**Folds:** C7 (anchor) + C72 absorbed
**Altitude:** meta-discipline

**Rule.** Investigation deliverables ship to git-tracked persistent storage at `docs/investigations/`, not to `/tmp/` or other ephemeral locations. `/tmp/` remains appropriate for transient computation; deliverables that future arcs cite back to require git-tracked persistence. Persistent deliverables are kept current when sequencing or substrate context changes — investigation documents update when sub-arc ordering inverts or scope refines, so future arcs read accurate state rather than stale state.

**Rationale.** The discipline emerged from the May 24, 2026 20:12 `/tmp/` rotation loss event that wiped ~35,500 words across the v1 task substrate investigation + (c) investigation + v2 investigation Phases 0-3. The recovery work — Option E consolidated state doc at `bc7c4ba` — captured what survived in session transcript at appropriate fidelity for forward flow, but the loss was real and the implementable specifics required re-derivation against current code rather than recovery from `/tmp/`. The discipline applies even when loss doesn't happen: investigation deliverables that future arcs cite back to require persistence across session boundaries (Opus context decay between sessions; agent context resets per dispatch). The keep-current dimension (C72's contribution) is the symmetric discipline: persistent storage is only useful if persistent deliverables stay accurate. WB investigation locked sub-arcs WB-5 → WB-8 in that order; operator reordered to WB-6 → WB-5; investigation documents needed update so future arcs read accurate order. Persistent storage + currency together produce reliable forward-reference for downstream arcs.

**Implementation.** All investigation deliverables (Phase 0 scope locks, Phase 1 audits, Phase 2 designs, Phase 3 substrate specs, Phase 4 phasing recommendations, Phase 5 build prompts, completion artifacts, state docs) ship to `docs/investigations/` with git-tracked persistence from the start of the deliverable's authorship. No `/tmp/` involvement for deliverables; `/tmp/` reserved for transient computation (build agent scratch files, intermediate parsing output, etc.). When sequencing changes or substrate context shifts mid-arc, the relevant persistent deliverables update (commit message captures the update). Closure artifacts at arc end capture the final state for forward-reference. Reference instances: task substrate v2 state doc (`bc7c4ba`), phasing doc (`ca88f50`), v1 build prompt (`50a07ff`), v1 completion artifact (`7b00942`), canon-update arc deliverables (this arc's `canon_update_candidates.md` + `canon_update_cull.md` + this drafted-entries artifact).

---

## Pass 2 — Substrate-decision (7 entries)

### Entry 5 — Hybrid-schema canon for substrate extensions over established tables

**Date:** 2026-05-26
**Folds:** C13 (lineage-fact dimension via task substrate Q1 (d) decision)
**Altitude:** substrate-decision (re-altituded from Phase 0 lineage-fact)

**Rule.** When substrate extends an established table with substantial existing consumers, the canonical shape is hybrid: the established table preserved as-is + a join table for substrate-specific fields + service-layer Task façade preserving backward-compat for existing consumers + migration backfill that creates the join-table rows for existing data. Avoid pure rename (introduces avoidable risk against existing route surface + consumers); avoid pure VaultItem absorption (loses substrate-specific schema specificity); avoid pure separate-table-with-FK-from-VaultItem (separates substrate from operational truth).

**Rationale.** The decision emerged during v2 task substrate investigation Phase 3 when Q1 surfaced as the gate-stopping schema decision. Four shape options surveyed: (a) pure VaultItem absorption, (b) keep existing `tasks` table standalone, (c) rename `tasks` → `task_details` with VaultItem reference, (d) hybrid. Option (a) lost task-specific schema; option (b) created two parallel "things needing attention" substrates; option (c) introduced rename risk against the existing `tasks` table's 8 consumers + active `/api/v1/tasks/*` route surface; option (d) preserved canonical "tasks are Vault items" thesis while normalizing task-specific fields into the join table. The hybrid landed because BRIDGEABLE_MASTER §3.24's unified-row-type thesis (VaultItem is canonical) holds while task-specific fields (assignee, due_date, priority, state machine, provenance, associations) properly belong in their own normalized table rather than bloating VaultItem schema. The architectural commitment generalizes beyond tasks: any future substrate extending an established table with substantial consumer base should consider hybrid before pursuing rename or absorption.

**Implementation.** Migration adds new item_type value to VaultItem enum + creates new `<substrate>_details` join table with FK CASCADE on `vault_item_id` (1:1 enforced via UNIQUE constraint). Task service layer (or substrate-equivalent service layer) implements façade pattern: existing consumer API preserved; new internal implementation queries through join. Migration backfill creates VaultItem rows for existing established-table rows + corresponding `<substrate>_details` rows in atomic transactions. Reference instance: r107 task substrate migration (`2fba161`) created `task_details` join + backfilled VaultItem rows for existing `tasks` content; 8 existing Task consumers verified working unchanged via `test_task_and_triage.py` 31/31 green at every commit checkpoint of v1 arc.

---

### Entry 6 — Built-but-dormant as third substrate state

**Date:** 2026-05-26
**Folds:** C52
**Altitude:** substrate-decision

**Rule.** Substrate audits enumerate three substrate states, not two: (1) built + operator-facing (substrate exists in schema/storage layer AND has UI surface exposure); (2) built + dormant (substrate exists in schema/storage layer but lacks UI exposure); (3) missing (substrate doesn't exist). The dormant state is canonically distinct from missing — investigation work treats dormant substrate as existing-but-unsurfaced rather than not-existing.

**Rationale.** Three-instance pattern surfaced across WB cycle sub-arc audits: WB-6 saved-view cross-tenant masking shipped substrate but lacked tenant-visibility surfacing; WB-7 PeekContext shipped substrate but lacked operator-visible peek invocation; WB-8 default_variant_id column shipped at schema layer but lacked authoring surface. In all three cases, treating the substrate as "missing" would have produced rebuild work; treating it as "dormant" surfaced the actual gap (UI exposure) and shipped surfacing rather than substrate. The vocabulary distinction matters because investigation audits default to binary "exists / doesn't exist" framing; the three-state framing changes audit conclusions. When investigation surfaces substrate-shape claim "X needs to be built," audit-first phase verifies which of the three states applies — dormant substrate earns surfacing arc, not substrate arc.

**Implementation.** Substrate audits in investigation Phase 1 enumerate per-substrate state: built-operator-facing / built-dormant / missing. Grep for schema slots + storage layer presence + UI surface registration as three orthogonal checks. Dormant substrate findings surface as "substrate exists at storage layer + UI exposure missing" rather than "substrate missing." Subsequent build arc against dormant substrate ships the UI exposure layer, not rebuilt substrate. Reference instances: WB-6 saved-view cross-tenant masking finding, WB-7 PeekContext audit, WB-8 default_variant_id column audit (all surfaced via sub-arc audit-first phase per investigation-methodology canon Entry 1).

---

### Entry 7 — Auto-save semantics depend on substrate clone-vs-shared shape

**Date:** 2026-05-26
**Folds:** C80
**Altitude:** substrate-decision

**Rule.** Auto-save is safe when substrate is cloned-per-instance (operator edits affect only their own clone). Auto-save is hazardous when substrate is rendered-shared (operator edits affect all consumers rendering the substrate). Substrate-clone-pattern analysis is load-bearing for save-semantics decisions; investigation must audit clone-vs-shared shape before locking save semantics.

**Rationale.** The distinction surfaced during Focus Builder substrate work (`focus_templates → focus_compositions` clone-per-instance pattern allows auto-save without cross-consumer impact) vs widget definition substrate (rendered-shared; auto-save would affect all widgets rendering the definition). Auto-save UX feels uniformly desirable for builder surfaces, but the substrate shape determines whether auto-save is safe or dangerous. The Focus Builder pattern (clone-on-instance) is canon-worthy precisely because it earns auto-save discipline; the widget definition pattern (rendered-shared) is canon-worthy because it earns manual-save discipline. Substrate decisions made before save-semantics decisions; save UX inherits from substrate shape, not vice versa.

**Implementation.** Investigation Phase 3 substrate design specifies clone-vs-shared shape per substrate as part of schema decision. Builder surfaces that operate on cloned-per-instance substrate ship auto-save defaults; builder surfaces that operate on rendered-shared substrate ship manual-save with explicit publish/commit affordance. When a builder surface proposes auto-save UX, audit the underlying substrate shape — if shared, surface to operator before locking save semantics. Reference instances: Focus Builder `focus_compositions` substrate (clone-on-instance, auto-save canonical), Widget Builder `widget_definitions` substrate (rendered-shared, manual-save canonical per WB-cycle decision lineage).

---

### Entry 8 — WYSIWYG discipline as canvas-layout-model constraint

**Date:** 2026-05-26
**Folds:** C81 + extends 2026-05-20 Monitor-vs-Decide canvas entry
**Altitude:** substrate-decision

**Rule.** Authoring canvas layout model must match rendering canvas layout model. Free-form-in-authoring + flex-at-runtime violates WYSIWYG and produces operator-perception drift between authoring intent and rendered output. Substrate choices in operator-facing builders are constrained by runtime rendering substrate; builder substrate decisions inherit from runtime substrate, not vice versa.

**Rationale.** Extends the 2026-05-20 Monitor canvas (grid model) vs Decide canvas (free-form model) architectural-distinct-substrate entry by adding the builder-vs-runtime coupling axis. The original entry established that Monitor and Decide canvas are distinct substrate concerns at runtime; this entry establishes that builder substrate for either canvas type must match the runtime layout model. A builder that authors free-form widgets which render through grid layout breaks WYSIWYG; operator sees one arrangement during authoring, another at runtime. The constraint propagates: builder substrate for grid-rendering surfaces ships grid-canvas authoring; builder substrate for free-form-rendering surfaces ships free-form-canvas authoring. The runtime substrate is the substrate of record; builder substrate is operationally constrained by it.

**Implementation.** Builder substrate design specifies canvas layout model as inherited-from-runtime constraint, not as independent choice. Authoring canvas implementation matches runtime layout substrate's coordinate/positioning model (grid coordinates vs free-form positions). When investigation surfaces a builder substrate decision, audit which runtime substrate the builder targets + verify layout-model coherence before locking builder substrate shape. Reference instances: Monitor canvas grid model (runtime + authoring both grid-coordinate); Decide canvas free-form model (runtime + authoring both free-form coordinate). Cross-reference: 2026-05-20 Monitor-vs-Decide canvas entry.

---

### Entry 9 — Substrate-minimal-default canon

**Date:** 2026-05-26
**Folds:** Cluster 9 — C54 (anchor), C59, C65
**Altitude:** substrate-decision (primary) with dispatch-pattern dimension

**Rule.** Default substrate-additive discipline: ship narrow + canonical; expand additively when operator-validated need surfaces. Resist building shared substrate before second consumer exists — premature shared substrate tends to drift dormant per built-but-dormant canon (DECISIONS.md 2026-05-26 — Built-but-dormant as third substrate state). Discriminator infrastructure ships with single-value type; expand the discriminator literal additively when second value earns it.

**Rationale.** The discipline generalizes from WB-7 verb-vocabulary asymmetry + WB-8 Area 4 widget-scoped lock. Both cases shipped narrow canonical substrate (single-verb infrastructure that could expand later) rather than generic substrate (multi-verb infrastructure prepared for unknown future verbs). The narrow-canonical shape forces second-consumer evidence before substrate expansion; this constrains substrate-growth honestly against operator-validated need rather than architect intuition. The discriminator-infrastructure-with-single-value pattern (`mutate_kind = Literal['anomaly_acknowledge']` forces single-option Select with no-op onChange) is the canonical implementation shape: substrate exists, type system constrains it to single value, expansion happens via Literal addition. Premature substrate shared across consumers that don't yet exist creates substrate-drift risk: substrate ships, consumer doesn't surface, substrate drifts dormant, future arc rebuilds against dormant substrate's incorrect assumptions.

**Implementation.** Investigation Phase 3 substrate design specifies substrate breadth per operator-validated demand. When investigation surfaces "X infrastructure needs to support multiple cases," audit whether the second case has operator-validated need or is architect-inferred — if the latter, ship narrow with discriminator infrastructure that can expand additively. Build agents implement discriminator types as single-value Literals when only one case has operator-validated need; expansion via Literal addition happens at sub-arc landing the second case. Reference instances: WB-7 mutate_kind single-value Literal (anomaly_acknowledge only; future kinds expand additively); WB-8 Area 4 widget-scoped variant authoring lock (narrow per-widget rather than generic).

---

### Entry 10 — Shared-dispatcher-multiple-authoring-surfaces canon

**Date:** 2026-05-26
**Folds:** Cluster 10 — C60 (anchor), C61, C63, C64
**Altitude:** substrate-decision

**Rule.** When authoring surfaces share dispatch infrastructure but differ in verb vocabularies (e.g. page-level admin verbs vs widget-level row-context verbs vs future builder-level verbs), the canonical pattern is shared dispatcher infrastructure with per-surface verb sets — not forcing identical verb vocabularies across surfaces, not building parallel dispatcher infrastructure per surface. Parameter binding sources expand at sub-arc boundaries per consumer-surface needs; each consumer-surface earns its own binding source as it lands. Rather than build parallel substrate, extend existing substrate when verb-vocabulary asymmetry warrants.

**Rationale.** R-4.0 dispatcher substrate originally served page-level admin verbs; WB-7 work extended dispatcher for widget-level row-context verbs (open_peek + mutate) + extended ParameterBindingRef from 7 to 8 sources (current_row). The substrate-additive pattern shipped lowest-risk consumer-extension: one dispatcher, two authoring surfaces, per-surface verb sets, shared parameter binding with surface-specific extensions. Future builders (Page Builder, Document Builder) will have their own verb vocabularies on the same shared dispatcher. The pattern resists two anti-patterns: (1) "make all surfaces use identical verbs" forces vocabulary compromise where surfaces have legitimate distinct semantics; (2) "build separate dispatcher per surface" duplicates infrastructure for the per-surface verb difference. Shared dispatcher + per-surface verbs preserves substrate reuse while respecting per-surface vocabulary distinctness.

**Implementation.** Dispatcher substrate ships with discriminator-by-surface-type (or equivalent); per-surface verb sets registered against shared dispatcher infrastructure. Parameter binding source enumeration expands at consumer-surface landing — each new consumer-surface earns its binding source when it ships, not pre-emptively. When investigation surfaces a new authoring surface that consumes dispatch substrate, audit whether existing dispatcher can accommodate the surface's verb vocabulary via additive extension (preferred) vs requires separate dispatcher (architectural divergence; surface to operator). Reference instances: R-4.0 dispatcher serves R-4.0 page-level admin + WB-7 widget-level authoring + future builders; ParameterBindingRef 7-source → 8-source expansion at WB-7 landing.

---

### Entry 11 — Always-visible preview substrate for operator-as-platform-builder authoring

**Date:** 2026-05-26
**Folds:** Cluster 11 — C62 + C67 (joint anchors), C70
**Altitude:** substrate-decision

**Rule.** Builder UX defaults to always-visible preview for substrate authoring (vs hover-tooltips or peek-on-demand). Operator-as-platform-builder framing benefits from constant operator awareness of substrate behavior during authoring. Preview substrate is non-dispatching: operator sees what the action would do without firing. When sub-arcs are sequenced and an intermediate operator-facing surface would help validation between them, build smaller verification affordance into the current sub-arc rather than waiting for the next sub-arc's full substrate.

**Rationale.** The distinction surfaced during WB-6 and WB-7 work as the substrate-authoring-vs-substrate-consumption split crystallized. Operator-as-platform-builder authoring is qualitatively different from operator-as-end-user consumption: builders need constant awareness of substrate behavior to verify authoring intent against runtime effect; end-users need on-demand information surfaces. Always-visible preview matches the former; hover-tooltips match the latter. WB-6 BindingPreviewCard + WB-7 ActionPreviewCard both shipped always-visible preview against this framing. The non-dispatching characteristic is load-bearing: preview substrate shows what would happen without firing, allowing operator to verify authoring intent against expected runtime behavior without side effects. The smaller-verification-affordance pattern (WB-6 ships in-inspector preview-value tooltip; WB-5 ships full canvas preview) prevents "wait for full substrate" anti-pattern when intermediate validation would meaningfully accelerate sub-arc landing.

**Implementation.** Builder substrate design specifies preview substrate as always-visible default; preview implementation is non-dispatching (no side effects). When sub-arc sequencing reveals that intermediate validation would help, design smaller verification affordance into the current sub-arc — partial preview substrate that consumes existing data shape rather than waiting for full preview substrate at later sub-arc. Reference instances: WB-6 BindingPreviewCard (always-visible binding preview), WB-7 ActionPreviewCard (always-visible action preview), WB-6 in-inspector preview-value tooltip (smaller verification affordance before WB-5 full canvas preview shipped).

---

## Pass 3 — Build-pattern (10 entries)

### Entry 12 — Subscriber-substrate canon for task-event-driven dispatch

**Date:** 2026-05-26
**Folds:** Cluster 4 — C18 (anchor), C20, C46, C53, C69
**Altitude:** build-pattern (primary) with substrate-decision dimension

**Rule.** When substrate ships subscriber registry against lifecycle events, four discipline dimensions cohere: (1) handler bodies fill in at integration phase, not foundation phase — substrate registration ships separately from handler implementation; (2) subscribers discriminating dispatch modes via metadata-presence include defensive assertion against task-type allowlist — failure-loud is the correct shape for substrate affecting user-observable behavior; (3) cross-vocabulary mapping tables default unknown values to "allowed" rather than "rejected" for forward-compatibility; (4) substrate that evolves independently of consuming substrate ships runtime-tolerant (defensive null-safe + unknown-value passthrough at consuming substrate boundary).

**Rationale.** The subscriber-substrate canon emerged across v1 task substrate B1-B2-B3 plus WB-cycle mapping substrates. The deferred-handler-body pattern (substrate registration in foundation phase; handler bodies in integration phase) shipped substrate behavior across 5 subscriber instances (notification_dispatcher in B2; briefings_invalidator + pulse_invalidator + workflow_resumer + focus_closer in B3) without breaking producer-side correctness. The metadata-presence discriminator with defensive assertion (subscriber checks `metadata.notification_permission_key`; cohort-allowlist task_types trigger explicit error if metadata absent) shipped at B2 close as the resolution to the dispatch-mode discrimination question — failure-silent would have produced wrong-recipient notifications when producer sites forgot to set permission_key, failure-loud surfaces the misconfiguration. Cross-vocabulary mapping defaults (WB-8 `surface_mapping` table; unknown atom_kind/target_surface defaults to allowed) ship forward-compatible substrate that doesn't retroactively block consumers as vocabulary expands. Runtime-tolerant substrate evolution (saved-view presentation_mode adding new vocabulary; widget runtime tolerating unknown values) preserves consumer correctness across substrate-additive arcs without forcing simultaneous consumer updates.

**Implementation.** Foundation phase ships subscriber registry + no-op handler stubs documenting their integration-phase wiring intent. Integration phase replaces stubs with substantive handler bodies per the deferred-handler-body pattern. Discriminator-by-metadata subscribers include `if task_type in COHORT_ALLOWLIST and not metadata.get(required_key): log.error(...); raise AssertionError(...)` defensive check. Cross-vocabulary mapping tables ship with `default_behavior='allowed'` semantics; explicit rejection requires explicit table entry. Consumer substrate that consumes evolving producer substrate ships with `try / except (UnknownValue): passthrough_with_default()` patterns at the consumption boundary. Reference instances: v1 task substrate B2 notification_dispatcher (`a400d1b`); B3 four subscriber handler bodies (`1c8dbbd`); WB-8 surface_mapping.py forward-compatible defaults; saved-view presentation_mode runtime tolerance.

---

### Entry 13 — Substrate-transition discipline for substrate-additive arcs

**Date:** 2026-05-26
**Folds:** Cluster 7 — C15 (anchor), C17, C19, C27
**Altitude:** build-pattern

**Rule.** Substrate-additive arcs ship four cohering disciplines: (1) dual-write keeps both write paths active during transition when substrate is added alongside existing implementation — consolidation arc post-substrate-maturation unifies write paths; (2) metadata-based extension preserves substrate-locked discipline when producer-supplied context is needed but plugin contracts are locked — plugin-field promotion is consolidation target for v2+ arcs; (3) forward-only is correct discipline when refactor changes upstream invocation path while preserving downstream behavior bit-for-bit (parity discipline) — pre-refactor invocations remain historical fact; (4) adapter-substrate (preserving operational continuity) defaults over absorbed-into-substrate (refactor each substrate to be task-driven internally) for first-shipped iteration; absorption defers to operator-validated consolidation arc.

**Rationale.** The four disciplines emerged across v1 task substrate B1-B2-B3 as resolution patterns for substrate-additive complexity that doesn't safely ship as single-shot consolidation. Dual-write at site #1 (legacy `task_service.create_task` keeps writing legacy Task row + calls `create_task_with_provenance`) preserves backward-compat against 8 existing consumers while adding canonical substrate; consolidation to single-write defers to v2+ post-substrate-maturation arc when consumer migration completes. Metadata-based extension (producer sites passing `metadata={"notification_permission_key": "...", ...}` to `create_task_with_provenance`) preserves Phase A plugin contracts as locked; plugin-field promotion to first-class type-system specification is the consolidation target when v2+ work touches plugin contracts substantively. Forward-only discipline (no backfill for B2 or B3 refactor) preserves the historical-fact / go-forward-operation distinction; pre-refactor notifications fired without creating task entities, and that's correct historical record. Adapter-substrate default (10 non-task triage queue task-creation adapters in v2a; family portal adapters in v2b) over absorbed-into-substrate (refactor each substrate to be task-driven internally) ships lowest-risk substrate-additive shape; absorption work earns its own arc when operator-validated need surfaces.

**Implementation.** Substrate-additive arc dispatch specifies which of the four disciplines applies per substrate boundary. Dual-write transitional state documented in commit message with explicit "consolidation deferred to v2+" reference. Metadata-based extension uses existing schema-flexible fields (e.g. JSONB metadata) rather than plugin contract changes; plugin-field promotion candidate filed forward. Forward-only refactors explicitly note "no backfill" with rationale: parity discipline preserves downstream behavior; historical pre-refactor invocations remain historical fact. Adapter-substrate ships per-substrate adapter files (e.g. `task_creation_from_anomaly.py` mapping AgentAnomaly events to task creation); absorbed-into-substrate refactors defer to operator-validated consolidation arc. Reference instances: v1 task substrate B2 dual-write at site #1 (`a400d1b`); metadata-based `notification_permission_key` extension; B2/B3 forward-only refactor; v2a triage-queue adapter pattern per phasing doc §3.

---

### Entry 14 — Dynamic permission inheritance via subtraction-from-all-keys

**Date:** 2026-05-26
**Folds:** C3
**Altitude:** build-pattern

**Rule.** Role-default permissions computed via subtraction-from-all-keys (`get_all_permission_keys() - {users.delete, roles.delete}`) let new permission slugs land without per-permission role-seed updates. Director-shape roles automatically inherit new permissions when the platform's permission registry grows.

**Rationale.** The pattern surfaced during (c) build arc when `fh_cases.aftercare` permission slug needed to ship; the dynamic-subtraction pattern at `role_service.MANAGER_DEFAULT_PERMISSIONS` meant the new slug landed without per-permission role-seed updates against FH-director-shape roles. The pattern generalizes: any role whose default-permission set is most naturally expressed as "all permissions except this small exclusion list" should use subtraction-from-all-keys rather than enumeration-of-included-permissions. Enumeration would force per-permission role-seed updates as the permission registry grows; subtraction inherits new permissions automatically with the small exclusion list as the only update surface when role-permission semantics shift.

**Implementation.** Role-default permission computation uses `get_all_permission_keys() - {<exclusion_set>}` pattern in role_service or equivalent. Exclusion set documented inline with rationale per excluded permission. New permission slugs added to the platform's permission registry inherit automatically into subtraction-pattern roles; per-role inheritance verified via test that exercises the role's effective permission set post-registry-extension. Reference instance: (c) build arc fh_cases.aftercare permission slug at `868fec3`; `MANAGER_DEFAULT_PERMISSIONS = get_all_permission_keys() - {users.delete, roles.delete}` pattern at role_service.

---

### Entry 15 — Forward-compat substrate canon when implementation absent

**Date:** 2026-05-26
**Folds:** C22
**Altitude:** build-pattern

**Rule.** When build prompt anticipates refactoring N call sites but audit reveals zero call sites exist, the canonical response is shipping canonical entry point + contract tests as forward-compat substrate rather than absorbing the refactor scope as deletion. Future arcs that need the substrate find it ready; the substrate's existence at canonical location documents the architectural commitment that future wiring will land here.

**Rationale.** The discipline surfaced at v1 build arc B3 when build prompt §7.6 anticipated 3-5 Intelligence direct-notification call sites for refactor against task substrate; grep returned zero. The honest response could have been (a) skip the work as no-op, (b) absorb the absent-target as material divergence and surface to operator. The agent shipped (c) canonical entry point + contract tests at `tasks/intelligence_integration.py` as forward-compat substrate. The forward-compat shape preserves the architectural commitment from the May 21-22 conversation (Intelligence creates persistent tasks rather than fleeting notifications) — when Intelligence later needs to fire task creation, the entry point is ready and the pattern is documented. Capability-demand mapping at investigation altitude should audit not just whether substrate consumes the conversation's claims, but whether implementation exists to refactor in the first place. When implementation is absent, forward-compat substrate is the canonical response, not no-op.

**Implementation.** Build agent encountering "refactor N call sites" with grep returning zero call sites ships canonical entry point + contract tests at the expected substrate location. Commit message flags the material-divergence finding explicitly (grep returned zero; canonical entry shipped as forward-compat). Investigation Phase 1 capability-demand mapping audits "implementation exists?" as separate question from "substrate consumes claim?" to catch this pattern at investigation altitude rather than at build dispatch. Reference instance: v1 build arc B3 `tasks/intelligence_integration.py` canonical entry point + contract tests at `1c8dbbd`.

---

### Entry 16 — Re-export shim pattern for module-internal substrate migration

**Date:** 2026-05-26
**Folds:** C31
**Altitude:** build-pattern

**Rule.** Module-internal substrate migration ships re-export shim pattern: replace module internals with re-exports from new substrate location; consumers unchanged. The shim pattern preserves consumer sites with zero churn while substrate migration completes internally; consolidation arc later removes shim when consumer migration completes.

**Rationale.** The pattern surfaced during WB-cycle-followup-2 when `widget-builder-service.ts` substrate migrated to `visual-editor-widgets-service`. The honest options were (a) update 5 existing consumers + 2 test mocks at migration time, (b) re-export shim from old location pointing to new substrate. Option (b) shipped because consumer-update at migration time would expand WB-cycle-followup-2 scope into consumer-migration territory; re-export shim preserved consumer correctness while substrate migration completed internally. Future consolidation arc removes shim when consumer migration is operationally validated. The pattern generalizes to any module-internal substrate migration where consumer-update can defer to dedicated consolidation arc.

**Implementation.** Substrate migration replaces module internals with `export { ... } from '<new substrate path>'` re-exports. Old module path retained as shim file; consumers unchanged. Re-export shim commit message documents substrate-canonical-location + consumer-migration-deferred-to rationale. Consolidation arc later removes shim file + updates consumers in single arc with operator-validated need. Reference instance: WB-cycle-followup-2 `widget-builder-service.ts` re-export shim from `visual-editor-widgets-service`; 5 existing consumers + 2 test mocks unchanged.

---

### Entry 17 — Substrate-prescience-meets-second-consumer pattern

**Date:** 2026-05-26
**Folds:** C34
**Altitude:** build-pattern

**Rule.** Substrate authored with future-consumer-in-mind produces clean consumption PLUS minimal disambiguator extension at the boundary the original author couldn't fully anticipate. Even prescient substrate accumulates one minimal extension per additional consumer. The extension is not substrate failure — it's substrate maturity meeting consumer specificity.

**Rationale.** The pattern surfaced at WB-cycle-followup-1 when Focus Builder F-1.1 substrate (`overrideHref` parameter authored prescient for future visual editor consumer) met its second consumer (visual editor) and earned a minimal disambiguator extension (`testIdSuffix` per-entry parameter). The original author couldn't fully anticipate that the second consumer would need per-entry test isolation; the extension was minimal (single per-entry parameter) and additive (didn't break first consumer). The pattern generalizes: prescient substrate-authoring reduces extension cost at second-consumer landing but doesn't eliminate it — first author can't audit second consumer's specificity until second consumer surfaces. The extension cost is canonical, not failure mode; substrate design should anticipate one minimal extension per additional consumer rather than aim for zero-extension reuse.

**Implementation.** Substrate authored for known-future-consumer accepts that one minimal extension per additional consumer is canonical. Extension shape at second-consumer landing: additive parameter or method with default behavior preserving first-consumer correctness. Investigation Phase 3 substrate design budgets one minimal extension per anticipated future consumer in LOC envelope. Reference instance: Focus Builder F-1.1 `overrideHref` prescient parameter; WB-cycle-followup-1 `testIdSuffix` per-entry disambiguator extension at second-consumer landing.

---

### Entry 18 — Resolution chain defensive substrate

**Date:** 2026-05-26
**Folds:** C48
**Altitude:** build-pattern

**Rule.** Chain-resolution substrate (where a value resolves through ordered fallback steps until a non-null/non-empty result is found) ships with defensive null-safe handling at each chain step. Edge cases (empty-string default, null blob, non-object) require explicit handling for backward-compat; substrate that crashes on edge cases produces consumer-side workaround substrate over time.

**Rationale.** The pattern surfaced during WB-8 `default_variant_id` resolution chain work where edge cases (empty-string default, null blob, non-object) needed explicit handling for backward-compat against existing data. Without defensive null-safe at each step, the chain would crash on edge-case input; consumers would need workaround substrate to avoid the crash. Defensive substrate at each chain step prevents consumer-side workaround accumulation and preserves substrate's "consumers can call without pre-validation" canonical shape.

**Implementation.** Chain-resolution functions wrap each step with null-safe check; null/empty result at any step proceeds to next chain step rather than raising. Edge cases explicitly enumerated in chain function's docstring + tested via per-edge-case unit test. Final fallback returns canonical default (null, empty, or substrate-specific sentinel). Reference instance: WB-8 `default_variant_id` resolution chain at variant authoring substrate.

---

### Entry 19 — Pydantic discriminated-union + strict validator pattern

**Date:** 2026-05-26
**Folds:** C58
**Altitude:** build-pattern

**Rule.** Discriminated-union schemas needing operator-friendly per-verb errors use Pydantic `Annotated[Union, Discriminator(...)]` + strict validator layer + per-discriminator config. Pattern generalizes for future discriminated-union schemas (workflow node configs, action specs, plugin configurations).

**Rationale.** The pattern surfaced during R-4.0 dispatcher work for action spec validation. Discriminated-union schemas (where a `type` discriminator field determines which sub-schema applies) need per-verb error messages that operator-facing surfaces can render meaningfully — "expected field X for verb Y" rather than generic union-mismatch errors. Pydantic `Annotated[Union, Discriminator(...)]` provides the type-system substrate; strict validator layer provides per-verb error specificity. The combination is the canonical Bridgeable shape for discriminated-union schemas; future schemas needing similar shape (workflow node configs across node types; plugin configurations across plugin categories) should adopt the pattern.

**Implementation.** Discriminator schema defines `Annotated[Union[VerbA, VerbB, VerbC], Discriminator('verb_type')]`; per-verb sub-schemas extend a base schema with verb-specific required fields. Strict validator layer wraps Pydantic validation with per-verb error formatting: catch ValidationError, identify which verb the discriminator pointed at, format error referencing the verb's expected schema. Reference instance: R-4.0 action spec discriminated-union substrate at dispatcher work.

---

### Entry 20 — Async operator-facing surface substrate-shape

**Date:** 2026-05-26
**Folds:** C75
**Altitude:** build-pattern

**Rule.** Any async operator-facing surface (data fetch + display) ships with explicit loading-error-cancel state machine substrate: loading state with operator-visible indicator; error state with retry affordance; race-condition cancellation via AbortController when surface unmounts or query parameters change mid-fetch. The pattern generalizes beyond specific data sources (dataContext, briefings, search) — any async operator-facing surface needs the three states substantively present.

**Rationale.** Generalizes from WB-5 investigation canon candidate α (dataContext-specific async substrate). The three-state shape (loading / error / cancel-on-change) is structural to async UX correctness, not specific to any one data source. Surfaces shipping without explicit loading state show flicker; surfaces without error state crash or silently fail; surfaces without cancel-on-change accumulate stale-query races where mid-fetch parameter changes produce wrong-data rendering. The state machine substrate is small (typically ~50-100 LOC per async surface); shipping it as canonical substrate-shape per async surface prevents reinventing-the-wheel and ensures consistent operator-facing async UX.

**Implementation.** Async operator-facing surface ships with state machine: `{ status: 'idle' | 'loading' | 'error' | 'success', data, error, abortController }` shape. Loading state shows operator-visible indicator (spinner, skeleton, etc.). Error state shows error message + retry affordance. AbortController cancels in-flight fetch when surface unmounts or query parameters change; cleanup in React useEffect return or equivalent. Reference instance: WB-5 dataContext async substrate; pattern generalizes per canon to any async operator-facing surface.

---

### Entry 21 — Studio routing substrate legacy editor-page catch-all + Spec-Override Discipline

**Date:** 2026-05-26
**Folds:** C79
**Altitude:** build-pattern

**Rule.** Studio routing substrate has legacy editor-page catch-all behavior that's load-bearing for legacy routes. New explicit routes mount above the catch-all via CLAUDE.md §12 Spec-Override Discipline. When a new explicit route needs to land before the existing catch-all, mount above the catch-all + flag the override explicitly in commit message.

**Rationale.** The Studio routing substrate evolved with legacy editor-page catch-all behavior preserving routes that haven't been migrated to explicit substrate. Removing the catch-all would break unmigrated legacy routes; preserving the catch-all means new explicit routes need to mount above it (or React Router's first-match wins logic routes them to the catch-all). CLAUDE.md §12 Spec-Override Discipline provides the canonical pattern: explicit override + commit message flag + verification that override doesn't break legacy routes. The pattern surfaces whenever Studio routing substrate gets extended; the catch-all isn't going away until legacy-route migration completes, so the override pattern is canonical for substrate-additive work against Studio routing.

**Implementation.** New explicit Studio routes register above the legacy catch-all in route registration order. Commit message flags the override explicitly with `[Spec-Override per CLAUDE.md §12]` or equivalent. Verification test exercises both new explicit route + at least one legacy catch-all route to confirm both reachable post-override. Reference instances: Studio navigation arc Widget Builder rail entry; WB-cycle-followup-2 platform-realm router mounting per Spec-Override.

---

## Pass 4 — Dispatch-pattern (11 entries)

### Entry 22 — Discoverability canon for operator-facing substrate cycles

**Date:** 2026-05-26
**Folds:** Cluster 1 — C36 (anchor), C37, C38, C39, C40, C41, C43 (C44 separate Phase 2.B CLAUDE.md §4 extension)
**Altitude:** dispatch-pattern (primary) with verification-pattern + substrate-decision sub-clauses

**Rule.** Operator-facing substrate cycles must include entry-point wiring (nav/rail entries, route registrations) as substrate deliverable, not follow-up. Build reports separate the two claims: discoverability (entry point renders) vs functional correctness (consumed substrate actually works end-to-end). Operator-ready substrate claim requires auth-realm reachability verification: endpoint exists in expected realm; frontend service consumes correct realm client; cross-realm boundary returns expected status. Substrates authored via Studio (which mounts at admin.* host) default to platform-realm endpoints. Route-touching arcs need explicit nav-label-audit step to prevent operator-perception drift between rail label and rewired route target. Substrate-cycle close-out explicitly plans for two follow-up arcs (discoverability + functional verification) as part of cycle close, not as discovered defects.

**Rationale.** Seven candidates from the WB cycle + F-cycle lineage converge on this canon. The discipline emerged across three failure-mode instances: (1) F-cycle and WB-cycle both shipped substrate that operator validation surfaced was undiscoverable — entry-point wiring landed reactively rather than as substrate deliverable; (2) WB-4b silently inherited rail label "Widgets" while rewiring route target, producing operator-perception drift surfacing months later; (3) WB cycle shipped substrate that rendered in admin context but consumed tenant-realm endpoints, producing 403 gap that WB-cycle-followup-2 retrofit corrected. The load-bearing thesis (C39, the sharpest canon-worthy finding from the WB cycle) is the two-claim distinction: post-deploy verification checklists must include explicit functional-exercise step beyond "page renders without error." Discoverability ≠ functional correctness; both must verify explicitly, not via inference from one to the other. The three-step pattern (substrate cycle ships → discoverability follow-up surfaces from operator validation → functional verification follow-up surfaces from second-stage operator use) was observed across F-cycle and WB-cycle both, suggesting close-out should explicitly plan for the two follow-up arcs rather than treating them as discovered defects.

**Implementation.** Substrate-cycle investigation Phase 1 includes nav/rail entry registrations as substrate audit dimension. Substrate-cycle build dispatch includes entry-point wiring as substrate deliverable line item. Post-deploy verification checklist separates "renders" from "functions" as distinct verification steps. Auth-realm reachability verification audits: endpoint realm + frontend service realm + cross-realm boundary status. Studio-authored substrates default to platform-realm endpoints (`/api/platform/admin/...` with `get_current_platform_user`); tenant-realm endpoints reachable only from tenant subdomain context. Route-touching arcs include nav-label-audit step in investigation Phase 1 checklist. Substrate-cycle close-out plans two follow-up arcs explicitly: discoverability-confirmation follow-up + functional-verification follow-up. Reference instances: WB-cycle-followup-1 (entry-point wiring follow-up); WB-cycle-followup-2 (platform-realm router retrofit for 403 gap); F-cycle / F-1.1 follow-up (same discoverability close-out pattern).

---

### Entry 23 — Build-prompt-spec failure pattern canon

**Date:** 2026-05-26
**Folds:** Cluster 3 — C23 (anchor), C30, C66, C91
**Altitude:** dispatch-pattern

**Rule.** Build prompts at refactor or substrate-additive scope inherit compression's lossiness from upstream investigation deliverables; agent execution surfaces the gaps; operator-decision-shaped correction at the dispatch level preserves both arc bounded-decision invariant and execution-reality alignment. Four manifestations of the pattern: (1) "X refactor" can hide architectural decisions when call sites use different helpers OR depend on producer-supplied context the substrate doesn't carry; (2) structural-parity mirroring duplicates module surface area, requiring envelope estimates accounting for full method surface count × per-method LOC + matching test coverage; (3) investigation-locked reframes (operator changes framing mid-investigation) need separate LOC calibration step accounting for what the reframe implies at substrate level; (4) mid-arc execution-reality discipline correction is canonical when execution surfaces material the prompt is wrong about — STOP + surface to operator + revise lock + proceed.

**Rationale.** Three-instance cross-arc-validated pattern in v1 build arc execution alone: v1.0→v1.5 gate-spec correction (staging-DB validation prescription assumed Railway access that auto-deploy pattern doesn't provide); B2 (c)-refactor 4-decision correction (call-site mechanics required substrate-aware decisions the build prompt §7.3 mapping table didn't specify); B3 Intelligence-refactor correction (refactor target empty; canonical entry point shipped forward-compat per DECISIONS.md 2026-05-26 — Forward-compat substrate canon when implementation absent). Plus WB-cycle-followup-2 structural-parity mirroring (shipped ~885 LOC vs ~230-380 envelope; 2.3× overrun honest absorption) + WB-6 operator-reframe scope expansion (3.3× envelope partly due to reframe-driven scope LOC envelope didn't recalibrate against). The pattern is the most substantive meta-discipline learning from the v1 build arc execution because it surfaces the asymmetry between investigation-altitude framing and build-altitude execution: investigations can specify substrate decisions at architectural altitude; build prompts compiling those decisions into refactor mapping tables inherit lossiness when the table abstracts mechanics that turn out to require architectural choices. The Lock A revision pattern (single-commit-at-arc-close → three-commits-within-arc-identity for substantively-larger arcs per DECISIONS.md 2026-05-26 — Arc-commit-granularity canon) is the canonical execution-reality discipline correction shape: prompt wrong → STOP + surface + revise lock + proceed. Captures the architectural reading that build prompts are themselves operational artifacts subject to honest correction against execution, not fixed specifications that execution must conform to.

**Implementation.** Build prompts at refactor or substrate-additive scope include four-decision-matrix verification upfront: call surface (which helper/path), downstream behavior (what gets fired), producer-supplied context (what context flows through), subscriber mechanics (how downstream consumer dispatches). LOC envelope estimates for structural-parity work account for full method surface count × per-method LOC + matching test coverage. Investigation-locked reframes trigger explicit LOC calibration step before build prompt drafts. Build agents encountering material the prompt is wrong about STOP + surface to operator + await locked revision + proceed against revised lock. The execution-reality discipline correction itself becomes a commit-message-flag pattern (`[Lock revised: ...]` or equivalent) so future-Claude reads not just what shipped but what got corrected mid-execution. Reference instances: v1 build arc Lock A revision (B1/B2/B3 commit messages reference Lock A revision lineage); WB-cycle-followup-2 structural-parity LOC absorption; WB-6 operator-reframe envelope overrun. Cross-reference: DECISIONS.md 2026-05-26 — Arc-commit-granularity canon (commit-shape canon for the Lock A revision pattern's commit-shape dimension).

---

### Entry 24 — LOC calibration canon for substrate-additive arcs

**Date:** 2026-05-26
**Folds:** Cluster 6 — C49 (anchor), C4, C35, C89
**Altitude:** dispatch-pattern

**Rule.** LOC envelope calibration matures as substrate cycle matures: four-instance pattern across WB cycle shows convergence from large variance (WB-6 3.3×) to predictable scoping (WB-8 ±5%) when investigation-locked + substrate-maturity-findings + restraint-discipline cohere. Backfill scripts servicing N distinct substrates carry roughly N × ~50-60 LOC of handler scaffolding; prefigure accordingly. Smaller arcs have larger percentage variance because absolute LOC of "one substantive refinement" is fixed; smaller envelopes amplify impact. When calibration ceiling violation surfaces, agent flags + offers two paths + operator decides (per honest-cost discipline at task substrate v2 phasing §7).

**Rationale.** The calibration pattern emerged across the WB cycle as the canonical reference dataset: WB-6 3.3× envelope overrun → WB-5 0.5% precision → WB-7 18% honest absorption → WB-8 ±5% predictable scoping. The pattern surfaces three substantive findings: (1) first-of-kind substrate inherits some irreducible variance — calibration matures as substrate cycle matures; (2) backfill scripts have substrate-cohort-specific scaffolding cost that pre-flight envelopes consistently misjudge (c) build arc shipped ~440 LOC across 7 cohorts; pre-flight envelope ~120-180 LOC misjudged due to mistaken-cohort-collapse assumption); (3) calibration ceiling violations are honest signal worth surfacing — task substrate v2 phasing §7 surfaced ~22-31k v1+v2+v3 total exceeding 25k ceiling, and operator resolved by accepting envelope + flagging v3 per-arc pre-dispatch rescoping rather than tightening v3 scope artificially at phasing time. v1 task substrate v1 build arc landed at ~8,200 LOC (under ~9,000 anchor) reflecting WB-8-band calibration maturity carrying forward into v1 build arc work. Cross-referenced from DECISIONS.md 2026-05-26 — Build-prompt-spec failure pattern canon: structural-parity mirroring (C30) and operator-reframe-driven scope expansion (C66) file in v1 lineage retrospective cluster as build-prompt-spec failure pattern instances; this entry captures the broader LOC calibration discipline of which they are specific causes.

**Implementation.** Investigation Phase 4 phasing recommendations include LOC envelope estimates per sub-arc with calibration band based on substrate-cycle maturity (first-of-kind: wide band; substrate-mature: narrow band). Backfill script estimates use N × ~50-60 LOC heuristic against distinct substrate cohort count. Small-arc envelopes (~300-500 LOC) explicitly note larger percentage variance expectation. Calibration ceiling violation triggers honest-cost surfacing pattern: agent surfaces + offers paths (accept envelope + flag + revisit; OR tighten scope to fit ceiling) + operator decides at gate review. Reference instances: WB cycle calibration band (WB-6 3.3× → WB-5 0.5% → WB-7 18% → WB-8 ±5%); (c) build arc backfill (~440 LOC vs ~120-180 envelope; honest absorption with mistaken-cohort-collapse rationale); task substrate v2 phasing §7 ceiling-violation handling (operator accepted ~25-31k envelope with v3 per-arc rescoping per DECISIONS.md 2026-05-26 — Per-arc pre-dispatch rescoping for distant-horizon arcs). Cross-reference: DECISIONS.md 2026-05-26 — Build-prompt-spec failure pattern canon (build-prompt-spec failure pattern instances that produce specific LOC envelope drift).

---

### Entry 25 — Deferral-flagging canon

**Date:** 2026-05-26
**Folds:** Cluster 13 — C51 (anchor), C73
**Altitude:** dispatch-pattern

**Rule.** Sub-arc deferrals require explicit flagging at deferral moment so end-of-cycle verification catches gaps. Silent deferral exposes substrate gaps that surface reactively rather than being caught at cycle close. When investigation locks "X is Phase 1 OUT-OF-SCOPE," the locked-out work may still require supporting substrate to ship (references in code, schema slots, etc.) — out-of-scope locks specify which adjacent substrate ships to support the lockout vs which adjacent substrate also defers.

**Rationale.** The pattern emerged from WB-4 step 8 silently deferring variant authoring to WB-8 without surfacing the deferral in cycle close-out; the substrate gap surfaced reactively when WB-8 work discovered the variant authoring surface was missing. The discipline correction is forward-flagging: deferral notes appear in commit messages + deferred-with-reason list appears in investigation document. The orthogonal discipline (locked-out work may require supporting substrate) emerged across multiple WB sub-arcs where Phase 1 scope locks left adjacent substrate ambiguous — does the lockout's adjacent substrate ship as forward-compat (schema slots, references in code) or also defer? The discipline requires investigation to specify per-lockout which adjacent substrate ships to support the lockout vs which adjacent substrate also defers, so future arcs against the lockout don't discover ambiguous adjacent substrate at dispatch time. Together the two disciplines form the deferral-flagging canon: deferrals are explicit + adjacent substrate disposition is specified.

**Implementation.** When a sub-arc defers work to a future arc, the deferral surfaces in: (1) the deferring arc's commit message with explicit "deferred to: [arc reference]" line; (2) the relevant investigation document's deferred-with-reason list. When investigation locks "X is Phase 1 OUT-OF-SCOPE," the lock specifies per-lockout which adjacent substrate ships (schema slots, code references, etc.) vs which adjacent substrate also defers. Investigation Phase 0 scope locks include "adjacent-substrate disposition" as audit dimension when lockouts surface. Cross-reference to DECISIONS.md 2026-05-26 — Deferral-tracking meta-pattern: this canon covers in-cycle deferral flagging; the deferral-tracking meta-pattern covers cross-arc deferral tracking through canon-update cycles. Reference instances: WB-4 step 8 silent deferral to WB-8 (counter-example); WB-8 Area 4 widget-scoped lock with adjacent-substrate disposition specified; WB-cycle-followup-2 Q-B1 lock with boot-adapter-takes-client adjacent-substrate explicitly deferred to September arc.

---

### Entry 26 — Arc-commit-granularity canon

**Date:** 2026-05-26
**Folds:** Operator-resolved merged entry — C14 + C16 + C24
**Altitude:** dispatch-pattern (primary) with lineage-fact dimension

**Rule.** Arc identity preserves through commits. Default regime is single-commit-at-arc-close. Multi-commit-within-arc-identity earned when arc scope exceeds ~3,000 LOC + parity-discipline complexity warrants per-sub-arc commit boundaries. Operator-confirm gates between phases are conversational; conversational gate timing differs between regimes — at internal phase close in single-commit regime, at sub-arc commit boundary in three-commit regime.

**Rationale.** Single-commit-at-arc-close was the original lock at task substrate v2 investigation Phase 3 → Phase 4 (per phasing doc §6.4). v1 build arc execution surfaced honestly that ~9,000 LOC + 8-site (c) refactor parity discipline + 4 subscriber handler bodies + 3 workflow nodes didn't safely fit single-shot agent execution + single-commit-no-rollback window. Lock A revised mid-B1 dispatch to three commits within v1 arc identity (B1 foundation + B2 parity-isolated refactor + B3 consumer integration). The revision is the canonical execution-reality discipline correction (per DECISIONS.md 2026-05-26 — Build-prompt-spec failure pattern canon). Pattern generalizes: sub-arcs deserving isolated commit boundaries are those where verification (parity, idempotency, migration safety) needs to be the sub-arc's primary success criterion rather than bundled with other substantive substrate changes. The operator-confirm-gate concept survives across commit-shape regimes — gates are conversational reviews of staging deploy + behavior verification; only their timing relative to commit shape differs. Both regimes are canonical; single-commit-at-arc-close is the default; multi-commit-within-arc earned by scope + parity-discipline criteria.

**Implementation.** Default single-commit-at-arc-close holds for arcs under ~3,000 LOC or without substantive parity-discipline work. Three-commit-within-arc pattern: sub-arc commit messages reference parent arc identity (`v1 task substrate B1: ...` / `v1 task substrate B2: ...` etc.); each commit independently shippable + Railway-deployable + verifiable; operator-confirm gate between sub-arc commits via conversational review. Single-commit regime gate timing: at v1.0 → v1.5 internal phase close (working tree dirty across gate; staging deploys after commit at arc close). Three-commit regime gate timing: at each sub-arc commit boundary (staging deploys after each sub-arc commit; gate review verifies staging behavior before next sub-arc dispatches). Examples: (c) build arc (`868fec3`) shipped single-commit at ~1,535 LOC; v1 task substrate arc (`2fba161` + `a400d1b` + `1c8dbbd`) shipped three-commit at ~8,200 LOC. Cross-reference: DECISIONS.md 2026-05-26 — Build-prompt-spec failure pattern canon (build-prompt-spec failure pattern includes Lock A revision as canonical execution-reality discipline correction); DECISIONS.md 2026-05-26 — Phasing recommendation shape canon (captures both regimes at phasing altitude); phasing doc §6.4 superseded for substantively-larger arcs only.

---

### Entry 27 — Phasing recommendation shape canon

**Date:** 2026-05-26
**Folds:** C26
**Altitude:** dispatch-pattern

**Rule.** Multi-phase architecture sequencing produces canonical Phase 4 deliverable in 8-section structure: (1) substrate phase final-lock; (2) integration phase final-lock; (3) v2 sub-arc grouping with operator-observable signal triggers; (4) v3 arc shape with per-arc pre-dispatch rescoping; (5) upgrade signals between phases with explicit anti-signal enumeration; (6) cross-version concerns (canon-update interleave, STATE.md narrative, dependencies); (7) honest cost (LOC envelopes per phase, total ceiling discussion); (8) open questions for operator resolution at phasing → build prompt gate.

**Rationale.** The 8-section structure emerged at task substrate v2 investigation Phase 4 as the canonical shape for any future multi-phase architecture sequencing. The structure cohered substantively because each section answers a distinct operator-decision question: §1 + §2 lock the immediately-dispatchable substrate work; §3 + §4 surface deferred scope without locking it; §5 specifies how phases trigger (operator-observable signals not architecture-observable thresholds, per DECISIONS.md 2026-05-26 — Operator-observable signals canon); §6 surfaces cross-version coordination; §7 captures honest cost transparently rather than hiding overruns at phasing time; §8 lifts pre-dispatch decisions to operator altitude rather than leaving them for build agent. Future multi-phase architectures benefit from the canonical structure because it produces phasing deliverables that future arcs can reliably consume — same section ordering means future-Claude reading any phasing doc finds substrate locks at §1-§2, signal patterns at §5, honest cost at §7, etc. without document-shape variance creating reading friction.

**Implementation.** Phase 4 investigation deliverables for any multi-phase architecture sequence follow the 8-section structure. Each section's substantive shape per task substrate v2 phasing doc precedent: §1-§2 final-locks include LOC envelope + close criteria + commit shape per DECISIONS.md 2026-05-26 — Arc-commit-granularity canon; §3-§4 sub-arc/arc shapes include scope sketch + signal-trigger requirements per DECISIONS.md 2026-05-26 — Operator-observable signals canon; §5 enumerates operator-observable signals + explicit anti-signals (LOC threshold, count threshold, time threshold, engineering preference, aesthetic-completeness, sunk-cost); §6 cross-version concerns include canon-update interleave (DECISIONS.md 2026-05-26 — Deferral-flagging canon cross-reference) + STATE.md narrative + dependencies; §7 LOC envelopes with calibration band per DECISIONS.md 2026-05-26 — LOC calibration canon for substrate-additive arcs; §8 open questions enumerated with proposed resolution paths. Reference instance: task substrate v2 phasing doc (`ca88f50`) is the canonical Phase 4 shape; future multi-phase architectures inherit the 8-section structure.

---

### Entry 28 — Audit-vs-redo discipline during resume work

**Date:** 2026-05-26
**Folds:** C45
**Altitude:** dispatch-pattern

**Rule.** Type-system diagnostics (unused imports; missing prop receivers; orphan exports) are kill-experience signals during resume work that indicate substrate-present-but-undisturbed rather than substrate-missing. Audit-first reads these signals before assuming substrate is missing; audit-then-fix at ~10% the LOC cost of redo work. Resume agents audit-first before assuming substrate is missing.

**Rationale.** The discipline emerged during WB-cycle-followup-1 resume work when the operator's framing surfaced "substrate appears missing" but audit revealed substrate present-but-undisturbed via type-system diagnostics. The redo path would have cost ~1,990 LOC of rebuild; audit-then-fix shipped ~170 LOC of surgical repair. Type-system diagnostics signal substrate presence indirectly: unused imports indicate exports without consumers (substrate present, unused); missing prop receivers indicate consumers without producers (substrate missing OR substrate name-changed); orphan exports indicate producers without consumers (substrate present, consumer-side broken). The signals require interpretation, not literal reading — "missing prop receiver" might mean substrate truly missing OR substrate present under different name. Audit work disambiguates; redo work assumes the worst case. The ~10% LOC cost ratio is canonical for resume context; the audit-first discipline pays for itself an order of magnitude across resume sessions.

**Implementation.** Resume work opens with type-system diagnostic scan: unused imports, missing prop receivers, orphan exports surfaced explicitly. Each diagnostic interpreted before redo work begins — "missing X" might be substrate-missing OR substrate-present-under-different-name OR substrate-present-but-misconfigured. Audit work writes diagnostic interpretation to investigation deliverable (or commit message for in-flight resume); audit-then-fix proceeds against confirmed substrate-missing diagnostics; substrate-present diagnostics surface as configuration/wiring fixes. Reference instance: WB-cycle-followup-1 resume work (~170 LOC audit-then-fix vs ~1,990 LOC redo counterfactual). Cross-reference: DECISIONS.md 2026-05-26 — Investigation-methodology canon (audit-first discipline; this entry specifies resume-context application).

---

### Entry 29 — Substrate-extending arcs with colliding field names

**Date:** 2026-05-26
**Folds:** C50
**Altitude:** dispatch-pattern

**Rule.** Substrate-extending arcs that encounter parallel substrates with colliding field names explicitly enumerate which substrate is canonical before extending either. Investigation Phase 1 audit includes "name-collision check" for substrate boundaries where parallel storage layers (column vs JSON blob; table vs configuration; etc.) might use the same field name with divergent semantics.

**Rationale.** The pattern surfaced during WB-8 work when `widget_definitions.variants` column was discovered alongside `composition_blob.variants[]` array — both named "variants" but with structurally different semantics. Without explicit canonical-substrate enumeration, substrate-extending work could land on either substrate ambiguously, producing future arcs that can't determine which substrate is authoritative. The discipline requires investigation to surface name collisions at audit time + adjudicate canonical-substrate explicitly + document the non-canonical substrate's relationship (deprecation candidate, parallel-substrate-with-distinct-purpose, future-consolidation-target). The two-parallel-variant-substrates finding generalizes: any substrate extension encountering parallel storage with name collision must adjudicate canonical-substrate before extending.

**Implementation.** Investigation Phase 1 audit includes name-collision check: for each substrate boundary in scope, audit parallel storage layers for field-name collisions. Surfaced collisions adjudicate canonical-substrate + document non-canonical-substrate disposition in Phase 1 deliverable. Substrate-extending build dispatch references canonical-substrate explicitly; non-canonical substrate either coexists with documented purpose or files as consolidation candidate. Reference instance: WB-8 variants name collision (column vs blob); investigation surfaced + adjudicated canonical-substrate at Phase 1 audit per discipline.

---

### Entry 30 — Sub-arc decomposition seams discovered during investigation

**Date:** 2026-05-26
**Folds:** C82
**Altitude:** dispatch-pattern

**Rule.** Sub-arc decomposition surfaces during investigation, not during build. Decomposition is investigation work — investigation discovers seams where sub-arc boundaries naturally cohere around substrate-shape distinctions; build executes against locked decomposition. Build-time decomposition attempts re-investigate substrate boundaries mid-execution, which is the wrong altitude for the decision.

**Rationale.** The pattern emerged from WB-4 work where investigation discovered the WB-4a/WB-4b split — substrate-shape distinctions between configuration-substrate and runtime-substrate work cohered as natural sub-arc boundaries. The seam was investigation-visible before build dispatched against the locked decomposition; build executed cleanly against the locked split because the substrate-shape distinction had been adjudicated. Counter-pattern: build agents encountering sub-arc-decomposition questions mid-execution surface them as scope decisions, but the cost of mid-execution decomposition is high — working tree state complicates re-decomposition, commit-shape decisions get re-litigated, build-agent context budget consumed on investigation work. Investigation-altitude decomposition keeps decomposition decisions at investigation altitude where they belong.

**Implementation.** Investigation Phase 2-3 work explicitly considers sub-arc decomposition as substrate-shape question: where do substrate-shape distinctions cohere as natural sub-arc boundaries? Phase 4 phasing recommendation locks decomposition before build prompt drafts. Build prompts reference decomposition as locked input, not as decision to be made at build time. When build agent surfaces "this sub-arc has internal seam" mid-execution, the surfacing is escalation to operator for investigation-altitude decision, not build-altitude resolution. Reference instances: WB-4a/WB-4b investigation-discovered split; v1 task substrate B1/B2/B3 three-commit structure (decomposition locked at Lock A revision moment, not at sub-arc execution time). Cross-reference: 2026-05-13 (PM) Studio 1a-i sub-arc refinement entry (related but does not supersede; that entry covers specific Studio sub-arc decomposition; this entry generalizes the "investigation discovers seams" principle).

---

### Entry 31 — Bounded-decision-per-arc explicit naming pattern

**Date:** 2026-05-26
**Folds:** C88
**Altitude:** dispatch-pattern (re-altituded from Phase 0 lineage-fact)

**Rule.** Every arc opens with a stated bounded decision in dispatch + every arc closes when the stated bounded decision is closed. The explicit naming pattern (`"Bounded decision the v1 build arc closes: ship task substrate v1 per locked scope (v1.0 substrate + v1.5 integration)"`) makes the arc's closure criterion legible to operator + future-Claude. Pattern surfaces existing-but-unnamed discipline that becomes canonical when consistently applied across arcs.

**Rationale.** The bounded-decision-per-arc discipline operated informally across many arcs in the WB cycle + task substrate lineage; the explicit naming pattern shipped consistently in v1 task substrate investigation arcs through the build prompt + v1 build arc dispatch + canon-update arc dispatch. The naming pattern matters because closure criteria implicit in arc framing are interpretable differently by build agent vs operator; explicit naming locks the criterion. Future-Claude reading a dispatch can identify the bounded decision before reading the rest of the dispatch + verify the dispatch's locked scope matches the bounded decision. The discipline complements DECISIONS.md 2026-05-26 — Investigation-methodology canon at the dispatch-altitude: investigation arcs apply bounded-decision-per-arc per investigation phase; build arcs apply per sub-arc; canon-update arcs apply per phase.

**Implementation.** Dispatch headers include `Bounded decision this arc closes: "..."` line stating the closure criterion verbatim. Arc-close moments verify the stated bounded decision is closed before committing or proceeding to next-arc. STATE.md close notes reference the bounded decision at close. Future dispatches adopt the naming pattern as canonical shape. Reference instances: v1 task substrate v1 build arc dispatch (this lineage); canon-update arc dispatch (this lineage); v2 investigation arc dispatches.

---

### Entry 32 — Per-arc pre-dispatch rescoping for distant-horizon arcs

**Date:** 2026-05-26
**Folds:** C90
**Altitude:** dispatch-pattern

**Rule.** Distant-horizon arcs (v3+ work in multi-phase sequencing; arcs whose dispatch trigger is operator-observable signal that may surface months later) cannot be scope-locked at phasing time. Rescoping discipline absorbs the temporal drift: distant-horizon arcs ship in phasing recommendations with explicit "rescope at dispatch" lock; scope re-evaluated against then-current platform state and operator signal context when dispatch trigger surfaces.

**Rationale.** The discipline emerged at task substrate v2 phasing §8.6 when v3 scope projected ~7,000-15,000 LOC across multiple potential arcs (v3a contractor portal + v3b coaching pattern + v3c shelf parking + v3d Workshop UI + v3e operational extensions). Locking v3 scope at phasing time would over-commit against signal patterns that haven't surfaced yet; tightening v3 scope artificially to fit 25k v1+v2+v3 ceiling would under-deliver the May 21-22 vision without operator-validated need-to-cut. The resolution: accept ~22-31k envelope with explicit "v3 per-arc pre-dispatch rescoping" lock; 25k anchor shifts to v1+v2 only; v3 arcs each earn their own investigation-first phase before dispatch with then-current scope re-evaluation. The pattern generalizes: any sub-arc whose dispatch trigger lies beyond ~3-6 months of phasing time inherits temporal drift risk (platform state shifts; operator signal context evolves; canonical patterns mature) — rescoping discipline absorbs the drift honestly rather than locking scope against assumptions that may not hold at dispatch time.

**Implementation.** Phasing recommendations explicitly tag distant-horizon arcs as "rescope at dispatch" with rationale (signal-trigger timing; substrate-maturity-pending). Distant-horizon arcs dispatch via investigation-first arc that includes rescope phase against then-current state. Rescope phase surfaces: (a) what platform state has shifted since phasing time; (b) what operator signal context has surfaced; (c) what canonical patterns have matured that affect substrate decisions; (d) what scope adjustments these shifts warrant. Operator confirms rescope before sub-arc proper dispatches. Reference instance: task substrate v2 phasing doc §8.6 v3 per-arc pre-dispatch rescoping lock; v3a/v3b/v3c/v3d/v3e arcs each earn rescope phase before substantive substrate work dispatches. Cross-reference: DECISIONS.md 2026-05-26 — LOC calibration canon for substrate-additive arcs (ceiling-violation handling that surfaced this discipline); DECISIONS.md 2026-05-26 — Operator-observable signals canon (dispatch-trigger shape).

---

## Pass 5 — Verification-pattern (3 entries)

### Entry 33 — Runtime-Pydantic-TypeScript symmetry audit canon

**Date:** 2026-05-26
**Folds:** Cluster 2 — C77 (anchor), C68, C74, C86
**Altitude:** verification-pattern (primary) with substrate-decision dimension

**Rule.** Runtime-vs-Pydantic-vs-TypeScript triad symmetry audit is structural to sub-arc execution for evolving substrate, not optional. Pydantic Optional ↔ TypeScript undefined boundaries require explicit null↔undefined coercion at construction sites; type-level cleanliness emits differently at runtime. Symmetry audit applies most strongly to substrate that evolves across sub-arcs; stable substrate (specified once, consumed without extension) stays symmetric without audit overhead. Cross-side TypeScript symmetry locks audit all consumption sites, not just enumerate the canonical type file — consumption-site enumeration is the audit's load-bearing dimension.

**Rationale.** Four-instance pattern across WB cycle: WB-2 Surprise 1 canonical TypeScript interface drift; WB-4a Surprise 1 runtime-vs-Pydantic drift; WB-4b platform-wide Pydantic-runtime drift; WB-6 stable-substrate-stays-symmetric refinement. The pattern surfaces a discipline that's strong when ignored (symmetry drift produces reactive fix-arc work that could have been preventive investigation work) and refines when applied (stable substrate doesn't pay the symmetry-audit cost; only evolving substrate does). The BindingRef construction-site finding (C68) is the canonical mechanism instance: Pydantic `Optional[str]` ↔ TypeScript `string | undefined` is clean at type level but emits differently at runtime — runtime values cross the boundary as null vs undefined, and construction sites must coerce explicitly to preserve downstream type contracts. The consumption-site enumeration finding (C86) is the audit-completeness criterion: enumerating the canonical type file alone misses drift in consumer sites that haven't migrated to the canonical type; symmetry audit must include all consumption sites + per-site verification. The stable-vs-evolving refinement (C74) prevents over-application of the discipline: substrate that's stable (specified once at substrate-design and consumed without extension across sub-arcs) doesn't accumulate symmetry drift; symmetry audit cost applies to substrate that evolves across sub-arc landings.

**Implementation.** Investigation Phase 3 substrate design specifies symmetry audit requirement per substrate: stable (audit at first landing; not re-audited per sub-arc) vs evolving (audit at every sub-arc landing). Substrate-additive sub-arcs include triad symmetry audit step per evolving substrate touched: runtime values + Pydantic schema + TypeScript types verified consistent. Construction-site boundaries between Pydantic and TypeScript include explicit null↔undefined coercion (`value ?? undefined` or equivalent at TypeScript consumption; `value or None` at Pydantic emission). Consumption-site enumeration audit grep for all consumer sites of the canonical type + per-site verification of expected shape consumption. Reference instances: WB-2 Surprise 1 canonical TypeScript interface drift; WB-4a Surprise 1 runtime-vs-Pydantic drift; WB-4b platform-wide drift; WB-6 stable-substrate refinement. Distinct from F-series cross-side-contracts canon (2026-05-19 entries) — that canon addresses test-shape for cross-side contracts; this canon addresses runtime-vs-Pydantic-vs-TypeScript type symmetry independent of test-shape.

---

### Entry 34 — Test-substrate JSDOM-blind-spot canon

**Date:** 2026-05-26
**Folds:** Cluster 12 — C47 (anchor), C78
**Altitude:** verification-pattern

**Rule.** Test substrate constraints inform UX patterns at substrate boundary. JSDOM cannot exercise drag-handle reorder, base-ui Select open behavior, or async-data-arrival data-shape-change effects; alternative affordances (Chevron reorder + base-ui-compatible alternatives + separate effect for data-shape change) ship instead. Defer JSDOM-incompatible UX flows to Playwright + cover state machine via hook-level unit tests. Async-data-arrival patterns require effect that triggers on data shape change, distinct from URL parameter change effects — conflating mount + URL change with async data arrival is a real bug class whose symptom doesn't surface in JSDOM.

**Rationale.** Two-instance pattern with established Q-40 generalization canon (2026-05-21) as anchor. Test substrate constraints aren't neutral against UX design: when JSDOM cannot exercise a UX flow, the substrate-correctness verification cost shifts from cheap (Vitest + JSDOM) to expensive (Playwright + browser environment). The discipline is to acknowledge the constraint at substrate-design time and ship alternative affordances that preserve user-facing functionality while moving expensive verification cost to Playwright. The async-data-arrival pattern (C78) is the canonical bug-class instance: effect bound to URL parameter change fires on mount + URL change but misses async data shape changes that happen post-fetch with unchanged URL parameters. JSDOM doesn't surface the symptom because JSDOM tests typically provide synchronous data or mock async behavior; the bug surfaces in production when real async data arrives mid-render. The discipline requires separate useEffect for data shape change vs URL change so both trigger pathways fire correctly.

**Implementation.** Substrate design surfaces UX flow's JSDOM compatibility as audit dimension. JSDOM-incompatible flows ship: (a) alternative affordance for primary user path (Chevron reorder instead of drag-handle; manually-managed open state instead of base-ui Select); (b) Playwright coverage for the full flow; (c) hook-level unit tests covering state machine without UI. Async data consumption ships separate useEffect per trigger source: URL parameter effect; data-shape-change effect (depends on data identity/shape, not just data presence). Reference instances: drag-handle vs Chevron reorder UX disposition (Vitest-coverable affordance for primary path); base-ui Select alternative affordance pattern; async-data-arrival data-shape-change effect bug class. Pairs with 2026-05-21 Q-40 generalization canon (existing entry).

---

### Entry 35 — Test isolation discipline for idempotency-load-bearing substrate

**Date:** 2026-05-26
**Folds:** C21 (anchor), C92 absorbed
**Altitude:** verification-pattern

**Rule.** Composite-key-enforced idempotency at substrate level changes test-isolation requirements at consumer level. Tests exercising idempotency-load-bearing substrate use uuid-randomized identifier per test OR explicit per-test cleanup. Hardcoded identifiers across test runs collide with substrate idempotency and produce false test fragility — the substrate's correctness behavior bleeds through into test failure when test fixtures don't account for the idempotency mechanism.

**Rationale.** The discipline emerged during v1 task substrate B1 verification when 5 Phase A tests failed against polluted dev DB; investigation traced to hardcoded `provenance_ref_id` values in the affected tests. The substrate's canonical idempotency precheck (composite key on `(provenance_kind, provenance_ref, event_kind)`) correctly returned the existing done-state task on re-run, causing test transition-from-done to fail when DB carried prior-run state. The substrate behavior was correct; the test isolation was wrong. The fix isn't to weaken substrate idempotency (which would break the load-bearing operationally-idempotent claim that revised Lock 1 depends on); it's to make tests honor substrate idempotency via per-test isolation. The pattern carried forward consistently across v1 build arc sub-arcs: B2 parity tests (19 new) and B3 substrate tests (31 new) both used uuid-randomized `provenance_ref_id` per test from inception, preventing the Phase A test-pollution finding from recurring. The discipline applies beyond task substrate to any future substrate with composite-key-enforced idempotency.

**Implementation.** Tests exercising idempotency-load-bearing substrate generate fresh identifiers per test via `uuid.uuid4()` or equivalent. Alternative: explicit per-test cleanup deletes prior-run rows from the affected table at test setup. Build agent documents test-isolation pattern choice in test file docstring (uuid-randomized vs cleanup). When substrate design includes composite-key-enforced idempotency, test cohort scope explicitly notes test-isolation discipline as substrate-correctness implication. Reference instances: v1 task substrate B1 Phase A test-pollution finding (5 affected tests with hardcoded `provenance_ref_id`); B2 parity test cohort (19 tests, uuid-randomized); B3 substrate test cohort (31 tests, uuid-randomized). Cross-reference: DECISIONS.md 2026-05-26 — Substrate-transition discipline for substrate-additive arcs (covers operationally-idempotent dual-write discipline at substrate layer; this entry covers test-discipline implication).

---

---

# Phase 2.B — 10 canon-doc edits across 5 canon docs

**Permission boundary reminder:** Phase 2.B edits are Opus-authored canon (same as Phase 2.A DECISIONS.md entries). Sonnet's staging work applies these edits to target canon docs at verified placement points + normalizes cross-references.

**Cross-reference handling at staging:** Internal references using "DECISIONS.md 2026-05-26 — `<title>`" shape land verbatim; references to canon docs use actual section numbers verified at staging.

**Placement-decision locks from operator confirmation at Pass 2.B.1 close:**
- Edit 1 placement: H3 within CLAUDE.md §4 (matches Bridgeable Vault placement convention)
- Edit 2 shape: canonical 9-section PLUGIN_CONTRACTS shape per doc's "verbatim" rule
- Edit 3 framing: "§3.24 Bridgeable Vault — V-1 Roll-Up extension"
- Edit 4 placement: PLATFORM_ARCHITECTURE §3.3 (The Pulse Surface), not §3.4
- Edit 5 placement: PLATFORM_ARCHITECTURE §5 Focus (correct as drafted)

**Placement-decision locks from operator confirmation at Pass 2.B.2 close:**
- Edit 6: SPACES_ARCHITECTURE §10.15 new subsection
- Edit 7: CLAUDE.md §4 Admin Platform Architecture new bold-headed paragraph
- Edit 8: CLAUDE.md §4 Admin Platform Architecture new bold-headed paragraph (positioned after audit-attribution-limitation paragraph)
- Edit 9: CLAUDE.md §4 new H3 subsection (Studio-builder Mapping Table)
- Edit 10: CLAUDE.md §4 Component Registry subsection appended paragraph

---

## Pass 2.B.1 — Task substrate canon (5 edits)

### Edit 1 — CLAUDE.md: New Task Substrate H3 subsection within §4

**Target doc:** `CLAUDE.md`
**Insertion point:** New H3 subsection within §4 Architecture, positioned immediately after `### Bridgeable Vault (V-1 complete — April 2026)` subsection per architectural-peer placement convention.
**Folds:** C5 + C6 merged
**Edit shape:** New H3 subsection opening with canonical statement, expanding into substrate details.

**Edit text:**

```markdown
### Task Substrate (v1 complete — May 2026)

Bridgeable runs on tasks. The platform's operational model is task-centric: tasks are the canonical representation of work that needs attention. All operational events that require human awareness, decision, or action manifest as tasks. The platform's various capabilities relate to each other through task lifecycle — workflows create and complete tasks; Focuses enable task work; documents are often task outputs; communications are often task triggers and task outputs; Intelligence creates tasks from observations.

The task substrate is foundational, not feature. It exists at the level of Vault-as-foundation and workflow-as-orchestration — substrate that capabilities consume rather than capability among many.

User experience of the platform is fundamentally about task awareness and task completion. The platform's value proposition is helping users know what needs doing and helping them complete it efficiently, with reduced cognitive burden of tracking work mentally.

**Substrate shape.** Tasks are VaultItems with `item_type='task'` (12th value added to existing 11-value enum at v1 task substrate B1) + `task_details` join table for task-specific fields. The hybrid pattern preserves Vault-as-canonical-row-type while normalizing task-specific schema (assignee, lifecycle_shape, provenance, visibility, etc.) into a dedicated join table. Task service layer + Task façade preserves backward-compat for the 8 existing Task consumers; consumers query through service-layer abstraction rather than direct table access.

Task lifecycle is dual-shape: action shape (`created → assigned → in_progress ↔ blocked → done | cancelled`) for tasks requiring completion action; reminder shape (`informational → acknowledged | dismissed`) for time-based informational tasks that don't require completion. Lifecycle state machine implementation lives at `backend/app/services/tasks/lifecycle.py`; backward-compat mapping from existing 5-state machine ships in backfill.

Task provenance is polymorphic across 12 `provenance_kind` values (workflow_step, intelligence_observation, manual_creation, communication_inbound, integration_event, shelf_parking, coaching_observation, scheduled_recurring, triage_event, focus_completion, anomaly_detection, system_internal). Composite idempotency key `(provenance_kind + provenance_ref + event_kind)` is partial-unique at schema layer; this is load-bearing for the operationally-idempotent claim that task-creation-event-driven dispatch depends on.

**Plugin substrate.** Three plugin categories register against the task substrate (see PLUGIN_CONTRACTS.md):
- **Task creators** (workflow steps, Intelligence observations, communications, shelf parking, manual creation, future triage adapters)
- **Task surfaces** (list views, detail views, creation forms, Pulse Personal layer wire, briefings consumption, future authoring surfaces)
- **Task type behaviors** (lifecycle behaviors, surface defaults, routing defaults per task type)

v1 ships 5 task type behavior plugins: `generic_task`, `review_approval_task`, `scheduled_recurring_task`, `customer_communication_task`, `anomaly_resolution_task`. Future task types register additively against the substrate.

**Subscriber registry.** Task lifecycle events fire to a subscriber registry (7 event types × 6 v1 subscribers; sync dispatch with isolated try/except per subscriber at `backend/app/services/tasks/subscribers/`). v1 subscribers: `audit_writer` (active at substrate-foundation), `notification_dispatcher` (active post-B2 (c) refactor), `briefings_invalidator`, `pulse_invalidator`, `workflow_resumer`, `focus_closer` (all active post-B3 consumer integration).

**Producer integration.** (c)'s 8 producer sites flow through task substrate post-v1.5 B2 refactor: producer call-sites create tasks via `task_service.create_task_with_provenance`; notification dispatch fires from task-creation events via subscriber registry rather than producer-direct dispatch. Parity preserved bit-for-bit at recipient side. Site mapping documented at task substrate v1 completion artifact §2 producer refactor section (`docs/investigations/task_substrate_v1_completion.md`).

**Reference instances.** v1 task substrate shipped across 3 commits: `2fba161` (B1 substrate foundation + r108 Focus extension), `a400d1b` (B2 (c) producer refactor), `1c8dbbd` (B3 consumer integration + r109 routing rules + v1 arc close). v1 build prompt at `docs/investigations/task_substrate_v2_v1_build_prompt.md`; v1 completion artifact at `docs/investigations/task_substrate_v1_completion.md`. v2 sub-arcs (10-triage-queue adapters, family portal, substrate refinements) await operator-observable signals per task substrate v2 phasing doc §5.
```

---

### Edit 2 — PLUGIN_CONTRACTS.md: 3 new plugin categories (canonical 9-section shape)

**Target doc:** `PLUGIN_CONTRACTS.md`
**Insertion point:** 3 new numbered top-level categories slotting among existing structure. Position determined at staging (likely positions ~11-13 or similar after existing 10 ✓ canonical categories at v1.0; staging reads current TOC + section numbering to finalize positions). Categories ship as `✓ canonical`. TOC entries updated alongside section additions.
**Folds:** C9
**Edit shape:** 3 new categories, each following the doc's canonical 9-section structure verbatim (Purpose / Input Contract / Output Contract / Guarantees / Failure Modes / Configuration Shape / Registration Mechanism / Current Implementations / Cross-References).

**Edit text:**

```markdown
## NN — Task creators

### Purpose

Plugins registering as task creators emit task entities from producer-side events. Producer sites — workflow steps completing, Intelligence observations surfacing, communications arriving, shelf parking events firing, future triage adapters, manual user creation — dispatch task creation through the task substrate via service-layer entry point. The category establishes the contract producer sites adhere to when authoring task-creating substrate.

### Input Contract

`task_service.create_task_with_provenance(company_id, provenance_kind, provenance_ref_type, provenance_ref_id, event_kind, task_type_key, title, description, assignee_user_id?, priority?, due_date?, suppression_key?, metadata?)` at `backend/app/services/tasks/task_service.py`.

Required fields: `company_id` (tenant scope); `provenance_kind` (Enum: 12 values per task substrate v1 lock); `provenance_ref_type` + `provenance_ref_id` (polymorphic source-entity reference); `event_kind` (substrate's lifecycle-event vocabulary); `task_type_key` (selects task type behavior plugin); `title`; `description`.

Optional fields: `assignee_user_id` (routing target; substrate falls back to task type behavior's routing default when absent); `priority` (substrate falls back to task type behavior's priority default); `due_date`; `suppression_key` (operator-facing notification suppression); `metadata` (JSONB free-form; producer-supplied context that subscribers may discriminate on per DECISIONS.md 2026-05-26 — Subscriber-substrate canon for task-event-driven dispatch).

### Output Contract

Returns `Task` façade object wrapping the created entity (VaultItem with item_type='task' + task_details row created in single atomic transaction). Task façade preserves backward-compat for the 8 existing Task consumers; new consumers use the canonical entity shape.

Substrate guarantees idempotency via composite key `(provenance_kind + provenance_ref + event_kind)` partial-unique constraint; on collision, substrate returns the existing task rather than raising or creating duplicate. Producer sites can safely retry; substrate is operationally idempotent.

### Guarantees

- Atomic creation in single transaction (VaultItem + task_details together, or neither)
- Subscriber registry fires post-creation (7 event kinds × 6 v1 subscribers; sync dispatch with isolated try/except per subscriber)
- Composite-key idempotency prevents duplicate creation across producer retries
- Task façade preserves backward-compat against existing Task consumers (8 sites at v1 close)

### Failure Modes

- **Composite key collision** → substrate returns existing task entity (canonical idempotency behavior; not a failure mode operationally)
- **FK violation on `company_id`** → raises `IntegrityError`; producer site responsibility to ensure tenant scope is valid
- **Subscriber-side failure** → individual subscriber error caught + logged via try/except; doesn't break task creation or other subscribers (sync dispatch with isolated handlers per task substrate v1 B1 substrate foundation)
- **Producer-side defensive wrapper** → producer sites wrap `create_task_with_provenance` calls in their own try/except per V-1d substrate-additive discipline; failure to create task doesn't break producer-side correctness

### Configuration Shape

Producer-side plugins declare:
- `provenance_kind`: which `provenance_kind` value the plugin emits (single value per plugin in v1; future plugins may emit multiple)
- `task_type_default`: which `task_type_key` the plugin creates by default (overridable per call-site)
- Producer plugin's own configuration (workflow-step config, Intelligence observation config, etc.) flows through producer-plugin's contract; task creator contract is the downstream call surface

### Registration Mechanism

In-memory registry per existing Bridgeable Tier R1 plugin pattern. Plugins register at module import time via decorator or registration call (consistent with existing plugin categories' registration mechanism per doc's R1 canon). Registry queryable via `get_task_creators_for_provenance_kind(kind)`.

### Current Implementations

v1 task substrate ships 8 producer sites refactored to task-creator contract via (c) build arc (`868fec3`):
- `backend/app/services/workflow/workflow_step_completion.py:154` (workflow step → workflow_step provenance)
- `backend/app/services/intelligence/observation_dispatch.py:89` (Intelligence observation → intelligence_observation provenance)
- `backend/app/services/communications/inbound_router.py:201` (inbound communication → communication_inbound provenance)
- `backend/app/services/shelf_parking/event_dispatch.py:74` (shelf parking event → shelf_parking provenance)
- `backend/app/services/agent_anomaly/anomaly_creation.py:118` (anomaly detection → anomaly_detection provenance)
- `backend/app/services/scheduling/recurring_dispatch.py:67` (scheduled recurring → scheduled_recurring provenance)
- `backend/app/services/integration/external_event_router.py:142` (external integration event → integration_event provenance)
- `backend/app/api/v1/routers/tasks.py:78` (manual user creation → manual_creation provenance)

Future implementations: v2a triage-queue adapters (10 sites planned per task substrate v2 phasing doc §3); v2b family portal adapters; v3+ contractor portal / coaching pattern / Workshop UI plugins.

### Cross-References

- CLAUDE.md §4 Task Substrate subsection (substrate shape canon)
- BRIDGEABLE_MASTER §3.24 Bridgeable Vault — V-1 Roll-Up (task item_type ratification)
- Category NN+1 Task surfaces (downstream consumption of task-creator output)
- Category NN+2 Task type behaviors (selects behavior per `task_type_key`)
- DECISIONS.md 2026-05-26 — Subscriber-substrate canon for task-event-driven dispatch (downstream dispatch)
- `docs/investigations/task_substrate_v1_completion.md` §2 (producer refactor reference instances)

---

## NN+1 — Task surfaces

### Purpose

Plugins registering as task surfaces render task data per surface type — list views, detail views, creation forms, summary cards, badges. Surface plugins are the consumption-side counterpart to task creators; they consume task entities from substrate and render per consumer-facing context. v1 ships substrate contract; v1.5 wires Pulse Personal layer + briefings consumption as canonical surface implementations. Visual editor authors task surfaces per Studio canon.

### Input Contract

Surface plugins declare contract shape `(surface_key, surface_kind, accepted_task_types[], render_context() → component_props)`:
- `surface_key`: unique identifier per surface plugin (e.g. `pulse_personal_task_list`, `briefings_task_summary`)
- `surface_kind`: one of `SURFACE_KINDS` frozen tuple (5 v1 kinds: `list`, `detail`, `creation`, `summary`, `badge`)
- `accepted_task_types`: list of `task_type_key` values the surface plugin handles; `['*']` for catch-all surfaces
- `render_context()`: function receiving `(task_entity, viewing_user, surface_context)` and returning component-rendering props per the visual editor's component contract

### Output Contract

Returns component_props dict consumed by visual editor's surface renderer. Component props follow Bridgeable's visual editor canonical contract (see Component Registry category); task surface plugins emit props within that contract rather than rendering DOM directly.

### Guarantees

- Surface registration queryable via `get_task_surfaces_for_task_type(task_type_key, surface_kind)`; returns list of registered plugins matching both criteria, sorted by specificity (exact task_type_key match before catch-all `['*']`)
- Renderer-agnostic at substrate layer; visual editor consumption layer handles per-surface_kind rendering
- Surface plugins respect task entity visibility + tenant scope (substrate-enforced; surface plugins receive pre-filtered entities)

### Failure Modes

- **Surface not registered for task_type/kind combination** → substrate falls back to `generic_task` surface plugin (canonical default; renders task title + description + assignee + due_date as universally-applicable shape)
- **Surface plugin's `render_context()` raises** → caught + logged; visual editor renders error placeholder per existing component-error convention
- **No hard failure mode for unregistered surface** — fallback to generic_task is the canonical degradation path

### Configuration Shape

Surface plugins declare:
- `surface_key` (unique identifier)
- `surface_kind` (one of 5 v1 kinds)
- `accepted_task_types` (list of task_type_key values or `['*']`)
- Per-plugin component configuration following Bridgeable visual editor component contract (Component Registry category)

### Registration Mechanism

In-memory registry per Tier R1 plugin pattern. Plugins register at module import time. Registry maintains per-(task_type, surface_kind) lookup index for query performance.

### Current Implementations

v1 ships substrate contract; v1.5 wires canonical consumers:
- `_build_tasks_item` at `backend/app/services/pulse/personal_layer_service.py:111` (Pulse Personal layer list surface; wired in v1 task substrate B3 `1c8dbbd`)
- Briefings consumption via `backend/app/services/briefings/task_summary_builder.py:43` (summary surface; wired in v1 task substrate B3)

Future implementations: v2+ visual editor surfaces (operator-authored list/detail/creation surfaces per task type); customer-facing portal surfaces (per task substrate v2 phasing doc §3.2 family portal scope).

### Cross-References

- CLAUDE.md §4 Task Substrate subsection
- CLAUDE.md §4 Component Registry (visual editor component contract)
- PLATFORM_ARCHITECTURE §3.3 The Pulse Surface (per Space) (canonical surface consumer)
- Category NN Task creators (upstream producer contract)
- Category NN+2 Task type behaviors (selects surface defaults per task_type_key)
- DECISIONS.md 2026-05-26 — Subscriber-substrate canon for task-event-driven dispatch (surfaces consume invalidation events)

---

## NN+2 — Task type behaviors

### Purpose

Plugins registering as task type behaviors declare per-task-type defaults — routing mode, priority, lifecycle behaviors, surface defaults per surface_kind, on-status-change hooks. Task type behaviors are the substrate's "personality per task type" layer; they encode what makes a `review_approval_task` operationally distinct from a `customer_communication_task` from an `anomaly_resolution_task`. The category is foundational to the substrate's polymorphic task handling.

### Input Contract

Task type behavior plugins declare contract shape `(task_type_key, routing_mode_default, priority_default, lifecycle_shape_default, surface_key_defaults{}, on_status_change(task, old_state, new_state) → None, render_default_payload(task) → dict)`:
- `task_type_key`: unique identifier (e.g. `review_approval_task`)
- `routing_mode_default`: substrate's routing vocabulary (`assignee_direct`, `round_robin`, `permission_cohort`)
- `priority_default`: low/medium/high/critical per substrate's priority enum
- `lifecycle_shape_default`: `action` or `reminder` (selects which lifecycle state machine applies)
- `surface_key_defaults`: dict mapping surface_kind → surface_key (which surface plugin to default to per surface kind)
- `on_status_change(task, old_state, new_state)`: hook fired synchronously on lifecycle transition
- `render_default_payload(task)`: function returning task-type-specific render context for surface plugins

### Output Contract

Substrate consumes plugin's declared defaults at task creation + lifecycle transitions. Task creation with `task_type_key='X'` inherits plugin X's routing_mode_default + priority_default + lifecycle_shape_default unless explicitly overridden by producer site. Surface plugins resolve surface_key via per-task-type lookup (plugin X's surface_key_defaults[surface_kind]) before falling back to generic_task.

`on_status_change` hook fires within the lifecycle-transition transaction; plugin can read task state + side-effect into other substrate (e.g. `anomaly_resolution_task` marks `AgentAnomaly.is_resolved=True` on transition to done state).

### Guarantees

- Single plugin per task_type_key (registry enforces uniqueness; collision raises at registration)
- Plugin defaults applied at task creation unless explicitly overridden in `create_task_with_provenance` call
- `on_status_change` hook fires sync with isolated try/except; hook errors caught + logged + don't break lifecycle transition or other subscribers
- `render_default_payload` invoked per-render by surface plugins requesting task-type-specific context

### Failure Modes

- **Unknown task_type_key in task creation** → substrate falls back to `generic_task` plugin (canonical catch-all; provides universally-applicable defaults)
- **Plugin registration collision** (two plugins declaring same task_type_key) → raises at module import time before substrate operational
- **`on_status_change` hook raises** → caught + logged via try/except wrapper; doesn't break lifecycle transition
- **`render_default_payload` raises** → caught + logged; surface plugin uses empty dict + falls back to substrate-default render context

### Configuration Shape

Plugins declare task type behavior via plugin module with `__plugin_config__` declaration:
- `task_type_key`
- `routing_mode_default`, `priority_default`, `lifecycle_shape_default`
- `surface_key_defaults` dict
- `on_status_change` and `render_default_payload` as plugin-module-level functions

Plugin authors implement the two hook functions; substrate calls them per documented contract.

### Registration Mechanism

In-memory registry per Tier R1 plugin pattern. Plugins register at module import time via `@register_task_type_behavior(task_type_key='X')` decorator or `register_task_type_behavior(plugin)` registration call. Registry maintains `task_type_key → plugin` lookup; queryable via `get_task_type_behavior(task_type_key)`.

### Current Implementations

v1 ships 5 canonical task type behavior plugins at `backend/app/services/tasks/plugins/type_behaviors/`:
- `generic_task.py` (catch-all defaults; routing=assignee_direct, priority=medium, lifecycle=action, no on_status_change side-effects)
- `review_approval_task.py` (approval-gate cohort; routing=permission_cohort, priority=high; on_status_change maps `metadata.outcome` → resolution_outcome on transition to done)
- `scheduled_recurring_task.py` (round_robin routing override; on_created populates due_date from schedule config)
- `customer_communication_task.py` (outbound dispatch wired through delivery_service; on_status_change to in_progress triggers delivery dispatch)
- `anomaly_resolution_task.py` (priority=high override; on_status_change to done sets `AgentAnomaly.is_resolved=True` with best-effort try/except)

Future implementations: v2+ task types per operator-validated need (e.g. `contractor_quote_task` for v3a contractor portal arc; `coaching_observation_task` for v3b coaching pattern arc).

### Cross-References

- CLAUDE.md §4 Task Substrate subsection
- Category NN Task creators (producer contract; task_type_key selects behavior)
- Category NN+1 Task surfaces (surface_key_defaults consumed by surface plugins)
- DECISIONS.md 2026-05-26 — Subscriber-substrate canon for task-event-driven dispatch (on_status_change hooks fire alongside subscriber registry)
- DECISIONS.md 2026-05-26 — Substrate-transition discipline for substrate-additive arcs (metadata-based extension pattern relevant for plugin metadata consumption)
- `backend/app/services/tasks/plugins/type_behaviors/` (canonical plugin location)
```

---

### Edit 3 — BRIDGEABLE_MASTER.md §3.24: 12th item_type 'task' ratified

**Target doc:** `BRIDGEABLE_MASTER.md`
**Insertion point:** Extend existing §3.24 (Bridgeable Vault — V-1 Roll-Up section). Append "### Update (v1 task substrate)" subsection at appropriate position within §3.24 — staging reads §3.24 body to determine whether existing Update subsections exist + where new Update lands (bottom of §3.24 vs after existing Update subsections vs other).
**Folds:** C10
**Edit shape:** Append to existing §3.24; document 'task' addition + relationship to deferred 'reminder' enum value.

**Edit text:**

```markdown
### Update (v1 task substrate)

The VaultItem `item_type` enum gains its 12th value at v1 task substrate B1 (`2fba161`): `'task'`. Tasks are VaultItems following the hybrid schema pattern (CLAUDE.md §4 Task Substrate subsection): VaultItem row carries canonical identity + visibility + tenant scope; `task_details` join table carries task-specific fields (assignee_user_id, lifecycle_shape, provenance_kind, provenance_ref, etc.) with 1:1 enforced via UNIQUE constraint on `vault_item_id`.

The `'reminder'` enum value documented at this section as V-2 deferred remains in the enum but its usage maps to `'task'` with reminder-shaped lifecycle (`informational → acknowledged | dismissed`) per the dual-lifecycle pattern at v1 task substrate. Future arcs may consolidate the enum by removing `'reminder'` if substrate maturity validates that all reminder-shape use cases live cleanly under `'task'`; v1 preserves both enum values per backward-compat discipline.

Cross-reference: CLAUDE.md §4 Task Substrate subsection for substrate shape + lifecycle + plugin substrate detail; `docs/investigations/task_substrate_v1_completion.md` for v1 arc reference instances.
```

---

### Edit 4 — PLATFORM_ARCHITECTURE.md §3.3: Pulse Personal layer task references

**Target doc:** `PLATFORM_ARCHITECTURE.md`
**Insertion point:** Extend existing §3.3 (The Pulse Surface (per Space) section). Append subsection documenting v1.5 task substrate wire as implementation pattern OF Pulse Surface.
**Folds:** C11
**Edit shape:** Append to §3.3; document `_build_tasks_item` wire + task substrate as canonical "what needs attention" source.

**Edit text:**

```markdown
### Task substrate consumption (v1.5)

Pulse Personal layer renders task state as canonical "what needs attention" source for the viewing user. The `_build_tasks_item` implementation at `backend/app/services/pulse/personal_layer_service.py:111` queries VaultItem WHERE item_type='task' joined to task_details, filtered by user assignment + visibility + non-terminal lifecycle states (action shape: {created, assigned, in_progress, blocked}; reminder shape: {informational}). Pagination, sorting, projection follow existing Pulse Personal layer conventions.

The `_build_tasks_item` function was scaffolded-but-deferred at original Pulse Personal layer implementation (returned `None` pending wire decision); v1.5 task substrate B3 (`1c8dbbd`) wired the deferred stub against post-r107 task substrate. The deferred-handler-body pattern (CLAUDE.md §4 Task Substrate subsection — subscriber registry section) describes the general discipline; `_build_tasks_item` is a canonical pre-substrate instance of the pattern.

Pulse Personal layer cache invalidates on task lifecycle events via `pulse_invalidator` subscriber (registered in task substrate B1 foundation; handler body active post-B3 consumer integration). Task state changes propagate to Pulse rendering within sync dispatch latency.

Cross-reference: CLAUDE.md §4 Task Substrate subsection for substrate shape; `docs/investigations/task_substrate_v1_completion.md` §2 for v1 reference instances.
```

---

### Edit 5 — PLATFORM_ARCHITECTURE.md §5: Task → Focus relationship

**Target doc:** `PLATFORM_ARCHITECTURE.md`
**Insertion point:** Extend existing §5 Focus (Decide) section. Append subsection at next-available numbering (likely §5.13 — staging verifies final subsection count).
**Folds:** C12
**Edit shape:** Append to §5; document r108 focus_session.task_id column + task-completion-closes-focus-session behavior.

**Edit text:**

```markdown
### Task Substrate Linkage (v1.5)

Focus sessions track originating tasks via `focus_session.task_id` FK column (added at r108 migration in v1 task substrate B1, `2fba161`). The FK uses `ON DELETE SET NULL`: if a VaultItem of type='task' deletes, the focus_session survives with task_id cleared rather than cascade-deleting focus sessions.

Focus → task workflow: tasks say "decide this"; Focus is where the decision gets made. When a Focus opens against a task, focus_session.task_id is populated at session creation. When the task transitions to done lifecycle state, `focus_closer` subscriber (registered in task substrate B1 foundation; handler body active post-B3 consumer integration at v1.5 close) closes corresponding focus_sessions automatically.

The bidirectional pattern (task creation → Focus opening; task completion → Focus closing) is the operational manifestation of the May 21-22 conversation's "Focuses are task work environments" architectural claim. Forward-only discipline applies: existing focus_sessions retain task_id=NULL; v1.5 work populates for newly-created sessions at task-creation time.

Cross-reference: CLAUDE.md §4 Task Substrate subsection for substrate shape; r108 migration at `backend/migrations/versions/r108_*.py` for FK schema specifics.
```

---

## Pass 2.B.2 — Studio + admin platform architecture canon (5 edits)

### Edit 6 — SPACES_ARCHITECTURE.md: New §10.15 subsection (task substrate cross-realm forward-compat)

**Target doc:** `SPACES_ARCHITECTURE.md`
**Insertion point:** New §10.15 subsection after §10.14 deferral list, before §11 two-layer navigation rationale.
**Folds:** C29
**Edit shape:** New numbered subsection within §10 Portal Foundation; documents task-substrate forward-compat extension for customer-facing portals.

**Edit text:**

```markdown
### 10.15 Task substrate cross-realm forward-compat (v1 close)

v1 task substrate ships with cross-realm forward-compat schema for customer-facing portal consumption. Tenant-realm task creation today; customer-facing portal task creation contemplated at v2b family portal arc per task substrate v2 phasing doc §3.2. The substrate's foundational schema accommodates both realms without breaking changes when customer-facing portals consume task substrate.

Forward-compat shape:

- **`task_details.visibility` enum extension** — current enum values cover tenant-realm visibility (`tenant_internal`, `tenant_assigned`, `tenant_audit`); v2b customer-portal visibility values (`customer_visible`, `customer_actionable`, `customer_informational`) ship as enum extension when family portal arc dispatches. No schema migration required mid-flight; enum value addition is backward-compatible.

- **`task_details.creator_realm` column** — VARCHAR(20) NULL column added at r107 captures realm context of task creation site (`tenant`, `customer_portal`, `system`). v1 task substrate B1 backfilled existing tasks with `creator_realm='tenant'`; new tasks created via tenant routes inherit `creator_realm='tenant'`. v2b customer-portal task creation will populate `creator_realm='customer_portal'` for portal-created tasks.

- **Provenance kinds reserved for customer-portal sources** — `provenance_kind` enum at v1 includes `customer_communication_inbound` value (currently unused; reserved for v2b customer-portal inbound communication producer). Customer-portal-originated tasks dispatch through canonical task creator contract (PLUGIN_CONTRACTS.md task creators category) with portal-specific producer plugins.

Cross-realm portal task surfaces follow Portal Foundation §10's path-scoped routing + JWT realm extension patterns. Customer-portal task surface plugins register against canonical PLUGIN_CONTRACTS.md task surfaces category with `accepted_task_types` filtered to customer-visible task types; portal renderer respects `task_details.visibility` filtering at query time.

The forward-compat substrate ships at v1 close per DECISIONS.md 2026-05-26 — Substrate-minimal-default canon: narrow + canonical foundation that expands additively when customer-portal arc dispatches. Future arcs against the substrate find the cross-realm hooks ready; no v1 task substrate redo required for v2b family portal landing.

Cross-references:
- CLAUDE.md §4 Task Substrate subsection (substrate shape canon)
- PLUGIN_CONTRACTS.md task creators / task surfaces / task type behaviors categories
- §10.10 Office vs operational distinction (portal-realm authentication boundary; relevant to customer_portal creator_realm enforcement)
- `docs/investigations/task_substrate_v2_phasing.md` §3.2 (family portal arc scope)
```

---

### Edit 7 — CLAUDE.md §4 Admin Platform Architecture: Realm-agnostic service layer

**Target doc:** `CLAUDE.md`
**Insertion point:** New bold-headed paragraph within existing Admin Platform Architecture H3 subsection (line 407 area). Positioned after the existing paragraphs covering tenant/admin tree structure + adminPath() helper + backend route placement.
**Folds:** C32
**Edit shape:** Bold-headed paragraph matching existing **Bold (arc-reference, date):** convention.

**Edit text:**

```markdown
**Realm-agnostic service layer (WB-cycle-followup-2, 2026-05-26):** Service-layer modules consumed by both tenant-realm and admin-platform-realm routers ship realm-agnostic. The service layer takes operational primitives (company_id, requested operation, data) without coupling to which router invoked it; realm-specific concerns (auth context, route prefix, response envelope) live at the router layer not the service layer.

The pattern was load-bearing at WB-cycle-followup-2 (`33d5721`) where Widget Builder substrate originally shipped with tenant-router coupling at service layer; the 403 gap on Studio (admin-realm) consumption forced refactor to realm-agnostic service. Post-refactor, `visual_editor_widgets_service` consumed by both `/api/v1/widget-builder/*` (tenant router) and `/api/platform/admin/widget-builder/*` (admin platform router) with identical service-layer behavior; auth context flows through router-layer dependencies (`get_current_user` vs `get_current_platform_user`); service layer operates against company_id + operation + data without realm awareness.

Pattern application: Studio-authored substrates (substrates whose primary authoring surface lives in Studio admin shell) ship realm-agnostic at service layer from foundation, not retrofit. Service-layer modules under `backend/app/services/visual_editor/` are canonical realm-agnostic examples; new visual-editor substrates extend this convention.

Cross-reference: `Per-request API URL resolution` paragraph (this subsection) for the client-side counterpart pattern; DECISIONS.md 2026-05-26 — Discoverability canon for operator-facing substrate cycles (auth-realm reachability verification as substrate-cycle dimension).
```

---

### Edit 8 — CLAUDE.md §4 Admin Platform Architecture: last_edit_session_actor_id without FK pattern

**Target doc:** `CLAUDE.md`
**Insertion point:** New bold-headed paragraph within existing Admin Platform Architecture H3 subsection, positioned immediately after the existing "Audit attribution limitation (relocation phase, May 2026)" paragraph.
**Folds:** C33
**Edit shape:** Bold-headed paragraph matching convention. Explicitly references the preceding audit-attribution-limitation paragraph as the problem statement this paragraph resolves.

**Edit text:**

```markdown
**`last_edit_session_actor_id` without FK pattern (WB-cycle-followup-2, 2026-05-26):** The audit attribution limitation documented above (PlatformUser vs User FK constraint problem) resolves via the `last_edit_session_actor_id` without-FK pattern. Affected columns ship as `VARCHAR(36) NULL` (UUID string) rather than `UUID NULL` with FK constraint to a specific user table. The string-typed column accepts UUIDs from either user-source table (`User` for tenant-realm edits; `PlatformUser` for admin-realm edits) without schema-level enforcement of which table the UUID references.

Audit reads resolve the user-source via two-step query: (1) attempt User lookup; (2) on miss, attempt PlatformUser lookup. The pattern preserves audit attribution across realms without requiring schema-level FK resolution. Substrate trades schema-enforced referential integrity for cross-realm audit attribution; the trade is honest given the realm-distinction architectural commitment.

The pattern applies to all substrate columns capturing actor identity that may originate from either realm (audit logs, last-edit attribution, content provenance). Substrate authors documenting `actor_id`-shaped columns specify which realms can produce values + which audit-read query pattern applies.

Cross-reference: preceding `Audit attribution limitation (relocation phase, May 2026)` paragraph for problem statement; DECISIONS.md 2026-05-26 — Substrate-extending arcs with colliding field names (relevant when audit columns share field names across substrates).
```

---

### Edit 9 — CLAUDE.md §4 new H3 subsection: Studio-builder Mapping Table

**Target doc:** `CLAUDE.md`
**Insertion point:** New H3 subsection within §4 Architecture, positioned among existing visual-editor-substrate H3 subsections, after `### Visual Editor Top-Level Structure (May 2026 reorganization)` (line 571 area). Lands as canonical reference subsection for Studio-builder routing.
**Folds:** C44
**Edit shape:** New H3 subsection introducing the canonical mapping table.

**Edit text:**

```markdown
### Studio-builder Mapping Table (WB-cycle close, 2026-05-26)

Canonical reference for Studio-builder substrates: frontend mount → backend router → realm → client. The table prevents repeat investigation of "where does Studio-builder X mount + what realm + what backend route prefix + which client?" — a question that surfaced reactively across WB cycle + studio nav arc work.

| Builder | Frontend mount | Backend router | Realm | Client |
|---|---|---|---|---|
| Theme Editor | `/admin/visual-editor/themes` (Studio) | `/api/platform/admin/visual-editor/themes/*` | platform | `adminApi` |
| Focus Editor | `/admin/visual-editor/focuses` (Studio) | `/api/platform/admin/visual-editor/focuses/*` | platform | `adminApi` |
| Widget Builder | `/admin/visual-editor/widgets` (Studio) + `/admin/widget-builder` (legacy alias) | `/api/platform/admin/visual-editor/widgets/*` (canonical) + `/api/v1/widget-builder/*` (tenant consumer path) | platform (Studio) + tenant (consumer) | `adminApi` (Studio) + `apiClient` (tenant) |
| Document Composer | `/admin/visual-editor/documents` (Studio) | `/api/platform/admin/visual-editor/documents/*` | platform | `adminApi` |
| Component Classes | `/admin/visual-editor/classes` (Studio) | `/api/platform/admin/visual-editor/classes/*` | platform | `adminApi` |
| Workflow Editor | `/admin/visual-editor/workflows` (Studio) | `/api/platform/admin/visual-editor/workflows/*` | platform | `adminApi` |
| Component Registry | `/admin/visual-editor/registry` (Studio) | `/api/platform/admin/visual-editor/registry/*` | platform | `adminApi` |

**Canonical pattern:** Studio-authored substrates default to platform realm via `/api/platform/admin/visual-editor/*` route prefix, consumed through `adminApi` client with `get_current_platform_user` auth dependency. Tenant-router consumer paths (`/api/v1/*`) exist for substrates with tenant-side consumers (e.g. Widget Builder's composed widgets registered at tenant boot); those paths route through realm-agnostic service layer (see `Realm-agnostic service layer` paragraph above) so consumption is realm-coherent at the service layer.

**Discoverability:** Each builder mounts in the Studio admin shell's left rail per Studio navigation arc (`3a019e1`). Builder rail entry registration lives in `frontend/src/admin/studio/nav-registry.ts`; entries reference the canonical frontend mount path. Future builders ship with rail entry registration as substrate deliverable (DECISIONS.md 2026-05-26 — Discoverability canon for operator-facing substrate cycles).

Cross-references:
- `Visual Editor Top-Level Structure` H3 subsection (editor-page-level enumeration; this table is broader)
- `Realm-agnostic service layer` paragraph (service-layer realm-coherence pattern)
- DECISIONS.md 2026-05-26 — Discoverability canon for operator-facing substrate cycles (auth-realm reachability verification)
- `docs/investigations/2026-05-26-widget-builder-auth-realm.md` (WB-cycle-followup-2 investigation context)
```

---

### Edit 10 — CLAUDE.md §4 Component Registry: Canvas widget-renderer registry

**Target doc:** `CLAUDE.md`
**Insertion point:** Append paragraph extending existing Component Registry H3 subsection (line 441 area).
**Folds:** C85
**Edit shape:** Bold-headed paragraph extending existing subsection, clarifying two-layer-registry distinction.

**Edit text:**

```markdown
**Canvas widget-renderer registry (R-1.6.12, 2026-05-26):** The Component Registry described above is the **visual-editor metadata registry** — admin-side metadata catalog covering component-kind enumeration, registration mechanism, public API for the visual editor's authoring surface. The visual-editor metadata registry lives at `frontend/src/lib/visual-editor/registry/` and serves authoring-time concerns: "what component kinds exist?", "what are their default property schemas?", "what UI variants are registered?"

The **canvas widget-renderer registry** is a distinct second registry serving runtime concerns. Canvas runtime (rendering authored widgets to operator-facing surfaces) consults a separate registry mapping component_kind → runtime renderer component. Canvas widget-renderer registry lives at `frontend/src/lib/canvas/widget-renderers.ts`; entries register at module import time via `registerWidgetRenderer(component_kind, renderer)` and are consumed by canvas rendering layer at runtime.

The two-layer distinction surfaced during WB-cycle work as substrate boundaries clarified: visual editor needs metadata about component kinds (for the authoring UI's component-kind palette, property schemas, etc.); canvas runtime needs renderer mappings (for actual DOM emission). Both layers consume the same component_kind enumeration but serve distinct runtime concerns. Substrate authors registering a new component_kind register against both layers — metadata in visual-editor registry + renderer in canvas widget-renderer registry.

Pattern application: when adding a new component kind, register at both layers from foundation (not retrofit). Missing canvas widget-renderer registration manifests as runtime "unknown widget kind" fallback rendering; missing visual-editor metadata registration manifests as authoring-time absence from component-kind palette. Both gaps surface reactively rather than at registration time.

Cross-reference: DECISIONS.md 2026-05-26 — Shared-dispatcher-multiple-authoring-surfaces canon (same architectural pattern at dispatcher altitude); DECISIONS.md 2026-05-26 — WYSIWYG discipline as canvas-layout-model constraint (relevant when canvas widget-renderer must match authoring-time visual representation).
```

---

# End of Phase 2 drafted entries

**Accounting:**
- Phase 2.A: 35 DECISIONS.md entries (Pass 1: 4 + Pass 2: 7 + Pass 3: 10 + Pass 4: 11 + Pass 5: 3)
- Phase 2.B: 10 canon-doc edits across 5 canon docs (Pass 2.B.1: 5 edits / Pass 2.B.2: 5 edits)
- Total: 45 canon additions / ~22,200 words

**Candidate accounting (92 Phase 0 candidates):**
- 77 DECISIONS.md filed across 35 entries
- 11 canon-doc EXTENDS IDs folded into 10 edits (C5+C6 merged)
- 3 CULL (C28, C56, C57)
- 1 carry-forward (C42 → September-decision arc per DECISIONS.md 2026-05-26 — Deferral-tracking meta-pattern)

**Staging consumption:** Sonnet reads this artifact at Phase 2 staging time + applies edits to target canon docs at verified placement points + normalizes "Entry N" internal references to canonical "DECISIONS.md 2026-05-26 — `<title>`" shape + writes STATE.md close note (Sonnet permission scope) + drafts commit message.

