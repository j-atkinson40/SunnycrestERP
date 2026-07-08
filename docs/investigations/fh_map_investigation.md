# The Funeral-Home Map — Inventory + Stamping Plan

**Date:** 2026-07-07 · **HEAD at read:** `6be88982` · **Read-only — no build, no seed.**

The second vertical MoC, September/Wilbert-critical (Hopkins FH is the pilot).
The manufacturing map is the proven template; this document is the TRIAGEABLE
INVENTORY + the stamping plan. The operator triages §1, then the stamp build
dispatches. Places where stamping is harder than it should be are recorded as
platform findings (§6).

---

## 1. The FH artifact inventory (the triage list)

### 1a. Runtime workflows — 13 rows, grouped

All from dev (`bridgeable_dev`); the 12 vertical-scope rows are the April 17
FH vertical-defaults batch (same provenance as manufacturing's 12).

**(a) CURRENT + REAL — the bring-in candidates (9):**

| Workflow | id | Steps | Shape | Demo-critical? |
|---|---|---|---|---|
| First Call Intake | `wf_fh_first_call` | 5 | input·input·action·action·output | **YES — the case-comes-in opening** |
| Schedule Arrangement Conference | `wf_fh_schedule_arrangement` | 4 | input·input·action·output | **YES — the arrangement step** |
| Arrangement Scribe Processing | `wf_sys_scribe_processing` | 4 | action·action·input·action | **YES — the Scribe is the FH demo model** |
| 7-Day Aftercare Follow-Up | `wf_fh_aftercare_7day` | 3 | action·action·action | **YES** — note: this is the Phase 8d TRIAGE-migrated workflow (its runtime canonical path is the aftercare triage queue; the mirror is an inert snapshot like every other) |
| Plot Reservation | `wf_sys_plot_reservation` | 4 | input·input·action·action | **YES — the St. Mary's cross-tenant seam** |
| Send Family Info Form | `wf_tpl_fh_send_info_form` | 5 | input·input·action·action·output | completeness |
| Coordinate Removal | `wf_tpl_fh_removal_coordination` | 6 | input·input·input·action·action·output | completeness |
| Anniversary Acknowledgment | `wf_tpl_fh_anniversary_message` | 2 | action·action | completeness |
| Flag Pre-Need Policy | `wf_tpl_fh_preneed_flag` | 2 | action·action | completeness |

**(b) STALE / THIN — probably exclude (3):** zero-step shells (a mirror would
be an empty canvas; nothing to show):
- Obituary Draft Generation (`wf_fh_obituary_draft`, 0 steps)
- Insurance Assignment (`wf_tpl_fh_insurance_assignment`, 0 steps)
- EDRS Death Certificate Submission (`wf_tpl_fh_edrs_submission`, 0 steps)

If the operator wants any on the map, they need runtime steps authored first —
a separate decision, not a mirror.

**(c) DEMO-OVERLAPS / EXCLUDE (1):** `Process inbound email (Example — AI
Prompt)` — a tenant-scope R-6-era example row, not vertical content.
`seed_fh_demo` creates NO runtime workflows (verified) — no dedup pressure
from the Hopkins demo seed. The disinterment-intake rows that match FH-ish
name searches are manufacturing tenant copies — out of scope.

### 1b. Focus templates

| Artifact | State | Note |
|---|---|---|
| **Cemetery Triage** (`cemetery-triage`) | vertical_default @ manufacturing (home), **joined to funeral_home** via `focus_template_verticals` | **The V-1 log-skip's waiting ref** — already scoped to FH, pinned v2 with a declined v3 offer (the V-2 witness state). Surfaces the V-arc on the FH map for free. Demo-critical (it demos variations + offered updates). |
| **Funeral Scheduling** (`scheduling-fh`) | vertical_default @ **manufacturing** | **The F-1.1 tension, made concrete**: per operator-vertical canon this template lives on the MANUFACTURING side (Sunnycrest schedules funeral-vault deliveries). The FH map can (a) cross-vertical-ref it (resolver is id-based — works), (b) the operator creates an FH-OWNED scheduling variation from the Kanban core via the V-1 guided flow (~2 minutes, exercises the product, gives FH operators their own artifact), or (c) omit. **Recommend (b) — demo-critical** (it IS the "exercising the platform as a product" move this arc is about). |
| (nothing else Tier 2 FH) | — | The runtime funeral-scheduling Focus (`SchedulingFocusWithAccessories` + the seeded compositions) is the May visual-editor RUNTIME work — its map presence is via whichever Tier 2 template the operator picks above. |

### 1c. Documents + widgets — honestly thin

- **Documents:** one FH-scoped hit — `email.fh_aftercare_7day` (r40, the
  managed aftercare template; vertical NULL/platform). The document-composer's
  funeral content (D-10/11 blocks, funeral_cascade-adjacent templates) carries
  no `vertical='funeral_home'` rows on dev. **Verdict: the FH Documents card
  starts with the aftercare email ref (1 row) or stays empty-with-room.**
  Authoring FH document templates is post-map content work, not this arc.
- **Widgets:** `todays_services` ("Today's Services") is the one FH-shaped
  widget — a natural single ref for the Widgets card.

### 1d. The 6 core workflows — mechanism carries over, confirmed

The core mirrors (Month-End Close, AR Collections, Compliance Sync, Statement
Run, Expense Categorization, Training Expiry) are `platform_default`-scope
templates referenced BY id per-page — `seed_moc_manufacturing` queries them and
authors refs; the FH seed does the identical query. **Include-core canon holds
with zero new machinery.** (They're also the platform map's core card — three
homes, one artifact, by reference.)

---

## 2. The mirror question — verdict: parameterize, don't fork

**The FH set is INSIDE the clean-transform subset — confirmed, not assumed.**
All 9 with-steps workflows: linear (`condition_true/false_step_id` NULL
everywhere, consecutive-order edges), step_types ⊆ {input, action, output} ⊆
`VALID_NODE_TYPES`, config carries verbatim. Zero hand-translation needed.
The 3 zero-step shells are excluded by triage, not by transform limits.

**The manufacturing mirror seed is one refactor-lite away from serving both:**
`_mirror_one(db, name, runtime_scope, tmpl_scope, tmpl_vertical)` is already
fully parameterized; the only hardcodes are the module-level `VERTICAL` used in
the thin-task upsert and the TARGETS list. Plan: add a `task_vertical`
parameter + an `_FUNERAL_HOME` targets block to the SAME script (one pattern,
one file, both verticals — a future vertical appends a block).

**One correctness improvement while in there:** `_find_runtime` matches by
`(name, scope)` without a vertical filter — today's FH/MFG name sets are
disjoint so it's safe, but the parameterized version should add
`AND vertical = :v` so a future name collision can't cross-wire a mirror.

---

## 3. The map seed — `seed_moc_funeral_home` (the stamping plan's core)

Follows `seed_moc_manufacturing` verbatim in shape (find-or-update by
(scope, vertical, slug); sections refreshed, operator renames preserved):

- **Page:** `vertical_default` / `funeral_home` / slug `funeral-home-map`,
  title "Funeral Home".
- **Workflows card:** the triaged FH mirrors (resolve-or-skip by
  `mirrored_from_workflow_id`, query-built) + the 6 core mirrors (same query
  as manufacturing's).
- **Focuses card — QUERY-BUILT from the join table (the recommended
  mechanism):** rows = active `focus_templates` at vertical=funeral_home +
  every slug joined to funeral_home in `focus_template_verticals`. **This
  makes the V-1 log-skip real via the SEED, idempotently** — Cemetery Triage
  surfaces because its join row already exists, and every FUTURE variation
  scoped to FH lights this card with no seed edit. Cleaner than a hand-authored
  ref or re-running the variation's authoring path (which would need the
  flow's page-existence branch anyway). This mechanism is worth
  back-porting to `seed_moc_manufacturing`'s Focuses card in the same session
  (same query, replaces its hardcoded slug list — content-agnostic like the
  platform seed).
- **Widgets card:** `todays_services`. **Documents card:**
  `email.fh_aftercare_7day` (or empty-with-room per triage).
- **Thin task rows:** one per mirrored workflow via `upsert_task(vertical=
  "funeral_home", …)` — descriptive cells em-dash for operator enrichment.
  **The shared vocabulary is platform-scope (verified: all rows
  `platform_default`, including "Funeral Service Operations")** — FH tasks
  use it with zero vocabulary seeding.

Sizing: **ONE session** — the mirror-seed parameterization (+ FH targets
block + the vertical filter), the map seed, the mfg Focuses-card
back-port, tests (mirror fidelity for the FH set + page shape + the
join-table card query), and the witness. Mostly parameterizing proven
scripts, as predicted.

---

## 4. What surfaces FREE — confirmed by code read

| Surface | Mechanism | Verdict |
|---|---|---|
| Verticals rail "no map yet" → live link | `MoCVerticalsRail` + seeded-slugs fetch (`GET /admin/moc/?scope=vertical_default`) | ✅ flips the moment the page row exists |
| Platform map's FH card → "Open the map" | `MoCHome.VerticalsCards` same seeded-slugs set | ✅ free |
| Hopkins as a destination | `/maps/funeral_home/hopkins-fh` (MoCTenantPage: slug→lookup resolve, merged task view, tenant fires card) | ✅ route + merge machinery vertical-generic — **but see finding P-1 on the Tenants card's default list** |
| Breadcrumb spine | `MoCBreadcrumb` + `KNOWN_VERTICALS` (funeral_home present, label "Funeral Home") | ✅ free |
| Command-bar context | `useAdminPageContext` vertical case is generic | ✅ free |
| Full-bleed | `isFullBleedRoute` matches `/maps/*` | ✅ free |
| V-2 offer badges | `MoCPage` fetches offer states for the page's focuses slugs — vertical-agnostic | ✅ Cemetery Triage's declined-offer gap chip shows on the FH map the moment the ref exists |

---

## 5. The September lens

The demo is the deep case-comes-in walk (Hopkins + St. Mary's + Sunnycrest),
not broad coverage. The **demo-critical set** (marked in §1): First Call
Intake → Schedule Arrangement → Scribe Processing → Aftercare (the case
spine), Plot Reservation (the St. Mary's seam), the FH scheduling Focus
(recommend the operator-created variation, §1b) + Cemetery Triage (demos
variations + offered updates live). Everything else is completeness the
operator can enrich after the map exists. The triage decision that most
shapes the demo: **§1b's scheduling-Focus choice** — option (b) turns the
stamp itself into a demo rehearsal.

---

## 6. Platform findings (where stamping is harder than it should be)

- **P-1 — `tenant_lookup` has no vertical filter (REAL, should fix in the
  stamp session).** The H-1 Tenants card filters by vertical CLIENT-SIDE over
  a server response capped at 100 rows with no `vertical` param
  (`admin/kanban.py::tenant_lookup`). On the FH map — 9,837 FH tenants among
  60,511 total — the empty-query default list is the first 100 companies
  alphabetically ACROSS ALL VERTICALS; the FH subset of those may be near
  zero, and Hopkins is reachable only by search. Manufacturing has the same
  latent defect (masked by content). Fix: a `vertical` query param on the
  endpoint + pass-through from TenantsCard (~10 lines, both sides). This is
  the one place the H-arc machinery is NOT vertically clean.
- **P-2 — dev FH tenant noise:** thousands of `wf-test-fh-*` fixture tenants
  (leaked test residue) drown the FH tenants list on dev. Not a blocker
  (search reaches Hopkins) and not a code defect, but the P-1 fix makes the
  default list usable DESPITE the noise; a dev-DB fixture-tenant sweep is a
  separate hygiene item if wanted.
- **P-3 — `_find_runtime`'s missing vertical filter** (§2): safe today by
  name-set disjointness, a landmine under parameterization. Fixed as part of
  the stamp.
- **P-4 — zero-step vertical defaults:** three FH default workflows shipped
  as empty shells (obituary, insurance, EDRS). Not a stamping problem
  (triage excludes them) but an honest content gap in the FH vertical
  defaults — flagged for whoever owns FH workflow content pre-September.
- Everything else measured CLEAN: the vocabulary is platform-scoped, the
  core-card mechanism is by-reference, the join table already carries
  Cemetery Triage's FH membership, and the V-2 badge machinery is
  vertical-agnostic. Four findings against a whole vertical stamp is a
  strong result for "the platform as a product."

---

## The triage ask (what the operator decides before the stamp dispatches)

1. Confirm the bring-in set §1a(a) — all 9, or trim the completeness four.
2. The scheduling-Focus choice (§1b): FH-owned variation (recommended) vs
   cross-vertical ref vs omit.
3. Documents card: the single aftercare ref, or empty-with-room.
4. Whether P-1 rides the stamp session (recommended — it's the Hopkins-
   as-destination polish) and whether P-2's dev sweep is wanted at all.
