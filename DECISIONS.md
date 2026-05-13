# Bridgeable — Architectural Decisions Log

> Append-only. Opus-only. Each entry: date, decision, one-paragraph rationale. New chats read this when they need to understand WHY something is the way it is.

> Format: each entry has date, decision title, and rationale paragraph. Superseding entries reference the prior entry's date and state the reason. Earlier entries are never edited.
---

## 2026-05-13 — Separate canon, state, and decisions log

Canon documents (PLATFORM_ARCHITECTURE, DESIGN_LANGUAGE, BRIDGEABLE_MASTER, FUNERAL_HOME_VERTICAL, VISION, CLAUDE.md) were being edited on every commit, conflating slow-changing architectural canon with fast-changing session state. New model: canon stays canon (Opus-only, batched, deliberate). STATE.md holds current truth and is the only doc Sonnet writes. DECISIONS.md is append-only and records why architectural choices were made. New chats read STATE.md first, then canon as needed.

---

## 2026-05-13 — Bridgeable Studio as consolidated visual authoring environment

The platform's visual authoring surfaces are consolidated into a single environment called the Bridgeable Studio, located at `/studio`. Single-app metaphor (Figma-comparable). All non-code visual work — themes, component classes, focuses, widgets, documents, workflows, edge panels, registry inspection, and runtime-aware editing — happens inside the Studio. Two modalities: Edit mode (form-driven authoring against substrate) and Live mode (click-on-runtime authoring against the same substrate). Both modalities ship from Studio launch; neither is aspirational. Scope-as-mode via top-bar picker: Platform or specific vertical. Standalone editor routes redirect into Studio deep links and are deprecated for one release before deletion. The Studio is admin-only, PlatformUser-authenticated.

---

## 2026-05-13 — Verticals as first-class entity ships as a small precursor arc

A `verticals` table with metadata for the four canonical slugs (manufacturing, funeral_home, cemetery, crematory) ships as a precursor to the Studio shell. Slug strings remain the value used by existing `vertical` columns across 16+ configuration tables; no FK migration is part of this arc. The precursor exists so the Studio rail can title itself and the scope picker has rows to enumerate. Slugs are immutable at the service layer — `update_vertical` does not accept a slug parameter. A CLAUDE.md convention is added: all future migrations introducing a `vertical` column must reference `verticals.slug` as an FK from inception, so the existing String-not-FK pattern stops being perpetuated by default.

---

## 2026-05-13 — Studio shell arc decomposition

The Studio shell ships in three arcs: (1) verticals-lite precursor — `verticals` table, three endpoints, admin page; (2) Studio 1a-i — routing, redirect layer, Studio rail with icon-strip + expanded modes, editor adaptation pass, Live mode wrap with placeholder overview surface; (3) Studio 1a-ii — overview surface implementation with inventory service, counts, and recent-edits feed. Live mode ships in 1a-i, not deferred. The Studio rail collapses to a 48px icon strip when an editor's own left pane is in use; editors retain their own left panes (model: rail-collapses-not-replaces). Per-editor refactor is a lightweight adaptation pass (~30-60 LOC per editor accepting a `studioRailExpanded` context value), folded into 1a-i. This decomposition supersedes the earlier four-sub-arc proposal (1a/1b/1c/1d) that assumed editors would drop their left panes; the rail-collapses model makes that refactor unnecessary.

---

## 2026-05-13 — Focus cores are picked, not composed

Operators select Focus cores from a registry of pre-built core templates. Cores appear as fixed-but-visible placements on the Focus composition canvas: movable and resizable, but not deletable and not decomposable. The Focus composition canvas authors only arrangement (which accessory widgets/buttons appear around the core, where they're positioned). The core itself remains code, per the May 2026 core-plus-accessories canon. This decision formalizes the unified-placement model in operator-facing terms: every Focus canvas element is a placement, with the core distinguished by its fixed-but-visible status.

---

## 2026-05-13 — Widget authoring is data-source-first

No widget can be authored in the Studio without first selecting a Vault data source (Vault saved view, Vault item type filter, or ad-hoc query). This prevents the decorative-widget anti-pattern where widgets exist without reactive data backing. Two entry points to widget authoring — Vault-initiated ("make widget from this view") and canvas-initiated ("blank canvas, pick a source") — converge in the same authoring surface and produce the same widget record. The authoring surface is three-pane: data source picker (left), live preview (center), visualization shape picker plus shape-specific config (right).

---

## 2026-05-13 — Spaces substrate is the next-on-queue arc after Studio shell

Investigation (`docs/investigations/2026-05-13-studio-shell.md` §2) confirmed there is no platform-tier Spaces substrate today: spaces are per-user JSONB in `user.preferences`, the 15 endpoints are tenant-token + per-user scoped, role-seeded templates live in Python code. The absence of platform-tier Spaces substrate is a strategic gap on the vertical-launch flow, not just a Studio-scoping question; per-user-JSONB-only constrains every future vertical launch. Spaces substrate arc — `space_templates` table with 3-tier scope inheritance, platform-admin API, service-layer resolver — is locked as the immediate post-Studio-shell priority, estimated ~1,500-2,500 LOC before any Studio integration. The Studio rail in 1a-i shows a "Spaces" entry as disabled with "Coming soon" affordance.

---

## 2026-05-13 — Live mode is vertical-or-tenant-tier authoring; platform-tier changes happen in Edit mode

In Studio Live mode, the scope picker is informational and read-only — scope is determined by the impersonated tenant's `Company.vertical`. Operators cannot author platform-tier changes from inside Live mode. Platform-tier authoring (changes affecting every tenant) happens exclusively in Edit mode at Platform scope. This is a deliberate constraint, not a limitation pending future work: authoring platform-tier changes while looking at one specific tenant's runtime would design against that tenant's data without surfacing the platform-wide blast radius. The constraint will eventually need surfacing in the Studio's chrome (Live mode top bar shows "Editing vertical_default for Wastewater — via tenant Hopkins FH"). Future tenant_override scope authoring inside Live mode is a separate UX arc.
---

## 2026-05-13 (PM) — Studio 1a-i sub-arc refinement

Supersedes 2026-05-13 (Studio shell arc decomposition) on the question of how Studio 1a-i is dispatched. Investigation at `docs/investigations/2026-05-13-studio-1a-i-scoping.md` applied R-7-α floor analysis (verticals-lite shipped at 2.3x estimate) to Studio 1a-i and found the bundled scope at ~4,000-4,500 LOC midpoint exceeds the sub-agent execution ceiling. The bundle splits into three sub-arcs: 1a-i.A1 (routing + rail + redirect + placeholder overview + smoke tests, ~2,300 worst case); 1a-i.A2 (Live mode wrap + impersonation handshake + mode-toggle URL helper + Live mode tests, ~1,900 worst case); 1a-i.B (editor adaptation pass + comprehensive tests, ~1,840 worst case). Each fits the ~2,000-2,500 ceiling at worst case.

The 2026-05-13 commitment "Live mode ships in 1a-i, not deferred" is honored by sequencing A2 immediately after A1 with no other arcs interleaved. The brief window between A1 and A2 ships where Studio is operator-visible without Live mode is treated as transitional sub-arc sequencing, not deferral. A2 dispatches as the next arc after A1 lands; B dispatches after A2.
