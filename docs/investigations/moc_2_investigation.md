# Maps of Content — MoC-2 Scoping Investigation (Phase 0)

**Date:** 2026-06-26 · **HEAD:** `c89a039` · **Read-only** — no code, no canon, no commit, no dispatch.
**Target (operator intent, scoped-against not redesigned):** restructure the vertical MoC page to the Notion mockup — (1) typed COLUMNS (Theme / Focuses / Workflows / Widgets, each listing that vertical's artifacts of that type, all deep-linked) + (2) a database-style TASK TABLE where each row is a vertical's Bridgeable-default task showing the workflows + focuses it USES, each cross-linked.
**Method:** A + B deep with witnessed DB queries against `bridgeable_dev`; C/D/E survey. The operator's "I believe [the task entity] already [exists]" treated as a HYPOTHESIS and verified both directions.

---

## HEADLINE VERDICT

**The operator's load-bearing belief is FALSE, witnessed — and it resizes the arc.** A task entity exists abundantly (1,436 VaultItem `item_type='task'` + 5,401 legacy `tasks` rows), BUT it does **not** carry the relationships the mockup shows: there is no "workflows used" / "focuses used" association, no per-vertical "default task" catalog, and no `vertical` column on any task table. The only task→workflow link is `task_details.provenance_ref_*` — **singular**, pointing at a workflow **run / agent_job** (a runtime execution), never a workflow **template** (the deep-linkable builder artifact); and **zero** tasks reference a focus at all. The mockup's populated "Workflow Used / Focus's Used" columns are the operator's **model**, not persisted backend.

**So MoC-2 is NOT "mostly rendering."** The columns (Section B) genuinely are mostly rendering. But the task table requires **modeling that doesn't exist yet**: a vertical-default-task concept + task↔workflow_template + task↔focus_template relationships. **The arc gains a schema/relationship phase the operator did not expect** — exactly the `create_vault_order` / unwitnessed-resolver pattern the dispatch's epistemic warning named, caught here before a build assumed it.

**Net:** columns = a generated query + one routing gap (themes). Task table = model-the-relationships-first, then render. De-risk by proving the relationships persist + resolve before rendering anything.

---

## A. THE TASK ENTITY (deep — the load-bearing claim) — verdict: **EXISTS-WITHOUT-RELATIONSHIPS**

Two task entities exist (witnessed counts in `bridgeable_dev`):

| Entity | Rows | Shape |
|---|---|---|
| Legacy `tasks` | 5,401 | `task.py` Task model; 17 cols; single polymorphic `related_entity_type/_id` + `metadata_json`. **No** workflow/focus/vertical columns. |
| Task substrate (`vault_items` `item_type='task'` + `task_details`) | 1,436 | The v1 substrate (CLAUDE.md). `task_details` 21 cols; single `provenance_kind`/`provenance_ref_type`/`provenance_ref_id`. **No** workflow/focus/vertical columns. |

**Witnessed: the closest thing to a task→workflow link is provenance, and it fails the mockup's requirement on three counts.** `task_details.provenance_kind` distribution (witnessed):
- `workflow_step → workflow_run` (40), `workflow_step → agent_job` (39), `workflow_step → workflow_review_item` (19), `workflow_step → safety_program_generation` (15) — i.e. some tasks were *created by* a workflow execution.
- `manual_creation` (large majority), `anomaly_detection`, `integration_event`, `communication_inbound`, `scheduled_recurring`.
- **Zero `focus_completion` rows** — the substrate *defines* that provenance_kind (CLAUDE.md) but no task uses it. **No task references a focus.**

Provenance fails the mockup three ways:
1. **Singular, not plural.** One `provenance_ref_id` = the ONE thing that created the task. The mockup's "Workflow**s** Used" + "Focus's Used" are lists.
2. **Runtime execution, not template.** It points at a `workflow_run` / `agent_job` (an execution instance), NOT a `workflow_templates` row — which is what the Workflows builder edits and what the deep-link helper routes to. A column built on provenance would link to a *run*, which has no builder to open.
3. **Provenance ≠ "uses."** "Created by workflow X" is not "this default task uses workflows X, Y + focuses A, B." Different semantic; the mockup wants a definitional relationship.

**No task↔workflow and no task↔focus association tables exist** (witnessed: `information_schema` search returned NONE). **No `vertical` column** on `tasks` or `task_details` — so "a vertical's Bridgeable-**default** task" (a per-vertical template/catalog, the way default workflows/focuses are seeded per vertical) is **not modeled at all**; tasks are tenant-scoped runtime instances, not vertical-default templates.

**Verdict: the task entity EXISTS, but the mockup's task→(workflows-used, focuses-used) relationships and the per-vertical default-task catalog DO NOT.** This is the arc-shaper: MoC-2 gains a relationship-modeling phase + a vertical-default-task-catalog concept the operator's "it already exists" did not anticipate.

---

## B. THE TYPED COLUMNS (deep — mostly rendering) — verdict: **GENERATED QUERY + ONE ROUTING GAP**

**Per-vertical listing is a clean generated query.** Every owning registry has a vertical column (witnessed):

| Column type | Owning table | Vertical column | Rows (dev) |
|---|---|---|---|
| Theme | `platform_themes` | `vertical` | 0 (none seeded) |
| Focuses | `focus_templates` | `vertical` | 1 |
| Workflows | `workflow_templates` | `vertical` | 2 |
| Widgets | `widget_definitions` | `required_vertical` | 242 (mostly cross-vertical; filter by `required_vertical`) |

So the columns are best **generated** — query each registry filtered to the vertical, group by type. (Authored-regroup of the Phase-1 `moc_pages` reference rows is possible but incomplete: the Manufacturing seed authored 4 refs; a generated query lists *all* of a vertical's artifacts of each type. See C.)

**Deep-link coverage — 3 of the mockup's 4 columns are free; Theme is the gap.** The Phase-1 `mocDeepLink` helper covers `workflows / focuses / widgets / documents` (witnessed `case` arms). The mockup's four columns are **Theme / Focuses / Workflows / Widgets** — so focuses/workflows/widgets link with **zero new routing**, but:
- **Theme has no deep-link arm** in the helper, AND the Themes editor was flagged NEEDS-A-ROUTE in the Phase-0 MoC investigation (no per-artifact route param — scope/vertical/mode are local-state dropdowns). So the **Theme column needs the themes-deep-link wiring** (an MoC-3 item, pulled forward here).
- (`documents` IS covered by the helper but is NOT a mockup column — no rework, just unused for this layout.)
- Note: a vertical typically has ONE theme (its `vertical_default` row), so "Theme" may be a single reference, not a list — still needs the route to deep-link.

**Verdict: columns = a generated registry query (clean, all four vertical-filterable) + the themes-deep-link route gap.** Mostly rendering, as hypothesized — with the one honest routing add for Theme.

---

## C. AUTHORED vs GENERATED (the model question MoC-2 forces) — survey + recommendation

Phase 1 settled MoC pages as **authored** (operator arranges flat reference rows in `moc_pages.sections`). MoC-2 introduces denser content; per piece:

- **Typed columns → recommend GENERATED** (registry query per vertical, §B). Authored placement of every artifact into a column is high-friction and goes stale as builders add artifacts; a generated query is complete + self-maintaining. The vertical columns make it clean.
- **Task table → RENDERS the task relationships** (generated from the entity) — *once they exist* (§A says they don't). It cannot render authored rows faithfully to "the real task entity the operator wants"; it must render the modeled relationships.

**Consistency flag (a real Type-B):** the vertical page would then be **mixed** — Phase-1 authored reference-rows + generated columns + a generated-from-entity task table on one page. The operator must decide the coherent end-state: (a) the vertical page becomes **mostly generated** (columns + task table auto-derived), and the Phase-1 authored reference-rows are retired or demoted to a curated "pinned" section; or (b) authored refs and generated columns **coexist** (risking redundancy — the same artifacts in an authored row and a generated column). Recommend (a): generated columns + generated task table as the page body, authored refs become an optional curated overlay — but this revisits the Phase-1 "authored" settlement and should be an explicit decision, not a drift.

---

## D. THE TASK TABLE RENDERING (survey) — verdict: **NEW multi-column component, not a LinkedTable extension**

`LinkedTable` (Phase 1) is a linked-**row** primitive: per row = icon + label + single type-tag + one deep-link. The mockup's task table is a **multi-column relational** grid: columns = Frequency, Workflow Used, Focus's Used, Type, Description — where the **Workflow Used** and **Focus's Used** cells each render (potentially multiple) deep-linked artifact references.

That is structurally richer than LinkedTable (multiple deep-linked chips per cell; several typed columns). Extending LinkedTable would distort its single-label-per-row contract. **Recommend a new component** (a relational table whose specific cells render lists of deep-linked artifact "chips"). The cross-link cells **reuse the Phase-1 `mocDeepLink` helper** (workflow cell → workflow builder, focus cell → focus builder — both covered, witnessed). Size: a moderate new component, but its **data depends entirely on §A's relationships existing** — so it cannot be built until MoC-2a models them.

---

## E. TYPE-B CALLS + PHASING (surface, don't decide)

**Type-B calls:**
1. **The task-entity verdict (THE arc-shaper):** exists-without-relationships (§A, witnessed). The arc gains (a) a per-vertical **default-task catalog** concept and (b) **task↔workflow_template + task↔focus_template** relationships. The operator's "it already exists" is false for the relationships — confirmed both directions.
2. **What "vertical default task" IS:** a new catalog (seeded per vertical, like default workflows/focuses), modeled how? A new `default_tasks` table (vertical + frequency + type + description) + association tables to `workflow_templates` / `focus_templates`? Or extend the existing task substrate with a vertical-default tier + the associations? (Leans: a purpose-built default-task catalog, since runtime `tasks`/`task_details` are instance-scoped and shouldn't carry vertical-template semantics.)
3. **Authored vs generated split + page coherence (§C):** columns generated, task table generated-from-entity, Phase-1 authored refs retired/demoted vs coexisting. Revisits Phase-1's "authored" settlement.
4. **Columns: registry-query (generated) vs authored-regroup (§B):** recommend registry-query.
5. **Task-table component: new vs LinkedTable-extension (§D):** recommend new multi-column component; cross-links reuse the deep-link helper.
6. **Theme column routing (§B):** themes deep-link is absent (NEEDS-A-ROUTE); the Theme column needs it wired (pulled forward from MoC-3).

**Proposed phasing — ONE arc (columns + task table together, per operator), de-risk ordering:**
- **MoC-2a — model the task relationships (THE unexpected, load-bearing phase).** Decide & build the vertical-default-task catalog + task↔workflow_template + task↔focus_template associations. **De-risk first (assembly-test discipline):** prove a seeded default task persists + its workflow/focus references resolve to real builder artifacts (witnessed row + witnessed relationships) BEFORE any rendering. Everything downstream hinges on this; it is the part the operator's "already exists" hid.
- **MoC-2b — typed columns (low-risk rendering).** Generated registry query per vertical (themes/focuses/workflows/widgets) + wire the themes deep-link (the Theme column's routing gap). Reuses the deep-link helper for the other three. No schema risk.
- **MoC-2c — the task table (depends on 2a).** New multi-column relational component rendering the 2a relationships; cross-link cells via the deep-link helper.
- **Sequence rationale:** 2a first because it's the risk AND the surprise (schema/relationship modeling the operator didn't expect); 2b is independent low-risk rendering that could even land first for a visible win; 2c last (consumes 2a). If the operator wants the *visible* win soonest, 2b → 2a → 2c; if de-risk-first, 2a → 2b → 2c.

**The resize, stated plainly:** the operator scoped MoC-2 expecting "render a task entity that already relates to workflows/focuses." Witnessed reality: that entity's relationships (and the per-vertical default-task notion) do not exist. MoC-2 is therefore a **schema/relationship arc (2a) + a rendering arc (2b/2c)**, not a pure rendering pass — and it remains MoC-2, post-September queue, per the held line.

---

**STOP.** Read-only; not committed (operator reviews; lands with the Phase-1 deliberation). Scope honesty: A + B went deep with witnessed `bridgeable_dev` queries (task counts, provenance distribution, column introspection, association-table search, deep-link helper arms, per-vertical filterability); C/D/E are survey/recommendation grounded in those witnessed facts + the Phase-1 model. The one fact only a Railway-side check could add — whether *staging* (vs dev) holds different task data — does not change the schema verdict (the absence is structural: no relationship columns, no association tables, no vertical column exist in the migration-built schema).

---

## PHASE 0 COMPLETION (2026-06-29) — resolved schema + buildable assembly-test-first plan

**HEAD `9dcbb3d`** (MoC Phase A + A.1 + A.2 shipped: the per-type cards are live full-page on staging). This completes the Phase-0 scoping into a concrete, phased, buildable plan. Still **read-only — no build, no migration, no seed.**

**Context shift since the original Phase 0:** Phase A shipped the typed cards reading the **authored** `moc_pages.sections` refs (grouped by builder), NOT a registry query. So §B/§C's "generated columns" question is **moot** — the cards are authored, and the task table will likewise read an **authored catalog** (below). The page is coherently authored/seeded content (cards from `moc_pages`, table from the new catalog) — no registry-generation, no Phase-1-settlement revisit needed.

### Q1 — "Task" is a NEW vertical-catalog concept. CONFIRMED (the bigger-2a flag fires).
The Notion rows ("Funeral Home Billing", "New Legacy Order") are **named recurring automations per vertical** — a catalog, not the 6,837 instance-task rows (`tasks` 5,401 + `vault_items` task 1,436), which are runtime instances ("review invoice #123"). The table does **NOT** read existing task rows. It needs a **new vertical-default task-catalog table**. This is the load-bearing 2a — a new table + a join + seed enrichment, not "add two join tables to an existing entity."

### Q2 — the relationships (minimal schema). ONE workflow (FK column) + MANY focuses (join table).
Per the Notion model (a task runs ONE workflow, opens MULTIPLE focuses — "New Legacy Order" → Legacy Generation + Decision Triage):

**New table `moc_task_catalog`** — the vertical-default task catalog. Mirrors `moc_pages`' scope model for consistency:
| col | type | note |
|---|---|---|
| `id` | VARCHAR(36) PK | uuid4, convention |
| `scope` | VARCHAR | `platform_default` / `vertical_default` / `tenant_override` (mirror moc_pages) |
| `vertical` | FK → `verticals.slug` | per the post-r95 new-table convention (siblings use String; new table uses the FK) |
| `tenant_id` | VARCHAR(36) NULL FK → companies.id | tenant_override tier (null for vertical_default) |
| `name` | VARCHAR | "Quote → Pour Run", etc. |
| `icon` | VARCHAR NULL | lucide name |
| `frequency` | VARCHAR | **free-form** ("End of Month", "On demand") — NOT derivable from workflow_templates (no trigger cols there) |
| `task_type` | VARCHAR | **free-form** → frontend pill, color-mapped ("Accounting", "Funeral Service Operations") — no taxonomy table |
| `description` | TEXT | |
| `workflow_template_id` | VARCHAR(36) NULL FK → `workflow_templates.id` | the ONE workflow; nullable (a task may have none) |
| `display_order` | INT | |
| `is_active` | BOOL | |
| `created_at`/`updated_at` | timestamptz | + FK-less actor cols, per the `moc_pages` precedent |

**New join table `moc_task_catalog_focuses`** — task↔focus_template (MANY):
| col | type | note |
|---|---|---|
| `task_id` | VARCHAR(36) FK → `moc_task_catalog.id` (ON DELETE CASCADE) | |
| `focus_template_id` | VARCHAR(36) FK → `focus_templates.id` | the SAME id the cards deep-link to |
| `display_order` | INT | pill order |
| | | composite PK `(task_id, focus_template_id)` |

**ONE migration** (`rNNN_moc_task_catalog`) creates both tables. No other schema change. (Workflow is an FK column, not a join — Notion shows one workflow per task.)

### Q3 — Type + Frequency = free-form strings (no new taxonomy). RESOLVED.
- **Frequency** — free-form VARCHAR. `workflow_templates` has **no** trigger/cron columns (witnessed; triggers live on the runtime `workflows` table, not templates), so frequency can't be derived from the deep-link target. The Notion values are descriptive labels → store the label.
- **Type** — free-form VARCHAR → frontend renders a colored pill (a small `TASK_TYPE_COLORS` map with a neutral fallback). No taxonomy table exists for "Accounting / Funeral Service Operations" (witnessed: only product/kb categories) and one isn't warranted for a handful of curated types.

### Q4 — deep-link reuse. FULLY CONFIRMED (witnessed against the resolver).
The MoC resolver `_resolve_workflow`/`_resolve_focus` (`maps_of_content/service.py`) key on `workflow_templates.id` / `focus_templates.id` and build the exact `routing` the cards' `mocDeepLink` consumes (workflow → `workflow_type`+`scope`; focus → `template_slug`+`scope`, deep-link via `tier=2&template=<id>`). So the catalog storing **template-row ids** means the table's Workflow cell + Focus pills resolve through the **same path** → **byte-identical hrefs to the cards**. A focus pill in the table and the focus entry in the Focuses card open the same builder at the same artifact. **Zero new deep-link routing.** Both FK targets are `VARCHAR(36)` (confirmed).

---

### THE PHASE PLAN (assembly-test-first, the JCF-1 / backend-arc discipline)

**MoC-2a — the schema + the assembly test (THE load-bearing phase). NEEDS A MIGRATION + SEED ENRICHMENT.**
- **Migration** `rNNN_moc_task_catalog`: `moc_task_catalog` + `moc_task_catalog_focuses` (above). The arc's one schema change.
- **Service layer** (realm-agnostic, under `app/services/maps_of_content/` or a sibling): catalog CRUD + a `resolve_task_catalog(db, vertical)` that, per row, resolves `workflow_template_id` → `_resolve_workflow` and each `focus_template_id` → `_resolve_focus` (REUSE the existing resolvers) → returns rows with the same `{label, routing}` shape the cards use, plus type/frequency/description.
- **ASSEMBLY TEST FIRST (before any UI — the JCF-1 discipline):** seed a `moc_task_catalog` row with `workflow_template_id` = a real `quote_to_pour` template + two `moc_task_catalog_focuses` → assert it **round-trips through the real models**: the row persists; the workflow resolves to real `workflow_type`/`scope` routing; **both** focuses resolve to real focus routing; the resolved routing equals what `mocDeepLink` would produce for the cards. This proves the relationship model + deep-link reuse **before rendering anything** — the part the operator's "it already exists" hid.
- **Seed enrichment (REQUIRED — the table is empty otherwise):** add 2-3 manufacturing task-catalog rows to `seed_moc_manufacturing.py` (or a new `seed_moc_task_catalog.py`), referencing the real seeded artifacts (`quote_to_pour` workflow + `job-coordination` focus, skip-if-missing like the existing seed). Idempotent, platform-canonical (no demo guard) — same discipline as the existing MoC seed.
- **Witness:** assembly test green + a witnessed `bridgeable_dev` row whose workflow + 2 focuses resolve to live builder routing.
- **Defers:** all rendering; the read API (2b); the table component (2c).

**MoC-2b — read API + typed cells (deep-link wiring, low schema risk).**
- **Backend:** admin-realm read endpoint (mirror `/api/platform/admin/moc/read`) returning the vertical's resolved task catalog (reuses 2a's `resolve_task_catalog`).
- **Frontend:** service + types fetch the catalog; build the relational cell renderers — Workflow cell → `mocDeepLink(workflows)` (reuse), Focus pills → `mocDeepLink(focuses)` per focus (reuse), Type → color-mapped pill, Frequency → label.
- **Witness:** a test asserting a focus pill's href === the same focus's card-entry href (proves the table and cards link to the identical artifact) + the cells render type/frequency.
- **Defers:** the table layout (2c); authoring.

**MoC-2c — the task table component (the Notion-style database view under the cards). VISUAL WITNESS REQUIRED.**
- **New multi-column relational component** (NOT a LinkedTable extension — §D): columns Task (name+icon) / Frequency / Workflow Used (deep-link) / Focus's Used (deep-link pills) / Type (pill) / Description. Rows = the vertical's resolved catalog (2b). Mounted **under** `MoCTypeCards` in `MoCPage` (the A.1 full-page surface; the empty lower region the cards left is where this lives).
- **Visual witness (required, like A/A.1/A.2):** live local render of manufacturing — the table under the cards, Workflow/Focus cells are live links/pills opening the right builders, Type pills colored, on the full-page surface.
- **Defers:** **authoring** (adding/editing catalog rows via UI) — read-only render first; authoring is a later MoC-2 sub-phase (mirrors Phase 1 deferring row-authoring to MoC-2). Orphan-tolerance per §18 (a catalog row whose workflow/focus was deleted renders muted, never a dead link — reuse the resolver's `available` flag).

### MIGRATIONS + SEED — flagged plainly
- **Migration: exactly ONE** — `rNNN_moc_task_catalog` (two tables) in MoC-2a. No other schema change across the arc.
- **Seed enrichment: YES, REQUIRED** — manufacturing task-catalog rows in MoC-2a (the table renders empty without them). Scoped to 2a; idempotent + platform-canonical.

### STOP-discipline answers
- **"Task" is genuinely a NEW concept** (vertical task-catalog), NOT existing rows — so **2a is the bigger "new table + join + seed," not "add two join tables to an existing entity."** Stated plainly per the STOP rule.
- **Relationships are NOT more entangled than the Notion model** — there is NO pre-existing task↔workflow_template / task↔focus_template anywhere (the only task→workflow link is singular runtime provenance, §A, which the table does not use). Clean slate; the model above is minimal and complete.
- **No build, no migration, no seed performed.** The plan is the deliverable.

**STOP.**
