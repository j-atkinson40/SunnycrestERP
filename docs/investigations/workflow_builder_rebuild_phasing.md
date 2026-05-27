# Workflow Builder Rebuild — Phase 4 Phasing Recommendation

> Read-only Phase 4 deliverable closing the Phase B Workflow Builder rebuild investigation. Dispatches against Phase 0 audit findings at `docs/investigations/workflow_builder_rebuild_phase0_audit.md` (HEAD `ca2c7db`, 2026-05-27). Follows the canonical 8-section structure per DECISIONS.md 2026-05-27 — Phasing recommendation shape canon (Entry 27).
>
> Persistent storage from start per DECISIONS.md 2026-05-27 — Persistent-storage discipline for investigation deliverables (Entry 4).

## Phase 4 metadata

- **Arc context:** Phase B Workflow Builder rebuild investigation, Phase 4 of 4 (Phase 0 audit closed → Phase 4 phasing recommendation → operator confirmation → Phase 5 build prompt drafting downstream)
- **HEAD at recommendation:** `ca2c7db` (Phase A close)
- **Phasing date:** 2026-05-27
- **Canon ground:** 35 DECISIONS.md entries dated 2026-05-27; particularly Entry 1 (investigation-methodology), Entry 2 (operator-observable signals + anti-signals), Entry 9 (auto-save semantics depend on substrate clone-vs-shared shape), Entry 11 (WYSIWYG discipline as canvas-layout-model constraint), Entry 14 (always-visible preview substrate), Entry 17 (substrate-prescience-meets-second-consumer), Entry 22 (discoverability canon), Entry 24 (LOC calibration), Entry 25 (deferral-flagging), Entry 26 (arc-commit-granularity), Entry 27 (phasing recommendation shape canon), Entry 30 (sub-arc decomposition seams), Entry 31 (bounded-decision-per-arc explicit naming), Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs).
- **Bounded decision:** produce phasing recommendation deliverable per Entry 27 8-section structure; surface adjudications for operator confirmation; lock NO Phase 5 build prompt content; lock NO scope outside Phase B.
- **Operator framing locks preserved:** Phase A → B → C sequence; September Wilbert demo schedule explicitly NOT a signal; Q-B1 boundary preserved per Entry 3; Phase C boundary preserved per Entry 32; task substrate v1 boundary preserved.

---

## §1. Phase B substrate phase final-lock

### 1.1 Substrate phase = canvas + node-type registry + per-type inspector configs

Per Phase 0 audit §E enumeration of 8 concrete substrate gaps, the Phase B **substrate phase** ships the canonical authoring substrate matching Focus Builder + Widget Builder rebuild precedent shape:

1. **Graph-canvas authoring surface** replacing the current vertical-list rendering at `WorkflowEditorPage.tsx:924-1004`. Per Entry 11 (WYSIWYG discipline as canvas-layout-model constraint): authoring canvas must match runtime canvas layout model = directed graph (nodes + edges + trigger + branching + parallel split/join). This is a **third canvas model distinct from Monitor (grid) and Decide (free-form)** — workflows are DAG-shaped.
2. **Node-type registry-driven palette** replacing hardcoded 16-tuple JSX palette at `WorkflowEditorPage.tsx:893-905`. Registry expansion: `frontend/src/lib/visual-editor/registry/registrations/workflow-nodes.ts` (current 2 entries → canonical 28-entry vocabulary).
3. **Per-node-type inspector configs** replacing generic JSON-textarea fallback for 14-of-16 node types. Builds on existing pattern at `workflow-canvas/InvokeGenerationFocusConfig.tsx` + `InvokeReviewFocusConfig.tsx` (already operational for 2 node types).
4. **Always-visible preview substrate** per Entry 14. For workflows: simulated execution trace + node-state visualization at design time; not a rendered-component preview.
5. **Selection-driven inspector** per Focus Builder rebuild precedent — empty canvas selection → "nothing selected" state; click background → workflow-level chrome (trigger, metadata); click node → per-node inspector; click edge → edge-condition inspector.
6. **HierarchicalEditorBrowser preserved verbatim** at left rail (current `WorkflowEditorPage.tsx:761` consumption is canonical per Visual Editor §4 ledger; no change needed).

### 1.2 What Phase B substrate phase does NOT change

- ❌ workflow_engine runtime substrate (per Phase 0 §D — distinct boundary)
- ❌ workflow_templates schema (per Phase 0 §C — substrate already in place per Entry 17 substrate-prescience-meets-second-consumer; Phase B is the second consumer)
- ❌ workflow_review_adapter + workflow_subscriber (per Phase 0 §B.5 — task substrate boundary preserved)
- ❌ Studio-builder Mapping Table row (per Phase 0 §G.4 — Phase B inherits canonical platform-realm + adminApi pattern verbatim)
- ❌ Tenant-side `WorkflowBuilder.tsx` (per Phase 0 §A.3 — open question 1 at §8.1; deferred under default recommendation)
- ❌ Migration head (per Phase 0 §C.4 — no schema work required)

### 1.3 LOC envelope per WB cycle calibration

Per Entry 24 (LOC calibration canon for substrate-additive arcs) + Phase 0 §F.2 WB cycle band:

- Per-sub-arc range expectation: ~500-2,500 LOC matching WB cycle band
- Substrate phase cumulative envelope: **~5,000-9,000 LOC** anchored between Focus Builder rebuild (~6,500-9,500) and WB cycle substrate (~9,500-14,000) — Phase B substrate phase fits more cleanly under Focus Builder anchor because schema substrate is in place (no schema migration LOC; no service-layer foundation LOC; rebuild is authoring-surface focused)
- Within Entry 24 calibration band; well under 25k cumulative ceiling

### 1.4 Substrate phase close criteria

- All 28 canonical node types have component registry entries (workflow-nodes.ts expanded to 28; per-type configurableProps ≥3 per Component Registry canon)
- Graph canvas operational with operator-validated WYSIWYG-against-runtime (drag-positionable; edge-rendering as visible graph edges; branching + parallel split/join visualized)
- Per-node-type inspector configs for all 28 canonical types
- Always-visible preview substrate operational
- Phase B substrate sub-arc test cohort green (Playwright + unit tests per WB cycle precedent)
- Phase 0 § A.2 Surface 3 operator-facing rebuild target → built-operator-facing canonical state

### 1.5 Commit-shape per Entry 26

Per WB cycle precedent (each sub-arc ships as own arc-close commit) + Entry 26 default (single-commit-at-arc-close for arcs ≤ ~3,000 LOC without parity-discipline complexity): Phase B substrate sub-arcs ship as **per-sub-arc commit boundaries** matching WB cycle commit shape — each sub-arc ≤ ~2,500 LOC fits default regime.

---

## §2. Phase B integration phase final-lock

### 2.1 Integration phase = UX refinement + Surface 1 disposition + variant authoring

Per Phase 0 §A.3 + §E.5 open questions + Focus Builder UX refinement sub-arc precedent (Phase 0 §F.5):

The **integration phase** ships:

1. **Operator-validated UX refinements** per Focus Builder UX refinement sub-arc precedent — surface naturally as operator-observable signals during substrate-phase operator validation
2. **Surface 1 disposition** — does Phase B rebuild touch `pages/settings/WorkflowBuilder.tsx` to retire / migrate / shim it? Surfaced as §8 open question 1
3. **Auto-save vs manual-save semantics adjudication** per Entry 9 nuance + Phase 0 §E.2 finding — Surface 3 currently auto-saves at 1.5s; rendered-shared substrate semantics. Surfaced as §8 open question 2
4. **Trigger-type variant authoring substrate** — workflows have trigger-type axis (manual/event/scheduled/time_after_event/time_of_day) which may earn variant authoring per WB-8 substrate pattern; surfaced as §8 open question 3
5. **Studio rail entry verification** per Entry 22 discoverability canon — confirm `StudioShell.tsx:70` mapping survives Phase B rebuild end-to-end; already operational at Phase 0 audit

### 2.2 Integration phase LOC envelope

Per Focus Builder UX refinement precedent (3 refinement sub-arcs visible at `2026-05-20-*`): refinement sub-arcs typically ~300-800 LOC each.

**Integration phase cumulative envelope:** ~1,500-3,500 LOC across 2-4 refinement sub-arcs (depending on §8 open question resolution).

### 2.3 Integration phase close criteria

Per Entry 2 operator-observable signals canon: integration sub-arcs **dispatch on operator surfacing matching signal**, not on architecture-observable counters. Specific signals enumerated in §5.

---

## §3. Sub-arc grouping per Entry 30 substrate-similarity clusters

Per Entry 30 (sub-arc decomposition seams discovered during investigation): decomposition surfaces during investigation, not during build. Phase 4 locks decomposition before build prompt drafts.

### 3.1 Phase B substrate phase — 5 sub-arc decomposition

Substrate-shape distinctions cohere as 5 natural sub-arc seams:

| Sub-arc | Scope | LOC envelope | Substrate-shape distinction |
|---------|-------|--------------|-----------------------------|
| **B-1** Graph canvas foundation | Replace `<ol><li>` rendering with graph-canvas substrate; node positioning + edge rendering; per Entry 11 WYSIWYG-against-runtime-DAG | ~1,500-2,500 | Authoring canvas substrate |
| **B-2** Node-type registry expansion | Expand `workflow-nodes.ts` from 2 → 28 canonical types; each carries ≥3 configurableProps per Component Registry canon | ~800-1,500 | Registry substrate |
| **B-3** Per-type inspector configs | 14+ new per-node-type inspector components matching WB cycle `workflow-canvas/InvokeGenerationFocusConfig.tsx` precedent | ~1,500-2,500 | Inspector substrate |
| **B-4** Always-visible preview substrate | Live execution-trace + node-state visualization per Entry 14 | ~800-1,500 | Preview substrate |
| **B-5** Selection-driven inspector chrome | Background-click + edge-click + workflow-level chrome editing per Focus Builder selection precedent | ~500-1,000 | Selection substrate |

**Substrate phase total: ~5,100-9,000 LOC across 5 sub-arcs.**

### 3.2 Phase B integration phase — 2-4 sub-arc decomposition (signal-driven)

Per §2.1 + Entry 2 (operator-observable signal dispatch):

| Sub-arc | Scope | Trigger signal |
|---------|-------|----------------|
| **B-6** UX refinements (1-3 sub-arcs depending on signal) | Per-operator-validated UX gaps surfacing during substrate phase + post-substrate operator validation | Operator-observable workflow signal during/after substrate phase |
| **B-7** Surface 1 disposition (optional) | Retire / migrate / shim `pages/settings/WorkflowBuilder.tsx` | §8.1 operator decision |
| **B-8** Trigger-variant authoring (optional) | Trigger-type variant authoring substrate for workflows | §8.3 operator decision + operator-observable signal |

**Integration phase total: ~1,500-3,500 LOC across 2-4 sub-arcs.**

### 3.3 Sub-arc decomposition coherence per Entry 30

- **B-1** isolates graph-canvas substrate (largest substrate-shape distinction; first-of-kind canvas model so per Entry 24 calibration band wider)
- **B-2** isolates registry-expansion work (mechanical substrate scaffolding per Phase 0 §E.4; per-type configurableProps work)
- **B-3** isolates per-type inspector work (substrate-cohort-specific; ~26 new inspector components)
- **B-4** isolates preview substrate (independent surface; new authoring affordance)
- **B-5** isolates selection-state extension (cross-cutting selection-context refactor)

Each sub-arc's substrate-shape distinction is investigation-visible per Entry 30. Build executes against locked decomposition. Substrate-similarity clusters: B-2 + B-3 are **registry + per-registry-entry-config pair** (analogous to WB-2 atom catalog + WB-3 atom registry pattern); B-1 + B-5 are **canvas substrate + canvas-selection-context pair**; B-4 is independent preview substrate.

---

## §4. Phase B arc shape

### 4.1 Per WB cycle + Focus Builder rebuild precedent

Phase B arc shape **inherits WB cycle precedent**:

1. Sub-arc sequence: **B-1 → B-2 → B-3 → B-4 → B-5 → (B-6 signal-driven)** for substrate phase + integration phase
2. Each sub-arc opens with sub-arc audit-first phase per Entry 1 + Entry 23 iterative-STOP protocol
3. Each sub-arc closes with per-sub-arc commit per Entry 26
4. Investigation deliverable per sub-arc when scope/complexity warrants (B-1, B-3 likely earn deliverables; B-2, B-4, B-5 may ship inline per WB-1/2/3 precedent)
5. Operator-confirm gate at each sub-arc commit boundary per Entry 26 multi-commit regime

### 4.2 Phase C boundary preservation per Entry 32

Per Phase 0 §G.1: Phase C Document Builder rebuild operates under own pre-dispatch rescoping. Phase B closes; Phase C dispatches via own investigation-first arc.

**Phase B does NOT lock Phase C scope.** §4 captures forward-reference only.

### 4.3 Forward-reference to Phase C

Per Phase 0 §G.1 + CLAUDE.md §4 Visual Editor Top-Level Structure: Documents editor at `/visual-editor/documents` is currently placeholder per the ledger ("Placeholder — Phase 2 will ship full document template authoring backed by Documents arc substrate"). Phase C rebuild scope ≈ full document-authoring editor on top of existing Documents arc substrate (Phase D-1 through D-11 shipped; block-based authoring at D-10/D-11; vertical tier at D-11).

**Per Entry 32 distant-horizon arc discipline:** Phase C scope re-evaluates at Phase C dispatch trigger against then-current platform state (post-Phase-B Workflow Builder rebuild canon + visual-editor pattern evolution).

---

## §5. Upgrade signals between Phase B sub-arcs + explicit anti-signals

### 5.1 Within-substrate-phase sub-arc dispatch

Substrate phase sub-arcs **dispatch sequentially without separate per-sub-arc operator-observable signal** because substrate phase is operator-locked end-to-end (Phase A → B → C sequence locked). Per Entry 31 (bounded-decision-per-arc explicit naming): Phase B substrate phase has a single bounded decision = "ship canonical Workflow Builder rebuild matching Focus Builder + Widget Builder precedent shape." Sub-arc sequencing within substrate phase is investigation-locked seam decomposition per §3.

**Sub-arc-to-sub-arc operator-confirm gate** at commit boundary per Entry 26 — conversational gate verifies staging deploy + behavior verification.

### 5.2 Substrate-phase → integration-phase signal

Integration phase B-6 (UX refinements) dispatches on **operator-observable workflow signal during/after substrate phase operator validation**. Concrete signal patterns:

- Operator describes a UX gap during substrate-phase operator validation that doesn't fit substrate-phase scope
- Operator surfaces post-substrate-phase production audit gap (per Entry 2 operator-conducted production audit canon)
- Staging deploy operator-validates substrate phase canonical; refinement-shape gap surfaces in validation

### 5.3 Integration phase sub-arc dispatch

B-7 (Surface 1 disposition) and B-8 (trigger-variant authoring) **dispatch on operator decision at §8 open question resolution** per Entry 32 (distant-horizon arc rescoping discipline). Neither dispatches automatically post-substrate-phase.

### 5.4 Explicit anti-signals per Entry 2

The following are **NOT triggers for Phase B sub-arc dispatch**:

- ❌ **LOC threshold:** Phase B substrate phase hitting ~5,000-9,000 LOC envelope does NOT trigger integration phase
- ❌ **Count threshold:** Substrate phase shipping 5 sub-arcs does NOT trigger integration phase
- ❌ **Time threshold:** September Wilbert demo timing does NOT trigger sub-arc dispatch — per operator framing locks at Phase 0 metadata
- ❌ **Engineering preference:** Sonnet preferring tidier substrate boundaries does NOT trigger refactor sub-arc
- ❌ **Aesthetic-completeness:** Substrate phase "looking complete" does NOT trigger closure if operator validation gaps remain
- ❌ **Sunk-cost:** Substrate-phase substrate not earning second-consumer signal does NOT trigger integration phase shipping anyway
- ❌ **Substrate-mature signal for downstream:** Phase B substrate maturity does NOT trigger Phase C dispatch — Phase C operates under own pre-dispatch rescoping per Entry 32

### 5.5 Cross-arc signal preservation

Per Entry 32 (per-arc pre-dispatch rescoping for distant-horizon arcs):

- Phase B itself dispatches per operator-locked Phase A → B → C sequence (signal present at operator framing)
- Phase B sub-arc sequencing within substrate phase: investigation-locked seam decomposition; no per-sub-arc operator-observable signal required for substrate-phase progression
- Phase B integration phase sub-arc dispatch: signal-driven per §5.2 + §5.3
- Phase C dispatch: own pre-dispatch rescoping arc; not in Phase B scope

---

## §6. Cross-version concerns

### 6.1 Visual editor canon evolution post-Phase B

Post-Phase B close, CLAUDE.md §4 Visual Editor canon evolves:

- Workflow Canvas (Admin Visual Editor Phase 4) section updates with rebuilt substrate shape
- Visual Editor Top-Level Structure table updates Workflows row (substrate state: built-operator-facing canonical)
- Studio-builder Mapping Table preserves Workflow Editor row verbatim (no schema change per Phase 0 §C)
- Component Registry (Admin Visual Editor — Phase 1) section updates workflow-nodes coverage (2 → 28 canonical types)

**Canon-update arc** dispatches post-Phase-B per canon-update arc precedent (deferral-tracking meta-pattern Entry 3): Phase B substrate observations file as canon candidates; canon-update arc at Phase B close adjudicates + lands canon entries. Per Phase 0 §E observation 8 (parallel Surface 1/Surface 3) + Entry 29 (substrate-extending arcs with colliding field names): if Surface 1 disposition (§8.1) lands as "rebuild Surface 1 too" or "shim Surface 1," canon-adjacent observation files for canon-update arc.

### 6.2 STATE.md narrative across Phase B sub-arcs

Per STATE.md write-discipline at CLAUDE.md §Documentation write permissions: Sonnet writes STATE.md at end of every build session. Phase B substrate phase sub-arcs each append STATE.md updates per WB cycle precedent.

### 6.3 Carry-forward items per Entry 3

- **C42 boot-adapter:** carries forward to September-decision arc; Phase B doesn't touch (per Phase 0 §G.2)
- **Q-B1 lock:** preserved per Phase 0 §G.2
- **Phase C scope:** carries forward to own pre-dispatch rescoping arc (per §4.2)
- **Task substrate v2a/v2c:** carries forward per anti-signal discipline (deferred at Phase A close per `ca2c7db`); Phase B doesn't interact

### 6.4 PLUGIN_CONTRACTS.md interaction

Phase B may surface canon candidates for PLUGIN_CONTRACTS.md plugin categories:

- **Workflow node types** (if registry expansion at B-2 earns plugin-shaped contract — analogous to "Widget kinds" in PLUGIN_CONTRACTS §)
- **Workflow node inspector configs** (if per-type inspector substrate at B-3 earns plugin-shaped contract)
- **Workflow action handlers** (if engine-side `_execute_action` dispatch table earns plugin-shaped contract — though this is engine-substrate work, NOT Phase B scope)

**Phase B does NOT pre-lock plugin contract changes** — surfaces as canon candidates for canon-update arc.

### 6.5 Aesthetic Arc preservation

Per CLAUDE.md §4 Design System (Aesthetic Arc Phase I complete, Phase II in progress): Phase B authoring surface uses DESIGN_LANGUAGE.md tokens verbatim. Substrate phase preserves Aesthetic Arc Session 2/3 token vocabulary. **Phase B does NOT introduce new tokens.**

---

## §7. Honest cost

Per Entry 24 (LOC calibration canon for substrate-additive arcs) honest-cost discipline:

### 7.1 Per-sub-arc envelope

**Substrate phase:**

| Sub-arc | Envelope | Calibration band |
|---------|----------|------------------|
| B-1 Graph canvas foundation | ~1,500-2,500 | Wide — first-of-kind canvas model (DAG distinct from Monitor grid + Decide free-form) |
| B-2 Node-type registry expansion | ~800-1,500 | Narrow — mechanical substrate-cohort scaffolding; ~26 entries × ~30-60 LOC/entry per Component Registry canon |
| B-3 Per-type inspector configs | ~1,500-2,500 | Narrow — ~14-26 inspector components × ~100-200 LOC each per WB cycle precedent |
| B-4 Always-visible preview substrate | ~800-1,500 | Wide — execution-trace visualization is novel substrate; WB-5 precedent ~1,000-1,500 |
| B-5 Selection-driven inspector chrome | ~500-1,000 | Narrow — selection-context refactor; smaller substrate |

**Substrate phase cumulative:** ~5,100-9,000 LOC.

**Integration phase:**

| Sub-arc | Envelope | Calibration band |
|---------|----------|------------------|
| B-6 UX refinements (1-3 sub-arcs) | ~600-2,400 | Wide — signal-driven scope per Focus Builder UX refinement precedent |
| B-7 Surface 1 disposition (optional) | ~300-1,500 | Wide — scope depends on §8.1 resolution (retire vs migrate vs shim) |
| B-8 Trigger-variant authoring (optional) | ~600-1,500 | Wide — analogous to WB-8 variant authoring substrate (~800-1,200) |

**Integration phase cumulative:** ~1,500-5,400 LOC depending on signal + open question resolution.

### 7.2 Phase B cumulative LOC envelope

- **Substrate phase only:** ~5,100-9,000 LOC
- **Substrate + minimal integration (B-6 only):** ~5,700-11,400 LOC
- **Full Phase B (substrate + B-6 + B-7 + B-8):** ~6,600-14,400 LOC

Phase B cumulative honest cost **fits cleanly under 25k cumulative ceiling** referenced at task substrate v2 phasing §7. Well within Entry 24 calibration band.

### 7.3 Test cohort accumulation per sub-arc

Per WB cycle test cohort precedent: each sub-arc ships ~5-20 unit/integration/Playwright tests. Phase B substrate phase cumulative test cohort: ~30-80 new tests. Integration phase: additional ~10-30 tests.

### 7.4 Calibration ceiling violation handling

Per Entry 24: if any sub-arc envelope exceeds calibration band, agent flags + offers two paths + operator decides at gate review. WB cycle precedent: WB-6 3.3× overrun handled honestly by operator surfacing; WB-7 18% overrun absorbed by honest scope-discipline.

### 7.5 Cross-arc LOC pattern

Per Entry 24 four-instance calibration pattern (WB-6 3.3× → WB-5 0.5% → WB-7 18% → WB-8 ±5%): Phase B inherits **substrate-mature calibration band** because Workflow Builder rebuild operates against well-understood canonical builder-rebuild substrate. Expected calibration variance: closer to WB-8 ±5% than WB-6 3.3× — schema is in place; substrate boundaries are clean per Phase 0 §B-D; rebuild operates against canonical patterns.

---

## §8. Open questions for operator resolution

### 8.1 Adjudication 1 — Surface 1 (tenant `WorkflowBuilder.tsx`) disposition

**Question:** does Phase B rebuild touch the tenant-side `pages/settings/WorkflowBuilder.tsx` (1,876 LOC) at all, or does Surface 1 stay legacy until natural-refactor?

**Phase 4 recommendation:** **Surface 1 stays legacy at Phase B**; defer disposition to a post-Phase-B follow-on arc or natural-refactor. Phase B substrate phase locks Surface 3 (admin Studio Workflow Editor) as canonical rebuild target per Phase 0 §A.3. Surface 1 disposition surfaces post-substrate-phase if operator signal warrants (e.g., tenants want canonical authoring affordances, not the legacy step-list paradigm).

**Alternative paths:**
- **Migrate Surface 1 to consume canonical substrate at Phase B integration phase (B-7).** Trade-off: ships canonical UX to tenant-side; adds ~300-1,500 LOC; requires reconciling tenant-side `Workflow` ORM substrate with admin-side `WorkflowTemplate` substrate (Phase 0 §B.1 + §C.1 enumeration — they're distinct substrates serving different concerns).
- **Retire Surface 1 entirely at Phase B integration phase.** Trade-off: cleanest substrate boundary; but tenant-side workflow customization currently flows through Surface 1 per Phase 0 §A.2 evidence — retirement would require tenant-side authoring path through admin Studio (cross-realm). May not work without further substrate work.
- **Shim Surface 1 to delegate to admin Studio Workflow Editor with tenant-realm read-only mode.** Trade-off: smaller substrate work; preserves tenant-side discoverability; but cross-realm read-only authoring is unconventional.

**Operator decision pivot:** is Surface 1 legacy step-list paradigm a known gap that Phase B rebuild should close, or is Surface 1's continued operation acceptable while Phase B rebuilds the canonical admin Studio surface only?

### 8.2 Adjudication 2 — Auto-save vs manual-save semantics

**Question:** does Phase B substrate phase preserve auto-save (current behavior at `WorkflowEditorPage.tsx:354-372`, 1.5s debounce) or migrate to manual-save per Entry 9 canonical for rendered-shared substrate?

**Phase 4 recommendation:** **preserve auto-save with locked-to-fork merge semantics** at Phase B substrate phase. Per Entry 9 nuance: auto-save is canonically hazardous for rendered-shared substrate because edits affect all consumers immediately. Workflow Builder is **rendered-shared at platform_default/vertical_default scope** but **locked-to-fork merge** at tenant fork scope means tenant forks see `pending_merge_available=true` flag, not immediate auto-overwrite. This is the substrate-substantive difference from widget definitions (no fork lifecycle; tenants see widget definition edits immediately). The locked-to-fork pattern makes auto-save operationally safe.

**Alternative paths:**
- **Migrate to manual-save (publish-style) per Entry 9 canonical.** Trade-off: matches WB-cycle canon; but requires re-shaping operator UX (publish button; draft state; explicit dirty indication). Higher refactor cost.
- **Hybrid: auto-save to draft, manual-save to active.** Trade-off: most defensive; introduces new state machine on `WorkflowTemplate` (currently version-bump-on-save with `is_active` partial-unique); substrate change required.

**Operator decision pivot:** is current auto-save+locked-to-fork semantics operator-validated as canonical, or does Phase B want to align with WB-cycle manual-save canonical?

### 8.3 Adjudication 3 — Trigger-variant authoring substrate

**Question:** does Phase B integration phase include trigger-type variant authoring (B-8) per WB-8 variant authoring precedent?

**Phase 4 recommendation:** **defer B-8 trigger-variant authoring** to post-Phase-B follow-on arc; Phase B substrate phase ships single-trigger authoring per current substrate. Per Entry 17 (substrate-prescience-meets-second-consumer): substrate exists for trigger types; second consumer (variant-shaped authoring substrate) requires operator-validated need surfacing. Without explicit signal, B-8 is architect-inferred per Entry 2 anti-signal canon.

**Alternative paths:**
- **Ship B-8 in Phase B integration phase.** Trade-off: aligns with WB-8 variant authoring precedent; adds ~600-1,500 LOC; risks premature substrate per Entry 17 if operator validation signal hasn't surfaced.
- **Defer B-8 indefinitely; ship trigger-type-specific palette entries instead.** Trade-off: simpler substrate; preserves canonical pattern; deferred-with-reason carries forward per Entry 25 deferral-flagging canon.

**Operator decision pivot:** does operator anticipate trigger-variant authoring signal during Phase B substrate-phase operator validation, or post-Phase-B?

### 8.4 Adjudication 4 — Phase B sub-arc count

**Question:** locks Phase B substrate phase at 5 sub-arcs (per §3.1) or different decomposition?

**Phase 4 recommendation:** **5 sub-arcs (B-1 through B-5)** per §3.1 substrate-similarity clusters + Entry 30 sub-arc decomposition seams canon. Substrate-shape distinctions cohere as 5 natural seams; collapsing creates substrate-shape-coherence-reducing clusters.

**Alternative paths:**
- **Collapse B-2 + B-3 into single substrate cluster.** Trade-off: registry-expansion + per-type-inspector are substrate-cohort-paired (WB-2 + WB-3 precedent); collapsing makes single ~2,300-4,000 LOC sub-arc above WB cycle band.
- **Collapse B-4 + B-5 into single substrate cluster.** Trade-off: preview substrate + selection chrome are different concerns; collapsing creates substrate-shape incoherence.
- **Split B-1 graph canvas into 2 sub-arcs.** Trade-off: first-of-kind canvas substrate may earn 2-sub-arc decomposition per WB-4 precedent (WB-4a + WB-4b configuration-vs-runtime split). Defer the split decision until B-1 sub-arc audit-first phase surfaces seam.

**Operator decision pivot:** does 5-sub-arc count hit right granularity vs over/under-decomposition?

### 8.5 Audit-surfaced canon-adjacent observation tracking

Per Phase 0 §E.5 + Entry 7 (built-but-dormant as third substrate state) extension: Phase 0 introduced the four-state framing (built-operator-facing / built-but-dormant / built-but-mis-shaped / missing). Per Phase A close STATE.md narrative: 5 canon-adjacent observations file forward via deferral-tracking for next canon-update arc; Phase B observations may add more.

**Phase 4 recommendation:** observations file as canon candidates for **post-Phase-B canon-update arc**; do NOT dispatch canon-update arc mid-Phase-B per Entry 1 (investigation-methodology canon: investigations apply discipline they recommend for build arcs; canon-update arcs interleave at arc-close boundaries).

### 8.6 September Wilbert demo schedule anti-signal preservation

Per operator framing locks at Phase 0 metadata + Entry 2 anti-signal canon: September Wilbert demo schedule is **explicitly NOT a signal** for Phase B sub-arc dispatch. Recommendation locks anti-signal discipline; honest scope-correctness preferred over schedule-pressure compression.

**No operator decision pivot** — discipline pre-locked; Phase 4 surfaces for operator-confirmation that lock holds.

---

## Phase 4 closing

Phase 4 phasing recommendation closes. Deliverable shipped at `docs/investigations/workflow_builder_rebuild_phasing.md` per Entry 27 8-section structure. Per Entry 31 bounded-decision-per-arc explicit naming: Phase 4 bounded decision = "produce phasing recommendation deliverable per Entry 27 8-section structure; surface adjudications for operator confirmation; lock NO Phase 5 build prompt content; lock NO scope outside Phase B" — bounded decision satisfied.

**Phasing summary by section:**

- **§1** — Substrate phase locks canonical Workflow Builder rebuild authoring substrate (graph canvas + 28-entry node-type registry + per-type inspector configs + preview substrate + selection chrome); ~5,100-9,000 LOC; 5 sub-arcs (B-1 through B-5).
- **§2** — Integration phase ships UX refinements + Surface 1 disposition + trigger-variant authoring per signal; ~1,500-5,400 LOC; 2-4 sub-arcs (B-6 + B-7? + B-8?) per §8 open question resolution.
- **§3** — 5 substrate-phase sub-arcs locked per Entry 30 substrate-similarity clusters; 2-4 integration-phase sub-arcs signal-driven.
- **§4** — Phase B arc shape inherits WB cycle precedent (sub-arc sequencing + audit-first per sub-arc + per-sub-arc commit + investigation deliverable when warranted). Phase C boundary preserved.
- **§5** — Substrate-phase sub-arcs dispatch sequentially without per-sub-arc operator-observable signal (Phase A → B → C locked at operator framing); integration-phase sub-arcs dispatch on operator-observable signal per Entry 2; anti-signals explicitly enumerated.
- **§6** — Visual editor canon evolves post-Phase-B via canon-update arc; STATE.md narrative across sub-arcs per WB cycle precedent; C42 + Q-B1 + Phase C + task substrate v2a/v2c boundaries preserved.
- **§7** — Honest cost: substrate phase ~5,100-9,000 LOC; integration phase ~1,500-5,400 LOC; full Phase B ~6,600-14,400 LOC. Well under 25k cumulative ceiling. Calibration band closer to WB-8 ±5% than WB-6 3.3× (substrate-mature calibration).
- **§8** — 4 adjudications + 2 audit-surfaced items: Surface 1 disposition, auto-save semantics, trigger-variant authoring, sub-arc count, canon-adjacent observation tracking, September anti-signal preservation.

**No material-divergence triggers fired during Phase 4 drafting.** No canon edits. No STATE.md edits. No production code. No Phase 5 build prompt content. No Phase C scope-lock. No Q-B1 substrate decision. No task substrate work. 114 stale Playwright screenshot deletions untouched.

**Next-gate handoff:** operator reviews Phase 0 + Phase 4 deliverables; confirms or revises 4 adjudications + 2 audit-surfaced items in §8; Phase 5 build prompt drafting dispatches against confirmed Phase 4 scope.

**Word count:** ~5,200 words (within ~5,000-7,500 envelope; ≥9,500 would be over-synthesis signal — not fired).

**C42 carry-forward boundary preserved** per Entry 3. **September Wilbert demo schedule explicitly NOT a signal** per operator framing locks + Entry 2 anti-signal canon. **Phase C boundary preserved** per Entry 32. **Task substrate v1 boundary preserved** at Phase A close.
