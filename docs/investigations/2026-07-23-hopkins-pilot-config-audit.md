# Hopkins Pilot — Persisted-Config Audit (READ-ONLY)

**Date:** 2026-07-23 · **Tenant:** hopkins-fh (staging, company_id
`52759c22-8f21-493d-ab00-6b2cffa188ec`) · **Trigger:** the fh_case
table-split fix surfaced two data-level defects (dead `/cases` pins,
blue light-mode accent) that a code grep can't see because they live in
seeded rows and JSONB. This audit walks the *persisted config* itself.

**Scope:** findings only. No code, no schema, no seed edits, no writes
of any kind — every staging query ran read-only (autocommit SELECTs).
Nothing pushed.

---

## Headline

Bucket (a) — making Hopkins canonical and correctly themed for the demo
— **is achievable without any bucket-(b) legacy-retirement work.** The
STOP conditions did NOT trigger:

- **A canonical cases LIST surface EXISTS today**: `/fh/cases` →
  `FhCaseList` → `fhApi.listCases()` → `GET /fh/cases` (the FH-1 backend
  reading `funeral_cases`). Repointing has somewhere to point. This is a
  data/code change, not a build-a-page arc.
- **No demo-critical fix requires touching the legacy `/cases` UI, its
  router, FK anchors, r31, or the 13 fh_* tables.** Repointing the pins
  *away* from `/cases` leaves that surface simply unlinked — which is the
  correct pre-retirement state.

**One premise correction (the point of the audit):** the blue accent is
**NOT a "pre-pivot platform_themes row."** It is **live CI test
residue** that regenerates on every push — `07-commit-overrides-persist.
spec.ts` deliberately writes `oklch(0.55 0.13 240)` to the
`funeral_home` vertical_default scope, and has done so 254 times (v254
active). Deleting the row is not durable; the fix is to stop the spec
targeting the pilot's vertical. Detail in §Theme below.

**One new defect the dispatch didn't list:** the FH director's seeded
saved-view pins point at seed keys whose VaultItems **were never
materialized** — hopkins-fh has **0 saved_view rows** (only 131 tasks).
So those pins are dead twice over: no target row exists, *and* the
executor would query the legacy table if one did.

---

## Job 1 — Full config census

Legend: **CANON** = points at canonical surface/value · **STALE** =
superseded pointer · **DEAD** = points at nothing · **RESIDUE** = value
re-written by CI.

| # | Config item | Points at / carries | Status | Source | Bucket |
|---|---|---|---|---|---|
| 1 | Space: admin **Arrangement** `default_home_route` + nav_item pin | `/cases` | STALE (legacy list, 0 rows) | `spaces/registry.py` SEED_TEMPLATES → `users.preferences.spaces` JSONB | a |
| 2 | Space: director **Arrangement** home + `nav_item:/cases` + `nav_item:/cases/new` | `/cases`, `/cases/new` | STALE | same | a |
| 3 | Space: director **Arrangement** 2× `saved_view` pins | seed_key `director:my_active_cases`, `director:this_weeks_services` — **target_id empty** | DEAD (0 saved_view VaultItems exist) | `spaces/registry.py`; saved-view rows never seeded (§Job 4) | a |
| 4 | Sidebar nav `getFuneralHomeNav()` "Active Cases" / "New Case" | `/cases`, `/cases/new` | STALE | `navigation-service.ts` (CODE) | a |
| 5 | Sidebar nav secondary "Cases" entry (line 565) | `/cases` | STALE | `navigation-service.ts` (CODE) | a |
| 6 | Saved-view executor `fh_case` entity query_builder | `FHCase` → `fh_cases` table | STALE (legacy table; same class as the resolver/mention_filter defects) | `saved_views/registry.py:258` (CODE) | a |
| 7 | Saved-view seed defs `my_active_cases` / `this_weeks_services` / `recent_cases` | `entity_type="fh_case"` | STALE-by-dependency (resolves through #6) | `saved_views/seed.py` (CODE) | a |
| 8 | `platform_themes` vertical_default / funeral_home / **light** / v254 | `accent: oklch(0.55 0.13 240)` (blue) + recursively self-nested `token_overrides` | RESIDUE + corrupt (calibrated light accent is ink `oklch(0.22 0.004 260)`) | **CI**: `07-commit-overrides-persist.spec.ts` (DATA, regenerates/push) | a |
| 9 | Command-bar action registry `funeral_home.ts` case actions | `/fh/cases` | **CANON** ✓ | `actions/funeral_home.ts` (CODE) | — |
| 10 | Command-bar resolver `fh_case` branch | `funeral_cases ⋈ case_deceased`, url `/fh/cases/{id}` | **CANON** ✓ (fixed `3a3b5759`) | `resolver.py` | — |
| 11 | MoC page `funeral-home-map` (vertical_default) | query-built, content-agnostic (resolve-or-skip); no embedded UI route | **CANON** ✓ (no stale pointer) | `seed_moc_funeral_home.py` | — |
| 12 | `workflow_templates` funeral_home: `funeral_cascade` (16 nodes) + 9 `mirror_*` | backend orchestration node types / service-method dispatch — not UI routes | **CANON** ✓ (no route pointer) | MoC/workflow seeds | — |
| 13 | Today/Pulse widget (`today_widget_service`) | queries `Delivery` only; case data marked "Future" | **CANON** ✓ (carries no case pointer yet) | `today_widget_service.py` | — |
| 14 | `platform_themes` platform_default / light / v2 | `{}` (inherit base tokens.css → ink) | **CANON** ✓ | — | — |
| 15 | FH dark-mode theme | no active vertical_default *or* platform_default dark row → falls to base-tokens `[data-mode="dark"]` = calibrated chrome | **CANON** ✓ (why dark witnessed correctly) | — | — |

**platform_themes totals on staging:** 256 rows, **2 active** — 1
platform_default (light, `{}`) and 1 funeral_home vertical_default
(light, blue). 254 of the 256 are inactive funeral_home versions: the CI
spec's write-side versioning accretion. No other vertical has a theme
row at all (manufacturing, cemetery, crematory all inherit base tokens —
correct).

---

## Job 2 — Does a canonical target exist?

**YES, and this sizes the whole arc down to data/code, not
build-a-surface.**

| Stale pointer | Canonical replacement | Exists? |
|---|---|---|
| `/cases` (list) | `/fh/cases` → `FhCaseList` → `GET /fh/cases` (reads `funeral_cases`) | ✅ mounted + working |
| `/cases/:id` (detail) | `/fh/cases/:caseId` → `FhCaseDashboard` | ✅ |
| `/cases/new` (create) | **No `/fh/cases/new` route.** Canonical create is a **button on the list** (`FhCaseList.createCase()` → `POST /fh/cases` → nav to `/fh/cases/{id}/arrangement`) | ⚠️ see Type B #2 |
| Saved-view `fh_case` entity | repoint executor query_builder to `funeral_cases` (parallels `3a3b5759`) | ✅ table exists |

The one wrinkle: **there is no standalone canonical "new case" route** —
creation is an action on the list page. The legacy `/cases/new` pin
therefore has no 1:1 route to repoint to; it should target `/fh/cases`
(where the create button lives) or be dropped. Small, but a decision
(Type B #2), not a blocker.

**Critically: `/fh/cases` is currently linked from NOTHING in
navigation.** `grep '"/fh/cases"' navigation-service.ts` → 0 hits. The
only frontend reachers are the command-bar action (#9) + resolver (#10).
So today a Hopkins director reaches their real cases *only* via Cmd+K —
the sidebar and every space pin dead-end at the empty legacy list. That
is the user-visible severity of this cluster.

---

## Job 3 — Scope split

### Bucket (a) — DEMO-CRITICAL (all achievable without bucket b)

Two sub-classes:

**(a1) DATA — one-time staging fixes (per-tenant JSONB / rows):**
- Repoint the 4 hopkins users' space pins + `default_home_route` from
  `/cases`/`/cases/new` → `/fh/cases` (items #1, #2).
- Resolve the dead saved-view pins (#3) — either materialize the
  director saved-views or drop the pins (depends on Type B #3).
- Neutralize the blue theme residue (#8): deactivate the corrupt
  funeral_home vertical_default rows so light inherits platform_default
  ink. **Not durable alone** — see (a3).

**(a2) CODE — regenerates-wrong-on-every-tenant, so seed/source fixes:**
- `navigation-service.ts::getFuneralHomeNav` — `/cases`→`/fh/cases`,
  `/cases/new`→`/fh/cases` (items #4, #5).
- `spaces/registry.py` SEED_TEMPLATES for `(funeral_home, director)` +
  `(funeral_home, admin)` — pins + `default_home_route` (#1, #2).
- **`saved_views/registry.py::fh_case_query`** — repoint from `FHCase`
  to `FuneralCase` + `CaseDeceased` (#6). **This is the exact same
  defect class as the resolver/mention_filter fix in `3a3b5759`** — a
  catalog/registry consumer still reading the legacy table. It is the
  fourth `SEARCHABLE_ENTITIES`-adjacent legacy reader, and it is
  demo-critical because seeded director saved-views are a headline
  Monitor surface.
- `saved_views/seed.py` — `entity_type="fh_case"` defs stay as-is once
  #6 is repointed (fh_case then means canonical); verify serialize
  fields match `FuneralCase`/`CaseDeceased` column names (the current
  `fh_case_serialize` reads `deceased_first_name` etc. off `FHCase` —
  those columns live on `case_deceased` in the canonical model, so the
  serializer needs the join, mirroring the resolver's `from_clause`).

**(a3) TEST — the durable theme fix:**
- `07-commit-overrides-persist.spec.ts` mutates `funeral_home`
  vertical_default scope with a deliberately-off accent, on every push.
  Even after deleting the rows, the next CI run re-stages blue on the
  pilot's exact scope. Durable fix = point the spec at a throwaway scope
  (a tenant_override on a disposable tenant, or a non-pilot vertical) so
  CI stops writing the pilot's theme. Until then, Hopkins light mode is
  owned by CI. (Dark mode — the hero — is unaffected.)

### Bucket (b) — LEGACY FH-v1 RETIREMENT (explicitly NOT this arc)

Unmount `/cases` + `pages/funeral-home/*`, retire `app/api/routes/
cases.py` + `case_service.py`, re-anchor `canonical_document.fh_case_id`
+ `intelligence` FKs, drop r31's orphaned `fh_cases` trigram index,
sunset the 13 `fh_*` tables. None of this is required for (a): once (a)
repoints every pointer away from `/cases`, the legacy surface is
unreached and can be retired on its own schedule.

**Is (a) achievable without (b)? YES — cleanly.** Repointing is
strictly additive-toward-canonical; it never touches a legacy artifact.
The legacy surface goes dark by losing its inbound links, which is
exactly the state a retirement arc starts from.

### Effort floor for bucket (a) only

Floor, not ceiling: **~120–160 LOC across ~6 files, one arc (likely 2
commits — a code/seed commit + a staging data-repair step).**
- Nav + spaces registry repoints: ~25 LOC (mechanical string swaps +
  the 14 NAV_LABEL / default_home_route touch-points).
- Saved-view executor `fh_case` repoint incl. the join-aware serializer:
  ~40–60 LOC (the substantive piece — it's the `3a3b5759` pattern
  again, with a serializer that now spans two tables).
- Staging data repair (repoint existing 4-user JSONB pins; deactivate
  254 residue theme rows): a scripted one-time `railway run`, ~30 LOC,
  no migration.
- Playwright spec scope change: ~10 LOC.
- Tests: extend the saved-view executor suite for the canonical fh_case
  path (the litter-safe fixture pattern from the resolver fix applies).

Not included (bucket b): everything in §Bucket (b).

---

## Job 4 — Seed vs data (per stale item)

| Item | Wrong in SEED CODE (regenerates)? | Wrong in DB ROWS (one-time)? |
|---|---|---|
| #1/#2 space pins + home `/cases` | ✅ `spaces/registry.py` | ✅ 4 hopkins users' JSONB already carry it |
| #3 dead saved-view pins | ✅ (pins seeded) + **seed GAP**: `seed_fh_demo` seeds spaces but **not** saved-view VaultItems → 0 rows on staging | ✅ (0 rows to repair = materialize) |
| #4/#5 sidebar nav | ✅ CODE only (`navigation-service.ts`) — no DB row | ❌ |
| #6 saved-view executor `fh_case` | ✅ CODE only (`registry.py`) — no DB row | ❌ |
| #7 saved-view seed defs | ✅ CODE (`seed.py`) — inert until #6 repointed | ❌ |
| #8 blue theme | ❌ no seed writes themes (verified: 0 seed refs; blue exists only as a **test fixture**) | ✅ 254 residue rows — but **CI re-creates on every push** (data + test-code) |

**Load-bearing implication:** every future FH tenant onboarding
regenerates items #1–#7 wrong (they're seed/source code), so the fix
must land in code, not just staging data. The theme (#8) is the
inverse — the seed is clean; the damage is CI-generated data that a
test-code change stops.

---

## Type B calls for James

1. **Saved-view executor `fh_case` repoint (#6/#7)** — this is the
   fourth legacy-table reader of the `3a3b5759` class and it's
   demo-critical (seeded director Monitor surfaces). Ship it *in this
   pilot-config arc*, or fold it into a follow-up to the resolver fix?
   Recommend: this arc — it's the same pattern and the demo needs
   director saved-views to return rows.
2. **`/cases/new` pin has no canonical route twin** — canonical create
   is a button on `/fh/cases`, not a standalone route. Repoint the "New
   Case" pin/nav to `/fh/cases` (list, where Create lives), or drop the
   New-Case pin entirely? Recommend: repoint to `/fh/cases` (keeps the
   affordance one click away).
3. **Dead saved-view pins (#3)** — the director's `my_active_cases` /
   `this_weeks_services` pins have no materialized VaultItems on staging
   (seed gap). Fix by making `seed_fh_demo` run the saved-view seed
   (so pins resolve), or drop the saved-view pins from the FH templates
   for now? Recommend: run the saved-view seed *after* #6 repoints, so
   the pins resolve to views that actually return canonical cases.
4. **Theme residue durability (#8/a3)** — accept that CI owns Hopkins
   light-mode theming until the Playwright spec is rescoped (demo in
   dark, the hero), or rescope the spec now as part of (a)? Recommend:
   rescope now — it's ~10 LOC and removes a standing pilot-scope
   pollution, and lets light mode demo cleanly.

---

*Read-only confirmation: no source files changed, no schema touched, no
seed edited, no staging writes, nothing pushed. Artifacts of this
session: this findings file only. All staging queries were autocommit
SELECTs; scratch scripts live under the session scratchpad.*
