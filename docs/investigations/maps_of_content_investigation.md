# Maps of Content (MoC) — Scoping Investigation (Phase 0)

**Date:** 2026-06-10 · **HEAD:** `5411f9a` (verified on both copies) · **Read-only** — no code, no canon, no commit, no dispatch.
**Working copy:** read + written against `~/Projects/SunnycrestERP` (the post-move canonical copy), NOT the soon-to-be-archived Drive copy — both at `5411f9a`, clean.
**Model under test (settled intent, scoped-against not redesigned):** an admin-first artifact navigation model — a HOME DASHBOARD (always-first admin landing: system widgets + links to MoC pages) + per-vertical AUTHORED MoC PAGES (Notion-like linked tables where each themes/focus/workflow/widget row deep-links into the owning builder with that artifact open). Admin-first but must generalize tenant-facing later (realm-crossing is a design constraint from the start).
**Method:** A+B deep (the load-bearing pair), C/D/E surveyed; every "exists" verified against live source with file:line, headline deep-link claims spot-witnessed directly.

---

## HEADLINE VERDICT

**MoC is mostly assembly, and the load-bearing reuse claim VERIFIED STRONGER than hypothesized.** The deep-link target — "click a row → the builder opens with that artifact loaded" — is a **thin routing layer, not per-builder work**: 4 of 7 builders already read an artifact id from the route and load it (witnessed), 2 are ~30–50 LOC param-wiring adds, and the 7th (Registry) is an inspector with no single-artifact concept (correctly out of scope). The dispatch's hypothesis ("the Builder-AI-Assistant Workflow deep-link generalizes") was *under*-stated — Focus, Widget, and Documents already do it too.

The genuinely net-new piece is the **MoC document model** (the authored page + sections + typed artifact-reference rows) — but it's **small and well-precedented**: the composition model (`focus_compositions`/`focus_templates`) is the structural analogue (authored ordered arrangements of typed references), and the orphan-tolerant-at-read pattern (edge-panel resolver, CompositionRenderer's "unavailable" fallback) is the witnessed answer to referential integrity. The **home dashboard is a new admin surface, not a Space** (Spaces are tenant-`User`-bound; `PlatformUser` has no preferences field — witnessed, this is the crux). **Rendering is reuse + ~80 LOC** (`Table` + `Icon` + `EmptyState` + `Panel` exist; a thin `LinkedTable` composes them). **Realm-agnostic-from-day-one is cheap and precluding-nothing** (the realm-agnostic-service pattern + three-tier scope even if the tenant tier starts empty).

**Net: MoC is a contained composition-and-routing arc, not a primitive build.** Cheapest first slice (recommended, §F): home dashboard + ONE vertical's MoC page + deep-links into the 4 already-parameterized builders — the whole model proven end-to-end on the narrowest real path before generalizing.

---

## A. THE DEEP-LINK TARGET (deep — the load-bearing reuse, VERIFIED)

Per-builder, against live source (`frontend/src/bridgeable-admin/`). Routes dispatch through `StudioShell` (`pages/studio/StudioShell.tsx` — `parseStudioPath` + the `EDITOR_PAGES` map + the `/studio/:vertical/:editor` scheme; `/visual-editor/*` redirects in). Query params thread through React Router unchanged.

| Builder | Route-param entry today | Classification | Evidence |
|---|---|---|---|
| **Workflows** | `?workflow_type=` + `?scope=` → loads that template | **EXISTS** | `WorkflowEditorPage.tsx:258-273` (the Builder-AI/runtime-editor deep-link; witnessed this session) |
| **Focus** | `?tier=` + `?core=` / `?template=` → loads that core/template | **EXISTS** | `FocusEditorPage.tsx:61-67` (`searchParams.get("tier"/"core"/"template")` → `selectedCoreId`/`selectedTemplateId` → child editors) — **spot-verified** |
| **Widget** | `/studio/widget-builder/:slug` → `widgetBuilderService.get(slug)` on mount | **EXISTS** | `components/widget-builder/WidgetBuilderPage.tsx:99,124` (`useParams` slug) |
| **Documents** | `?template_id=` → loads that template | **EXISTS** | `DocumentsEditorPage.tsx:94-108` (`searchParams.get("template_id")` → `selectedTemplateId` → `getTemplate`) — **spot-verified** |
| **Themes** | none — scope/vertical/mode via local-state dropdowns | **NEEDS-A-ROUTE** | `ThemeEditorPage.tsx` — 0 `useSearchParams` (verified); `themesService.resolve()` loader EXISTS, just unwired to a URL param |
| **Classes** | none — class via in-app browser | **NEEDS-A-ROUTE** | `ClassEditorPage.tsx` — 0 `useSearchParams` (verified); `componentClassConfigurationsService.resolve(className)` EXISTS, unwired |
| **Registry** | none — it's an inspector/browser, no single-artifact "load" | **N/A (inspector)** | `RegistryDebugPage.tsx` — no per-artifact editor entry; deep-link target is filters (`?type=`/`?search=`) at most |

**Verdict: thin routing layer.** 4 builders land an artifact from the route TODAY; 2 are copy-the-Focus/Workflow-pattern adds (~30–50 LOC each: `useSearchParams` → init state → write-back on selection); Registry isn't an artifact editor so it has no deep-link-to-open semantics (a row pointing at "the registry" is just a nav link, not an artifact-open). **The StudioShell dispatch needs no changes** — params already flow. The arc's deep-link cost is ~2 small per-builder wirings, not seven.

---

## B. THE MoC DOCUMENT MODEL (deep — net-new but small + precedented)

An authored MoC page = a page + ordered sections + ordered typed-reference rows `{builder, artifact_id, label, icon, order}`. Candidate substrates, against live source:

| Candidate | Verdict | Why (file:line) |
|---|---|---|
| **Vault (`VaultItem`)** | **FIGHTS** | `vault_item.py` — polymorphic instance container; `related_entity_*` is a SINGLE pointer (`:80-85`), not an ordered list of refs; `saved_views` stores ONE config in `metadata_json` (`saved_views/crud.py:257`), not reference rows. A MoC page is *N curated cross-builder pointers* — the Vault holds instances, not pointer-lists. |
| **Document model / blocks** | **FIGHTS** | `document.py` + the Documents-arc blocks are template-RENDERING-specific (Jinja/PDF output, `compile_to_jinja`); not a generic authored-page-of-references container. |
| **Composition (`focus_compositions`/`focus_templates`, `dashboard_layouts`)** | **CLOSEST ANALOGUE** | The structural match: authored, ordered `rows[].placements[]` of typed references (`component_kind`+`component_name`+grid), 3-tier scope-inherited, versioned (`focus_template.py:128 rows JSONB`; `focus_composition.py:133 deltas`). But the reference shape differs — placements point at *registered visual components by name*; an MoC row points at *a builder artifact by id* (`workflow_templates.id`, `focus_cores.id`, etc.). Reusing it would mean overloading `component_kind="artifact-link"` + stuffing `artifact_id` into prop_overrides — a fit-fight. |

**Smallest model: a net-new `moc_pages` table** (lean, NOT the composition machinery). The composition model proves the *shape is sound and conventional*, but an MoC page wants a purpose-built reference-row (`{builder, artifact_id, label, icon, order}` in JSONB sections) without the placement/grid/component-registry baggage. ~1 table + service + 5 CRUD endpoints + tests. (Type-B call B below: net-new `moc_pages` vs overload `focus_compositions` — I lean net-new for reference-shape clarity; flagged, not decided.)

**Referential integrity: NET-NEW, but the pattern is witnessed.** No substrate cascades on builder-artifact deletion today. The witnessed convention is **orphan-tolerant-at-read**: the edge-panel resolver + `CompositionRenderer` silently drop missing references (debug-log, render "unavailable") rather than cascade — `frontend/.../CompositionRenderer.tsx` runtime "unavailable" fallback; `edge_panel_inheritance/resolver.py:27-32`. Recommendation (Type-B): adopt orphan-tolerant-at-read (cheapest, matches convention) over write-time cascade — a deleted workflow's MoC row renders a "no longer available" state (a natural §18 surface) rather than requiring delete-time cleanup across every builder.

---

## C. HOME DASHBOARD — NEW SURFACE vs SPACE (the one open Type-B; recommendation, not decision)

**The crux, witnessed: Spaces are tenant-`User`-bound; the admin realm has no Space substrate.** `SpaceProvider` mounts in the tenant tree's `AppLayout` (`App.tsx`), NOT `BridgeableAdminApp`; Spaces persist in `User.preferences.spaces` (tenant identity) and **`PlatformUser` has no preferences field** (`platform_user.py`). The admin tree lands via `AdminLayout`/`StudioOverviewPage` with its own nav (`StudioRail`/`AdminHeader`), no per-admin-user workspace contexts.

**Recommendation: NEW ADMIN SURFACE, not a Space** — with the tradeoff stated:
- **Reuse Spaces** would require `PlatformUser.preferences` + cross-realm Space storage refactor (~150–200 LOC schema/service churn) to host a primitive built for *per-operator tenant* personalization (accent-switching, pins) that admin ops don't need.
- **New admin surface** (e.g. a landing at `/admin` / `/studio` overview) composes the existing `Panel`/`Icon`/`EmptyState` chrome, slots into the already-wired admin nav, **zero schema migration** (~80–120 LOC page). The admin realm is intentionally decoupled (CLAUDE.md admin-tree architecture) — honor the boundary.

The home dashboard's "links to MoC pages" content is itself just an MoC-style linked list — so the home surface and the MoC page **share the `LinkedTable` rendering** (§E) and differ only in role/data source, exactly as the model intends.

## D. REALM GENERALIZATION (survey — cheapest non-precluding design)

The same realm split that forced JCF its platform route applies. The cheapest design that doesn't preclude the tenant future, per the **realm-agnostic-service pattern** (CLAUDE.md "Realm-agnostic service layer"):
- **Service layer realm-agnostic from day one**: `moc_service` functions take `(db, scope, tenant_id|None, …)` operational primitives — no auth, no request state. Both an admin platform router (`/api/platform/admin/moc/*`, `get_current_platform_user`, `adminApi`) and a future tenant router (`/api/v1/moc/*`, `get_current_user`) call the same service. (The platform-themes service is the witnessed exemplar.)
- **Three-tier scope (`platform_default → vertical_default → tenant_override`) in the model from the start**, even if the tenant tier ships empty — matches every other Studio substrate; adding the tenant face later is a router + a populated tier, not a rebuild.
- **FK-less actor attribution** (`created_by`/`updated_by` as `VARCHAR(36)` not FK to a single user table) per the documented cross-realm pattern — so admin-`PlatformUser` and future tenant-`User` authorship both record without a schema fight.
- **Flag (would force a rebuild if ignored):** hardcoding `company_id` in the service, or admin-only audit FKs. Avoided by the above.

**Verdict: realm-agnostic-now is nearly free and precludes nothing** — the admin-first slice ships with the tenant future already structurally accommodated.

## E. RENDERING (survey — reuse + ~80 LOC)

The Notion-like linked table maps almost entirely onto shipped primitives: `ui/table.tsx` (semantic rows + hover/selected states), `ui/panel.tsx` (PanelChrome from craft-1a), `ui/empty-state.tsx` (the §18 quiet variant for empty/true-empty pages), `ui/icon.tsx` (the §7 Icon wrapper — the inline per-artifact icons land here directly). The one gap: `Table` has **no clickable-row abstraction** (rows are bare `<tr>`; the witnessed pattern is `SavedViewRenderer`'s `onPeek` wrapping the title cell in a button). **Build a thin `LinkedTable` (~80 LOC)** composing Table + Icon + a row-as-link wrapper + the EmptyState fallback. No new tokens. Reuse + light composition — not a net-new rendering system.

---

## F. TYPE-B CALLS (surfaced, not decided) + PHASING

1. **Home: new admin surface vs Space** — recommend new surface (C: Spaces are tenant-User-bound, PlatformUser has no preferences; reuse = ~150-200 LOC realm refactor vs ~80-120 LOC new page). Operator's open call.
2. **MoC persistence: net-new `moc_pages` vs overload `focus_compositions`** — recommend net-new (B: the reference shape {builder, artifact_id, label, icon} differs from composition's component_kind+name+grid; the inheritance machinery is overhead). Composition proves the shape is conventional, so either is viable.
3. **Deep-link route shape + the per-builder gaps** — 4 EXISTS, 2 NEEDS-A-ROUTE (~30-50 LOC each), Registry N/A. The route convention to settle: a uniform `?artifact=<id>` vs each builder's current bespoke param names (`workflow_type`/`core`/`template_id`/`:slug`) — a thin adapter in the link-builder can map MoC-row → each builder's existing param, OR the 2 NEEDS-A-ROUTE adds adopt a uniform param. Lean: a `deepLinkFor(builder, artifact_id)` helper that emits each builder's native param (no builder churn beyond the 2 adds).
4. **Referential integrity on artifact delete** — recommend orphan-tolerant-at-read (the witnessed convention: resolver drops/renders-unavailable) over write-time cascade. Cheapest + a natural §18 "no longer available" row state.
5. **Realm-agnostic-now vs admin-only-now** — recommend realm-agnostic service + 3-tier model from day one (D: nearly free, precludes nothing).
6. **The authored-arrangement editing UX** — how the operator builds an MoC page (add-link picker over the builders' artifacts? drag-reorder rows/sections?). This is the genuine net-new UX surface; scope it explicitly in Phase 1+ (the §18 + craft-1a/1b chrome covers the rendering; the *authoring* affordances — an artifact-picker that lists a vertical's workflows/focuses/etc. to drop as rows — is the design work).

### Proposed phasing (de-risk-then-render; prove the model on the narrowest real path)
- **MoC-1 — the end-to-end thin slice (RECOMMENDED first):** the `moc_pages` model + realm-agnostic service + admin CRUD; the home dashboard as a new admin surface; **ONE vertical's MoC page** authored (seeded, not yet operator-editable); the `LinkedTable` render; deep-links into the **4 already-parameterized builders** (Workflows/Focus/Widget/Documents). This proves click-row → builder-opens-with-artifact end-to-end with **zero per-builder work** — the whole model demonstrated on real seams before any generalization.
- **MoC-2 — the authoring UX:** the add-link picker + section/row arrangement (Type-B 6); operator builds an MoC page from scratch.
- **MoC-3 — fill the builder gaps + integrity:** wire the 2 NEEDS-A-ROUTE builders (Themes/Classes); orphan-tolerant render state; Registry/filter links.
- **MoC-4 (later, not now) — the tenant face:** the tenant router over the already-realm-agnostic service + the tenant-tier scope; "how a tenant views/customizes their platform."

---

**STOP.** Read-only; not committed (operator reviews; lands with the Phase 1 deliberation). One scope-honesty note: A+B went deep with direct file:line verification (deep-link claims spot-witnessed); C/D/E are surveys — confident on the witnessed crux facts (Spaces tenant-bound, primitives present, realm-agnostic pattern), lighter on the authoring-UX sizing (Type-B 6), which Phase 1 should scope before committing MoC-2's shape.
