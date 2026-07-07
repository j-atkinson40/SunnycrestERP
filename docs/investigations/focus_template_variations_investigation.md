# Focus Template Variations + Offered Updates — Investigation / Scoping

**Date:** 2026-07-07 · **HEAD at read:** `bed9a58` · **Read-only — no build.**

Operator direction under scope: default focus templates surface on the platform MoC
(Focuses card); clicking a default opens a fork menu (edit-the-default with blast-radius
framing vs create-a-variation); variation creation is a guided flow (name → vertical(s),
plural → task wiring → editor); inheritance is **offered updates** (software-update
model: opt-in propagation with change legibility), platform→vertical this arc, designed
level-generic. Focuses first; workflows/widgets/documents inherit the pattern later.

---

## 1. The existing tier + version system (the reuse map)

### 1.1 The three tiers, precisely

```
focus_cores            Tier 1 — the canonical SHAPE. Code-registered component
                       (registered_component_kind/name → e.g. SchedulingKanbanCore)
                       + chrome blob + canvas/geometry defaults. scope-less;
                       identity = core_slug (partial unique on is_active=true).
    ← focus_templates  Tier 2 — a USE-CASE arrangement of ONE core + accessory
                       rows. scope ∈ {platform_default (vertical NULL),
                       vertical_default (vertical NOT NULL, FK verticals.slug)}
                       — CHECK-enforced correlation. Carries: rows (placements
                       JSONB), canvas_config, chrome_overrides, substrate,
                       typography. Identity = (scope, vertical, template_slug),
                       partial unique on is_active=true.
        ← focus_compositions  Tier 3 — per-tenant DELTA (hidden_placement_ids,
                       additional_placements, geometry/order overrides,
                       substrate/typography/chrome override keys). Keyed
                       (tenant_id, inherits_from_template_id).
```

**"Inheritance" today is live-pointer, not copy.** A Tier 2 template stores
`inherits_from_core_id` + `inherits_from_core_version`, but the resolver
(locked decision 2) **ignores the version pin** and always resolves the ACTIVE
core — repaired in C-2.1.2 to translate stale core id → `core_slug` → active row.
Chrome/substrate/typography cascade is **field-level by key-presence** (Tier 3 >
Tier 2 > Tier 1; explicit None overrides). Template `rows` (accessories) are NOT
inherited from anything — they're the template's own authored content; the core
appears in them as the single `is_core=true` placement injected at resolve time.

**The staging version numbers** (core v15, `scheduling-fh` vertical_default v25 per
deploy logs) are editor churn on staging. Local dev currently holds different seed
content (`job-coordination` core v1 + a **platform_default-scope Tier 2 template**
v1 — proof the platform_default template tier is real, not hypothetical).

### 1.2 Version mechanics — what an offer's delta can be built from

- **Every non-session save version-bumps**: deactivate prior active row + insert a
  fresh row at `version+1` **with a new UUID**. Prior versions are **retained as
  full-row snapshots** (`is_active=false`). Same pattern on cores (r102) and
  templates (r103).
- **Edit-session collapse** (C-2.1.2): saves carrying the same `edit_session_id`
  within 5 minutes mutate in place — so versions ≈ edit sessions, not keystrokes.
  Still: staging's v25 shows sessions accumulate fast. **A "version" is NOT a
  release** — this shapes the patch-notes recommendation (§5.1).
- **No changelog text exists** on focus rows (document templates have a
  `changelog` column; focus tables don't). No diff machinery exists.
- **Verdict on STOP finding (b): version history EXISTS.** Full snapshots are
  retained, so "default moved v15→v16, here's the delta" is **derivable** by
  diffing two retained rows. No retention lift needed. What's missing is only
  the diff *renderer* and the release boundary.

### 1.3 Identity: slugs are stable, row ids rotate — a design canon AND a live hazard

Because version bumps mint new row ids, **anything referencing a focus template by
row id decays on edit**:

- **MoC card refs + task-catalog focus joins** store `focus_template_id` = a row id
  captured at seed/author time. `_resolve_focus` (maps_of_content/service.py) looks
  up by id: an old row resolves `available=False` — the pill dims. On staging (25
  bumps) authored refs are already pointing at inactive rows unless re-seeded.
- **Tier 3 compositions** key on `inherits_from_template_id` = a row id; the
  resolver looks up the composition at the ACTIVE template's id — a template bump
  **orphans tenant customizations** (pre-existing hazard, out of this arc's cause
  but directly in the offered-updates blast zone; flagged in §7 hazards).

The repair pattern already exists: C-2.1.2's slug translation (stale id → slug →
active row). **The plan adopts slug-keyed lineage as canon** for everything new
(variation provenance, the verticals join, offers), and Phase V-1 includes the
cheap `_resolve_focus` hardening (id → (scope, vertical, slug) → active row
rebind) so MoC focus pills stop decaying.

### 1.4 Customization detection — granularity verdict (gates §5.3 apply semantics)

Four detection mechanisms exist, at different granularities:

| Mechanism | Where | Granularity |
|---|---|---|
| Option A seed state machine (`skipped_customized`) | document-template seeds (Phase 6/8b/8d.1/calendar 5.1) | **whole-template** — proxy = "more than one version row exists"; platform_update = content-compare + deactivate v1/create v2 |
| Seed drift-detect | `seed_focus_template_inheritance` | declared-fields compare (chrome / substrate / typography / display_name blobs) |
| Chrome/substrate/typography cascade | resolver | **field-level** — key-presence per tier; an empty `chrome_overrides` = "fully inheriting" |
| Tier 3 deltas | focus_compositions | **part-level by construction** — hidden/additional/geometry/order keyed on stable `placement_id`s |

**Verdict on STOP finding (a): detection is NOT whole-template-only.** The
override families (chrome/substrate/typography) are field-granular by key-presence,
and template `rows` carry **stable `placement_id`s** ("stable across edits" per the
model doc) — so a **per-placement diff** between two retained snapshots is
buildable (added / removed / geometry-changed / prop-changed placements).
Merge-uncustomized-parts is feasible per family; the full recommendation is §5.3.

### 1.5 What already exists that the flow needs (the reuse inventory)

- `create_template(...)` — the variation-creation primitive (versions on slug
  collision; captures core version pin at create).
- `admin_core_usage` + `admin_template_usage` endpoints — **the blast-radius data
  for the fork menu already exists** (which templates inherit this core / which
  compositions reference this template).
- Full admin CRUD at `/api/platform/admin/focus-template-inheritance/*` (cores,
  templates, compositions), hybrid platform/tenant auth.
- The Studio Focus Builder (edit deep-link target) + `listFocusTemplateOptions()`
  (the 2b picker's feed) + `ArtifactPicker` multi-select.
- MoC: `MoCTypeCards` renders any seeded page's cards (H-2); `admin_patch_task`
  replaces a task's focus set; `upsert_task`'s focus-set replace semantics;
  page-section write endpoints (`admin_create_page` / update).
- The workflow precedent: `tenant_workflow_forks` + `pending_merge_available` +
  accept/reject — the platform's existing offered-update-shaped machinery (at
  tenant level, take-wholesale only, no patch notes). Instructive, not reused
  directly; the new offers system is designed to eventually absorb it (§6).

---

## 2. Multi-vertical variations — schema verdict

`focus_templates.vertical` is a **single column** (String FK → verticals.slug) with
a CHECK correlating scope↔vertical and a partial unique on (scope, vertical,
template_slug) active. One variation serving multiple verticals does **not** fit
today. **STOP finding (c) confirmed: a migration is needed.**

Options:

- **(a) RECOMMENDED — slug-keyed join table.** `focus_template_verticals
  (template_slug, vertical)` unique pair, vertical FK → verticals.slug.
  Slug-keyed (not row-id-keyed) so join rows **survive version rotation** with
  zero churn — the slug-stable-identity canon (§1.3). The variation row itself
  keeps `scope='vertical_default'` + `vertical=<primary/home vertical>` (the
  vertical the operator picked first), preserving the CHECK unchanged;
  additional verticals live in the join. Resolver's `_find_active_template`
  gains one branch: after the exact (slug, vertical) miss, look up slugs joined
  to the requested vertical. MoC surfacing reads the join for "which vertical
  MoCs show this variation."
- (b) Copies-per-vertical — rejected: breaks "one artifact, several homes" (an
  edit must show in all its verticals); N rows = N divergent artifacts.
- (c) JSONB verticals array on the row — rejected: loses the FK, complicates the
  partial-unique identity tuple, worse queryability for "all variations visible
  in vertical X."

A one-vertical variation authors a single join row — the join table is the
uniform path (no special casing).

---

## 3. The platform MoC Focuses card — confirmed cheap, one addition

The platform page (H-2) is a seeded `MoCPage` whose cards `MoCHome` renders via
`toTypeCards(page)` — same composition as vertical maps. A Focuses card =
one more section authored by `seed_moc_platform` with builder refs. Two notes:

- **Cores need a resolver key.** MoC's `BUILDERS` resolves `focuses` against
  `focus_templates` only. The card is to show **the Tier 1 core defaults** (plus
  any platform_default-scope templates, which resolve already). Add a
  `focus-cores` builder resolver (~15 lines, mirrors `_resolve_focus`; routing =
  core_slug → Studio Focus Builder) OR list only platform_default templates.
  **Recommend adding the resolver** — the operator's model is "the canonical
  shapes live at platform level," and cores are the canonical shapes.
- **Ref-staleness hardening rides along** (§1.3): `_resolve_focus` rebinds an
  inactive id to the active row at the same (scope, vertical, slug) — labels stay
  live and pills stop dimming under editor churn. Same trick for the core
  resolver from day one.

---

## 4. The fork menu + the guided variation flow — mapped against existing machinery

### 4.1 Fork menu (frontend-only; no backend change)

Clicking a default's pill on the platform Focuses card → a small menu:

- **"Edit the default"** — deep-links the existing Studio Focus Builder. The
  blast-radius framing is populated from the **existing** usage endpoints
  (`admin_core_usage`: N templates inherit this core; `admin_template_usage`:
  N compositions) — "changes affect all N inheritors" rendered in the menu
  item's description, not a separate screen.
- **"Create a variation"** — opens the guided flow.

### 4.2 Guided variation flow, step by step

| Step | Machinery | Status |
|---|---|---|
| Name it | slug generated from name; `create_template` takes display_name + slug | exists |
| Scope to vertical(s), multi-select | verticals list (verticals table, r95); **join rows written** | join table is new (§2 migration); picker UI is standard |
| Content at creation | forking a **core**: `create_template(inherits_from_core_id=core, rows=[])` — chrome/substrate/typography start empty/default = fully-inheriting. Forking a **platform_default template**: copy its rows/canvas/override blobs into the new row (placement_ids preserved verbatim — they're what per-placement diff keys on later) | exists (create_template); the copy is trivial service code |
| Provenance | **new columns** on focus_templates: `variation_of_slug` (nullable String) + `variation_source_version` (nullable int) — slug-keyed lineage; for core-derived variations the existing `inherits_from_core_id/_version` pin already IS the provenance | migration (same one as §2) |
| Task/workflow wiring | the 2b picker edits task→focuses (`admin_patch_task` replaces `focus_template_ids`). This flow is the REVERSE (focus→tasks): the join API has no reverse write. **Recommend a small endpoint** `POST /admin/moc/focus-wiring {template_slug, task_ids}` that appends the variation to each task's focus set atomically (read-modify-write per task under one transaction). Frontend-looping admin_patch_task works but is non-atomic + racy against concurrent edits | small backend addition (~40 lines + tests); reuses upsert semantics |
| Land in the editor | deep-link with the new template id | exists |

### 4.3 Where the variation surfaces (the keystone rule)

On each chosen vertical's MoC Focuses card, **auto-authored at creation** — the
flow appends a `{builder:"focuses", artifact_id, label}` row to each vertical's
MoCPage focuses section (write path: the existing page-update endpoint /
service). This mirrors what the demo seeds did by hand and is the "creation
authors the map" discipline. The task-table focus cells populate independently
via the wiring step (task-catalog joins resolve through the same BUILDERS path,
byte-identical labels).

---

## 5. The offered-updates flow — the genuinely new system

### 5.1 Version + delta + patch-notes provenance

**Recommendation: publish-boundary + authored-with-derived-fallback.**

Versions are edit sessions (§1.2) — offering on every save would spam v25-style
churn. Introduce an explicit **"Publish update"** action on defaults (a Studio
button on cores + platform_default templates):

1. Marks the current active version as the new **offered baseline**.
2. Prompts for **patch notes** (authored — intent). Skippable; when skipped the
   offer renders the **derived diff** alone (mechanics).
3. Creates one offer per downstream variation (per §5.4's table).

The derived diff is computed from the two retained snapshots (baseline the
variation last accepted → the newly published version): per-placement rows diff
(added/removed/geometry/prop changes keyed on `placement_id`), field diffs for
chrome/substrate/typography, canvas_config key diffs. Between publishes, edits
accumulate silently — matching the software-update model (releases, not commits).
This adds one column to focus_cores + focus_templates: `published_version`
(nullable int) — or equivalently the offers table records the baseline; the
column keeps "unpublished changes exist" cheap to badge in Studio.

### 5.2 The offer surface

**Recommendation: the MoC badge as primary + an editor banner as the act surface.**

- **Primary — a badge on the variation's pill** on its vertical MoC Focuses card
  (and its task-table focus cells): the map is where state lives (the same
  argument that put Live pills and fires on the map). Clicking the badged pill's
  menu shows the offer: patch notes + derived diff + Accept / Decline / Later.
- **Secondary — the Focus Builder banner** when the variation is opened: "The
  default this derives from moved v15 → v17 — review update." Same offer object.
- **Not the fires/notification surface** for v1: offers aren't fires; muddying
  the runs log with governance state would cost legibility. Revisit if operators
  miss badges in practice.

### 5.3 Apply semantics — gated by §1.4's granularity verdict

Detection is **mixed-granularity**, so apply is per-family, not one rule:

- **Chrome / substrate / typography (field-granular):** for core-derived
  variations this is already solved by the cascade — the variation's own override
  keys win, inherited keys flow — so **accepting = moving the version pin** and
  the field-merge happens naturally at resolve time. Zero merge UI needed.
- **Rows / accessories (placement-granular):** placement_id-keyed three-way diff
  between (baseline snapshot, new default snapshot, variation's current rows):
  placements the default added/removed/changed that the variation never touched
  apply cleanly; conflicts (the variation moved/removed the same placement)
  surface as **diff-and-choose** rows in the offer panel. v1 can ship a simpler
  cut honestly: cleanly-appliable changes listed with one Apply, conflicted ones
  listed as "kept yours" — no interactive per-row picker until evidence demands
  it.
- **Take-new-wholesale** stays available as an explicit "Reset to default"
  action (safe only when the variation has no own-content; the button says what
  it destroys).

**The resolver change this rides on:** honoring the version pin — exactly the
"v2 Option B (versioned cascade) lands additively here" seam the resolver's own
docstring reserves, using the `inherits_from_core_version` column that has been
waiting since r96. Pin-honoring applies to offer-enrolled variations only;
templates without provenance keep today's live-cascade (no behavior change for
existing content). Accepting an offer = move the pin + apply the rows merge +
record acceptance.

### 5.4 The offers table — level-generic by construction (§6)

New table `artifact_update_offers` (migration):

```
id · artifact_type ('focus_core' | 'focus_template' | later: 'workflow_template' …)
source_slug · source_version_from · source_version_to
target_kind ('focus_template' | later: 'focus_composition' tenant tier …)
target_slug (+ target_vertical for disambiguation) · target_tenant_id (NULL this arc)
patch_notes (authored, nullable) · derived_diff (JSONB, computed at publish)
status ('pending' | 'accepted' | 'declined' | 'superseded')
created_at · decided_at · decided_by
```

- A newer publish **supersedes** older pending offers for the same target (one
  live offer per edge — the catalog-fetch supersede semantics, proven in 8d).
- **Declined = dismissible-but-recallable:** status `declined`, the badge drops,
  but the version gap persists on the pill's menu ("derived from v15 · default
  is v17 · review") — recallable, never nagging. A later publish creates a fresh
  pending offer (cumulative diff from the last-accepted baseline, not from the
  declined one).
- The chain is level-generic: platform→vertical this arc (source = core or
  platform_default template, target = variation); tenant-level later plugs
  `target_kind='focus_composition'` + `target_tenant_id` with zero schema change.

### 5.5 Blast-radius framing on "edit the default"

With offers in place, editing a default's consequence CHANGES: live-cascade
families still propagate immediately (chrome et al. for pin-less templates);
pin-honoring variations move only on accept. The fork menu's blast-radius copy
comes from usage counts + pin status ("3 variations — 2 will be offered this
update, 1 live-inherits").

---

## 6. Generalization guard — what's generic vs focus-specific

| Generic (artifact_type as parameter) | Focus-specific |
|---|---|
| `artifact_update_offers` table + offer service (publish/list/accept/decline/supersede) | the diff builder (placement_id rows diff; chrome-family field diff) |
| The fork-menu component (label/blast-radius/actions injected per artifact type) | variation creation (`create_template`, content copy, core pin) |
| Publish-with-patch-notes UI shell (Studio button + notes prompt) | pin-move semantics (`inherits_from_core_version`, `variation_source_version`) |
| MoC pill badge plumbing (BUILDERS-keyed pending-offer counts in card resolution) | the focus-wiring endpoint (task join) |
| The guided-flow shell (name → scope → wire → land-in-editor steps) | verticals join table (`focus_template_verticals` — workflows may reuse the pattern, not the table) |

**Workflows note:** `workflow_templates` already ships locked-to-fork +
`pending_merge_available` (take-wholesale, no patch notes, tenant tier). When
workflows adopt this pattern, the offers system should absorb that flow (its
accept/reject becomes an offer with an empty diff renderer initially). **Do not
unify now** — flagged so nobody builds a second parallel offer system.

---

## 7. Phased plan + honest sizing

### Phase V-1 — the card, the fork menu, the variation flow (mostly existing machinery)

1. Migration `r1XX`: `focus_template_verticals` join (slug-keyed) +
   `variation_of_slug`/`variation_source_version` columns on focus_templates.
2. `focus-cores` MoC builder resolver + the `_resolve_focus` active-row rebind
   hardening (fixes live ref decay).
3. `seed_moc_platform`: Focuses section (Tier 1 cores + platform_default
   templates), idempotent per the H-2 seed's operator-rename-preserving pattern.
4. Fork menu on default pills (usage-endpoint blast radius) + guided variation
   flow (name → verticals multi-select → task wiring → editor deep-link).
5. `POST /admin/moc/focus-wiring` (focus→tasks batch) + auto-authoring of the
   variation's refs onto each chosen vertical's MoC Focuses card.
6. Resolver: `_find_active_template` join-table branch.

**Sizing: ~2 build sessions.** Risk: low — every step leans on shipped machinery;
the join-table resolver branch is the only resolver touch and it's additive.

### Phase V-2 — offered updates (the genuinely new system)

1. Migration: `artifact_update_offers` + `published_version` columns.
2. Publish action (Studio button on cores + platform_default templates; patch
   notes prompt; offer creation + supersession).
3. Derived-diff builder (snapshot pairs → placement/field diff JSONB) + the
   offer panel renderer.
4. Pin-honoring resolver branch (Option B seam) for provenance-carrying
   variations; accept = move pin + clean-apply rows; decline = recallable gap.
5. MoC pill badges (pending-offer counts in card read shape) + Focus Builder
   banner.

**Sizing: ~2–3 build sessions** (the diff builder + apply semantics is the bulk;
the offer CRUD + badges are routine). Ship 4's apply as clean-apply +
kept-yours-listing first; interactive per-placement choose only on evidence.

### Migrations flagged

- V-1: `focus_template_verticals` + two provenance columns (one migration).
- V-2: `artifact_update_offers` + `published_version` on focus_cores +
  focus_templates (one migration).

### Hazards / adjacent findings surfaced (not this arc's build)

- **Tier 3 composition orphaning** (§1.3): template version bumps strand tenant
  compositions keyed to prior row ids. Pre-existing; offered-updates INCREASES
  edit traffic on defaults, so the exposure grows. Recommend a small dedicated
  fix (slug-keyed or rebind-on-bump) — candidate rider on V-1's hardening item.
- **MoC ref decay on staging**: authored focus refs from the demo seeds point at
  version-rotated rows today; V-1 item 2 repairs read-side. No data fix needed.
- **Dev/staging seed divergence**: local dev holds `job-coordination` content,
  staging holds `scheduling-kanban`/`scheduling-fh` at v15/v25. V-1's seed work
  must be content-agnostic (enumerate active cores/templates, not hardcode slugs).

### STOP findings — answered

- **(a) Customization detection granularity:** NOT whole-template-only. Override
  families are field-granular (key-presence cascade); rows are placement_id-keyed
  → per-placement diff feasible. Apply = pin-move (cascade merges the families
  free) + placement-level clean-apply/diff-and-choose for rows. The
  whole-template-only detection (`skipped_customized`) is the *document-template
  seed* pattern, not the focus substrate's.
- **(b) Version history:** EXISTS as full retained row snapshots on both cores
  and templates. Deltas derivable; only the diff renderer + publish boundary need
  building. No retention lift.
- **(c) Multi-vertical:** needs the join migration (slug-keyed
  `focus_template_verticals`) — copies-per-vertical rejected as breaking
  one-artifact-many-homes.
