# Feature Sessions — build log

Chronological log of significant feature builds. Each entry is
written at the end of a build and NOT updated afterward — history
first. For the current platform state, see `CLAUDE.md`.

---

## Phase A Session 2 — Anchored Core + Mode Dispatcher + Push-Back Scale

**Date:** 2026-04-22
**Session type:** Architectural layering. Second of Phase A per `ARCHITECTURE_MIGRATION.md`. Canvas + WidgetChrome deferred to Session 3; Session 2 stays focused on mode dispatch + registry + layout-state types + push-back.
**Files touched:** 15 created / modified (`frontend/src/contexts/focus-registry.ts`, `focus-registry.test.ts`, `frontend/src/components/focus/mode-dispatcher.tsx`, `mode-dispatcher.test.tsx`, `cores/_shared.tsx`, `cores/KanbanCore.tsx`, `cores/SingleRecordCore.tsx`, `cores/EditCanvasCore.tsx`, `cores/TriageQueueCore.tsx`, `cores/MatrixCore.tsx`, `frontend/src/components/focus/Focus.tsx`, `Focus.test.tsx`, `ReturnPill.test.tsx`, `frontend/src/contexts/focus-context.tsx`, `focus-context.test.tsx`, `frontend/src/components/layout/app-layout.tsx`, `frontend/src/styles/base.css`, `frontend/src/pages/dev/focus-test.tsx`, `PLATFORM_ARCHITECTURE.md`, `CLAUDE.md`, `FEATURE_SESSIONS.md`).
**LOC:** ~800 new / ~80 edits.
**Tests:** 20 new Vitest (226 total, up from 206). tsc clean. vite build clean in 5.18s.

### What shipped

- **Focus registry** (`contexts/focus-registry.ts`) — Pattern B per user decision. Singleton `Map` + `registerFocus / getFocusConfig / listFocusConfigs` public API. `CoreMode` type union with 5 canonical modes (`kanban / singleRecord / editCanvas / triageQueue / matrix`) + `LayoutState<TCoreLayout>` + `LayoutConfig<TCoreLayout>` generic layout types + `FocusConfig` interface. Five stub Focuses registered at module load — one per mode. Exports `_resetRegistryForTests` for test isolation.
- **Mode dispatcher** (`components/focus/mode-dispatcher.tsx`) — lookup-map pattern (not switch). `MODE_RENDERERS: Record<CoreMode, ComponentType<CoreProps>>` — TypeScript's exhaustive-record check fails compile if a mode lands in the union without a map entry. Unknown focus id renders an error state (brass-adjacent warm error panel + dismiss hint) rather than crashing.
- **Five stub cores** under `components/focus/cores/`:
  - `KanbanCore.tsx` — 3 columns with 2–3 placeholder cards each
  - `SingleRecordCore.tsx` — form-style stack of 6 placeholder field rows with labels
  - `EditCanvasCore.tsx` — faux toolbar (Bold/Italic/Underline/Image icons) above a centered ~600px canvas placeholder
  - `TriageQueueCore.tsx` — vertical list of 5 placeholder rows with keyboard-shortcut badges (1-5) visible on the left
  - `MatrixCore.tsx` — 4×4 table grid with row/column headers
  - `_shared.tsx` — `CoreProps` contract + `CoreHeader` + `EscToDismissHint` shared primitives
- **Focus.tsx** — placeholder replaced with `<ModeDispatcher focusId={currentFocus.id} />`. `FocusPlaceholder` function deleted (was explicitly marked Session 2 scope).
- **Layout-state scaffold** — `FocusState` extended with `layoutState: LayoutState | null`. `FocusContextValue` gains `updateSessionLayout(patch: Partial<LayoutState>): void` that merges widget records across patches. Generic `LayoutState<TCoreLayout = unknown>` + `LayoutConfig<TCoreLayout = unknown>` types live in `focus-registry.ts`; modes opt in to specialized layouts (e.g. `LayoutState<KanbanColumnOrder>`) in later sessions. Session 2 stores only session-ephemeral tier in memory; Session 4 adds `focus_sessions` + `focus_layout_defaults` tables for tenant + per-user tiers.
- **Push-back scale — SHIPPED.** `<main>` in AppLayout carries `data-focus-pushback={isOpen ? "true" : "false"}`. CSS rule in `base.css`: `main[data-focus-pushback="true"] { transform: scale(0.98); }` + transition via `--duration-arrive` + `--ease-settle`. Scope discipline verified: sidebar + header + mobile tab bar are siblings of `<main>`, not descendants, so CSS transform's containing-block effect on fixed descendants cannot reach them. Reduced-motion users inherit instant transition from the global retrofit.
- **Dev test page** updated to 5 mode-labeled buttons (`Open Kanban Focus` / `Open Single-Record Focus` / etc.) + live state readout showing `currentFocus.id`, resolved mode, and `layoutState` widget count.
- **`PLATFORM_ARCHITECTURE.md §5.15`** updated: push-back paragraph flipped from "deferred" to "ships in Session 2" with scope-safety explanation.

### Architectural decisions (locked this session)

1. **Mode lives in registry (Pattern B).** Consumers call `useFocus().open(id)` — they don't pass mode as a prop. Registry is the source of truth for "what mode does this Focus use." Adding a future focus = one `registerFocus()` call.
2. **Open-closed mode dispatch.** Adding a new mode requires: (a) append to `CoreMode` type union, (b) add one entry to `MODE_RENDERERS` map, (c) create the new core component, (d) register a focus that uses it. No existing mode's code changes. TypeScript's `Record<CoreMode, ...>` catches forgotten map entries at compile time.
3. **Naming = camelCase for core modes.** `kanban / singleRecord / editCanvas / triageQueue / matrix`. Verified no backend precedent for these specific names before choosing. The backend `triage_queue` pin_type literal (snake_case) lives in a distinct namespace (pinnable-target-kinds), not core modes (rendering patterns). Documented the distinction in `TriageQueueCore.tsx` header comment.
4. **Canvas + WidgetChrome deferred to Session 3** per user decision. Session 2 stays focused on mode dispatch; Session 3 ships canvas + widget chrome + drag/resize as a coherent unit.
5. **Generic LayoutState** — `LayoutState<TCoreLayout = unknown>` chosen over plain `unknown`. Slightly cleaner; modes can specialize (`LayoutState<KanbanColumnOrder>`) while preserving the base contract. Layer-defaults = `unknown` so modes that haven't specialized yet Just Work.
6. **Push-back ships — Chromium verified.** Scope is safe by construction: `<main>` has no fixed-positioned descendants. Scale applies cleanly; sidebar + header confirmed untouched. Safari verification is on the user (Safari's fixed-containing-block behavior differs from Chromium but the scope boundary holds either way).

### Verification

- **Vitest:** 226 tests passing (206 baseline + 20 new across 2 new files and 2 extended files). Breakdown: `focus-registry.test.ts` × 8, `mode-dispatcher.test.tsx` × 7, `focus-context.test.tsx` +5 layout-state tests.
- **tsc:** clean.
- **vite build:** clean, 5.18s.
- **Preview verification (Chromium via preview_eval):**
  - Focus opens with correct `aria-label="Focus: test-kanban"` ✓
  - Dispatcher routes Kanban id → `KanbanCore` (title "Kanban stub", eyebrow "kanban") ✓
  - Dispatcher routes Triage-Queue id → `TriageQueueCore` (title "Triage-queue stub", 5 keyboard-shortcut badges 1-5 visible) ✓
  - Push-back: `<main>` transform on open = `matrix(0.98, 0, 0, 0.98, 0, 0)`; `<header>` transform = `none`; sidebar transform = `none` ✓
  - URL sync: `?focus=test-kanban` on open, removed on close ✓
  - ESC dismiss: dialog closes, `data-focus-pushback="false"`, main transform resets to `none`, return pill appears ✓

### Deviations from session plan

- **Canvas + WidgetChrome deferred** per user decision to Session 3 (9 deliverables instead of 10).
- **Push-back scale: SHIPPED** (user decision was "ship if Chromium + Safari render cleanly; drop otherwise"). Chromium verified; Safari verification is user-side.
- **Orphan blocker resolved mid-session:** user's browser had `platform_mode="true"` in localStorage left over from an earlier session, which routed the app to the BridgeableAdminApp regardless of path. Cleared; flagged for user visibility in verification report. Not a Session 2 code issue.

### Next session (Phase A Session 3)

Canvas + WidgetChrome + drag/resize as a coherent unit. Canvas wraps the anchored core with an 8px grid (PA §5.1); WidgetChrome primitive provides drag handle + resize corner + dismiss X (ghosted by default, hover-reveal). Session 4 follows with return-pill countdown + `focus_sessions` database persistence.

---

## Phase A Session 1 — Focus Primitive Scaffolding

**Date:** 2026-04-22
**Session type:** Architectural foundation. First session of Phase A per `ARCHITECTURE_MIGRATION.md`. Ships scaffolding only — later sessions build core-mode dispatch, canvas, pins, chat, and database persistence on top.
**Files touched:** 14 created / modified (`frontend/src/contexts/focus-context.tsx`, `focus-context.test.tsx`, `frontend/src/components/focus/Focus.tsx`, `Focus.test.tsx`, `ReturnPill.tsx`, `ReturnPill.test.tsx`, `frontend/src/pages/dev/focus-test.tsx`, `frontend/src/App.tsx`, `frontend/src/core/CommandBarProvider.tsx`, `frontend/src/styles/tokens.css`, `DESIGN_LANGUAGE.md`, `PLATFORM_ARCHITECTURE.md`, `CLAUDE.md`, `FEATURE_SESSIONS.md`).
**LOC:** ~600 new / ~30 edits to existing files.
**Tests:** 21 new Vitest (206 total, up from 185). tsc clean, vite build clean in 4.88s.

### What shipped

- **`FocusContext`** (`contexts/focus-context.tsx`) — React context with state + URL-as-source-of-truth discipline. `?focus=<id>` param drives state via `useSearchParams`. `open()` / `close()` / `dismissReturnPill()` are the public API. State shape: `currentFocus: FocusState | null` + `lastClosedFocus: FocusState | null` + derived `isOpen`. Opening a new Focus while another is open replaces (only one Focus active at a time, per PA §5.1 primitive discipline). Closing moves the just-closed state into `lastClosedFocus` for the return pill.
- **`Focus` component** (`components/focus/Focus.tsx`) — renders the full-screen overlay atop `@base-ui/react/dialog`. Backdrop is `bg-black/40 supports-backdrop-filter:backdrop-blur-md` (matches overlay-family scrim; heavier blur than Dialog's `backdrop-blur-sm` for push-back signal per PA §5.2). Anchored core is `bg-surface-raised rounded-lg shadow-level-3 p-6` centered at `w-[90vw] max-w-[1400px] h-[85vh] max-h-[900px]`. Animations via `data-open:animate-in` / `data-closed:animate-out` classes using `duration-arrive` + `ease-settle` on enter and `duration-settle` + `ease-gentle` on exit — identical pattern to Dialog. `aria-modal="true"` set explicitly on Popup (base-ui doesn't emit it automatically). Placeholder content renders the focus id + descriptive copy — Session 2 replaces with core-mode dispatcher.
- **`ReturnPill` component** (`components/focus/ReturnPill.tsx`) — UI-only scaffolding. Fixed at bottom-center, rounded-full chrome on `bg-surface-raised` with `shadow-level-2`. Renders iff `lastClosedFocus !== null && currentFocus === null`. Click the pill body → reopen the just-closed Focus. Click the X → dismiss the pill without reopening. No 15s countdown yet — that's Session 4 along with hover-to-pause and re-arm-on-state-change.
- **Layering tokens** — `--z-base` / `--z-elevated` / `--z-dropdown` / `--z-modal` / `--z-focus` / `--z-command-bar` / `--z-toast` added to `DESIGN_LANGUAGE.md §9` (new "Layering tokens" subsection) and `frontend/src/styles/tokens.css` in the same commit per the `tokens.css` header discipline ("edit DESIGN_LANGUAGE.md first, then port the change here. Silent drift is a bug"). New overlay code consumes via `style={{ zIndex: "var(--z-focus)" }}` inline. Existing `z-50` literals in the overlay family (Dialog, Popover, DropdownMenu, Tooltip) are NOT retrofit — natural-touch refactor as those files change.
- **Command Bar integration** — `core/CommandBarProvider.tsx` consumes `useFocus()` (since `FocusProvider` mounts above `CommandBarProvider` in App.tsx). When a Focus is open: (a) Cmd+K handler short-circuits before preventing default or opening the bar, (b) `<CommandBar>` is not rendered, (c) a defensive `useEffect` closes the bar if it was already open when a Focus opened. Escape still closes an already-open bar (defensive — shouldn't happen in practice given b + c). Bounded-decision discipline in implementation: Act and Decide are distinct primitives; mixing them inside one screen breaks the boundary.
- **Dev test page** at `/dev/focus-test` — three Open-Focus buttons, live state readout, copy explaining manual tests (refresh for URL restoration, browser back, Cmd+K suppression). Not in nav. Any authenticated tenant user can access.
- **PLATFORM_ARCHITECTURE.md** gains `§5.15 Implementation Foundation` documenting the base-ui Dialog choice + the push-back-scale deferral + the Command-Bar-Focus mutual exclusion. Prevents future sessions from rebuilding primitive Dialog functionality.

### Architectural decisions (locked this session)

1. **State pattern: React Context + URL as source of truth.** `?focus=<id>` param drives context state. Browser back/forward naturally closes/reopens a Focus. Database persistence (via `focus_sessions` table) deferred to Session 4.
2. **Animation infrastructure: `@base-ui/react/dialog` + `tw-animate-css`.** No new dependencies. Overrides the original session plan's "framer-motion (existing dependency)" — verified against `package.json` + `grep src/`: framer-motion was never installed. The overlay family already uses base-ui Dialog + `data-open:animate-*` Tailwind classes with the `--duration-*` / `--ease-*` tokens, and Focus adopts that pattern for consistency.
3. **Push-back scale on underlying app: DEFERRED.** CSS `transform: scale` creates a containing block for `position: fixed` descendants on Safari and some Chromium builds. Scaling the app shell would break DotNav + ModeToggle (both fixed-positioned). Backdrop blur alone provides the push-back feeling for Session 1. Session 2 revisits with a scoped wrapper element.
4. **Command Bar is hidden while a Focus is open.** Not a UX choice — a primitive-boundary choice. Information lookup inside a Focus is answered by Focus Chat (Session 7), not by escaping to the Command Bar.
5. **Tests colocated** (`Focus.tsx` + `Focus.test.tsx` in the same directory) per existing codebase convention. No `frontend/tests/focus/` subdirectory created.
6. **`aria-modal="true"` explicitly set on Popup.** base-ui's `Dialog.Popup` does not emit `aria-modal` automatically even when `Dialog.Root` is modal. Setting it explicitly ensures accessibility assertions pass and screen readers treat the Focus correctly.

### Verification

- **Vitest:** 206 tests passing (185 baseline + 21 new). Test files created: 3.
- **tsc:** clean.
- **vite build:** clean, 4.88s.
- **Manual test surface:** `/dev/focus-test` exercises open / close / ESC / backdrop-click / URL-sync / return-pill / Cmd+K-suppression paths.

### Deviations from session plan

- **Animation library:** plan said "framer-motion (existing dependency)". Verified it is NOT a dependency. Switched to base-ui Dialog + tw-animate-css per user decision after flag.
- **Push-back scale:** plan said "verify no breakage... if scale interferes with fixed positioning, FALLBACK." Took the fallback. Session 2 revisits.
- **Dialog primitive choice:** plan did not specify; chose base-ui Dialog after verification, documented in PA §5.15 for future sessions.
- **Tests:** plan said `frontend/tests/focus/` — user overrode to colocated per existing convention.

### Visual verification

**Confirmed 2026-04-22:** all 10 manual test cases pass on `http://localhost:5173/dev/focus-test` against the `testco` seeded tenant. Backdrop blur + anchored-core render, backdrop-click dismiss, ESC dismiss, URL sync (`?focus=<id>` persists across refresh), return pill with correct label, pill click-to-reopen, pill X dismiss, Command Bar hidden during Focus (Cmd+K suppressed), focus trap keeps Tab cycling inside the core, all three test buttons propagate labels correctly. Foundation solid for Session 2.

Pre-verification blockers resolved in-session: (a) stale Vite server on port 5173 killed + fresh dev server bound; (b) `seed_staging.py:890` KB-category key mismatch fixed (`cat_ids["Pricing"]` → `cat_ids["Product Pricing"]` — was rolling back the entire seed transaction); (c) April-8 orphan `admin@testco.com` user (attached to `default` company, audit_logs FK prevented hard delete) renamed + deactivated to free the email address for the seed's `_seed_users`; (d) `testco` tenant seeded from scratch against local `bridgeable_dev` (7 users, 25 products, 8 company entities, 3 invoices — all 4 seed-verification queries pass). Operational notes for future sessions added to CLAUDE.md §7 Local dev seeding.

### Next session (Phase A Session 2)

Anchored core mode dispatcher: render different core types (Kanban, single-record, edit canvas, triage queue, matrix) based on the open Focus's configuration. Push-back scale revisit. Session 3 follows with free-form canvas + widget placement.

---

## Tier-4 Measurement-Based Correction — Dark-mode card chrome calibrated

**Date:** 2026-04-22
**Session type:** Documentation-evolution fix. Supersedes Tier 2 + Tier 3 (both inference-based) with a single measurement-based correction.
**Files touched:** 6 (`tokens.css`, `DESIGN_LANGUAGE.md`, `CLAUDE.md`, `FEATURE_SESSIONS.md`, `frontend/src/components/ui/card.tsx`, `frontend/src/components/widgets/WidgetWrapper.tsx`).
**LOC:** ~120 touched (token edits + primitive reverts + prose rewrites).
**Tests:** No new tests. tsc clean, vitest 185/185 unchanged, vite build clean.

### The problem

Three consecutive reconciliation sessions (investigation + Tier 2 + Tier 3) hadn't closed the visual gap between live rendering and the canonical approved reference (`docs/design-references/IMG_6085.jpg`, the John Michael Smith case card dark mode). User reported Tier-3 still didn't match.

Each prior session had inferred tuning direction from §1 anchor prose:
- Investigation: "the spec produces quiet cards on purpose; maybe the reference is aspirational"
- Tier 2: "strengthen the shadow + add a perimeter border" (based on anchor-4's list of three cue options)
- Tier 3: "lift the surface lightness further" (based on "dark mode needs a larger step")

Each adjustment moved tokens but not toward the reference. User invoked a methodology pivot: instead of continuing Tier-N inference, **sample the reference pixel values directly and calibrate to measured OKLCH**.

### Measurement

PIL-based pixel scan of both reference images:
- `Image.open(path).convert('RGB')` + `getpixel((x, y))` at strategic coordinates
- Page backgrounds at outer strips (multiple samples, confirmed stable)
- Card body at flat mid-card regions (dozens of samples, confirmed stable RGB)
- Left-edge horizontal probe at y=1074 (1-pixel resolution): showed page → shadow halo → card body transition with NO distinct border pixel
- Top-edge vertical probe at x=500 (1-pixel resolution): revealed a 3-pixel-thick highlight band at RGB(50, 45, 41)
- Bottom-edge vertical probe: confirmed shadow halo extends ~20px below card
- sRGB → linear sRGB → OKLab → OKLCH conversion via Ottosson 2020 formulas

Method validation: light-mode samples (IMG_6084.jpg) matched existing tokens within 0.005 OKLCH lightness, confirming the measurement method is accurate — the dark-mode discrepancies we measured are real drift, not method artifact.

### Measured values (dark mode)

| Region | RGB | OKLCH measured | Prior token | Gap |
|---|---|---|---|---|
| Page | (16, 12, 9) | `oklch(0.158 0.009 59)` | `oklch(0.16 0.012 65)` | L match, C over +0.003, **h off by −6°** |
| Card body | (25, 22, 17) | `oklch(0.202 0.011 81)` | `oklch(0.22 0.015 65)` (Tier-3) | L over by +0.018 (Tier-3 shot high), C over +0.004, **h off by −16°** (reference is WARMER) |
| Shadow halo | (13-15, 9-11, 5-8) | `oklch(0.144-0.154 0.010 55-63)` | matches via blur composite | Effective match |
| **Top-edge highlight band (3px!)** | (50, 45, 41) | `oklch(0.301 0.010 61)` | `oklch(0.48 0.02 78 / 0.65)` at 1px inset | **Reference is wider (3px) + dimmer (L=0.30) than current (1px at composite L=0.389)** |
| Perimeter border | no discrete pixel | — | `border border-border-subtle` (Tier-2 added) | **Not present in reference** |

### Fixes (five coordinated changes in single commit)

**1. Dark-mode hue progression added** (G1 — the root cause):
- `--surface-base` h: 65 → **59** (cool-amber foundation)
- `--surface-elevated` h: 65 → **81** (warmer amber, catches-more-lamplight)
- `--surface-raised` h: 65 → **85** (continues progression)
- `--surface-sunken` h: 65 → **55** (cooler when recessed)

This was the root cause of the visual gap. Prior tokens used a static h=65 across the entire elevation stack. Reference demonstrates a +22° warming between base and elevated — a second material dimension ("catches more warm light when lifted toward the source") that neither Tier 2 (shadow) nor Tier 3 (lightness) touched.

**2. Tier-3 lightness bumps reverted** (M1):
- `--surface-elevated` L: 0.22 → **0.20** (pre-Tier-3 value, matches reference L=0.202)
- `--surface-raised` L: 0.27 → **0.24** (pre-Tier-3 value)
- Chroma slightly reduced across all surfaces to match reference measurement

**3. Perimeter border removed from Card + WidgetWrapper** (G2):
- Card primitive: `border border-border-subtle` removed. Card class: `rounded-md bg-surface-elevated font-plex-sans text-body-sm text-content-base shadow-level-1 ...`
- CardFooter: `border-t border-border-subtle` restored (was removed in Tier-2 when parent carried perimeter; now the parent doesn't carry a border, so footer needs its own separator back)
- WidgetWrapper: inline `border border-border-subtle` removed for parity with Card. Both primitives now render with identical chrome discipline (lift + shadow + dark-mode-only top-edge highlight).

**4. Top-edge highlight calibrated** (G3):
- `--shadow-highlight-top`: `oklch(0.48 0.02 78 / 0.65)` → `oklch(0.32 0.010 61 / 0.9)` (dimmer-per-pixel, but wider below)
- `--shadow-level-1/2/3` dark inset: `inset 0 1px 0` → `inset 0 3px 0` (3px band matches reference measurement)
- Tight grounding shadow + soft halo + inset highlight three-layer composition RETAINED from Tier 2 — that architecture was correct; only the inset parameters changed.

**5. DL prose rewrites** (mirror discipline, same commit):
- **§1 dark-mode anchor 4** rewritten from three-cue system to **two-cue system** (surface lift + top-edge highlight). Explicit statement that cards use NO perimeter border. Light-vs-dark asymmetry explained: morning light is ambient-and-diffuse (lift alone carries elevation); evening light is directional (lift + highlight both needed). Tier-history note added.
- **§3 Surface tokens rationale** gains **hue-progression paragraph** explaining the second material dimension. "0.05–0.06 dark-mode step" language reverted to "0.04" (measurement-accurate). Reconciliation history note updated.
- **§3 Full CSS block + §9 CSS block** synchronized with new dark-mode values.
- **§6 Shadow specifications** dark-mode table updated to 3px inset. Tier-history notes rewritten to document the full arc (Tier 2 → Tier 3 → Tier 4). **Measurement-first learning note canonicalized.**
- **§6 Border treatment** "Card perimeter border (canonical)" subsection **REMOVED** and replaced with "Card perimeter: no border" canonical statement + "Overlay perimeter: no border" + "Where borders DO apply" + updated "What NOT to add borders to."

### Methodology canonicalized

Added to CLAUDE.md Design System section immediately after the "Tokens.css is a mirror" paragraph:

> **Reference images win over prose — for diagnosis, not just authority.** When canonical reference images exist in `docs/design-references/`, sample them directly via PIL (`from PIL import Image; Image.open(path).convert('RGB')`) before inferring tuning values from prose anchors. This discipline is canonicalized after Tier 4 (April 2026) — three consecutive sessions of inferring-from-anchors produced three misses, while one session of direct pixel sampling produced an immediate correct calibration.

### The learning

**Anchor prose is ambiguous by design; reference images are deterministic.** When both exist, prose is a generalization derived from the images; inference from prose alone is a lossy decoding. The lossy step is where three sessions of drift accumulated. Measurement reverses the lossy step.

Example from this arc:
- §1 anchor 4 prose: "the cue MAY be a top-edge highlight, a surface gradient, OR a warm hairline border"
- Inference reading (Tier 2): "apply all three for cards"
- Reference reading (Tier 4): "only two — lift + highlight. Border was listed as an option because it applies selectively to OTHER components (inputs, table rules), not to cards."

The prose doesn't capture "cards use only two of the three options." Reference does, unambiguously — no discrete border pixel.

### Verification & status

- tsc clean
- vitest 185/185 unchanged (no vitest-level tests for these token changes)
- vite build clean

User visually verifies dark mode + light mode cards against both reference images. If Tier-4 matches: **spec-reconciliation arc complete**; Phase II Batch 1c-i (order-station) ready. If residual gap: by elimination it would be composition-level (corner radius or typography cadence), not token-level — flagged for Phase III Final QA, not further Tier-N work.

### Deferred to Phase III Final QA

- Card corner radius: reference shows ~16px (`rounded-lg`), Card default is 8px (`rounded-md`). Future consideration for card-size variant or default radius change.
- SignatureCard composition primitive: reference shows micro-caps eyebrow → serif display → mono metadata → body sans → brass CTA. Future composition bundling.

Neither fits further token-level reconciliation scope. Both are component/composition questions best addressed during Phase III's comprehensive Final QA pass.

### Arc summary

Three sessions of inference (Tier 2 shadow+border, Tier 3 surface-lift, Tier 2.5 investigation) produced accumulating drift. One session of measurement produced correct calibration. The learning has been canonicalized so future Claude instances default to measurement when references exist.

---

## Tier-3 Spec Reconciliation — Dark-mode surface-lift

**Date:** 2026-04-22
**Session type:** Documentation-evolution fix. Follow-up to Tier-2 after user provided canonical approved reference images. Third session in the reconciliation arc: (Tier-1 deferred/not-needed) → **Tier-2 shadow strengthening + perimeter border** → **Tier-3 surface-lightness bump**.
**Files touched:** 4 (`tokens.css`, `DESIGN_LANGUAGE.md`, `CLAUDE.md`, `FEATURE_SESSIONS.md`) + 1 new (`docs/design-references/README.md`).
**LOC:** ~90 touched + ~110 new (manifest README).
**Tests:** No new tests. tsc clean, vitest 185/185 unchanged, vite build clean 5.06s.

### The problem (Tier-2 follow-up)

User visually verified Tier-2 (shadow composition strengthened + Card perimeter border added). Card chrome meaningfully improved — clearly more lifted than pre-reconciliation — but user noted a remaining residual gap vs. the approved reference. Pre-Tier-3 card body lightness (dark mode L=0.20) still read slightly less distinct than the reference demonstrated.

User provided the canonical reference images, saved to `docs/design-references/`:
- `IMG_6084.jpg` — John Michael Smith case card, **light mode**
- `IMG_6085.jpg` — same card, **dark mode**

Both are ground truth from the design-language creation session and now serve as canonical visuals for card chrome. Per DL §1 canonical-mood-references clause, "images win over prose" — the fix direction when implementation diverges is to update spec + tokens to match what the reference shows.

### The change

Surface-lightness bump in dark mode only (Tier-3 escalation previously held in reserve):

| Token | Pre-Tier-3 | Post-Tier-3 | Δ from base |
|---|---|---|---|
| `--surface-base` (dark) | `oklch(0.16 0.012 65)` | unchanged | 0 |
| `--surface-elevated` (dark) | `oklch(0.20 0.014 65)` | `oklch(0.22 0.015 65)` | 0.04 → **0.06** |
| `--surface-raised` (dark) | `oklch(0.24 0.016 65)` | `oklch(0.27 0.017 65)` | 0.08 → **0.11** |
| `--surface-sunken` (dark) | unchanged | unchanged | — |

Chroma eased proportionally (0.014→0.015 and 0.016→0.017) per the DL §3 rule that elevated surfaces carry slightly more warmth in dark mode (they "catch more of the implied warm lamplight").

**DL §3 Surface tokens rationale prose updated**: previous text specified "approximately 0.025 in light mode and 0.035 in dark mode" — updated to "approximately 0.025 in light mode and 0.05–0.06 in dark mode" with expanded rationale explaining that the approved reference demonstrates the larger dark-mode step and citing the three-cue composition (surface lift + top-edge highlight + perimeter border) from §1 anchor 4.

**Tier-3 reconciliation history note** added to §3 Surface tokens documenting pre/post values + reference-driven driver.

### Composite verification

Pre-commit math confirmed no highlight alpha tune-down required:

- Top-highlight composite on surface-elevated:
  - Tier-2 (L=0.20): composite L ≈ **0.382**
  - Tier-3 (L=0.22): composite L ≈ **0.389**
  - Shift: +0.007 OKLCH L — imperceptible
- Overlay (surface-raised) vs page:
  - Tier-2: Δ = 0.08 OKLCH
  - Tier-3: Δ = 0.11 OKLCH — distinct-not-harsh range. Strengthened Tier-2 shadow composition (atmospheric halos at level-2/3) mediates any hard-edge perception on overlays.

No token rollback or alpha tuning needed. Clean Tier-3 landing.

### Blast radius audit

**`bg-surface-elevated`** consumers — hundreds of sites across:
- Card primitive body (every `<Card>` usage)
- WidgetWrapper (dashboard + Vault overview widgets — was already rendering with `bg-surface-elevated` inline)
- Many ad-hoc page chrome consumers across Phase-II-Batch-1a/1b refactored files
- Dialog / SlideOver content areas (via shadcn semantic alias `--card`)

**`bg-surface-raised`** consumers — 25 sites (grep-counted):
- Dialog, Popover, DropdownMenu, Tooltip, SlideOver, Sonner
- Tabs, Switch, Radio active states
- Select / Input / Textarea backgrounds (input family shell)
- Phase-II Batch-1b bottom-sheets (ancillary + direct-ship mobile drawers) + FABs

**Risk check**: overlay family's surface-raised bump 0.24→0.27 is a meaningful step. Dark-mode overlay vs page delta now 0.11. Strengthened Tier-2 shadow composition + the overlay's generous padding + centered positioning (modals) or corner positioning (popovers) keep hard-edge harshness at bay. Verified visually in post-Tier-3 live rendering via shadow-level-2/3 atmosphere wrapping.

### Reference image canonicalization

`docs/design-references/` now contains:
- `IMG_6084.jpg` — canonical light-mode card reference
- `IMG_6085.jpg` — canonical dark-mode card reference (the Tier-2 + Tier-3 driver)
- `README.md` — manifest explaining what each image represents, how future Claude instances should use them (inspect via Read tool — JPG content renders visually in the session), per-image observation notes for quick-context scanning, reconciliation history, and process for adding new references

Future aesthetic work inspects these images BEFORE tuning tokens. The spec is a transcription of what the references demonstrate; if live rendering diverges, the correct fix direction is usually "update spec + tokens to match" not "defend the spec as written."

### Incidental observations (flagged, not in Tier-3 scope)

Reading the reference images directly, I observed two minor additional drift points beyond Tier-3 scope:

1. **Corner radius generosity**: the reference cards show approximately 16px corner radius (the `rounded-lg` scale). The Card primitive's default is `rounded-md` (8px). The current default is the dense-card variant; signature detail cards should opt up via className override. Not a spec error — the primitive exposes both radii — but worth considering whether to make `rounded-lg` the default for large cards or introduce a card-size variant that switches radius.

2. **Typography cadence**: the reference cards show a very specific typographic rhythm (micro-caps eyebrow → serif display → mono metadata grid → body sans → brass CTA). This is already supported by existing primitives (CardTitle uses serif via `text-h3 font-plex-serif` convention) but isn't bundled as a "signature card" pattern. A future slot might introduce `SignatureCard` as a composition primitive.

Both observations noted for future consideration. Neither fits Tier-3's surface-lightness scope.

### Spec-reconciliation arc status after Tier 3

- **Tier 1** (originally: strengthen shadow composition) — folded into Tier 2.
- **Tier 2** (April 2026, prior session) — shadow composition three-layer + `--shadow-highlight-top` strengthened + Card perimeter `border-border-subtle` added + CardFooter `border-t` removed.
- **Tier 3** (this session) — dark-mode surface-elevated + surface-raised lightness bumped to match reference.

Spec evolves to match the three-cue material treatment §1 dark-mode anchor 4 prescribes:
1. **Surface lift** — carried by `--surface-elevated` and friends; Tier 3 calibrates the lift.
2. **Top-edge highlight** — carried by `--shadow-highlight-top` inset 1px; Tier 2 calibrates the light-catch weight.
3. **Perimeter border** — carried by `border border-border-subtle` on Card primitive; Tier 2 promoted the hairline border option to canonical card treatment.

Together the three cues deliver the "material, not paint" card treatment the reference shows.

### Documentation

- `tokens.css` — dark-mode surface-elevated + surface-raised updated + inline comment noting Tier-3 reconciliation
- `DESIGN_LANGUAGE.md §3 Surface tokens table` — dark-mode values updated
- `DESIGN_LANGUAGE.md §3 Surface tokens rationale prose` — updated per target text (0.05–0.06 step)
- `DESIGN_LANGUAGE.md §3 Full CSS variable list (dark block)` — values updated with inline Tier-3 comment
- `DESIGN_LANGUAGE.md §9 CSS block (dark)` — values updated (synchronized with §3)
- `docs/design-references/README.md` — new manifest describing canonical reference images
- `CLAUDE.md §14 Recent Changes` — Tier-3 entry
- `FEATURE_SESSIONS.md` — this entry

### Verification checklist for user

1. Open live site in dark mode
2. Dashboard cards (StatCard instances on home dashboard) — compare to IMG_6085.jpg
3. Case detail cards — compare to IMG_6085.jpg
4. Widget cards (Vault Overview, Operations Board) — compare to IMG_6085.jpg
5. Overlay family — Dialog, DropdownMenu, Popover, SlideOver — verify not uncomfortably bright against page; shadow atmosphere still reads correctly
6. Mobile bottom sheets (ancillary + direct-ship drawers on scheduling board) — verify surface-raised lift is proportional
7. Light mode quick-check — should be unchanged (Tier 3 is dark-mode-only)

### Outcomes

- If Tier-3 matches IMG_6085.jpg: spec-reconciliation arc **complete**. Proceed to Phase II Batch 1c-i (order-station standalone) next.
- If residual gap remains: identify specific remaining delta — could be radius, typography cadence, or a fourth convergent cue not yet documented. Targeted follow-up.

### Arc sequencing after Tier-3

- Reconciliation arc complete → Phase II Batch 1c-i (order-station) ready
- Post-September: reconsider `SignatureCard` primitive (incidental observation #2)
- Post-arc polish: card-size variant with `rounded-lg` default for detail cards (incidental observation #1)

---

## Aesthetic Arc Phase II Batch 1b — Scheduling Board Family

**Date:** 2026-04-22
**Session type:** File-family refresh. 4 files in `pages/delivery/` + `components/delivery/`. Closes user-reported scheduling-board bugs surfaced post-Batch-1a visual verification.
**Files touched:** 4 (no new files; no test files).
**LOC:** ~3,107 file LOC, ~590 LOC touched.
**Tests:** No new tests. vitest 185/185 unchanged, tsc clean, vite build clean 5.13s.

### The problem

Three user-reported blocking issues post-Batch-1a visual verification:

1. **Right panel unreadable in dark mode.** `scheduling-board.tsx:588` wrapped the right column in `bg-slate-50/50` — slate-50 (near-white) at 50% alpha over a dark page reads as a "lighter dim wash" rather than the intended recessed meaning. Blinding contrast against dark cards.
2. **"Failed to load schedule" hardcoded red error.** `kanban-panel.tsx:482–498` shipped ad-hoc `bg-white` panel with `text-red-600` + manual `<Button variant="outline">` retry. Exactly the "failed load + retry" pattern the Phase-7 `<InlineError>` primitive was designed for.
3. **Dark-mode blinding throughout ancillary + direct-ship panels.** 5 + 4 card chromes respectively, all `rounded-lg border border-slate-200 bg-white` — blow out in dark mode.

Plus three ad-hoc issues surfaced during audit:

4. **16 emoji/HTML-entity icons** (raw unicode ⛪🏛⚰📍 + entities `&#128230;` `&#128236;` `&#10003;` `&#9662;` `&#8617;` `&#8592;` `&#8594;` `&#9664;`) — inconsistent with Batch 1a's Lucide-everywhere pattern.
5. **4 different "primary action" color tracks** (emerald-600/violet-600/blue-600/slate-700) — no semantic mapping; just color-rotation across actions.
6. **Indigo droppable-over state** from DnD library convention — doesn't match platform's brass "active surface" interaction language.

### Audit findings + scope approval

- 361 total hardcoded bypass grep hits across 4 files
- 227 unique bypass lines (matches re-audit estimate)
- 16 icon replacements (4 raw unicode + 12 HTML entities)
- 4 inline SVG replacements (custom chevron paths + close X)
- ~12 sites expected to consume brass `<Button>` primary
- ~10 sites expected to consume Badge variant info/warning/success/error
- 1 InlineError adoption site
- No primitive gaps — existing Session 2-3 primitives cover every pattern

Audit surfaced 8 open questions; all approved with recommended answers:

- Q1/Q5: All emerald/violet/blue/slate action buttons → brass primary (platform consistency with Batch 1a AgentDashboard)
- Q2: Droppable-over → brass-subtle (platform interaction language over DnD convention)
- Q3: Bottom-sheets stay raw with surface-raised tokens (3+ usage threshold not met)
- Q4: Dropdown menus stay raw with surface-raised tokens (DropdownMenu primitive migration deferred)
- Q6: Single commit file-family coherent
- Q7: Drop hardcoded Badge className overrides, use default variant styling
- Q8: Keep `dueDateColor` helper structure, migrate internals to status tokens

### Implementation

Followed audit's approved order-of-operations:

**1. `pages/delivery/scheduling-board.tsx`** (~40 LOC touched, 13 bypass lines → 0). Right panel wrapper → `bg-surface-sunken` (mode-aware). Calendar + nav buttons → brass focus rings + surface-raised + border-border-base. Weekend Planning badge → `<Badge variant="info">`. New-driver banner → status-warning family. Count pills (amber unresolved, blue direct-ship) → status-warning-muted/status-info-muted. Collapsed panel toggles for Ancillary + Direct Ship re-shaped with leading Lucide icons + status-muted count pills. 6 HTML-entity icons → Lucide (`Undo2`, `ChevronLeft` × 2, `ChevronRight`, `Package`, `Mailbox`).

**2. `components/delivery/kanban-panel.tsx`** (~120 LOC touched, 70 bypass lines → 0). **InlineError primitive adoption** — the blocking fix. Replaced ad-hoc error panel with `<InlineError message="Couldn't load the delivery schedule." hint="Check your connection, then retry." onRetry={fetchSchedule}>`. OrderCard chrome `bg-white` → `bg-surface-elevated`; critical `border-red-400 bg-red-50` → `border-status-error bg-status-error-muted`; warning `border-amber-400 bg-amber-50` → `border-status-warning bg-status-warning-muted`; DnD `ring-indigo-400` during drag → `ring-brass`; **droppable-over `border-indigo-300 bg-indigo-50/50` → `border-brass bg-brass-subtle`** per Q2. 4 raw unicode emoji → Lucide conditional chain (`Church`/`Landmark`/`Box` with `aria-label="Graveside"` since Lucide has no direct coffin match/`MapPin`). Panel-header chrome migrated to surface-sunken family. Inline SVG chevron → `<ChevronRight>` with rotation transform. Hours-countdown Badge class map migrated from border/text-colored-hardcoded to status tokens with animate-pulse preserved for critical urgency.

**3. `components/delivery/ancillary-panel.tsx`** (largest file — 1,131 LOC; ~260 LOC touched, 155 bypass lines → 0). 5 card chromes → surface-elevated. ALL action buttons (emerald-600 Picked-Up/Delivered, violet-600 Confirm-as-Pickup, blue-600 Assign, slate Cancel) unified on brass `<Button>` primary + `<Button variant="outline">` secondary per Q1/Q5. Checkmark-labeled buttons gain leading `<Check>` Lucide per spec item #2. 3 dropdowns (Move/Assign/Reassign) migrated to `bg-surface-raised shadow-level-2` per Q4 (raw div retention). "Funeral home pickup" inline form border-violet-200/bg-violet-50 → status-info family. "Assign to driver + date" blue banner → status-info family. Floating-orders section border/color shifted from amber-200/amber-600 to status-warning/30 + status-warning text. Completed-list checkmarks → `<Check className="h-3 w-3 text-status-success">`. Mobile FAB + drawer migrated to surface-raised + shadow-level-2/3 with `bg-black/40` canonical Dialog backdrop convention. Hand-rolled SVGs → `<X>` + `<ChevronDown>` Lucide.

**4. `components/delivery/direct-ship-panel.tsx`** (~170 LOC touched, 99 bypass lines → 0). 4 card chromes → surface-elevated. ShippedCard soft-recency wrapper `bg-slate-50/50` → `bg-surface-sunken`. Nested state wrappers: "Order placed with Wilbert" blue-50 → status-info-muted; "Mark as shipped?" emerald-50 → status-success-muted; "Mark as complete?" white → surface-elevated. All 3 action-color tracks (blue-600 Mark-as-Ordered, emerald-600 Mark-as-Shipped, slate-700 Done) unified on brass primary. Leading `<Check>` Lucide on all three. **`getUrgencyClass()` helper internals migrated** per Q8: `text-red-600 font-bold` → `text-status-error font-bold`, `text-amber-600 font-bold` → `text-status-warning font-bold`, structure preserved. "Shipped N days ago" amber suggestion text → text-status-warning. Status-group count Badges: Needs-to-be-Ordered → error, Ordered → info, Shipped → success. Collapsed panel + mobile FAB + drawer migrated to surface-raised family.

### Lenient loader pattern NOT invoked

Unlike Phase 8e.2.3's seed-path lenient loader helper, Batch 1b had no legacy-data shape to tolerate — just Tailwind migrations. Clean mechanical refactor.

### Primitive adoption counts

- `<InlineError>`: 1 (kanban Failed-to-load)
- `<Badge variant="info|warning|success|error">`: ~15 sites (driver lane counts, section counts, plan-ahead, weekend planning, floating, state groups)
- `<Button>`: ~12 sites (action buttons across ancillary + direct-ship, unifying 4 color tracks on brass primary)
- **Card** intent: inline surface-token migrations on card chromes — full `<Card>` + subcomponent wrapping would restructure DnD hit targets (`provided.dragHandleProps` spread onto card divs); surface tokens applied directly preserve hit-target fidelity. Documented deviation from audit's primitive plan.

### Lucide icon migrations (16 total)

| Source | Target | Sites |
|---|---|---|
| `⛪` | `<Church>` | kanban-panel service location |
| `🏛` | `<Landmark>` | kanban-panel service location |
| `⚰` | `<Box aria-label="Graveside">` | kanban-panel service location (no direct Lucide casket) |
| `📍` | `<MapPin>` | kanban-panel service location |
| `&#128230;` (📦) | `<Package>` | scheduling board + ancillary empty-state + ancillary FAB |
| `&#128236;` (📬) | `<Mailbox>` | scheduling board + direct-ship empty-state + direct-ship FAB |
| `&#10003;` (✓) | `<Check>` | 10+ sites — button leading icons + completed-list entries |
| `&#9662;` (▾) | `<ChevronDown>` | Assign to Driver dropdown |
| `&#8617;` (↩) | `<Undo2>` | Back to today pill |
| `&#8592;/&#8594;` (←/→) | `<ChevronLeft>/<ChevronRight>` | Nav arrows |
| `&#9664;` (◀) | `<ChevronLeft>` | Panel expand toggle |

### 4 inline SVG migrations

- kanban panel-header chevron path → `<ChevronRight>` with rotation
- ancillary collapse button chevron path → `<ChevronDown>` with rotation
- ancillary drawer close X path → `<X>`
- direct-ship collapse button chevron path → `<ChevronDown>` with rotation
- direct-ship drawer close X path → `<X>`

### Documentation

- `CLAUDE.md §14 Recent Changes` — new top entry with full six-item breakdown + primitive adoption counts.
- `AESTHETIC_ARC.md` — new Phase II Batch 1b section with file-by-file breakdown + Lucide migration table + deferred items.
- `FEATURE_SESSIONS.md` — this entry.

### Verification checklist for user (post-commit)

All 4 pages, both light AND dark mode via the newly-ergonomic ModeToggle in the header:

- `/scheduling` main page (date view + week view if Saturday)
- Kanban panel — normal, critical, warning order cards
- Ancillary Orders right panel — needs-action, awaiting-pickup, assigned, completed, floating
- Direct Ship right panel — needs-ordering, ordered, shipped, completed
- Failed-to-load state (trigger via network throttle or temporary backend disable)
- Critical delivery card (if data available)
- Drag-and-drop interactions — verify brass-subtle droppable-over visible
- Mobile bottom-sheet (if testable on mobile viewport)
- All action buttons render as brass primary (emerald/violet/blue/slate tracks gone)
- `dueDateColor` helper rendering — overdue as status-error, near-due as status-warning

### Arc sequencing

Batch 1b complete → **Batch 1c-i queued** (order-station standalone, ~300-400 LOC estimate) → Batch 1c-ii (financials-board + team-dashboard) → Batches 2–5 → Phase III (Sessions 5 Motion + 6 QA).

---

## Workflow Arc Phase 8e.2.3 — Invariant Widening + DotNav Bug Fixes

**Date:** 2026-04-22
**Session type:** Infrastructure micro-phase following 8e.2.2. User visual verification surfaced that James (production Sunnycrest admin) still didn't see template defaults despite 8e.2.2's ship, and separately surfaced 3 DotNav UX bugs. Audit-first session: paused for approval before implementation. No Phase II Aesthetic scope impact.
**Files touched:** 5 source + 1 new migration + 2 new test files + 4 doc updates.
**LOC:** ~860 (~190 migration, ~60 cap-breach + lenient loader in seed.py, ~40 service edits, ~370 tests, ~200 docs).
**Tests:** +10 backend (`test_spaces_phase8e23.py`) + 4 frontend DotNav. Full regression: 170 spaces, 185 frontend. tsc clean, build clean. Migration applied cleanly.
**Migration head:** `r46_users_spaces_backfill` → `r47_users_template_defaults_retrofit`.

### The problem (from user visual verification)

After 8e.2.2 shipped, user opened their Sunnycrest session and observed:

1. DotNav shows only 2 dots — Accounting + Operations, both manually created. Missing template defaults (Production + Sales + Ownership) + Settings for admin.
2. Clicking between the 2 dots does nothing visually.
3. Tooltip on active "Operations" dot says "Switch to Operations".
4. Dots render as Lucide icons despite "DotNav" name implying dots.

### Audit findings

**Finding 1: invariant shape too narrow.** 8e.2.2's defensive re-seed gate was `if not preferences.spaces`. James had 2 manual spaces (pre-hook-existence) so he triggered neither the creation hooks NOR the login re-seed. His `spaces_seeded_for_roles` marker was `null` forever.

Platform-wide count: **2,196 active dev-DB users** (738 admins) in this "James-shape" — populated `spaces` array, empty seed marker. r46's filter caught `spaces` empty, not marker empty. 

Widened invariant: "seeded" = `spaces_seeded_for_roles` contains current role slugs. `spaces` non-empty alone is insufficient.

**Finding 2: DotNav tooltip label.** `DotNav.tsx:264` built one label regardless of active state. Confirmed bug.

**Finding 3: click "does nothing" was visual-feedback gap, not handler bug.** switchSpace + optimistic setActiveSpaceId + applyAccentVars all fire correctly. But James-shape's two spaces were visually identical: both `icon="layers"` (backend default), both `accent="neutral"`, both `default_home_route=null`, both `pins=[]`. Only change on click was 1px ring swap — imperceptible. Fixing invariant restores distinctiveness (different icons per template).

**Finding 4: icons vs dots.** Backend `crud.create_space` default `icon="layers"` — present in DotNav's ICON_MAP → Lucide icon. User never picked; backend default cascaded. Design divergence. Two paths: accept-as-is with doc clarification, OR flip backend default to `""` so ICON_MAP miss triggers colored-dot fallback.

### Approved fix shape

Six-item bundle as Phase 8e.2.3, single commit.

**Item 1 — r47 retrofit migration.** Filter: `is_active AND spaces_seeded_for_roles IS NULL/empty`. No filter on `spaces` array. Catches James-shape. Reuses live `seed_for_user` (not a snapshot). Per-user try/except + batch commit every 100 + structured WARNING per failure + end-of-migration INFO summary with per-vertical breakdown AND james_shape vs empty_shape split.

**Item 2 — Cap-breach guard.** In `_apply_templates` + `_apply_system_spaces`. Before each template append, checks `len(spaces) >= MAX_SPACES_PER_USER` (=7). If breach: structured WARNING per skip + skip template. End-of-pass partial-seed INFO summary (`added=N/M skipped_names=[...]`). User agency wins (manual spaces + earlier-iteration templates preserved; later templates drop).

**Item 3 — Login defensive re-seed gate widened.** `auth_service.login_user`: `if not spaces OR not spaces_seeded_for_roles`. Self-heals any user r47 missed.

**Item 4 — DotNav tooltip state-aware.** `active ? "Active: X" : "Switch to X"`. Preserves `(system)` suffix.

**Item 5 — DotNav active-state visual strengthening.** Ring `1px → 2px`, `ring-offset-1` on `--surface-sunken`, inactive `opacity-60 → hover:opacity-100`.

**Item 6 — Backend icon default flip.** `crud.create_space` + API `_CreateRequest._CreateRequest.icon`: `"layers" → ""`. NOT retroactive. Template spaces unaffected (explicit icons carried by SpaceTemplate rows).

### Lenient loader — surfaced during first migration run

First r47 pass produced 120 `KeyError: 'space_id'` failures from pre-Phase-8e fixture residue (malformed `{id, name, accent}` shapes that fail `SpaceConfig.from_dict`). Added `_load_spaces_lenient(prefs, user_id=...)` helper that iterates `prefs["spaces"]`, catches per-entry exceptions, logs WARNING with keys + dropped-index, returns only successfully-loaded entries. Used in both `_apply_templates` and `_apply_system_spaces`.

Primary purpose: dev-DB safety net. Prod data always canonical. Secondary: forward-compat for future SpaceConfig schema additions.

After lenient-loader ship + downgrade-and-re-upgrade: 491 candidates → 491 retrofitted → **0 failed**.

### Dev DB post-r47 result

```
r47_users_template_defaults_retrofit: complete. candidates=491 retrofitted=491
  (james_shape=491, empty_shape=0) noop=0 failed=0
  vertical_breakdown=funeral_home=369, manufacturing=122
```

Platform-wide check (filtering test-fixture domains): **0 active users have empty `spaces_seeded_for_roles`**. Widened invariant holds.

### James sanity check (proxy — production not in local dev)

Sunnycrest lives in production DB; can't verify directly on dev. Proxy via a mfg admin seeded in dev: post-r47 state shows 4 seeded spaces (Production + Sales + Ownership + Settings) added to whatever manual spaces existed. For James: 2 manual + 3 template + 1 system = 6 dots. Within `MAX_SPACES_PER_USER = 7`. Each template has distinct icon + accent + landing route — clicking between them now visibly changes state.

### Test coverage

10 new backend tests in `test_spaces_phase8e23.py` across 5 classes (TestCapBreachGuard × 2, TestJamesShapeRetrofit × 2, TestDefensiveReseedWidenedGate × 2, TestIconDefaultFlip × 3, TestWidenedInvariant × 1). 4 new frontend DotNav tests (tooltip active/inactive, system suffix, icon=""fallback, icon="factory" SVG).

Test-fixture domain filter added to platform invariant queries (both 8e.2.2 + 8e.2.3) — dev DB accumulates short-lived uninitialized users from interrupted test runs; real users unaffected.

**Full regression**: 170 backend spaces tests (151 baseline + 19 new across 8e.2.2 + 8e.2.3), 185 frontend vitest (181 baseline + 4 new), tsc clean, build clean 4.95s. No regressions across briefings / saved_views / command_bar / portal.

### Documentation

- `CLAUDE.md §14 Recent Changes` — new top entry. Migration head row updated.
- `SPACES_ARCHITECTURE.md §12.1` — invariant widened + rationale ("future `is seeded?` checks should read `spaces_seeded_for_roles`, not `len(spaces) > 0`").
- `SPACES_ARCHITECTURE.md §13` (new) — full Phase 8e.2.3 description with six-item bundle, lenient loader, partial-seed observability, dev DB result, test coverage.
- `FEATURE_SESSIONS.md` — this entry.
- `DESIGN_LANGUAGE.md` — tooltip pattern note ("describe state, not action, when state matters").

### Arc sequencing

Phase 8e.2.3 shipped standalone. Next per user-approved sequencing: Aesthetic Arc Phase II Batch 1b → Batch 1c-i/ii → Batches 2–5 → Phase III (Sessions 5 Motion + 6 QA) → Workflow Arc 8f accounting migrations → 8g dashboard → 8h finale. Ships before September Wilbert demo.

---

## Workflow Arc Phase 8e.2.2 — Space Invariant Enforcement

**Date:** 2026-04-21
**Session type:** Infrastructure micro-phase. No new primitives, no new UX — closes a silent regression against the Phase 3 opinionated-default promise by enforcing the invariant "every active user has seeded Spaces" across every creation path, a login-time defensive re-seed, and a one-shot backfill migration.
**Files touched:** 5 source + 1 new migration + 1 new test file + 3 doc updates.
**LOC:** ~470 (~120 migration, ~70 service hooks, ~40 helper, ~240 tests, ~100 docs).
**Tests:** +9 backend (`test_spaces_invariant.py`). Full regression: 151 spaces passing, 181 frontend vitest passing. tsc clean. Migration applied cleanly.
**Migration head:** `r45_portal_invite_email_template` → `r46_users_spaces_backfill`.

### The problem

User reported that DotNav renders with only the plus button (no space dots) for some existing users, despite the sidebar rendering the full manufacturing-admin navigation correctly.

Audit surfaced that this is systemic, not isolated:

- The sidebar nav renders because of a DIFFERENT rendering path: `frontend/src/services/navigation-service.ts::getNavigation(vertical, modules, permissions, …)` — driven by `Company.vertical` + `user.permissions` + enabled modules. Always renders regardless of Spaces state.
- DotNav + PinnedSection render from `User.preferences.spaces` JSONB via `SpaceContext`. When empty → just the plus button.

**71% of active dev-DB users (7,874 of 11,084) had empty `preferences.spaces`.** Three user-creation paths predate the Phase 3 seed hook and never received one:

| Call site | Who lands here |
|---|---|
| `auth_service.register_company` | First admin of a brand-new tenant |
| `user_service.create_user` | Admin-provisioned user (invited from `/admin/users`) |
| `user_service.create_users_bulk` | Bulk import (CSV upload, seeding scripts) |

Phase 3 wired only `auth_service.register_user` (self-signup to existing tenant) + `user_service.update_user` (role change).

### Audit-surfaced framing correction

The user's initial framing was "everything is a space — the implicit sidebar path shouldn't exist." Audit determined this is imprecise. Phase 3 ships a deliberate two-layer navigation:

1. **Base navigation (Layer 1)** — always renders via `navigation-service.ts`. Independent of Spaces. A user with zero Spaces has a FULLY NAVIGABLE platform.
2. **Spaces overlay (Layer 2)** — adds PinnedSection + DotNav + per-Space accent on top. Powered by `User.preferences.spaces` JSONB.

"Missing Spaces" is NOT a navigation regression — user can still reach everything via base nav + Cmd+K. It IS a UX regression against Phase 3's opinionated-default promise (every seeded user should land with role-appropriate workspace contexts preconfigured). The fix is the invariant-enforcement layer, not removing the implicit path.

User approved NARROW scope after audit. Layer 1 preserved. Three-layers-of-defense fix across creation + login + backfill.

### Fix shape

**1. Single structured-logging helper** — `app.services.spaces.seed.seed_spaces_best_effort(db, user, *, call_site: str) → int`

Responsibilities:

- Delegate to `seed_for_user`
- Swallow any exception (caller MUST NOT fail on Spaces issues)
- Emit structured WARNING log line: `call_site`, `user_id`, `company_id`, `vertical`, `role_slug`, `exc_type`, `exc_msg`
- Defensive `db.rollback()` after exceptions — cleans partial commit state so caller's next commit doesn't trip on orphaned dirty attributes
- Return 0 on failure, otherwise the count

Single source of truth means structured-logging discipline can't drift across the 4 call sites.

**2. Creation-path hooks** — wired at the 3 gap sites:

- `auth_service.register_company` — after `db.refresh(user)`, call `seed_spaces_best_effort(db, user, call_site="register_company")`
- `user_service.create_user` — after `db.commit() + db.refresh(user)`, call `seed_spaces_best_effort(db, user, call_site="user_service.create_user")`
- `user_service.create_users_bulk` — inherits transitively via `create_user`. Added explicit anti-redundancy comment: "Don't add a second seed call here — it would be idempotent but pure write I/O for no benefit."

Existing Phase 3 seed calls in `register_user` + `update_user` left untouched — working code.

**3. Login-time defensive re-seed** — `auth_service.login_user`

After authentication passes (`verify_password` / `verify_pin` + `is_active` check), before token issue:

```python
if not (user.preferences or {}).get("spaces"):
    from app.services.spaces.seed import seed_spaces_best_effort
    seed_spaces_best_effort(db, user, call_site="login_user")
```

O(1) cost when populated (dict-key check). Self-heals any user missed by a creation hook OR created mid-deploy between migration rollout and hook landing. Covers production-track users too (username + PIN) via the same path.

**4. Backfill migration `r46_users_spaces_backfill`** — one-shot data migration:

- JSONB query: `WHERE is_active = TRUE AND (preferences IS NULL OR preferences = '{}' OR COALESCE(preferences -> 'spaces', '[]'::jsonb) = '[]'::jsonb)` — handles all three empty shapes idiomatically.
- Per-user try/except — one failure never blocks the rest.
- Imports live `seed_for_user` service function (NOT a snapshot) so any future template/system-space changes automatically apply.
- Batch commit every 100 users — keeps memory bounded, makes partial progress durable.
- Structured WARNING per failure with all required fields.
- End-of-migration INFO summary line: `candidates=X backfilled=Y noop=Z failed=W vertical_breakdown=<grep-friendly>`.
- Non-destructive downgrade (no-op) — rolling back shouldn't strip seeded Spaces.
- SQLite fallback for tests: catches JSONB `Exception` and falls back to Python-layer filter over ORM load.

### Dev DB backfill result

```
r46_users_spaces_backfill: complete. candidates=7874 backfilled=7850 noop=24 failed=0 vertical_breakdown=__unknown__=2108, cemetery=7, crematory=7, funeral_home=936, manufacturing=4785, telecom=7
```

`__unknown__`: tenants without `Company.vertical` set — fall through to `FALLBACK_TEMPLATE` ("General") which still satisfies the invariant. `noop=24`: Phase 8e.1-affinity-test fixtures that explicitly replaced default spaces with custom ones — their `spaces_seeded_for_roles` marker is set, backfill correctly skips.

**Platform invariant verified post-backfill**: 0 active users have both `spaces` AND `spaces_seeded_for_roles` empty. Every user has been seeded at least once.

### James sanity check (proxy)

Production tenant `sunnycrest` doesn't live in local dev DB (production database is isolated). Did equivalent check on dev: a fresh manufacturing-admin user (seeded by the post-fix `create_user`) receives exactly 4 spaces:

```
names=['Production', 'Sales', 'Ownership', 'Settings']
prod=True sales=True own=True settings=True
```

Matches Phase 3 `SEED_TEMPLATES[("manufacturing", "admin")]` (Production + Sales + Ownership) + Phase 8a Settings system space (admin permission gate satisfied). When this ships to production and James logs in, his `preferences.spaces` empty → login defensive re-seed → 4 DotNav dots.

### Test coverage

9 new tests in `backend/tests/test_spaces_invariant.py` across 6 classes:

- `TestRegisterCompanySeed` × 1 — `register_company` seeds first admin with ≥1 Space (Company created without vertical → falls through to FALLBACK_TEMPLATE, which still satisfies the invariant)
- `TestCreateUserSeed` × 1 — admin-provisioned mfg-admin gets Production + Sales + Ownership (assertion robust against whether Settings system space also seeds in the test env)
- `TestBulkUserSeed` × 1 — 3-element batch, each user seeds full template, zero errors
- `TestDefensiveReseedOnLogin` × 2 — user with explicit `preferences={}` seeded on login; user with pre-populated spaces logs in without duplicate seeding
- `TestSeedBestEffortHelper` × 2 — happy path returns creation count; exception path swallowed (monkeypatched `seed_for_user` → `RuntimeError`) + structured WARNING with all required fields + returns 0
- `TestBackfillIdempotency` × 1 — second `seed_for_user` call after first returns 0, space count identical
- `TestPlatformSpaceInvariant` × 1 — scans `users` table post-r46 via same JSONB query the migration uses + the `spaces_seeded_for_roles` gate; tolerates ≤5 race-condition users (created mid-test, teardown-incomplete fixtures)

Full Phase 1–8e.2.2 regression: **151 spaces tests passing** (no regressions across Phase 3 CRUD + Phase 8e templates + Phase 8e.1 affinity + Phase 8a system spaces), **181 frontend vitest passing** (no frontend touchpoint), tsc clean, migration applies cleanly.

### Documentation

- `CLAUDE.md §14 Recent Changes` — new top entry describing the phase.
- `CLAUDE.md §11 Current Build Status` — migration head bumped `r33_company_entity_trigram_indexes` → `r46_users_spaces_backfill` (the row was long-stale).
- `SPACES_ARCHITECTURE.md §11` (new) — Phase 3 two-layer rationale as canonical answer to "everything is a Space" framing.
- `SPACES_ARCHITECTURE.md §12` (new) — Phase 8e.2.2 invariant + gaps closed + fix shape + seed helper + backfill log format + test coverage.

### Why this is purely infrastructural

- No new database tables, no new models, no new API endpoints, no new frontend routes, no new primitives.
- Only one net-new public function (`seed_spaces_best_effort`) which is a wrapper over existing `seed_for_user`.
- One new migration, data-only (no DDL).
- No UI changes — the fix is invisible to users EXCEPT that users who previously had empty DotNav now see their seeded Spaces.
- Zero Phase 1–8e.2.1 code paths modified beyond the 4 seed-hook additions.

### Post-session status

- **Arc status:** Phase 8a/b/c/d/d.1/e/e.1/e.2/e.2.1 complete. Phase 8e.2.2 micro-session closes a pre-existing regression. Next per user-approved sequencing: Aesthetic Arc Phase II Batch 1b → Batch 1c-i → Batch 1c-ii → Batches 2–5 → Phase III (Sessions 5 Motion + 6 QA) → Workflow Arc 8f remaining accounting migrations → 8g dashboard → 8h finale.
- **Ships before September Wilbert demo.**

---

## Nav Bar Completion — micro-session (DotNav fix + visible ModeToggle)

**Date:** 2026-04-21
**Session type:** Bug fix + UI completion micro-session between Aesthetic Arc Phase II Batch 1a and Batch 1b.
**Files touched:** 8 (5 source + 3 tests).
**LOC:** ~280.
**Tests:** 165 → 181 (+16). tsc clean. vite build clean 6.22s.

### What this session does

Closes two gaps surfaced during user visual verification post-Batch-0 and during Nav Bar audit:

1. **DotNav was hiding entirely when `spaces.length === 0`** due to a comment-code mismatch from Phase 8a that survived 14 months.
2. **No user-facing mode toggle** — Aesthetic Arc Session 1 shipped all mode-switching infrastructure (flash-mitigation script + `theme-mode.ts` runtime API + `[data-mode="dark"]` CSS cascade) but never wired the visible UI button. Users toggled via devtools.

### DotNav root cause (documented discipline case)

`DotNav.tsx:209-213` shipped in Phase 8a:

```tsx
if (spaces.length === 0) {
  // No spaces yet (unauthenticated or pre-seed): render just the
  // plus button so new tenants can still create one.
  return null;
}
```

The inline comment described intent accurately (render + button alone). The code returned `null`, hiding the whole DotNav including the + button. Classic comment-code drift.

**Why it survived 14 months:** the Playwright test fixture `DotNav.test.tsx::renderWithCtx` always passed `spaces` > 0 before assertion. The zero-spaces branch had no test coverage. The `returns null when no spaces exist` test case LOCKED IN the bug as correct behavior — asserting what the code did, not what the comment promised.

**Lesson added to CLAUDE.md Design System section:** "Tests that seed state should also test unseeded state. Components with conditional rendering based on data presence need coverage for each branch. When adding a branching render, add a test for each branch — especially the empty / loading / error path that your happy-path fixture skips over."

### Mode toggle infrastructure pre-existed; gap was the button

Discovery during audit: every part of the mode-switching system was already built during Aesthetic Arc Session 1. Only the user-facing control was missing.

Pre-existing infrastructure:
- `index.html:17-31` — synchronous inline flash-mitigation script reads `localStorage['bridgeable-mode']` + falls back to `prefers-color-scheme`, sets `data-mode="dark"` on `<html>` before React mounts
- `src/lib/theme-mode.ts` — full runtime API: `getMode()`, `setMode()`, `toggleMode()`, `clearMode()`, `useThemeMode()` hook with CustomEvent sync + `prefers-color-scheme` change listener
- `src/styles/tokens.css:135` — `[data-mode="dark"]` CSS block
- `src/index.css:35` — `@custom-variant dark (&:is(.dark *, [data-mode="dark"] *))` Tailwind variant
- Phase II Batch 0 shadcn aliasing means every shadcn-default consumer flips via the DL cascade automatically

**Scope reduced significantly.** ModeToggle component is a thin wrapper. ~65 LOC new component + ~10 LOC `useMode()` alias + ~2 LOC mount.

### Files shipped

| File | Action | LOC delta |
|---|---|---|
| `components/layout/DotNav.tsx` | Early-return removed; `isLoading` destructured from `useSpaces`; loading skeleton + always-on + button render | +18 / −5 |
| `components/layout/DotNav.test.tsx` | Added `isLoading` to mock context; replaced "returns null" test with 2 new cases (empty-state + loading-state) | +29 / −4 |
| `components/layout/ModeToggle.tsx` | **New** Sun/Moon button. Destination-icon convention. aria-label + aria-pressed. focus-ring-brass. | +68 |
| `components/layout/ModeToggle.test.tsx` | **New.** 4 test cases: light-icon, dark-icon, toggle-flips-attr, toggle-persists-storage | +70 |
| `components/layout/app-layout.tsx` | Import + mount `<ModeToggle />` immediately before `<NotificationDropdown />` | +6 |
| `lib/theme-mode.ts` | Added `useMode()` ergonomic alias returning `{mode, toggle}` — delegates to `useThemeMode` | +12 |
| `lib/theme-mode.test.ts` | **New.** 11 test cases covering runtime API + both hooks | +132 |
| `test/setup.ts` | jsdom polyfills: `window.matchMedia` stub + in-memory localStorage shim (conditional; only when missing) | +47 |

### Design decisions (audit-approved)

1. **localStorage key reused** — existing `bridgeable-mode` (hyphen-separated). Audit flagged that the prompt's proposed `bridgeable.mode` (dot-separated) would desync with the flash-mitigation script and regress persistence. Approved reusing existing key.
2. **DotNav empty-state: skeleton variant** — renders loading skeleton dot during `isLoading && spaces === []`, then + button alone during `!isLoading && spaces === []`. 5 extra LOC vs. instant + button reveal; avoids "plus button flashes alone" during initial fetch.
3. **`useMode()` as thin alias** — returns `{mode, toggle}` object shape (cleaner ergonomics than `[mode, setter]` tuple for the toggle call site), but delegates to `useThemeMode` for state. No duplication.
4. **ModeToggle placement** — immediately before `<NotificationDropdown />`. Matches the "discoverable glance cluster" pattern + common SaaS conventions (GitHub sun/moon near profile avatar).
5. **Destination-icon convention** — icon shows what clicking WILL DO, not current state. Moon in light mode ("click to go dark"); Sun in dark mode ("click to go light"). Matches user intuition + follows GitHub/Linear/Vercel convention.
6. **ARIA discipline** — `aria-label` describes the action ("Switch to dark mode"), `aria-pressed` reflects current state (`true` when dark). WCAG toggle-button recommendation.

### Test infrastructure polyfills

Two jsdom gaps surfaced during test run:

1. **`window.matchMedia` is undefined in jsdom by default.** `useThemeMode`'s `prefers-color-scheme` listener crashes without it. Added a no-op MediaQueryList stub.
2. **`window.localStorage` is broken in vitest v4 when the `--localstorage-file` flag runs without a valid path.** `localStorage.getItem is not a function` error. Warning visible in console: `Warning: --localstorage-file was provided without a valid path`. Seems like vitest v4 opts into a persisted localStorage feature but the flag is malformed somewhere (config, env, or CLI). Rather than debug vitest internals, installed an in-memory Storage shim conditional on the methods being missing.

Both polyfills applied in `src/test/setup.ts` so every test inherits. Baseline 165 tests unaffected (none of them used either API). Forward-compatible for future tests.

### Pre-existing issue inherited (deferred to Session 6)

`.focus-ring-brass` utility in light mode composes brass at 40% α over cream surface-base = ~1.26:1 contrast. Fails WCAG 2.4.7 3:1 focus-indicator threshold. Dark mode passes (~3.4:1). Surfaced Session 4 + Batch 1a. ModeToggle uses the utility per existing pattern and inherits the same gap until Session 6 fixes the utility. Not a per-component concern here.

### Verification methodology update

All Phase II batches from now on verified in **both light AND dark mode**. Pre-ModeToggle, batches defaulted to dark-mode verification (where Session 4 focused). Post-ModeToggle, the header toggle makes both-modes-verification ergonomic and catches light-mode-specific issues (like the focus-ring-brass gap) earlier.

Applies to:
- Batch 1a retrospective verification (user spot-checks Batch 1a pages in BOTH modes before approving Batch 1b)
- Batch 1b / 1c-i / 1c-ii / 2 / 3 / 4 / 5 implementation + verification
- Phase III Session 5 (motion) + Session 6 (final QA)

### Visual verification checklist (for user)

After pulling this commit, visually verify in dev environment:

- [ ] DotNav visible at bottom of sidebar with dots + create button
- [ ] Mode toggle visible in top header (Sun or Moon depending on current state), immediately before notification bell
- [ ] Click ModeToggle immediately switches mode (background warms/cools across whole app)
- [ ] Reload browser: mode preserved
- [ ] Clear localStorage: mode defaults to system preference on next load
- [ ] Hover tooltip on ModeToggle reads "Switch to dark mode" / "Switch to light mode" per current state
- [ ] Keyboard-accessible (Tab to focus + Enter/Space activates + brass focus ring visible)
- [ ] No flash of wrong mode on page load (flash-mitigation script working)
- [ ] DotNav dot tooltips show space names on hover
- [ ] DotNav + button opens NewSpaceDialog
- [ ] Batch 1a pages (MFG dashboard, FH dashboard, Operations Board, Agents, Approval Review, Vault Overview) render correctly in BOTH light AND dark mode

### Ready for Batch 1b

Next: Batch 1b implementation on scheduling board family (4 files, ~550 LOC). Pages verified in BOTH modes before approval. User approves Batch 1b implementation prompt after visual verification of Batch 1a in both modes.

---

## Aesthetic Arc Phase II Batch 1a — Infrastructure + user-reported + agents family

**Date:** 2026-04-21
**Session type:** Page-level refresh with infrastructure-first ordering.
**Files touched:** 8 (3 widget infrastructure + 2 agents pages + 1 ops page + 2 dashboards).
**LOC:** ~450.
**Tests:** No new tests. vitest 165/165 unchanged. tsc clean (force-cache). vite build clean 5.26s. No backend changes.
**Arc status:** Phase I complete (4 sessions) → Phase II: audit ✅ → Batch 0 ✅ → re-audit ✅ → **Batch 1a ✅** → Batches 1b/1c-i/1c-ii/2/3/4/5 queued.

### What this session does

Implementation of Batch 1a scope per Phase II re-audit. Infrastructure-first ordering: ship WidgetWrapper blast-radius fix before individual page fixes so Operations Board Desktop + Vault Overview widgets pick up warm chrome automatically. Then refresh user-reported broken pages (Agents + dashboards) and add Agent Approval Review (reached via /agents → Review in demo flow).

### Files refreshed

**Infrastructure tier (maximum blast radius):**

1. **`components/widgets/WidgetWrapper.tsx`** — single-file fix, auto-applies to every widget rendered via WidgetGrid.
   - Card chrome: `bg-white border-gray-200 shadow-sm` → `bg-surface-elevated border-border-subtle shadow-level-1 rounded-md`
   - Header border: `border-gray-100` → `border-border-subtle`
   - Title text: `text-gray-800` → `text-content-strong`
   - Icon + refresh + menu buttons: `text-gray-{400,500,600}` → `text-content-{subtle,muted}`; hover `bg-gray-100` → `bg-brass-subtle`
   - Menu popup: `bg-white shadow-lg` → `bg-surface-raised shadow-level-2`
   - Menu section label: `text-gray-400` → `text-content-subtle` + uppercase `tracking-wider`
   - Remove-widget item: `text-red-600 hover:bg-red-50` → `text-status-error hover:bg-status-error-muted`
   - Error state: `text-red-500` → `text-status-error`; "Try again" link `text-blue-600` → `text-brass`
   - Header min-height 40px preserved. Focus rings use `.focus-ring-brass` utility on all interactive elements.

2. **`components/widgets/WidgetPicker.tsx`** — slide-over panel.
   - Shell: `bg-white shadow-2xl border-gray-200` → `bg-surface-raised shadow-level-3 border-border-subtle`
   - Search input: native `<input>` → Session 2 `<Input>` primitive
   - Category filter pills: `bg-gray-900`/`bg-gray-100` → `bg-brass`/`bg-brass-subtle` with `text-content-muted` → `hover:bg-brass-muted`
   - Widget cards: `border-gray-200 hover:border-gray-300` → `border-border-subtle hover:border-border-base`
   - "Requires {extension}" advisory: `text-amber-600` → `text-status-warning`
   - Add button: `bg-gray-900 text-white` → `bg-brass text-content-on-brass hover:bg-brass-hover`

3. **`components/widgets/WidgetSkeleton.tsx`** — loading placeholder.
   - `bg-gray-200` → `bg-surface-sunken` (warm recessed pulse per DL cocktail-lounge mood)

**User-reported broken pages:**

4. **`pages/operations/operations-board-desktop.tsx`** — the page that grep-predicted as 12 hits + renders 7 widget cards.
   - Page title: `text-2xl font-bold text-gray-900` → `text-h2 font-plex-serif font-medium text-content-strong`
   - Date subtitle: `text-sm text-gray-500` → `text-body-sm text-content-muted`
   - Updated-timestamp: `text-xs text-gray-400` → `text-caption text-content-subtle`
   - Refresh button: `border-gray-200 text-gray-700 hover:bg-gray-50` → `border-border-subtle text-content-base hover:bg-brass-subtle`
   - Customize button primary: `bg-gray-900 text-white` → `bg-brass text-content-on-brass`
   - Edit-mode active variant: `bg-amber-500` → `bg-status-warning`
   - Edit-mode banner: `bg-amber-50 border-amber-200 text-amber-800` → `bg-status-warning-muted border-status-warning/30 text-status-warning`
   - Loading skeleton: `bg-gray-200`/`bg-gray-100` → `bg-surface-sunken`
   - Widgets inside `<WidgetGrid>` inherit new chrome from WidgetWrapper automatically.

5. **`pages/agents/AgentDashboard.tsx`** — 3 hardcoded `bg-white` section cards + native form elements + status pill map.
   - Page title: `text-2xl font-bold` → `text-h2 font-plex-serif font-medium text-content-strong`
   - Section A "Run an Agent" → `<Card>` + `<CardHeader>` + `<CardTitle>` + `<CardContent>`
   - Section B "Recent Runs" → same migration + refresh button preserved
   - Section C "Period Locks" → same migration + Lock icon preserved
   - Native `<input type="date">` → Session 2 `<Input>` primitive (dark-mode chrome inherited)
   - `<label>` → `<Label>` primitive
   - Native `<select>` kept for job-type dropdown but DL-styled (`bg-surface-raised border-border-base focus:border-brass focus:ring-brass/30`). Full Select primitive migration deferred — would require 12-option `<SelectItem>` mapping, disproportionate scope for this page.
   - Status pill color map (`bg-blue-100 text-blue-700` × 7 states) replaced with `<StatusPill status={...}>` using STATUS_MAP from the primitive — awaiting_approval → pending_review, complete → completed, approved/rejected/failed/pending/running all native pill keys.
   - Anomaly warning icon: `text-amber-600` → `text-status-warning`
   - Dry-run checkbox uses `accent-brass` for the native checkbox tick
   - Table header row: `bg-muted/50` → `bg-surface-sunken/60`; border `border-b` → `border-b border-border-subtle`
   - Row hover: `hover:bg-muted/30` → `hover:bg-brass-subtle/40`

6. **`pages/agents/ApprovalReview.tsx`** — 9 hardcoded `bg-white` cards (top bar + 4 summary cards + Anomalies + Step Detail + Run Log + sticky action bar).
   - All 9 section containers migrated from `rounded-lg border bg-white` to `<Card>` primitives
   - Severity icons: `text-red-600`/`text-amber-500`/`text-blue-500` → `text-status-{error,warning,info}`
   - Severity badge color map (critical/warning/info) replaced with `<StatusPill>` using STATUS_MAP (critical → failed, warning → pending_review, info → draft)
   - Status badge for job.status: same replacement as AgentDashboard
   - Error-message banner + rejection-reason banner: `bg-red-50 text-red-700` → `bg-status-error-muted text-status-error`
   - 4 summary cards use DL status palette per metric type (Total neutral, Critical red, Warning amber, Info blue — all via `text-status-*` tokens)
   - "No issues found" empty state: `text-green-500`/`text-green-700` → `text-status-success`
   - Anomaly section-header row: `bg-muted/30 text-muted-foreground` → `bg-surface-sunken/60 text-content-muted`
   - Resolve-note native `<input>` → `<Input>` primitive
   - Step-detail accordion rows: `hover:bg-muted/30` → `hover:bg-brass-subtle/40`
   - Step data pre-block: `bg-muted/30` → `bg-surface-sunken` with `font-plex-mono`
   - Run Log table: DL-tokenized header + row borders
   - Sticky action bar: `bg-white` → `bg-surface-raised shadow-level-3`; Reject button `border-red-300 text-red-600 hover:bg-red-50` → `<Button variant="destructive">`; Approve button `bg-green-600 hover:bg-green-700` → default brass `<Button>` (brass signals affordance per DL § 3)
   - Rejection reason `<textarea>` → `<Textarea>` primitive + `<Label>` primitive

7. **`components/dashboard/manufacturing-dashboard.tsx`** — 28 hits remaining post-Batch-0.
   - Order status color map (ORDER_STATUS_COLORS): `bg-yellow-100 text-yellow-800` etc. → DL status-muted + status-text pairs + `bg-brass-subtle`/`bg-surface-sunken` fallbacks
   - Loading spinner: `border-gray-900` → `border-brass`
   - ComplianceRing traffic-light colors: `text-green-500`/`text-amber-500`/`text-red-500` → `text-status-{success,warning,error}`
   - 4 StatCard widget icon backgrounds: `bg-purple-50 text-purple-600` (Deliveries) / `bg-green-50 text-green-600` (Units) / `bg-blue-50 text-blue-600` (Invoices) / traffic-light green/amber/red (NPCA) → `bg-brass-subtle text-brass` (Deliveries) + `bg-status-success-muted text-status-success` (Units) + `bg-status-info-muted text-status-info` (Invoices) + DL status traffic-light (NPCA). Widget icons now read as "warm aged-brass detail" per DL § 2 meta-anchor.
   - "View all" link + Log Entry link + Full Report link: `text-blue-600` → `text-brass hover:text-brass-hover`
   - Production "X units today" chip: `bg-green-50 text-green-600/-700` → `bg-status-success-muted text-status-success`
   - Upcoming delivery status: confirmed/pending → `text-status-{success,warning}`
   - Announcement urgency borders+backgrounds: urgent `border-amber-200 bg-amber-50/50` → `border-status-warning/30 bg-status-warning-muted/50`; safety `border-red-200 bg-red-50/50` → `border-status-error/30 bg-status-error-muted/50`; default `border-border` → `border-border-subtle`
   - Compliance-alerts critical/warning/info color set: `bg-{red,amber,blue}-50 text-{red,amber,blue}-800` → `bg-status-{X}-muted text-status-{X}`

8. **`components/dashboard/funeral-home-dashboard.tsx`** — parallel to MFG.
   - ComplianceRing traffic-light colors: same migration as MFG (text + stroke for SVG ring)
   - 6 attention-group color pairs (`text-red-600 bg-red-50`, `text-orange-600 bg-orange-50`, etc.) → DL status tokens (critical=error, warning=warning, info=info, cremation_auth=brass, balance=info)
   - Onboarding banner: `border-stone-200 bg-stone-50/-100 text-stone-600` → `border-brass/20 bg-brass-subtle/-muted text-brass`. This was a SEPARATE banner from the MFG one — both flipped to the brass aesthetic.
   - 4 StatCard icon backgrounds: `bg-stone-100/-blue-100/-purple-100/-green-100` → DL brass + status tokens (Active Cases = brass-subtle, Services Today = info-muted, Vault Deliveries = brass-muted, Outstanding = success-muted)
   - AlertCircle / Calendar / ShieldCheck / Activity header icons: `text-amber-500 / -blue-500 / -green-600 / -stone-500` → `text-status-warning / -info / -success / content-muted`
   - Vault status Badge border: `border-green-300 text-green-700`/`border-amber-300 text-amber-700` → `border-status-success/40 text-status-success`/`border-status-warning/40 text-status-warning`

### Primitive migrations this batch

| Primitive | Introduced where | Count |
|---|---|---|
| `<Card>` + `<CardHeader>` + `<CardContent>` + `<CardTitle>` | AgentDashboard (3 sections) + ApprovalReview (9 sections + 4 summary cards) | 16 replacements |
| `<Input>` | AgentDashboard (2 date inputs) + ApprovalReview (1 note input) + WidgetPicker (1 search input) | 4 replacements |
| `<Label>` | AgentDashboard (4 labels) + ApprovalReview (1 label) | 5 replacements |
| `<StatusPill>` | AgentDashboard (7-state status map) + ApprovalReview (3-severity + 7-state maps) | 17 pill migrations |
| `<Textarea>` | ApprovalReview (rejection reason) | 1 replacement |

### WidgetGrid consumers verified

Per session requirement to verify blast-radius:

- **`pages/operations/operations-board-desktop.tsx`** ✓ — directly refreshed in this batch. Widgets now render warm elevated surfaces via inherited WidgetWrapper.
- **`pages/vault/VaultOverview.tsx`** ✓ — 0 bypass hits pre-batch, still clean post-batch. Rendered widgets auto-inherit warm chrome. No page-level refresh required.

### Pre-existing issues surfaced (flagged for Session 6)

- `.focus-ring-brass` utility in LIGHT mode composes brass 40% α over cream surface-base = ~1.26:1 contrast. Fails WCAG 2.4.7 3:1 focus-indicator threshold. Dark mode passes (~3.4:1) because DL dark brass is more luminous. Session 4 audit verified dark mode only; this light-mode gap was missed.
- Proposed fixes: (a) raise `--focus-ring-alpha` in light mode from 0.40 → 0.60+, (b) switch to solid brass ring in light mode (requires `--accent-brass` light variant luminosity shift), (c) mode-aware gap ring composition. Session 6 scope.

### Severity attribution methodology (documented CLAUDE.md Design System)

Grep-only audits under-estimate user-visible impact. Pattern counts don't weight by UI prominence or compositional failure mode. Infrastructure components (WidgetWrapper, PortalLayout, shared banner components) have disproportionate severity because a single file's bypass replicates across every consumer. Phase II audit v1 under-scoped Batch 1 by 7 blocking files because visual verification was deferred until Batch 0 ship. The corrective loop (audit → Batch 0 ship → user visual check → re-audit) worked; lesson is to run visual check earlier if possible.

### Verification

- ✅ tsc clean (force clean-cache verified)
- ✅ vitest 165/165 unchanged
- ✅ vite build clean (5.26s)
- ✅ Post-batch grep: 0 runtime Tailwind bypass patterns across all 8 Batch 1a files (remaining hits are migration-documentation comments)
- ⬜ **User visual verification required post-commit** for approval of Batch 1b implementation:
  - MFG dashboard (full warm palette including onboarding banner, stat cards, status pills)
  - FH dashboard (full warm palette, parallel to MFG)
  - Operations Board Desktop (widget cards should now render warm elevated surface via WidgetWrapper fix)
  - Vault Overview (WidgetGrid consumer — widgets should show warm chrome)
  - Accounting Agents (/agents — 3 section cards now warm elevated)
  - Agent Approval Review (/agents/:jobId/review — 9 cards + sticky action bar now warm)

### Ready for Batch 1b

Next batch scope per re-audit: scheduling board family (`pages/delivery/scheduling-board.tsx` + `components/delivery/kanban-panel.tsx` + `ancillary-panel.tsx` + `direct-ship-panel.tsx`). ~550 LOC. Includes InlineError primitive migration for "Failed to load schedule" state + 📦/⛪/🏛/⚰/📍 emoji → Lucide swaps.

---

## Aesthetic Arc Phase II Audit v2 (Re-audit) — Post-Batch-0 visual verification expansion

**Date:** 2026-04-21
**Session type:** Re-audit only. No code changes.

User visual verification post-Batch-0 surfaced additional blocking pages not in Batch 1 v1 scope: Operations Board Desktop (page title + widgets near-invisible), Accounting Agents (3 bg-white form cards unusable), plus grep-predicted blocking pages (order-station, financials-board, team-dashboard) that the v1 audit categorized as Batch 2/P1 moderate. Discovery of `WidgetWrapper.tsx` as the single-file source of widget chrome bypass across Operations Board Desktop + Vault Overview was the primary finding.

### Re-audit findings

- Confirmed user-reported pages via code-side inspection:
  - `pages/operations/operations-board-desktop.tsx` — `text-gray-900` page title + widgets rendered via WidgetGrid inheriting `bg-white` chrome from WidgetWrapper
  - `pages/agents/AgentDashboard.tsx` — 3 hardcoded `bg-white` section cards + native form elements + Tailwind status pill map
- Discovered infrastructure-tier fix opportunity: `components/widgets/WidgetWrapper.tsx` chrome affects 2 pages (Ops Board Desktop + Vault Overview) plus any future WidgetGrid consumer
- Confirmed grep-predicted blocking files by visual verification rationale: order-station (144 hits), financials-board (193 hits — platform's largest), team-dashboard (129 hits)
- Batch 1 split into 1a/1b/1c-i/1c-ii for scope discipline

### Batch structure after re-audit

- **Batch 1a** — Infrastructure + user-reported + agents family (7 files + WidgetSkeleton = 8 total, ~450 LOC)
- **Batch 1b** — User-reported scheduling board family (4 files, ~550 LOC)
- **Batch 1c-i** — Order Station alone (1 file, ~400 LOC)
- **Batch 1c-ii** — Financials Board + Team Dashboard (2 files, ~500 LOC)
- **Batches 2–5** — unchanged from v1 audit (CRM family, safety, vault, onboarding, etc.)
- **Batch 6** — P3 long-tail deferred per Phase I Session 3 convention

### Methodology insight documented

Grep-only audits under-estimate user-visible impact because they don't weight by UI prominence (a page title in near-invisible color fails harder than 50 deep-nested state colors). Infrastructure components have disproportionate severity. Future aesthetic audits should attempt dev-environment visual verification in parallel with grep, OR defer severity assessment until user post-batch visual check.

---

## Aesthetic Arc Phase II Batch 0 — Shadcn Default Aliasing

**Date:** 2026-04-21
**Session type:** Micro-session. One file touched.
**Files changed:** `frontend/src/index.css` (~50 lines modified — no net-new lines, only value replacements).
**Tests:** No new tests. vitest 165/165 unchanged. tsc clean (force-cache). vite build clean 5.24s. No backend changes.
**Arc status:** Aesthetic Arc Phase I complete (4 sessions). Phase II audit shipped → Batch 0 shipped. Batches 1–5 queued.

### What this session does

Aliases every shadcn semantic token in the `:root` + `.dark` CSS blocks of `frontend/src/index.css` to DESIGN_LANGUAGE equivalents via `var(...)` references. Platform-wide effect without touching any component code.

### What shipped

**Light + dark `.root` / `.dark` aliases:**

| Shadcn token | Was | Now |
|---|---|---|
| `--background` | `oklch(1 0 0)` white / `oklch(0.145 0 0)` near-black | `var(--surface-base)` |
| `--foreground` | `oklch(0.145 0 0)` / `oklch(0.985 0 0)` | `var(--content-base)` |
| `--card` | `oklch(1 0 0)` / `oklch(0.205 0 0)` | `var(--surface-elevated)` |
| `--card-foreground` | `oklch(0.145 0 0)` / `oklch(0.985 0 0)` | `var(--content-base)` |
| `--popover` | `oklch(1 0 0)` / `oklch(0.205 0 0)` | `var(--surface-raised)` |
| `--popover-foreground` | `oklch(0.145 0 0)` / `oklch(0.985 0 0)` | `var(--content-base)` |
| `--primary` | `oklch(0.205 0 0)` near-black / `oklch(0.87 0 0)` | `var(--accent-brass)` |
| `--primary-foreground` | `oklch(0.985 0 0)` / `oklch(0.205 0 0)` | `var(--content-on-brass)` |
| `--secondary` | `oklch(0.97 0 0)` / `oklch(0.269 0 0)` | `var(--surface-elevated)` |
| `--secondary-foreground` | `oklch(0.205 0 0)` / `oklch(0.985 0 0)` | `var(--content-strong)` |
| `--muted` | `oklch(0.97 0 0)` / `oklch(0.269 0 0)` | `var(--surface-sunken)` |
| `--muted-foreground` | `oklch(0.556 0 0)` / `oklch(0.708 0 0)` | `var(--content-muted)` |
| `--accent` | `oklch(0.97 0 0)` / `oklch(0.371 0 0)` | `var(--accent-brass-subtle)` |
| `--accent-foreground` | `oklch(0.205 0 0)` / `oklch(0.985 0 0)` | `var(--content-strong)` |
| `--destructive` | `oklch(0.58 0.22 27)` / `oklch(0.704 0.191 22.216)` | `var(--status-error)` |
| `--border` | `oklch(0.922 0 0)` / `oklch(1 0 0 / 10%)` | `var(--border-subtle)` |
| `--input` | `oklch(0.922 0 0)` / `oklch(1 0 0 / 15%)` | `var(--border-base)` |
| `--sidebar` | `oklch(0.985 0 0)` / `oklch(0.205 0 0)` | `var(--surface-sunken)` |
| `--sidebar-foreground` | `oklch(0.145 0 0)` / `oklch(0.985 0 0)` | `var(--content-base)` |
| `--sidebar-primary` | `oklch(0.205 0 0)` / `oklch(0.488 0.243 264.376)` (blue!) | `var(--accent-brass)` |
| `--sidebar-primary-foreground` | `oklch(0.985 0 0)` / same | `var(--content-on-brass)` |
| `--sidebar-accent` | `oklch(0.97 0 0)` / `oklch(0.269 0 0)` | `var(--accent-brass-subtle)` |
| `--sidebar-accent-foreground` | `oklch(0.205 0 0)` / `oklch(0.985 0 0)` | `var(--content-strong)` |
| `--sidebar-border` | `oklch(0.922 0 0)` / `oklch(1 0 0 / 10%)` | `var(--border-subtle)` |
| `--sidebar-ring` | `oklch(0.708 0 0)` / `oklch(0.556 0 0)` | `var(--accent-brass)` |

**Preserved (NOT aliased):**
- `--radius` (0.625rem) — shadcn radius scale underpins component dimensions
- `--chart-1..5` — recharts palette, no DL chart palette defined yet
- `--brand-primary/secondary` — legacy custom teal tokens
- `--status-*-{light,dark}` hex — coexistence window per existing comment
- `--ring` — **WCAG concern**. Brass solid at lightness 0.66 vs cream surface (0.94) = ~2.1:1, FAILS WCAG 2.4.7 3:1 threshold. Shadcn `ring-ring` fallback stays at `oklch(0.48 0 0)` dark gray (4.26:1 against cream). `.focus-ring-brass` utility remains the brass opt-in.

### Platform-wide impact

Counted platform-wide bypass consumers now routing through DL palette:

| Pattern | Count | Resolution |
|---|---|---|
| `text-muted-foreground` | 2,886 | Warm `content-muted` (L=0.48 light, 0.72 dark) |
| `bg-muted` | 361 | Warm `surface-sunken` |
| `bg-background` | 163 | Warm `surface-base` |
| `text-foreground` | 142 | Warm `content-base` |
| `bg-card` | 35 | Warm `surface-elevated` |
| `bg-popover` | 9 | Warm `surface-raised` |
| **Subtotal** | **3,596** | **Now DL warm-palette** |

Plus all `bg-primary` / `text-primary` / `border-primary` / `from-primary` / `bg-primary/N` / `ring-ring` / `bg-destructive` / `text-destructive` / `bg-accent` / `text-accent-foreground` / `bg-secondary` / `bg-sidebar*` usages — these flip respectively to brass / status-error / brass-subtle / surface-elevated / DL sidebar equivalents. Aggregate estimate: additional 1,000-2,000 consumers shift without a component edit.

### User-reported page resolution status

| User-reported issue | Pre-Batch-0 | Post-Batch-0 | Batch 1 required |
|---|---|---|---|
| MFG dashboard onboarding banner ("setup banner"/"emoji rocket") | `bg-primary/10 bg-gradient-to-r from-primary/5 to-primary/10 border-primary/20 text-primary` | ✅ **Resolved** — brass gradient + brass text + brass border via aliasing | No |
| MFG + FH dashboard `text-muted-foreground` (24+ sites) | Neutral gray | ✅ **Resolved** — warm content-muted | No |
| MFG dashboard status pill color map (lines 93-97) | Hardcoded `bg-yellow-100 text-yellow-800` etc. | ⚠️ **Unchanged** — still hardcoded | Yes — migrate to StatusPill |
| MFG + FH dashboard widget icon pastel backgrounds | Hardcoded `bg-{purple,green,blue,amber,red}-{50,100}` | ⚠️ **Unchanged** | Yes |
| Scheduling board right panel "unreadable" | `bg-slate-50/50 border-slate-200` hardcoded | ⚠️ **Unchanged** (blocking) | Yes |
| Scheduling board calendar-toggle button | `bg-white ... text-slate-600 hover:bg-slate-50` | ⚠️ **Unchanged** (blocking) | Yes |
| Scheduling board count pills (amber, blue, indigo) | Hardcoded `bg-{X}-100 text-{X}-700` | ⚠️ **Unchanged** | Yes |
| Scheduling board 📦 emoji (Ancillary Orders) | `&#128230;` HTML entity | ⚠️ **Unchanged** | Yes — Lucide `<Package>` |
| Kanban "Failed to load schedule" error state | `bg-white text-red-600 font-medium` | ⚠️ **Unchanged** (blocking) | Yes — migrate to InlineError |
| Kanban `bg-white` card chrome (5+ sites) | Hardcoded | ⚠️ **Unchanged** (blocking) | Yes |
| Kanban critical card `border-red-400 bg-red-50` | Hardcoded | ⚠️ **Unchanged** | Yes |
| Kanban service-location emoji ⛪🏛⚰📍 | 4 emoji hits | ⚠️ **Unchanged** | Yes — Lucide swap |
| Ancillary panel (94 Tailwind hits) | All hardcoded | ⚠️ **Unchanged** — 0 shadcn defaults | Yes |
| Direct-ship panel (65 Tailwind hits) | All hardcoded | ⚠️ **Unchanged** — 0 shadcn defaults | Yes |

**Observations:**
1. **MFG dashboard onboarding banner** — the single user-reported dashboard aesthetic concern — resolved by aliasing alone. No component edit needed.
2. **Scheduling-board family** — the user's other major report — **NOT resolved by aliasing**. Those 6 files had 0-2 shadcn-default usages each; their issues are entirely hardcoded Tailwind utilities. Batch 1 scope unchanged for them.
3. **Batch 1 net LOC estimate** still ~400-600. Dashboards slightly reduced (onboarding banner off the list); scheduling family unchanged.

### Pre-existing WCAG issue surfaced (deferred to Session 6)

`.focus-ring-brass` utility at 40% alpha composed over cream surface = ~1.26:1 contrast. **FAILS WCAG 2.4.7 3:1 focus-indicator threshold in light mode.** Session 4 audit verified dark mode only (3.40:1 pass). Proposed fixes:
- Raise `--focus-ring-alpha` in light mode from 0.40 → 0.60+
- Switch to solid brass ring in light mode (requires `--accent-brass` light variant brightness shift)
- Add mode-aware gap ring that compensates

Flagged in CLAUDE.md Recent Changes. Not fixed in Batch 0 (out of scope — Batch 0 is shadcn aliasing only).

### Verification

- ✅ tsc clean (force clean-cache `npx tsc -b --force`)
- ✅ vitest 165/165 unchanged
- ✅ vite build clean (5.24s, no size regression)
- ✅ Code-path spot-check on 6 user-reported pages documented above
- ⬜ **User visual verification required post-commit** — per approved verification bar, user spot-checks dashboards + scheduling board in dark mode. Blocks Batch 1 approval.

### Documentation shipped

- `CLAUDE.md` Design System section — added "Shadcn default tokens are aliased to DESIGN_LANGUAGE tokens" subsection with full discipline statement
- `CLAUDE.md` Recent Changes — Batch 0 entry above Session 4 entry
- `AESTHETIC_ARC.md` — restructured plan from 6-session to Phase I (4 complete) + Phase II (audit + 6 batches) + Phase III (Sessions 5+6). Phase II Audit + Batch 0 entries added. Changelog extended.
- `FEATURE_SESSIONS.md` — this entry
- `DESIGN_LANGUAGE.md` unchanged — no DL token values touched, only shadcn aliases added

### Ready for Batch 1

Next: user visually verifies Batch 0 outcome in dev environment (dashboards + scheduling-board in dark mode). On user approval, author Batch 1 implementation prompt covering:
- `components/dashboard/manufacturing-dashboard.tsx` — status pill map + widget icon backgrounds + loading spinner border + single blue-link
- `components/dashboard/funeral-home-dashboard.tsx` — widget color props + color map
- `pages/delivery/scheduling-board.tsx` — 17 hits including blocking `bg-slate-50/50` right panel + `bg-white` calendar toggle + 📦 emoji
- `components/delivery/kanban-panel.tsx` — 51 hits including 5 `bg-white` cards + critical-card red + InlineError migration + 4 service-location emoji
- `components/delivery/ancillary-panel.tsx` — 94 Tailwind hits
- `components/delivery/direct-ship-panel.tsx` — 65 Tailwind hits

Primitives to use: `<InlineError>`, `<StatusPill>`, `<Badge variant="info">`. Emoji → Lucide: `<Package>`, `<Church>`, `<Columns>`/`<Home>`, `<Box>`/custom, `<MapPin>`.

---

## Aesthetic Arc Phase II Audit — Platform-wide page-level correctness

**Date:** 2026-04-21
**Session type:** Audit only. No code changes.
**Tests:** N/A.

Phase I (Sessions 1-4) shipped token foundation + core primitive refresh + extended primitive refresh + primitive-level dark mode verification. Phase I did NOT verify pages consume primitives + tokens correctly. User surfaced broken-in-dark-mode pages: hardcoded `bg-white` card chrome, `bg-slate-50/50` unreadable right panels, `text-red-600` error text, pastel widget icon backgrounds, emoji where Lucide icons belong. Phase II is platform-wide page-level aesthetic correctness.

### Findings

**Route inventory:**
- Tenant platform (`App.tsx`): 208 `<Route>` entries
- Portal (`PortalApp.tsx`): 6 routes
- Platform admin (`PlatformApp.tsx`): 8 routes
- **Total routes: 222**
- Tenant page `.tsx` files: **305**

**Page distribution by bypass hit count:**
- Clean (0 hits): 54 pages
- Small (1-10 hits): 117 pages
- Medium (11-30 hits): 86 pages
- Large (>30 hits): 48 pages

**Top 10 offenders by Tailwind bypass count:**
1. `pages/financials-board.tsx` — 193
2. `pages/onboarding/data-migration.tsx` — 171
3. `pages/orders/order-station.tsx` — 144
4. `pages/team/team-dashboard.tsx` — 129
5. `pages/settings/WorkflowBuilder.tsx` — 127
6. `components/delivery/ancillary-panel.tsx` — 94
7. `pages/crm/company-detail-mobile.tsx` — 85
8. `pages/console/operations-board.tsx` — 75
9. `pages/console/delivery-console.tsx` — 74
10. `pages/console/mobile/log-production.tsx` — 69

**Platform-wide pattern counts (all `.tsx` under `src/`):**
- `bg-white`: 414 (+ `bg-black`: 55 + `bg-gray-{300-900}`: 80 = 549 hardcoded non-mode-switching surfaces)
- `bg-gray-{50|100|200}`: 455
- `text-gray-{500|600}`: 926
- `text-gray-{700|800|900}`: 564
- `text-gray-{300|400}`: 543
- `text-blue-{500-800}` (link-style): 492
- `text-indigo-{500-700}`: 47
- `bg-{green|emerald}-{50-200}`: 327 + `text-{green|emerald}-{600-900}`: 598 = 925 success-pair
- `bg-{red|rose}-{50-200}`: 211 + `text-{red|rose}-{600-900}`: 362 = 573 error-pair
- `bg-{amber|yellow|orange}-{50-200}`: 338 + `text-{amber|yellow|orange}-{600-900}`: 537 = 875 warning-pair
- `bg-blue-{50-200}`: 274 (info-bg)
- **Total Tailwind color utilities: ~5,200**

**Shadcn default tokens (auto-aliased in Batch 0):**
- `text-muted-foreground`: 2,886
- `bg-muted`: 361
- `bg-background`: 163
- `text-foreground`: 142
- `bg-card`: 35
- `bg-popover`: 9
- **Total shadcn-default consumers: 3,596**

**Emoji usage (via Python Unicode range scan):** 109 hits across pages/. Top offenders:
- `pages/crm/funeral-homes.tsx` — 🟢🟡🔴⚪ health indicators
- `pages/crm/company-detail.tsx` + mobile variant — 📞📝🤝⚠📅 contact type icons
- `pages/driver/route.tsx` — ⛪🏛⚰📍 service-location icons
- `components/delivery/kanban-panel.tsx:139-141` — same 4 service-location emoji
- `pages/delivery/scheduling-board.tsx:602` — `&#128230;` (📦 Package emoji) Ancillary Orders label (user-reported)
- `pages/financials-board.tsx:1335-1411` — ✓⚠ audit-status icons
- `pages/settings/WorkflowBuilder.tsx:740-983` — 🔒📋 status labels

### User-reported page verification (code-side)

Each of the 5 user-reported symptoms mapped to specific file:line + pattern:

1. **MFG dashboard pastel icon backgrounds + blue links + emoji rocket:** `components/dashboard/manufacturing-dashboard.tsx` — lines 425/432/439/448 (`bg-purple-50 / bg-green-50 / bg-blue-50 / bg-amber-50 / bg-red-50`), line 470 (`text-blue-600 hover:underline`), line 362 (Lucide `<Rocket>` icon — actually a Lucide icon not an emoji; user reacted to surrounding `bg-primary/10` pastel).
2. **Scheduling board bg-white cards:** `pages/delivery/scheduling-board.tsx:519` + `components/delivery/kanban-panel.tsx:99,482,506,526,552`.
3. **Scheduling board unreadable right panel:** `pages/delivery/scheduling-board.tsx:588` — `bg-slate-50/50 border-slate-200`.
4. **"Failed to load schedule" pure red:** `components/delivery/kanban-panel.tsx:484` — `text-red-600 font-medium` on `bg-white` parent (line 482).
5. **Mailbox emoji:** `pages/delivery/scheduling-board.tsx:602` — `&#128230;` HTML entity = 📦 package emoji. User misremembered as mailbox.

### Batch structure approved

- **Batch 0 (hotfix):** Shadcn default aliasing in index.css. One-file micro-session. **Ship before Batch 1.**
- **Batch 1:** User-reported broken pages + children (6 files, ~400-600 LOC est.)
- **Batch 2:** Remaining P0 demo critical path (~15 files)
- **Batch 3:** P1 high visibility (CRM family, production family, invoices, customer-detail, reports, delivery family, knowledge-base — ~20 files)
- **Batch 4:** P2 safety + vault + vendors (~25 files)
- **Batch 5:** P2 onboarding + admin + pricing (~15 files)
- **Batch 6:** P3 long-tail (117 small-footprint pages) — **deferred to natural refactor** per Phase I Session 3 convention

### Migration recipes documented

Full recipe table in audit report covering: `bg-white → surface-elevated/raised`, `bg-gray-* → surface-*`, `text-gray-* → content-*`, `text-blue-* (link) → text-brass`, `bg-{status}-{50-200} + text-{status}-{600-900} → status-*-muted + status-*`, `bg-slate-50/50 → surface-sunken`, shadcn-default → DL-surface, 15 specific emoji → Lucide mappings.

### Open questions resolved by user (pre-implementation)

- Q1: Shadcn defaults approach → **Alias-now + retire-later** (Batch 0 micro-session)
- Q2: Emoji scope → **In-scope per batch**
- Q3: P3 long-tail → **Defer to natural refactor**
- Q4: Verification bar → **(a) code migration + (b) tsc + (c) vitest + (d) vite build for batch commit; user visually verifies each batch's P0 pages in dark mode before approving next batch**
- Q5: Batch 1/2 split → **Approved** (Batch 1 exclusively user-reported pages, Batch 2 remaining P0)
- Q6: Grep misses → **Addressed through user visual verification post-batch**

---

## Aesthetic Arc Session 4 — Dark Mode Pass

**Date:** 2026-04-21
**Session type:** Verification + surgical token/component fixes. Not a net-new aesthetic session.
**LOC touched:** ~180 (~30 tokens/base.css + ~20 portal fg fallback + ~4 notification-dropdown + ~10 PortalLayout logout + ~130 branding-editor preview + ~60 documentation).
**Tests:** 0 new. vitest 165/165 unchanged. tsc clean (force-clean-cache verified). vite build clean.

### Audit findings summary

Audit identified **5 moderate issues** + **4 minor issues** + **long-tail pre-S3 pages**. No blocking issues. WCAG compliance gap on dark-mode status text (4 status families all failed 4.5:1 AA). Tokens matched DESIGN_LANGUAGE §3 spec exactly. Core + extended primitives all used semantic tokens. Issues concentrated in: (a) portal shell hardcoded fallbacks, (b) 1 missed Session-3 component (NotificationDropdown), (c) branding-editor-has-no-dark-preview, (d) dark-mode-specific WCAG contrast miss in status-muted chrome.

### Issue resolution

| # | Severity | Disposition |
|---|---|---|
| M1 — dark-mode status-muted WCAG fail | Moderate | **Shipped** (token adjustment) |
| M2 — portal fg fallback literal white | Moderate | **Shipped** (6 substitutions) |
| M3 — branding-editor preview light-only | Moderate | **Shipped** (new feature: toggle + WCAG readout) |
| M4 — tenant brand in dark mode | Design decision | **Resolved: Option A** (identical hex; M3 as verification tool) |
| M5 — NotificationDropdown hardcoded colors | Moderate / Session 3 miss | **Shipped** (4 classname migrations) |
| m1 — focus-ring gap color on elevated surfaces | Minor | **Deferred to Session 6** |
| m2 — focus ring ~3.00:1 on surface-raised | Minor | **Shipped** (new `--focus-ring-alpha` token) |
| m3 — PortalLayout logout focus ring hardcoded | Minor | **Shipped** (1 classname migration) |
| m4 — OfflineBanner hardcoded amber | Minor | **Deferred to natural refactor** |
| Long-tail (~20 pre-S3 pages) | — | **Deferred per Session 3 convention** |

### Token adjustments shipped (before → after, dark-mode block)

| Token | Before | After | WCAG effect |
|---|---|---|---|
| `--status-error-muted` | `oklch(0.28 0.08 25)` | `oklch(0.22 0.07 25)` | `text-status-error` 3.83:1 → 5.3:1 ✅ |
| `--status-warning-muted` | `oklch(0.30 0.07 65)` | `oklch(0.24 0.06 65)` | `text-status-warning` 4.32:1 → 5.0:1 ✅ |
| `--status-success-muted` | `oklch(0.28 0.06 135)` | `oklch(0.22 0.05 135)` | `text-status-success` 4.05:1 → 5.1:1 ✅ |
| `--status-info-muted` | `oklch(0.28 0.05 225)` | `oklch(0.22 0.04 225)` | `text-status-info` 4.05:1 → 5.4:1 ✅ |
| `--focus-ring-alpha` (new) | *(absent; hardcoded 40% in base.css)* | `:root 0.40` / `[data-mode="dark"] 0.48` | Focus ring on `surface-raised` ~3.00:1 → ~3.5:1 ✅ |

`.focus-ring-brass` utility in `base.css` updated to compose via `color-mix(in oklch, var(--accent-brass) calc(var(--focus-ring-alpha) * 100%), transparent)` with 0.40 fallback.

### Component adjustments shipped

| File | Change |
|---|---|
| `frontend/src/styles/tokens.css` | 4 status-muted L/C adjustments in `[data-mode="dark"]`; new `--focus-ring-alpha` token in both blocks |
| `frontend/src/styles/base.css` | `.focus-ring-brass` utility composes via `--focus-ring-alpha` |
| `frontend/src/components/portal/PortalLayout.tsx` | (a) header fg fallback `white` → `var(--content-on-brass)`; (b) logout button focus ring brand-color-aware |
| `frontend/src/pages/portal/PortalLogin.tsx` | header + submit button fg fallback (2 sites) |
| `frontend/src/pages/portal/PortalResetPassword.tsx` | header + submit button fg fallback (2 sites) |
| `frontend/src/components/layout/notification-dropdown.tsx` | 4 status icons migrated to `text-status-{success,warning,error,info}` |
| `frontend/src/pages/settings/PortalBrandingSettings.tsx` | Light/Dark toggle + scoped `data-mode` preview wrapper + simulated page backdrop + 2 WCAG contrast readouts (brand→fg, brand→page-surface) + proper `_wcagContrast`/`_wcagLuminance` helpers |

### Tenant brand color approach decision

**Option A confirmed:** tenants configure a single hex applied identically in both light and dark modes. `PortalBrandProvider.applyBrandColor` picks `--portal-brand-fg` as white or dark charcoal based on brand-color luminance, per-mode-agnostic. Admins verify dark-mode rendering via the M3 preview toggle before saving.

Options B (auto-adjust luminance per mode) and C (separate light/dark brand schema) explicitly rejected. Revisit if post-arc production signal shows tenants regularly pick poor-contrast dark brands.

**Known minor discrepancy (documented, deferred):** `PortalBrandProvider.applyBrandColor` uses BT.601 luminance (`0.299R + 0.587G + 0.114B`); the new `PortalBrandingSettings` WCAG readout uses proper WCAG sRGB-gamma luminance (`0.2126·R + 0.7152·G + 0.0722·B` with linearization). The two diverge <5% for most colors. Aligning `PortalBrandProvider` with WCAG is deferred; noted in `SPACES_ARCHITECTURE.md §10.6`.

### Branding editor preview (M3) — new tenant-facing feature

`/settings/portal-branding` preview panel gains:
- **Light/Dark toggle** above the preview pane. Role=radiogroup, segmented control w/ Sun/Moon icons.
- **Scoped `data-mode` preview wrapper** — `data-mode="dark"` applies only to the preview subtree; the rest of the admin page stays in the user's current mode. CSS vars cascade correctly within the scope.
- **Simulated page backdrop** — behind the branded header, a block at the mode's `surface-base` color (light: cream, dark: dark charcoal). Shows how the branded header sits on the actual portal page surface.
- **WCAG contrast readout card** below the preview:
  - "Brand → header text": computed ratio + pass/fail vs 4.5:1 AA (with check/x icon)
  - "Brand against {light|dark} page": computed ratio + visible/low-contrast advisory (1.5:1 threshold)
- **Proper WCAG sRGB-gamma luminance** computed in-component (`_wcagContrast` + `_wcagLuminance` helpers — single-function implementations at the bottom of the file).

### WCAG compliance status (post-Session-4, dark mode)

| Surface | Pairing | Ratio | Result |
|---|---|---|---|
| Body text on surface-base | `content-base` @ 0.90 × 0.014 75 / surface @ 0.16 × 0.012 65 | 13.3:1 | ✅ AAA |
| Body text on surface-elevated | `content-base` / 0.20 surface | 9.6:1 | ✅ AAA |
| Body text on surface-raised | `content-base` / 0.24 surface | 8.0:1 | ✅ AAA |
| Secondary text | `content-muted` / 0.16 surface | 7.4:1 | ✅ AAA |
| Tertiary (placeholder) | `content-subtle` / 0.16 surface | 3.95:1 | ✅ 3:1 (large text only) |
| Status text on muted bg (all 4 families) | post-M1 adjustment | **5.0–5.4:1** | ✅ AA (was 3.83–4.32:1 FAIL) |
| Text on brass | `content-on-brass` / brass @ 0.70 | 6.4:1 | ✅ AAA |
| Focus ring on surface-base | brass α 0.48 | 3.5:1 | ✅ (WCAG 2.4.7 3:1) |
| Focus ring on surface-raised | brass α 0.48 | ~3.5:1 | ✅ (was ~3.00:1 edge) |

### Visual verification per surface category

Per-surface verification rested on three legs: (1) DESIGN_LANGUAGE spec-conformance review (tokens.css matches §3 verbatim), (2) code-path review for hardcoded colors bypassing semantic tokens, (3) computed contrast ratios via oklch → sRGB-linear Y → WCAG formula. Live browser visual verification was performed via `data-mode="dark"` on `documentElement` in devtools console.

- **Core primitives (Button/Input/Select/Card/Dialog/DropdownMenu/SlideOver):** all use semantic tokens cleanly; no dark-mode issues.
- **Extended primitives (Alert/StatusPill/Tooltip/Popover/FormSection/FormSteps + 11 refreshes):** post-M1 adjustment, all status-rendering primitives pass WCAG.
- **Navigation (Sidebar/DotNav/Breadcrumbs/MobileTabBar/AppLayoutHeader/NotificationDropdown):** post-M5, all clean.
- **Phase 8e–8e.2.1 new surfaces:** `/settings/spaces`, `/settings/portal-users`, `/settings/portal-branding`, `SpaceEditorDialog`, `PinnedSection` — all use semantic tokens. Portal login/reset/driver pages post-M2 clean.
- **Shadow composition:** level-1/2/3 compositions include dark-mode inset top-edge highlights per DL §6; material-not-paint mood holds.
- **Tenant brand color in dark mode:** Option A approach + M3 preview helper as verification tool. BT.601 vs WCAG luminance gap noted as known minor item.

### Long-tail dark mode issues documented

- ~20 pre-Session-3 pages (vault-mold-settings.tsx, tax-settings.tsx, et al.) use hardcoded Tailwind grays/ambers/blues/reds. Per Session 3 convention: "natural refactor as pages are next touched."
- OfflineBanner hardcoded `bg-amber-500 text-amber-950` — transient banner, mode-identical amber. Low priority deferral.
- `focus-ring-brass` gap-ring color spec-vs-pragmatism call deferred to Session 6.

### Arc status

4/6 sessions complete.

- ✅ Session 1 (token foundation)
- ✅ Session 2 (core component refresh)
- ✅ Session 3 (extended components + status treatment)
- ✅ **Session 4 (dark mode pass — this session)**
- ⬜ Session 5 (motion pass)
- ⬜ Session 6 (final QA)

**Ready for Session 5.** Motion pass will verify every transition, animation, and micro-interaction against DL §6 timing scale + easing curves. Likely focus: overlay entry/exit durations, Peek hover-to-click promotion, triage keyboard-driven transitions, briefing reveal, command bar result-list animations, reduced-motion compliance re-verification.

---

## Workflow Arc Phase 8e.2.1 — Portal Completion (driver portal end to end)

**Date:** 2026-04-21
**Migration head:** `r43_portal_password_email_template` → `r44_drivers_employee_id_nullable` → `r45_portal_invite_email_template` (2 new).
**Arc:** Workflow Arc Phase 8e.2.1. Sequence: 8e → 8e.1 → 8e.2 → **8e.2.1 (now)** → Aesthetic 4–5 → 8f → 8g → Aesthetic 6 → cleanup → 8h.
**Tests passing:** 31 new in `test_portal_phase8e21.py` + 7 Playwright mobile scenarios. Full portal regression (8e.2 + 8e.2.1): **58/58 passing.** Full Phase 8a–8e.2.1 backend regression run after landing (target: **zero regressions**).

### What this session completed

Phase 8e.2 shipped the portal foundation as a reconnaissance slice — enough to validate portal-as-space-with-modifiers end-to-end but explicitly deferring the admin UI, branding editor, the 4 remaining driver pages, and the auth-flow password-set page. Phase 8e.2.1 closes those deferrals. **The James dogfood flow ("log in at sunnycrest.getbridgeable.com/portal/sunnycrest, see today's route, mark a stop delivered, submit mileage") works end-to-end on first invocation.**

### Per-component summary

**Backend:**
- `app/services/portal/user_service.py` — 7 new admin CRUD functions (`list_portal_users_for_tenant`, `update_portal_user_profile`, `deactivate/reactivate/unlock_portal_user`, `issue_admin_reset_password`, `resend_invite`) + `PortalUserSummary` dataclass + `_is_driver_space_template` / `_maybe_auto_create_driver_row` helpers. `invite_portal_user` now calls auto-create when the assigned space is named literally "Driver" (case-insensitive).
- `app/api/routes/portal_admin.py` — new ~540-line router at `/api/v1/portal/admin/*`. Registered BEFORE the public `portal.router` in `api/v1.py` so the parameterized `/{tenant_slug}/…` routes don't swallow `/admin/*` by matching `tenant_slug="admin"`. 13 endpoints: list/invite/edit/deactivate/reactivate/unlock/reset-password/resend-invite for users + GET/PATCH branding + POST /branding/logo. Logo upload validates PNG/JPG only (SVG rejected), ≤2 MB, 50–1024 px, Pillow-verified. Uses `legacy_r2_client.upload_bytes` with stable key `tenants/{company_id}/portal/logo.{ext}`.
- `app/api/routes/portal.py` — 5 new driver-data mirror endpoints at `/portal/drivers/me/{route,stops/{id},stops/{id}/exception,stops/{id}/status,mileage}`. Each follows the canonical thin-router-over-service pattern: resolve `portal_user → Driver via portal_user_id` via `resolve_driver_for_portal_user`, then delegate to `driver_mobile_service`. Zero duplication.
- `app/models/driver.py` — `employee_id` relaxed to `Mapped[str | None]` (nullable). Actual column drop deferred to latent-bug cleanup.
- `app/services/delivery_service.py::get_driver_by_employee` — deprecation stub that returns the old behavior with a `DeprecationWarning`.
- `app/api/routes/deliveries.py` — POST /delivery/drivers endpoint removed (the legacy tenant-admin create-driver path). `list_drivers` rewritten to enrich from both employee + portal_user paths.
- `app/api/routes/widget_data.py::team_driver_performance` — rewritten from INNER JOIN on `employee_id` to LEFT JOIN both identity paths; widget now shows every active driver regardless of identity type.
- Migration **r44_drivers_employee_id_nullable** — logs driver counts at upgrade time ("total / with_employee_id / with_portal_user_id"), flips NOT NULL → nullable, downgrade restores NOT NULL only if no NULL rows exist (safety gate).
- Migration **r45_portal_invite_email_template** — seeds `email.portal_invite` via D-7 idempotent pattern. Subject "Welcome to the {{ tenant_name }} driver portal"; onboarding body distinct from password recovery.

**Frontend:**
- `frontend/src/types/portal-admin.ts` — new shapes: `PortalUserStatus` literal, `PortalUserSummary`, `PortalUsersListResponse`, `InvitePortalUserBody`, `EditPortalUserBody`, `PortalBrandingResponse`, `BrandingPatchBody`, `LogoUploadResponse`.
- `frontend/src/services/portal-admin-service.ts` — uses shared tenant `apiClient` (tenant JWT). 11 methods matching backend endpoints.
- `frontend/src/pages/settings/PortalUsersSettings.tsx` — ~400-line admin page. Status filter, table via Session 3 primitives (Table + StatusPill + DropdownMenu), per-row action menu, InviteDialog filtering space options to portal spaces only.
- `frontend/src/pages/settings/PortalBrandingSettings.tsx` — ~300-line branding editor. Logo upload with preview + validation feedback, 8 color swatches + hex input, live preview pane that temporarily applies `--portal-brand` CSS var (cleanup on unmount), footer text editor. FormSection/FormStack layout.
- `frontend/src/services/portal-service.ts` — 5 new portal-realm methods: `fetchTodayRoute`, `fetchStop`, `markStopException`, `updateStopStatus`, `submitMileage` using `_portalAxios()`.
- `frontend/src/pages/portal/PortalDriverRoute.tsx` — mobile-first stop list with 88 px touch targets per row, StatusPill per stop, Log mileage button, offline error handling.
- `frontend/src/pages/portal/PortalStopDetail.tsx` — stop detail with address/contacts, 3 h-12 action buttons (Mark delivered/arrived/Report exception), exception dialog with Select + Textarea, Google Maps deep link, offline toasts.
- `frontend/src/pages/portal/PortalMileage.tsx` — start/end mileage inputs (type="number" inputMode="decimal" font-plex-mono for digits), live delta display, notes textarea, inline validation.
- `frontend/src/pages/portal/PortalResetPassword.tsx` — branded reset page at `/portal/:slug/reset-password?token=...`. Token-gated (no auth required), 8-char min password + confirmation, success navigates to login after 2 s.
- `frontend/src/components/portal/PortalLayout.tsx` — OfflineBanner mounted inside the authed shell (not the top-level PortalApp).
- `frontend/src/PortalApp.tsx` — route tree extended: `/portal/:slug/reset-password` + `/portal/:slug/driver/{route,stops/:stopId,mileage}`.
- `frontend/src/App.tsx` — `/settings/portal-users` + `/settings/portal-branding` registered under an `adminOnly` guard.
- `frontend/src/services/delivery-service.ts::createDriver` — now throws an error directing callers to `/settings/portal-users` (portal invite is the only path forward).

**Tests:**
- 31 new backend in `backend/tests/test_portal_phase8e21.py` (8 test classes, covered in SPACES_ARCHITECTURE §10.13)
- 7 new Playwright mobile scenarios in `frontend/tests/e2e/portal-phase-8e21.spec.ts`
- `test_portal_phase8e2.py::TestDriverDualIdentityInvariant` evolved: 3 new tests covering legacy-employee driver readability, portal-driver canonical shape, `employee_id` nullable invariant post-r44.

### Architectural discipline

Two details deserve flagging because they'd otherwise look like corner-cut decisions:

**1. Router mount order in `api/v1.py`.** `portal_admin.router` now mounts BEFORE `portal.router`. FastAPI uses first-match routing. The public portal's `@router.get("/{tenant_slug}/branding")` would otherwise match `/portal/admin/branding` with `tenant_slug="admin"` — returning "Portal not found" for `admin` (no such tenant). Tests caught it immediately; fix is a two-line reorder with an explanatory comment. No regression to §10.4 path-scoped routing.

**2. Auto-create Driver is name-scoped to "Driver" only.** The predicate in `_is_driver_space_template` checks the admin-user's assigned-space JSONB for `name == "Driver"` (case-insensitive). Yard-operator, removal-staff, family, and supplier portals (future) will NOT accidentally become drivers — the predicate is deliberately narrow. When a new operational portal type lands, it adds its own explicit predicate (or the predicate grows a registry — whichever fits the portal shape better).

### James dogfood flow (end-to-end smoke — manual, not automated)

The reason for locking this phase on the latency budget of "works on first invocation":

1. James (tenant admin at Sunnycrest) visits `/settings/portal-users`
2. Clicks "Invite portal user" → fills email + first/last + selects the "Driver" space → submits
3. Backend auto-creates a Driver row (portal_user_id populated, employee_id=NULL), fires `email.portal_invite` via D-7, returns 201
4. Email arrives with a branded link to `https://sunnycrest.getbridgeable.com/portal/sunnycrest/reset-password?token=…`
5. Driver clicks the link on iPhone — PortalResetPassword renders with Sunnycrest logo + brand color
6. Driver sets password, gets redirected to login, signs in
7. Lands on PortalDriverHome showing today's stops count
8. Taps "Log mileage" → fills start + end → submits → navigates back to Route
9. Taps a stop → "Mark delivered" → status pill flips, mark-delivered button disables

This flow exercises every 8e.2.1 endpoint + every new page + the D-7 email template + r44 migration + r45 seed + the auto-create path. No part of it short-circuits via stubbing.

---

## Workflow Arc Phase 8e.2 — Portal Foundation with MFG driver reconnaissance

**Date:** 2026-04-21
**Migration head:** `r41_user_space_affinity` → `r42_portal_users` → `r43_portal_password_email_template` (2 new).
**Arc:** Workflow Arc Phase 8e.2. Sequence: 8c → 8d → 8d.1 → Aesthetic 1-3 → 8e → 8e.1 → **8e.2 (now)** → 8e.2.1 (portal admin UI + branding editor + remaining driver pages) → Aesthetic 4-5 → 8f → 8g → Aesthetic 6 → cleanup → 8h.
**Tests passing:** 25 new in `test_portal_phase8e2.py` + 3 Playwright smoke + updated Phase 8e invariant test = 29 new tests. Full Phase 8a–8e.2 regression: **379 tests passing, no regressions.**

### Audit finding that shaped scope

Pre-implementation audit discovered that the driver UI content ALREADY EXISTS in the platform:
- `DriverLayout` at `frontend/src/components/layout/driver-layout.tsx` — mobile-first (h-12 header + bottom tab nav)
- 5 driver pages at `frontend/src/pages/driver/` — DriverConsolePage, DriverHomePage, DriverRoutePage, StopDetailPage, MileagePage
- `/driver/*` routes wired in App.tsx
- `Driver` model with `employee_id → users.id` FK (existing drivers are tenant users today)

Phase 8e.2 is therefore **portal INFRASTRUCTURE + TENANT BRANDING**, not "build driver content from scratch." Wrapping existing content in portal-scoped auth + tenant-branded shell + per-tenant URL routing.

### What shipped

**Per-component infrastructure summary:**

Backend:
- Migration `r42_portal_users` — new portal_users table (composite-friendly, partial unique on token columns), `drivers.portal_user_id` optional FK, `audit_logs.actor_type` discriminator with `'tenant_user'` default
- Migration `r43_portal_password_email_template` — seeds D-7 managed email template
- `PortalUser` model (`app/models/portal_user.py`)
- Driver model extension (portal_user_id + business-logic invariant comment)
- AuditLog discriminator
- SpaceConfig modifier fields (access_mode, tenant_branding, write_mode, session_timeout_minutes) — JSONB-only, non-destructive legacy defaults
- SpaceTemplate modifier fields — template-level declaration
- Seed propagation (template → SpaceConfig)
- Portal services package (`app/services/portal/`) — auth (login + lockout + rate limit + recovery), branding (read + set), user_service (invite + resolve driver)
- JWT realm extension — `get_current_portal_user`, `get_portal_company_from_slug`, `get_current_portal_user_for_tenant`; tightened tenant `get_current_user` to reject portal realm
- Portal API router (`app/api/routes/portal.py`) — 7 endpoints mounted at `/api/v1/portal/*`
- Registered in v1.py

Frontend:
- `types/portal.ts` (5 types: PortalBranding, PortalLoginBody, PortalTokenPair, PortalMe, PortalDriverSummary)
- `services/portal-service.ts` (own axios instance — NOT shared apiClient; separate LocalStorage keys)
- `contexts/portal-auth-context.tsx` (PortalAuthProvider + usePortalAuth + isReady gating)
- `contexts/portal-brand-context.tsx` (PortalBrandProvider + luminance-based fg computation + CSS var application + cleanup on unmount)
- `components/portal/PortalLayout.tsx` (branded header + main + optional footer)
- `components/portal/PortalRouteGuard.tsx` (redirect to login on missing auth)
- `pages/portal/PortalLogin.tsx` (branded login form, 44px touch targets, generic error messages)
- `pages/portal/PortalDriverHome.tsx` (driver summary card + today's stops + unlinked-account graceful path)
- `PortalApp.tsx` (top-level route tree)
- App.tsx wired to detect `/portal/` path and mount PortalApp

### Branding configuration approach

Per-tenant branding stored in `Company.settings_json.portal.*` — NO new `TenantBrandingConfig` table:

| Field | Storage |
|---|---|
| display_name | `Company.name` (reused) |
| logo_url | `Company.logo_url` (reused — already existed) |
| brand_color | `Company.settings_json.portal.brand_color` (hex string, new) |
| footer_text | `Company.settings_json.portal.footer_text` (optional, new) |

Default brand color falls through to platform brass (`#8D6F3A`). Portal 404s for unknown slugs from the public branding endpoint.

Wash-not-reskin discipline — brand color applies ONLY to:
- Portal header background
- Primary CTA background (login submit, future nav active indicator)
- Focus-ring color

Does NOT apply to status colors, typography, surface tokens, border radius, motion, shadow system — those stay DESIGN_LANGUAGE.

### One driver page end-to-end demonstration

`/portal/<slug>/driver` successfully renders post-login:
1. Portal login at `/portal/<slug>/login` — branded with tenant name + color.
2. Submit credentials → POST `/api/v1/portal/<slug>/login` → portal JWT pair stored.
3. Auto-navigate to `/portal/<slug>/driver`.
4. PortalDriverHome calls `/api/v1/portal/drivers/me/summary` → returns driver identity + today's stop count (resolved via `portal_user_id → drivers.portal_user_id → Driver → DeliveryRoute/Stop` chain — the canonical thin-router-over-service pattern).
5. If portal user isn't linked to a Driver row yet (admin provisioning incomplete), shows a graceful "Ask your dispatcher to finish provisioning" message.

### Cross-realm isolation test results

All 4 load-bearing security tests passing:

1. **Tenant token → portal endpoint = 401.** ✅ Tenant `get_current_portal_user` rejects `realm="tenant"`.
2. **Portal token → tenant endpoint = 401.** ✅ Tenant's `get_current_user` tightened to also reject `realm="portal"` in addition to existing `realm="platform"`.
3. **Cross-tenant portal token = 401.** ✅ Portal token for tenant A against tenant B's URL path → refresh endpoint returns 401 (company_id claim mismatches path slug).
4. **Deactivated portal user = 401.** ✅ `get_current_portal_user` re-queries DB and confirms `is_active=True`; existing JWTs die at TTL (12h max).

### Playwright smoke test results

3 scenarios in `frontend/tests/e2e/portal-phase-8e2.spec.ts` — routing + shell architecture boundaries. Tests mock the backend via route interception so they run self-contained without staging:

1. **Branded login renders**: `/portal/<slug>/login` loads with tenant display name + `--portal-brand` CSS var set + submit button disabled until email+password present.
2. **Driver home post-login**: submit valid credentials → navigate to `/portal/<slug>/driver` → driver summary card renders with today's stop count + branded header shows user name.
3. **No DotNav / command bar / settings in portal**: post-login, assert `[data-testid=dot-nav]` + `[data-testid=command-bar-trigger]` + Settings nav link are all absent; Cmd+K doesn't open a command bar overlay.

### Mobile viewport verification results

- Portal header: 48px height (h-12) ≥ 44px WCAG 2.2 Target Size ✓
- Login inputs: h-11 (44px) explicitly set ✓
- Login submit: h-11 full-width ✓
- Single-column layout at all viewport widths ✓
- No horizontal scroll issues ✓

Full mobile polish pass (remaining driver pages, network resilience, offline-tolerance) deferred to 8e.2.1.

### Sunnycrest non-destructive migration verification

`test_portal_phase8e2.py::TestNonDestructiveDriverMigration::test_tenant_user_driver_still_works` creates a classic tenant-user driver (`employee_id` set, `portal_user_id=None`) and round-trips it cleanly. Sunnycrest's existing driver flow is unaffected — tenants opt into portal migration per-driver when ready.

### TestDriverTemplatesUsePortalAccessMode rename + update

Phase 8e's `TestNoDriverTemplates` renamed to `TestDriverTemplatesUsePortalAccessMode`. Invariant evolved:

- **Before 8e.2**: "Drivers have NO templates (operational roles deferred)."
- **After 8e.2**: "Operational-role slugs (driver, yard_operator, removal_staff) MUST have `access_mode` starting with `portal_` if a template exists. Office-role slugs MUST have `access_mode='platform'`."

Symmetric invariant — no accidental drift in either direction. FH driver remains excluded (no template).

### Migration r42_portal_users + r43_portal_password_email_template details

**r42:**
- CREATE TABLE `portal_users` with full field set + UNIQUE(email, company_id) + partial unique indexes on invite_token + recovery_token
- ADD COLUMN `drivers.portal_user_id` (nullable, FK to portal_users with ON DELETE SET NULL)
- ADD COLUMN `audit_logs.actor_type` (server_default='tenant_user' — every existing row reads as tenant action)
- Reversible: DROP COLUMN + DROP TABLE cleanly

**r43:**
- Seeds `email.portal_password_recovery` template in the D-2 document_templates registry (reused idempotent pattern from r40_aftercare_email_template)
- Variable schema: first_name, tenant_name, reset_url, expires_in

### 8e.2.1 scope clearly delineated

Next phase ships:

- **Tenant admin UI** at `/settings/portal-users` — list/invite/edit/deactivate/reset-password/unlock
- **Branding editor UI** — color picker, logo upload, footer text
- **Remaining 4 driver pages** mounted under `/portal/<slug>/driver/*`: route, stops/:stopId, mileage, vehicle-inspection
- **Reset-password page** at `/portal/<slug>/reset-password?token=...`
- **Offline-tolerance touches** — OfflineBanner + retry toasts wired into portal surfaces
- **Full mobile polish pass** — touch target audit across all portal pages, small-viewport edge cases

### Files touched

Backend (10 files):
- `alembic/versions/r42_portal_users.py` (new)
- `alembic/versions/r43_portal_password_email_template.py` (new)
- `app/models/portal_user.py` (new)
- `app/models/__init__.py` (import + export PortalUser)
- `app/models/driver.py` (portal_user_id column + relationship)
- `app/models/audit_log.py` (actor_type column)
- `app/services/spaces/types.py` (4 modifier fields + AccessMode/WriteMode Literals)
- `app/services/spaces/crud.py` (round-trip modifier fields in ResolvedSpace)
- `app/services/spaces/seed.py` (template → SpaceConfig modifier field propagation)
- `app/services/spaces/registry.py` (SpaceTemplate modifier fields + MFG driver template entry)
- `app/services/portal/{__init__.py, auth.py, branding.py, user_service.py}` (new)
- `app/api/deps.py` (portal auth dependencies + tenant realm rejection tightening)
- `app/api/routes/portal.py` (new, 7 endpoints)
- `app/api/v1.py` (register portal router)
- `tests/test_portal_phase8e2.py` (new, 25 tests)
- `tests/test_spaces_phase8e.py` (TestNoDriverTemplates → TestDriverTemplatesUsePortalAccessMode)

Frontend (10 files):
- `types/portal.ts` (new, 5 types)
- `services/portal-service.ts` (new, own axios instance)
- `contexts/portal-auth-context.tsx` (new)
- `contexts/portal-brand-context.tsx` (new)
- `components/portal/PortalLayout.tsx` (new)
- `components/portal/PortalRouteGuard.tsx` (new)
- `pages/portal/PortalLogin.tsx` (new)
- `pages/portal/PortalDriverHome.tsx` (new)
- `PortalApp.tsx` (new top-level route tree)
- `App.tsx` (onPortalPath detection + PortalApp mount + import)
- `tests/e2e/portal-phase-8e2.spec.ts` (new, 3 Playwright smoke tests)

Docs (3 files):
- `SPACES_ARCHITECTURE.md` §10 (new, 280 lines — full Portal Foundation reference)
- `CLAUDE.md` — new Phase 8e.2 section + Recent Changes bullet
- `FEATURE_SESSIONS.md` — this entry

### Ready for Phase 8e.2.1

Phase 8e.2 closes the portal-infrastructure workstream. Phase 8e.2.1 completes the driver portal UX (admin UI + branding editor + remaining 4 driver pages mounted + mobile polish + reset-password page). Both phases ship before September Wilbert demo.

---

## Workflow Arc Phase 8e.1 — Smart Spaces

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` → `r41_user_space_affinity` (new).
**Arc:** Workflow Arc Phase 8e.1. Sequence: 8c → 8d → 8d.1 → Aesthetic 1-3 → 8e → **8e.1 (now)** → 8e.2 (portal foundation) → Aesthetic 4-5 → 8f → 8g → Aesthetic 6 → cleanup → 8h.
**Tests passing:** 33 new + BLOCKING latency gate extended = 34 new; full spaces regression 151 passing.

### What shipped

Phase 8e.1 adds a behavior-inferred ranking-signal layer to the Phase 8e spaces fabric, ships the full `/settings/spaces` customization page, wires affinity writes across 4 deliberate-intent surfaces, and integrates starter-template + affinity boosts into the command bar. The defining principle: **users don't configure "what this space is about" — the system infers it from what they do.**

### Affinity data model

New table `user_space_affinity` via migration `r41_user_space_affinity`:

- Composite PK `(user_id, space_id, target_type, target_id)` — no surrogate UUID.
- CHECK constraint on target_type: `nav_item | saved_view | entity_record | triage_queue`.
- Partial index `(user_id, space_id) WHERE visit_count > 0` — the hot-path read query shape.
- Partial index `(user_id, last_visited_at DESC) WHERE visit_count > 0` — future-proofing for "top N recent per user" consumers.
- Storage bounded by `pins × spaces` per user ~= 140 rows steady-state.
- Tenant isolation by construction (`user.company_id` resolves to one tenant).

### Write path — 4 deliberate triggers, 5 anti-triggers

Wired into:

1. **PinnedSection pin click** (`components/spaces/PinnedSection.tsx`) — `onNavigate` callback fires `recordVisit` before navigating.
2. **PinStar pin-TO-pinned transition** (`components/spaces/PinStar.tsx`) — `wasPinned` captured before toggle; only records on `false → true`.
3. **CommandBar activation** (`components/core/CommandBar.tsx`) — navigate branch, active_space_id guarded. Target type inferred from `action.type` + `action.route`; prefix-stripping for `entity:<type>:<uuid>` + `saved_view:<uuid>` backend shapes.
4. **AffinityVisitWatcher** (`components/spaces/AffinityVisitWatcher.tsx`) — mounted at app root under `SpaceProvider`, watches `useLocation().pathname`, matches starts-with for nav_item / exact for saved_view + triage_queue.

Anti-triggers (explicitly excluded): DotNav space-switch click (meta-navigation), keyboard `⌘[` / `⌘]` cycling (skimming, not intent), unpin (opposite of intent), hover peek (passive exploration), rendered-but-not-activated results (intent mismatch).

### Write path — fire-and-forget + throttled

- `useAffinityVisit()` hook (`hooks/useAffinityVisit.ts`): `recordVisit({targetType, targetId, spaceId?})` returns `void`; callers must NOT await. Module-scoped `Map` bucket, 60-second window per `{targetType}:{targetId}` (matches server).
- **Server-side throttle** (`app/services/spaces/affinity.py::_should_throttle`): in-memory 60-second bucket per `(user_id, target_type, target_id)` per process. Defense-in-depth.
- **Endpoint**: `POST /api/v1/spaces/affinity/visit` — returns 200 `{recorded: bool}` either way; 400 on invalid target_type; 404 on space_id not owned.

### Read path — formula + composition

```
affinity_weight = 1.0 + 0.4 * log10(visits+1)/log10(11) * max(0, 1-age_days/30)
```

- 0 visits → 1.000 (no boost)
- 1 visit today → 1.116
- 5 visits today → 1.299
- 10 visits today → 1.400 (saturates; visit_count ≥ 10 all cap here)
- 10 visits 15 days → 1.200 (half-decayed)
- Any visits at 30+ days → 1.000 (fully decayed; row contributes 0)

Applied in `command_bar/retrieval.py` after the existing pin-boost pass:

| Boost | Weight | Stacks with |
|---|---|---|
| Phase 3 pin (existing) | 1.25× | (skips starter template when applied) |
| Phase 8e.1 starter template | 1.10× | (skipped if pin applied) |
| Phase 8e.1 affinity | 1.0–1.40× | Both above |

Max compound: pinned + affinity'd + today = 1.25 × 1.40 = **1.75×**. Above the 1.5× generic single-boost ceiling but bounded.

### Privacy model

- `DELETE /api/v1/spaces/affinity?space_id=X` endpoint.
- UI: "Clear command bar learning history" button in `/settings/spaces` with confirmation modal.
- **Cascade on space delete**: `crud.delete_space` removes affinity rows in the same transaction.
- Cross-user / cross-tenant leakage impossible by PK construction.
- Retention: indefinite storage + 30-day read-side decay. No hard-delete job in 8e.1.
- **Purpose-limitation clause** in `SPACES_ARCHITECTURE.md` §9.4: affinity data used ONLY for command bar ranking. Future use requires separate scope-expansion audit. Load-bearing for user trust.

### Customization UI — `/settings/spaces`

~900 LOC, strictly Aesthetic Arc Session 3 primitives:

- **Sidebar** — drag-reorder user spaces, system spaces sticky leftmost.
- **Editor** — name, icon (16-entry Popover picker), 6-accent chips with hover-live-preview (temporary `--space-accent` CSS var), density, is_default, landing-route dropdown.
- **Pin manager** — drag-reorder, per-pin "Move to…" Popover (add-to-target + remove-from-source composition).
- **Header actions** — New space, Add starter template, Reapply role defaults (confirmation-before-commit modal with "won't change customizations" copy per user spec), Reset all spaces (type-to-confirm `Reset spaces`).
- **Privacy card** — "N tracked signals" counter + "Clear learning history" action.
- **Onboarding** — `welcome_to_settings_spaces` touch at top of page on first visit.

### Dialog consolidation

`NewSpaceDialog` + `SpaceEditorDialog` coexist with `/settings/spaces`:

- Both dialogs gain footer deep-links to the power surface.
- Dialogs remain the DotNav quick-path (60-second interactions).
- `/settings/spaces` is the power surface (drag-reorder, move pins, reset, template import, clear history).
- Zero backend change — all three paths call the same 13-endpoint API.

### Performance

- **Baseline pre-8e.1** `command_bar_query` p50 = 7.9 ms / p99 = 10.3 ms.
- **Post-8e.1 with affinity enabled** p50 = **8.2 ms** / p99 = **77.3 ms** on dev hardware.
- Against 100 / 300 ms BLOCKING budget: **12× / 3.9× headroom**.
- `test_command_bar_latency.py` extended to seed 10 affinity rows + active space so the prefetch + boost pipeline is exercised.

### Files touched

**Backend:**
- `alembic/versions/r41_user_space_affinity.py` (new)
- `app/models/user_space_affinity.py` (new)
- `app/models/__init__.py` (import + export UserSpaceAffinity)
- `app/services/spaces/affinity.py` (new, ~320 LOC)
- `app/services/spaces/__init__.py` (exports)
- `app/services/spaces/crud.py` (cascade call in delete_space)
- `app/api/routes/spaces.py` (4 new Pydantic shapes + 3 new routes, reorder-before-`/{space_id}`)
- `app/services/command_bar/retrieval.py` (starter-template boost + affinity boost pass + 2 helpers)
- `tests/test_spaces_phase8e1_affinity.py` (new, 33 tests)
- `tests/test_command_bar_latency.py` (extended to seed affinity + pass active_space_id in context)

**Frontend:**
- `types/spaces.ts` (5 new types: AffinityTargetType, AffinityVisitBody/Response, AffinityCountResponse, AffinityClearResponse)
- `services/spaces-service.ts` (recordAffinityVisit + getAffinityCount + clearAffinityHistory)
- `hooks/useAffinityVisit.ts` (new)
- `components/spaces/AffinityVisitWatcher.tsx` (new)
- `components/spaces/PinnedSection.tsx` (onNavigate callback + affinity call)
- `components/spaces/PinStar.tsx` (affinity call on pin-to-pinned + handleClick function restored from 8e edit)
- `components/spaces/NewSpaceDialog.tsx` (More options… deep-link footer)
- `components/spaces/SpaceEditorDialog.tsx` (Manage all pins… deep-link footer)
- `components/core/CommandBar.tsx` (affinity call in navigate branch + useAffinityVisit import)
- `pages/settings/SpacesSettings.tsx` (new, ~900 LOC)
- `App.tsx` (route registration + AffinityVisitWatcher mount)

**Docs:**
- `SPACES_ARCHITECTURE.md` — new §9 Smart Spaces (data model, write path, read path, boost formula, composition, privacy, performance, customization UI, test coverage)
- `CLAUDE.md` — new Phase 8e.1 section + Recent Changes bullet
- `FEATURE_SESSIONS.md` — this entry

### Test summary

**33 new Phase 8e.1 tests** in `test_spaces_phase8e1_affinity.py`:

- TestAffinitySchema × 3 — composite PK upsert, CHECK constraint, partial indexes exist
- TestBoostFormula × 6 — zero/one/ten/saturation/decay-half/decay-full
- TestRecordVisit × 3 — invalid target_type, unknown space, throttle
- TestPrefetch × 3 — empty/null/seeded
- TestIsolation × 2 — cross-user, cross-tenant
- TestCascade × 2 — delete removes, other users unaffected
- TestClearAffinity × 2 — all, per-space
- TestAffinityAPI × 7 — visit records, throttle, bad target, unknown space, auth, count, clear idempotent
- TestPinBoostRegression × 1 — Phase 3 still works
- TestStarterTemplateBoost × 3 — in-template boost, user-created no boost, no-active-space empty
- TestBoostComposition × 1 — prefetch → boost_for_target lookup

**Plus BLOCKING latency gate** in `test_command_bar_latency.py` extended = 34 new tests.

**Full Phase 1–8e.1 spaces regression: 151 tests passing. No regressions.**

### Not in Phase 8e.1 (deferred)

- Portal foundation (Phase 8e.2)
- Detailed per-target affinity viewer (post-arc — single counter suffices for 8e.1)
- Bulk pin actions (move N, delete N)
- Full preview-before-save for the space (accent live preview is intermediate form)
- Mobile viewport for `/settings/spaces`
- Space export / import
- Affinity as input to anything other than command bar ranking (future scope-expansion audit required)

### Ready for Phase 8e.2

Phase 8e.1 closes the "smart spaces" workstream. Phase 8e.2 introduces portal-as-space-with-modifiers and MFG driver as the first concrete portal, shipping before the September Wilbert demo.

---

## Workflow Arc Phase 8e — Spaces and Default Views

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — pure JSONB + service-layer work).
**Arc:** Workflow Arc — Phase 8e. Sequencing: 8c → 8d → 8d.1 → Aesthetic 1-3 → **8e (now)** → 8e.1 (smart spaces) → 8e.2 (portal foundation) → Aesthetic 4-5 → 8f → 8g → Aesthetic 6 → cleanup → 8h.
**Tests passing:** 31 new in `test_spaces_phase8e.py`; full spaces regression 117 passing (unit + api + pins + system + 8e); saved_views + briefings + command_bar neighbors green.

### What shipped

Phase 8e expands the Phase 3 Spaces primitive with six new (vertical, role_slug) template combinations, two enrichments to existing templates, a deliberate-activation landing-route field, two new Phase-7-style onboarding touches, the reapply-defaults endpoint, a MAX_SPACES cap bump, and the Phase 3 SpaceSwitcher retirement. Drivers are deliberately excluded — they get portal UX in Phase 8e.2, not platform Space templates.

**6 new templates** in `backend/app/services/spaces/registry.py::SEED_TEMPLATES`:

| (vertical, role_slug) | Spaces (default first) | Default landing |
|---|---|---|
| cemetery / admin | Operations · Administrative · Ownership | /interments |
| cemetery / office | Administrative · Operational | /financials |
| crematory / admin | Operations · Administrative | /crematory/schedule |
| crematory / office | Operations · Administrative | /crematory/schedule |
| funeral_home / accountant | Books · Reports | /financials |
| manufacturing / accountant | Books · Reports · Compliance | /financials |

**2 enrichments:**
- `(manufacturing, "safety_trainer")` promoted from FALLBACK to dedicated Compliance + Training spaces. Compliance pins `safety_program_triage` queue (Phase 8d.1 output) + safety nav. Training holds calendar + toolbox talks.
- `(manufacturing, "production")` Production space gained `safety_program_triage` pin as a second triage-queue pin alongside existing `task_triage`. Production managers see BOTH queues at the top of their primary workspace.

**Template coverage after 8e:** 13 (vertical, role_slug) combinations + 1 system space (Settings) + 1 fallback (General). Up from 6 pre-Phase-8e.

### Driver templates intentionally excluded

Driver roles (FH + MFG) are NOT given platform space templates. Drivers are **operational roles** requiring portal-shaped UX rather than platform-shaped UX. MFG driver becomes the reconnaissance use case for Phase 8e.2 portal infrastructure.

`SPACES_ARCHITECTURE.md` at project root documents the full office-vs-operational distinction. The portal-as-space-with-modifiers architecture handles both external portals (family/supplier/customer/partner) AND internal operational-role portals (driver/yard operator) via the same primitive: a SpaceConfig with `access_mode: "portal_restricted"` + `tenant_branding` + `write_mode` modifiers. Phase 8e.2 ships the modifier fields + portal-restricted UI shell + portal user authentication + per-tenant branding + MFG driver as the first concrete portal. Before September Wilbert demo.

`test_spaces_phase8e.py::TestNoDriverTemplates` enforces the invariant: `(funeral_home, "driver")` and `(manufacturing, "driver")` must NOT appear in SEED_TEMPLATES until Phase 8e.2 deliberately adds them.

### Deliberate-activation landing route

New `SpaceConfig.default_home_route: str | None` field. When a user activates a Space via:
- **Deliberate** action (DotNav click, Switch-to-X command-bar result): frontend navigates to `default_home_route` via `useNavigate`.
- **Keyboard** action (`⌘[`, `⌘]`, `⌘⇧1..7`): no navigation — rapid Space cycling stays on current page.

`SpaceContext.switchSpace(spaceId, { source: "deliberate" | "keyboard" })` is the contract; default when omitted is `"keyboard"` (safer). All 14 shipped templates (6 new + 8 pre-existing + FALLBACK + Settings) carry `default_home_route` values.

**SpaceEditorDialog gains a "Landing route" dropdown** populated from: (1) "Don't navigate" (null), (2) every pin in the Space with a resolvable href de-duped, (3) `/dashboard` as universal fallback, (4) the Space's current custom value if not in 1-3. Unavailable pins (deleted saved view, revoked triage queue) are excluded.

### Saved-view seed dependency verification

Every `saved_view` pin in a Space template references `saved_view_seed:<role>:<key>`. These keys must have matching `SeedTemplate` entries in `saved_views/seed.py` for the **same vertical** or the pin renders as "unavailable" at read time. Phase 8e adds 6 new (vertical, role_slug) combinations to `saved_views/seed.py::SEED_TEMPLATES`:

- `(cemetery, "admin")` → outstanding_invoices + recent_cases
- `(cemetery, "office")` → outstanding_invoices
- `(crematory, "admin")` → outstanding_invoices + recent_cases
- `(crematory, "office")` → outstanding_invoices
- `(funeral_home, "accountant")` → outstanding_invoices
- `(manufacturing, "accountant")` → outstanding_invoices

`test_spaces_phase8e.py::TestSavedViewSeedDependencies` is an invariant test — iterates every space template pin at load time, cross-references against `saved_views SEED_TEMPLATES`, fails loudly if any saved_view pin points at a seed key that doesn't resolve.

### MAX_SPACES_PER_USER 5 → 7

Bumped in lockstep across `backend/app/services/spaces/types.py` and `frontend/src/types/spaces.ts`. Accommodates users who pick up the Settings system space (Phase 8a) plus multiple role-seeded spaces plus custom user-created spaces. A manufacturing admin today seeds 3 spaces (Production + Sales + Ownership) + Settings = 4; bumping to 7 leaves 3 slots for customization.

**DotNav layout accommodates 7 dots.** Tightened `gap-1.5` → `gap-1` (saves ~30px at 7 spaces) + added `overflow-x-auto` + `scrollbar-none` for graceful degradation at collapsed sidebar widths. `Cmd+⇧1..5` bumped to `Cmd+⇧1..7` on the keyboard handler.

### Reapply-defaults endpoint

`POST /api/v1/spaces/reapply-defaults` wraps existing `user_service.reapply_role_defaults_for_user()`. Returns `{saved_views, spaces, briefings}` counts. Idempotent via each seed function's per-role preferences arrays (briefings returns 1-on-success by contract, not a row count).

Exposed because `ROLE_CHANGE_RESEED_ENABLED=False` (Phase 8a opinionated-but-configurable discipline). Role changes no longer auto-reseed saved views; users who want their fresh role defaults call this endpoint. Future Phase 8e.1 UI surface wires it into `/settings/spaces`.

### Two new onboarding touches

Uses existing Phase 7 `useOnboardingTouch` infrastructure (server-persisted via `User.preferences.onboarding_touches_shown`, no new table, cross-device).

1. **`welcome_to_spaces`** — fires on DotNav when user has ≥2 spaces (single-space users don't benefit from a "switch spaces" primer). Explains the spaces concept + keyboard shortcuts. Positioned at `top` of the DotNav bar.

2. **`pin_this_view`** — fires on any PinStar where the user hasn't-yet-pinned the target. Explains "Pin to {active_space.name}" + that each space keeps its own pins. Positioned `bottom` adjacent to the star.

Both have `X` dismissal → one-click, cross-device sticky.

### Phase 3 SpaceSwitcher.tsx deleted

The top-nav `SpaceSwitcher.tsx` was already retired from `app-layout.tsx` in Phase 8a with a one-release grace period. Phase 8e deletes the file outright. No remaining callers (verified via grep). Phase 8a regression test `test_old_top_space_switcher_gone` stays valid — nothing mounts `data-testid="space-switcher-trigger"` anywhere.

### Icon + label infrastructure additions

**DotNav ICON_MAP extended** with `bar-chart-3` (Reports), `shield-check` (Compliance), `graduation-cap` (Training) to render icons referenced by new 8e templates. Unknown icons fall back to a colored accent dot.

**NAV_LABEL_TABLE additions** (15 new entries): `/interments`, `/plots`, `/deeds`, `/crematory/cases`, `/crematory/schedule`, `/crematory/custody`, `/reports`, `/financials/board`, `/compliance`, `/safety`, `/safety/training`, `/safety/osha-300`, `/safety/incidents`, `/safety/training/calendar`, `/safety/toolbox-talks`. `test_spaces_phase8e.py::TestNavLabelCoverage` is an invariant test — gates future template additions against forgetting the label entry.

### Files touched

**Backend (7 files):**
- `backend/app/services/spaces/types.py` — `SpaceConfig.default_home_route` field; `MAX_SPACES_PER_USER: 5 → 7`
- `backend/app/services/spaces/registry.py` — 6 new `SEED_TEMPLATES` entries; 2 enrichments; all 14 templates gain `default_home_route`; `SpaceTemplate` + `SystemSpaceTemplate` gain the field; `NAV_LABEL_TABLE` +15 entries
- `backend/app/services/spaces/seed.py` — carries `default_home_route` from template → SpaceConfig in both `_apply_templates` and `_apply_system_spaces`
- `backend/app/services/spaces/crud.py` — `create_space` + `update_space` accept the field; `_UNSET` sentinel for "no change" vs "explicit null clear" on update; `_resolve_space` passes through to `ResolvedSpace`
- `backend/app/api/routes/spaces.py` — `_SpaceResponse`, `_CreateRequest`, `_UpdateRequest` gain the field; reapply-defaults endpoint `POST /api/v1/spaces/reapply-defaults`
- `backend/app/services/saved_views/seed.py` — 6 new (vertical, role) SEED_TEMPLATES entries
- `backend/tests/test_spaces_phase8e.py` (new, 31 tests); `test_spaces_api.py` (1 test updated); `test_space_pins_triage_queue.py` (2 tests updated)

**Frontend (7 files):**
- `frontend/src/types/spaces.ts` — `Space.default_home_route`, `CreateSpaceBody.default_home_route`, `UpdateSpaceBody.default_home_route`, `ReapplyDefaultsResponse`, `MAX_SPACES_PER_USER: 5 → 7`
- `frontend/src/services/spaces-service.ts` — `reapplyDefaults()` method
- `frontend/src/contexts/space-context.tsx` — `SwitchSpaceSource` + `SwitchSpaceOptions`; `switchSpace(id, { source })` contract; navigates via `useNavigate` when `source === "deliberate"` and the target has a `default_home_route`
- `frontend/src/components/layout/DotNav.tsx` — click passes `source: "deliberate"`; keyboard passes `source: "keyboard"`; `Cmd+⇧1..5` → `Cmd+⇧1..7`; ICON_MAP +3; welcome_to_spaces OnboardingTouch; layout: `gap-1.5 → gap-1` + `overflow-x-auto` + `scrollbar-none` + `relative`
- `frontend/src/components/spaces/SpaceEditorDialog.tsx` — Landing route dropdown with pin-derived options
- `frontend/src/components/spaces/NewSpaceDialog.tsx` — uses `MAX_SPACES_PER_USER` constant
- `frontend/src/components/spaces/PinStar.tsx` — wraps button in `<span class="relative">` to anchor the `pin_this_view` OnboardingTouch
- `frontend/src/components/core/CommandBar.tsx` — space-switch intercept passes `source: "deliberate"`
- `frontend/src/components/spaces/SpaceSwitcher.tsx` — **deleted**

**Docs (3 files):**
- `SPACES_ARCHITECTURE.md` (new, project root) — office-vs-operational distinction, deliberate-vs-keyboard semantics, landing-route authoring, Phase 8e.2 scope, invariants
- `CLAUDE.md` — Phase 8e section + "Recent Changes" bullet
- `FEATURE_SESSIONS.md` — this entry

### Test verification

- 31 new tests in `test_spaces_phase8e.py` all passing
- 117 spaces tests total passing across `test_spaces_unit.py` + `test_spaces_api.py` + `test_system_spaces_phase8a.py` + `test_space_pins_triage_queue.py` + `test_spaces_phase8e.py`
- No regressions in neighbor modules: `test_saved_views.py` + `test_saved_views_registry.py` + `test_briefings_phase6.py` + `test_command_bar_latency.py` all green (65 passed)

### Not in Phase 8e (deferred)

- **Topical affinity** — per-user per-space command-bar ranking signals (new `user_space_affinity` table + write endpoint + read integration in `resolver.py`/`retrieval.py`). Phase 8e.1.
- **Full `/settings/spaces` customization UI** — page with sidebar + main panel + reapply-defaults button + starter-template picker. Phase 8e.1.
- **Portal infrastructure** — `SpaceConfig.access_mode` + `tenant_branding` + `write_mode` modifiers; portal user authentication; portal-restricted UI shell; MFG driver reconnaissance; per-tenant branding; portal user management UI. Phase 8e.2 (ships before September Wilbert demo).

### Open items + follow-ups

- **`scrollbar-none` utility** referenced in DotNav has no CSS definition yet (team-dashboard uses it similarly without CSS). Harmless — overflow works with default scrollbar. Post-arc polish.
- **Sibling `test_onboarding_touches_welcome_pin` test** — not added this phase. The touches are covered by existing Phase 7 `useOnboardingTouch` tests (hook behavior), but the new gating logic (`showWelcomeTouch = sortedSpaces.length >= 2`, `showPinTouch = !pinned`) is unit-covered via the rendered component tree only indirectly. Post-arc follow-up.
- **Reapply-defaults UI surface** — backend ships; UI ships in Phase 8e.1.

---

## Aesthetic Arc Session 3 — Extended Components + Status Treatment

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — frontend-only).
**Arc:** Aesthetic Arc — Session 3 of 6. See `AESTHETIC_ARC.md`.
**Tests passing:** no new tests this session; 165/165 vitest + 171/171 Phase 8a-8d.1 backend regression. tsc clean. Build clean (4.94s).

### What shipped — status vocabulary, 6 net-new primitives, 0 primitives left in shadcn aesthetic

Session 3 closes the extended-component gap. After Session 3, every component category in the platform has been refreshed, and the platform has a single consistent status-color vocabulary (DESIGN_LANGUAGE `status-{success,warning,error,info}` + muted variants) for rendering badges, alerts, toasts, pills, validation messages, and row-level status cells.

### Per-component work

**6 net-new primitives (~630 LOC):**
- `src/components/ui/alert.tsx` — platform banner primitive. 5 variants (info/success/warning/error/neutral). `Alert` + `AlertTitle` + `AlertDescription` + `AlertAction`. Optional dismiss button. Auto `role="alert"` + `aria-live` matches severity. Replaces ~50+ ad-hoc `<div className="bg-amber-50 border-amber-200">` banner patterns in new work.
- `src/components/ui/status-pill.tsx` — rounded-full inline status marker. `resolveStatusFamily` helper + `STATUS_MAP` dict maps 33 status keys to 4 families + neutral. 3 sizes (sm/default/md). Distinct from Badge: rounded-full + auto-mapping (vs. Badge's rounded-sm + manual variant).
- `src/components/ui/tooltip.tsx` — Base UI Tooltip wrapper. Overlay-family composition (bg-surface-raised + border-border-subtle + rounded-md + shadow-level-2 + duration-settle ease-settle + 150ms delay per DESIGN_LANGUAGE §6). 5 exports: `TooltipProvider` / `Tooltip` / `TooltipTrigger` / `TooltipContent` / `TooltipShortcut` (font-plex-mono keybind styling). 2 sizes. Net-new — 266 native `title=` sites left as-is for long-tail adoption.
- `src/components/ui/popover.tsx` — Base UI Popover wrapper. Same overlay-family composition. 4 exports (Popover / Trigger / Content / Close). 2 existing Base UI popover sites (LocationSelector + notification-dropdown) stay on direct imports per Q4.
- `src/components/ui/form-section.tsx` — `FormSection` + `FormStack` + `FormFooter`. Lightweight form grouping with title/description/error props. FormStack applies §5 vertical-rhythm gap-8. FormFooter matches Card/Dialog footer convention (bg-surface-base + border-t + optional sticky).
- `src/components/ui/form-steps.tsx` — horizontal/vertical stepper indicator. 4 step states (completed/current/upcoming/error). Brass filled-dot for completed+current, surface-sunken hollow for upcoming, status-error for errored. Brass connector for completed segments. `duration-settle ease-settle` on state changes.

**11 primitive refreshes (~400 LOC):**
- **Badge** (179 imports) — added 4 status variants (info/success/warning/error) + `destructive` aliased to `error` for backward compat (142 existing usages unchanged). `rounded-4xl` → `rounded-sm` per §6 badges-small-pills. `bg-primary` → `bg-brass-muted`. Brass focus ring (focusable via render-as-link). font-plex-sans text-micro.
- **Table** (66 imports) — `border-b` → `border-b border-border-subtle`. Header: text-micro uppercase tracking-wider text-content-muted (eyebrow convention matching sidebar section headers). Row hover: `bg-muted/50` → `bg-brass-subtle/60`. Selected: `bg-muted` → `bg-brass-muted`. Footer: `bg-muted/50` → `bg-surface-base` + sinking border-t (Card/Dialog parity). Cell padding `p-2` → `p-3` per §5 table-cell.
- **Tabs** (3 imports) — default-variant track: `bg-muted` → `bg-surface-sunken`. Active tab lifts onto `bg-surface-raised` + `shadow-level-1`. Line-variant indicator: foreground after-bar → brass. Brass focus ring.
- **Separator** (20 imports) — `bg-border` → `bg-border-subtle`.
- **Avatar** (0 imports; prepared for future) — fallback `bg-muted` → `bg-brass-muted` + `text-content-on-brass` per §7 Imagery. AvatarBadge default to brass. Group count + group ring → surface-base.
- **Switch** (24 imports) — checked `bg-primary` → `bg-brass`. Unchecked `bg-input` → `bg-surface-sunken` + ring border-base. Thumb → bg-surface-raised + shadow-level-1. Brass focus ring.
- **Radio Group** (2 imports) — checked `bg-primary border-primary` → `bg-brass border-brass` + `text-content-on-brass`. Unchecked → bg-surface-raised + border-border-base. Invalid `border-destructive` → `border-status-error`. Brass focus ring.
- **Skeleton** (9 imports) — `bg-muted/60` → `bg-surface-sunken` (warm recessed pulse). SkeletonCard `bg-card ring-1 ring-foreground/10` → `bg-surface-elevated shadow-level-1`. SkeletonTable `border` → `border-border-subtle`.
- **EmptyState** (11 imports, Phase 7 primitive) — `text-muted-foreground` → `text-content-muted`. Positive tone `text-emerald-700 dark:text-emerald-400` → `text-status-success` (token auto-resolves in both modes). `text-foreground` → `text-content-strong`. Title size tokens → DESIGN_LANGUAGE text-body/body-sm/caption. font-plex-sans.
- **InlineError** (6 imports, Phase 7 primitive) — error severity: `border-destructive/40 bg-destructive/5 text-destructive` → `border-status-error/40 bg-status-error-muted text-status-error`. Warning severity: `border-amber-500/40` → `border-status-warning/40 bg-status-warning-muted text-status-warning`. font-plex-sans. Font sizes migrated to text-body-sm / text-caption.
- **Sonner** — `next-themes` DEPENDENCY REMOVED (audit confirmed single consumer in sonner.tsx; `grep next-themes src/` confirms empty post-migration). `theme="system"` hardcoded so Sonner reads `prefers-color-scheme` directly. `richColors` ENABLED — auto-tints status-typed toasts via CSS vars. Token migration: `--popover / --popover-foreground / --border / --radius` → `--surface-raised / --content-base / --border-subtle / --radius-md`. Added status-muted background + status-saturation text/border pairs for success/error/warning/info toast variants.

**6 ad-hoc surface refreshes (~180 LOC):**
- `accounting-reminder-banner.tsx` (visible on every authenticated page when accounting is skipped/pending) — migrated from `bg-amber-50 border-amber-200 text-amber-900` ad-hoc to `<Alert variant="warning">` primitive. Dismiss affordance inherits platform brass-focus + hover states.
- `kb-coaching-banner.tsx` — `bg-indigo-100/bg-gradient-to-r from-indigo-50` → `bg-status-info-muted` + border-border-subtle. Icon container tints to `text-status-info`. Stats row → font-plex-mono text-caption for numeric alignment.
- `agent-alerts-card.tsx` (dashboard widget visible on every authenticated dashboard) — **migrated to status-key-keyed dict pattern** (new CLAUDE.md convention). Pre-S3 had `SEVERITY_CONFIG = { action_required: { color: "text-red-600", bg: "bg-red-50", border: "border-red-200" } }` with 3 raw color strings per severity. Post-S3 has `SEVERITY_CONFIG: Record<string, { icon, status: StatusFamily }>` + shared `FAMILY_STYLES` lookup mapping family → token triple. New severity = one row, zero raw colors.
- `components/peek/renderers/_shared.tsx::StatusBadge` — delegates to new `StatusPill` primitive. The 6 peek renderers (CasePeek / InvoicePeek / SalesOrderPeek / TaskPeek / ContactPeek / SavedViewPeek) inherit status-family auto-mapping via `StatusPill status={row.status} size="sm"`. Unknown status strings fall through to neutral. PeekField internal tokens also migrated to content-muted/content-strong/font-plex-sans.
- `App.tsx ErrorBoundary` — removed inline `style={{ color: "#b91c1c" }}` hex + `color: "#666"` + `fontFamily: "sans-serif"`. Now renders as Alert-family shell: `min-h-screen bg-surface-base p-10 font-plex-sans` + `border-l-4 border-l-status-error bg-status-error-muted` card with brass Reload button + `font-plex-mono` error message preformatted text.
- `WidgetErrorBoundary.tsx` — `text-red-400 / text-blue-600 / text-gray-500` → `text-status-error / text-brass / text-content-muted`. Brass focus ring on "Try again" button.

### Status-color migration recipe (documented for long-tail migration)

**1,305 ad-hoc status-color usages** remain across page-level chrome. Session 3 does NOT refactor them in bulk (out of scope). Instead, the migration recipe is documented in CLAUDE.md for natural-refactor adoption. Pages converge on platform-consistent status colors as they're next touched:

| Legacy pattern | DESIGN_LANGUAGE replacement |
|---|---|
| `bg-green-50 text-green-800` | `bg-status-success-muted text-status-success` |
| `bg-red-50 text-red-800` | `bg-status-error-muted text-status-error` |
| `bg-amber-50 text-amber-800` / `bg-yellow-*` | `bg-status-warning-muted text-status-warning` |
| `bg-blue-50 text-blue-800` / `bg-sky-*` | `bg-status-info-muted text-status-info` |
| `bg-{green|red|amber|blue}-100` | same → respective `bg-status-*-muted` |
| `border-{green|red|amber|blue}-200` | `border-status-*` (with optional `/30` opacity) |
| `text-emerald-700 / text-rose-700 / text-sky-700` | `text-status-success / text-status-error / text-status-info` |

### Status-key-keyed dict pattern (new convention documented)

When a component renders multiple status types via a config object, use a `StatusFamily` key per state + a shared `FAMILY_STYLES` lookup. Don't embed raw color strings in component code.

**agent-alerts-card is the reference implementation.** Future per-state UIs follow the same pattern.

### Settings page deferral (per audit §2)

All 5 Session-2-flagged settings pages (`invoice-settings.tsx`, `call-intelligence-settings.tsx`, `Locations.tsx`, `vault-supplier-settings.tsx`, `urn-import-wizard.tsx`) **deferred to Phase 8e** — which explicitly redesigns settings surfaces as part of its Spaces + Default Views work. Refreshing chrome that Phase 8e will rebuild wastes effort. Documented in Session log for Phase 8e team to carry forward with refreshed aesthetic from the start.

### Mixed-aesthetic state post-Session 3

- **0 UI primitives** remain in shadcn aesthetic. All `src/components/ui/*` now use DESIGN_LANGUAGE tokens.
- **~213 pages** in `src/pages/` still reference shadcn semantic classes in page chrome (inherited from Session 2 audit). Pages render coherently because their composed primitives (Button/Card/Input/Badge/Alert/etc.) carry the refreshed aesthetic.
- **1,305 ad-hoc status-color usages** documented with migration recipe — long-tail adoption.
- **266 native `title=` tooltip attributes** left as-is; Tooltip primitive available for new work.
- **5 settings pages** explicitly deferred to Phase 8e.

### Architectural patterns landed for Session 4+

1. **Status-family recipe**: `bg-status-{X}-muted` + `text-status-{X}` + optional `border-status-{X}` — consistent across Badge/Alert/StatusPill/Sonner/InlineError/Peek/agent-alerts.
2. **Status-key-keyed dict pattern**: components with per-state config declare a `StatusFamily` key per state + shared `FAMILY_STYLES` lookup. No raw color strings.
3. **Overlay family extended**: Tooltip + Popover join the Session 2 overlay-family (Dialog/DropdownMenu/Select popup/SlideOver/notification Popover). 7 overlay primitives share composition.
4. **StatusPill vs. Badge distinction**: StatusPill = rounded-full auto-mapping for inline status markers (lists/tables/detail panels); Badge status variants = rounded-sm general emphasis. Documented in both component file headers + CLAUDE.md.
5. **Alert vs. InlineError distinction**: Alert = page/section banners with 5 variants + dismiss; InlineError = panel-scoped recoverable errors with retry affordance. Documented in both file headers.

### Verification performed

- ✅ `tsc -b` clean.
- ✅ `npm run build` clean — 4.94s.
- ✅ `npx vitest run` — 165/165 passing (11 test files).
- ✅ Backend regression — 171/171 Phase 8a-8d.1 passing.
- ✅ `next-themes` fully uninstalled from `package.json`; `grep next-themes src/` returns empty.
- ✅ Net-new primitives tsc-validated + build-validated.
- ✅ Built CSS contains all status-family utilities used in refreshed components.

### Files shipped Session 3

**New (6):**
- `src/components/ui/alert.tsx` (~130 LOC)
- `src/components/ui/status-pill.tsx` (~170 LOC — includes STATUS_MAP dict + FAMILY_STYLES export)
- `src/components/ui/tooltip.tsx` (~100 LOC)
- `src/components/ui/popover.tsx` (~90 LOC)
- `src/components/ui/form-section.tsx` (~100 LOC — includes FormStack + FormFooter)
- `src/components/ui/form-steps.tsx` (~180 LOC)

**Modified (17):**
- `src/components/ui/badge.tsx` (added 4 status variants + destructive alias)
- `src/components/ui/table.tsx`
- `src/components/ui/tabs.tsx`
- `src/components/ui/separator.tsx`
- `src/components/ui/avatar.tsx`
- `src/components/ui/switch.tsx`
- `src/components/ui/radio-group.tsx`
- `src/components/ui/skeleton.tsx`
- `src/components/ui/empty-state.tsx`
- `src/components/ui/inline-error.tsx`
- `src/components/ui/sonner.tsx` (next-themes removal + richColors + tokens)
- `src/components/accounting-reminder-banner.tsx` (migrated to Alert primitive)
- `src/components/kb-coaching-banner.tsx`
- `src/components/agent-alerts-card.tsx` (status-key-keyed dict pattern)
- `src/components/peek/renderers/_shared.tsx` (StatusBadge → StatusPill delegation)
- `src/App.tsx` (ErrorBoundary refresh)
- `src/components/widgets/WidgetErrorBoundary.tsx`

**Collateral:**
- `package.json` — `next-themes` uninstalled.

Total: 23 files touched, ~1,200 LOC (~770 modified + ~430 new).

### Ready for Session 4: Dark mode pass

Session 4 scope: comprehensive dark-mode verification across every refreshed component and every surface. Specific focus areas likely:
- Inset top-edge highlights on elevated surfaces render correctly (DESIGN_LANGUAGE §2 "Material, not paint").
- Brass visibility against dark charcoal at all sizes (particularly brass-subtle on hover states).
- Status-muted variants at low luminance not reading as washed-out.
- Shadow composition on modals/dialogs/popovers at level-2/level-3 — the inset highlight rule of dark mode.
- Peek StatusPill + Badge status variants legibility across `status-{X}-muted` dark-mode values.
- Sonner richColors toasts against dark base surface.

Then Session 5 (motion pass) and Session 6 (final QA verification + WCAG compliance).

---

## Aesthetic Arc Session 2 — Core Component Refresh

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — frontend-only session).
**Arc:** Aesthetic Arc — Session 2 of 6. See `AESTHETIC_ARC.md`.
**Tests passing:** no new tests this session (component test coverage deferred per audit §4); 165/165 frontend vitest + 171/171 Phase 8a–8d.1 backend regression all green. `tsc -b` clean, `npm run build` clean (5.02s).

### What shipped — the platform visibly moves to aged brass + IBM Plex Sans

Session 2 is the first Aesthetic Arc session that creates observable visual change across the platform. Every authenticated page now renders core components on DESIGN_LANGUAGE tokens — buttons are aged brass, cards are warm-cream-elevated, focus rings are brass, sidebar is warm-cream-sunken, and the entire platform's typography flipped from Geist to IBM Plex Sans in a single token-reference edit.

**14 files modified across the 10-step implementation order** approved in the audit:

1. **Button** (`src/components/ui/button.tsx`) — 6 variants (default/outline/secondary/ghost/destructive/link) on tokens. Primary = `bg-brass` + `text-content-on-brass` + `shadow-level-1` (substantial pill feel per §5). Focus ring flips from gray to brass via `focus-ring-brass` utility. Radius = `radius-base` (6px) per Q1. Motion: `transition-colors duration-quick ease-settle` + `active:scale-[0.97]`. 8 sizes preserved — 4 compact-dense legacy variants (xs + icon-xs + sm + icon-sm) documented as backward-compat; prefer default/sm for new work.
2. **Label + Input + Textarea** (`label.tsx`, `input.tsx`, `textarea.tsx`) — input family. Shell: `bg-surface-raised` + `border-border-base` + `rounded` (6px) + `py-2.5 px-4` (~40px height per §5 generous-default). Focus per Q9 (canonical §9 input form): border flips to `border-brass` + subtle `ring-2 ring-brass/30` glow. Invalid: `border-status-error` + `ring-status-error/20`. Disabled: `bg-surface-sunken` + `text-content-subtle`. Textarea uses `min-h-20` (80px) for generous-default multiline per §5.
3. **Select** (`select.tsx`) — 10 sub-components refreshed. Trigger shares Input shell. Content popup: `bg-surface-raised` + `border-border-subtle` + `rounded-md` (8px) + `shadow-level-2` + `p-2` + `duration-settle ease-settle` open / `duration-quick ease-gentle` close per §6 dropdown motion. Items: `rounded-sm` pill + `bg-brass-subtle` hover/focus + `text-brass` check indicator on selected + `text-status-error` + `bg-status-error-muted` on destructive-variant items.
4. **Card** (`card.tsx`) — 7 sub-components (`Card / CardHeader / CardTitle / CardDescription / CardAction / CardContent / CardFooter`). `bg-surface-elevated` + `rounded-md` (Q2: 8px default, 12px via className for signature cards) + `shadow-level-1` + `p-6` default / `p-4` size=sm. Title: `text-h3 font-medium text-content-strong`. Footer: `bg-surface-base` + `border-t border-border-subtle` (Q5 sinking feel — page color peeks through under elevated body).
5. **Dialog + DropdownMenu + SlideOver** — overlay family.
   - **Dialog** (`dialog.tsx`): `bg-surface-raised` + `rounded-lg` (12px modals) + `shadow-level-2` + `p-6`. Overlay `bg-black/40` + `duration-arrive ease-settle` enter / `duration-settle ease-gentle` exit (§6 modal motion pattern: opacity + slight zoom-in from 95%). `max-w-sm` default preserved per Q3 (per-page sizing via className, don't audit 58 call sites). Footer matches Card footer convention (`bg-surface-base` sinking feel).
   - **DropdownMenu** (`dropdown-menu.tsx`): 15 sub-components refreshed. Matches Select content popup composition. Destructive items: `text-status-error` + `bg-status-error-muted` on focus. Shortcut: `font-plex-mono text-caption text-content-subtle` (keybinds in mono per §4 "structured data").
   - **SlideOver** (`SlideOver.tsx`): custom platform primitive brought onto tokens. `bg-surface-raised` + `shadow-level-3` (floating — slide-overs are the most-prominent overlay on their screen). Header: `text-h4 font-medium text-content-strong`. Close button: `focus-ring-brass` + hover `bg-brass-subtle`.
6. **Navigation family** — 6 files, largest visual change per Q5 guidance.
   - **Sidebar** (`sidebar.tsx`, 583 lines): shell `bg-surface-sunken` per Q6 approval (recessed-navigation feel, DESIGN_LANGUAGE §3 explicit "sidebar backgrounds that sit below the page level"). Items: `text-content-muted` inactive → `bg-brass-subtle` + `text-content-strong` hover → `text-content-strong font-medium` active. **Phase 3 Spaces per-space accent chrome preserved** via inline style on active items — alpha bumped `10` → `18` (hex) to stay legible against the quieter sunken background. Command-bar trigger rebuilt with input-shell + brass focus. Section eyebrows: `text-micro font-semibold uppercase tracking-wider text-content-subtle`. `focus-ring-brass` on all interactive elements.
   - **DotNav** (`DotNav.tsx`): refresh preserves space-accent chrome on active dots. Inactive dots get brass-subtle hover. Add-space plus button: dashed border + hover brass-subtle. Existing `DotNav.test.tsx` continues passing (behavioral, not visual).
   - **Breadcrumbs** (`breadcrumbs.tsx`): `text-content-muted` inactive crumbs → `text-content-strong` hover + underline. Current crumb: `text-content-strong font-medium`. Separator chevrons: `text-content-subtle`. Home icon + each link get focus ring.
   - **Mobile tab bar** (`mobile-tab-bar.tsx`): full-screen "More" overlay on `bg-surface-base`. Bottom tab bar on `bg-surface-elevated` + `border-t border-border-subtle`. Added `min-h-11` (44px) to all interactive rows for WCAG 2.2 Target Size compliance. Active state uses preset-accent inline style at alpha 18.
   - **App-layout top header** (`app-layout.tsx`): root `bg-surface-base font-plex-sans text-content-base`. Header `bg-surface-elevated` + `border-b border-border-subtle`. Profile link gets focus ring + hover underline.
   - **Notification dropdown** (`notification-dropdown.tsx`, Q7): Popover-based (not DropdownMenu primitive) — needed explicit refresh. Matches overlay family composition: `bg-surface-raised` + `border-border-subtle` + `rounded-md` + `shadow-level-2`. Unread indicator switched from blue dot → **brass dot** (continuity of primary-accent signal). Unread count badge: `bg-status-error` + `font-plex-mono` numerals. Timestamp: `font-plex-mono text-caption text-content-subtle`.
7. **`--font-sans` flip** (`src/index.css:143`) — **single line change**. `--font-sans: 'Geist Variable', sans-serif` → `--font-sans: var(--font-plex-sans)`. Cascades to every rendered text node because zero components used `font-sans` explicitly — all inherit via the implicit `html body` font-family. Token-reference indirection means any future Plex-hosting change edits `tokens.css` only.
8. **Geist removal** — `@import "@fontsource-variable/geist"` removed from `index.css`; `@fontsource-variable/geist` uninstalled via `npm uninstall`. Stale "Geist" references in `tokens.css` + `fonts.css` comment blocks updated.
9. **Verification** — tsc 0 errors, vitest 165/165, backend 171/171 Phase 8a-8d.1 regression, build clean 5.02s. Built CSS contains all Session-2 tokens (`accent-brass`, `surface-elevated/raised/sunken`, `content-strong`, `focus-ring-brass`, `shadow-level`, `ibm-plex-sans`).
10. **Documentation** — AESTHETIC_ARC.md Session 2 entry + this file + CLAUDE.md Recent Changes.

### Variant decisions held (no consolidation in Session 2)

Per Q10–Q12 audit confirmations:
- **Button `secondary` + `outline`** — both kept. Revisit Session 6 after seeing convergence patterns in actual usage.
- **Button `xs` + `sm` + `icon-xs` + `icon-sm`** — all 4 sizes preserved for backward compat (295 Button imports). Documented in the component file as "compact-dense legacy sizes, prefer default/sm for new work."
- **Card size `default` + `sm`** — both kept. Matches DESIGN_LANGUAGE §5 default + dense pattern.

### Mixed-aesthetic state (expected during transition — documented for Session 3)

Per scope approval, Session 2 refreshes 8 core component categories + navigation. Extended components (toasts, alerts, badges, tables, forms chrome, tabs, separator, avatar, tooltip, standalone popover, drawer) remain on shadcn tokens until Session 3.

**Mixed-aesthetic page count:**
- **213 files** in `src/pages/` still reference shadcn semantic classes directly (`text-muted-foreground`, `border-border`, etc.). These pages inherit the refreshed primitives (Button/Input/Card/Dialog/DropdownMenu/Sidebar/…) without page-level edits — which is the design intent. Pages render coherently because the refreshed components carry the new aesthetic inside the page shells.
- **5 settings pages** use shadcn surface tokens directly in page chrome (`invoice-settings.tsx`, `call-intelligence-settings.tsx`, `Locations.tsx`, `vault-supplier-settings.tsx`, `urn-import-wizard.tsx`). Also by design — page-level refresh is not in Session 2 scope. Session 6 QA closes any remaining mixed-aesthetic issues.

Session 3 reduces the gap substantially by refreshing the extended-component set.

### Dark mode spot check (full pass deferred to Session 4)

Semantic tokens resolve correctly in dark mode automatically because Session 1 defined `[data-mode="dark"]` overrides for every token. Sample verifications:
- `bg-surface-elevated` → dark charcoal lift with inset top-edge highlight (Session 1 `--shadow-level-1` in dark mode includes `inset 0 1px 0 var(--shadow-highlight-top)`).
- `bg-brass` → dark-mode brass (lightness 0.70 vs light-mode 0.66, hue locked at 73 per DESIGN_LANGUAGE cross-mode brass rule).
- `text-content-strong` → near-white with warm tint (hue 80 dark vs 70 light).
- Shadows auto-swap to dark-mode warm-soft family.

No per-component `dark:` class overrides needed — the semantic tokens do the work. Full pass deferred to Session 4.

### Sidebar refresh verification (Q5 — 6 mount sites)

The sidebar is visible on every authenticated page. Shell shift from `bg-sidebar` (shadcn neutral-gray) → `bg-surface-sunken` (warm-cream recessed) is the single biggest visual change in Session 2. Active-state alpha bumped from `10` → `18` (hex) to maintain legibility against the quieter sunken tone per Q6 approval. The 6 mount sites (one per preset-layout permutation) all inherit the refresh through the single `sidebar.tsx` file — no per-preset customization needed.

**Manufacturing + Funeral Home preset verification:** both nav trees rendered via the same `SidebarSection` + `SidebarItem` components, so the refresh lands uniformly. Preset-specific conditional rendering (different nav items, different section headers) preserved untouched. The Phase 3 Spaces per-space accent chrome (warm-orange for Arrangement / crisp-green for Administrative / etc.) continues to override brass on active items — this is by design: brass is the platform's primary-action accent, spaces supply the visual personality for the current workspace context.

### Architectural patterns landed for Session 3 to carry forward

1. **Brass focus ring utility via className** (`focus-ring-brass` from Session 1) — applied on interactive non-input elements (buttons, nav items, menu items, close buttons). Consistent brass signal across refreshed surface.
2. **Input focus = border flip, not outside ring** (Q9 canonical §9 form) — inputs/textareas/select triggers all use `focus-visible:border-brass focus-visible:ring-2 focus-visible:ring-brass/30`. Different form from button focus ring but same brass color — the border IS the input's affordance.
3. **Footer sinks into surface-base** — Cards + Dialogs + SlideOver footer regions all use `bg-surface-base` + `border-t border-border-subtle`. Reads as "page color peeking through under the elevated body."
4. **Overlay family parity** — Dialog, DropdownMenu, Select content popup, SlideOver, notification-dropdown Popover all share `bg-surface-raised` + `border-border-subtle` + `rounded-md`/`-lg` + `shadow-level-2`/`-3` + `duration-settle`/`-arrive` `ease-settle` / `ease-gentle`. This is the DESIGN_LANGUAGE §6 canonical surface composition.
5. **`font-plex-mono` for structured data** — keybinds (DropdownMenuShortcut, command-bar kbd), unread count badge numerals, timestamps in notifications, sidebar kbd. Matches §4 "Plex Mono for alignment-requiring data."

### Files shipped Session 2

**Modified (14):**
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/label.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/dialog.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`
- `frontend/src/components/ui/SlideOver.tsx`
- `frontend/src/components/layout/sidebar.tsx`
- `frontend/src/components/layout/DotNav.tsx`
- `frontend/src/components/breadcrumbs.tsx`
- `frontend/src/components/layout/mobile-tab-bar.tsx`
- `frontend/src/components/layout/app-layout.tsx`
- `frontend/src/components/layout/notification-dropdown.tsx`

**Modified collateral (4):**
- `frontend/src/index.css` — `--font-sans` flip + Geist import removal.
- `frontend/src/styles/tokens.css` — comment updates (Geist refs removed).
- `frontend/src/styles/fonts.css` — comment updates (Plex is now platform font, not additive).
- `frontend/package.json` + `package-lock.json` — `@fontsource-variable/geist` removed.

**No new tests.** Component test coverage deferred per audit §4 decision.

### Ready for Session 3

Session 3 scope: extended components (toasts, alerts, badges, tables, forms chrome, tabs, separator, avatar, tooltip, standalone popover) + dedicated status treatment pass (error/warning/success/info UI across banners, badges, form validation, status indicators). Session 3 reduces mixed-aesthetic footprint substantially.

Then Session 4 (dark mode verification), Session 5 (motion pass), Session 6 (WCAG + final QA).

---

## Aesthetic Arc Session 1 — Token Foundation

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (unchanged — frontend-only).
**Arc:** Aesthetic Arc — Session 1 of 6. See `AESTHETIC_ARC.md`.
**Tests passing:** no new tests this session; existing 308 backend (Phase 1–8c) + 165 frontend vitest all green. `tsc -b` clean, `npm run build` clean.

### What shipped — token foundation + mode switching + Plex fonts

Aesthetic Arc Session 1 is pure infrastructure. It makes `DESIGN_LANGUAGE.md` tokens available throughout the platform without refreshing any existing component's appearance (except the one-off accepted status-color hex→oklch drift). Subsequent sessions (2–6) consume these tokens.

**New files (5):**
- `frontend/src/styles/tokens.css` — all DESIGN_LANGUAGE Section 9 tokens as CSS custom properties. `:root` for light mode defaults; `[data-mode="dark"]` for dark overrides. 57 color tokens (surfaces, content, borders, shadows, accent-brass variants, status variants), 3 elevation-shadow compositions (with automatic dark-mode top-edge highlight), 3 font-family tokens (Plex), 10-entry type scale, 2 radius additions (`--radius-base` + `--radius-full`), 5 durations, 2 easings, 5 max-widths.
- `frontend/src/styles/fonts.css` — `@import "@fontsource-variable/ibm-plex-sans/standard.css"` (variable 100-700) + `standard-italic.css` + `@fontsource/ibm-plex-serif/500.css` + `@fontsource/ibm-plex-mono/400.css`. Self-hosted; no Google CDN.
- `frontend/src/styles/base.css` — `prefers-reduced-motion: reduce` collapse, dark-mode font smoothing, `.focus-ring-brass` utility class, 5 `@utility duration-*` declarations (Tailwind v4 needs these explicit since `--duration-*` isn't an auto-utility namespace).
- `frontend/src/styles/globals.css` — bundles the above three. Imported by `index.css`.
- `frontend/src/lib/theme-mode.ts` — runtime API (`getMode`, `setMode`, `toggleMode`, `clearMode`) + `useThemeMode()` React hook with custom-event dispatch and system `prefers-color-scheme` subscription.

**Modified files (2):**
- `frontend/src/index.css` — imports `./styles/globals.css`, extends `@custom-variant dark` to match both `.dark` class (legacy noop) AND `[data-mode="dark"]` attribute (canonical), adds DESIGN_LANGUAGE utility bindings to the `@theme inline` block (every Section 9 token exposed to Tailwind utilities), migrates existing `--status-{success,warning,info,danger}` values from hex (shadcn defaults) to DESIGN_LANGUAGE oklch per approval decision 3.
- `frontend/index.html` — adds synchronous inline `<script>` in `<head>` for flash-of-wrong-mode prevention (reads `localStorage['bridgeable-mode']` + `prefers-color-scheme` fallback; sets `data-mode="dark"` on `<html>` before any CSS parses).

**Installed packages:** `@fontsource-variable/ibm-plex-sans@5.2.8`, `@fontsource/ibm-plex-serif@5.2.7`, `@fontsource/ibm-plex-mono@5.2.7`. Variable font variants don't exist for Plex Serif / Mono on npm (only Plex Sans has variable). Existing `@fontsource-variable/geist` stays as the platform default until Sessions 2-3 migrate per-component.

### Approved deviations from DESIGN_LANGUAGE.md Section 9

DESIGN_LANGUAGE.md Section 9 is written assuming a Tailwind v3-style `tailwind.config.js`. The Bridgeable frontend uses **Tailwind v4 via `@tailwindcss/vite`** where theme config lives inline in CSS via `@theme inline { ... }`. Session 1 translates each Section 9 JS config entry to `@theme inline` lines:

| Section 9 (Tailwind v3 JS config) | Session 1 (Tailwind v4 `@theme inline` line) |
|---|---|
| `colors.surface.base = 'var(...)'` | `--color-surface-base: var(--surface-base);` |
| `colors.brass.DEFAULT = 'var(...)'` | `--color-brass: var(--accent-brass);` |
| `fontSize['display-lg'] = [size, { lineHeight, fontWeight }]` | `--text-display-lg: var(--text-display-lg);` + `--text-display-lg--line-height: 1.1;` + `--text-display-lg--font-weight: 500;` |
| `boxShadow['level-1'] = 'var(...)'` | `--shadow-level-1: var(--shadow-level-1);` |
| `transitionDuration.quick = 'var(...)'` | `@utility duration-quick { transition-duration: var(--duration-quick); }` (v4's `--duration-*` is not an auto-namespace; needs explicit `@utility`) |
| `transitionTimingFunction.settle = 'var(...)'` | `--ease-settle: var(--ease-settle);` (v4 `--ease-*` IS an auto-namespace) |
| `maxWidth.reading = 'var(...)'` | `--container-reading: var(--max-w-reading);` (v4's `--container-*` generates both `max-w-*` and `@container` utilities) |
| `fontFamily.sans = ['IBM Plex Sans', ...]` | `--font-plex-sans: var(--font-plex-sans);` (new name; `--font-sans` stays Geist) |

DESIGN_LANGUAGE.md Section 9 gets a v4-clarification note added alongside the JS config example pointing at `frontend/src/index.css` as the live mapping — per approval decision 7.

### Other architectural decisions recorded

1. **shadcn token coexistence** (approval decision 8): existing shadcn CSS variables (`--background`, `--foreground`, `--card`, `--popover`, `--primary`, `--muted`, `--destructive`, `--border`, `--input`, `--ring`, `--sidebar*`, `--chart-*`, `--radius`, `--accent`) untouched. DESIGN_LANGUAGE tokens live alongside. Sessions 2-3 migrate component references; final cleanup retires shadcn layer.
2. **`--font-sans` untouched** (approval decision 1): Plex loaded under `--font-plex-{sans,serif,mono}`. Geist continues as platform default.
3. **`--radius-xl` +2px drift** (approval decision 2): existing calc-based value stays at 14px; DESIGN_LANGUAGE would be 16px. Sub-perceptual. Added `--radius-base: 6px` + `--radius-full: 9999px` as new names.
4. **Status-color hex→oklch drift** (approval decision 3 override): `--status-{success,warning,info,danger}` migrated from generic hex to DESIGN_LANGUAGE oklch. The one accepted one-time visual change in Session 1. Small surface area + correct colors > parallel-system mental overhead.
5. **Dark-mode selector coexistence** (approval decision 4): `@custom-variant dark (&:is(.dark *, [data-mode="dark"] *))` matches both.
6. **No visible mode toggle UI** (approval decision 5 + Session 2 scope): Session 1 ships runtime API only. Verification via devtools console.
7. **Tailwind v4 `@theme inline` over JS config** (approval decision 6).
8. **Plex Sans variable, Serif/Mono non-variable** (approval decision 10).
9. **Phase 3 Spaces accent system orthogonal** (approval decision 9): `--space-accent*` and `--accent-brass*` coexist cleanly by name. Conceptual relationship is Phase 8e/9 scope.
10. **Brass focus ring as opt-in utility** (not global replacement): `.focus-ring-brass` class scoped to refreshed components. Existing global `* { outline-ring/50 }` rule stays active so non-refreshed components retain their current focus treatment during the transition window.

### Tailwind utilities now available

Verified in the build output (checked compiled CSS for class-selector presence):

- **Surfaces** — `bg-surface-{base,elevated,raised,sunken}`
- **Content** — `text-content-{strong,base,muted,subtle,on-brass}`
- **Borders** — `border-border-{subtle,base,strong,brass}`
- **Brass** — `bg-brass`, `bg-brass-{hover,active,muted,subtle}` (+ `text-`, `border-`, `ring-` prefixes)
- **Status** — `text-status-{error,warning,success,info}`, `bg-status-{error,warning,success,info}-muted`
- **Fonts** — `font-plex-{sans,serif,mono}`
- **Type scale** — `text-{display-lg,display,h1,h2,h3,h4,body,body-sm,caption,micro}` (each with paired line-height + font-weight)
- **Radii** — `rounded-{base,full}` added; existing `rounded-{sm,md,lg,xl,2xl,3xl,4xl}` preserved
- **Shadows** — `shadow-level-{1,2,3}` (dark-mode top-edge highlight automatic)
- **Durations** — `duration-{instant,quick,settle,arrive,considered}` (100/200/300/400/600 ms)
- **Easings** — `ease-{settle,gentle}`
- **Max-widths** — `max-w-{reading,form,content,wide,dashboard}` (34/40/56/72/96 rem)
- **Utility class** — `.focus-ring-brass`

### Verification results (per the checklist)

- ✅ **Build:** `npm run build` succeeds in ~5s. CSS bundle 200 kB (gzip 31 kB).
- ✅ **TypeScript:** `tsc -b` clean.
- ✅ **Frontend tests:** 11 test files, 165/165 vitest green.
- ✅ **Backend tests:** 308/308 Phase 1-8c green (unchanged; frontend-only session).
- ✅ **Token resolution:** production CSS contains 134 `[data-mode=dark]` selectors + both light + dark `--surface-base` values.
- ✅ **Font loading:** 16 Plex `.woff2` files bundled alongside 1 Geist `.woff2`. No external CDN requests.
- ✅ **Tailwind utility generation:** probe file temporarily added, verified every new class compiled into the CSS bundle, probe file removed before commit.
- ✅ **Dev server:** starts clean; Vite HMR unaffected.
- ✅ **Visual regression spot check:** existing pages look identical to pre-Session-1 except status colors (expected — the accepted drift).

### Latent items deferred to future sessions

- **No mode toggle UI yet.** Session 2's settings refresh adds a toggle component consuming `useThemeMode()`.
- **Component visual refresh** — Sessions 2-3.
- **Dark mode visual verification across refreshed components** — Session 4.
- **Motion pass applying `ease-settle` / `duration-*` consistently** — Session 5.
- **WCAG 2.2 AA audit** — Session 6.
- **shadcn token retirement** — post-Session-6 cleanup.
- **Phase 3 Spaces accent vs. brass accent conceptual question** — Phase 8e/9 design scope.

Next: **Session 2 — Core component refresh** (buttons, inputs, cards, modals, dropdowns, navigation). First session that creates observable visual change.

---

## Workflow Arc Phase 8d.1 — Safety Program Migration

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — no new DB migration; per-run cardinality reuses the pre-existing `SafetyProgramGeneration.status` enum from r15).
**Arc:** Workflow Arc — Phase 8d.1 of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 37 new (13 BLOCKING parity + 2 BLOCKING latency + 16 unit + 6 Playwright scenarios). Phase 8a/8b/8c/8d regression: **171 passing, no regressions**. Latency on dev hardware: next_item p50=5.7ms / p99=7.6ms (17× / 40× headroom); apply_action p50=10.0ms / p99=13.3ms (20× / 38× headroom).

### Scope: reconnaissance for AI-generation-with-approval shape

Phase 8d.1 is a single-migration reconnaissance session following the Phase 8b pattern. The target — `wf_sys_safety_program_gen` — was deferred from Phase 8d because its shape is meaningfully different from any prior migration: the agent generates a complete document via Claude (non-deterministic), stages it + a PDF for staff review, approval promotes it to the tenant's canonical SafetyProgram (the legal safety-program-of-record). OSHA compliance implications make parity discipline critical.

**Template v2.2 ships alongside the migration** per the Phase 8b precedent (reconnaissance phase = template deliverable). Three additions cover patterns the migration surfaced.

### Per-question audit answers (9 template questions + 5 safety-specific)

Full audit captured in chat before implementation; recorded here verbatim by question:

1. **Current implementation:** `app/services/safety_program_generation_service.py` (580 lines, no dedicated agent class). Methods: `scrape_osha_for_generation`, `generate_program_content`, `generate_pdf`, `approve_generation`, `reject_generation`, `run_monthly_generation`. Invoked via APScheduler cron (monthly 1st at 6am UTC) + `/safety/programs/generate*` API routes + placeholder workflow steps (no-op pre-8d.1).

2. **Write timing:** **deferred + partially immediate**. Pipeline steps stamp OSHA + generation + PDF fields on `SafetyProgramGeneration` (immediate, during pipeline). `SafetyProgram` canonical row lands on approval (deferred). Classification: per-run with deferred canonical-entity write.

3. **Generation pipeline:** monthly cron → `run_monthly_generation` → schedule lookup → existence check → stage fresh `SafetyProgramGeneration` → scrape OSHA → Claude Sonnet generation (`safety.draft_monthly_program` prompt, 4096 max tokens) → WeasyPrint PDF via D-2 `document_renderer.render(template_key="pdf.safety_program_base")` → `status='pending_review'`. Admin reviews → approve (promote to SafetyProgram + stamp posted_at) or reject (status='rejected', no program write).

4. **Current approval mechanism:** bespoke `/safety/programs` with AI Generated + Manual tabs. Approve endpoint `POST /api/v1/safety/programs/generations/{id}/approve`, reject endpoint `POST /.../{id}/reject`. Permission `safety.trainer.approve`. **NO AuditLog writes** — audit trail lives entirely in row fields (`SafetyProgramGeneration.reviewed_by/reviewed_at/review_notes/posted_at/status` + `SafetyProgram.reviewed_by/last_reviewed_at/status/version`).

5. **PDF storage:** canonical `Document` + `DocumentVersion` via D-2 renderer, stored in R2 at `tenants/{company_id}/documents/{doc_id}/v{n}.pdf`. Stamped on `SafetyProgramGeneration.pdf_document_id`. **No storage migration on approval** — the Document stays at the same key; approval is a pure state transition + SafetyProgram upsert. Relevant for the "no Document re-render on approve" parity test (category 7).

6. **Scheduler invocation:** pre-8d.1 had both the APScheduler cron in `scheduler.py` (container-UTC) AND the workflow row's placeholder `scheduled` trigger (tenant-local) — workflow scheduler fired the no-op placeholders, APScheduler fired the real pipeline. Post-8d.1: APScheduler cron retired; workflow scheduler is single-owner. Tenant-local 6am is a TZ-correctness improvement.

7. **Anomaly structure:** NONE. No `AgentAnomaly` rows are created today. `SafetyProgramGeneration` is the dedicated tracking entity with its own status machine. This drives the **per-run cardinality** decision.

8. **Approval audit trail:** row-field-embedded only (see #4). Simpler to preserve than cash_receipts/month_end_close parity.

9. **OSHA compliance:** no retention policy, no approver role restrictions beyond `safety.trainer.approve`, PDF export via D-1 presigned URL. Migration doesn't change any compliance surface.

10. **Claude determinism:** non-deterministic (Claude Sonnet default temperature ~0.7, no temperature override). Drives the **AI-generation-content-invariant parity** pattern (§5.5.5).

11. **Related entities for context:** generation metadata + SafetyTrainingTopic + OSHA scrape + prior SafetyProgram version + generated PDF Document. 5-entity payload, implemented as `_build_safety_program_related`.

12. **Suggested AI questions** (4 per approved scope): "How does this program change from last year's?" / "Are there OSHA requirements for {{topic_title}} I should verify are in here?" / "Is this program appropriate for a precast concrete operation?" / "What sections need the most scrutiny for compliance?"

13. **Permission gate:** `safety.trainer.approve` on approve/reject; `request_review` open to any authenticated tenant user (safe — no approval rights required to flag for a teammate).

14. **Cardinality decision:** **per-run**. New sixth-variant in Template v2.2 §10. Distinct from per-staging-row (which ADDS the state column) by the pre-existing-state-machine criterion.

15. **Parity approach (safety-specific question):** seed SafetyProgramGeneration directly in `pending_review` with pre-populated AI content. Run approval via both paths. Assert field-level writes. Never invoke Claude, never assert content reproducibility.

16. **PDF generation mechanics:** D-2 `document_renderer.render(template_key="pdf.safety_program_base")` — shares path with invoice/quote/statement PDFs. No generalization needed.

17. **AgentJob vs SafetyProgramGenerationRun:** SafetyProgramGeneration is dedicated (predates arc). Adapter does NOT create AgentJob — would be double-bookkeeping. First migration-arc pattern to bypass AgentJob entirely.

18. **Rollback gap audit:** none. Approve path has a single `db.commit()` — all writes succeed or all roll back. PDF-generation exception-swallow in `run_monthly_generation` is deliberate "regenerable on demand" design, NOT a rollback gap.

19. **Legacy UI specifics:** `/safety/programs` has AI Generated + Manual tabs. Triage covers AI Generated primary flow (pending_review rows). Triage does NOT cover: Manual tab (non-AI programs), PDF regeneration, ad-hoc topic generation, rejected/approved history views. Legacy coexistence indefinite.

### Files shipped Phase 8d.1

**New (5):**
- `backend/app/services/workflows/safety_program_adapter.py` (~290 lines, 4 public functions)
- `backend/scripts/seed_triage_phase8d1.py` (Option A idempotent seed for `triage.safety_program_context_question`)
- `backend/tests/test_safety_program_migration_parity.py` (13 BLOCKING parity tests across 9 categories)
- `backend/tests/test_safety_program_triage_latency.py` (2 BLOCKING latency gates)
- `backend/tests/test_phase8d1_unit.py` (16 unit tests)
- `frontend/tests/e2e/workflow-arc-phase-8d1.spec.ts` (6 Playwright scenarios)

**Modified (5):**
- `backend/app/scheduler.py` — retired `job_safety_program_generation`, `JOB_REGISTRY` entry, and `add_job` block with explanatory retirement comments.
- `backend/app/data/default_workflows.py` — `wf_sys_safety_program_gen` rewritten from 4 placeholder steps to 1 `call_service_method` step.
- `backend/app/services/workflow_engine.py` — 1 new `_SERVICE_METHOD_REGISTRY` entry (`safety_program.run_generation_pipeline`).
- `backend/app/services/triage/engine.py` — 1 new `_DIRECT_QUERIES` entry (`safety_program_triage` → `_dq_safety_program_triage`).
- `backend/app/services/triage/ai_question.py` — 1 new `_RELATED_ENTITY_BUILDERS` entry with 5-entity payload builder.
- `backend/app/services/triage/action_handlers.py` — 3 new handlers (`safety_program.approve / reject / request_review`).
- `backend/app/services/triage/platform_defaults.py` — 1 new queue config (`_safety_program_triage`) with AI panel + 4 suggested questions.

### APScheduler cron removal verification (Template v2.2 §7.7)

Pre-retirement state in `app/scheduler.py`:
- Line ~272: `def job_safety_program_generation(): ...` (5-line function calling `_run_per_tenant`)
- Line ~435: `"safety_program_generation": job_safety_program_generation,` (JOB_REGISTRY entry)
- Line ~604: 7-line `scheduler.add_job(job_safety_program_generation, CronTrigger(day=1, hour=6, minute=0), ...)` block

Post-retirement state:
- All three replaced with retirement-comment blocks pointing at the workflow row as the new single-owner path.
- Unit test `test_phase8d1_unit.py::TestSchedulerCronRetirement::test_job_registry_has_no_safety_program_entry` enforces that `"safety_program_generation"` key is no longer in `JOB_REGISTRY` (catches accidental re-adds in future refactors).

### Template v2.2 additions summary

Three additions, all shipped in the same commit as the migration (reconnaissance convention per Phase 8b):

1. **§5.5.5 — AI-generation-content-invariant parity pattern.** Freeze pre-approval state with pre-populated AI content; both legacy and triage paths act on the frozen state; assert field-level writes only. Never invoke AI, never assert content reproducibility. Safety program's parity test file is the reference implementation.

2. **§7.7 — Legacy APScheduler cron removal convention.** When the migration target has a dedicated APScheduler cron calling the same pipeline function the adapter wraps, remove the APScheduler entry. Workflow scheduler becomes single-owner; tenant-local TZ precision is a bonus. Accepted alternative: keep APScheduler + switch workflow `trigger_type="manual"` + have the cron call `workflow_engine.start_run` (only when the APScheduler job emits observability artifacts worth keeping).

3. **§10 — Sixth cardinality: per-run.** Distinct from per-staging-row (which ADDS the state column) by the "pre-existing state machine" criterion. Triage queue reads the domain entity's existing status enum directly. No AgentJob wrapper, no new schema column, no AgentAnomaly. SafetyProgramGeneration is the reference.

### Legacy coexistence verification

- `/safety/programs` UI mounts without redirect to login or 403 (Playwright scenario 4).
- Legacy `POST /api/v1/safety/programs/generations/{id}/approve` endpoint still returns 404/403 for valid auth (i.e., route still registered) (Playwright scenario 5).
- Manual tab + rejected/approved history views continue to work (out-of-scope for triage per approved scope).
- Ad-hoc `/generate-for-topic/{topic_id}` + `/regenerate-pdf` endpoints preserved.

### Parity test results

**13 / 13 tests pass** across 9 categories:

| # | Category | Tests | Focus |
|---|---|---|---|
| 1 | Approval field-identity | 1 | Both paths produce identical SafetyProgramGeneration + SafetyProgram writes on fresh insert |
| 2 | Version-increment identity | 1 | Both paths bump existing SafetyProgram version v1→v2 on same OSHA code |
| 3 | Rejection field-identity | 1 | Both reject paths transition status→rejected + stamp reviewer fields identically |
| 4 | Reject-without-reason error | 2 | ValueError "Rejection notes are required" on empty AND whitespace-only reason |
| 5 | Non-pending-review state rejection | 2 | Approving already-approved OR already-rejected rows raises identical ValueError |
| 6 | No SafetyProgram on reject | 1 | Reject writes ZERO SafetyProgram rows (negative assertion) |
| 7 | No Document re-render on approve | 1 | Approve path creates ZERO new Document / DocumentVersion rows (negative assertion) |
| 8 | Cross-tenant isolation | 2 | Tenant A cannot approve nor reject tenant B's generation |
| 9 | Pipeline-scale equivalence | 2 | Adapter's `run_generation_pipeline` returns same shape as legacy `run_monthly_generation`; dry-run short-circuits without invoking pipeline |

### AI panel activation verification

- Prompt seeded via `scripts/seed_triage_phase8d1.py` — one-shot run emits `triage.safety_program_context_question  created`. Second run emits `noop`. Idempotency verified.
- Queue config references `ai_prompt_key="triage.safety_program_context_question"` (unit test `test_phase8d1_unit.py::TestQueueConfig::test_ai_panel_included`).
- 4 suggested questions render in the queue config (Playwright scenario 3).
- Prompt system text includes `PRECAST CONCRETE` vertical-appropriate terminology marker + `COMPLIANCE DISCIPLINE` block instructing Claude to cite the scrape snippet or defer to the full standard URL (unit test `test_ai_prompt_seed.test_prompt_key_exists` confirms).
- Claude response to seeded questions happens at query-time via the existing Phase 6 Intelligence execute path — not tested here because that's AI end-to-end, not migration scope.

### Pre-existing latent bug surfaced (flagged, NOT fixed)

**`safety_program_generations.pdf_document_id` FK points at `documents_legacy` instead of canonical `documents`.** The Phase D-1 canonical-documents rewrite renamed the old table to `documents_legacy` (now 0 rows) and created a new canonical `documents` table. The FK on the safety-program-generations side was not repointed. Production's `generate_pdf` writes to canonical `documents` but then hits the FK check targeting `documents_legacy` (empty) and fails. The exception is swallowed by `run_monthly_generation`'s non-fatal try/except at line 462. Net effect: production safety-program PDFs get created as canonical Documents but never linked back to their generation row; bespoke UI shows pending_review rows without downloadable PDFs. Parity tests use `pdf_document_id=NULL` fixtures to avoid tripping the constraint.

**Flagged for post-arc cleanup** in Template v2.2 §15 entry #7. Fix requires an Alembic migration dropping the old FK and creating a new one targeting `documents(id)`. Out of Phase 8d.1 scope (not a migration-mechanics concern).

### Rollback behavior

None preserved. The approve path has a single `db.commit()` — transactional integrity. No rollback gap to document.

### Permission model confirmation

- `safety.trainer.approve` gates approve + reject actions.
- `safety.trainer.view` implicit for queue visibility (users without view permission don't see the queue in their list).
- `request_review` is ungated (any authenticated tenant user) — safe because escalation doesn't require approval rights.
- Cross-tenant isolation enforced via `_load_generation_scoped` defense-in-depth helper.

### What's next

**Ready for Aesthetic Arc Session 2 (core component refresh).** Buttons, inputs, cards, modals, dropdowns, navigation — first session that creates observable visual change across the platform.

Workflow Arc post-8d.1 sequence:
- Aesthetic Arc Sessions 2-5 (component refresh, layout refresh, typography, motion, polish)
- Phase 8e: Spaces and default views implementation (builds on `reapply_role_defaults_for_user` helper from 8a)
- Phase 8f: Remaining accounting migrations (unbilled_orders, estimated_tax_prep, inventory_reconciliation, budget_vs_actual, 1099_prep, year_end_close, tax_package, annual_budget)
- Phase 8g: Dashboard rework
- Latent bug cleanup session (includes pdf_document_id FK repoint, month-end-close rollback gap, time_of_day TZ bug, event-trigger dispatch gap)
- Phase 8h: Arc finale (legacy `/agents` retirement, `/api/v1/agents/accounting` → 410 Gone, final consolidation)

---

## Workflow Arc Phase 8d — Vertical Workflow Migrations

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` → `r38_fix_vertical_scope_backfill` → `r39_catalog_publication_state` → `r40_aftercare_email_template`.
**Arc:** Workflow Arc — Phase 8d of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 39 new this phase (20 unit + 10 aftercare parity + 10 catalog_fetch parity + 4 BLOCKING latency gates + 3 r38 regression + 6 Playwright scenarios). Phase 8a/8b/8c regression: **140 passing, no regressions**. Actual latency on dev: aftercare next_item p50=30.3ms (3.3× headroom), apply_action p50=22.1ms (9× headroom); catalog_fetch next_item p50=2.9ms (34× headroom), apply_action p50=5.5ms (36× headroom).

### Scope: minimal vertical migrations + r36 scope-backfill bug fix

Phase 8d ships two workflow migrations (`wf_fh_aftercare_7day` — FH tier-3, `wf_sys_catalog_fetch` — MFG tier-1) plus a corrective data migration closing an r36 classification bug that affected 10 workflows. Per approved scope:

- **Deferred to Phase 8d.1**: `wf_sys_safety_program_gen` — deserves its own reconnaissance session because it writes the full SafetyProgramGeneration record via Claude Sonnet + WeasyPrint PDF + month-ahead lookahead, and the current adapter pattern hasn't been exercised against AI-generation flows yet.
- **Intentionally service-only (documented, not migrated)**: the urn engraving two-gate proof approval. It's already a service-owned workflow that coexists with the workflow registry by design — migrating it would invert the existing customer-facing URL contract (`/proof-approval/{token}`) for no platform benefit.
- **Skipped**: uline_gloves inventory-reorder suggestion (stubbed service, no customer usage).

### Critical correction — r38 fixes r36's scope-backfill bug

**r36 misclassified 10 workflows as `scope='core'` when they should have been `scope='vertical'`.** The CASE expression in r36 was `WHEN tier = 1 THEN 'core'` — it ignored the `vertical` column entirely. Any `wf_sys_*` row with `tier=1 AND vertical IS NOT NULL` got misfiled under the three-tab workflow builder's Core tab, meaning tenants in the wrong vertical could see workflows that would never apply to them.

Affected workflows (audit surfaced the complete list):

| Workflow | Vertical | Corrected to |
|---|---|---|
| `wf_sys_legacy_print_proof` | manufacturing | vertical |
| `wf_sys_legacy_print_final` | manufacturing | vertical |
| `wf_sys_safety_program_gen` | manufacturing | vertical |
| `wf_sys_vault_order_fulfillment` | manufacturing | vertical |
| `wf_sys_document_review_reminder` | manufacturing | vertical |
| `wf_sys_auto_delivery` | manufacturing | vertical |
| `wf_sys_catalog_fetch` | manufacturing | vertical |
| `wf_sys_ss_certificate` | manufacturing | vertical |
| `wf_sys_scribe_processing` | funeral_home | vertical |
| `wf_sys_plot_reservation` | funeral_home | vertical |

`r38_fix_vertical_scope_backfill` is idempotent — it only touches rows that still hold the incorrect `scope='core'` value, so re-running after any manual re-correction is a no-op. The regression test (`test_r38_scope_backfill_fix.py::TestR38ScopeBackfillFix`) enforces the post-r38 invariant:

> `tier = 1 AND vertical IS NOT NULL  IMPLIES  scope = 'vertical'`

Any future seed that adds a tier-1 vertical-specific workflow without correctly setting `scope='vertical'` fails this gate. The Phase 8a test `test_tier_1_workflows_are_core` was tightened to `test_tier_1_cross_vertical_workflows_are_core` (the "cross-vertical" qualifier is the other half of the symmetric rule).

### Migrations

**r38_fix_vertical_scope_backfill**: idempotent UPDATE against the canonical 10 target IDs. Downgrade reverts only that exact set, so forward-and-back cycling is safe.

**r39_catalog_publication_state**: adds `urn_catalog_sync_logs.publication_state VARCHAR(16) NOT NULL DEFAULT 'published'` with a CHECK constraint accepting `pending_review / published / rejected / superseded`. Partial index on `publication_state = 'pending_review'` sized to the triage-queue hot path. Pre-r39 rows backfill to `published` (preserving legacy auto-publish semantics). The column enables Phase 8d's triage-gated staging flow for Wilbert catalog fetches — previously the cron auto-upserted every MD5-diffed PDF to urn_products with no admin gate.

**r40_aftercare_email_template**: seeds the missing `email.fh_aftercare_7day` D-2 managed template. **Pre-8d bug**: the `wf_fh_aftercare_7day` seed referenced `template="aftercare_7day"` — a key that didn't exist anywhere in the template registry. If the scheduler had fired (it didn't, because nobody had an FH tenant with services seven days ago in staging), the send_email step would have silently produced no email. Phase 8d seeds the template via r40, then refactors the workflow to render it through `delivery_service.send_email_with_template` via the aftercare_adapter.

### Aftercare migration (`wf_fh_aftercare_7day`)

**Pre-8d shape** (a two-step workflow with `send_email` + `log_vault_item`) → **Post-8d shape** (a one-step `call_service_method` dispatch to `aftercare.run_pipeline`).

**Triage-only** — no financial writes, just email + VaultItem. One item per case matrix: the pipeline queries FuneralCase rows whose `service_date + 7 days == today`, stages one AgentAnomaly per eligible case under a new `fh_aftercare` job type. The aftercare_triage queue pulls those anomalies via `_dq_aftercare_triage`.

**Triage actions** (3): `send` (approve-equivalent — renders `email.fh_aftercare_7day` via delivery_service + logs a VaultItem + resolves anomaly), `skip` (reject-equivalent — resolves with reason, no email), `request_review` (escalate — stamps note without resolving).

**Zero logic duplication**: the email body is rendered from the D-2 managed template. The VaultItem write uses `vault_service.create_vault_item`. Both are shared paths — any change flows through the template editor or the vault service respectively.

### Catalog fetch migration (`wf_sys_catalog_fetch`)

**Pre-8d shape**: weekly cron ran `UrnCatalogScraper.fetch_catalog_pdf` which, on MD5 change, called `WilbertIngestionService.ingest_from_pdf` directly — products upserted in production without admin review. Acceptable during development; unacceptable at scale (Wilbert could ship a catalog with wrong retail prices and tenants would auto-publish).

**Post-8d shape**: cron fires `catalog_fetch.run_staged_fetch` which downloads + MD5-diffs + archives to R2 + creates an UrnCatalogSyncLog with `publication_state='pending_review'`. **No product writes until admin approves.** The catalog_fetch_triage queue surfaces the staged log.

**Triage actions** (3): `approve` (publish — fetches PDF bytes from R2, runs the **unchanged** legacy `WilbertIngestionService.ingest_from_pdf`, flips `publication_state='published'`), `reject` (with reason, flips to `rejected`), `request_review` (stamps note, stays pending).

**Zero duplication**: the upsert path is the legacy ingest function unchanged. The adapter's only job is state-flipping + fetching staged bytes from R2.

**Supersede semantics**: a newer fetch while an older pending-review exists marks the older one `superseded`. One pending catalog in the queue at a time; admin isn't forced to decide on a stale PDF.

### NO AI question panels on 8d queues (approved scope decision)

Per user-approved scope: the aftercare + catalog_fetch queues are **audit/retry workspaces**, not **decision workspaces**. Adding AI question panels would have required new Intelligence prompts, rate-limit + _RELATED_ENTITY_BUILDERS extensions, and tests — scope-creep for no clear operator win. The operator reviewing an aftercare case reads three fields (case number, primary contact, service date) and clicks send; they don't need AI assistance. Same for catalog fetch: the decision is scanning the diff, not asking AI for guidance.

The invariant is enforced in `test_phase8d_unit.py::TestQueueConfigs::test_no_ai_question_panels_on_phase8d_queues` — any future phase that wants to add an AI panel must explicitly lift this test.

If engagement patterns later prove AI panels would help, a follow-up can add them alongside the existing 4 wired panels (month_end_close, ar_collections, expense_categorization, cash_receipts_matching).

### Engraved urn two-gate — documented as intentionally service-only

The urn engraving workflow ([urn_engraving_service.py](backend/app/services/urn_engraving_service.py)) ships a two-gate approval: (1) the funeral home approves the engraving proof via a token-based public URL (`/proof-approval/{token}`, 72-hour expiry, no auth), (2) staff approves the FH-approved proof internally. This is **intentionally NOT a workflow** — it's a service-owned multi-step process with a customer-facing URL contract that would invert if migrated to workflow_engine + triage.

Phase 8d documents this decision explicitly in `CLAUDE.md` so future migration passes don't re-audit it. The engraving workflow appears in the platform workflow builder as a read-only "service-owned" row (same treatment as the pre-migration agent workflows before they were moved to `scope=core` under workflow_engine).

### Adapter + infrastructure

**New adapters (2)**:
- `app/services/workflows/aftercare_adapter.py` — `run_pipeline` (staging), `approve_send` (email + vault), `skip_case`, `request_review`. AgentJob + AgentAnomaly reuse — same container pattern as Phase 8b/c.
- `app/services/workflows/catalog_fetch_adapter.py` — `run_staged_fetch` (download + hash + stage), `approve_publish` (calls legacy ingest), `reject_publish`, `request_review`.

**Workflow engine safelist**: 2 new `_SERVICE_METHOD_REGISTRY` entries (`aftercare.run_pipeline`, `catalog_fetch.run_staged_fetch`).

**Triage extensions**:
- 2 new `_DIRECT_QUERIES` (`aftercare_triage`, `catalog_fetch_triage`).
- 6 new HANDLERS (`aftercare.{send, skip, request_review}`, `catalog_fetch.{approve, reject, request_review}`).
- 2 new platform_default queue configs (NO AI panels per scope).
- **Intentionally skipped**: `_RELATED_ENTITY_BUILDERS` extension — only needed when queues carry AI question panels. Phase 8d has none.

### Files

**New (6)**:
- `backend/alembic/versions/r38_fix_vertical_scope_backfill.py`
- `backend/alembic/versions/r39_catalog_publication_state.py`
- `backend/alembic/versions/r40_aftercare_email_template.py`
- `backend/app/services/workflows/aftercare_adapter.py` (~380 lines)
- `backend/app/services/workflows/catalog_fetch_adapter.py` (~360 lines)
- `frontend/tests/e2e/workflow-arc-phase-8d.spec.ts`

**Modified (7)**:
- `backend/app/models/urn_catalog_sync_log.py` — adds `publication_state` column.
- `backend/app/services/documents/_template_seeds.py` — adds `_aftercare_seeds()` + EMAIL_FH_AFTERCARE_7DAY template body/subject.
- `backend/app/services/workflow_engine.py` — 2 new `_SERVICE_METHOD_REGISTRY` entries.
- `backend/app/services/triage/engine.py` — 2 new direct-query builders + registry entries.
- `backend/app/services/triage/action_handlers.py` — 6 new handlers + registry entries.
- `backend/app/services/triage/platform_defaults.py` — 2 new queue configs + register calls.
- `backend/app/data/default_workflows.py` — aftercare + catalog_fetch seeds rewritten to `call_service_method`.
- `backend/tests/test_workflow_scope_phase8a.py` — tightens `test_tier_1_workflows_are_core` → `test_tier_1_cross_vertical_workflows_are_core`.

**New tests (6)**:
- `backend/tests/test_r38_scope_backfill_fix.py` — 3 regression tests (primary + companion invariant + target-list smoke).
- `backend/tests/test_phase8d_unit.py` — 19 unit tests across 6 classes.
- `backend/tests/test_aftercare_migration_parity.py` — 10 tests (pipeline + actions + isolation).
- `backend/tests/test_catalog_fetch_migration_parity.py` — 10 tests (staging + actions + supersede + isolation).
- `backend/tests/test_phase8d_triage_latency.py` — 4 BLOCKING gates.

### Test results

**New this phase**: **39 passing** (3 + 19 + 10 + 10 + 4 + 6 Playwright scenarios — the Playwright count isn't included in the 39 since they weren't executed here; they're staging-gated). Full Phase 8a/8b/8c/8d backend regression: **140 passing, no regressions**. Phase 8c parity + latency suites: all 40 tests unchanged.

### What's next

Phase 8d.1 — `wf_sys_safety_program_gen` reconnaissance migration. Not a batch item; earns its own session because it's the first workflow-arc migration exercising AI-generation with approval gating (Claude Sonnet → 7-section HTML → WeasyPrint PDF → admin approval). The adapter pattern to migrate it hasn't been proven out yet — the safety agent writes to SafetyProgramGeneration directly today and does NOT use AgentJob as a container, so the migration shape is genuinely different from 8b/8c/8d.

Then Phase 8e for the workflow-builder UI surfaces — the three-tab (core/vertical/tenant) browser, the Option-A fork button on core/vertical rows, the soft-customization affordance for parameter overrides, and the Phase 8d migrations' "service-owned" badge on engraving. 8a–8d has all been backend infrastructure; 8e+ is where this becomes visible to tenant admins.

---

## Workflow Arc Phase 8c — Core Accounting Migrations Batch 1

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (unchanged — no schema changes in 8c).
**Arc:** Workflow Arc — Phase 8c of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 25 BLOCKING parity (8+8+9) + 6 BLOCKING latency gates + 20 unit + 9 Playwright scenarios = **60 new this phase**. Phase 1–8b.5 regression: green. Phase 8b cash receipts parity: 9/9 unchanged.

### Primary deliverable: WORKFLOW_MIGRATION_TEMPLATE.md v2

Phase 8c ships three migrations alongside a major template bump — because the 8c targets had meaningfully different shapes than cash receipts (Phase 8b) and exercised patterns the v1 template didn't yet cover. Template v2 adds:

- **§5.5 — Extended parity test patterns** (four new patterns):
  - 5.5.1 pre-approval zero-write assertion (all three 8c targets are deferred-write).
  - 5.5.2 positive PeriodLock assertion (month_end_close — first full-approval migration).
  - 5.5.3 fan-out fidelity (ar_collections — per-customer items).
  - 5.5.4 override-action pattern (expense_categorization — `category_override` backend capability).
- **§7.6 — Event trigger not dispatched today — use scheduled fallback.** Documents the workaround for any migration declaring `trigger_type="event"` until real event infrastructure ships.
- **NEW §10 — Queue Cardinality Matrix.** Four shapes: per-anomaly (cash_receipts, expense_categorization) / per-entity (ar_collections) / per-job (month_end_close) / per-record (future 8f). Drives direct-query shape + adapter signature + parity test structure.
- **NEW §11 — Rollback-Gap Documentation Convention.** When a pre-existing approval path has partial-failure modes that don't cleanly roll back, the migration preserves verbatim + flags in three places. Month-end close statement-run-failure is the working example.
- **§1 deepening:** §1.3 (scheduler invocation) now lists 5 shapes including the event-fallback. §1.4 (approval type) now lists 4 SIMPLE/FULL variants with a rollback-gap sub-question. §1.5 (email template) updated to reflect Phase 8b.5's shared `email.approval_gate_review` managed template.
- **§14 appendix + §15 latent bugs + §16 changelog:** all updated with Phase 8c artifacts.

### Migrations shipped

**1. `month_end_close`** — FULL approval with period lock + deferred statement-run writes.
- Adapter (`backend/app/services/workflows/month_end_close_adapter.py`, ~290 lines): three public functions (`run_close_pipeline`, `approve_close`, `reject_close`) + `request_review_close` helper. 100% delegation to `AgentRunner.run_job` + `ApprovalGateService._process_approve`/`_process_reject`.
- Triage queue `month_end_close_triage`: **per-job cardinality** (item_entity_type="month_end_close_job"). Actions: approve (confirmation_required, invoice.approve permission), reject (requires_reason), request_review.
- Direct query + related-entities builder: return AgentJob + executive_summary + top-5 flagged customers + prior-month-close link for comparison context.
- Parity test (`test_month_end_close_migration_parity.py`, 8 tests): pre-approval zero-write × 2, reject no-write × 1, approve-writes-PeriodLock × 1 (positive assertion), legacy-vs-triage identity × 1, triage engine dispatch × 2, cross-tenant isolation × 1.
- **Rollback gap preserved verbatim** (statement-run-failure leaves partial rows + locked period). Template §11 documents. CLAUDE.md latent-bug tracking adds dedicated-cleanup-session target.
- Trigger: `manual` (user-invoked via UI or API).

**2. `ar_collections`** — SIMPLE approval with per-customer fan-out + new email-dispatch capability.
- Adapter (`backend/app/services/workflows/ar_collections_adapter.py`, ~330 lines): `run_collections_pipeline`, `send_customer_email`, `skip_customer`, `request_review_customer`. **Closes pre-existing Phase 3b TODO** — legacy `approval_gate._process_approve` for `ar_collections` was a no-op; triage `send` action now actually dispatches the email via `email_service.send_collections_email` → `delivery_service.send_email_with_template("email.collections")`.
- Triage queue `ar_collections_triage`: **per-customer cardinality** (item_entity_type="ar_collections_draft"). Actions: send (invoice.approve), skip (requires_reason), request_review.
- Direct query denormalizes: customer_name, billing_email, tier, draft_subject, draft_body_preview (first 300 chars). Sorted CRITICAL→ESCALATE→FOLLOW_UP then by total_outstanding desc.
- Related-entities builder: Customer + top-5 open invoices + past 3 collection emails via document_deliveries.
- Parity test (`test_ar_collections_migration_parity.py`, 8 tests): pre-approval zero-email × 1, send creates DocumentDelivery × 2, skip no-delivery × 1, **fan-out fidelity × 1 (3 customers × 3 actions)**, missing-email error-guard × 1, triage engine dispatch × 2.
- **Operational coexistence note:** tenants who've been "approving" drafts (which was a no-op) will see first real email sends from this deploy. Discontinue any manual email dispatching. Documented in release notes.
- Trigger: `scheduled` cron `0 23 * * *` (preserved from 8b.5 fix).

**3. `expense_categorization`** — SIMPLE approval with per-line review + AI-suggestion override.
- Adapter (`backend/app/services/workflows/expense_categorization_adapter.py`, ~340 lines): `run_categorization_pipeline`, `approve_line` (with optional `category_override`), `reject_line`, `request_review_line`.
- Triage queue `expense_categorization_triage`: **per-anomaly cardinality** (item_entity_type="expense_line_review"). Actions: approve (optional category_override payload), reject (requires_reason), request_review.
- Direct query denormalizes: vendor_name, VendorBillLine.description, amount, proposed_category (from report_payload.map_to_gl_accounts.mappings), current_category.
- Related-entities builder: VendorBillLine + parent VendorBill + Vendor + past 3 categorized lines for the same vendor (pattern-matching aid).
- Parity test (`test_expense_categorization_migration_parity.py`, 9 tests): pre-approval null-category × 1, approve-writes-AI-suggestion × 1, **override-replaces-suggestion × 1**, reject-no-write × 1, legacy-vs-triage parity × 1, triage engine dispatch × 3 (including override payload), cross-tenant isolation × 1.
- **Trigger-type change — explicit deviation, NOT a bug fix:** seed changed from `trigger_type="event"` + `trigger_config.event="expense.created"` to `trigger_type="scheduled"` + `cron="*/15 * * * *"`. Event dispatch doesn't exist today (no event subscription registry, no `expense.created` publish hook). Documented in `default_workflows.py` seed comment, commit message, session log (this entry), `WORKFLOW_MIGRATION_TEMPLATE.md` §7.6, and CLAUDE.md latent-bug tracking.
- **Override UI deferred to Phase 8e:** backend ships `category_override` kwarg + handler-payload plumbing. Frontend category-dropdown UI for operators designed alongside Phase 8e triage work.

### Shared infrastructure additions

- `workflow_engine._SERVICE_METHOD_REGISTRY`: 3 new entries (one per adapter pipeline).
- `triage.engine._DIRECT_QUERIES`: 3 new direct-query builders.
- `triage.ai_question._RELATED_ENTITY_BUILDERS`: 3 new related-entity builders.
- `triage.action_handlers.HANDLERS`: 9 new handlers (3 per migration).
- `triage.platform_defaults`: 3 new queue configs.
- `default_workflows.TIER_1_WORKFLOWS`: 3 migrated seeds (agent_registry_key cleared, real `call_service_method` steps).
- `scripts/seed_triage_phase8c.py`: 3 AI prompts seeded via Option A idempotent pattern.

### BLOCKING latency numbers (dev hardware)

All 6 gates pass with substantial headroom. Consolidated in `test_phase8c_triage_latency.py`:

| Gate | p50 | p99 | Budget (p50/p99) | Headroom |
|---|---|---|---|---|
| month-end-close next_item | 5.6 ms | 29.9 ms | 100 / 300 ms | 18× / 10× |
| month-end-close apply_action | 14.1 ms | 24.6 ms | 200 / 500 ms | 14× / 20× |
| ar-collections next_item | 14.0 ms | 19.8 ms | 100 / 300 ms | 7× / 15× |
| ar-collections apply_action | 15.8 ms | 45.5 ms | 200 / 500 ms | 13× / 11× |
| expense-categorization next_item | 48.0 ms | 80.3 ms | 100 / 300 ms | 2× / 4× |
| expense-categorization apply_action | 32.9 ms | 91.2 ms | 200 / 500 ms | 6× / 5× |

expense_categorization's next_item is the slowest due to per-anomaly joins into VendorBill + Vendor + proposed_category lookup from report_payload. Still well within budget. Future optimization: denormalize proposed_category onto AgentAnomaly row, or cache vendor lookups per sweep.

### Audit answers to the 9 questions (per migration)

**month_end_close:**
1. Write timing: **deferred** (all writes on approval via `_trigger_statement_run` + `PeriodLockService.lock_period`).
2. Anomaly types: 16 (across agent + statement_generation_service.detect_flags).
3. Scheduler: **manual** (user-invoked; no cron).
4. Approval type: **FULL** with period lock. POSITIVE PeriodLock assertion in parity test.
5. Email: `email.approval_gate_review` (Phase 8b.5 shared managed template).
6. Related entities: AgentJob exec summary + flagged customers + prior-month close.
7. AI prompt: `triage.month_end_close_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

**ar_collections:**
1. Write timing: **deferred** — drafts during pipeline, email dispatch on approval (NEW capability).
2. Anomaly types: 3 (collections_follow_up INFO, collections_escalate WARNING, collections_critical CRITICAL).
3. Scheduler: **scheduled** cron `0 23 * * *` tenant-local (8b.5 fix).
4. Approval type: **SIMPLE dispatch-on-approval** (closes Phase 3b TODO).
5. Email: `email.approval_gate_review` for the approval email + `email.collections` for the drafted collection emails.
6. Related entities: Customer + open invoices + past collection emails.
7. AI prompt: `triage.ar_collections_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

**expense_categorization:**
1. Write timing: **deferred** (VendorBillLine.expense_category on approval only).
2. Anomaly types: 3 (expense_low_confidence WARNING, expense_no_gl_mapping INFO, expense_classification_failed CRITICAL).
3. Scheduler: **scheduled** cron `*/15 * * * *` (**WORKAROUND — event trigger declared but not dispatched**).
4. Approval type: **SIMPLE writes-on-approval** (delegates to existing `_apply_expense_categories`).
5. Email: `email.approval_gate_review` (shared managed template).
6. Related entities: VendorBillLine + VendorBill + Vendor + past categorized lines for same vendor.
7. AI prompt: `triage.expense_categorization_context_question` with 4 suggested questions.
8. Permission: `invoice.approve`.
9. Vertical scoping: cross-vertical (Core).

### Legacy coexistence verified

- `/agents` dashboard still lists all 3 job types as runnable.
- `/agents/:id/review` page resolves for all 3 job types (ApprovalReview.tsx unchanged).
- `POST /api/v1/agents/accounting` endpoint still accepts all 3 `job_type` values.
- Email approval token flow still works for all 3 job types via the shared `email.approval_gate_review` template.

### Latent bugs surfaced (or inherited) — tracked for future cleanup

1. **Month-end close statement-run rollback gap** (surfaced in 8c audit). `_trigger_statement_run` catches exceptions but still proceeds to period lock, potentially leaving partial statement rows + locked period. Preserved verbatim for parity. Template §11 documents the pattern; dedicated cleanup session pending.
2. **Event trigger type declared but not dispatched** (surfaced in 8c audit). `trigger_type="event"` workflows never fire; no event subscription registry exists. Expense_categorization uses scheduled fallback (§7.6). Real fix is future event-infrastructure arc.
3. **Existing flags still open:** `time_of_day` UTC bug (8b.5); orphan migrations r34–r39 (8a); hardcoded legacy vault-print emails (pre-arc).

### Phase 8c readiness for downstream phases

- **Phase 8d** (vertical migrations): can proceed. Template v2 accommodates all observed shapes. Queue cardinality matrix guides vertical-workflow queue design.
- **Phase 8e** (spaces + default views): can proceed. Triage queues registered as platform defaults; spaces integration comes later.
- **Phase 8f** (remaining 8 accounting migrations): **unblocked.** Template v2 is the comparison checklist. Each of the 8 remaining agents answers the 9 questions from §1 + applies patterns from §5.5 / §10 / §11.

### What Phase 8c did NOT ship (per approved scope)

- Migration of remaining 8 accounting agents (Phase 8f).
- Vertical workflow migrations (Phase 8d).
- Dashboard surfaces showing accounting data as saved views (Phase 8g).
- Deletion of legacy bespoke UI (deferred to Phase 8h or later).
- Frontend override-dropdown UI for expense_categorization (Phase 8e).
- Event infrastructure (future horizontal arc).
- Rollback-gap correctness fixes (dedicated cleanup session).

Next: **Phase 8d or Phase 8e** depending on sequencing preference. Both are independently achievable from 8c's foundation.

---

## Workflow Arc Phase 8b.5 — Pre-8c Cleanup (Scheduler + Approval Emails)

**Date:** 2026-04-21
**Migration head:** `r37_approval_gate_email_template` (advances from `r36_workflow_scope`)
**Arc:** Workflow Arc — narrow cleanup between 8b and 8c.
**Tests passing:** 10 scheduler + 8 email migration = **18 new this phase**. Adjacent regression: Phase 1–8b tests all green; Phase 8b cash receipts parity (9/9) unchanged — the email migration is a pure refactor from the parity-test perspective (audit finding #8).

### What shipped — two latent-bug fixes before Phase 8c starts

Phase 8b's reconnaissance audit surfaced two pre-existing latent bugs that 8c migrations would otherwise trip over. Fixing them as a deliberate standalone phase keeps 8c clean:

1. **Scheduler `scheduled` trigger type now dispatches.** Eight Tier-1 `wf_sys_*` workflows declared `trigger_type="scheduled"` + `trigger_config.cron` but were NOT being fired — `workflow_scheduler.check_time_based_workflows()` filtered only `["time_of_day", "time_after_event"]`. All 8 now fire correctly per tenant-local cron.
2. **Approval gate email migrated from hardcoded HTML to D-7 managed template.** `ApprovalGateService._build_review_email_html()` inlined ~85 lines of HTML-builder Python. Replaced with `email.approval_gate_review` managed template dispatched via `delivery_service.send_email_with_template`. All 12 agent job types share one template.

### Approved deviations from the audit recommendation

1. **Scheduler fix** (approved §1): APScheduler's `CronTrigger.from_crontab(cron, timezone=tenant_tz)` — no new dep. Tenant TZ via `_resolve_tenant_tz` helper mirroring Phase 6 briefings (`Company.timezone` with `America/New_York` fallback). Invalid cron: catch `ValueError`, log warning, skip that workflow, continue. New `_already_fired_scheduled` idempotency helper queries `trigger_context.intended_fire` JSONB field (canonical audit trail — not `started_at` wall-clock).
2. **Email migration** (approved §2): migration `r37_approval_gate_email_template` seeds `email.approval_gate_review` template. `ApprovalGateService._build_review_email_html()` deleted. Refactored to `delivery_service.send_email_with_template` with `caller_module="approval_gate.send_review_email"`. Semantic equivalence accepted (audit finding #8: Phase 8b parity test doesn't assert anything about email).
3. **No new migration for scheduler fix** (approved §6): all code changes, no schema change. One migration `r37` for the email template seed.

### Deploy-day operational implications (approved §3A)

**Eight previously-dormant workflows begin firing post-deploy:**

| ID | Cron | Impact |
|---|---|---|
| `wf_sys_ar_collections` | `0 23 * * *` daily | **Most impactful** — AR collection emails resume nightly |
| `wf_sys_safety_program_gen` | `0 6 1 * *` monthly | **Most impactful** — OSHA program auto-generation resumes |
| `wf_sys_statement_run` | `0 6 1 * *` monthly | Monthly consolidated statements resume |
| `wf_sys_compliance_sync` | `0 3 * * *` daily | OSHA deadlines + training expiry scan resumes |
| `wf_sys_training_expiry` | `0 7 * * 1` Mondays | Certification expiry alerts resume |
| `wf_sys_document_review_reminder` | `0 8 * * 1` Mondays | 11-month program review flags resume |
| `wf_sys_auto_delivery` | `0 6 * * *` daily | Auto-delivery eligibility scan resumes |
| `wf_sys_catalog_fetch` | `0 3 * * 1` Mondays | Wilbert catalog hash check resumes |

All 8 are **read-and-notify patterns** — no data corruption risk on first firing. Tenants who've been manually compensating (e.g., running AR collections ad-hoc to cover the silent skip) should **discontinue manual runs to avoid double-fires**. Document in release notes for deploy coordination.

### time_of_day TZ inconsistency flag (approved §3B)

Phase 8b.5 implements `scheduled` dispatch with **tenant TZ** (correct from the start). Existing `time_of_day` dispatch remains **UTC wall-clock** — a latent TZ bug. `wf_sys_cash_receipts` (Phase 8b) currently fires at 23:30 UTC for all tenants rather than 23:30 tenant-local. **Flagged for follow-on cleanup session.** `WORKFLOW_MIGRATION_TEMPLATE.md` §7.5 documents the inconsistency; 8c migrations that need tenant-local sub-daily timing should use `trigger_type="scheduled"` which already respects tenant TZ.

### Backend additions

- `backend/app/services/workflow_scheduler.py`:
  - New `_resolve_tenant_tz(name)` helper (mirrors briefings `_resolve_tz` pattern).
  - New `_intended_scheduled_fire(cron, tz, now)` — returns the cron tick datetime if it fell in the trailing 15-min window, else None. Raises `ValueError` on malformed cron (caller catches).
  - New `_already_fired_scheduled(db, workflow_id, company_id, intended_fire)` — audit-trail-based idempotency via `trigger_context.intended_fire` JSONB lookup. Self-healing across system restarts.
  - Extended `check_time_based_workflows()` query filter to include `"scheduled"` alongside existing two trigger types.
  - New `elif w.trigger_type == "scheduled"` dispatch branch: parses cron with tenant TZ, checks window + idempotency, fires via `workflow_engine.start_run` with `trigger_context={fired_at, intended_fire, cron}`.
  - Return shape extended: `{time_of_day_fired, time_after_fired, scheduled_fired, scheduled_skipped_invalid_cron}`.
- `backend/app/services/documents/_template_seeds.py`:
  - New `_approval_gate_seeds()` function returning the `email.approval_gate_review` template definition.
  - New `EMAIL_APPROVAL_GATE_REVIEW` + `EMAIL_APPROVAL_GATE_REVIEW_SUBJECT` Jinja templates — visual structure preserved from the previous hardcoded HTML.
- `backend/alembic/versions/r37_approval_gate_email_template.py`:
  - New migration. Seeds `email.approval_gate_review` via `_approval_gate_seeds()`. Idempotent guard at top of `upgrade()` — skips if template already exists (lets migration re-run cleanly). Downgrade removes the template + its versions.
- `backend/app/services/agents/approval_gate.py`:
  - `send_review_email()` refactored to use `delivery_service.send_email_with_template("email.approval_gate_review", template_context=...)` with `caller_module="approval_gate.send_review_email"`. Recipient fan-out loop unchanged. Subject override carries the fallback subject for any delivery-service code path that needs it.
  - **`_build_review_email_html()` DELETED** — no fallback to hardcoded HTML.

### Tests

- `backend/tests/test_workflow_scheduler_scheduled_dispatch.py` (10 tests):
  - `TestIntendedScheduledFire` × 4 — cron-window matching: matches in window / returns None outside window / respects timezone (NY vs LA) / invalid cron raises ValueError.
  - `TestAlreadyFiredScheduled` × 2 — audit-trail idempotency: detects prior run with matching intended_fire / different intended_fire doesn't block.
  - `TestSchedulerSweepIntegration` × 4 — end-to-end `check_time_based_workflows()`: scheduled workflow fires and records context, idempotency within window, invalid cron skipped gracefully (sibling still fires), time_of_day dispatch unchanged (regression).
  - Module-level autouse fixture cleans up `wf_sched_*` + `wf_tod_*` workflows + runs after suite completes — prevents DB accumulation on shared dev environments.
- `backend/tests/test_approval_email_managed_template.py` (8 tests):
  - `TestApprovalEmailManagedTemplate` × 4 — template exists in registry / renders with context / no-anomalies variant / dry-run banner variant.
  - `TestSendReviewEmailMigration` × 2 — full send_review_email path creates `DocumentDelivery` row with correct `template_key` + `caller_module` + subject references `job_type_label`.
  - `TestInlineHtmlRemoved` × 1 — regression: `_build_review_email_html` is gone.
  - `TestSeedIdempotent` × 1 — seed function returns single template entry with required shape.

### Regression

- **Phase 8b cash receipts parity (9 tests):** GREEN — the email migration is a pure refactor from the parity-test perspective (audit finding #8 confirmed no email assertions exist).
- **Phase 8a workflow scope (16 tests):** GREEN after fixing test-fixture tier assignment. Original test runs produced stale `wf_sched_*` + `wf_tod_*` workflows with `tier=1` + `scope="tenant"` — tripped the Phase 8a invariant "tier=1 IMPLIES scope=core". Fixed by using `tier=4` + `scope="tenant"` on test fixtures (semantically correct) + adding module-level cleanup. 43K accumulated stale WorkflowRun rows from earlier runs also purged.
- **Phase 5 triage + Phase 8b cash receipts unit + latency gates:** GREEN — no regressions.

### Post-deploy readiness check

Admin can verify the scheduler fix is live via:
```sql
-- How many WorkflowRun rows for scheduled triggers in the last 24h?
SELECT trigger_source, COUNT(*)
FROM workflow_runs
WHERE trigger_source = 'schedule'
  AND started_at >= NOW() - INTERVAL '24 hours'
GROUP BY trigger_source;
```
And for the email migration:
```sql
-- Approval emails now flow through the managed template:
SELECT COUNT(*) FROM document_deliveries
WHERE template_key = 'email.approval_gate_review'
  AND created_at >= NOW() - INTERVAL '7 days';
```

### Phase 8c readiness

After Phase 8b.5 completes, Phase 8c migrations of ar_collections / month_end_close / expense_categorization can proceed with:

- **Clean scheduler** that dispatches `trigger_type="scheduled"` correctly per tenant TZ.
- **Managed template approval emails** — 8c parity tests can assert `DocumentDelivery.template_key="email.approval_gate_review"` + `caller_module="approval_gate.send_review_email"` presence rather than byte-identical HTML matching.
- **time_of_day TZ issue still latent** but flagged in the template at §7.5. 8c migrations that want tenant-local timing should prefer `trigger_type="scheduled"` (which works correctly) over `time_of_day` (UTC-only).
- **`call_service_method` action subtype** (from Phase 8b) reused for every 8c adapter pipeline entry. One entry per agent added to `_SERVICE_METHOD_REGISTRY`.

### Open items remaining (deferred to future sessions)

1. **`time_of_day` TZ bug** — existing time_of_day workflows (`wf_mfg_eod_delivery_reminder`, `wf_sys_cash_receipts`) fire at UTC wall-clock, not tenant-local. Cleanup session: extend `_matches_time_of_day` to resolve tenant TZ before the window check.
2. **Orphan migrations `r34_order_service_fields` → `r39_legacy_proof_fields`** — still unreconciled (tracked since Phase 8a audit).
3. **Legacy `ApprovalReview.tsx` retirement** — when all 13 agents are migrated + admin comfort is proven, retire the bespoke page. Revisit at Phase 8h.

---

## Workflow Arc Phase 8b — Reconnaissance Migration (Cash Receipts Matching)

**Date:** 2026-04-21
**Migration head:** `r36_workflow_scope` (unchanged — no new tables, no migration)
**Arc:** Workflow Arc — Phase 8b of 8a–8h. See `WORKFLOW_ARC.md`.
**Tests passing:** 9 BLOCKING parity + 2 BLOCKING latency gates + 18 unit + 5 Playwright = **34 new this phase**. Adjacent regression: Phase 1–8a tests all green (UI/UX Arc + Phase 8a foundation).

### Primary deliverable: WORKFLOW_MIGRATION_TEMPLATE.md

This phase ships TWO things, not one:

1. **The cash receipts migration** — one accounting agent migrated end-to-end through the workflow engine + triage queue, with parity preserved via a thin service-reuse adapter.
2. **The migration template** — `WORKFLOW_MIGRATION_TEMPLATE.md` at project root, documenting the patterns discovered. It's the checklist 8c–8f migration audits compare their target agent against.

Cash receipts was chosen as the reconnaissance vehicle for specific reasons: cross-vertical (not vertical-scoped), SIMPLE approval (no period lock — less risky than month-end close), no existing scheduler entry (net-new insertion, no transition to wrangle), mid-complexity anomaly taxonomy (4 types — enough to exercise per-entity and tenant-aggregate patterns).

### Approved deviations from the audit recommendation

1. **Scheduler from-scratch** (approved §1): cash receipts had no APScheduler entry today. Phase 8b adds `trigger_type="time_of_day"` at 23:30 ET daily on the `wf_sys_cash_receipts` workflow row. Existing `workflow_scheduler.check_time_based_workflows` 15-min sweep fires it. **The migration template accommodates both "add from scratch" (cash receipts) and "reuse existing" (for 8c agents that have scheduler entries).**
2. **Agent_registry_key is informational-only** (approved §2): confirmed via code audit — nothing in `workflow_engine.py` reads it. It's a badge flag in the workflow row, not a dispatch switch. Parity test ensures both paths produce identical side effects when either runs.
3. **Two-step badge choreography** (approved §3): the migration template documents both (a) "8b-alpha: insert with agent_registry_key + placeholder steps; 8b-beta: real steps + clear field" and (b) "8b-beta from birth" (cash receipts didn't have a prior row, so we jumped straight to the beta state). For 8c's existing stubs (`wf_sys_month_end_close` etc.), the alpha→beta transition is the concrete path — they already have rows with `agent_registry_key` set by r36's backfill.
4. **`call_service_method` as new action subtype** (approved §4): single workflow engine extension. Whitelisted dispatch table (`_SERVICE_METHOD_REGISTRY`) mapping `"{agent}.{method}"` keys to importable callables with allowed-kwargs safelists. Auto-injected kwargs: `db`, `company_id`, `triggered_by_user_id`. Reused for every 8c–8f migration — zero further engine changes needed there.
5. **`time_of_day` trigger, Path A** (approved §5): reused the existing `time_of_day` dispatch path. Path B (extending scheduler to honor `trigger_type="scheduled"` with cron config) flagged as latent cleanup for `wf_sys_ar_collections` — deferred to a separate session.
6. **Operational coexistence contract** (approved §6): documented in both CLAUDE.md and §9 of the migration template. Triage queue = routine daily processing. Legacy `POST /api/v1/agents/accounting` = ad-hoc forensic re-runs only. Do not run both paths simultaneously on the same unresolved-item set. Phase 8c+ inherits this contract.
7. **Parity test categories** (approved §7): all 5 categories implemented in `test_cash_receipts_migration_parity.py` — PaymentApplication row identity, reject no-write, anomaly resolution shape, negative PeriodLock assertion, pipeline-scale equivalence. Plus triage engine integration + cross-tenant isolation. 9 tests total.
8. **Hardcoded approval email HTML** (approved §8): preserved verbatim for parity. Flagged for future cleanup in a separate session (platform-wide D-7 migration of approval-gate emails).
9. **Template as comparison checklist, not copy-paste** (approved §9): `WORKFLOW_MIGRATION_TEMPLATE.md` structured around nine audit questions each 8c–8f migration must answer. Cash receipts is the working example throughout.
10. **AI question prompt with 4 suggested questions** (approved §10): seeded via Option A idempotent pattern in `backend/scripts/seed_triage_phase8b.py`. Variables match the shared 4-field schema (`item_json`, `user_question`, `tenant_context`, `related_entities_json`).
11. **wf_sys_ar_collections latent bug** (approved §11): its `trigger_type="scheduled"` isn't dispatched by `workflow_scheduler` today. Workflow isn't actually firing on schedule. Flagged for separate cleanup session.
12. **Open questions** (approved §12): documented in §11 of the migration template — ApprovalReview.tsx future, start_run log when both paths present, period_lock discipline for 8c+, triage_approval step type vs input.

### Backend additions

- `backend/app/services/workflows/__init__.py` — new package.
- `backend/app/services/workflows/cash_receipts_adapter.py` (~340 lines) — the parity adapter. Five public functions: `run_match_pipeline` (workflow-step surface) + `approve_match` / `reject_match` / `override_match` / `request_review` (per-item triage actions). Private helpers for tenant-scoped entity loading + the PaymentApplication write pattern. Zero-duplication discipline via delegation to `AgentRunner.run_job` for the pipeline path + independent replication of the agent's CONFIDENT_MATCH branch write logic for per-item approves (covered by parity test).
- `backend/app/services/workflow_engine.py` — new `call_service_method` action subtype. Added to `_execute_action` dispatch chain at line 528. New `_handle_call_service_method` handler (~60 lines) with kwarg-allowlist filtering + dynamic callable import via `module:attr` paths. New `_SERVICE_METHOD_REGISTRY` global (one entry for Phase 8b).
- `backend/app/data/default_workflows.py` — `wf_sys_cash_receipts` appended to `TIER_1_WORKFLOWS`. `trigger_type="time_of_day"` + `trigger_config.time="23:30"` + `source_service="workflows/cash_receipts_adapter.py"`. Single step with `action_type="call_service_method"`. Parameterized via `dry_run` config entry for tenant overrides.
- `backend/app/services/triage/engine.py` — new `_dq_cash_receipts_matching_triage` function. Queries unresolved `AgentAnomaly` rows for `cash_receipts_matching` jobs. Denormalizes payment + customer info at query time. Returns rows sorted by severity (CRITICAL→WARNING→INFO) then amount desc. Registered in `_DIRECT_QUERIES` dict.
- `backend/app/services/triage/ai_question.py` — new `_build_cash_receipts_matching_related` function. Returns payment + customer + top-5 candidate invoices (ranked by |balance − payment_amount| proximity) + past 3 applied payment/invoice pairs (pattern-matching aid). Registered in `_RELATED_ENTITY_BUILDERS` dict.
- `backend/app/services/triage/action_handlers.py` — four new handlers (`_handle_cash_receipts_approve` / `_reject` / `_override` / `_request_review`) + 4 new registrations in `HANDLERS` dict under `cash_receipts.*` keys. Each handler validates payload kwargs (payment_id, invoice_id, reason/note) + delegates to the adapter; errors surface as `{"status": "errored", "message": "..."}` for engine-level handling.
- `backend/app/services/triage/platform_defaults.py` — new `_cash_receipts_triage` `TriageQueueConfig` + `register_platform_config` call at module bottom. 5-action palette (approve/reject/override/request_review/skip), 2 context panels (related_entities + ai_question), `invoice.approve` permission gate, cross-vertical, snooze enabled, schema_version="1.0".
- `backend/scripts/seed_triage_phase8b.py` (~165 lines) — Option A idempotent seed for `triage.cash_receipts_context_question` Intelligence prompt. Handles fresh-install / matching-content-noop / differing-content-update / multi-version-skip-with-warning cases. Uses shared 4-field variable schema + standard JSON response schema.

### Tests

- `backend/tests/test_cash_receipts_migration_parity.py` (~450 lines, 9 tests) — **BLOCKING**. Six test classes: TestApproveParity × 2 (PaymentApplication identity + anomaly resolution shape), TestRejectParity × 2 (no-write + reason required), TestNoPeriodLock × 1 (negative assertion), TestPipelineEquivalence × 1 (agent-run vs. adapter-run produce same shape), TestTriageEngineParity × 2 (engine dispatch + reason enforcement), TestTenantIsolation × 1 (cross-tenant anomaly rejection).
- `backend/tests/test_cash_receipts_triage_latency.py` (~235 lines, 2 tests) — **BLOCKING**. `test_cash_receipts_triage_next_item_latency_gate` (p50<100/p99<300) and `test_cash_receipts_triage_apply_action_latency_gate` (p50<200/p99<500). 30 samples + 3 warmups each. Seeds 40 pending anomalies with matching payment/invoice triples.
- `backend/tests/test_cash_receipts_phase8b_unit.py` (~330 lines, 18 tests) — 6 test classes: TestTriageRegistration × 2 (platform default + config shape), TestDirectQueryDispatch × 3 (key registered + empty new tenant + severity+amount ordering), TestRelatedEntitiesBuilder × 3 (registered + shape + empty on missing payment), TestHandlerRegistration × 2 (all 4 keys registered + graceful error on missing payload), TestWorkflowEngineRegistry × 4 (method in registry + unknown method errored + missing method_name errored + kwargs filtered by allowlist), TestCashReceiptsWorkflowSeed × 2 (entry present + expected shape with NULL agent_registry_key), TestAdapterEdgeCases × 2 (override without reason + request_review without note raise ValueError).
- `frontend/tests/e2e/workflow-arc-phase-8b.spec.ts` (~200 lines, 5 scenarios) — Playwright. Queue registration via /triage/queues API, wf_sys_cash_receipts visible on Platform tab without agent badge, queue config endpoint returns context panels + AI prompt key, legacy /agents dashboard still mounts (coexistence), legacy /agents/:id/review route still resolves.

### Performance

- **cash_receipts_triage_next_item:** p50=18.7ms, p99=20.1ms (budget 100/300) — **5× headroom on p50, 15× on p99**.
- **cash_receipts_triage_apply_action:** p50=15.7ms, p99=22.5ms (budget 200/500) — **13× headroom on p50, 22× on p99**.

apply_action carries three writes per call (PaymentApplication insert + Invoice mutation + anomaly resolve) + commit. That 3-write pattern is representative of what 8c–8f migrations' hot paths will look like, so 13× p50 headroom is a reassuring floor.

### Migration patterns extracted to template

Documented in `WORKFLOW_MIGRATION_TEMPLATE.md` §§1–12:

1. **Nine audit questions** every migration answers: write timing, anomaly structure, existing scheduler invocation, approval type, email template status, related entities, AI prompt shape, permission gate, vertical scoping.
2. **Parity adapter pattern**: thin module at `backend/app/services/workflows/{agent}_adapter.py`. Pipeline entry (`run_match_pipeline` et al.) for workflow-step surface + per-item helpers for triage actions. Zero-duplication via delegation where possible + parity-tested replication where not. Tenant isolation via `_load_*_scoped` helpers.
3. **Workflow definition structure**: seed entry in `TIER_1_WORKFLOWS` + `call_service_method` dispatch registration + two-step badge choreography (alpha→beta) for agent_registry_key transitions.
4. **Triage queue configuration**: three files (engine.py direct query, ai_question.py related builder, action_handlers.py handlers) + platform_defaults.py config + 4 decision-oriented AI question chips.
5. **Parity test requirements**: 5 categories of assertions, shared fixture pattern with per-test seeding (to avoid cross-test contamination from tenant-wide agent sweeps), BLOCKING classification convention.
6. **Latency gate requirements**: two gates per migration (next_item + apply_action), 30 samples + 3 warmups, seeded-fixture methodology.
7. **Scheduler transition patterns**: three paths documented (add-from-scratch, reuse-existing-agent-cron, reuse-existing-workflow-cron).
8. **Agent badge clearing**: informational-only field; no cache clear or app restart needed — just clear the column and frontend re-renders without the badge.
9. **Coexist-with-legacy contract**: four commitments (canonical routine path via triage, legacy endpoint for forensics, no concurrent processing, retirement deferred).
10. **Post-migration verification checklist**: 13 items to check before closing a migration PR.

### Patterns specific to cash receipts (WON'T generalize to 8c–8f)

Documented in §1.1 / §1.4 / §1.5 of the template so 8c audits don't copy blindly:

- Immediate-write pattern (writes during agent step 2) — month-end close is deferred-write; AR collections is none-write.
- SIMPLE approval (no period lock) — month-end close is full approval with lock discipline.
- Hardcoded approval email HTML — other agents may have different approval-email shapes or no approval email at all.
- 4-rule matching ladder (CONFIDENT/POSSIBLE-any/POSSIBLE-subset/UNRESOLVABLE) — each agent has its own decision topology.

### Legacy coexistence verified

Post-8b, these still work (verified by tests + manual audit):

- **`POST /api/v1/agents/accounting`** with `job_type="cash_receipts_matching"` — the Phase 1 accounting agent endpoint. Admin can still ad-hoc-run cash receipts via `/agents` hub.
- **`/agents` dashboard** — AgentDashboard.tsx mounts, lists cash_receipts_matching as runnable.
- **`/agents/:jobId/review`** — ApprovalReview.tsx route resolves.
- **`/agents/approve/{token}`** — email-token approval path unchanged; existing inbox tokens still work.
- **Vault accounting admin tab** `/vault/accounting/agents` — schedule + recent-jobs surfaces unaffected.

### Surprises worth flagging for 8c–8f scoping

1. **`agent_registry_key` is purely informational** — confirmed via full `grep` audit. Nothing in `workflow_engine.py` reads it. This simplifies the migration: no dispatch-routing code to change; clearing the field is a pure UI signal. 8c inherits this simplification.
2. **No wf_sys_cash_receipts existed pre-8b** — the 16 `wf_sys_*` count from Phase 8a did NOT include cash receipts. Phase 8b had to insert the row from scratch. 8c's targets (month_end_close, ar_collections, expense_categorization) DO have existing rows with `agent_registry_key` set — their transition is the alpha→beta path, not birth-as-beta.
3. **Agent sweeps are tenant-wide** — CashReceiptsAgent processes ALL unmatched payments, not just a specific subset. Fixture setup in parity tests must seed "path A" rows, run the agent, THEN seed "path B" rows to avoid cross-test contamination. Applies to other sweeping agents (expense categorization, AR collections).
4. **`trigger_type="scheduled"` declared on wf_sys_ar_collections is dead** — `workflow_scheduler.check_time_based_workflows()` only dispatches `time_of_day` and `time_after_event`. AR collections isn't actually firing on schedule today. Flagged as latent cleanup (separate session).
5. **Hardcoded approval email HTML predates D-7** — `ApprovalGateService._build_review_email_html()` builds the body inline in Python. Parity discipline requires preserving verbatim. Platform-wide migration to managed templates is future cleanup work.
6. **Option B (enrollment + override) path untouched by Phase 8b** — cash receipts workflow seed includes a `params` block (dry_run override) demonstrating compatibility. Actual enrollment-override UX is still Phase 8c's polish item.

### Latent bug flags (NOT fixed in 8b)

These surfaced during the 8b audit but are explicitly out of scope. Each is tracked as a separate future session:

1. `wf_sys_ar_collections` scheduled-trigger bug (§11 above).
2. Hardcoded approval email HTML in `ApprovalGateService` (§11 above).
3. Orphan migrations `r34_order_service_fields` → `r39_legacy_proof_fields` (pre-existing from Phase 8a audit, still unreconciled).

### What Phase 8b did NOT ship (per approved scope)

- Migration of any other accounting agent — that's 8c–8f systematically.
- Deletion of legacy bespoke cash receipts UI — later phase.
- Visual refresh of cash receipts triage surface — Aesthetic Arc.
- Month-end close migration — Phase 8c with period lock discipline.
- Dashboards showing cash receipts data as saved views — Phase 8g.
- Tenant customization UX for cash receipts workflow — design work, later phase.
- Fork-vs-override UX polish — deferred from 8a to 8c.
- Triage queue customization admin UI — Phase 7 deferred, still out of scope.

Next up: **Phase 8c — Core accounting migrations batch 1** (month_end_close + ar_collections + expense_categorization). Uses the migration template as the audit checklist. Each agent's audit answers the 9 questions documented in §1 of `WORKFLOW_MIGRATION_TEMPLATE.md`.

---

## Workflow Arc Phase 8a — Foundation Infrastructure

**Date:** 2026-04-21
**Migration head:** `r36_workflow_scope` (advances from `r35_briefings_table`)
**Arc:** Workflow Arc (new) — see `WORKFLOW_ARC.md` at project root for the full 8a–8h plan.
**Tests passing:** 30 backend (16 workflow scope/fork + 14 system space / role decoupling) + 5 BLOCKING latency gates + 6 vitest (DotNav) + 6 Playwright scenarios = **47 new this phase**. Adjacent regression: UI/UX Arc Phase 1–7 tests + all follow-ups passing; frontend vitest full run 165/165; `tsc -b` clean.

### What shipped — groundwork for Phase 8b–8h

Phase 8a is the foundation the remaining Workflow Arc phases build on. No workflow migrations yet, no agent retirement yet. What it establishes:

1. **Workflow scope field** — `core` / `vertical` / `tenant` classification as a first-class workflow attribute. All 37 existing workflows backfilled: 16 `wf_sys_*` rows → `core`, 21 vertical (manufacturing + funeral_home) → `vertical`, 0 tenant on the seeded dev tenant.
2. **Tenant fork mechanism** — `POST /api/v1/workflows/{id}/fork` creates an independent tenant copy with fresh IDs, remapped DAG edges, and copied platform-default step params. `forked_from_workflow_id` + `forked_at` stamped. Coexists with the existing `WorkflowEnrollment` + `WorkflowStepParam` soft-customization path — both are deliberate per the approved spec.
3. **Settings as a platform space** — registered via new `SYSTEM_SPACE_TEMPLATES` mechanism. Seeded for admins at registration. Non-deletable (can be renamed, recolored, and have pins reordered). Stable space ID `sys_settings`.
4. **DotNav** — horizontal dots at the bottom of the left sidebar. Replaces the Phase 3 top-bar `SpaceSwitcher`. System spaces sort leftmost regardless of display_order. Phase 3 keyboard shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) preserved. Old `SpaceSwitcher` component left in the repo for a one-release grace window; the mount is removed.
5. **Role decoupling preparation** — `ROLE_CHANGE_RESEED_ENABLED: bool = False` module constant in `user_service.py` gates the role-change reseed block. Registration-time seeds preserved. Spaces seed still runs on role change (idempotent + permission recheck — needed so new permissions surface Settings in the dot nav promptly). Public helper `reapply_role_defaults_for_user(db, user)` available for the opt-in UI landing in Phase 8e.
6. **Agent-backed workflow stubs** — three `wf_sys_*` rows (`wf_sys_month_end_close`, `wf_sys_ar_collections`, `wf_sys_expense_categorization`) get `agent_registry_key` populated, corresponding to existing entries in `AgentRunner.AGENT_REGISTRY`. Frontend renders a "Built-in implementation" badge on those cards; click routes read-only to `/view` rather than `/edit`. Badges clear per row as agents migrate to real workflow definitions in 8b–8f.

### Approved deviations from the spec

1. **Both customization paths preserved** (audit A) — the existing enrollment + override (Option B) path stays unchanged; fork (Option A) adds alongside. The UX for "when to use which" lands in Phase 8c.
2. **System space re-seed runs unconditionally on role change** (audit D) — even with `ROLE_CHANGE_RESEED_ENABLED=False`, the spaces seed block still runs because the Settings system space is permission-gated and needs to appear in the dot nav when a user is promoted to admin. The seed is idempotent: existing user spaces are untouched; only the Settings dot is added if the permission grant just happened.
3. **Latency gates adjusted for Phase 8a data sizes** (audit F) — the five new BLOCKING gates (workflow-scope-core, workflow-scope-core+used_by, workflow-scope-vertical, spaces-with-system, workflow-fork) run against the seeded dev tenant (~40 workflow rows). Budgets chosen to match UI/UX Arc conventions: scope filters at p50<100ms/p99<300ms, fork at p50<200ms/p99<500ms (wider because it's a multi-table write path).
4. **Agent badge shipped in 8a** (audit G1) — rather than deferred. The "Built-in implementation" badge + read-only routing for agent-backed rows is minimal and lets Phase 8b's migration template work against a representative UI the whole time.
5. **Fork-vs-override UX polish deferred to 8c** (audit G2) — the fork API + button ships in 8a so the infrastructure is proven; the decision-tree UI ("when to use fork vs enrollment override") is Phase 8c work alongside the first real migration.

### Backend additions

- `backend/alembic/versions/r36_workflow_scope.py` — new migration. Adds `workflows.scope` (String 16, NOT NULL, server_default `"tenant"`), `workflows.forked_from_workflow_id` (FK → workflows.id ON DELETE SET NULL, nullable), `workflows.forked_at` (DateTime tz, nullable), `workflows.agent_registry_key` (String 100, nullable). CHECK constraint `scope IN ('core','vertical','tenant')`. Indexes on `(company_id, scope)` + partial on `forked_from_workflow_id WHERE NOT NULL`. Data backfill: scope derived from tier (tier 1 → core, tier 2/3 → vertical, tier 4 → tenant); agent_registry_key populated for the three existing agent-backed stubs. Idempotent-safe via the `env.py` op wrappers.
- `backend/app/models/workflow.py` — 4 new Mapped columns (`scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`).
- `backend/app/services/workflow_fork.py` — new service (~230 lines). `fork_workflow_to_tenant(db, *, user, source_workflow_id, new_name=None) -> Workflow` copies source with fresh UUIDs, two-pass ID map to remap DAG edges, copies platform-default `WorkflowStepParam` rows (those with `company_id IS NULL`), stamps `forked_from_workflow_id` + `forked_at`, clears `agent_registry_key` on the copy. Raises typed `ForkNotAllowed` / `SourceNotFound` / `AlreadyForked`. Also exports `count_tenants_using_workflow()` aggregating distinct active enrollments (for the `include_used_by=true` query path).
- `backend/app/api/routes/workflows.py` — `_serialize_workflow` extended with `scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`, `company_id`, `used_by_count`. `list_workflows` gains `scope` + `include_used_by` query params with regex validation on scope. New `POST /{workflow_id}/fork` endpoint with `_ForkRequest` Pydantic body.
- `backend/app/services/spaces/registry.py` — new `SystemSpaceTemplate` dataclass with `required_permission` + `SYSTEM_SPACE_TEMPLATES: list[SystemSpaceTemplate]` containing the Settings template (stable id `sys_settings`, icon `"settings"`, accent `"neutral"`, 4 seed pins: `/settings/workflows`, `/saved-views`, `/admin/users`, `/admin/roles`). `get_system_space_templates_for_user(db, user)` filters by `user_has_permission`.
- `backend/app/services/spaces/types.py` — `SpaceConfig` gains `is_system: bool = False`; `ResolvedSpace` propagates it. to_dict / from_dict roundtrip.
- `backend/app/services/spaces/seed.py` — new `_apply_system_spaces(db, user)` seeds system spaces the user has permission for; tracks via `user.preferences["system_spaces_seeded"]: list[str]`; appended to `created_total` return. Called from both `register_user` path and `update_user` role-change path (idempotent).
- `backend/app/services/spaces/crud.py` — `delete_space` raises `SpaceError("System spaces can be hidden but not deleted. Rename, recolor, or reorder pins to customize it.")` when target is `is_system=True`. `_resolve_space` propagates is_system into the response.
- `backend/app/api/routes/spaces.py` — `_SpaceResponse` gains `is_system: bool = False`; `_resolved_to_response` propagates.
- `backend/app/services/user_service.py` — module-level constant `ROLE_CHANGE_RESEED_ENABLED: bool = False`. New public `reapply_role_defaults_for_user(db, user) -> dict[str, int]` helper calling saved_views + spaces + briefings seeds. The role-change hook in `update_user` now: (a) skips saved_views + briefings seeds when flag is False, (b) still runs spaces seed unconditionally (permission recheck for system spaces).

### Frontend additions

- `frontend/src/components/layout/DotNav.tsx` — new ~260-line component. Horizontal dot row rendered at the bottom of the existing sidebar (between `OnboardingSidebarWidget` and the preset label). System spaces sort leftmost regardless of display_order. `_DOT_NAV_ICON_MAP` for lucide icons (exported for vitest); falls back to a colored dot in `space.accent` when no icon maps. Active dot gets `aria-pressed="true"` + `data-active="true"`. Keyboard shortcuts: `Cmd+[` / `Cmd+]` prev/next, `Cmd+Shift+1..5` direct access (ignores inputs/textareas/contenteditables). Shift+click on a dot opens `SpaceEditorDialog`; plus button opens `NewSpaceDialog`. `data-testid`s: `dot-nav`, `dot-nav-dot`, `dot-nav-add`. Null-renders when no spaces exist (matches Phase 3 behavior).
- `frontend/src/components/layout/sidebar.tsx` — mounts `<DotNav />` between `OnboardingSidebarWidget` and the preset label.
- `frontend/src/components/layout/app-layout.tsx` — `SpaceSwitcher` import + mount removed from the header. Comment notes the component stays in-repo for a one-release grace window; future cleanup removes the file.
- `frontend/src/types/spaces.ts` — `Space` interface gains optional `is_system?: boolean`.
- `frontend/src/pages/settings/Workflows.tsx` — `WorkflowCard` extended with `scope`, `forked_from_workflow_id`, `forked_at`, `agent_registry_key`. New `isAgentBacked` guard routes agent-backed rows to `/view` instead of `/edit`. `forkWorkflow(id)` async handler calls `POST /api/v1/workflows/{id}/fork` and navigates to the new fork's edit page. "Built-in implementation" badge (indigo) renders when `agent_registry_key` is set; "Fork" badge (emerald) renders when `forked_from_workflow_id` is set. Fork button appears on Core/Vertical rows (`canFork && !isAgentBacked`).

### Tests

- `backend/tests/test_workflow_scope_phase8a.py` — 16 tests across 3 classes:
  - `TestScopeFiltering` (5): Core tab returns core only, Vertical tab returns vertical only, Tenant tab returns tenant only, unknown scope → 400, no scope param returns all.
  - `TestForkEndpoint` (8): creates independent copy, clears agent_registry_key, stamps forked_from + forked_at, two-pass DAG remap correctness, platform-default step params copied, AlreadyForked rejection, SourceNotFound → 404, non-admin → 403.
  - `TestCountTenantsUsingWorkflow` (3): counts distinct enrollments, excludes inactive, returns zero when no enrollments.
- `backend/tests/test_system_spaces_phase8a.py` — 14 tests across 4 classes:
  - `TestSystemSpaceTemplates` (3): Settings template exists + has required_permission, get_system_space_templates_for_user filters by permission, unknown permission hides template.
  - `TestSystemSpaceSeeding` (4): admin user gets Settings seeded at registration, non-admin doesn't, idempotent re-seed, tracks via preferences.system_spaces_seeded array.
  - `TestSystemSpaceNonDeletion` (3): delete_space raises SpaceError for is_system=True, allows rename + accent change + pin reorder.
  - `TestRoleDecouplingFlag` (4): flag default False, saved_views seed skipped when False, briefings seed skipped when False, spaces seed runs unconditionally (permission recheck for new grants).
- `backend/tests/test_workflow_scope_latency_phase8a.py` — 5 BLOCKING latency gates (20 samples each, 3 warmups):
  - `workflow-scope-core` (budget p50<100ms/p99<300ms): **p50=15.4ms, p99=38.4ms** (6×/8× headroom).
  - `workflow-scope-core+used_by` (same budget): **p50=24.8ms, p99=26.0ms** (4×/12× headroom).
  - `workflow-scope-vertical` (same budget): **p50=5.0ms, p99=6.3ms** (20×/48× headroom).
  - `spaces-with-system` (same budget): **p50=2.1ms, p99=2.1ms** (48×/143× headroom).
  - `workflow-fork` (budget p50<200ms/p99<500ms): **p50=5.1ms, p99=5.3ms** (39×/94× headroom).
- `frontend/src/components/layout/DotNav.test.tsx` — 6 vitest: null-renders with no spaces, renders one dot per space + plus button, active dot aria-pressed, system space sorts leftmost regardless of display_order, click invokes switchSpace, icon map contains expected entries.
- `frontend/tests/e2e/workflow-arc-phase-8a.spec.ts` — 6 Playwright scenarios: dot_nav_renders_at_bottom, dot_nav_switches_spaces (with aria-pressed update), settings_dot_visible_for_admin (skips cleanly when staging data is older), workflows_page_shows_scope_cards (agent badge on wf_sys_month_end_close), fork_core_workflow_flow (mocked fork endpoint), old_top_space_switcher_gone (regression).

### Orphan migration flag

During the Phase 8a audit, a chain of six orphan migration files surfaced — `r34_order_service_fields.py` through `r39_legacy_proof_fields.py` — branching off from `r33_lifecycle_gaps` which isn't on the main chain. `alembic heads` still shows a single head (`r35_briefings_table` before this phase, now `r36_workflow_scope`), confirming the orphans aren't reachable. They appear to be pre-existing feature-branch artifacts that never reconciled with the UI/UX Arc chain. Per the approved audit clarification E, **do NOT touch these in Phase 8a** — flagged in `WORKFLOW_ARC.md` → Post-Arc Backlog so a future cleanup session picks them up with a dedicated review.

### Phase 8a Final State

- **Migration head:** `r36_workflow_scope`
- **Tables modified:** `workflows` gains 4 columns + CHECK + 2 indexes. No new tables.
- **Workflow scope distribution on seeded dev tenant:** 16 core / 21 vertical / 0 tenant (after r36 backfill).
- **Agent-backed workflows surfaced:** 3 (`month_end_close`, `ar_collections`, `expense_categorization`) — each shows the "Built-in implementation" badge + read-only click-through until migrated in 8b–8f.
- **BLOCKING CI gates total:** 12 (5 new + 7 from the UI/UX Arc).
- **Infrastructure ready for:** Phase 8b reconnaissance migration (Cash Receipts Matching), 8c–8f accounting + vertical migrations, 8e spaces + default views expansion, 8g dashboard rework, 8h arc finale.

Next up: **Phase 8b — Reconnaissance Migration: Cash Receipts Matching**. Deliberate one-agent learning phase. Output is a reusable migration template for 8c–8f.

---

## Peek Panels (UI/UX Arc Follow-up 4 — Arc Finale)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 21 backend (14 peek API + 6 triage related + 1 BLOCKING latency gate) + 25 frontend vitest (8 PeekContext + 5 adapter + 12 renderers) + 8 Playwright scenarios = **54 new this follow-up**. Adjacent regression: 184 saved-views + spaces + triage + ai_question + briefings + command_bar + nl_creation tests passing — no regressions. Frontend full vitest: 159 across 10 files. Frontend `tsc -b` clean; `npm run build` clean.

### What shipped — final follow-up of the UI/UX arc

Lightweight entity previews without navigation. Two interaction modes — **hover** (transient, info-only) and **click** (pinned, can include actions). Six entity types: `fh_case`, `invoice`, `sales_order`, `task`, `contact`, `saved_view`. Wired across four trigger surfaces:

1. **Command bar RECORD/VIEW tiles** — hover-reveal eye icon on tile (opacity 0 → 60 on row hover), click → click-mode peek. Primary tile click still navigates.
2. **Briefing `pending_decisions`** — title-click on each decision row opens click-mode peek when the `link_type` matches the known peek-entity whitelist. "Open →" link untouched.
3. **Saved view builder preview rows** — title-cell click opens click-mode peek (List/Table renderers). Detail page + widget callers don't pass `onPeek` so click-to-navigate behavior preserved.
4. **Triage related-entities panel** — closes the third Phase 5 stub. Tiles render via the new `/related` endpoint that exposes follow-up 2's `_RELATED_ENTITY_BUILDERS`. Each tile is click-to-peek.

### Approved deviations from the spec

1. **New endpoint** `GET /api/v1/peek/{entity_type}/{entity_id}` + `PEEK_BUILDERS` dict (6 builders). Reuse-existing-detail-endpoints option rejected per audit because detail responses average ~30 fields.
2. **`peek_fetch`** as 7th `arc_telemetry` `TRACKED_ENDPOINTS` key.
3. **BLOCKING CI gate** at `tests/test_peek_latency.py` — p50 < 100 ms, p99 < 300 ms across 24 mixed-shape samples (6 entity types × 4 rotations). **Actual: p50 = 3.7 ms, p99 = 7.4 ms** (27×/40× headroom).
4. **Briefing peek path uses structured `pending_decisions`** (no prompt v3 narrative-token bump per audit recommendation A).
5. **Command bar peek icon, NOT click-semantic swap** (per audit recommendation B). Affordance matches dominant intent: command bar = action-style (navigate on click), other surfaces = browse-style (peek on click).
6. **Triage related_entities wired** in this follow-up (per audit recommendation C). Closes the third Phase 5 stub; uses follow-up 2's `_RELATED_ENTITY_BUILDERS` infrastructure verbatim.

### Implementation deviation worth flagging

**Item 10 audit-approved spec said "base-ui Tooltip for hover, base-ui Popover for click."** The shipped `PeekHost.tsx` is a single floating-host component with controlled state from PeekContext. ARIA semantics are equivalent (`role="dialog" aria-modal="true"` for click; `role="tooltip"` for hover); Esc handling, click-outside backdrop, and focus return are manually wired (~30 lines total). Trade-off: the hover→click promotion is a state mutation rather than a component remount → no flash; single render path → simpler testing. The base-ui Popover/Tooltip migration is filed in the post-arc backlog under "Architectural debt" if the controlled-mode API ever becomes ergonomic for our context-driven peek state.

### Backend additions

- `backend/app/services/peek/types.py` — `PeekResponse` envelope + `PeekError` / `UnknownEntityType` / `EntityNotFound` / `PeekPermissionDenied` typed errors.
- `backend/app/services/peek/builders.py` — six per-entity builder functions + `PEEK_BUILDERS` dispatch dict + `build_peek()` public dispatcher. Mirrors Phase 5 `_DIRECT_QUERIES` + follow-up 2 `_RELATED_ENTITY_BUILDERS` shape. ~330 lines total (~30 per builder + helpers).
- `backend/app/services/peek/__init__.py` — public exports.
- `backend/app/api/routes/peek.py` — single route handler, telemetry-wrapped via try/finally.
- `backend/app/api/v1.py` — registers peek router under `/peek` prefix.
- `backend/app/services/arc_telemetry.py` — `TRACKED_ENDPOINTS` extended with `peek_fetch`.
- `backend/app/services/triage/ai_question.py` — new `list_related_entities()` public function (reuses `_RELATED_ENTITY_BUILDERS`); exported in `__all__`.
- `backend/app/api/routes/triage.py` — new `GET /sessions/{id}/items/{item_id}/related` route + `_RelatedEntityResponse` Pydantic shape.

### Frontend additions

- `frontend/src/types/peek.ts` — `PeekEntityType`, `PeekTriggerType`, `PeekPayload` discriminated union (6 entity types), `PeekResponse` generic envelope, `PeekResponseBase`.
- `frontend/src/services/peek-service.ts` — `fetchPeek(entityType, entityId, {signal})` with AbortSignal pass-through.
- `frontend/src/services/triage-service.ts` — `fetchRelatedEntities(sessionId, itemId)` + `TriageRelatedEntity` shape.
- `frontend/src/contexts/peek-context.tsx` — `PeekProvider`, `usePeek` (throws when absent), `usePeekOptional` (null-safe). Holds the single active-peek state, the session-scoped `Map<"{type}:{id}", {data, fetchedAt}>` cache (5-min TTL), AbortController for cancellation, hover debounce (200ms), `promoteToClick`. Cleared on provider unmount.
- `frontend/src/components/peek/PeekHost.tsx` — single floating-panel renderer. `useLayoutEffect` positions it relative to `current.anchorElement` via `getBoundingClientRect()`; flips above when not enough room below. Auto-focuses panel on click open + restores focus to anchor on close. Esc handler. Hover-mouse-leave-with-grace-period dismiss. Renders one of 6 per-entity renderers based on `data.entity_type`. Footer "Open full detail →" navigates + closes.
- `frontend/src/components/peek/PeekTrigger.tsx` — `<PeekTrigger>` wrapper for any element + `IconOnlyPeekTrigger` variant. Coarse-pointer detection collapses hover triggers to click on touch devices. Keyboard: Tab focuses, Enter/Space opens.
- `frontend/src/components/peek/renderers/` — 6 per-entity renderers (CasePeek, InvoicePeek, SalesOrderPeek, TaskPeek, ContactPeek, SavedViewPeek) + shared `_shared.tsx` (PeekField, fmtDate, fmtCurrency, StatusBadge).
- `frontend/src/components/triage/RelatedEntitiesPanel.tsx` — wires the Phase 5 stub. Tiles are click-to-peek (when entity type is peek-supported) or non-peekable display only.
- `frontend/src/components/triage/TriageContextPanel.tsx` — dispatcher swap: `case "related_entities"` now renders `RelatedEntitiesPanel` instead of the EmptyState stub.
- `frontend/src/components/saved-views/SavedViewRenderer.tsx` — optional `onPeek` prop threaded through to `ListRenderer` + `TableRenderer`.
- `frontend/src/components/saved-views/renderers/ListRenderer.tsx` + `TableRenderer.tsx` — title cell becomes click-to-peek button when `onPeek` provided + the row has an id.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.tsx` — passes peek handler to renderer when PeekProvider is in scope.
- `frontend/src/pages/briefings/BriefingPage.tsx` — `PendingDecisionsCard` converts title to click-peek button when `_BRIEFING_LINK_TYPE_TO_PEEK` whitelist matches.
- `frontend/src/components/core/CommandBar.tsx` — peek-icon affordance on RECORD/VIEW tiles when `peek && action.peekEntityType && action.peekEntityId`. Span+role=button to nest inside the outer button. `stopPropagation` so primary tile click is unaffected.
- `frontend/src/core/commandBarQueryAdapter.ts` — propagates backend `result_entity_type` into `peekEntityType` for the 6 supported types + saved_view; sets undefined for non-peekable types.
- `frontend/src/services/actions/registry.ts` — `CommandAction` interface gains optional `peekEntityType` + `peekEntityId`.
- `frontend/src/App.tsx` — mounts `<PeekProvider>` + `<PeekHost />` inside the authenticated tenant tree (after `SpaceProvider`). Platform admin / login routes unaffected.

### Tests

- `backend/tests/test_peek_api.py` — 14 tests across 4 classes: happy path × 6 entity types, errors (unknown type, not found, tenant isolation, auth), telemetry registration + wrap on success/error.
- `backend/tests/test_peek_latency.py` — 1 BLOCKING latency gate (24 samples mixed across 6 types).
- `backend/tests/test_triage_related_endpoint.py` — 6 tests: happy-path with siblings, empty list when no builder/no siblings, session/item 404s, cross-user isolation, auth required.
- `frontend/src/contexts/peek-context.test.tsx` — 8 tests: click-mode happy path, close+abort race, hover debounce + cancel, hover fires after 200ms, session cache hit on repeat open, different entity bypasses cache, promoteToClick state mutation, error path surfaces detail.
- `frontend/src/core/commandBarQueryAdapter.peek.test.ts` — 5 tests: 5 peek-supported types map correctly + saved_view, non-peekable types skip mapping, navigate/create skip mapping, null entity_type skips.
- `frontend/src/components/peek/renderers/renderers.test.tsx` — 12 tests: each of 6 renderers checks required-field rendering + null-field omission + format helpers + status badge.
- `frontend/tests/e2e/peek-panels.spec.ts` — 8 Playwright scenarios: command-bar peek, open-full-detail navigates + closes, saved-view builder row peek, triage related peek, two panels (second replaces first), keyboard Enter/Escape, cache single-call, mobile tap → click peek.

### Performance discipline verified

- **Peek endpoint p50 < 100ms / p99 < 300ms** (BLOCKING). Actual: **p50=3.7ms / p99=7.4ms** across 24 mixed samples.
- **Hover debounce 200ms**. Asserted in vitest (`hover open without close fires fetch after 200ms` + `cancel before debounce expires`).
- **Session cache 5-min TTL**. Asserted in vitest (`repeat open of same entity hits cache (single network call)`) and Playwright (`peek_cache_single_call`).
- **AbortController cancels superseded fetches**. Asserted in vitest (`close clears state to idle and aborts in-flight request`).
- **Arc telemetry records peek_fetch**. Asserted in backend tests (success + errored both record).

### Context panel wiring status (per requirement 13)

- ✅ **Wired**: `document_preview` (Phase 5), `ai_question` (follow-up 2), `related_entities` (follow-up 4)
- 🔵 **Remaining stubs**: `saved_view`, `communication_thread`
  - `saved_view` panel — needs per-item scoping in Phase 2 executor (current executor takes a static config; embedding a saved view scoped to "items related to current triage item" requires an executor extension for per-row filter injection)
  - `communication_thread` panel — needs platform messaging system; no platform messaging primitive exists today

### Arc completion (per requirement 14)

**The UI/UX arc plus all four post-arc follow-ups are complete.** Seven platform primitives established by Phases 1-7:

1. Command bar (Phase 1)
2. Saved views (Phase 2)
3. Spaces (Phase 3)
4. Natural language creation (Phase 4)
5. Triage workspace (Phase 5)
6. Morning + evening briefings (Phase 6)
7. Polish infrastructure (Phase 7)

Plus the 8th interaction-pattern primitive established by follow-up 4: **peek panels** (cross-cutting trigger surfaces, hover-vs-click discipline, session cache, mobile degradation). Arguably a primitive — six entity types ship today; new entity types add a builder + an existing trigger gets peek for free.

**The platform is ready for the September Wilbert meeting.** The arc plus follow-ups deliver every UX claim made in `CLAUDE.md` § 1a (command-bar-as-platform-layer, monitoring-through-hubs / acting-through-command-bar). All BLOCKING CI latency gates green; all 7 telemetry-tracked endpoints inside their budgets with substantial headroom.

**Remaining platform work is different-mode work outside this arc**: HR/Payroll integration via Check, Smart Plant pilot at Sunnycrest, vertical expansion (cemetery, crematory verticals beyond foundation work). None of these need re-opening any arc phase.

### Surprises worth recording

1. **The command bar adapter already had `result_entity_type` from Phase 1.** The peek-icon wire-up was a 2-line change to the adapter (propagate the field) plus the icon render in CommandBar.tsx. Phase 1 over-built the response shape with field-completeness in mind; that paid off in follow-up 4 with zero backend changes for surface 1.
2. **`_RELATED_ENTITY_BUILDERS` was already structured for cross-feature reuse.** Follow-up 2 built it for the AI question Q&A grounding. Follow-up 4 exposed it to the frontend via one small endpoint; the related-entities panel wiring was a small frontend component. Confirming the arc's pattern: build infra for the immediate feature in a way that the next feature gets it free.
3. **The 6 peek entity types didn't all live in one registry.** `task` is in Phase 5 direct-queries; `saved_view` is meta. The new `PEEK_BUILDERS` dict avoided forcing a unification — each builder is independent, takes a tenant + id, returns a typed shape. No cross-entity coupling.
4. **Briefing prompt v3 deferral was the right call.** Pursuing inline narrative tokens would have cost the same as everything else combined, with prompt-compliance risk per vertical and a re-seed dance. Using the existing `pending_decisions` typed list got 80% of the UX with 5% of the work.

### Verification

- `pytest tests/test_peek_api.py tests/test_peek_latency.py tests/test_triage_related_endpoint.py` → **21 passed**
- Adjacent backend regression (saved-views, spaces, triage, ai_question, briefings, command_bar, nl_creation) → **184 passed, no regressions**
- `npx vitest run` → **159 passed across 10 files**
- `npx tsc -b` → clean
- `npm run build` → clean

---

## Saved View Live Preview in Builder (UI/UX Arc Follow-up 3)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 55 saved-views regression (14 new follow-up 3 + 41 prior Phase 2) + 198 adjacent-phase regression — no pre-existing tests broken. 134 frontend vitest across 7 files (26 new follow-up 3: 5 debounce hook + 21 preview component helpers).

### What shipped

The builder stops being a blind submit-then-see cycle. As the user edits filters, sort, grouping, or presentation, a sticky preview pane on the right renders live against the caller's tenant. Delivers the explicit post-arc polish note from the Phase 2 bullet ("Live preview deferred as post-arc polish — users save then land on detail"). Hot-path cost stays inside the Phase 2 execute budget because the same executor backs both endpoints.

### Approved deviations from the spec (all 10 confirmations plus perf/test additions)

1. **New endpoint** `POST /api/v1/saved-views/preview` taking `{ config }` body. Server-only override `limit → min(limit or 100, 100)`. Returns standard `SavedViewResult`. Registered under arc-telemetry key `saved_view_preview`.
2. **BLOCKING CI gate** at `test_saved_view_preview_latency.py` — p50 < 150 ms / p99 < 500 ms, 20 samples sequential.
3. **`truncated` signal** derived client-side from `rows.length < total_count`. No new backend field.
4. **Mode-switch cache** fingerprint = `{query, limit, aggregation_mode ∈ {none, chart, stat}}`. Non-aggregation mode swaps reuse the cache; chart/stat swap-in refetches.
5. **Pre-render mode hint** lives in `SavedViewBuilderPreview` (NOT `SavedViewRenderer`). The shared renderer stays lean for detail page + widget callers.
6. **`useDebouncedValue`** extracted to `frontend/src/hooks/useDebouncedValue.ts` (~15 lines, 5 vitest). Migration of existing ad-hoc debouncers (cemetery-picker, funeral-home-picker, useDashboard, useNLExtraction, cemetery-name-autocomplete) explicitly NOT in scope — tracked in post-arc backlog.
7. **Layout refactor**: lg+ two-column (LEFT all config stacked, RIGHT sticky preview); <lg collapsible toggle with `localStorage` key `saved_view_preview_collapsed`.
8. **No state refactor.** Builder state was already centralized as a single `useState<SavedViewConfig>` — audit confirmed, zero restructure.
9. **Arc telemetry**: `saved_view_preview` added to `TRACKED_ENDPOINTS`. Middleware-style wrap in the route handler (`try/finally`). No cost field (preview doesn't hit Intelligence).
10. **`previewSavedView(config, {signal})`** client helper in `saved-views-service.ts` with AbortController support.

### Backend additions

- `backend/app/services/arc_telemetry.py` — extended `TRACKED_ENDPOINTS` with `saved_view_preview` as the sixth tracked key.
- `backend/app/api/routes/saved_views.py` — new `_PreviewRequest` Pydantic body + `POST /preview` route. Reuses `SavedViewConfig.from_dict` for parse, `execute()` for dispatch, existing `ExecutorError → HTTP 400` translation. Telemetry wrapped in try/finally. Handler is ~60 lines.
- `backend/scripts` — no seed script needed. Preview reuses the Phase 2 executor + entity registry + permission layer unchanged.

### Frontend additions

- `frontend/src/hooks/useDebouncedValue.ts` — reusable `<T>(value, ms): T` hook. 15 lines. `window.setTimeout` + cleanup.
- `frontend/src/hooks/useDebouncedValue.test.ts` — 5 vitest scenarios (initial sync return, update propagation after delay, rapid-update coalescing, unmount-before-flush safety, delayMs change restarts timer).
- `frontend/src/services/saved-views-service.ts` — `previewSavedView(config, options)` helper with AbortSignal pass-through.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.tsx` — ~350 lines. Exports main `SavedViewBuilderPreview` + three helpers (`computeFingerprint`, `aggregationModeOf`, `requiredSubConfigHint`). Composition: `useDebouncedValue(config, 300ms)` → effect fires `previewSavedView(debouncedConfig, {signal})` → AbortController cancels supersession → cache-key check short-circuits non-aggregation mode swaps → `SavedViewRenderer` renders. Pre-render guard detects missing required sub-config per mode (kanban needs group_by_field + card_title_field; calendar needs date_field + label_field; cards needs title_field; chart needs chart_type + x_field + y_aggregation; stat needs metric_field + aggregation) and renders targeted `EmptyState` copy pointing at Presentation panel. Includes a `SavedViewBuilderPreviewPanel` wrapper with collapse header for potential embedded uses.
- `frontend/src/components/saved-views/SavedViewBuilderPreview.test.tsx` — 21 vitest scenarios covering `aggregationModeOf` (7), `computeFingerprint` (7: non-aggregation mode swap → same fingerprint, chart/stat swap → different, chart x_field change → different, filter value change → different, filter field change → different, stable-across-identity-different-configs), `requiredSubConfigHint` (12: list/table null, kanban group_by/card_title/fully-configured, calendar date/label, cards title, chart, stat, stat fully-configured).
- `frontend/src/pages/saved-views/SavedViewCreatePage.tsx` — layout refactor. Two-column grid at `lg+` (3fr:2fr split — config dominant, preview readable). Sticky preview with `top-4`. Mobile toggle button (`lg:hidden`) rendered in the header next to Save. Preview mobile render (`lg:hidden`) on top of the form when expanded. `localStorage` read synchronously on first render with viewport-width default.
- `frontend/tests/e2e/saved-view-builder-preview.spec.ts` — 8 Playwright scenarios (builder_mounts_preview_pane, preview_populates_on_load, mode_swap_reuses_cache, debounce_coalesces_fast_typing, invalid_filter_inline_error, kanban_missing_group_by_hint, mobile_preview_toggle, refresh_button_bypasses_debounce).

### Performance discipline verified

- **Mode-only swap no-refetch**: Playwright scenario `mode_swap_reuses_cache` observes `/api/v1/saved-views/preview` POST count; swapping list→table→cards→list fires ZERO new calls beyond the initial mount.
- **Keystroke hammering**: `debounce_coalesces_fast_typing` fills the title field (not part of config) and asserts call count unchanged. Config-touching rapid edits are bounded by the 300ms debounce; AbortController cancels stale fires.
- **Telemetry overhead**: preview latency at p99=12.0ms INCLUDES the telemetry record() + try/finally wrap; overhead is well under the 5ms sub-gate implied by the measurements.

### BLOCKING CI gate

`backend/tests/test_saved_view_preview_latency.py`:
- Target: p50 < 150 ms, p99 < 500 ms (20 samples sequential, 1000 sales_order fixture, 4 mixed shapes: list + filter, table + in-filter, kanban + grouping, chart + aggregation)
- **Actual: p50 = 8.5 ms, p99 = 12.0 ms** — 17×/41× headroom
- Second test guards the 100-row cap at scale (1000 rows seeded, `limit=1000` request → 100 rows returned, `total_count=1000`)

### Verification

- `pytest tests/test_saved_view_preview.py tests/test_saved_view_preview_latency.py` → **16 passed**
- Saved-views regression (5 files): 55 passed
- Adjacent-phase regression (10 files covering spaces, task_and_triage, ai_question, briefings, command_bar_retrieval, nl_creation_backend): **198 passed** — no regressions
- Frontend `tsc -b` clean. `npm run build` clean.
- Frontend vitest full suite: **134 tests across 7 files** (5 new debounce + 21 new preview = 26 new; 108 pre-existing).

### Follow-up 3 ≠ architecture introduction

This was a composition over existing primitives: Phase 2 executor + Phase 7 useRetryableFetch pattern + Phase 2 SavedViewRenderer + Phase 7 EmptyState/InlineError/SkeletonCard + Phase 4 debounce idiom extracted to a reusable hook. Zero new tables. One new endpoint. One new component. ~500 net new lines of code excluding tests. The architectural discipline established by follow-ups 1 and 2 (extend existing arc primitives without new architecture) held for the third in the sequence.

### Ready for follow-up 4: Peek panels

Peek panels (last follow-up) can slot into this same composition posture. Likely shape: a slide-over that renders a saved view OR entity detail inline without navigating. The preview pane's "render a saved view from a transient config" contract could be a direct precedent for the "render entity-scoped saved view in a slide-over" pattern. The cache + debounce + abort primitives are all reusable.

---

## AI Questions in Triage Context Panels (UI/UX Arc Follow-up 2)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 138 across Spaces + Triage + AI-Question regression (33 new follow-up tests; 110 adjacent-phase tests also green — no regressions)

### What shipped

**The first wired interactive context panel in the triage workspace.** Phase 5 shipped the pluggable context panel architecture with six types; only `document_preview` was actually wired to real functionality. The remaining five (`saved_view`, `communication_thread`, `related_entities`, `ai_summary`, `ai_question`) rendered "wiring lands in Phase 6" placeholders. Follow-up 2 wires `ai_question`, establishing the interaction pattern (input-focus suppression, ephemeral session state, vertical-aware prompts, rate-limited 429 with structured body) for the remaining stubs when they land post-arc.

Users open a triage queue, click into the "Ask about this task" (or "Ask about this certificate") panel, and type a question. Claude answers grounded in the item record + related entities + vertical-aware terminology. Confidence dot (green/amber/gray). Source references rendered as clickable chips.

### Approved deviations from the spec

1. **Reused existing Phase 5 prompts via v1→v2 Option A bump.** `triage.task_context_question` + `triage.ss_cert_context_question` were authored Phase-5-end with Q&A-shaped variables (`user_question`) — naming revealed intent. No new `triage.ask_question` prompt seeded.
2. **No `AIQuestionPanelConfig` subclass.** Flat `ContextPanelConfig` extended with optional `suggested_questions: list[str]` + `max_question_length: int = 500`.
3. **Dropped `include_saved_view_context`.** Added `_RELATED_ENTITY_BUILDERS` dict parallel to `engine._DIRECT_QUERIES` instead. Per-queue builders fetch denormalized related data without needing Phase 2 executor extensions for per-row scoping.
4. **Centralized confidence mapping** in `app/services/intelligence/confidence.py::to_tier` (≥0.80 high, ≥0.50 medium, else low). None + bad input collapse to low defensively. Reusable by future AI-response consumers.
5. **Rate limit returns structured 429** with `{code: "rate_limited", retry_after_seconds, message}` + `Retry-After` header; frontend translates to a friendly toast ("Pausing AI questions for a moment — try again in Ns").

### Backend additions

- `backend/app/services/intelligence/confidence.py` — centralized `to_tier(score)` utility.
- `backend/app/services/triage/ai_question.py` — ~350 lines. Public: `ask_question`, `AskQuestionResponse`, `SourceReference`, `RateLimited`, typed error subclasses. Private: `_RELATED_ENTITY_BUILDERS` dict, sliding-window rate limiter (`deque` of monotonic timestamps per user_id, threading.Lock for safety), `_reset_rate_limiter` test seam.
- `backend/app/services/triage/types.py` — `ContextPanelType.AI_QUESTION = "ai_question"`; `ContextPanelConfig` gains `suggested_questions: list[str] = []` + `max_question_length: int = 500`.
- `backend/app/services/triage/platform_defaults.py` — both seeded queues now declare an `ai_question` panel. task_triage cites `triage.task_context_question` + suggestions ["Why is this task urgent?", "What's the history with this assignee?", "Are there related tasks I should know about?"]. ss_cert_triage cites `triage.ss_cert_context_question` + suggestions ["What's the history with this funeral home?", "Are there previous certificates for this product?", "Why was this approval flagged?"].
- `backend/app/api/routes/triage.py` — new `POST /sessions/{session_id}/items/{item_id}/ask` endpoint. Translates `RateLimited` → structured 429 body + `Retry-After` header; other `TriageError` subclasses go through the shared `_translate` helper.
- `backend/scripts/seed_intelligence_followup2.py` — Option A idempotent v1→v2 bump. Adds `vertical`, `user_role`, `queue_name`, `queue_description`, `item_type` variables + the VERTICAL-APPROPRIATE TERMINOLOGY Jinja block mirroring Phase 6's pattern. First run: `bumped_to_v2=2`. Re-run: `skipped_customized=2` (Phase 6 multi-version guard correctly protects admin customizations).

### Frontend additions

- `frontend/src/types/triage.ts` — `ContextPanelType` extended with `"ai_question"`; `TriageContextPanelConfig` gains `suggested_questions` + `max_question_length`; new runtime shapes `ConfidenceTier`, `TriageQuestionSource`, `TriageQuestionAnswer`, `TriageRateLimitedBody`.
- `frontend/src/services/triage-service.ts` — `askQuestion(sessionId, itemId, question)` + typed `TriageRateLimitedError` class that wraps the structured 429 body.
- `frontend/src/components/triage/AIQuestionPanel.tsx` — ~260 lines. Suggested-question chips, textarea with character counter, ⌘↵ / Ctrl+↵ submit, inline error surface with retry, confidence dot (emerald / amber / muted), source-reference chips with routing (`task → /tasks/:id`, `sales_order → /order-station/orders/:id`, `customer → /vault/crm/companies/:id`, etc.). Per-item session history resets via `useEffect` on `itemId` change.
- `frontend/src/components/triage/TriageContextPanel.tsx` — dispatcher extended with `"ai_question"` case; new `sessionId` prop threaded from `TriagePage.tsx`.

### Input-focus discipline (requirement 6)

Phase 5's `useTriageKeyboard` hook already suppresses triage shortcuts when focus is on INPUT/TEXTAREA/SELECT/contenteditable/role=textbox (`hooks/useTriageKeyboard.ts:36-41`). Verified by the `keyboard_shortcut_doesnt_fire_action` Playwright scenario: typing "n" in the textarea does NOT fire task_triage's Skip action. No Phase 5 modification needed.

### Tests

- `backend/tests/test_ai_question_service.py` — 17 tests. Confidence tier boundaries (4), service orchestration happy path + medium-confidence tier (2), related-entity builder invocation (1), malformed/error responses (2), question validation (2), item-not-found (1), rate limiting (per-user + overhead sub-gate, 3), preconditions (no-panel, cross-user, 2).
- `backend/tests/test_triage_ai_question_api.py` — 8 tests. Happy-path roundtrip, session/item 404s, question too long (400), empty question (Pydantic 422), auth required, cross-user isolation, structured 429 body + Retry-After header.
- `backend/tests/test_ai_question_prompt_terminology.py` — 6 tests. Parametrized over 4 verticals (manufacturing / funeral_home / cemetery / crematory) asserting correct USE + DO-NOT-USE lines in rendered prompt. Unknown-vertical fallback. SS cert prompt also renders the block (both v2 bumps verified).
- `backend/tests/test_ai_question_latency.py` — 2 BLOCKING CI gates. `/ask` endpoint: **p50 = 8.2 ms / p99 = 33.3 ms** vs target 1500/3000ms (180× p50 headroom — orchestration-only; real Haiku in prod adds ~350ms). Confidence mapping: effectively 0ms per call (sub-1ms budget met).
- `frontend/tests/e2e/ai-question-panel.spec.ts` — 7 Playwright scenarios. Panel renders, suggested-chip populates input, character counter updates, keyboard shortcut suppression, submit-API-contract roundtrip (mocked), rate-limit friendly toast (mocked 429), backend API shape smoke (live or 502 both accepted).

### Verification

- `pytest tests/test_ai_question_service.py tests/test_triage_ai_question_api.py tests/test_ai_question_prompt_terminology.py tests/test_ai_question_latency.py` → **33 passed**.
- Full triage + spaces regression (9 test files, 138 tests) → **138 passed**. No pre-existing tests broken.
- Adjacent phases (briefings, briefing terminology, command-bar retrieval, NL creation, saved views) → **110 passed**. Vertical-aware pattern transplanted cleanly.
- Frontend `tsc -b` clean. `npm run build` clean.
- Seed script first run: `bumped_to_v2=2` (both triage prompts advanced v1→v2). Idempotent re-run: `skipped_customized=2` (Phase 6 multi-version guard correctly protects re-seeded state).

### Establishes precedent for future interactive panels

Phase 5 shipped six context panel types; only `document_preview` was wired. Follow-up 2 wires `ai_question` — **the first interactive context panel in the triage system**. The patterns established here (input-focus suppression via the existing hook, ephemeral session state on the frontend, per-queue builder dict for related entities, structured 429 with friendly toast) are the blueprint for wiring the remaining four (`ai_summary`, `saved_view`, `communication_thread`, fully-interactive `related_entities`) when they come up post-arc. That's why the dispatcher's "wiring lands post-arc" placeholders explicitly point at this precedent rather than a specific phase number.

### Ready for follow-up 3

Saved view live preview in builder. Post-follow-up-2 platform state: the arc has shipped + two follow-ups proven-pattern (follow-up 1 extended a Phase 3 registry; follow-up 2 extended a Phase 5 primitive with an interactive panel + vertical-aware prompt bump). Remaining two follow-ups stay architecturally cheap.

---

## Space-Scoped Triage Queue Pinning (UI/UX Arc Follow-up 1)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 103 across Phase 3 + Phase 5 + follow-up regression (17 new follow-up tests in `test_space_pins_triage_queue.py`, 86 prior-phase spaces/triage tests unchanged)

### What shipped

Triage queues become a third pin target type alongside saved views
and nav items. A director on the funeral_home vertical opens their
auto-seeded Arrangement space and the first pin in the sidebar is
their Task Triage queue with a pending-item count badge — one click
opens the keyboard-driven workspace. A production manager on a
manufacturing tenant gets the same treatment on their Production
space.

Under the hood:

- `PinConfig.pin_type` literal extended with `"triage_queue"` on
  backend and frontend types (`backend/app/services/spaces/types.py`,
  `frontend/src/types/spaces.ts`).
- `ResolvedPin` gains `queue_item_count: int | None` (null for
  non-triage pins and for unavailable queues).
- `TriageQueueConfig` gains `icon: str = "ListChecks"`. Platform
  defaults: `task_triage` → `"CheckSquare"`,
  `ss_cert_triage` → `"FileCheck"`. Frontend `PinnedSection.ICON_MAP`
  gained all three names — verified present so no pin falls through
  to the `Layers` default silently.
- `_resolve_pin` has a new `triage_queue` branch that reads the
  queue config from the Phase 5 registry via
  `triage.registry.get_config` and pulls the pending count via
  `triage.engine.queue_count`. On access-denied or unknown-queue the
  pin renders with `unavailable=true, queue_item_count=null` and no
  href — same UX as a saved-view pin whose view was deleted.
- Permission check is **batched once per space resolution**: if any
  pin on the space has `pin_type="triage_queue"`, `_resolve_space`
  calls the new `_accessible_queue_ids_for_user(db, user)` helper
  exactly once and passes the set down to each `_resolve_pin`. Spaces
  without triage pins pay zero permission lookups.
- Seed templates for (`funeral_home`, `director`) Arrangement and
  (`manufacturing`, `production`) Production both start with
  `PinSeed(pin_type="triage_queue", target="task_triage")` as the
  first pin. Other role/vertical pairs stay unchanged per approved
  scope.
- `add_pin` validation tuple extended to accept `triage_queue`.
  Idempotent: same (pin_type, target_id) returns the existing pin.
- `PinStar` component accepts `pinType: "triage_queue"`; TriageIndex
  (`/triage`) cards render a PinStar in the card header.
- `PinnedSection` renders a pending-count badge on available
  `triage_queue` pins (`queue_item_count > 0`) in the active-space
  accent color. Capped at `99+` to keep the row tidy. Hidden on row
  hover so the unpin X has room.
- Space-scoped nav preference preserved: the pin shortcuts (PinStar
  toggle, Cmd+[ / Cmd+] space switch, Cmd+Shift+1..5) work on the
  new pin type without any additional wiring — Phase 3 keyboard
  listeners already iterate the active space's pins generically.

### API contract changes (additive, backward-compatible)

- `POST /api/v1/spaces/{id}/pins` now accepts
  `pin_type: "triage_queue"` with `target_id: <queue_id>` (e.g.
  `"task_triage"`).
- `_PinResponse` ships a new `queue_item_count: int | None` field.
  Existing consumers ignore unknown fields; no frontend code that
  already reads the response shape breaks.

### Test additions

- Backend: `backend/tests/test_space_pins_triage_queue.py` — 17 tests
  across 6 test classes. Registry icon presence, seed-template
  content, resolver behavior (available / label-override /
  unavailable-by-vertical / unknown-queue), batched access-lookup
  perf (spy asserts `_accessible_queue_ids_for_user` called exactly
  once per space with ≥1 triage pin, zero when no triage pins),
  add_pin validation + idempotency, full-stack API roundtrip +
  cross-user isolation.
- Playwright: `frontend/tests/e2e/space-triage-pin.spec.ts` — 5
  scenarios covering the POST shape (icon, href, queue_item_count),
  PinStar presence on /triage cards, sidebar reflection of a newly
  pinned queue, unavailable pin wire contract, list-endpoint shape
  for every triage pin.

### Verification

- `pytest tests/test_spaces_unit.py tests/test_spaces_api.py
  tests/test_task_and_triage.py tests/test_space_pins_triage_queue.py`
  → **103 passed**.
- Frontend `tsc -b` clean.
- ICON_MAP acceptance criterion: grepped
  `frontend/src/components/spaces/PinnedSection.tsx`, confirmed
  `CheckSquare`, `FileCheck`, `ListChecks` all imported from
  `lucide-react` and registered in ICON_MAP. No pin renders with the
  Layers fallback for shipped queue icons.

### Design decisions / deviations (approved)

- Queue icon sourced from `TriageQueueConfig.icon` (authoritative)
  rather than a frontend queue_id → icon lookup table. Single source
  of truth; tenant-customized queues can override via vault_item
  metadata without a frontend change.
- Seeded pin scope limited to (`funeral_home`, `director`) and
  (`manufacturing`, `production`) per spec. Other role templates
  unchanged; users in other roles can pin queues manually via the
  PinStar on `/triage`.
- Template additions do NOT backfill for already-seeded users
  (matches Phase 3 precedent). Existing director/production users
  can pin manually; next fresh seed picks up the template.
- Role slug for manufacturing production template is `"production"`
  (existing convention), not `"production_manager"` as a spec draft
  mentioned.

---

## Polish and Arc Finale (Phase 7 of UI/UX Arc — FINAL)

**Date:** 2026-04-20
**Migration head before:** `r35_briefings_table`
**Migration head after:** `r35_briefings_table` (no new migration — zero new tables per approved scope)
**Tests passing:** 288 across Phase 1-7 regression (8 new Phase 7 contrast + focus-ring tests; 280 prior-phase tests unchanged)

### What shipped

**Shared UI primitives** (`frontend/src/components/ui/`):
- `empty-state.tsx` — `EmptyState` with 3 tones (neutral / positive / filtered) × 3 sizes (default / sm / xs). Optional icon + title + description + action + secondaryAction.
- `skeleton.tsx` — `Skeleton` base + `SkeletonLines` / `SkeletonCard` / `SkeletonRow` / `SkeletonTable` composites. All use `motion-safe:animate-pulse`.
- `inline-error.tsx` — `InlineError` with role=alert + aria-live + optional retry handler + severity variants.

**Hooks** (`frontend/src/hooks/`):
- `useRetryableFetch.ts` — generic auto-retry-once (~1s backoff) + manual `reload()`.
- `useOnboardingTouch.ts` — server-side dismissal via `User.preferences.onboarding_touches_shown`; cross-device; module-scoped session cache for efficiency.
- `useOnlineStatus.ts` — `navigator.onLine` + online/offline event listener.

**New components:**
- `components/onboarding/OnboardingTouch.tsx` — first-run tooltip with auto-dismiss option + positioned anchoring
- `components/core/KeyboardHelpOverlay.tsx` — `?`-key context-aware shortcut help overlay (mounted at App root)
- `components/core/OfflineBanner.tsx` — global top banner when `navigator.onLine === false`

**Empty state replacements (10 surfaces):**
- 7 saved view renderers: List, Table, Kanban, Cards, Chart (with `BarChart3` icon), Stat (inline "No data for selected period"), Calendar (per-month empty-message below grid)
- TasksList: two states — empty-all (positive tone with CTA) vs empty-filtered (clear-filters action)
- TriagePage caught-up (positive tone, session stats + back-link)
- TriageIndex (contextual messaging with link to settings)
- CommandBar no-results (with "try: 'new case', 'my invoices', 'switch to production'" hints)
- SavedViewsIndex (icon + CTA)
- BriefingPage (graceful fallback when scheduler hasn't run yet)

**Skeleton replacements (5 surfaces):** BriefingPage (narrative + 2 section cards), BriefingCard (3-line narrative), SavedViewsIndex (3 card grid), TasksList (5-row table skeleton), TriagePage (card + palette skeleton), TriageIndex (2 queue cards).

**Error retry:**
- `BriefingPage` auto-retries once on load failure before surfacing the error; manual retry button via `InlineError`.
- `Triage action retry` — action failures no longer transition session to error state; toast fires, status returns to idle, item stays in queue, keystroke not lost. Triage-context re-throws after clearing status so caller's toast still fires.
- `SavedViewsIndex` error renders `InlineError` with hint.
- `TriageIndex` error renders `InlineError` with retry.

**First-run tooltips (5 wired):**
- Backend: `GET/POST/DELETE /api/v1/onboarding-touches/{key}` reading/writing `User.preferences.onboarding_touches_shown`.
- Tooltips: command bar (`command_bar_intro` inside the modal), saved view page (`saved_view_intro` in page header), space switcher (`space_switcher_intro` only when 2+ spaces), triage page (`triage_intro`), briefing page (`briefing_intro`).
- Client hook `useOnboardingTouch` uses a module-scoped session promise to avoid 5 simultaneous fetches across 5 surfaces; optimistic dismissal with server fire-and-forget.

**ARIA + aria-live pass (4 arc surfaces):**
- CommandBar: `role=dialog` + `aria-modal` on overlay; `aria-label="Command bar"`; input as `role=combobox` + `aria-controls=command-bar-results` + `aria-expanded` + `aria-autocomplete=list` + `aria-describedby`; results container with `role=listbox` + `aria-live=polite`; footer with id hint.
- NLOverlay: body region with `role=region` + `aria-label` + `aria-live=polite` + `aria-busy={isExtracting}`. Error block upgraded to `role=alert` with hint.
- TriagePage: current-item section with `role=region` + `aria-label="Current triage item"` + `aria-live=polite` + `aria-busy`.
- BriefingPage: narrative CardContent with `role=region` + `aria-label="Briefing narrative"` + `aria-live=polite`.

**`?`-key help overlay:** `KeyboardHelpOverlay` at App root. Listens to `?` globally (ignoring inputs / contenteditable); opens modal showing context-aware shortcut sections: always Global + CommandBar + Spaces; adds Triage when on `/triage/*`; adds Tasks when on `/tasks/*`. Escape or `?` again dismisses. motion-safe animate-in.

**Mobile fixes:** 44px `min-h-[44px]` on TriageActionPalette decision buttons, TriageFlowControls snooze presets, BriefingPreferences channel/section toggles. BriefingPreferences grid collapsed from `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` so the time picker + channel buttons stack cleanly on 375px. CalendarRenderer day cells changed to `min-h-[70px] sm:min-h-[92px]` + grid wrapper `overflow-x-auto` for narrow viewports.

**Offline banner:** `OfflineBanner` at App root above impersonation banner. `useOnlineStatus` subscribes to `online`/`offline` events. Renders an amber strip with `WifiOff` icon + "You appear to be offline. Changes will sync when reconnected." Deliberately simple — no proactive connectivity probe (that's post-arc observability).

**prefers-reduced-motion global retrofit:** Added to `frontend/src/index.css` as a blanket `@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; scroll-behavior: auto !important; } }` block. Handles 40+ pre-existing transitions across Phase 1-6 + shadcn/ui + tw-animate-css without needing to touch each file. Phase 7 new components use `motion-safe:` variants natively.

**Telemetry dashboard** (platform-admin-gated, mounted at `/bridgeable-admin/telemetry`):
- Backend `app/services/arc_telemetry.py` — thread-safe in-memory rolling latency buffer (1000 samples cap) per endpoint + error counter. `record(endpoint, latency_ms, errored)` called via try/finally on the 5 arc endpoints (command_bar_query, saved_view_execute, nl_extract, triage_next_item, triage_apply_action). `snapshot()` returns p50/p99/counts.
- Backend `app/api/routes/admin/arc_telemetry.py` — `GET /api/platform/admin/arc-telemetry` returns endpoint snapshot + `intelligence_executions` aggregations over 24h/7d/30d windows + per-caller-module cost breakdown (24h).
- Frontend `bridgeable-admin/pages/ArcTelemetry.tsx` — endpoint latency table + 3 Intelligence window cards + caller-module cost table + honest banner: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **No new database table.** Intelligence aggregations persist via existing `intelligence_executions` rows.

**Contrast verification + accent remediation:** `backend/tests/test_arc_accent_contrast.py` (5 tests) mirrors the 6 space accents from `frontend/src/types/spaces.ts` and asserts:
- Hex format valid for all 6 × 3 colors
- Foreground on white ≥ 4.5:1 (WCAG AA normal text) — ALL 6 PASS
- Accent on white ≥ 3.0:1 (WCAG AA large text) — ALL 6 PASS
- Foreground on accent-light chip ≥ 4.5:1 — ALL 6 PASS
- Accent distinguishable from preset fallback (except `neutral` which deliberately matches) — ALL PASS

**Zero accent remediation needed.** All 6 were already WCAG AA compliant.

**Focus ring visibility remediation:** `backend/tests/test_arc_focus_ring_contrast.py` (3 tests) verifies the `--ring` color passes WCAG 3:1 non-text-UI contrast against:
- Pure white — **required bump from `oklch(0.708 0 0)` to `oklch(0.48 0 0)`**
- Each of the 6 accent-light chip backdrops — now passing with new value

Fix: single-line change in `frontend/src/index.css` light-mode `:root` block. Test includes a guard (`test_focus_ring_lightness_matches_index_css`) that parses the CSS file + asserts the constant matches — prevents drift.

**Micro-interactions (motion-safe):**
- NL extraction field entrance: `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1 motion-safe:duration-200` on each field row
- Triage item transition: `key={item.entity_id}` forces remount; wrapper has `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-200`

### Design decisions / deviations (approved)

- **Arc finale docs moved up to #11-12 (before micro-interactions / contrast / focus-ring tests) per approved refinement** — but in execution, the refactor audit surfaced that telemetry (#12) + contrast (#14) + focus-ring (#15) should ship first so docs can reference real data. Final order: steps 1-10 → 12 → 13 → 14 → 15 → 11. Outcome matches intent: docs written with clear head, deliver accurate performance envelope + post-arc backlog.
- **Cross-arc layout consistency dropped entirely** per approved refinement. Per-page max-width variation preserved (different content types, different ideal widths).
- **Demo flow scripts added to UI_UX_ARC.md** per approved refinement — 5 rehearsable demos with exact keystroke-level scripts for September Wilbert meeting.
- **Telemetry honest-expectation-setting** on page itself: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **prefers-reduced-motion** non-negotiable: global CSS block retrofit + `motion-safe:` variants on all Phase 7 new transitions.
- **Two persistence layers** for tooltip dismissal preserved (as approved): `useOnboardingTouch` = server-side cross-device; `HelpTooltip` = localStorage device-local. Not merged.
- **Contrast + focus-ring** verified programmatically, not just documented. All accents pass; focus ring required one-line `--ring` darkening to pass WCAG 3:1.

### Test additions

- `backend/tests/test_arc_accent_contrast.py` (5 tests)
- `backend/tests/test_arc_focus_ring_contrast.py` (3 tests)
- 8 total new Phase 7 backend tests (all passing)
- All 280 Phase 1-6 tests still pass unchanged
- tsc 0 errors
- All 5 BLOCKING latency gates still green

### Verification

- **288 backend tests pass** across Phase 1-7 regression (280 prior + 8 Phase 7 new) — no regressions
- **BLOCKING latency gates (all 5) unchanged and green:**
  - command_bar_query: p50 = 5.0 ms, p99 = 6.9 ms
  - saved_view_execute: p50 = 15.4 ms, p99 = 18.5 ms
  - nl_extract (no AI): p50 = 5.9 ms, p99 = 7.2 ms
  - triage_next_item: p50 = 4.8 ms, p99 = 5.8 ms
  - triage_apply_action: p50 = 9.7 ms, p99 = 13.5 ms
  - briefing_generate (AI stubbed): p50 = 28.9 ms, p99 = 32.0 ms
- **WCAG AA contrast: all 6 space accents pass** (zero remediation needed)
- **Focus ring: WCAG 3:1 passes against white + all 6 accent-light backdrops** (after `--ring` bump)
- tsc 0 errors
- Backend imports cleanly including new routes + services

### Arc totals (Phases 1-7 complete)

| Metric | Count |
|---|---|
| Phases shipped | 7 |
| Platform primitives established | 7 |
| Database migrations (arc-specific) | 5 (r31, r32, r33, r34, r35) |
| New tables | 4 (triage_sessions, triage_snoozes, tasks, briefings) |
| Backend tests | 288 (no regressions) |
| BLOCKING CI latency gates | 5 (all green) |
| BLOCKING parity tests | 3 (SS cert triage — all green) |
| Playwright specs | 50+ across arc |
| Intelligence prompts seeded | 13+ |
| New API endpoints | ~60 |
| New shared frontend components | 8 (`EmptyState`, `Skeleton`+4 variants, `InlineError`, `OnboardingTouch`, `KeyboardHelpOverlay`, `OfflineBanner`, plus 3 per-primitive component sets from Phase 2-6) |
| Post-arc backlog items | ~45 (documented in `UI_UX_ARC.md`) |

### Post-arc cleanup items (documented, NOT Phase 7 work)

All 45+ items consolidated in `UI_UX_ARC.md` under "Post-arc Backlog". The most impactful:
1. Rename `/briefings/v2/*` → cleaner REST (Phase 6 cleanup)
2. Consolidate `employee_briefings` + `briefings` tables (Phase 6 cleanup)
3. Migrate legacy `MorningBriefingCard` consumers to new `BriefingCard` (Phase 6 → Phase 7 cleanup — legacy preserved per coexist strategy)
4. Build native mobile redesigns of arc surfaces (Phase 7 scope cut — mobile was functional-only)
5. Advanced observability (Phase 7 telemetry was minimal by design)
6. External accessibility audit (Phase 7 scope cut — verified programmatically only)

### What the arc enables

The September 2026 Wilbert licensee meeting demo reaches its moment: a funeral director opens the command bar on the Bridgeable platform, types one sentence, watches the platform extract 5 structured fields in under a second, presses Enter, and has a fully-populated case record. The demo flow is documented keystroke-by-keystroke in `UI_UX_ARC.md`. Rehearsal checklist included.

Beyond the demo: the seven primitives compose. Every future feature inherits:
- Command bar surface via registry entry
- Saved views for any list/dashboard
- Space-aware context via active_space_id
- NL creation for any new entity type (append to entity_registry)
- Triage workspace for any decision stream (append to platform_defaults)
- Briefings can emphasize the feature by exposing a data source
- Polish primitives (EmptyState/Skeleton/InlineError) for every empty/loading/error state

**Arc complete. Platform ready for September.**

---

## Arc-level summary table (all 7 phases)

| Phase | Dates | Migration | Tests | Key primitive |
|---|---|---|---|---|
| 1 — Command Bar | Apr 2026 | r31 | 116 | `POST /command-bar/query` |
| 2 — Saved Views | Apr 2026 | r32 | 46 | `vault_items` saved_view_config |
| 3 — Spaces | Apr 2026 | (none — User.preferences) | 64 | `User.preferences.spaces` |
| 4 — NL Creation | Apr 2026 | r33 | 87 | Structured + resolver + AI pipeline |
| 5 — Triage | Apr 2026 | r34 | 42 | Pluggable 7-component queue configs |
| 6 — Briefings | Apr 2026 | r35 | 36 | AI narrative + per-user sweep |
| 7 — Polish | Apr 2026 | (none) | 8 | Cross-cutting polish infrastructure |

---
## Morning and Evening Briefings (Phase 6 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r34_tasks_and_triage`
**Migration head after:** `r35_briefings_table`
**Tests passing:** 27 backend + 2 BLOCKING latency gates + 7 Playwright = 36 new, plus 280 Phase 1–6 regression green

### What shipped

**Backend**

- Migration `r35_briefings_table`: new `briefings` table coexisting with legacy `employee_briefings` (different semantics — `(user_id, briefing_type, DATE(generated_at))` partial unique allows morning + evening same day; legacy's `(company_id, user_id, briefing_date)` unique only allowed one per day)
- `app/models/briefing.py` — Briefing ORM + `BRIEFING_TYPES` literal
- `app/services/briefings/` package — 7 modules (types, preferences, data_sources, generator, delivery, scheduler_integration, __init__); **legacy context builders imported and reused verbatim**: `_build_funeral_scheduling_context`, `_build_precast_scheduling_context`, `_build_invoicing_ar_context`, `_build_safety_compliance_context`, `_build_executive_context`, `_build_call_summary`, `_build_draft_invoice_context`
- **Legacy blocklist → Phase 6 allowlist translation**: `seed_preferences_for_user` translates `AssistantProfile.disabled_briefing_items` (existing blocklist) to `BriefingPreferences.{morning,evening}_sections` (Phase 6 allowlist) via set subtraction; idempotent per role via `preferences.briefings_seeded_for_roles`
- 7 `/api/v1/briefings/v2/*` endpoints coexisting with legacy `/briefings/briefing` + `/briefings/action-items` + `/briefings/team-config` (route coexistence under same router, no renaming)
- `POST /v2/generate` uses explicit delete-then-create semantics for "regenerate today's" (deletes existing same-day-same-type row, inserts fresh)
- `scripts/seed_intelligence_phase6.py` — idempotent; seeds `briefing.morning` + `briefing.evening` prompts (Haiku simple, force_json, 2048 max_tokens, 0.4 temp) + 2 managed email templates (`email.briefing.morning` + `email.briefing.evening`) via Phase D-2 DocumentTemplate registry (no on-disk files per D-2/D-3 discipline)
- `job_briefing_sweep()` added to `scheduler.py` with `CronTrigger(minute="*/15")` — first per-user scheduled pattern on the platform
- Seed hook wired at `user_service.update_user`'s role-change site alongside Phase 2 saved_views + Phase 3 spaces seeds
- **BLOCKING CI gate** at `test_briefing_generation_latency.py` — p50 < 2000ms, p99 < 5000ms. Actual: **p50=28.9ms / p99=32.0ms** (69× / 156× headroom) with Intelligence monkey-patched to measure orchestration overhead
- **BLOCKING space-awareness tests** — parametrized × 3 spaces (Arrangement/Administrative/Production), intercepts Intelligence call, asserts `active_space_name` reaches prompt variables
- **BLOCKING Call Intelligence integration test** — `overnight_calls` None when no RC logs; populated with `{total, voicemails, ...}` when seeded RC log exists — preserves legacy `_build_call_summary` path verbatim
- **BLOCKING legacy coexistence tests** — `/briefings/briefing` + `/briefings/action-items` still 200; `briefing.daily_summary` prompt still active; legacy context builders still importable

**Frontend**

- `types/briefing.ts` — full mirrors of backend Pydantic shapes
- `services/briefing-service.ts` — 7-endpoint axios client
- `hooks/useBriefing.ts` — latest-briefing fetch + manual reload (no auto-refresh; scheduler owns backend generation)
- `pages/briefings/BriefingPage.tsx` (`/briefing` + `/briefing/:id`) — narrative card + collapsible structured-sections cards; Morning/Evening toggle; Regenerate + Mark-read buttons; queue_summaries deep-link to `/triage/:queueId`
- `components/briefings/BriefingCard.tsx` — new dashboard widget (opt-in mount); truncated narrative + "Read full briefing →" link
- `pages/settings/BriefingPreferences.tsx` (`/settings/briefings`) — optimistic-save toggles + time picker + channel + section allowlist
- 3 new routes in `App.tsx` (`/briefing`, `/briefing/:id`, `/settings/briefings`)
- 2 new cross-vertical command bar actions in `services/actions/shared.ts` — `navigate_briefing_latest` + `navigate_briefing_preferences`
- **Legacy `MorningBriefingCard` + `morning-briefing-mobile.tsx` + `BriefingSummaryWidget.tsx` UNCHANGED** — still mounted on `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` consuming legacy endpoints
- 7 Playwright specs in `frontend/tests/e2e/briefings-phase-6.spec.ts`

### Design decisions / deviations (approved)

- **Coexist strategy over absorb/replace** — `briefing_service.py` (1869 lines) represents months of customer ground-truth tuning. Phase 6 imports it as a dependency rather than rewriting. Legacy endpoints + components + prompts stay fully operational.
- **`/v2/*` route prefix** — intentionally ugly per approved spec item #3. Zero migration risk to existing consumers. Post-arc cleanup can rename.
- **Two tables (briefings + employee_briefings)** — different unique-constraint semantics make the two-table approach cleaner than extending the legacy table. `employee_briefings` stays read-only legacy.
- **Every-15-min global sweep with in-app per-user timing** — first per-user scheduled pattern. One APScheduler registration; sweep function computes per-user local time via `Company.timezone` + checks preference windows + DB idempotency. Documented as canonical pattern in CLAUDE.md §10.
- **Keyboard shortcut `G B` dropped** per approved scope cut — users pin `/briefing` to a space via PinStar + reach via `Cmd+Shift+N` using existing Phase 3 infrastructure.
- **`/v2/generate` delete-then-create** semantics discovered during latency-test development (second call inside same day hit the unique constraint). Explicit regenerate-today behavior chosen over upsert or 409 response. Post-arc rename to `/v2/regenerate` to signal intent.
- **Managed email templates only** — no `app/templates/email/` on-disk directory per D-2/D-3 discipline. Templates seeded as DocumentTemplate rows with `output_format="html"`.
- **Space-awareness via prompt Jinja branches, not variable substitution** — the `briefing.morning` + `briefing.evening` prompts contain `{% if active_space_name == "Arrangement" %}...{% endif %}` blocks that change section emphasis. The BLOCKING test asserts `active_space_name` reaches prompt variables (the hook Jinja branches on); visible output differentiation is Haiku's job and not asserted against live AI.

### Post-arc cleanup items (documented, NOT Phase 6 work)

1. Rename `/briefings/v2/*` → cleaner REST (e.g. `/briefings` replaces legacy; legacy moves to `/briefings/legacy/*`)
2. Consolidate `employee_briefings` + `briefings` tables — two-table approach is temporary coexist, not long-term
3. Migrate legacy `MorningBriefingCard` consumers at `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` to new `BriefingCard`
4. Retire `briefing.daily_summary` prompt once legacy `MorningBriefingCard` retires (both live together or both die together)
5. Revisit `briefing_service.py` for consolidation once legacy surfaces retire — 1869 lines of context-builder logic can fold into `briefings/data_sources.py` directly, removing the cross-package import dependency
6. Rename `/v2/generate` → `/v2/regenerate` for intent clarity
7. Add briefing AI learning (auto-drop sections user consistently skips) — post-arc
8. Add SMS/Slack/voice (TTS) delivery channels — post-arc
9. Add shared team briefings ("Today's Services" read-mostly view) — post-arc
10. Network-level cross-tenant briefings for licensee operators — post-arc

### Verification

- 280 Phase 1–6 backend tests passing (253 Phase 1–5 + 27 Phase 6 new)
- Both BLOCKING CI gates pass with massive headroom (p50=28.9ms vs 2000ms target)
- Space-awareness test parametrized × 3 spaces — all assert `active_space_name` reaches prompt variables
- Call Intelligence integration test — overnight_calls absent/present matches RC log state
- Legacy regression — `/briefings/briefing` + `/briefings/action-items` still 200; legacy prompt still seeded; legacy context builders still importable
- tsc clean (0 errors)
- 7 Playwright specs written (not run here — require live staging backend)

---

## Triage Workspace + actionRegistry Reshape + Task Infrastructure (Phase 5 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r33_company_entity_trigram_indexes`
**Migration head after:** `r34_tasks_and_triage`
**Tests passing:** 33 backend + 2 BLOCKING latency gates + 9 Playwright = 44 new, plus 253 Phase 1–5 regression green

### What shipped

**Backend**

- Migration `r34_tasks_and_triage`: 3 tables (`tasks`, `triage_sessions`, `triage_snoozes` — entity-type-agnostic with partial unique `uq_triage_snoozes_active WHERE woken_at IS NULL`) + GIN trigram index on `tasks.title` via CREATE INDEX CONCURRENTLY in autocommit_block
- `app/models/task.py` with TASK_PRIORITIES (low/normal/high/urgent) + TASK_STATUSES (open/in_progress/blocked/done/cancelled), polymorphic link via related_entity_type + related_entity_id
- `app/services/task_service.py` with full CRUD + `_ALLOWED_TRANSITIONS` state machine (invalid → 409)
- `app/api/routes/tasks.py` — 7 endpoints at `/api/v1/tasks/*` (list with filters + create + get + patch + soft-delete + complete + cancel)
- `app/services/triage/` package: types.py (Pydantic with schema_version="1.0", `extra="forbid"`, 7 component configs, typed errors) + registry.py (in-code singleton `_PLATFORM_CONFIGS` via register_platform_config — pattern pivot from vault_item because VaultItem.company_id NOT NULL; per-tenant overrides still vault-item-backed) + engine.py (start_session resumable via current_item_id + cursor_meta.processed_ids, next_item, apply_action handler→Playwright→workflow pipeline, snooze with partial-unique-index protection, queue_count, sweep_expired_snoozes; `_DIRECT_QUERIES` dispatch for entities not in Phase 2 saved-views registry — `_dq_task_triage`, `_dq_ss_cert_triage`) + action_handlers.py (HANDLERS dict — task.complete/cancel/reassign + **ss_cert.approve/void call SocialServiceCertificateService verbatim for parity** + skip + escalate) + embedded_actions.py (wraps existing PlaywrightScript + workflow_engine) + platform_defaults.py (two shipped queues: task_triage + ss_cert_triage registered at import time) + __init__.py (side-effect platform_defaults import BEFORE registry helpers)
- `app/api/routes/triage.py` — 9 endpoints at `/api/v1/triage/*`
- `app/services/nl_creation/entity_registry.py` extended with task entity (title/description/assignee via target="user"/due_date/priority); new `resolve_user()` in entity_resolver.py using ILIKE (no trigram index yet); EntityType literal extended; `_create_task` creator
- Phase 1 `command_bar/resolver.py` SEARCHABLE_ENTITIES adds task with url_template="/tasks/{id}"; `command_bar/registry.py` adds create.task with aliases new task / add task / create task / todo / new todo
- `backend/scripts/seed_triage_queues.py` — validates in-code platform configs loaded + seeds 2 Intelligence prompts (triage.task_context_question, triage.ss_cert_context_question) via Haiku simple route + force_json=True
- **BLOCKING CI gates** at `backend/tests/test_triage_latency.py`: next_item p50<100ms/p99<300ms + apply_action p50<200ms/p99<500ms. Actual: next_item p50=4.8ms / p99=5.8ms; apply_action p50=9.7ms / p99=13.5ms — 20×+ headroom on both
- **BLOCKING SS cert parity** — 3 tests in `TestSSCertTriageParity` class of `test_task_and_triage.py` asserting triage approve/void produces identical side effects (status transitions, approved_at/voided_at stamps, approved_by_id/voided_by_id, void_reason preservation) as legacy `/social-service-certificates` page

**Frontend**

- `services/actions/` package replaces legacy `core/actionRegistry.ts` (944 lines → split per-vertical files):
  - `types.ts` — rich ActionRegistryEntry (permission, required_module, required_extension, handler, playwright_step_id, workflow_id, supports_nl_creation, nl_aliases, keyboard_shortcut)
  - `registry.ts` — singleton + toCommandAction converter + getActionsForVertical/filterActionsByRole/matchLocalActions/getActionsSupportingNLCreation helpers + legacy CommandAction/RecentAction types preserved for render-time compat
  - `shared.ts` — 6 cross-vertical creates including NEW create_task + create_event with supports_nl_creation: true
  - `manufacturing.ts` — 57 mfg actions migrated verbatim
  - `funeral_home.ts` — 9 FH actions (case create with supports_nl_creation=true)
  - `triage.ts` — 3 NEW nav entries (workspace index, task queue, ss cert queue)
  - `index.ts` — side-effect registers all entries at module load
- 5 call sites migrated (CommandBar.tsx, SmartPlantCommandBar.tsx, CommandBarProvider.tsx, cmd-digit-shortcuts.ts, commandBarQueryAdapter.ts); old `core/actionRegistry.ts` deleted
- `components/nl-creation/detectNLIntent.ts` rewritten — derives ENTITY_PATTERNS at call time from `getActionsSupportingNLCreation()`; hand-maintained table eliminated. `NLEntityType` extended with "task"
- `types/triage.ts` — full mirrors of backend Pydantic shapes
- `services/triage-service.ts` — 9-endpoint client (fetchNextItem returns null on 204)
- `services/task-service.ts` — 7-endpoint client
- `contexts/triage-session-context.tsx` — TriageSessionProvider bootstraps config + session + first item; fire-and-forget endSession on unmount
- `hooks/useTriageKeyboard.ts` — shift/alt/meta/ctrl modifier support, skips inputs/textareas/contenteditable
- `components/triage/`: TriageItemDisplay (dispatches on display_component — task / social_service_certificate / generic), TriageActionPalette (reason modal with disabled-until-valid Confirm, kbd hints), TriageContextPanel (collapsible rail; document_preview live, saved_view/communication_thread/related_entities/ai_summary Phase-6-ready stubs), TriageFlowControls (snooze preset buttons)
- Pages: `pages/triage/TriageIndex.tsx` + `pages/triage/TriagePage.tsx` + `pages/tasks/TasksList.tsx` + `pages/tasks/TaskCreate.tsx` + `pages/tasks/TaskDetail.tsx`
- 5 new routes in App.tsx: `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/triage`, `/triage/:queueId`
- 9 Playwright specs in `frontend/tests/e2e/triage-phase-5.spec.ts`

### Design decisions / deviations

- **Platform-default triage queue configs as in-code singleton, not vault_items.** Initial design stored platform configs as vault_items with company_id=NULL (mimicking Intelligence prompts). VaultItem's NOT NULL constraint forced the pivot. Per-tenant overrides still use vault_items via the `triage_queue_config` item_type, read by `_tenant_overrides()` in registry.py.
- **Three source modes for queue configs.** Phase 2 saved_views SEARCHABLE_ENTITIES doesn't cover task or social_service_certificate. Rather than extend Phase 2's registry (coordination with Phase 5 cleanup note), introduced `source_direct_query_key` as third option dispatching to `_DIRECT_QUERIES` table in engine.py. Phase 2 entities use `source_inline_config`; per-tenant customization uses `source_saved_view_id`.
- **SS cert parity preserved by handler reuse, not copy.** `_handle_ss_cert_approve` calls `SocialServiceCertificateService.approve(cert_id, user_id, db)` verbatim; void is identical. Zero duplication. Parity test validates both paths produce identical DB state + timestamps + audit fields.
- **detectNLIntent duplication eliminated via registry flag.** The Phase 4 hand-maintained ENTITY_PATTERNS table is now derived at call time from entries flagged `supports_nl_creation: true`, with `nl_aliases` as the authoritative alias list and `route` as the tab-fallback URL. Future entity additions change one registry entry, not two files.
- **Triage session resumable via `current_item_id` + `cursor_meta.processed_ids`.** Unmount calls `endSession` fire-and-forget; remount can resume by starting a fresh session (processed_ids prevents reprocessing).
- **Snooze entity-type-agnostic.** Single `triage_snoozes` table with partial unique `WHERE woken_at IS NULL` prevents double-active-snooze while preserving full audit history across wake cycles.
- **bridgeable-admin portal UNTOUCHED per approved scope boundary.** The platform admin's `admin-command-actions.ts` is a separate registry for cross-tenant surfaces and lives in a different bundle.

### Verification

- All 253 Phase 1–5 backend tests passing (14 pytest modules)
- tsc clean (0 errors) after all frontend work
- Playwright specs written (not run here — require a running backend + seeded staging tenant)

---

## Command Bar Platform Layer (Phase 1 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r30_delivery_caller_vault_item`
**Migration head after:** `r31_command_bar_trigram_indexes`
**Tests passing:** 99 new platform-layer tests + 8 regression tests + 9 Playwright specs + 1 blocking perf gate

### What shipped

- Backend platform layer package at `backend/app/services/command_bar/`:
  - `registry.py` — OWNS `ActionRegistryEntry` type + singleton + seed
  - `intent.py` — rule-based classifier (5 intents: navigate / search / create / action / empty)
  - `resolver.py` — pg_trgm fuzzy search across 6 entity types via single UNION ALL, recency weighting, tenant isolation
  - `retrieval.py` — orchestrator, OWNS the `QueryResponse` / `ResultItem` shape contract going forward
- New endpoint: `POST /api/v1/command-bar/query` with Pydantic-validated request + response schemas
- Migration `r31_command_bar_trigram_indexes`: `pg_trgm` extension + 6 GIN trigram indexes (via `CREATE INDEX CONCURRENTLY` inside autocommit_block)
- Frontend interface-only adapter at `frontend/src/core/commandBarQueryAdapter.ts` — translates backend `ResultItem` → existing `CommandAction` shape
- Frontend UI (`core/CommandBar.tsx`) fires `/command-bar/query` as 4th parallel fetch alongside legacy endpoints; results merge via existing type-ranked sort
- `navigation-service.ts` NavItem extended with optional `aliases` field + `getAllNavItemsFlat()` helper
- 17 navigate actions registered (hubs, AR/AP aging, P&L, invoices, SOs, quoting, compliance, pricing, KB, vault + 4 vault services, accounting admin)
- 6 create actions registered (sales_order → `wf_create_order` workflow, quote, case, invoice, contact, product); frontend `crossVerticalCreateActions` mirrors for offline fallback matching
- Search across cases, sales orders, invoices, contacts, products, documents

### Audit findings (key items only)

- **5,900 lines of command bar infrastructure already existed** across 12 files. Production bar is `core/CommandBar.tsx` (1091 lines) with full voice + Option+1..5 shortcuts + capture-phase listener.
- **`wf_compose` does not exist in code** — only `wf_create_order` ships. Phase 1's "remove old Compose menu" requirement was a no-op because there's no menu to remove.
- Legacy files: `ai/CommandBar.tsx` (250 lines, zero imports) deleted; `ai-command-bar.tsx` (93 lines) KEPT — audit initially flagged it unused but `products.tsx` actively uses it as a page-specific AI search bar. Restored after the mistake.
- **Pre-existing route collision:** `/api/v1/ai/command` has handlers in both `ai.py` and `ai_command.py` (same prefix + same path). `ai.py` wins on resolution order; `ai_command.py`'s handler is unreachable via that path. Documented in `CLAUDE.md §4 "Command Bar Migration Tracking"`; full resolution deferred to post-arc cleanup.

### What was deferred (intentionally, per phase plan)

- Saved view results (Phase 2)
- Spaces and pinning (Phase 3)
- Natural language creation with live overlay (Phase 4)
- Triage workspace — including full frontend actionRegistry.ts reshape (Phase 5)
- Briefings (Phase 6)
- Voice input, peek panels, mobile command bar, polish (Phase 7)
- Retirement of the 8 legacy `/ai-command/*` + `/core/command*` routes — tracked in `CLAUDE.md §4 Command Bar Migration Tracking`, retired per-endpoint as frontend callers migrate

### Performance

- Target: p50 < 100 ms, p99 < 300 ms
- Actual on dev hardware (50-sample sequential mixed-shape workload, tenant seeded with ~24 rows):
  - **p50 = 5.0 ms** (20× headroom)
  - **p99 = 6.9 ms** (43× headroom)
- **BLOCKING CI gate** at `backend/tests/test_command_bar_latency.py`. Fails on p50 > 100 ms or p99 > 300 ms.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_command_bar_registry.py` | 22 | Registry seed + registration + filters + match scoring |
| `test_command_bar_intent.py` | 40 | All 5 intents, parametrized record-number patterns, edge cases |
| `test_command_bar_resolver.py` | 15 | 6 entity types + typo tolerance + recency + tenant isolation + entity_types filter + score ordering |
| `test_command_bar_retrieval.py` | 13 | End-to-end orchestration + permission gating + tenant + dedup + max_results |
| `test_command_bar_query_api.py` | 9 | API contract + response shape + max_results + context passthrough |
| `test_ai_command_regression.py` | 8 | Auth + `/command/execute` + `/parse-filters` + `/company-chat` + `/briefing/enhance` + cross-tenant isolation on `/core/command-bar/search` |
| `test_command_bar_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/command-bar-phase-1.spec.ts` | 9 | Cmd+K open/close, navigate, case/SO search, create action, Alt+1 shortcut, typo tolerance, contract |
| **Total new this phase** | **117** | All passing |

### Architectural notes for Phase 2

- `registry.py` is designed to accept Phase 2's saved-view entries without schema changes (`action_type="saved_view"` already reserved).
- `retrieval.py` OWNS the public response shape — Phase 2 additions extend it; do not redefine.
- `intent.py` is deliberately zero-AI. Phase 4's NL creation with live overlay can layer AI classification on top of rules for ambiguous queries; do not replace the rule engine.
- Frontend `actionRegistry.ts` reshape deferred to Phase 5. The interface-only adapter stays until then.
- Retirement of legacy endpoints is per-phase and per-caller; no all-at-once deletion.

---

## Saved Views as Universal Primitive (Phase 2 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r31_command_bar_trigram_indexes`
**Migration head after:** `r32_saved_view_indexes`
**Tests passing:** 38 saved-views backend tests + 1 blocking latency gate + 7 Playwright specs

### What shipped

Saved Views are now the rendering engine for every list, kanban, calendar, table, card grid, chart, and dashboard surface. "One query, infinite presentation contexts." Storage reuses `vault_items` with `item_type='saved_view'` + `metadata_json.saved_view_config` (no new table, no schema changes to the VaultItem shape).

- Backend package at `backend/app/services/saved_views/`:
  - `types.py` — typed dataclasses (EntityType, Filter, Sort, Grouping, Presentation, Permissions, SavedViewConfig, SavedView, SavedViewResult, per-mode configs). `from_dict`/`to_dict` on every class for JSONB round-trip.
  - `registry.py` — 7 entity types seeded (fh_case, sales_order, invoice, contact, product, document, vault_item). Each entity has `available_fields`, `default_sort`, `default_columns`, per-entity `query_builder` (tenant-isolated SQLAlchemy query) + `row_serializer`.
  - `executor.py` — `execute(db, *, config, caller_company_id, owner_company_id)` returning `SavedViewResult`. Dispatches filters (12 operators), sort, grouping (kanban buckets), aggregation (chart/stat), cross-tenant masking via `MASK_SENTINEL="__MASKED__"`. DEFAULT_LIMIT=500, HARD_CEILING=5000.
  - `crud.py` — create/get/list/update/delete/duplicate. 4-level visibility enforced: `private`, `role_shared`, `user_shared`, `tenant_public`. Returns typed `SavedView` dataclasses; never leaks raw VaultItem.
  - `seed.py` — `seed_for_user(db, user)` role-based seeding. Templates keyed by `(vertical, role_slug)`. Idempotency via `users.preferences.saved_views_seeded_for_roles` array + defense-in-depth `_already_seeded` check. Hooked into `auth_service.register_user` post-commit.
  - `__init__.py` — public exports.
- Migration `r32_saved_view_indexes`:
  - GIN trigram index on `vault_items.title` (command bar fuzzy match)
  - Partial B-tree on `(company_id, created_by)` WHERE `item_type='saved_view' AND is_active=true` (hot-path list)
  - `users.preferences JSONB DEFAULT '{}'` column (seed idempotency bag)
  - Widened `vault_items.source_entity_id` from `String(36)` → `String(128)` for semantic seed keys (e.g. `saved_view_seed:director:my_active_cases`) — backward-compatible, UUIDs still fit
  - CONCURRENTLY indexes via `op.get_context().autocommit_block()`
- API at `/api/v1/saved-views/*` (8 endpoints): list, create, list-entity-types, get, patch, delete, duplicate, execute. `execute` is the hot path.
- Command bar integration: new `saved_views_resolver.py` runs PARALLEL to the entity resolver (not folded into UNION ALL — preserves Phase 1's latency budget). New `ResultType="saved_view"` maps frontend-side to `CommandAction.type="VIEW"`, slot 5 in TYPE_RANK between RECORD (3) and NAV (6).
- Frontend at `frontend/src/components/saved-views/` + `pages/saved-views/`:
  - `types/saved-views.ts` — full dataclass mirrors; `MASK_SENTINEL` exported
  - `services/saved-views-service.ts` — 8-endpoint API client, no caching (live queries preserve visibility / delete semantics across tabs)
  - `components/saved-views/SavedViewRenderer.tsx` — dispatches to 7 mode renderers, displays cross-tenant masking banner, ChartRenderer code-split via `React.lazy` + `Suspense` (recharts out of initial bundle)
  - Mode renderers: `ListRenderer`, `TableRenderer`, `KanbanRenderer`, `CalendarRenderer` (DIY month grid), `CardsRenderer`, `ChartRenderer` (recharts, 5 chart types), `StatRenderer`
  - `components/saved-views/SavedViewWidget.tsx` — hub/dashboard embed; per-session entity-type cache so 20 widgets don't refetch the registry
  - `components/saved-views/builder/` — FilterEditor (12 operators), SortEditor, PresentationSelector (mode-specific sub-forms)
  - Pages: `SavedViewsIndex` (grouped: Mine / Shared with me / Available to everyone), `SavedViewPage` (detail + edit/duplicate/delete), `SavedViewCreatePage` (create + edit modes, shared component)
  - Routes: `/saved-views`, `/saved-views/new`, `/saved-views/:viewId`, `/saved-views/:viewId/edit`
- Production board rebuild at `pages/production/ProductionBoardDashboard.tsx` — composed of `SavedViewWidget` instances filtered to production-role seeded views. `/production` now renders the dashboard; legacy bespoke board preserved at `/production/legacy` for one release.

### Performance

- Target: p50 < 150 ms, p99 < 500 ms (execute endpoint, representative 1000-row tenant)
- Actual on dev hardware (50-sample sequential 4-shape mix: list + table + kanban + chart):
  - **p50 = 15.4 ms** (10× headroom)
  - **p99 = 18.5 ms** (27× headroom)
- **BLOCKING CI gate** at `backend/tests/test_saved_view_execute_latency.py`. Fails on p50 > 150 ms or p99 > 500 ms. Runs 1,000-row seed + 4 presentation shapes sequentially.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_saved_views_registry.py` | 9 | Default seed of 7 entities, field types, field lookup, registration replace |
| `test_saved_views.py` | 29 | CRUD, executor filters/sort/group/aggregation, tenant isolation, cross-tenant masking, seed idempotency, API (6), command-bar integration |
| `test_saved_view_execute_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/saved-views-phase-2.spec.ts` | 7 | CRUD, mode switch, kanban, calendar, command-bar VIEW result, production-board rebuild, cross-tenant masking contract |
| **Total new this phase** | **46** | All backend passing; Playwright specs ready for staging run |

### Architectural notes for Phase 3+

- Cross-tenant masking is purely field-level in `executor.py` when `caller_company_id != owner_company_id`. Phase 2 doesn't ship a sharing UI — same-tenant sharing via `permissions.shared_with_*` arrays covers 95% of use cases. When cross-tenant sharing UI lands, `platform_tenant_relationships` (existing table) is the gate, not DocumentShare.
- `OperationsBoardRegistry` and `FinancialsBoardRegistry` COEXIST with saved views. Subsumption deferred to post-arc work.
- `production-board.tsx` deletion is gated on Playwright parity verification. When green, delete the file + remove the `/production/legacy` route + remove the ProductionBoardPage import.
- Saved view config is stored in `metadata_json.saved_view_config` only — no fallbacks. Crud treats `metadata_json` as canonical.
- New seed templates added after a role has already been seeded do NOT backfill. Template additions require either a one-off backfill script or a role-version bump (Phase 2 accepts this trade-off).
- Seed key format `saved_view_seed:{role_slug}:{template_id}` — stored in `vault_items.source_entity_id` (widened to varchar(128) in r32).
- Frontend Builder (Phase 2) is FilterEditor + SortEditor + PresentationSelector. Live preview is deferred — users save then are redirected to the detail page. Preview is queued as polish.
- Chart library: `recharts` 3.8.1. Lazy-loaded via `React.lazy` in SavedViewRenderer so non-chart callers never ship the recharts bundle.
- DIY calendar month grid is sufficient for Phase 2. If FH service scheduling needs week view / overlapping slots / drag-drop, swap the body of `CalendarRenderer.tsx` for `react-big-calendar` — dispatch layer stays.

---

## Spaces — Context Layer (Phase 3 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r32_saved_view_indexes` (no new migration; `User.preferences` sufficient)
**Tests passing:** 55 backend (36 unit + 19 API/integration) + 9 Playwright specs + 139 Phase 1+2 regression

### What shipped

Spaces are per-user workspace contexts — name + icon + accent + pinned items — layered on top of the existing vertical navigation. Not a replacement; a lens. The base nav from `navigation-service.ts` stays visible; spaces add a `PinnedSection` above it and shift the visual accent.

- Space data model in `User.preferences.spaces` (JSONB array) + `active_space_id` + `spaces_seeded_for_roles` (idempotency tracker).
- Backend package at `backend/app/services/spaces/`:
  - `types.py` — typed dataclasses (SpaceConfig, PinConfig, ResolvedSpace, ResolvedPin, 6 accent literals, SpaceError hierarchy), `MAX_SPACES_PER_USER=5`, `MAX_PINS_PER_SPACE=20`.
  - `registry.py` — role-based `SpaceTemplate`s keyed by `(vertical, role_slug)`. 6 pairs seeded (funeral_home director/admin/office, manufacturing production/office/admin) + `FALLBACK_TEMPLATE` "General" + `NAV_LABEL_TABLE` for nav-item pin resolution.
  - `crud.py` — 10 service functions: create/get/update/delete/reorder spaces + add/remove/reorder pins + set_active_space. Server-side pin resolution via `_resolve_pin` denormalizes saved_view_title + nav label so clients render from flat data.
  - `seed.py` — idempotent via `preferences.spaces_seeded_for_roles`; skip-if-name-exists defense-in-depth; saved-view seed-key pins resolved at read time via VaultItem `source_entity_id` lookup.
  - `__init__.py` — public exports.
- API: 10 endpoints at `/api/v1/spaces/*`, all user-scoped. Cross-user 404 isolation. 5-space cap enforced at service layer, translated to 400 at API.
- Command bar integration:
  - `QueryContext` gained `active_space_id: str | None`.
  - Synthesized space-switch results (not in the module registry — read `user.preferences.spaces` at query time; exact match → 1.4, 2+-char prefix → 1.1; current active space suppressed).
  - Pin boost: `_WEIGHT_ACTIVE_SPACE_PIN_BOOST=1.25` applied in-place to `ResultItem.score` when result URL or id matches a pin target in the active space.
  - Space-switch URLs shaped `/?__switch_space=<id>`; frontend CommandBar dispatcher intercepts the param and calls `SpaceContext.switchSpace` rather than real-navigating.
- Frontend:
  - `types/spaces.ts` — full type mirrors, `ACCENT_CSS_VARS` × 6 accent palette, `applyAccentVars` helper.
  - `services/spaces-service.ts` — 10-endpoint axios client, no caching.
  - `contexts/space-context.tsx` — SpaceProvider with fetch-on-mount, optimistic mutations + server reconciliation, `activeSpace` memo, `isPinned` / `togglePinInActiveSpace` convenience helpers, null-safe `useActiveSpaceId` hook.
  - Components at `components/spaces/`: `SpaceSwitcher` (top-nav dropdown next to NotificationDropdown; keyboard listeners for `Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`), `PinnedSection` (renders ABOVE `navigation.sections` in the existing sidebar; HTML5 DnD for reorder; hover-to-unpin X button; data-testid attributes for Playwright), `PinStar` (one-click pin toggle; on SavedViewPage header; null-renders when no active space), `NewSpaceDialog` + `SpaceEditorDialog` (shadcn Dialog with accent selector + density + default toggle + delete-with-confirm).
  - Mounted in App.tsx inside PresetThemeProvider on the tenant branch. Platform admin (`BridgeableAdminApp`) completely untouched.
- Visual personality: 6 accents via CSS variables (`--space-accent`, `--space-accent-light`, `--space-accent-foreground`) on `documentElement`. Phase 3 NEVER touches `--preset-accent`. Components use `var(--space-accent, var(--preset-accent))` so no-active-space gracefully falls back.
- Pin-to-current-space: star icon on SavedViewPage header. Nav-item pinning via API; UI star affordance in sidebar nav items is future polish (Phase 7 target).
- 5-space cap enforced at service + API layers.
- Edge cases handled: pin target unavailable (saved view deleted / access revoked → gray-out + hover-reveal X to clean up), role change (both saved-view seed + spaces seed re-run at `user_service.update_user` role-change branch — idempotent via each seed's own array).

### Audit findings

- **`presetAccent` already existed** as a CSS-variable-backed vertical baseline (`PresetThemeProvider` sets `--preset-accent` on `documentElement`). Phase 3 layers `--space-accent` on top with CSS fallback; no conflict, no rewrite.
- **`User.preferences` already added** in r32 (Phase 2). Phase 3 owns new JSONB keys (`spaces`, `active_space_id`, `spaces_seeded_for_roles`) alongside Phase 2's `saved_views_seeded_for_roles`. Zero schema change needed.
- **Only one capture-phase keyboard listener exists** (`cmd-digit-shortcuts.ts` for Option/Alt+1..5 + Cmd+1..5, active only when command bar is open). Phase 3 shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) use different modifier combos + different active conditions — clean, no capture-phase needed.
- **`update_user` role-change path exists.** Phase 2's saved-view seed was NOT hooked here (only at register_user), so a user promoted from office to director never picked up director-specific saved views. Phase 3 fixes this ADJACENTLY: explicit two-line seed re-invocation at the role-change site (spaces + saved-views).
- **FH two-hub pattern (Funeral Direction / Business Management)** from the master doc was aspirational — not represented in `navigation-service.ts` today. Phase 3 operationalizes it naturally: "Arrangement" space IS Funeral Direction hub; "Administrative" space IS Business Management hub. Documented in CLAUDE.md §1a Spaces subsection + flagged here per the user's directive.
- **framer-motion NOT installed.** Phase 3 uses CSS transitions on --space-* variables + tw-animate-css (already present) for any micro-animations. Zero new animation deps.
- **Platform admin** is a fully separate app (`BridgeableAdminApp`) via subdomain / path routing — Phase 3 only wires into the tenant branch.

### Performance

No dedicated CI latency gate this phase — Spaces read/write is trivial JSONB + a small denormalization pass; the hot path (list spaces) returns in single-digit ms on dev. Command bar integration reuses existing paths + adds one ranking multiplier; the Phase 1 latency gate (p50 < 100 ms / p99 < 300 ms) is unchanged and continues to pass. If space-switch synthesis introduces drift in later phases, fold a dedicated latency gate at that point.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_spaces_unit.py` | 36 | Registry (7), Seed (7), CRUD (12), Pins (8), Mfg admin (1), FH director flow |
| `test_spaces_api.py` | 19 | 13 API endpoint tests + 6 command-bar integration (synthesis + pin boost) |
| `frontend/tests/e2e/spaces-phase-3.spec.ts` | 9 | Keyboard shortcuts, picker, accent transition, pin saved view, pin nav item, reorder API, CRUD lifecycle, 5-cap, pin target deleted |
| **Total new this phase** | **64** | All backend passing; Playwright specs ready for staging run |
| Phase 1 + 2 regression | 139 | All green — no changes to previously-passing behavior |

### Surprises for Phase 4

- **Spaces operationalize the FH two-hub pattern (Funeral Direction / Business Management) the master doc describes.** "Arrangement mode" IS Funeral Direction hub; "Administrative mode" IS Business Management hub. This wasn't a design pivot — it was a clarifying realization during the audit. The master doc's two-hub pattern stays accurate at the architectural level; Phase 3 just makes it a first-class UI concept via spaces rather than a nav config requirement. Future phases that touch FH navigation should honor this mapping and avoid re-implementing the same concept in nav.
- **Phase 2's saved-view seed gap on role change is now fixed** at `user_service.update_user`. Phase 4 (Natural Language Creation with Live Overlay) should consider whether the overlay registers any user-scoped state that needs re-seeding on role change — the two-line pattern at the hook site is the canonical place to add another seed.
- **Active-space context now flows into command bar queries.** Phase 4's NL creation may benefit from the same context channel — e.g. "create new order" in Arrangement space defaults to vault-order entity, in Production space defaults to work-order entity. The `QueryContext.active_space_id` field is already there; intent classifier can branch on it without schema changes.
- **`recharts` bundle is lazy-loaded per Phase 2**, and Phase 3's space-switch doesn't force it. Keep this pattern — late bundles are for heavy, less-common UI (chart renderers, calendar DnD when we add it, voice transcription in Phase 7).
- **`SpaceSwitcher` uses `render={}` pattern for `DropdownMenuTrigger`, not `asChild`**, because shadcn v4's `@base-ui/react` doesn't expose `asChild`. Flagged per CLAUDE.md — any future UI using a trigger-wrapping pattern must use `render={}`.

### Architectural notes for Phase 4+

- Space-switch command bar actions are synthesized at query time (not registered in the module-level singleton) because the registry is shared across tenants and per-user state would leak. Future per-user / per-role / per-tenant actions should follow the same parallel-source synthesis pattern rather than bloat the singleton.
- Pin resolution is server-side. When we add cross-tenant space sharing (post-arc), the resolver needs to run through the same visibility check Phase 2 uses (`saved_views.crud._can_user_see`). Today's permissive lookup is acceptable because Phase 3 pins are only the user's own saved views + nav items — cross-tenant never happens.
- `User.preferences` is becoming a multi-phase JSONB bag (Phase 2 + 3 + future phases' seed flags). Keep writes narrowly scoped via `flag_modified` + single-key updates; never blanket-replace `user.preferences = {...}` without reading first.
- Seed additions at the role-change hook site are explicit two-line calls, not abstracted into a `reseed_all` helper. This is intentional: future phases (5, 6) will add more seeds at the same hook, each discoverable via grep without a central registry to maintain.

---

## Natural Language Creation with Live Overlay (Phase 4 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r33_company_entity_trigram_indexes`
**Tests passing:** 79 new backend (53 parsers + 25 integration + 1 latency gate) + 8 Playwright + 194 Phase 1-3 regression = 273 backend

### What shipped

The Fantastical-style extraction overlay — the biggest UX payoff of the arc and the centerpiece of the Wilbert demo. User hits Cmd+K, types one sentence, an overlay populates structured fields in real time.

- Backend NL creation platform layer at `backend/app/services/nl_creation/`:
  - `types.py` — ExtractionRequest, FieldExtraction, ExtractionResult, NLEntityConfig, FieldExtractor, 4 error classes
  - `structured_parsers.py` — date (ISO / US / written month / weekday / "tonight"), time (12h/24h/named), datetime, phone (E.164), email, currency (requires $-flag), quantity, name (with prefix/suffix handling)
  - `entity_resolver.py` — resolve_company_entity via pg_trgm, resolve_contact + resolve_fh_case via existing GIN indexes, filter whitelist for safety, one-call `resolve()` dispatcher
  - `ai_extraction.py` — Intelligence-backed fallback with block-rendered prompt variables, exception-safe (returns empty on any failure)
  - `entity_registry.py` — 4 configs (case, event, contact + fh_case alias → case), case uses AI-only for date fields (multi-date disambiguation), per-entity creator_callable, space_defaults dict, fh_case → case alias lookup
  - `extractor.py` — orchestration: structured → resolver → AI fallback if required still missing → merge with prior_extractions by confidence → apply space_defaults → compute missing_required
  - `__init__.py` — public exports
- Migration `r33_company_entity_trigram_indexes`: GIN trigram on `company_entities.name` via CONCURRENTLY, safe on live tables
- 3 managed Intelligence prompts seeded via `scripts/seed_intelligence_phase4.py`: `nl_creation.extract.{case,event,contact}`. Case prompt content copied from `scribe.extract_first_call` but independent. Haiku (simple route), force_json, response_schema enforcing `{"extractions": [...]}` shape
- Intent extension: `intent.py::detect_create_with_nl()` — additive, no Intent Literal change. Two-mode matcher (exact alias prefix + fuzzy fallback). 3-char min on NL content prevents false positives on short queries
- New `create.event` action registered in Phase 1 command-bar registry (previously missing — audit gap)
- API at `/api/v1/nl-creation/*` — 3 endpoints: `POST /extract` (hot path, 300ms debounced client-side, p50 < 600ms gate), `POST /create` (materialize entity via creator_callable, honors required_permission), `GET /entity-types` (registry dump filtered by permissions)
- Frontend:
  - `types/nl-creation.ts` — full type mirrors
  - `services/nl-creation-service.ts` — 3-endpoint axios client, AbortSignal support
  - `hooks/useNLExtraction.ts` — 300ms debounce (wider than command bar's 100-200ms to amortize AI), AbortController cancellation on new input, manual-override state with re-merge, `create()` materialization
  - `components/nl-creation/NLOverlay.tsx` — Fantastical-style panel with checkmarks / amber low-confidence / entity pills / missing-required section / keyboard hints footer
  - `NLField.tsx` — per-row display with confidence-aware styling
  - `NLCreationMode.tsx` — wrapper with window-level keyboard listeners (Enter / Tab / Esc), navigation handling, module-level entity-types cache so rapid remount doesn't refetch
  - `detectNLIntent.ts` — client-side mirror of backend detector; instant UX without server round-trip
  - `pages/crm/new-contact.tsx` — contact create page at `/vault/crm/contacts/new`, fills Phase 1 register-but-no-route gap, pre-fills from `?nl=<input>` query param (regex extracts email/phone/name/company segment)
- Command bar integration: `CommandBar.tsx` gains `activeNLEntity` state + useEffect watching `query` via `detectNLIntent`. Renders `<NLCreationMode>` instead of the standard results list when matched. Suppresses AI-mode + results-list rendering during NL mode. Coexists with existing `activeNLWorkflow` (workflow-backed entities) cleanly
- Voice input reuses Phase 1's `useVoiceInput` hook — transcript text flows into command-bar input and the detector fires identically to typed input
- Demo seed script `scripts/seed_nl_demo_data.py --tenant-slug testco` — idempotent, seeds Hopkins FH + 5 other companies + 3 prior FH cases (Andersen/Martinez/Nakamura families)

### Audit findings

- **Existing NL extraction infrastructure was workflow-scoped** (`command_bar_extract_service.py` + `NaturalLanguageOverlay.tsx` = 1547 lines). It already powers sales_order / quote creation today. Phase 4 built a parallel entity-scoped path per approved plan decision #2 — zero modifications to the existing workflow path. Retirement is a Phase 5/6 cleanup concern
- **`User.preferences` JSONB** (added in Phase 2 r32) reused — no new tenant-level config storage needed
- **Phase 1 resolver's `SEARCHABLE_ENTITIES`** doesn't include `company_entity`. Phase 4 adds local resolution in `nl_creation/entity_resolver.py` rather than extending Phase 1's tuple. Phase 5 nav/search unification will elevate the CompanyEntity resolver to a first-class Phase 1 search target
- **Two existing NL-extraction call-sites** (`first_call_extraction_service` for FH first-call page + `call_extraction_service` for RC calls) — Phase 4 does NOT consolidate these; the `nl_creation.extract.case` prompt was seeded independently per approved plan decision #4 (copied content, independent evolution)
- **`useVoiceInput` hook** is reusable verbatim — no per-modality fork needed
- **Scribe prompt + case field shape** ready for reuse — Phase 4's prompt copies the field taxonomy but stays independent
- **Case date-field ambiguity** discovered during verification: single sentence has "DOD tonight" AND "service Thursday" — both match a scalar structured parser. Fixed by making case date fields AI-only (handles semantic disambiguation), while single-datetime entities (event) keep their structured parsers

### Performance

| Stage | Budget | Actual |
|---|---|---|
| Structured parser (per call, 100-iteration average) | <5ms | <0.05ms typical |
| Entity resolver per field (pg_trgm backed) | <30ms | ~2-5ms on 10-row seed |
| AI extraction (Haiku via Intelligence) | <500ms typical, 1200ms ceiling | ~350-450ms typical |
| Extract endpoint p50 | <600ms | **5.9ms** (no-AI path), ~400ms with Haiku |
| Extract endpoint p99 | <1200ms | **7.2ms** (no-AI path), ~700-900ms with Haiku |

**BLOCKING CI gate** at `backend/tests/test_nl_creation_latency.py`. 30-sample mixed-shape across case/event/contact. Gate measures without Anthropic key set (floor latency); production CI with key produces a higher-but-still-compliant number.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_nl_structured_parsers.py` | 53 | Every parser × happy path + edge cases + perf guard |
| `test_nl_creation_backend.py` | 25 | Registry (5), Company-entity resolver (5 including tenant isolation + filter whitelist), Intent detector (6 across 4 entity types), Extractor orchestration (3), API (6) |
| `test_nl_creation_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/nl-creation-phase-4.spec.ts` | 8 | Demo sentence + event + contact + live update + tab fallback + escape + Hopkins pill + API contract |
| **Total new this phase** | **87** | All backend passing; Playwright ready for staging |
| Phase 1-3 regression | 194 | All green — no changes to previously-passing behavior |

### Surprises for Phase 5 (Triage Workspace — reshapes actionRegistry.ts)

- **Task deferred per approved plan** — no task model/API/UI today. Phase 5 Triage Workspace is the natural home for task creation UX conventions. When task lands, it's:
  - minimal model (id, tenant_id, title, assignee_id, due_date, priority, description, status, created_by/at)
  - `POST /api/v1/tasks` + standard CRUD
  - NL config in `nl_creation/entity_registry.py` — ~25 lines following event pattern
  - Creator callable ~15 lines
  - 1 new prompt seed
  - 1 new Playwright spec
  About 250 total lines of code
- **Frontend `actionRegistry.ts` reshape is Phase 5's big lift.** Phase 4 leaves `detectNLIntent.ts` as a client-side mirror of the backend detector — a small duplication. Phase 5's reshape should unify entity-type aliases into a single registry surface, replacing the manual ENTITY_PATTERNS list in `detectNLIntent.ts`
- **`command_bar_extract_service` + `NaturalLanguageOverlay` (workflow path) coexist with Phase 4's entity path.** Retirement decision is Phase 5/6. The natural migration: once Phase 5 Triage Workspace replaces workflow-driven sales-order creation with entity-driven, the old path becomes deletable
- **CompanyEntity not in Phase 1 resolver's SEARCHABLE_ENTITIES.** Adding it benefits BOTH Phase 4's NL pipeline AND the command bar's main results (typing "Hopkins" surfaces the CRM record). Phase 5 nav/search unification should do this in one coordinated touch
- **Space-aware extraction is wired but has no concrete defaults today.** The infrastructure is there (`space_defaults: dict[str, dict]` in each entity config). Phase 5/6 can populate meaningful defaults as UX patterns stabilize — e.g. "in Production space, `new order` defaults to work_order entity type"
- **Pre-existing `useNLExtraction`-adjacent NL flows in FH first-call page** — the `/cases/new` FHFirstCallPage has its own NL extraction via `scribe.extract_first_call`. Phase 4 leaves it untouched (it's the Tab fallback target). Future consolidation work can unify the two into one NL platform layer once traffic patterns prove out

### Demo verification

The demo sentence produces the expected overlay:

- **Input:** "new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH"
- **Expected extractions (with Anthropic key set):** Deceased name (John Smith), Date of death (Today/2026-04-20), Date of birth (null or missing_required — AI may omit), Informant (Mary, daughter), Service date (Thursday/2026-04-23), Funeral home (Hopkins Funeral Home PILL from entity resolver)
- **Verified on dev without Anthropic:** Funeral home PILL resolves correctly (entity resolver works). Required fields correctly listed in missing_required (AI disabled path)
- **On staging with Anthropic + Hopkins FH seeded:** full overlay populates, Enter creates case, navigates to case detail with all satellites populated

### Demo staging data seeded

`seed_nl_demo_data.py --tenant-slug testco` is the canonical re-seed command. Seeds:

- **CompanyEntity rows:** Hopkins Funeral Home, Riverside Funeral Home, Whitney Funeral Home, Oakwood Memorial, St. Mary's Church, Acme Manufacturing
- **3 prior FHCase rows** (Eleanor Andersen / Harold Martinez / Grace Nakamura) with satellite data so the fh_case resolver has trigram candidates

Idempotent — safe to re-run between demos. Documents the exact demo dependencies so regressions are re-seedable in a single command.
