# MoC Tenant View — Investigation / Scoping (read-only)

**Date:** 2026-07-06 · **HEAD at investigation:** `265d768` (post-T-2.1c push) ·
**Trigger:** the T-2.1c witness-visibility gap — the seeded witness marker-task is
`tenant_override → testco`, but `/maps/:vertical` reads `vertical_default` only, so
tenant-scoped tasks (which the sweep REALLY fires) are invisible in the page.

**The chosen fix:** a PAGE-SCOPED tenant selector — pick a tenant → the whole MoC
recontextualizes to that tenant's view. This doc maps what that actually means per
card, where the tenant list comes from, the default/empty/label states, and the
read-path changes. **The headline finding: the feature is smaller than "page-wide
machinery" — the page read is already tenant-aware end-to-end; only the TASK read
needs a real backend change (a merge-semantics fix), and the tenant-picker control
already exists as a reusable component.**

---

## 1. What "this tenant's MoC" means per card — the tenant-awareness map

The page loads via exactly TWO reads (`MoCPage.tsx::load`):

| Read | Feeds | Tenant-aware today? |
|---|---|---|
| `readForContext({vertical})` → `GET /api/platform/admin/moc/read` | ALL FOUR artifact cards (Workflows / Focuses / Widgets / Documents) — they are groupings of ONE resolved page's rows (`toTypeCards`) | **YES — end to end, unused.** Route accepts `tenant_id` (moc.py:471); `read_for_context → resolve_for_context` runs the 3-tier walk; the service client's `readForContext` already types `tenant_id?`. The page just never passes it. |
| `readTaskCatalog({vertical})` → `GET /api/platform/admin/moc/tasks` | The Tasks table | **PARAM EXISTS, SEMANTICS WRONG.** See §1.2 — this is the one real backend change. |

### 1.1 The four artifact cards — tenant-aware at PAGE granularity (first-match, not merge)

`resolve_for_context` (service.py:310) is a **first-match-wins walk**:
`tenant_override(tenant, vertical)` → `vertical_default(vertical)` → `platform_default`.

So "this tenant's MoC cards" means: **if the tenant has authored a replacement
MoCPage, they see THAT page (all four cards from it); otherwise they fall through
to exactly today's vertical_default page.** There is no row-level merge — a tenant
page replaces the whole page. That's the shipped scope model (MoC Phase 1), and the
selector should honor it, not invent a merge.

**Honest scope statement (dispatch asked for this plainly):** no `tenant_override`
MoCPage rows exist today (only vertical_default manufacturing is seeded), so for
every current tenant the cards will render IDENTICALLY with or without a tenant
selected. The selector's page-scope is REAL for the cards (the walk runs, and the
moment a tenant authors an override page it appears) but is **forward-looking in
practice** — today the visible recontextualization is the Tasks table. Build the
frame (pass `tenant_id` to `readForContext`, label the result's scope), don't build
card-level merge machinery for a dimension the scope model doesn't have.

**Zero backend change for the cards.** The only card-side work is frontend: pass
the param + label the resolved page's scope (the response already carries
`scope` + `tenant_id`, so "you're viewing <tenant>'s page" is derivable from data
already returned).

### 1.2 The Tasks table — the one REAL backend change (merge semantics)

`resolve_task_catalog` (task_catalog.py:118) is an **exact-match filter**, not a
walk and not a merge:

```python
.filter(scope == scope, vertical == vertical, tenant_id == tenant_id, is_active)
# defaults: scope="vertical_default", tenant_id=None
```

Consequences, verified in code:
- Today's page call (`tenant_id` omitted) → vertical_default rows only. Correct
  current behavior.
- **Passing `tenant_id=X` alone returns EMPTY** — it filters
  `scope="vertical_default" AND tenant_id=X`, and vertical_default rows have
  `tenant_id NULL`. The route (moc.py:485) passes `tenant_id` straight through, so
  `GET /tasks?vertical=manufacturing&tenant_id=<testco>` is a well-formed request
  that can never return anything. The parameter exists but is unusable for the
  selector — "readTaskCatalog already accepts tenant_id" was true but misleading.
- **No caller depends on the broken path**: the only route caller passes the
  query param through (same emptiness), and every test/seed caller uses the
  defaults. Changing the `tenant_id` path's semantics breaks nobody.

**The fix — tenant-view merge, mirroring the sweep's own fan-out.** The honest
definition of "this tenant's tasks" is *the set the schedule sweep would fire for
this tenant* (`_fanout_companies`): `platform_default` (all tenants) +
`vertical_default` (vertical matches) + `tenant_override` (tenant matches). So:

```
tenant view  = rows where (scope='vertical_default' AND vertical=V AND tenant_id IS NULL)
             ∪ rows where (scope='tenant_override'  AND vertical=V AND tenant_id=T)
             [∪ platform_default — include for sweep-parity; zero such rows exist today]
```

One query with an OR of filter tuples (or two queries concatenated), ordered
scope-group then `display_order, name`. ~15 LOC in `resolve_task_catalog` when
`tenant_id` is provided; the no-tenant default path stays byte-identical
(non-regressive).

**Read-shape addition for labeling:** `resolve_task` (the task read dict) does NOT
expose `scope`/`tenant_id` today — the merged table can't label tenant rows without
it. Add `"scope"` (and `"tenant_id"`) to the dict. Additive; no existing consumer
breaks (verified: consumers key on name/id/workflow/triggers).

### 1.3 Card-by-card summary

| Card | Tenant dimension today | Selector effect | Backend change |
|---|---|---|---|
| Workflows | Page-granularity (override page replaces) | Falls through until a tenant page exists | none |
| Focuses | same | same | none |
| Widgets | same | same | none |
| Documents | same | same | none |
| **Tasks** | **Row-granularity** (`tenant_override` rows are real + sweep-fired) | **vertical rows + tenant rows, labeled** — the witness marker appears | **merge read + scope in read shape** |

---

## 2. The tenant-list source — ALREADY EXISTS, reuse it

- **Endpoint:** `GET /api/platform/admin/tenants/lookup` (kanban.py:25) —
  `{id, slug, name, vertical}` for active companies, ILIKE search on name/slug,
  limit ≤ 100. Platform realm (`get_current_platform_user`) — same realm as the
  MoC page. Built for exactly this job ("Lightweight tenant search for picker UI").
- **Component:** `TenantPicker` (`frontend/src/bridgeable-admin/components/TenantPicker.tsx`)
  — search input + result list against that endpoint, returns
  `{id, slug, name, vertical}`, **with a `verticalFilter` prop** (client-side
  exact-match on `Company.vertical`). Already consumed by the Visual Editor scope
  selectors + the runtime editor's TenantUserPicker.

**No backend add needed. No new component needed.** Mount `TenantPicker` with
`verticalFilter={vertical}` in the MoC page header.

**Which tenants appear — recommendation: tenants in THIS vertical** (via
`verticalFilter`). A cemetery tenant inside the manufacturing MoC is incoherent —
their overrides live under their own vertical's walk. "Only tenants WITH MoC
overrides" is rejected: the selector's job includes *authoring* a tenant's first
override (you must be able to select a tenant that has none yet). Caveat noted:
`verticalFilter` filters client-side over a ≤100-row fetch — fine at current scale
(staging is small; ~200 Wilbert licensees later still fits one fetch + search).

---

## 3. Default, empty, and label states

- **Default (no tenant selected) = today's view, byte-identical.** The null
  selector state passes NO `tenant_id` to either read — both backends take their
  current paths. Non-regressive by construction, not by care.
- **Tenant with no overrides:** pages walk falls through → same cards; task merge
  returns vertical rows + zero tenant rows → same table. Graceful degradation to
  the default view, optionally with a quiet "no tenant-specific tasks yet" hint in
  the table region (plus "Add task" now creating FOR this tenant — §4).
- **Labeling tenant-scoped rows (required — never confusable with defaults):**
  - Task rows: a scope pill on tenant_override rows (e.g. an accent-subtle chip
    with the tenant's short name or "Tenant"), driven by the new `scope` field in
    the read shape. Vertical rows stay unadorned (the default is calm; the
    override is marked).
  - The page cards: when the walk returned a tenant page, a banner/badge derived
    from the response's `scope`/`tenant_id` ("Viewing <tenant>'s page —
    replaces the manufacturing default").
  - The selector itself is the primary context signal: a persistent, visible
    control in the page header showing the active tenant (or "All manufacturing
    (defaults)" when null).
- **URL state:** put the selection in the URL — `/maps/manufacturing?tenant=<slug>`
  — so a tenant view is linkable/refreshable/shareable (precedent: the runtime
  editor's `?tenant=&user=` params). Slug (not id) for readability; resolve via
  the lookup on load.

---

## 4. Read-path (and write-path) changes, precisely

**Frontend-only:**
1. `MoCPage.tsx`: tenant state (+ URL param sync); pass `tenant_id` to BOTH
   `readForContext` and `readTaskCatalog`; mount `TenantPicker`
   (`verticalFilter={vertical}`) in the header; scope banner for a tenant page.
2. `MoCTaskTable` / row: render the scope pill from the new `scope` field.
3. `moc-service.ts`: `MoCTask` gains `scope?` (+ `tenant_id?`) — type-only.

**Backend (the one real change):**
4. `resolve_task_catalog`: tenant-merge semantics when `tenant_id` is passed
   (§1.2). Default path unchanged. No route signature change — the param already
   exists; its meaning goes from broken-empty to correct.
5. `resolve_task`: add `scope` + `tenant_id` to the read dict (additive).

**Write-path (small but load-bearing for coherence):**
6. In tenant view, the panel's **"Add task" should create
   `scope="tenant_override", tenant_id=<selected>`** — `admin_create_task`
   already accepts both in the body (moc.py:156); the panel just needs to send
   them when a tenant is active. Without this, an operator "in testco's view"
   silently authors a vertical-wide default — the confusing failure.
   - Editing/deleting a **vertical_default** row while tenant-scoped: keep direct
     edit (it edits the shared default; the pill + a hint make that legible).
     Fork-on-edit ("customize this default for this tenant") is a REAL future
     feature but explicitly out of scope — flag, don't build.
   - Trigger writes (T-1b/T-2.1c, incl. the Live toggle) ride the task row —
     zero changes; the merged view is precisely where the witness marker-task
     becomes visible and promotable from the UI, closing the T-2.1c gap.

**No changes:** `admin_read_for_context` (already takes tenant_id),
`tenants/lookup`, `TenantPicker`, the sweep, the trigger CRUD, the live toggle.

---

## 5. Recommended build scope (one session), phased

1. **Backend merge + read shape** (items 4–5) + assembly tests — the enabling
   change, ~30–60 LOC + tests.
2. **The selector + recontextualization** (items 1–3) — TenantPicker in the
   header, URL param, both reads take the tenant, scope pill + page banner,
   empty-state hint. ~150–250 LOC + vitest.
3. **The tenant-aware Add-task** (item 6) — panel sends
   tenant_override/tenant_id when a tenant is active. ~20 LOC + tests.

Explicitly OUT: fork-on-edit of defaults; tenant-page authoring UI (the walk
serves one when it exists — authoring it is MoC-authoring scope, later);
per-card merge semantics for artifact cards (the scope model is
page-replacement); any sweep/trigger/live-toggle change.

## 6. Assembly + witness plan

- **Backend assembly:** merge returns vertical + that-tenant's rows (and NOT
  another tenant's); no-override tenant → defaults only (byte-equal to the
  no-tenant call); `scope` present in the read shape; default no-tenant path
  unchanged (regression pin on the existing tests' expectations).
- **Frontend vitest:** null selector → reads called WITHOUT tenant_id (the
  non-regression pin); selecting → both reads called with it; tenant row renders
  the scope pill; vertical row doesn't; Add-task in tenant view POSTs
  scope=tenant_override + tenant_id; URL param round-trip.
- **Visual witness (local, admin tree, shell-witness@example.com):** on
  /maps/manufacturing select testco → the T-2.1b witness marker-task APPEARS,
  labeled as testco's, with its schedule chip + Dry-run badge + functional Live
  toggle (compiled) — the exact row the page couldn't show before; deselect →
  it disappears and the view is today's; a no-override tenant shows defaults
  gracefully.

## 7. Honest sizing + flags

- **Smaller than "page-wide":** the cards' tenant path exists end-to-end (unused);
  the picker exists; the ONLY backend change is the task-merge (+2 read-shape
  fields). The selector is, today, **a task-table recontextualization inside a
  page-level frame that's genuinely ready** for tenant pages when they arrive —
  built honestly at that size. Single build session including tests + witness.
- **Flag (dispatch STOP (c), resolved):** the Tasks read *couldn't* take tenant
  scope cleanly — the param existed with broken exact-match semantics (always
  empty). It needs the merge change; nothing depends on the broken behavior.
- **Flag:** `resolve_task`'s read shape lacks `scope` — labeling requires the
  additive field.
- **Flag (future):** `verticalFilter` on TenantPicker is client-side over a
  ≤100-row fetch — revisit if tenant count outgrows one fetch+search.
- **Flag (future):** fork-on-edit for defaults in tenant view; tenant MoC-page
  authoring surface.
