# Monitor → daily note: supersession inventory

**Date:** 2026-09-04 · **HEAD:** `9306654d` · **Read-only — no code changed.**

Pre-flight for the 2026-09-04 DECISIONS entries replacing the Monitor primitive
with a per-user, per-day note surface. Establishes what the decision actually
supersedes, and what it does not.

Existence-first per CLAUDE.md §12: *what depends on Monitor-as-dashboard, by any
mechanism, exhaustively* — not a confirmation of a supplied list.

---

## 1. CLAUDE.md §1a — nine dependent sites

§1a spans lines 57–250. The operator's inventory named four. All nine below were
read verbatim from the file.

| Site | The dependent text |
|---|---|
| Section title | "Monitor through hubs. Act through the command bar." |
| MODE 1 | "Widgets are the unit of monitoring"; "should know everything they need to know for their day without clicking anything" |
| Decision Framework Q1 | "If yes → it belongs in a hub dashboard widget"; "The user should see it when they open their hub" |
| "If a feature is both" | "Put a summary widget on the hub" |
| "A feature is INCOMPLETE if" | "It has no command bar workflow or hub widget entry point" |
| "A feature is COMPLETE if" | "Monitoring aspects surface in the appropriate hub" |
| Rule 2 | "Every metric, status, or alert that users need to notice must have a hub widget representation" |
| Rule 3 | "Which hub(s) get a widget for this feature" — leg one of four |
| Rule 4 | "The hub widget if the feature has a monitoring aspect" |

⚠️ **Rule 3 becomes unsatisfiable, not shorter.** It closes "If you cannot
specify all four, the feature is not fully designed." Deleting leg one leaves a
four-leg gate with three legs available, so every future feature fails it as
written. The gate must be explicitly suspended, not silently shortened — a
stated gate that everyone ignores is worse than no gate.

---

## 2. PLATFORM_ARCHITECTURE.md — a primitive, not a framing line

Headings: `## 3. Spaces (Monitor)` · `3.1 The Monitor Reframe` · `3.2 What
Monitor Should Actually Do` · `3.3 The Pulse Surface (per Space)` · `3.4
Components of the Monitor Surface` · `8.2 Naming of the Pulse Surface` · `8.4
Monitor's Default Landing per Space`.

### ⚠️ §3 is not uniformly superseded

**§3.2 survives intact.** It lists five obligations for Monitor — surface what's
actionable now; show ambient state; highlight what's changed; provide go-deeper
paths; adapt to context — and closes "A static dashboard list does maybe 30% of
#4 and nothing else."

§3.2 is already an indictment of the dashboard, written from inside the
dashboard-era document. It survives the transition on its own terms and is the
test the note surface must pass. The note does 1/3/5 in prose, 2 in the standing
set, 4 in peeks and Focus entrances.

**What is superseded** is §3.1's "Each Space has one composed Monitor surface
(the Pulse / Home), not a sidebar list of destinations" — the per-Space scoping —
and §3.3/§3.4's layered widget-composition execution.

The distinction is: the Monitor **thesis** stands; the Pulse **execution** is
superseded.

---

## 3. Pulse is shipped, and it is the front door

This is the finding that changes the decision's shape from a documentation edit
to a surface replacement.

- **115 code files** reference Pulse (excluding `node_modules`).
- **`/home` IS Pulse.** `frontend/src/components/root-redirect.tsx:37-38`
  records the canon it honors: authenticated tenant users land on `/home`
  (Pulse) on app entry.
- **Backend:** `app/models/pulse_signal.py`, `app/api/routes/pulse.py`, and
  `app/services/tasks/subscribers/pulse_subscriber.py`.
- **Frontend surface:** `PulseSurface.tsx`, `PulseLayer.tsx`, `PulsePiece.tsx`,
  `PulseFirstLoginBanner.tsx`, tier-dispatch and empty-slot-filter tests,
  `viewport-fit-constants.ts`, `utils/layer-row-count.ts`.
- **10 widgets** in `frontend/src/components/widgets/foundation/`.

### `pulse-widget` disposition is a migration, not a ruling

The kind is carried by a **database CHECK constraint** at
`backend/app/models/component_configuration.py:111`, and mirrored in
`backend/app/api/routes/admin/visual_editor_components.py:53`, the frontend
registry types, the runtime-host edit-mode context, and the Studio inspector.
Retiring it is schema work.

### The task substrate already emits the fragment-regeneration stream

`pulse_subscriber.py` is one of six task-lifecycle subscribers. Its docstring:
it invalidates the Pulse composition cache for the affected user on
`task_created`, `task_assigned`, `task_status_changed`. Invalidation is
best-effort and sync; it never raises.

This is the material-change stream that per-fragment incremental regeneration
needs. It exists and is wired. The decision should adopt it rather than describe
building one.

---

## 4. Documentation footprint

~750 real `Pulse` references across 13 root documents: BRIDGEABLE_MASTER 368 ·
AESTHETIC_ARC 132 · ARCHITECTURE_MIGRATION 107 · SPACES_PLAN 65 ·
PLATFORM_ARCHITECTURE 30 · PLATFORM_PRODUCT_PRINCIPLES 29 · STATE 18 ·
CLAUDE 7 · PLUGIN_CONTRACTS 5 · PLATFORM_INTERACTION_MODEL 6 · DECISIONS 3 ·
PLATFORM_QUALITY_BAR 1 · PLATFORM_DESIGN_THESIS 1.

**Supersession marks live canon, never logs.** AESTHETIC_ARC and
ARCHITECTURE_MIGRATION are historical records of what was decided when; marking
them would corrupt them as evidence. BRIDGEABLE_MASTER is already second-order
superseded per CLAUDE.md:277.

---

## 5. ⚠️ The persistent-storage rule already existed, and did not hold

**`DECISIONS.md:474` — "2026-05-27 — Persistent-storage discipline for
investigation deliverables."** Its rule: investigation deliverables ship to
`docs/investigations/`, not `/tmp/`. Its rationale cites the **May 24, 2026
`/tmp/` rotation loss that wiped ~35,500 words** across three investigations.

The September 2026 campaign then wrote four deliverables to `/tmp/` and lost
them at the 2026-09-03 boot. **This was the second loss, under a rule written in
response to the first.**

The rule was in canon and out of force, and the filing location predicts it:
CLAUDE.md's read order says "**DECISIONS.md — only when you need to understand
WHY** something is the way it is." A binding constraint on where work is written
was filed in the document the read order tells you not to open. It is a *what*
living in the *why* file.

The 2026-09-03 landing of the same rule into CLAUDE.md §12 is the correction,
arrived at independently and four months late. It works because CLAUDE.md is
read every session.

**Generalization worth canonizing:** a rule filed where it will not be read is
not in force, however well written. Constraints belong in the always-read
document; rationale belongs in the log. When a rule is violated by someone who
would have followed it, check where it was filed before concluding anything
about discipline.

---

## 6. Two claims that did not survive checking

### The dangling citation does not exist

The operator reported that the 2026-05-13 Spaces entry cites
`/tmp/studio_shell_investigation_findings.md §2`, that the file is gone, and
that append-only canon therefore holds a dead reference needing a note.

**All three are false.**

- `grep "studio_shell" DECISIONS.md` → **0 hits.**
- The only `/tmp/` strings in DECISIONS.md are lines 476/478/480, inside the
  2026-05-27 rule entry that *prohibits* `/tmp/`.
- The actual entry (`DECISIONS.md:44`) cites
  **`docs/investigations/2026-05-13-studio-shell.md §2`** — a repo path.
- **That file exists.**

The citation resolves. Writing the proposed explanatory note would have placed a
false statement into append-only canon about a defect that was never there —
the more costly direction, since a note explaining why a live reference is dead
would itself need later correction.

### AESTHETIC_ARC's 132 references are real

Checked before reporting: of 179 raw case-insensitive `pulse` matches, only 6
are `animate-pulse` / `pulsing`. The remaining 132 are Pulse-the-surface. Absent
the check this would have been a false-presence report in a design document.

---

## 7. Method note — a count that measured the wrong unit

The first pass reported 289 Pulse references in BRIDGEABLE_MASTER. The real
figure is 368. `grep -c` counts **matching lines**, not occurrences, and a line
carrying three references counts once.

This is adjacent to *enumeration defeated by presentation* but distinct: there
the members are hidden by a transform, here the unit of measurement is silently
wrong. The failure is invisible because the number is well-formed, plausible,
and in the right order of magnitude — nothing about 289 looks incorrect.

Both this and the substring check were caught before publication.

Proposed for methodology canon at arc close: **the count that measured the wrong
unit.** Before reporting a count, state what one counted thing is, and confirm
the tool counts that.
