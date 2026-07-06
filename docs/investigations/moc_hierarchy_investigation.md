# MoC Hierarchy — Investigation / Scoping (read-only)

**Date:** 2026-07-06 · **HEAD:** `273f49f` ·
**Direction:** the entire admin converts to a hierarchical, hyperlinked MoC
architecture — the MoC becomes the NAVIGATION SPINE. Three levels: Platform
MoC (login landing) → Vertical MoCs (the proven pages) → Tenant MoCs
(superseding the tenant selector — tenants become destinations). Editors and
operational pages stay what they are; the map links to them.

**Two findings up front that shrink this from "conversion" to "completion":**

1. **The platform tier ALREADY EXISTS in the scope model.** `platform_default`
   is a first-class scope on BOTH `moc_pages` AND `moc_task_catalog` (model
   comments, create-validation, and `resolve_for_context`'s walk all carry it:
   tenant_override → vertical_default → **platform_default**). Zero platform
   pages/tasks are authored — but the slot exists. The platform MoC is
   "author a page into an existing slot," NOT a schema extension. STOP
   finding (a): resolved, no migration for the tier.
2. **The admin's login landing is ALREADY MoC-shaped.** `/` renders `MoCHome`
   — a two-pane with the persistent `MoCVerticalsRail` (the 4 verticals with
   live/no-map-yet states) beside an empty "select a vertical" content pane.
   The Level-1 conversion is "fill the empty pane with the resolved platform
   page," not "replace the landing." The front door was built pointing this
   direction.

**Honest sizing: 3 sessions** (H-1 tenant MoC, H-2 platform MoC, H-3 the
spine/nav pass). Details in §6.

---

## 1. Level 1 — the Platform MoC (fills MoCHome's content pane)

**What it shows, grounded in what exists today:**

| Card | Grounding | Status |
|---|---|---|
| **Verticals** (linked cards → each vertical's MoC) | The rail already renders exactly this (4 presets, live/no-map-yet). In-pane vertical cards duplicate the rail deliberately — the pane is the MAP (hyperlinked content), the rail is the persistent shortcut. | EXISTS (re-render in pane) |
| **Core artifacts** (the cross-vertical canon: Month-End Close, AR Collections, the `scope=core` wf_sys_* workflows) | These are `scope="core"` workflows — vertical-independent by definition. Today they appear on the manufacturing map only because its authored rows reference them. **The platform MoC is their canonical home**; the manufacturing map keeps its links (a map may link anything), but the platform page is where "Bridgeable's own machinery" lives. | EXISTS (data); authoring the rows is the work |
| **Platform activity** (the MoC fires log — schedule + event, source-discriminated, all tenants) | `list_schedule_runs` exists and is already cross-tenant (platform-realm). A compact "recent fires" card = one fetch of the existing endpoint. | EXISTS |
| **Tenant/health summary** (counts; a link to Health) | `platform_tenants` list + Health dashboard exist as endpoints/pages. The platform MoC LINKS to them (a stat line + hyperlink), it does not absorb them. | EXISTS (link + count) |
| **Platform tasks** | `moc_task_catalog` accepts `platform_default` scope; zero exist. The task table can render at platform scope with `resolve_task_catalog(scope="platform_default")` — the read takes the param today. Ship the empty table (Add-task works); content accrues. | SLOT EXISTS, empty |

**Authoring mechanism:** create the `platform_default` MoCPage (a seed like
`seed_moc_manufacturing`, or the existing "create starter" affordance
generalized). `read_for_context(vertical=None, tenant_id=None)` already
resolves it. `MoCHome`'s pane swaps the EmptyState for the same
`MoCTypeCards` + `MoCTaskTable` composition `MoCPage` uses — the rendering is
the proven vertical page's, pointed at a different resolved page.

**What the current landing/nav does that must survive:** `MoCHome` renders
inside `AdminLayout`, whose header nav carries: Maps, Health, Tenants (kanban),
Audit, Migrations, Feature Flags, Deployments, Staging, Verticals (registry
admin), Studio, (+Telemetry route). None of these dissolve in H-2 — the
platform map gains LINKS to the right ones (§3), and the header survives as
the shortcut layer (§3's recommendation).

## 2. Level 3 — the Tenant MoC (supersedes the selector)

**Route:** `/maps/:vertical/:tenantSlug` — the hierarchy in the URL, each
segment meaningful. (Slug, not id — matches the retired `?tenant=` param's
choice and stays readable.)

**What it shows — honest contents (STOP finding (b): yes, thin today; here is
exactly how thin, and it is still worth a page):**

| Section | Grounding | Today |
|---|---|---|
| **Tasks — the merged view** (defaults + THIS tenant's overrides, overrides pilled) | The tenant-view arc's merge read (`resolve_task_catalog(tenant_id=…)`) IS this page's task read, verbatim. The pills, the tenant-aware Add-task coherence guard, the trigger chips with Live/Dry-run badges + toggles — all transfer unchanged. | **REAL — the substantive content** |
| **Trigger live-state at a glance** | The merged rows already carry each trigger's is_live badge — a tenant page IS "what fires for this tenant and which of it is live." This is the sweep-honest view (the merge mirrors `_fanout_companies`). | REAL (rides the task table) |
| **The tenant's fires** (recent schedule/event runs for THIS tenant) | `list_schedule_runs` has trigger_id but NO company filter — a tenant-scoped fires card needs a small `company_id` param addition (a WHERE clause; the run rows carry company_id). | SMALL BACKEND ADD (~5 LOC) |
| **Artifact cards** (Workflows/Focuses/Widgets/Documents) | Page-granularity replacement: `read_for_context(vertical, tenant_id)` serves the tenant's OWN MoCPage when authored (zero exist), else falls through to the vertical's. Render the fall-through with the existing "replaces the default" banner logic inverted: "showing the manufacturing defaults — this tenant has no map of its own yet (create one)". The create-starter affordance already exists and takes tenant scope. | SLOT EXISTS, fall-through honest |
| **Tenant identity strip** (name, slug, vertical, active, link to the Tenant Kanban detail / Studio-live-as-tenant) | `tenants/lookup` + kanban detail endpoints exist. Links, not absorption. | EXISTS (links) |

**The supersession diff — a move, not a rebuild:**

| Tenant-selector arc piece | Fate |
|---|---|
| `resolve_task_catalog` tenant-merge read | **TRANSFERS** — becomes the tenant page's task read, unchanged |
| Override pills (+ `scope`/`tenant_id` in the read shape) | **TRANSFERS** — same labeling job on the tenant page |
| Tenant-aware Add-task (creates tenant_override + tenant-titled panel) | **TRANSFERS** — on the tenant page it's unconditional (always tenant-scoped) |
| Tenant-page banner ("has its own map page") | **TRANSFERS, inverted** — the tenant page states which source its cards came from |
| `TenantPicker` "Viewing" control on the vertical page | **RETIRES** — replaced by the Tenants card's links (below). The component itself survives (Visual Editor + runtime editor still consume it) |
| `?tenant=<slug>` URL param + lookup-restore effect | **RETIRES** — the route param IS the state; deep-links become real URLs |
| `activeTenant` state threading in MoCPage | **RETIRES** (moves into the tenant page as route-derived) |
| The 7 TenantView vitest | **TRANSFER with edits** — same claims, exercised via the tenant page |

**Where tenant links live on the vertical MoC:** a **Tenants card** on
`/maps/:vertical` — the vertical's tenants as links to their pages, fed by the
existing `tenants/lookup` (`verticalFilter` semantics move server-side or stay
client-side as today; ≤100-row caveat from the tenant-view investigation still
flagged). Each entry links `/maps/:vertical/:slug`. This is the "tenants
become destinations, not a dropdown" moment.

## 3. The spine — breadcrumbs, nav, links, command bar

- **Breadcrumbs:** `Platform › Manufacturing › Test Vault Co` on every map
  page, every segment a link (`/` → `/maps/manufacturing` →
  `/maps/manufacturing/testco`). Route-derived, no state. Lives on the map
  surfaces (MoCHome pane header + MoCPage + tenant page); non-map pages keep
  their current chrome.
- **The admin nav — RECOMMEND: keep as the shortcut layer, do not dissolve
  (STOP finding (c), surfaced).** The spine vision reads as "the map IS the
  nav," but killing the persistent header has a real usability cost: (1)
  operational pages (Migrations, Deployments, Staging, Audit) are
  task-interrupt destinations — an operator mid-incident should not traverse
  a map to reach Migrations; (2) the map's own failure modes (a page that
  won't resolve) need an escape hatch; (3) muscle memory during the
  transition. Recommendation: H-1/H-2 change nothing in the header; H-3
  *rationalizes* it (Maps stays leftmost as today; possibly demote rarely-used
  links) and revisits shrinking only after the map has carried real traffic.
  The map becomes the primary nav by being better, not by being the only.
- **Where existing destinations hang off the hierarchy:**
  - Platform level: Health, Tenants kanban, Migrations, Deployments, Staging,
    Feature Flags, Audit, Telemetry, Verticals registry, Studio (root).
  - Vertical level: Studio's per-vertical editors (the deep-link resolver
    already produces these hrefs — the artifact cards ARE these links),
    vertical defaults in the Visual Editor.
  - Tenant level: Studio live-as-tenant (the runtime editor's
    `?tenant=&user=` flow), the tenant's kanban detail, tenant overrides in
    Visual Editor scope.
- **The command bar coexists cleanly.** `useAdminPageContext.derive(pathname)`
  is a pure per-path derivation already covering `/maps/:vertical` and Studio;
  it extends with two cases: `/` → platform context ("Platform · MoC"),
  `/maps/:vertical/:slug` → tenant context ("testco · manufacturing · MoC").
  Small, tested, additive.

## 4. Exists vs net-new (the sizing map)

**EXISTS (the reuse credit — most of the feature):** the vertical MoC page
(complete, the template — cards, task table, editing, triggers, Live toggles);
the `platform_default` tier in BOTH scope models + the resolve walk; the
tenant page-granularity replacement mechanism; the tenant task-merge +
pills + coherence guard (the selector arc's machinery, transferring); the
deep-link resolver (`mocDeepLink` — the hyperlinks); `tenants/lookup`;
`MoCHome` two-pane landing + verticals rail; the Notion aesthetic + all
components; the fires log (cross-tenant); the command-bar context hook
(extensible by design); create-starter authoring.

**NET-NEW (the actual work):**
1. The tenant MoC route + page (assembling transferred machinery into a
   destination) + the Tenants card on the vertical page + selector
   retirement. (H-1)
2. `company_id` filter on `list_schedule_runs` (~5 LOC) + a tenant fires
   card. (H-1)
3. Breadcrumbs component (route-derived, small). (H-1 ships it on map pages)
4. The platform MoCPage seed (+ optionally 2-3 platform tasks for the core
   workflows) + MoCHome's pane rendering the resolved platform page +
   platform cards (verticals / core artifacts / recent fires / links). (H-2)
5. Command-bar context extension (2 cases + tests). (H-3, or ride H-1/H-2)
6. The nav rationalization + cross-level links pass + any header changes. (H-3)

**NOT in scope anywhere here:** absorbing editors/operational pages into maps
(direction says link, not absorb); tenant-page authoring UI beyond the
existing create-starter; per-tenant artifact-card merge (the scope model is
page-replacement — unchanged).

## 5. Recommended phasing (against reality: most-machinery-first)

- **H-1 — THE TENANT MoC (1 session).** The route + page (merge-read task
  table, trigger toggles, fires card via the small company filter, identity
  strip, fall-through cards with honest source note), the Tenants card on the
  vertical map, breadcrumbs on map pages, selector retirement (the transfer
  diff in §2), tests moved + extended. Supersedes the selector cleanly —
  tenants become destinations. Most machinery exists; highest value per line.
- **H-2 — THE PLATFORM MoC (1 session).** Seed the platform_default page
  (verticals card + core-artifact rows + links); MoCHome's pane renders it
  (same composition as MoCPage); platform task table (empty, functional);
  recent-fires card; breadcrumb root. The landing "conversion" is filling a
  pane that was built waiting for this.
- **H-3 — THE SPINE PASS (1 session).** Command-bar contexts for
  platform/tenant levels; the cross-level links audit (every admin destination
  reachable from its right level); nav rationalization per §3's
  keep-as-shortcut recommendation; visual polish so the three levels read as
  one continuous, hyperlinked surface (Notion discipline).

Each phase independently shippable and witnessed (H-1's witness: navigate
Platform › Manufacturing › testco and see the witness marker task with its
Live toggles as a DESTINATION; H-2's: log in and land on the platform map).

## 6. STOP findings — status

- **(a) Platform tier — EXISTS.** No schema work; the platform MoC is
  authoring + rendering into a slot both scope models already carry.
- **(b) Tenant-page contents — thin today, and stated so.** The substantive
  content is the merged task view + trigger live-states (real, sweep-honest)
  + a small tenant-fires card; artifact cards fall through until tenant pages
  are authored (the mechanism exists, zero pages do). That is a genuinely
  useful page — "what runs for this tenant and what's live" — without
  inflation. It grows as tenant pages/tasks accrue.
- **(c) Nav dissolution — real usability cost, surfaced.** Recommendation:
  the header survives as the shortcut layer through H-3; shrink later on
  evidence, not on vision. The map earns primacy by use.

**Sizing, honestly: 3 sessions (H-1 → H-2 → H-3), no migrations, one ~5-LOC
backend read addition; everything else is authoring, assembly, and one new
route/page built from transferred machinery.**
