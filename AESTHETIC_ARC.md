# Bridgeable Aesthetic Arc

Companion arc to the Workflow Arc. Where Workflow Arc ships functional capability, Aesthetic Arc ships the design language — the felt quality of the platform. Both run in parallel and compose cleanly at the seam.

**Source of truth:** [`DESIGN_LANGUAGE.md`](DESIGN_LANGUAGE.md) at project root. Every value in this arc's implementation derives from that document. When prose in DESIGN_LANGUAGE.md and prose here disagree, DESIGN_LANGUAGE.md wins.

---

## Purpose and scope

Bridgeable's design language is **not** a theme — it's the platform's identity expressed visually. Two moods (Mediterranean garden morning and cocktail lounge evening), one architectural color thread (deepened terracotta `#9C5640`, single value across both modes — see DESIGN_LANGUAGE §2 cross-mode rule), and an underlying meta-anchor of deliberate restraint.

The Aesthetic Arc's job is to take DESIGN_LANGUAGE.md from document to shipped surface. Six sessions. Each session is infrastructure, visual, or verification — distinct from the others so scope stays clean and regressions stay localized.

**What the arc does NOT do:**
- Workflow Arc migrations (those have their own arc; 8a–8h).
- Functional capability changes (no new features).
- Feature parity breaks for existing components (component visual refresh is progressive; existing surfaces may look and behave unchanged through Session 3).
- Rewrites of the application layer.

---

## Arc structure — Phase I → Phase II → Phase III

Phase I shipped primitive-level aesthetic (4 sessions). Platform-wide page-level audit surfaced ~8,000 moderate issues concentrated in 200+ pages. Arc restructured into three phases.

### Phase I — Primitive refresh (✅ Complete)

| Session | Status | Scope |
|---|---|---|
| 1 — Token foundation | ✅ Shipped | CSS variables, Plex fonts, Tailwind v4 `@theme inline` extensions, mode-switching mechanism. Infrastructure only; no visual refresh. |
| 2 — Core component refresh | ✅ Shipped | Buttons, inputs, cards, modals, dropdowns, navigation + `--font-sans` flip to Plex + Geist removal. First observable visual change; entire platform now renders in IBM Plex Sans. |
| 3 — Extended component refresh + status treatment | ✅ Shipped | 6 net-new primitives (Alert, StatusPill, Tooltip, Popover, FormSection, FormSteps) + 11 primitive refreshes (Badge+status, Table, Tabs, Separator, Avatar, Switch, Radio, Skeleton, EmptyState, InlineError, Sonner) + 6 ad-hoc surface refreshes. `next-themes` removed. 0 primitives remain in shadcn aesthetic. |
| 4 — Dark mode verification | ✅ Shipped | Every refreshed component verified in dark mode + WCAG 2.2 AA verified. Surgical token adjustments (status-muted backgrounds, focus-ring alpha) + 3 component fixes + 1 new feature (branding editor Light/Dark preview toggle + WCAG readout). |

### Phase II — Platform-wide page correctness (🟡 In progress)

| Batch | Status | Scope |
|---|---|---|
| Audit v1 | ✅ Shipped | Platform-wide page-level bypass pattern survey. 414 `bg-white` + 2,886 `text-muted-foreground` + ~5,000 Tailwind color utilities + 109 emoji found across 305 page files. P0/P1/P2/P3 categorized. Batch structure proposed. |
| **0 — Shadcn default aliasing** | ✅ **Shipped** | One-file micro-session on `frontend/src/index.css`. All shadcn `:root` + `.dark` semantic tokens aliased to DESIGN_LANGUAGE equivalents. 3,596 shadcn-default consumers auto-shift to warm palette without component edits. Resolves MFG dashboard onboarding banner. |
| Audit v2 (re-audit) | ✅ Shipped | Post-Batch-0 visual verification surfaced 7 additional blocking pages. Batch 1 expanded + split into 1a/1b/1c-i/1c-ii. Severity attribution methodology documented. |
| **1a — Infrastructure + user-reported + agents family** | ✅ **Shipped** | 8 files, ~450 LOC. WidgetWrapper blast-radius fix (Operations Board + Vault Overview inherit) + WidgetPicker + operations-board-desktop + AgentDashboard + ApprovalReview + MFG dashboard + FH dashboard. Zero runtime Tailwind bypass across all 8 files post-batch. |
| **Nav Bar Completion (micro-session)** | ✅ **Shipped** | Between 1a and 1b. DotNav comment-code mismatch fix + visible ModeToggle (Sun/Moon) in AppLayout top header. Reuses existing `theme-mode.ts` runtime API + flash-mitigation script; just adds the UI button + `useMode()` ergonomic alias. Verification methodology update: all Phase II batches from now on verified in BOTH light AND dark mode. |
| 1b — Scheduling board family | ⬜ Queued | scheduling-board + kanban-panel + ancillary-panel + direct-ship-panel. InlineError primitive migration for error state. 📦/⛪/🏛/⚰/📍 emoji → Lucide. ~550 LOC. |
| 1c-i — Order Station | ⬜ Queued | Single file, 144 Tailwind hits. Primary MFG order-entry surface. ~400 LOC. |
| 1c-ii — Financials Board + Team Dashboard | ⬜ Queued | financials-board (193 Tailwind hits, platform's largest offender) + team-dashboard (129 hits). ~500 LOC. |
| 2 — Remaining P0 demo critical path | ⬜ Queued | 4 hub pages, `urn-catalog` family, `case-detail` family, `BriefingPage`, `CallOverlay`, `EntityTimeline`. |
| 3 — P1 high visibility | ⬜ Queued | CRM family (+ emoji health indicators), production family, invoices, customer-detail, reports, delivery family, knowledge-base. |
| 4 — P2 safety + vault + vendors | ⬜ Queued | Safety family, vault accounting tabs, vendor family. |
| 5 — P2 onboarding + admin + pricing | ⬜ Queued | Onboarding flow, platform-admin, pricing, announcements, legacy studio. |
| 6 — P3 long-tail | ⬜ Deferred | 117 small-footprint pages (1-10 bypass hits). Deferred to natural refactor per Phase I Session 3 convention. |

### Phase III — Motion + QA (⬜ Pending)

| Session | Status | Scope |
|---|---|---|
| 5 — Motion pass | ⬜ Queued | Apply `ease-settle` / `ease-gentle` + named durations consistently. Hover, focus, modal/dropdown entrances, toast arrivals. |
| 6 — Accessibility + QA across all surfaces | ⬜ Queued | Full WCAG 2.2 AA verification. Contrast automation. Keyboard navigation. Reduced-motion spot checks. Screen reader pass. Long-tail focus-ring-accent light-mode alpha fix. |

---

## Session 1 — Token Foundation (✅ Shipped)

**Date:** 2026-04-21  
**Migration head:** `r37_approval_gate_email_template` (unchanged — frontend-only session).  
**Tests:** no new tests; 308 Phase 1–8c backend + 165 frontend vitest continue passing. TypeScript build clean, production build clean.

### What shipped

Four new CSS files under `frontend/src/styles/`:

- **`tokens.css`** — every DESIGN_LANGUAGE Section 9 token as a CSS custom property. `:root` block for light mode (the default); `[data-mode="dark"]` block for dark mode overrides. Covers surfaces, content, borders, shadows, accents (brass), status (error/warning/success/info + `-muted` variants), typography (size scale + font families), radii, motion (durations + easings), max-widths.
- **`fonts.css`** — `@fontsource-variable/ibm-plex-sans` (variable 100-700) + `@fontsource/ibm-plex-serif/500.css` + `@fontsource/ibm-plex-mono/400.css`. Self-hosted; no Google Fonts CDN.
- **`base.css`** — `prefers-reduced-motion` collapse, dark-mode font smoothing, brass focus-visible utility class `.focus-ring-brass`, explicit `@utility duration-*` declarations for Tailwind v4 (the `--duration-*` namespace doesn't auto-generate utilities in v4).
- **`globals.css`** — entry point bundling the above three.

One new TypeScript module:

- **`frontend/src/lib/theme-mode.ts`** — programmatic API (`getMode`, `setMode`, `toggleMode`, `clearMode`) + React hook (`useThemeMode`) that subscribes to custom-event dispatches and system `prefers-color-scheme` changes. No toggle UI ships in Session 1; this is the API Session 2's settings UI will consume.

Two files modified:

- **`frontend/src/index.css`** — imports the new globals.css bundle, extends `@custom-variant dark` to match both `.dark` and `[data-mode="dark"]`, extends the `@theme inline` block with DESIGN_LANGUAGE utility bindings, updates legacy `--status-success/warning/info/danger` values from hex to DESIGN_LANGUAGE oklch (drift accepted).
- **`frontend/index.html`** — adds synchronous inline `<script>` in the `<head>` for flash-of-wrong-mode prevention. Runs before any CSS parses; sets `data-mode="dark"` from `localStorage['bridgeable-mode']` or `prefers-color-scheme` fallback.

### Tailwind utilities now available (Session 1 surface)

| Category | Utilities |
|---|---|
| Surfaces | `bg-surface-{base,elevated,raised,sunken}` |
| Content | `text-content-{strong,base,muted,subtle,on-brass}` |
| Borders | `border-border-{subtle,base,strong,brass}` |
| Brass | `bg-brass`, `bg-brass-{hover,active,muted,subtle}` (+ `text-`, `border-`, `ring-` prefixes) |
| Status | `text-status-{error,warning,success,info}`, `bg-status-{error,warning,success,info}-muted` |
| Fonts | `font-plex-{sans,serif,mono}` |
| Type scale | `text-{display-lg,display,h1..h4,body,body-sm,caption,micro}` (each with paired line-height + font-weight) |
| Radii | `rounded-{base,full}` (supplements existing `rounded-sm/md/lg/xl/2xl/3xl/4xl`) |
| Shadows | `shadow-level-{1,2,3}` (dark-mode top-edge highlight automatic) |
| Durations | `duration-{instant,quick,settle,arrive,considered}` (100ms/200ms/300ms/400ms/600ms) |
| Easings | `ease-{settle,gentle}` (DESIGN_LANGUAGE cubic-beziers) |
| Max-widths | `max-w-{reading,form,content,wide,dashboard}` (34/40/56/72/96rem) |
| Focus | `.focus-ring-brass` utility class (apply to interactive elements) |

### Architectural decisions recorded

1. **Tailwind v4 `@theme inline` over JS config** — DESIGN_LANGUAGE.md Section 9 shows a Tailwind v3-style `tailwind.config.js`; Session 1 translates each entry to `@theme inline` in `frontend/src/index.css`. Per approval decision 6.
2. **shadcn token coexistence** — existing shadcn CSS variables (`--background`, `--foreground`, `--primary`, `--card`, `--popover`, `--muted`, `--destructive`, `--border`, `--input`, `--ring`, `--sidebar*`, `--chart-*`, `--radius`, `--accent`) remain untouched. DESIGN_LANGUAGE tokens live alongside. Sessions 2–3 migrate component references; cleanup session retires shadcn layer. Per approval decision 8.
3. **`--font-sans` untouched** — Plex loaded under new names `--font-plex-{sans,serif,mono}`. Geist continues as the platform default until Sessions 2–3 migrate per-component. Per approval decision 1.
4. **`--radius-xl` +2px drift accepted** — current `calc(var(--radius) * 1.4) = 14px`; DESIGN_LANGUAGE = 16px. `rounded-xl` renders 2px larger post-Session-1. Sub-perceptual; no retune needed. Added `--radius-base: 6px` + `--radius-full: 9999px` as new names. Per approval decision 2.
5. **Status color drift accepted in Session 1** — existing `--status-{success,warning,info,danger}` values migrated from hex (generic shadcn defaults) to DESIGN_LANGUAGE oklch. The only one-off visual change this session. Session 6 QA verifies. Per approval decision 3 override.
6. **Dark-mode selector coexistence** — `@custom-variant dark (&:is(.dark *, [data-mode="dark"] *))` matches both. `.dark` class is noop today (never set); `[data-mode="dark"]` is the canonical switch going forward. Post-arc consolidation retires `.dark`. Per approval decision 4.
7. **No visible mode toggle UI** — Session 2's settings refresh owns it. Session 1 ships the runtime API only. Per approval decision 5 / Session 2 scope.
8. **Verification via inline devtools patch** — no temporary test routes shipped; manual verification by setting `data-mode` in devtools console. Per approval decision 5.
9. **Plex Sans variable, Serif/Mono non-variable** — only `@fontsource-variable/ibm-plex-sans` exists; `@fontsource-variable/ibm-plex-serif` + `-mono` don't exist on npm. Variable where possible, specific-weight packages where not. Per approval decision 10.
10. **Phase 3 Spaces accent system orthogonal** — `--space-accent` + `--space-accent-light` + `--space-accent-foreground` (per-user-space tenant accent, 6 palettes) and `--accent-brass` + variants (platform primary) coexist cleanly. Conceptual relationship ("when do I reach for space accent vs. brass?") is Phase 8e/9 design question, not Aesthetic Arc scope. Per approval decision 9.

### Verification performed

- ✅ `npm run build` clean (5s build time, 200KB gzip-30KB CSS, 4.7MB JS including chart lib).
- ✅ `tsc -b` clean.
- ✅ `npm test` — 11 test files, 165/165 vitest green.
- ✅ Backend regression — 308/308 Phase 1-8c tests green.
- ✅ Production CSS contains **134** `[data-mode=dark]` selectors (minified form) — mode switching scope lands correctly.
- ✅ `--surface-base` light value `oklch(94% .018 82)` and dark value `oklch(16% .012 65)` both present in minified CSS.
- ✅ Plex `.woff2` files bundled (16 files across latin / latin-ext / cyrillic / greek / vietnamese subsets; regular + italic variable axes for Sans; 500 weight for Serif; 400 weight for Mono). Geist `.woff2` continues to bundle alongside.
- ✅ Tailwind utility generation probe verified every new class: `bg-surface-base`, `bg-brass`, `text-content-strong`, `shadow-level-1`, `rounded-base`, `rounded-full`, `duration-quick`, `ease-settle`, `font-plex-sans`, `max-w-reading`, `text-h1`, `text-display`, `border-border-brass`, `text-status-error`, etc.
- ✅ Flash-prevention inline script present in `index.html` head; no linting issues.
- ✅ Dev server starts clean (Vite hot-reload unaffected).

### Deferred to Sessions 2–6

- Visible mode toggle UI (Session 2 — settings refresh).
- Component visual refresh: buttons/inputs/cards/modals/dropdowns/navigation (Session 2).
- Component visual refresh: toasts/alerts/badges/tables/forms (Session 3).
- Dark mode visual verification across refreshed components (Session 4).
- Motion pass applying `ease-settle`/`ease-gentle` + named durations platform-wide (Session 5).
- Full WCAG 2.2 AA accessibility audit (Session 6).
- Retiring shadcn tokens after all component refactors complete (post-Session-6 cleanup).
- Resolving the Phase 3 Spaces accent vs. brass accent conceptual question (Phase 8e/9 design work).

---

## Session 2 — Core Component Refresh (✅ Shipped)

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — frontend-only session).
**Tests:** no new tests; 165/165 vitest + 171/171 Phase 8a-8d.1 backend regression continue passing. `tsc -b` clean. Production build clean (5.02s).

### What shipped

**14 files modified.** Estimated LOC touched: ~480 lines across component class strings + CSS imports + package.json.

**Core UI primitives (8 files, ~200 modified lines):**
- `src/components/ui/button.tsx` — 6 variants (default/outline/secondary/ghost/destructive/link) on DESIGN_LANGUAGE tokens. Primary = `bg-brass` + `text-content-on-brass` + `shadow-level-1`. Focus ring flips from gray to brass platform-wide (via `focus-ring-brass` utility from Session 1). Radius = `radius-base` (6px) per Q1 audit decision. 8 sizes preserved (default/lg/sm/xs + 4 icon variants — documented as "compact-dense legacy" for the 4 xs sizes; prefer default/sm for new work).
- `src/components/ui/label.tsx` — `text-body-sm font-medium text-content-base`. UI label role per §4 size-weight pairings.
- `src/components/ui/input.tsx` — shell: `bg-surface-raised` + `border-border-base` + `rounded` + `py-2.5 px-4`. Focus: `border-brass` + `ring-2 ring-brass/30` subtle glow (Q9 canonical §9 form). Invalid: `border-status-error` + `ring-status-error/20`. Disabled: `bg-surface-sunken` + `text-content-subtle`.
- `src/components/ui/textarea.tsx` — identical shell to Input with `min-h-20` (80px) for multiline generous-default per §5.
- `src/components/ui/select.tsx` — 10 sub-components. Trigger shares Input shell. Content popup: `bg-surface-raised` + `border-border-subtle` + `rounded-md` (8px) + `shadow-level-2` + `p-2` + `duration-settle ease-settle` open / `duration-quick ease-gentle` close. Items: `rounded-sm` pill + `bg-brass-subtle` on hover/focus + `text-brass` checkmark on selected.
- `src/components/ui/card.tsx` — `bg-surface-elevated` + `rounded-md` (Q2: 8px default; 12px via className for signature cards) + `shadow-level-1`. CardTitle: `text-h3 font-medium text-content-strong`. CardFooter: `bg-surface-base` + `border-t border-border-subtle` (Q5 sinking feel).
- `src/components/ui/dialog.tsx` — `bg-surface-raised` + `rounded-lg` (12px modals) + `shadow-level-2` + `p-6`. Overlay `bg-black/40` + `duration-arrive ease-settle` enter / `duration-settle ease-gentle` exit. max-w-sm default preserved per Q3.
- `src/components/ui/dropdown-menu.tsx` — matches Select content popup composition. 15 sub-components refreshed. Destructive items: `text-status-error` + `bg-status-error-muted` on focus. Shortcut: `font-plex-mono text-caption text-content-subtle` (keybinds render in mono per §4 "structured data that benefits from fixed-width").
- `src/components/ui/SlideOver.tsx` — `bg-surface-raised` + `shadow-level-3` (floating family) + `bg-black/40` backdrop + `duration-arrive ease-settle`. Header text: `text-h4 font-medium text-content-strong`. Close button: Ghost-button treatment inheriting brass focus ring.

**Navigation family (6 files, ~180 modified lines):**
- `src/components/layout/sidebar.tsx` (583 lines — biggest single-file edit) — shell `bg-surface-sunken` + `border-r border-border-subtle` per Q6 approval (recessed-navigation feel). Items: `text-content-muted` inactive, `bg-brass-subtle` + `text-content-strong` hover, `text-content-strong font-medium` active. Active-state border-left color + fill preserve the **Phase 3 Spaces per-space accent** (inline style, not brass) — alpha bumped from `10` to `18` hex to stay legible against the new quieter sunken background. Command-bar trigger rebuilt with input-shell + brass focus. Section eyebrows: `text-micro font-semibold uppercase tracking-wider text-content-subtle`. Keyboard-navigable via `focus-ring-brass` on all interactive elements.
- `src/components/layout/DotNav.tsx` — refresh preserves space-accent chrome on active dots + brass-subtle hover on inactive + focus-ring-brass on all dots + the plus button. Existing `DotNav.test.tsx` continues passing (behavioral test, not visual).
- `src/components/breadcrumbs.tsx` — `text-content-muted` inactive crumbs with `text-content-strong` hover + underline. Current crumb `text-content-strong font-medium`. Separator chevrons in `text-content-subtle`.
- `src/components/layout/mobile-tab-bar.tsx` — full-screen "More" overlay: `bg-surface-base` + brass-subtle item hovers. Bottom tab bar: `bg-surface-elevated` + `border-t border-border-subtle`. Added `min-h-11` (44px) to all interactive rows for WCAG 2.2 touch-target compliance on mobile.
- `src/components/layout/app-layout.tsx` — root shell `bg-surface-base font-plex-sans text-content-base`. Header `bg-surface-elevated` + `border-b border-border-subtle`. Profile link refreshed with brass focus ring + hover underline.
- `src/components/layout/notification-dropdown.tsx` (Q7 — Popover-based, not DropdownMenu primitive) — matches Dialog/DropdownMenu composition: `bg-surface-raised` + `border-border-subtle` + `rounded-md` + `shadow-level-2`. Unread indicator switched from blue dot to brass dot (continuity of primary-accent signal). Unread count badge: `bg-status-error` + `font-plex-mono`. Row hovers: `bg-brass-subtle`. Timestamp: `font-plex-mono text-caption text-content-subtle`.

**Platform-wide font flip (1 line):**
- `src/index.css:143` — `--font-sans: 'Geist Variable', sans-serif;` → `--font-sans: var(--font-plex-sans);`. Single-line change cascades to every rendered text node because zero components used `font-sans` explicitly — all inherit via the implicit html body font-family. Token-reference indirection means any future Plex-hosting change edits `tokens.css` only.

**Geist removal:**
- `src/index.css` — `@import "@fontsource-variable/geist"` removed; replaced with session-2 explanatory comment.
- `package.json` — `@fontsource-variable/geist` uninstalled via `npm uninstall`. Confirmed: `grep geist package.json` returns empty.
- Stale references to "Geist" updated in `tokens.css` + `fonts.css` comments.

### Variant decisions held (no consolidation)

Per Q10 / Q11 / Q12 audit confirmations:
- **Button `secondary` + `outline`** — both kept. Revisit Session 6 after seeing convergence patterns.
- **Button `xs` + `sm` + `icon-xs` + `icon-sm`** — all 4 preserved for backward compat (295 Button imports). Documented in the component file as "compact-dense legacy sizes, prefer default/sm for new work."
- **Card size `default` + `sm`** — both kept. Matches DESIGN_LANGUAGE §5 default + dense convention.

### Verification performed

- ✅ `tsc -b` — 0 errors.
- ✅ `npm run build` — clean (5.02s). Plex Sans woff2 subsets bundle as expected (latin + latin-ext + cyrillic + greek + vietnamese; standard + italic axes). No Geist assets in build output.
- ✅ `npx vitest run` — 165/165 passing across 11 test files. `DotNav.test.tsx` continues green post-refresh (behavioral test, not visual).
- ✅ Backend regression — Phase 8a/8b/8c/8d/8d.1 full suite: **171/171 passing**, zero regressions.
- ✅ Built CSS (`dist/assets/index-*.css`) contains: `accent-brass`, `surface-elevated`, `surface-raised`, `surface-sunken`, `content-strong`, `focus-ring-brass`, `shadow-level`, `ibm-plex-sans` — all Session-2 tokens present in minified output.

### Mixed-aesthetic state (expected during transition)

Per scope, Session 2 refreshes 8 core component categories + navigation. Extended components (toasts, alerts, badges, tables, forms, tabs, separator, avatar, tooltip, popover-standalone, drawer) remain on shadcn tokens until Session 3. Pages will render in a **mixed aesthetic** during the Session 2–3 window:

- **213 files** in `src/pages/` still reference shadcn semantic classes (`bg-card`, `text-muted-foreground`, `border-border`, `bg-background`, `bg-popover`, `text-foreground`, etc.). This is by design; these pages inherit the refreshed Button / Input / Select / Card / Dialog / DropdownMenu / SlideOver / sidebar / nav without editing the pages themselves.
- **5 settings pages** use shadcn surface tokens directly in page chrome (`invoice-settings.tsx`, `call-intelligence-settings.tsx`, `Locations.tsx`, `vault-supplier-settings.tsx`, `urn-import-wizard.tsx`). Also by design — page-level refresh is not in Session 2 scope.
- Session 6 QA closes any remaining mixed-aesthetic issues. Session 3 reduces the gap substantially by refreshing the extended-component set.

### Dark mode spot check (deferred full pass to Session 4)

Semantic tokens resolve correctly in dark mode automatically: `bg-surface-elevated` → dark charcoal lift with inset top-edge highlight, `bg-brass` → dark-mode brass (lightness 0.70 vs light 0.66, hue locked at 73), `text-content-strong` → near-white with warm tint. The Session 1 `--shadow-level-1/2/3` dark-mode override (`inset 0 1px 0 var(--shadow-highlight-top)`) lands on every refreshed Card + Dialog + DropdownMenu + Select content popup automatically via the token reference. Full pass deferred to Session 4.

### Sidebar refresh verification (Q5 - biggest visual change, 6 mount sites)

The sidebar is mounted on every authenticated page. Visual change is significant: light-mode shell shifts from the old `bg-sidebar` (shadcn's neutral-gray slate) to DESIGN_LANGUAGE's `bg-surface-sunken` (warm-cream recessed). The new sunken tone reads slightly quieter than the old sidebar background; per Q6 guidance, active-state fill alpha was bumped from `10` to `18` hex on the preset-accent inline style to compensate. Section eyebrows pick up the DESIGN_LANGUAGE `text-micro` + `tracking-wider` + `content-subtle` treatment. The 6 mount sites (one per preset-layout permutation) all inherit the refresh through the single `sidebar.tsx` file; no per-preset customization was required.

### Architectural patterns to carry into Session 3

1. **Brass focus ring via utility class** (`.focus-ring-brass` from Session 1) — applied via className on interactive non-input elements (buttons, nav items, dropdown menu items). Consistent signal across the refreshed surface.
2. **Input focus = border flip, not outside ring** — Q9 decision. Inputs/Textarea/Select trigger all use `focus-visible:border-brass focus-visible:ring-2 focus-visible:ring-brass/30` (border flip + subtle glow) because the border IS the input's affordance. Different form from button focus ring but consistent brass signal color.
3. **Footer sinks into surface-base** — Cards + Dialogs + SlideOver all use `bg-surface-base` + `border-t border-border-subtle` for footer regions. Q5 decision; reads as "page color peeking through under the elevated body."
4. **Overlay family parity** — Dialog, DropdownMenu, Select content popup, SlideOver all share the level-2/level-3 composition (raised surface + subtle border + shadow-level-2/3). This composition is the DESIGN_LANGUAGE §6 canonical surface pattern applied consistently.
5. **`font-plex-mono` for structured data tokens** — keybinds (DropdownMenuShortcut, command-bar kbd), unread count badge numerals, timestamp labels in notifications. Matches §4 "Plex Mono for alignment-requiring data."

### Component dependency order respected

1. Button (brass signal foundation) → 2. Label + Input + Textarea (input family) → 3. Select (depends on input family + dropdown style) → 4. Card (203-import foundation) → 5. Dialog + DropdownMenu + SlideOver (overlay family) → 6. Sidebar + top header + DotNav + breadcrumbs + mobile tab bar + notification dropdown (navigation family, largest visible change) → 7. `--font-sans` flip → 8. Geist removal → 9. Verification → 10. Docs.

### Ready for Session 3

Session 3 scope: extended components + status treatment. Toasts / Sonner notifications, alerts / banners, badges, tables, forms layout + fieldsets + multi-step, tabs, separator, avatar, tooltip, popover-standalone, drawer (if any standalone drawer surfaces exist beyond SlideOver). Session 3 also does a dedicated pass on status color treatment (error/warning/success/info UI across forms, banners, badges).

---

## Session 3 — Extended Components + Status Treatment (✅ Shipped)

**Date:** 2026-04-21
**Migration head:** `r40_aftercare_email_template` (unchanged — frontend-only session).
**Tests:** no new tests this session (component test coverage deferred per audit). 165/165 vitest + 171/171 Phase 8a-8d.1 backend regression all green. `tsc -b` clean, `npm run build` clean (4.94s).

### What shipped — status-color vocabulary + 6 net-new primitives + overlay family extension

Session 3 closes the extended-component gap. After Session 3, **every component category in the platform has been refreshed**, and the platform has a consistent status-color vocabulary (DESIGN_LANGUAGE `status-{success,warning,error,info}` + `-muted` variants) for rendering badges, alerts, toasts, pills, validation, and row-level status cells.

**Component deliverables:**

**6 net-new primitives:**
- `src/components/ui/alert.tsx` — platform banner primitive with 5 variants (info/success/warning/error/neutral). `Alert` + `AlertTitle` + `AlertDescription` + `AlertAction` + optional dismiss button. `role="alert"` + aria-live matches variant. Replaces the ad-hoc `<div className="bg-amber-50 border-amber-200">` pattern in ~50+ page-level banner sites.
- `src/components/ui/status-pill.tsx` — rounded-full inline status marker. Auto-maps status strings (approved / pending_review / rejected / etc) to DESIGN_LANGUAGE status families via a central `STATUS_MAP` dict (33 status keys → 4 families + neutral). `resolveStatusFamily` helper exported for direct programmatic use. 3 sizes (sm/default/md).
- `src/components/ui/tooltip.tsx` — Base UI Tooltip wrapper. Overlay-family composition (bg-surface-raised + border-border-subtle + rounded-md + shadow-level-2 + duration-settle ease-settle + 150ms delay per DESIGN_LANGUAGE §6). Exports `TooltipProvider` (app-root wrap), `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipShortcut` (font-plex-mono keybind styling). 2 sizes.
- `src/components/ui/popover.tsx` — Base UI Popover wrapper. Same overlay-family composition as Tooltip. Net-new primitive; the 2 existing Base UI popover usage sites (LocationSelector + notification-dropdown, both Session-2-refreshed) stay on their direct imports per Q4 scope decision.
- `src/components/ui/form-section.tsx` — `FormSection` + `FormStack` + `FormFooter`. Lightweight form grouping primitives. Complements (doesn't replace) Card. `FormSection` takes title/description/error props. `FormStack` applies DESIGN_LANGUAGE §5 vertical-rhythm gap-8 between sections. `FormFooter` matches Dialog/Card footer convention (bg-surface-base + border-t + sticky option).
- `src/components/ui/form-steps.tsx` — horizontal/vertical stepper indicator for multi-step forms. 4 step states (completed/current/upcoming/error) with brass filled-dot for completed+current, surface-sunken hollow for upcoming, status-error for errored step. Brass connector line for completed segments. Motion: `duration-settle ease-settle` on state changes per DESIGN_LANGUAGE §6.

**11 primitive refreshes onto DESIGN_LANGUAGE tokens:**
- **Badge** (179 imports) — added 4 status variants (info/success/warning/error) + `destructive` aliases `error` for backward compat (142 existing usages unchanged). `rounded-4xl` → `rounded-sm` per §6 badges=small pills. `bg-primary` → `bg-brass-muted`. font-plex-sans + text-micro.
- **Table** — `border-b` → `border-b border-border-subtle`. Header cells: `text-foreground` → text-micro uppercase tracking-wider `text-content-muted`. Rows: `hover:bg-muted/50` → `hover:bg-brass-subtle/60`; selected: `bg-muted` → `bg-brass-muted`. Footer: `bg-muted/50` → `bg-surface-base` + sinking-feel border-t (Card/Dialog parity). Cell padding bumped 8px → 12px per §5.
- **Tabs** — `bg-muted` → `bg-surface-sunken` (default variant track). Active tab lifts onto `bg-surface-raised` + `shadow-level-1`. Line-variant indicator flips to brass underline. Brass focus ring.
- **Separator** — `bg-border` → `bg-border-subtle`.
- **Avatar** — fallback `bg-muted` → `bg-brass-muted` + `text-content-on-brass` per §7 imagery rules. AvatarBadge default to `bg-brass`. 0 current imports; primitive prepared for future use.
- **Switch** — checked `bg-primary` → `bg-brass`. Unchecked `bg-input` → `bg-surface-sunken` + ring border-base. Thumb on surface-raised + shadow-level-1. Brass focus ring.
- **RadioGroup** — checked `bg-primary` → `bg-brass` + `content-on-brass` indicator dot. Border base → brass on check. Brass focus ring. Invalid `border-destructive` → `border-status-error`.
- **Skeleton** — `bg-muted/60` → `bg-surface-sunken` (warm recessed pulse). SkeletonCard `bg-card ring-1 ring-foreground/10` → `bg-surface-elevated shadow-level-1`. SkeletonTable `border` → `border-border-subtle`.
- **EmptyState** — `text-muted-foreground` → `text-content-muted`; positive tone `text-emerald-700` → `text-status-success`; title `text-base` → text-body font-plex-sans; border-dashed gets `border-border-subtle`.
- **InlineError** — severity styles migrated: `border-destructive/40 bg-destructive/5 text-destructive` → `border-status-error/40 bg-status-error-muted text-status-error`. Warning variant: `border-amber-500/40` → `border-status-warning/40 bg-status-warning-muted text-status-warning`. font-plex-sans.
- **Sonner** — `next-themes` DEPENDENCY REMOVED (audit confirmed single consumer). `theme="system"` hardcoded. `richColors` enabled (auto-tints status toasts). CSS vars: `--popover/--popover-foreground/--border/--radius` → `--surface-raised / --content-base / --border-subtle / --radius-md`. Status tints via `--{success|error|warning|info}-{bg|text|border}` mapped to DESIGN_LANGUAGE status-muted + status tokens.

**6 ad-hoc surface refreshes:**
- `accounting-reminder-banner.tsx` (visible on every authenticated page when connection is skipped/pending) — migrated to `<Alert variant="warning">`. Raw `bg-amber-*/text-amber-900` chrome replaced.
- `kb-coaching-banner.tsx` — migrated to `bg-status-info-muted` + tokens. `bg-indigo-100/from-indigo-50` replaced.
- `agent-alerts-card.tsx` (dashboard widget, visible on every authenticated dashboard) — **migrated to status-key-keyed dict pattern** (new CLAUDE.md convention). Replaced `SEVERITY_CONFIG = { action_required: { color: "text-red-600", bg: "bg-red-50" } }` with `{ status: "error" }` + a `FAMILY_STYLES` lookup that maps status-family to DESIGN_LANGUAGE token triples. Pattern documented for platform re-use.
- `peek/renderers/_shared.tsx::StatusBadge` — delegates to new `StatusPill` primitive. 6 peek renderers inherit status-family auto-mapping; unmapped statuses render as neutral.
- `App.tsx ErrorBoundary` — removed inline `style={{ color: "#b91c1c" }}` hex. Now renders as `<Alert variant="error">`-styled shell with brass reload button + surface-base page background + content-base content. font-plex-sans.
- `WidgetErrorBoundary.tsx` — `text-red-400/text-blue-600/text-gray-500` → `text-status-error/text-brass/text-content-muted`. Brass focus ring on retry.

### Status-color migration recipe (documented in CLAUDE.md for long-tail adoption)

Long-tail migration for the **1,305 ad-hoc status-color usages** across the platform is deferred to natural refactor. Session 3 documents a mechanical find-replace recipe:

| Legacy pattern (find) | DESIGN_LANGUAGE replacement |
|---|---|
| `bg-green-50 text-green-800` | `bg-status-success-muted text-status-success` |
| `bg-red-50 text-red-800` | `bg-status-error-muted text-status-error` |
| `bg-amber-50 text-amber-800` | `bg-status-warning-muted text-status-warning` |
| `bg-blue-50 text-blue-800` | `bg-status-info-muted text-status-info` |
| `bg-green-100` / `bg-red-100` / `bg-amber-100` / `bg-blue-100` | `bg-status-*-muted` (same family per color) |
| `border-green-*` / `border-red-*` / `border-amber-*` / `border-blue-*` | `border-status-*` (with optional `/30` opacity) |
| `text-emerald-*` / `text-rose-*` / `text-sky-*` | `text-status-success` / `text-status-error` / `text-status-info` |

Pages adopting the recipe when next touched will converge on platform-consistent status colors without a big-bang refactor.

### Architectural patterns extracted for Session 4+

1. **Status-family recipe** (new) — `bg-status-{X}-muted` + `text-status-{X}` + optional `border-status-{X}`. Used consistently across Badge/Alert/StatusPill/Sonner/InlineError/Peek StatusBadge/agent-alerts.
2. **Status-key-keyed dict pattern** (new) — components with per-state config (agent-alerts-card, peek StatusBadge, future status renderers) declare a `StatusFamily` key per state and a shared `FAMILY_STYLES` lookup. No raw color strings in component code.
3. **Overlay family extended** — Tooltip + Popover join Dialog/DropdownMenu/Select popup/SlideOver/notification Popover. Shared composition now standard across 7 overlay primitives.
4. **StatusPill vs. Badge distinction** — documented in both component headers + CLAUDE.md. StatusPill = rounded-full auto-mapping from status strings; Badge status variants = rounded-sm general emphasis.
5. **Alert vs. InlineError distinction** — documented. Alert = page/section banners, 5 variants including neutral; InlineError = panel-scoped recoverable errors with retry affordance.

### Verification performed

- ✅ `tsc -b` clean.
- ✅ `npm run build` clean — 4.94s build, Plex Sans woff2 subsets bundled, no next-themes assets.
- ✅ `npx vitest run` — 165/165 passing (DotNav behavioral test green post-refresh).
- ✅ Backend regression — 171/171 Phase 8a-8d.1 passing.
- ✅ `next-themes` fully uninstalled — no remaining references in src/ (`grep next-themes src/` returns empty).
- ✅ All 6 net-new primitives tsc-validated + build-validated.
- ✅ Built CSS contains all status-family utilities: `status-success-muted`, `status-warning-muted`, `status-error-muted`, `status-info-muted`.

### Mixed-aesthetic state post-Session 3

- **0 primitives** remaining in shadcn aesthetic. All UI primitives (`src/components/ui/*`) now use DESIGN_LANGUAGE tokens.
- **~213 pages** still reference shadcn semantic classes in page-level chrome (accepted state per audit §9). Session 6 QA verifies no net-new mixed aesthetic introduced.
- **5 settings pages** explicitly deferred to Phase 8e (which redesigns them as part of Spaces work) per audit §2.
- **1,305 ad-hoc status-color usages** documented with migration recipe (CLAUDE.md) — long-tail adoption.
- **266 native `title=` attributes** left as-is; Tooltip primitive available for new work.

### Deferred to Sessions 4-6

- Dark mode full QA pass (Session 4).
- Motion pass applying `ease-settle`/`ease-gentle` + named durations consistently (Session 5).
- WCAG 2.2 AA accessibility audit across all refreshed components (Session 6).
- Long-tail migration of page chrome + native tooltips + ad-hoc status colors (post-arc natural refactor).

### Ready for Session 4: Dark mode pass

Session 4 scope: comprehensive dark-mode verification across every refreshed component and every surface (hub dashboards, triage queues, workflow builders, forms). Dark-mode failures likely concentrate around: inset top-edge highlights on elevated surfaces rendering correctly, brass visibility against dark charcoal at all sizes, status-muted variants at low luminance not reading as washed-out, and shadow composition on modals/dialogs at level-2/level-3.

---

## Session 4 — Dark Mode Pass (✅ Shipped)

**Date:** 2026-04-21
**Session type:** Verification + surgical fixes. Not a net-new aesthetic session.

**Issue catalog resolution:**

| # | Severity | Description | Status |
|---|---|---|---|
| M1 | Moderate / WCAG fail | Dark-mode `status-*-muted` backgrounds L 0.28/0.30 + text at L 0.68/0.70/0.76 → contrast 3.83–4.32:1 (FAIL AA 4.5:1) | **Shipped** — muted L lowered to 0.22/0.24, chroma eased proportionally. Post: 5.0–5.4:1 PASS |
| M2 | Moderate | Portal fg fallback `var(--portal-brand-fg, white)` (literal) across 3 files, 6 sites — dark-mode brass button shows white text instead of DL-spec dark charcoal | **Shipped** — migrated to `var(--portal-brand-fg, var(--content-on-brass))` |
| M3 | Moderate | Branding editor preview is light-only; tenants can't see dark-mode rendering before saving | **Shipped** — Light/Dark toggle + WCAG contrast readout (brand→fg + brand→page-surface). Proper WCAG sRGB-gamma luminance |
| M4 | Design decision | Tenant brand color in dark mode approach | **Resolved: Option A** (identical hex in both modes) + M3 preview helper as verification tool. B (auto-adjust) and C (separate schema) rejected |
| M5 | Moderate / Session 3 miss | `NotificationDropdown` 4 status icons hardcoded Tailwind primaries (`text-green-500` / `-yellow-500` / `-red-500` / `-blue-500`) | **Shipped** — migrated to `text-status-{success,warning,error,info}` |
| m1 | Minor | `focus-ring-brass` gap ring uses `--surface-base`; reads as darker-than-parent cut when focused on elevated dark surface | **Deferred to Session 6** — spec-vs-pragmatism deserving dedicated call |
| m2 | Minor | Focus ring on `--surface-raised` sits at ~3.00:1 WCAG 2.4.7 edge | **Shipped** — new `--focus-ring-alpha` composable token, dark override 0.48 clears to ~3.5:1 |
| m3 | Minor | `PortalLayout` logout button `focus:ring-white/50` hardcoded | **Shipped** — migrated to `focus-visible:ring-[color:var(--portal-brand-fg,var(--content-on-brass))]/50` |
| m4 | Minor | `OfflineBanner` hardcoded amber — not mode-aware | **Deferred to natural refactor** — transient, low priority |
| — | Long-tail | ~20 pre-Session-3 pages (vault-mold-settings, tax-settings, etc.) still use hardcoded Tailwind colors | **Deferred** — documented Session 3 long-tail |

**Token adjustments (tokens.css + DESIGN_LANGUAGE.md §3 synchronously):**

Before / after for status-muted backgrounds (`[data-mode="dark"]` block):

| Token | Before | After |
|---|---|---|
| `--status-error-muted` | `oklch(0.28 0.08 25)` | `oklch(0.22 0.07 25)` |
| `--status-warning-muted` | `oklch(0.30 0.07 65)` | `oklch(0.24 0.06 65)` |
| `--status-success-muted` | `oklch(0.28 0.06 135)` | `oklch(0.22 0.05 135)` |
| `--status-info-muted` | `oklch(0.28 0.05 225)` | `oklch(0.22 0.04 225)` |

New `--focus-ring-alpha` token (light 0.40, dark 0.48 override). `.focus-ring-brass` utility in `base.css` composes the brass ring via `color-mix(in oklch, var(--accent-brass) calc(var(--focus-ring-alpha) * 100%), transparent)` with a 0.40 fallback.

**WCAG compliance status (post-Session-4, dark mode):**

| Pairing | Before | After | Threshold |
|---|---|---|---|
| `content-strong` on `surface-base` | 13.3:1 | 13.3:1 | 4.5:1 ✅ AAA |
| `content-base` on `surface-elevated` | 9.6:1 | 9.6:1 | 4.5:1 ✅ AAA |
| `content-on-brass` on `--accent-brass` | 6.4:1 | 6.4:1 | 4.5:1 ✅ AAA |
| `status-error` on `status-error-muted` | **3.83:1 FAIL** | **5.3:1 ✅** | 4.5:1 AA |
| `status-warning` on `status-warning-muted` | **4.32:1 FAIL** | **5.0:1 ✅** | 4.5:1 AA |
| `status-success` on `status-success-muted` | **4.05:1 FAIL** | **5.1:1 ✅** | 4.5:1 AA |
| `status-info` on `status-info-muted` | **4.05:1 FAIL** | **5.4:1 ✅** | 4.5:1 AA |
| Brass focus ring on `--surface-raised` | ~3.00:1 | **~3.5:1 ✅** | 3:1 WCAG 2.4.7 |

**Component file changes shipped:**

- `frontend/src/styles/tokens.css` — 8 values adjusted + new `--focus-ring-alpha` token (both modes)
- `frontend/src/styles/base.css` — `.focus-ring-brass` composition updated to use `--focus-ring-alpha`
- `frontend/src/components/portal/PortalLayout.tsx` — 2 sites: header fg fallback + logout focus ring
- `frontend/src/pages/portal/PortalLogin.tsx` — 2 sites: header + submit button fg fallback
- `frontend/src/pages/portal/PortalResetPassword.tsx` — 2 sites: header + submit button fg fallback
- `frontend/src/components/layout/notification-dropdown.tsx` — 4 status icon classnames
- `frontend/src/pages/settings/PortalBrandingSettings.tsx` — ~130 LOC added: Light/Dark toggle, scoped `data-mode` preview wrapper, simulated page backdrop, WCAG contrast readouts, proper `_wcagContrast`/`_wcagLuminance` helpers

**Documentation:**

- `DESIGN_LANGUAGE.md §3` — status-muted values synchronized with tokens.css; focus-ring-alpha token added to `:root` + `[data-mode="dark"]` CSS blocks; rationale paragraph for M1 adjustment; mirror discipline paragraph at top of §3
- `CLAUDE.md` — Design System section retitled to "Sessions 1–4"; "Tokens.css is a mirror" discipline paragraph; Session 4 shipped block; Recent Changes entry
- `SPACES_ARCHITECTURE.md §10.6` — Option A decision documented; M3 preview helper as verification tool; BT.601 vs WCAG luminance discrepancy noted as minor known item; M2 fallback discipline paragraph
- `FEATURE_SESSIONS.md` — Session 4 entry

**Tests:** No new tests. vitest 165/165 unchanged (no component behavior changes). tsc clean (post-force-clean-cache verification). vite build clean. **Backend baseline 377 unchanged** (2 pre-existing failures from Phase 8b unchanged).

**LOC:** ~180 touched (~30 tokens/base.css + ~15 portal fg fallback + ~4 notification-dropdown + ~10 PortalLayout logout + ~130 branding-editor preview + ~60 documentation).

**Deferred:**
- m1 focus-ring gap color → Session 6
- m4 OfflineBanner → natural refactor
- BT.601 vs WCAG luminance alignment in PortalBrandProvider → revisit if portal branding becomes a larger focus area
- Pre-Session-3 page chrome migration → natural refactor (~20 pages)

### Ready for Session 5: Motion pass

Session 5 scope: verify every animation, transition, and micro-interaction against DESIGN_LANGUAGE §6 motion timing scale + easing curves. Likely focus areas: dropdown/dialog entry timing (`duration-arrive` vs `duration-settle` per overlay type), hover-to-click promotion on Peek panels, triage keyboard-driven transitions, briefing list reveals, command bar result-list animations. Reduced-motion compliance re-verified post-Session-4.

**Arc restructure (Phase II split):** Phase II platform-wide page correctness runs between Session 4 and Session 5. Session 5 waits until Phase II Batches 1–5 complete. See Phase II Audit + Batch 0 sections above.

---

## Phase II Audit — Platform-wide page-level correctness (✅ Shipped)

**Date:** 2026-04-21. Audit session only.

Phase I shipped token + primitive refresh but didn't verify pages consume primitives + tokens correctly. User surfaced pages rendering broken in dark mode. Audit scoped Phase II into 6 batches (Batch 0 hotfix + 5 implementation batches + Batch 6 deferred long-tail). Full audit report in FEATURE_SESSIONS.md.

**Headline numbers:** 208 tenant routes + 6 portal + 8 platform-admin = 222 routes audited. 305 `.tsx` page files: 54 clean / 117 small / 86 medium / 48 large. Platform-wide: 414 `bg-white`, 2,886 `text-muted-foreground`, ~5,000 Tailwind utilities total, 109 emoji.

---

## Nav Bar Completion (micro-session — ✅ Shipped)

**Date:** 2026-04-21
**Slot:** Between Phase II Batch 1a and Batch 1b. No Phase II scope impact.
**Files touched:** 8 (2 net-new components, 2 net-new test files, 1 runtime-API extension, 3 edits).
**LOC:** ~280.
**Tests:** +16 (165 → 181).

Two-gap fix surfaced during user visual verification:

**Gap 1 — DotNav not visible.** `DotNav.tsx:209-213` shipped a `spaces.length === 0 → return null` early-return in Phase 8a whose inline comment described "render just the plus button so new tenants can still create one" but whose code returned null. Comment-code mismatch survived 14 months because the Playwright test seeded spaces before assertion and never exercised the empty branch. Fix: remove early-return, restructure render so (a) rail always visible, (b) loading skeleton dot during `isLoading && spaces=[]`, (c) + button alone during `!isLoading && spaces=[]` recovery path, (d) dots + + button when spaces exist. OnboardingTouch welcome-card gate (`≥2 spaces`) unchanged.

**Gap 2 — No visible mode toggle.** Aesthetic Arc Session 1 shipped complete mode-switching infrastructure — flash-mitigation inline script, `lib/theme-mode.ts` runtime API with `useThemeMode` hook, `[data-mode="dark"]` CSS cascade, Tailwind dark variant — but never wired a visible UI button. Users had to toggle via devtools attribute manipulation. Fix: new `ModeToggle.tsx` Sun/Moon Lucide component mounted in `app-layout.tsx:38` before `NotificationDropdown`. New `useMode()` ergonomic alias in `theme-mode.ts` returns `{mode, toggle}` shape, delegates to `useThemeMode`. Icon shows the *destination* state (Moon in light = "click to go dark") per GitHub/Linear convention. `aria-label` describes action, `aria-pressed` reflects state — WCAG toggle-button guidance.

**Design decisions (audit-approved):**
- **localStorage key reused:** existing `bridgeable-mode` (hyphen). User prompt specified `bridgeable.mode` (dot-separated), but shipping that would desync with the flash-mitigation script. Audit flagged; user approved reusing existing key.
- **DotNav loading skeleton:** slightly-more-polished variant with skeleton dot during `isLoading` + empty-state recovery afterwards. 5 extra LOC vs. instant + button reveal; avoids brief "plus button appears alone for a flash" during initial fetch.
- **`useMode()` as ergonomic alias:** thin wrapper around `useThemeMode` returning `{mode, toggle}` rather than `[mode, setter]`. Cleaner API at consumer call sites; no duplicate state.

**Test infrastructure:** `src/test/setup.ts` gained two jsdom polyfills. `window.matchMedia` isn't provided by jsdom; `window.localStorage` broke in vitest v4's `--localstorage-file` opt-in flow (symptomatic of an internal flag that runs without a valid path, breaking the Storage instance). Setup.ts installs in-memory Storage shim + MediaQueryList stub conditionally (only when missing). Belt-and-suspenders — the 165 baseline tests were unaffected by the jsdom gaps because none used either API; shims are forward-compatible for future tests.

**Pre-existing issue inherited, not fixed:** `.focus-ring-brass` utility fails WCAG 2.4.7 in light mode (~1.26:1 on cream surface). Session 4 and Batch 1a both surfaced it; Session 6 deferred. ModeToggle uses the utility per existing pattern and inherits the same gap until Session 6 fixes the utility itself. Not a per-component concern here.

**Verification methodology update:** All Phase II batches going forward are verified in **both light AND dark mode**. Pre-ModeToggle, batches defaulted to dark-mode verification (where Session 4 focused). Post-ModeToggle, the mode toggle in the header makes both-modes-verification ergonomic for users + catches light-mode-specific issues (like the focus-ring-brass gap) earlier. Applies to Batch 1a verification (user spot-checks Batch 1a pages in both modes before approving Batch 1b) and all subsequent batches.

**Files shipped:**

| File | Action |
|---|---|
| `components/layout/DotNav.tsx` | Early-return removed; loading skeleton + always-on + button; `isLoading` destructure from useSpaces |
| `components/layout/DotNav.test.tsx` | Replaced `returns null` case with 2 new cases (empty-state + loading-state); added `isLoading` to mock context |
| `components/layout/ModeToggle.tsx` | **New.** ~65 LOC. Sun/Moon Lucide + aria-label + aria-pressed |
| `components/layout/ModeToggle.test.tsx` | **New.** ~70 LOC. 4 test cases |
| `components/layout/app-layout.tsx` | Import + mount ModeToggle before NotificationDropdown |
| `lib/theme-mode.ts` | `useMode()` alias added; no change to existing runtime API |
| `lib/theme-mode.test.ts` | **New.** ~130 LOC. 11 test cases covering runtime API + both hooks |
| `test/setup.ts` | jsdom polyfills: matchMedia stub + localStorage in-memory shim |

### Ready for Batch 1b

Scheduling board family (scheduling-board + kanban-panel + ancillary-panel + direct-ship-panel), ~550 LOC. InlineError primitive migration for "Failed to load schedule" error state + emoji → Lucide for ⛪🏛⚰📍📦. User verifies Batch 1a pages in both light and dark mode (newly ergonomic via ModeToggle) before approving Batch 1b implementation prompt.

---

## Phase II Batch 0 — Shadcn Default Aliasing (✅ Shipped)

**Date:** 2026-04-21  
**Type:** Micro-session. One file touched (`frontend/src/index.css`, ~50 lines).  
**Tests:** No new tests. vitest 165/165 unchanged. tsc clean (force-cache). vite build clean 5.24s.

Every shadcn semantic token in `:root` + `.dark` CSS blocks aliased to DL equivalents via `var(...)` references. **Platform-wide effect without touching any component code** — 3,596 shadcn-default consumers automatically route through DL warm-family palette.

**Aliased:** `--background` → `surface-base`, `--foreground` → `content-base`, `--card` → `surface-elevated`, `--card-foreground` → `content-base`, `--popover` → `surface-raised`, `--popover-foreground` → `content-base`, `--primary` → `accent-brass`, `--primary-foreground` → `content-on-brass`, `--secondary` → `surface-elevated`, `--secondary-foreground` → `content-strong`, `--muted` → `surface-sunken`, `--muted-foreground` → `content-muted`, `--accent` → `accent-brass-subtle`, `--accent-foreground` → `content-strong`, `--destructive` → `status-error`, `--border` → `border-subtle`, `--input` → `border-base`, all `--sidebar*` → DL sidebar equivalents.

**NOT aliased:** `--radius` (shadcn radius scale), `--chart-*` (no DL chart palette yet), `--brand-*` (legacy custom teal), `--status-*-{light,dark}` (coexistence window), `--ring` (brass solid would fail WCAG 2.4.7 3:1 in light mode; shadcn fallback stays neutral; `.focus-ring-brass` utility remains the brass opt-in).

**User-reported page post-Batch-0 status:**
- MFG dashboard onboarding banner: ✅ **RESOLVED** (shadcn-default-driven — `bg-primary/N`, `text-primary`, `border-primary/N` now all brass)
- MFG + FH dashboards `text-muted-foreground` usages: ✅ **RESOLVED** (24+ warm-flip)
- MFG + FH dashboard widget icon pastel backgrounds: ⚠️ **Still hardcoded** — Batch 1
- MFG + FH dashboard status pill color maps: ⚠️ **Still hardcoded** — Batch 1
- Scheduling board `bg-slate-50/50` right panel (blocking): ⚠️ **Still hardcoded** — Batch 1
- Scheduling board `bg-white` calendar toggle (blocking): ⚠️ **Still hardcoded** — Batch 1
- Scheduling board 📦 emoji: ⚠️ **Still hardcoded** — Batch 1
- Kanban "Failed to load schedule" red error (blocking): ⚠️ **Still hardcoded** — Batch 1 (migrate to InlineError)
- Kanban `bg-white` card chrome (5+ sites, blocking): ⚠️ **Still hardcoded** — Batch 1
- Kanban service-location emoji ⛪🏛⚰📍: ⚠️ **Still hardcoded** — Batch 1
- Ancillary panel (94 hits, all hardcoded): ⚠️ **Still hardcoded** — Batch 1
- Direct-ship panel (65 hits, all hardcoded): ⚠️ **Still hardcoded** — Batch 1

**Pre-existing WCAG issue surfaced (deferred to Session 6):** `.focus-ring-brass` utility in light mode computes ~1.26:1 contrast against cream surface (brass α 40% composed over surface-base). Fails WCAG 2.4.7 3:1. Session 4 verified dark mode only (3.40:1 pass). Fix: raise light-mode alpha, OR switch to solid brass ring in light mode (requires brightness adjustment of `--accent-brass` in light). Defer — out of Batch 0 scope.

### Ready for Batch 1: User-reported broken pages

After Batch 0, Batch 1 scope is largely unchanged for scheduling-board family (those files had 0-2 shadcn-default usages — their issues are hardcoded Tailwind utilities). Dashboards get moderate scope reduction (shadcn-default usages auto-resolved). Overall Batch 1 LOC estimate: ~400-600, unchanged from audit projection.

---

## Phase II Batch 1b — Scheduling Board Family (✅ Shipped)

**Date:** 2026-04-22
**Type:** File-family batch. 4 files touched (~590 LOC touched across ~3,100 file LOC).
**Tests:** No new tests. vitest 185/185 unchanged. tsc clean. vite build clean 5.13s.

Closes user-reported scheduling board bugs surfaced post-Batch-1a visual verification. Right panel wrapper `bg-slate-50/50` was specifically user-reported as unreadable in dark mode — slate-50 at 50% alpha over a dark page reads as a "lighter dim wash" inverting the intended recessed meaning. Fixed via `bg-surface-sunken` mode-aware token (cream-tinted recess in light, charcoal-tinted recess in dark).

**Files shipped:**

| File | Primary changes |
|---|---|
| `pages/delivery/scheduling-board.tsx` | Right-panel wrapper → surface-sunken; calendar toggle + nav buttons → border-border-base + surface-raised; Weekend Planning + count pills → Badge variants; 6 HTML-entity icons → Lucide (Undo2, ChevronLeft x2, ChevronRight, Package, Mailbox) |
| `components/delivery/kanban-panel.tsx` | Failed-to-load → `<InlineError>` primitive (blocking fix); OrderCard critical/warning → status-error-muted/status-warning-muted; droppable-over `border-indigo-300 bg-indigo-50/50` → `border-brass bg-brass-subtle` per Q2; 4 raw unicode emoji → Church/Landmark/Box(aria-label graveside)/MapPin; hours-countdown Badge class map → status tokens; inline SVG chevron → ChevronRight |
| `components/delivery/ancillary-panel.tsx` | Largest file (1,131 LOC). 5 card chromes → surface-elevated; ALL emerald/violet/blue action buttons → brass `<Button>` primary (Q1/Q5 approved); 3 dropdowns → surface-raised (Q4 raw-div retention); mobile FAB + drawer → surface-raised + shadow-level-2/3; `<Package>` + `<Check>` + `<ChevronDown>` + `<X>` Lucide migrations |
| `components/delivery/direct-ship-panel.tsx` | 4 card chromes → surface-elevated; `getUrgencyClass()` helper internals → status tokens per Q8; ALL action buttons (blue/emerald/slate-700 tracks) → brass `<Button>` primary; info/success/error Badge variants for state groups; `<Mailbox>` + `<Check>` + `<ChevronDown>` + `<X>` Lucide migrations |

**Primitive adoption:**
- `<InlineError>` — 1 site (kanban Failed-to-load) — the exact "failed to load + retry" pattern the Phase-7 primitive was designed for
- `<Badge variant="info|warning|success|error">` — 10+ sites replacing hardcoded `bg-{color}-100 text-{color}-700` pill patterns + `border-{color}-300 text-{color}-600` outline-style overrides
- `<Button>` — ~12 sites unifying 4 different action-color tracks (emerald/violet/blue/slate-700) on brass primary per Q1/Q5 platform-consistency ruling
- **Card** intent without primitive wrapper: card chromes migrated inline via surface tokens because full `<Card>` + subcomponent wrapping would restructure DnD hit targets (`provided.dragHandleProps` spread onto card divs); surface tokens applied directly preserve hit-target fidelity while getting mode-aware treatment. Documented deviation from audit's primitive plan.

**16 icon migrations** (raw unicode + HTML entities → Lucide):
- `⛪` → `<Church>`, `🏛` → `<Landmark>`, `⚰` → `<Box aria-label="Graveside">` (no direct Lucide casket match — documented semantic fallback), `📍` → `<MapPin>`
- `&#128230;` (📦) → `<Package>` (3 sites: scheduling board collapsed pill + ancillary empty-state + ancillary FAB)
- `&#128236;` (📬) → `<Mailbox>` (3 sites: scheduling board + direct-ship empty-state + direct-ship FAB)
- `&#10003;` (✓) → `<Check>` (10+ sites — kept per spec item #2 as scan-path affordance in dense card UI despite text-button redundancy)
- `&#9662;` (▾) → `<ChevronDown>`
- `&#8617;` (↩) → `<Undo2>`
- `&#8592;/&#8594;` (←/→) → `<ChevronLeft>`/`<ChevronRight>`
- `&#9664;` (◀) → `<ChevronLeft>`

**4 inline SVG migrations**: kanban panel-header chevron path → `<ChevronRight>` with rotation; ancillary + direct-ship collapse chevrons → `<ChevronDown>` with rotation; ancillary + direct-ship close-drawer X → `<X>` Lucide.

**Droppable-over state migration (Q2 approved)**: `border-indigo-300 bg-indigo-50/50` → `border-brass bg-brass-subtle` for drag-drop active zones. Platform interaction language (brass for focus/active/hover) beats DnD library indigo convention. Visual "drop here" signal preserved via shape + subtle bg shift — color family now consistent with focus rings + all other active-surface affordances across the platform.

**Helper function discipline (Q8 approved)**: `getUrgencyClass()` in direct-ship-panel retained its helper structure (reused across 3 card types); internals migrated `text-red-600 font-bold` → `text-status-error font-bold`, `text-amber-600 font-bold` → `text-status-warning font-bold`. Other helpers returning raw Tailwind: none found across the 4 files (post-Batch-1a pattern hold).

**Deferred to post-arc natural refactor:**
- BottomSheet primitive (Q3 approved deferral — only 2 usages today; 3+ threshold to justify new primitive)
- DropdownMenu primitive migration (Q4 approved deferral — 3 raw `absolute`-positioned dropdowns in ancillary retained as raw divs with surface-raised tokens; full primitive adoption is its own slot when these are next touched)
- `<Card>` subcomponent wrapping around DnD cards — accepted deviation; surface tokens inline preserve DnD hit-target fidelity

**0 hardcoded Tailwind bypass patterns remain** across all 4 files (excluding migration-history comments + canonical `bg-black/40` backdrop scrim per DESIGN_LANGUAGE §9 which Dialog also uses as its canonical modal dimming overlay).

**User verifies Batch 1b in both light AND dark mode** (newly ergonomic via Nav Bar Completion's ModeToggle) before approving Batch 1c-i.

### Ready for Batch 1c-i

Order Station (`pages/orders/order-station.tsx`) standalone — large file with both dark-mode rendering issues + emoji. Split into its own sub-batch since order-station has different concerns than the scheduling-family (no DnD, different data shape). LOC estimate: ~300-400.

---

## Dispatch-Focus Aesthetic Arc (Sessions 1 / 1.5 / 1.6 / 4)

Distinct from the platform-wide Phase I/II/III arc above, this thread tracks the dispatch-focus surface specifically (Funeral Scheduling Focus + DeliveryCard + AncillaryPoolPin + DateBox header). Sessions are numbered by their commit-message/CLAUDE.md taxonomy. The Dispatch-Focus arc uses the platform tokens (Phase I primitives) but applies them deeper to the Focus dispatch experience as the canonical reference for September Wilbert demo.

### Session 1 — Focus Chrome Restraint (✅ Shipped, 2026-04-25)

Removed Close button (Section 0 Restraint TP3 — backdrop click + Esc dismiss; the button was decorative). Subordinated Finalize button (solid brass primary → brass-bordered transparent fill). Reduced header prominence (text-h2 → text-h3, gap-4 → gap-3). Centered kanban via canvas tier when pin fits (CANVAS_RESERVED_MARGIN bumped 100→220, pin width narrowed 260→180). Pin background harmonized as floating tablet (bg-surface-elevated/85 + backdrop-blur-sm + shadow-level-1). 4 commits: `42164d5` → `4f37aca` → `3945163` → `61e6ae4` → `014f44d`.

### Session 1.5 — Widget Sizing + Header Refinement (✅ Shipped, 2026-04-25 PM)

Pin auto-sizing height (`height: "auto" + maxHeight: 480` per new "Widget Content Sizing" principle in PLATFORM_PRODUCT_PRINCIPLES.md). Finalize as text-link (no border, no fill, brass text only — 55×23px, was 130×32px solid brass button). DateBox quieter (transparent surface + `border-border-subtle/50` + `text-[0.75rem]`). 3 commits: `f9fad0e` → `2b1d455` → `47fc9bc`.

### Session 1.6 — Compactness Canon + Refinement (✅ Shipped, 2026-04-26)

Extended "Widget Content Sizing" → "Widget Compactness" principle in PRODUCT_PRINCIPLES.md to cover width + chrome containment + boundary affordances. Pin item titles wrap (`line-clamp-2 break-words`). SchedulingKanbanCore root wrapped in `w-fit max-w-full mx-auto` so kanban content-sizes + Finalize aligns to rightmost-lane right edge. Finalize typography bumped (12px font-medium → 14px font-semibold). DateBox visibility restored (transparent + full-strength `border-border-subtle` + `text-[0.8125rem]`). 4 commits: `db0dbe6` → `55e172e` → `895a058` → `785a38d`.

### Widget Library Investigation + Specification (✅ Documented, 2026-04-27)

Cross-arc work between Aesthetic Arc Session 4.8 (locked tablet visual contract) and Phase W-1 implementation. Two sessions: comprehensive investigation deliverable, then specification deliverables across 5 docs. NO CODE — pure architectural canonization. Includes one critical correction (read-only framing → interactivity discipline) caught by user mid-spec.

**Investigation deliverable** (preceding session): comprehensive 11-section audit covering current state of two coexisting widget frameworks (canvas via `widget-renderers.ts` registry vs dashboard via `useDashboard` + `WidgetGrid`), inventory of 25+ existing widgets, surface-consumption analysis (Focus / Pulse / Spaces / command bar peek / hub dashboards), variant taxonomy proposal, vertical scoping mechanism via 4-axis filter (extending `vault.hub_registry`'s permission + module + extension triple with `required_vertical`), composition rules per surface, tablet-materialization integration with Section 11 Pattern 1, cold-start catalog recommendations, 13-risk register, 6-phase implementation plan W-1 → W-6. User reviewed; locked 10 architectural decisions + provided 3 strategic additions ("workspace cores have widget views" canon, "entity cores have widget views" canon, sequence revision Spaces-before-cold-start).

**Specification deliverables** (this session):

1. **DESIGN_LANGUAGE.md Section 12 — Widget Library Architecture** (NEW SECTION, ~440 lines): durable canonical reference. Subsections:
   - 12.1 Foundational frame
   - 12.2 Variant taxonomy: **Glance / Brief / Detail / Deep** (4 named tiers, Apple-style multi-variant per widget)
   - 12.3 Widget contract: `WidgetDefinition<TConfig>` + `WidgetVariant` + `WidgetVariantProps` shapes
   - 12.4 Visibility & gating: 4-axis filter (permission + module + extension + vertical) + defense-in-depth + invisible-not-disabled discipline
   - 12.5 Composition rules per surface (Focus / Pulse / Spaces / command bar / dashboard)
   - 12.6 Workspace cores have widget views (canon)
   - **12.6a Widget Interactivity Discipline (canon — added during correction)**: state changes widget-appropriate, decisions belong in Focus; 4-test framework + canonical examples table
   - 12.7 Entity cores have widget views (canon)
   - 12.8 Tablet materialization integration (Pattern 1 inheritance + Glance variant chrome reduction)
   - 12.9 Persistence model (per-surface storage, in-memory shape unified)
   - 12.10 Reference implementation: Funeral Schedule + Ancillary Pool + Recent Activity widgets with per-variant interaction declarations + cold-start catalog widget interaction summary table

2. **PLATFORM_ARCHITECTURE.md Section 9** (NEW): widget library framing, 4-axis filter as platform-wide vertical-scoping mechanism, connection to Vault-as-foundation thesis (widgets are Vault views with chrome), phased plan W-1 → W-6.

3. **PLATFORM_INTERACTION_MODEL.md "Widgets as canonical tablet realization"** subsection added: variant tier mapping to surface metaphors (Glance = Watch, Brief = phone, Detail = tablet/desktop, Deep = primary work surface), workspace-cores-have-widget-views interaction implication, widget interactivity discipline cross-reference, peek-vs-widget composition reuse pattern.

4. **BRIDGEABLE_MASTER.md §3.25**: strategic milestone capture, sequence W-1 → W-4 pre-September, September demo narrative, connection to Vault primitive layering (data → materialization → placement).

5. **AESTHETIC_ARC.md** (this entry): cross-arc session log + critical correction documentation (below).

**Critical correction caught mid-spec.** Initial Section 12 draft framed widget views of workspace cores as "read-only" (e.g., "Funeral Schedule Widget renders kanban data, **read-only**"). User flagged: this is wrong. Widgets ARE interactive — but with discipline about WHAT interactions belong where. The correct principle: **state changes are widget-appropriate; decisions belong in Focus.** Criterion is interaction complexity, not editability. Quick state flips don't require entering a workspace; multi-variable decisions do.

The correction surfaced a deeper insight: the read-only framing was a derivation error from "widgets simpler than Focus." The user's strategic insight ("operators shouldn't have to enter Focus for quick edits") is more architecturally correct than the read-only simplification. If widgets were truly read-only, operators forced into Focus for every micro-update — friction without payoff. If widgets had full editing capability, workspace metaphor muddied — no clear "where do I do which work" answer. Threading the needle: widgets are reference + micro-actions; Focus is considered decisions + complex coordination. Two genuinely different work modes.

Section 12 amended in same session: 12.6 rewritten ("abridged interactive surface" replacing "read-only mirror"); new 12.6a added with 4-test framework + canonical examples table + widget catalog interaction summary; 12.7 entity cards rewritten with bounded-edit set; 12.5 composition rules updated per-surface with interactivity discipline notes; 12.10 reference implementations updated with per-variant interaction declarations. Cross-references to PLATFORM_ARCHITECTURE + PLATFORM_INTERACTION_MODEL all carry the corrected framing.

**Methodology learning canonicalized.** Per-variant interaction declarations are convention for Phase W-1 + W-2, schema-promoted for Phase W-3+ if interaction discoverability becomes catalog-relevant. Phase W-3 widget builds declare per-variant supported interactions in their definition file as documentation-comments + Storybook examples. The canonical examples table in §12.6a is the discipline anchor; new widgets pass the 4 tests for each candidate interaction.

**Variant naming locked: Glance / Brief / Detail / Deep.** User preferred named tiers over generic Compact / Standard / Expanded / Full (investigation proposed). Names map to user mental model ("give me a brief on..."), reinforce platform identity, future-proof surface metaphor (Glance = Watch tier, etc.).

**Sequence locked: W-1 → W-2 (Spaces) → W-3 (cold-start) → W-4 (Pulse).** Investigation proposed W-2 = cold-start, W-3 = Spaces. Revised because Spaces sidebar absorbs widget pins (Spec Decision 2) — widgets need Glance variants from inception, not retroactively bolted on. Pulse becomes more bounded after Spaces-with-widgets exists.

**Cold-start catalog locked at 12 widgets** (4 cross-vertical + 3 funeral-home + 3 manufacturing + 2 cross-surface infrastructure), each with 2-4 declared variants. Phase W-3 ships these.

**September demo strategy.** Per user direction: "build correctly for long-term platform health, timeline measured in days not weeks." Phase W-1 → W-4 all ships pre-September given velocity. Demo narrative: "Same widget library. Vertical-aware visibility. Variant-aware density. Coherent across surfaces. Workspace cores have widget views — bounded interactions in widgets, considered decisions in Focus."

**After spec lock.** Phase W-1 (Foundation) ready to begin. Phases W-1 through W-4 are bounded application of the now-locked spec. Subsequent surface builds (Pulse beyond W-4, expanded Focus types, command-bar peek content composition unification, long-tail dashboard widget migration to declared variants) become bounded application of the canonized library.

**Sequence after Widget Library Phases:** Phase 4.4.4 (slide animation + multi-day functional work) + Aesthetic Arc Sessions 5-9 component-by-component refinement against the locked Pattern 1 + Pattern 2 references unblock simultaneously.

---

### Widget Library Phase W-3a — Foundation Widget Cluster (✅ Shipped, 2026-04-27)

Six commits shipped end-to-end. Phase W-3a delivers the **cross-vertical foundation widget cluster** — four widgets (`today`, `operator_profile`, `recent_activity`, `anomalies`) plus the AncillaryPoolPin retag per the Product Line + Operating Mode canon shipped earlier same day. Establishes the **three-component variant shape** as canonical (proved across two W-2 widgets, now four more); locks the **5-axis filter** end-to-end (5th axis activated by code in this phase); ships **explicit tenant-isolation-at-service-level** discipline for every widget data source. Patterns cleanly generalize for W-3b (saved_view + briefing infrastructure), W-3c (FH arrangement_pipeline), W-3d (manufacturing per-line widgets).

**Commit 1 — AncillaryPool retag + 5-axis filter activation + TenantProductLine vault auto-seed.** Migration `r59_widget_product_line_axis` adds `required_product_line` JSONB column to `widget_definitions` (default `["*"]`); backfills all 28 existing widgets to `["*"]`; retags `scheduling.ancillary-pool` from `required_vertical: ["funeral_home"]` → `["manufacturing"]` + new `required_product_line: ["vault"]` per the canon investigation finding (the scheduling Focus is Sunnycrest's manufacturing operations, not FH — FH-tagging was the bug the canon investigation surfaced). Migration `r60_backfill_tenant_product_lines_vault` backfills `TenantProductLine(line_key="vault")` for every active manufacturing tenant; **preserves `Company.vault_fulfillment_mode` value** via canonical `operating_mode` enum translation per the canon migration plan (`produce → production`, `purchase → purchase`, `hybrid → hybrid`). 9982 vault rows backfilled in dev DB (test pollution from accumulated fixtures; production Sunnycrest gets exactly 1 row). `widget_service.get_available_widgets` extended to 5-axis filter via new `_get_enabled_product_lines(db, tenant_id)` helper. New `seed_default_product_lines(db, company)` helper auto-seeds vault for manufacturing tenants based on `default_for_verticals` registry; wired into `auth_service.register_company` (new tenants) + `seed_staging.py` (testco). **Drift correction (Spec-Override Discipline):** `AVAILABLE_PRODUCT_LINES` catalog renamed `burial_vaults → vault`, `urns → urn_sales`, `rosetta_hardscapes → rosetta` to match canon (BRIDGEABLE_MASTER §5.2). 24 W-2 test fixtures flipped from `funeral_home` → `manufacturing+vault`; `_make_tenant_user_token` helpers extended with optional `product_lines` parameter. The inversion test `test_funeral_home_cannot_pin_manufacturing_vault_widget` flipped from the pre-canon direction (mfg-rejects-FH-widget) to post-canon (FH-rejects-mfg-widget). 60/60 W-1 + W-2 tests passing post-flip; 0 regressions.

**Commit 2 — `today` widget (vertical+line-aware aggregation + multi-line builder pattern).** Cross-vertical foundation widget with **per-vertical-and-line content rendering**. Backend service `today_widget_service.py` resolves "today" in tenant local timezone (`Company.timezone`, default `America/New_York`), dispatches to per-(vertical, active product line) category builders. **Multi-line builder pattern locks the future-proofing shape** — `_build_manufacturing_vault_categories` for vault rows; `_build_manufacturing_redi_rock_categories` plugs in alongside when redi_rock activates without restructuring. Manufacturing+vault tenants get vault deliveries + ancillary pool + unscheduled count breakdown. Other verticals get empty payload + vertical-aware `primary_navigation_target` so the empty-state CTA "Open schedule →" lands somewhere useful (`/dispatch` for mfg, `/cases` for FH, `/interments` for cemetery, `/crematory/schedule` for crematory). Frontend `TodayWidget.tsx` three-component shape (presentation tablet + variant wrappers + dispatcher) per AncillaryPoolPin precedent. Glance variant: Pattern 1 frosted-glass tablet 60×280px with bezel-grip column + eyebrow/subtext/count chip — **same chrome as AncillaryPoolPin Glance** for cross-surface continuity. Brief variant: Pattern 2 solid-fill content with header (eyebrow + date + count chip), body (per-category breakdown rows with `→` chevron, click navigates), footer with empty-state CTA. `useWidgetData` 5-min auto-refresh. Endpoint `GET /api/v1/widget-data/today`. **Tenant isolation explicit** via `Company.id == user.company_id` filter; cancelled deliveries excluded; tenant-local-today resolution. 16 backend tests + 18 frontend tests passing.

**Commit 3 — `operator_profile` widget (auth-context-only widget pattern).** Establishes the canonical pattern: **not every widget needs a backend endpoint**. Reads entirely from `useAuth()` (full user identity + role + permissions/modules/extensions counts) + `useSpacesOptional()` (active space name) — zero new endpoint surface area. Three-component shape per W-3a precedent. Glance: 24×24 initials avatar (`bg-accent-muted` with `text-content-on-accent`) + first/last name + role label; tap to summon `/settings/profile`. Brief: larger 32×32 avatar + full name + email header + role/active-space/access-summary rows + "Manage profile →" footer CTA. Access summary uses singular/plural-aware labels (`1 permission` vs `3 permissions`); extensions row omitted when zero. Defensive null behavior when unauthenticated (returns null rather than crashing). 4 backend catalog tests + 15 frontend tests passing.

**Commit 4 — `recent_activity` widget (V-1c endpoint reuse with additive shim).** Establishes the canonical pattern: **when an existing endpoint is "almost right" for widget consumption, prefer additive Pydantic shim over new endpoint surface area**. V-1c `GET /api/v1/vault/activity/recent` (CrmRecentActivityWidget data source per V-1c roll-up) gained an optional `actor_name: str | None` field populated server-side via User left-join in `activity_log_service.get_tenant_feed`. Existing V-1c consumers ignore the new field (Pydantic optional). No new endpoint. Frontend `RecentActivityWidget.tsx` three-component shape with **all three variants** (Glance + Brief + Detail). Brief shows top 5 events (actor + verb + entity + relative timestamp). Detail adds 4 filter chips (All / Comms / Work / System) collapsing the activity_type taxonomy with proper `aria-selected` semantics + tablist accessibility. View-only per §12.6a — click-through navigates to related CRM company. **First widget shipping with `peek_inline` surface support** per §12.5 — peek panels stay separately routed but compose this widget's components for content. Cross-surface reuse is the pattern; per-surface reinvention is what the widget library prevents. 9 backend tests + 22 frontend tests passing.

**Commit 5 — `anomalies` widget (real production data + bounded state-flip + tenant isolation discipline).** Real production data over stub — backed by existing `agent_anomalies` table (Phase 1+ accounting agent infrastructure: month_end_close, ar_collections, cash_receipts, expense_categorization, etc.). Wilbert licensee tenants running accounting agents have real unresolved anomalies this widget surfaces directly; Phase W-5 (Intelligence-detected anomalies) extends the data source rather than replacing the widget. **Severity vocabulary canonical: 3 levels (`critical`, `warning`, `info`) per `app.schemas.agent.AnomalySeverity` enum** — Spec-Override Discipline note: the user spec mentioned 4-level (critical/high/medium/low); actual production enum has 3 levels. Severity colors map to locked tokens: critical → terracotta (`status-error`), warning → terracotta-muted (`status-warning`), info → `status-info`. Brief + Detail variants — **NO Glance per §12.10** (anomalies need at least Brief context; count alone doesn't communicate severity or actionability). New backend service `anomalies_widget_service.py` with `get_anomalies` (severity-sorted critical → warning → info, then created_at desc) + `resolve_anomaly` (state-flip + audit log via `audit_service.log_action`). UI vocabulary "Acknowledge" maps to data-layer `resolved=true` + optional `resolution_note` (per CLAUDE.md §12: data model uses `resolved`, model precedes the widget; UI vocabulary kept as user's mental model). Endpoints: `GET /api/v1/widget-data/anomalies?severity=...&limit=N` + `POST /api/v1/widget-data/anomalies/{id}/acknowledge`.

**Tenant isolation load-bearing for anomalies.** `agent_anomalies` has no direct `company_id` column; tenant scoping flows through `agent_job_id` FK → `AgentJob.tenant_id`. Every query in the service explicitly joins AgentJob and filters `AgentJob.tenant_id == user.company_id`. The acknowledge endpoint **re-validates tenant ownership BEFORE mutation**; cross-tenant `anomaly_id` returns 404 (not 403, to avoid leaking existence). Verified explicitly via `TestTenantIsolation` test class with both directions tested (read + acknowledge); confirmed an A-tenant user can NEITHER see NOR acknowledge a B-tenant anomaly.

**The Acknowledge action is the canonical §12.6a test case** for widget-appropriate interactions, satisfying all four tests:
1. ✅ Bounded scope: single anomaly per click
2. ✅ No coordination required: independent of other anomalies
3. ✅ Reversible / low-stakes: false-alarm acks can be re-investigated via audit log
4. ✅ Time-bounded: instant

Empty state "All clear" + sage `CheckCircle2` icon — operational signal (good state) without celebratory accent terracotta. 18 backend tests (including dedicated TestTenantIsolation class with explicit cross-tenant fixtures) + 21 frontend tests passing.

**Commit 6 — Integration tests + canon doc updates.** New `test_widget_library_w3a_integration.py` — 19 tests across 5 classes:
- `TestW3aCatalog` — all 4 widgets in catalog; cross-vertical visibility verified for manufacturing + funeral_home + cemetery + crematory
- `TestFiveAxisFilterConformance` — all 4 declare `["*"]` on both vertical + product_line axes
- `TestVariantDeclarations` — parametrized check that each widget's variants match §12.10 reference exactly (today: Glance+Brief, operator_profile: Glance+Brief, recent_activity: Glance+Brief+Detail, anomalies: Brief+Detail). Explicit regression guard: `test_anomalies_explicitly_has_no_glance` — prevents accidental Glance addition in future variant work
- `TestSidebarPinLifecycle` — parametrized test that each widget pinnable to a Spaces sidebar via Phase W-2 widget pin API
- `TestCrossSurfaceCoverage` — all 4 declare `spaces_pin` + `dashboard_grid` + `pulse_grid` in supported_surfaces
- `TestWidgetDataEndpointsResolve` — endpoint shape contracts for today, recent_activity, anomalies; operator_profile flagged as auth-context-only

DESIGN_LANGUAGE.md §12.10 expanded with reference implementations 6-9 covering the new W-3a foundation widgets. Establishes the **cross-vertical + cross-line foundation widget pattern** as canonical reference for future Phase W-3 cluster work. Each widget's reference entry includes: cold-start catalog id, variants declared, surface compatibility, vertical + product line scope, data source, per-variant content + interactions, NOT-supported list (the explicit boundary), reference component file path, notable design decisions.

**Architectural patterns established this phase (cross-cluster):**

1. **Three-component variant shape canonical** — proven across 4 widgets (TodayWidget, OperatorProfileWidget, RecentActivityWidget, AnomaliesWidget) plus the W-2 reference (AncillaryPoolPin). The structure: presentation tablet/card (render-only, no hooks) + variant wrapper (data fetch + navigation handlers) + top-level dispatcher (selects variant via `surface` + `variant_id` props, calls no hooks). Avoids rules-of-hooks violations across variant branches; cross-widget visual continuity via shared chrome vocabulary.

2. **Pattern 1 vs Pattern 2 chrome by surface** — Glance variants on `spaces_pin` use Pattern 1 frosted-glass tablet (60px tall, bezel-grip column, eyebrow/subtext/count chip); Brief + Detail variants on grid surfaces use Pattern 2 solid-fill content (no widget-level chrome — host's `WidgetWrapper` provides card surface; widget renders header + body + footer interior).

3. **Multi-line builder pattern (today widget)** — per-(vertical, line) category builder functions plug into the dispatcher without restructuring. Future-proof for Phase W-3d when redi_rock + wastewater + urn_sales lines activate widget content.

4. **Endpoint reuse over new surface area (recent_activity)** — additive Pydantic shim (`actor_name` field) extended an existing V-1c endpoint instead of building a new one. Existing consumers unaffected.

5. **Tenant isolation explicit at service level (anomalies)** — when a model has no direct `company_id` column, the service explicitly joins through the tenant-bearing FK chain. Acknowledge endpoint re-validates ownership before mutation; cross-tenant id → 404 (existence-hiding). Verified by dedicated `TestTenantIsolation` test class with cross-tenant fixtures.

6. **Real data over stub when production source exists (anomalies)** — `agent_anomalies` is genuine production-emitted data from accounting agents. Wiring to real source ships demo-functional widget on day one; W-5 extends the data source rather than replacing the widget shell.

7. **Auth-context-only widget pattern (operator_profile)** — not every widget needs a backend endpoint. Some widgets render context already in scope (auth, spaces, theme, etc.). Establishes the discipline: a widget's backend surface area should be the minimum needed.

**Final regression posture:**
- Backend: **254 passed, 1 skipped** across W-1 + W-2 + W-3a Commits 1-6 + spaces phases (8e, 8e.1, invariants). 0 regressions.
- Frontend: **634 vitest tests passing** (up from 580 pre-Phase-W-3a). +54 tests added across the 4 new widgets.
- tsc: 0 errors. vite build clean (4.32s).
- Migration head: `r60_backfill_tenant_product_lines_vault` (unchanged from W-3a Commit 1).

**Patterns unblocked for next clusters:**
- W-3b (`saved_view`, `briefing`) — cross-surface infrastructure widgets composing existing endpoints; same three-component shape, same 5-axis cross-vertical scope, same pattern-1-vs-pattern-2 chrome
- W-3c (FH `arrangement_pipeline`) — first vertical-scoped W-3 widget (`required_vertical: ["funeral_home"]`); same shape patterns, vertical-axis filter exercised end-to-end
- W-3d (manufacturing per-line widgets `vault_schedule`, `line_status`, `urn_catalog_status`) — first product-line-scoped widgets (`required_product_line: ["vault"]` etc.); mode-aware rendering hooks, per-line builder pattern (proven by today widget) extends to per-line schedule widgets

**Sequencing after Phase W-3a:** W-3b ships next (saved_view + briefing infrastructure), then W-3c (FH arrangement_pipeline), then W-3d (manufacturing per-line widgets). Phase W-4 (Pulse surface) ships post-W-3 with role-driven default layouts incorporating the now-established widget catalog. Phase 4.4.4 (slide animation + multi-day Focus rendering) and Aesthetic Arc Sessions 5-9 unblock simultaneously per the Phase W-2 entry.

---

### Widget Library Phase W-3b — Cross-Surface Infrastructure Widgets (✅ Shipped, 2026-04-27)

Three commits shipped end-to-end. Phase W-3b delivers the **cross-surface infrastructure widget cluster** — two widgets (`saved_view`, `briefing`) plus a load-bearing widget config plumbing fix (Commit 0) that closes a latent gap surfaced during investigation. Establishes the **config-driven user-authored widget catalog** pattern via `saved_view` (any saved view becomes a widget instance via `config: {view_id}`), and the **per-user scoped narrative widget** pattern via `briefing` (Phase 6 BriefingCard promoted to widget contract without disturbing data path). Patterns generalize cleanly to W-3c (FH arrangement_pipeline) and W-3d (manufacturing per-line widgets).

**Commit 0 — Widget config plumbing fix (load-bearing prerequisite).** The Phase W-2 canon claimed `PinnedSection` carried `pin.config` through to the widget component, but the actual code didn't. Investigation surfaced this as a blocker: `saved_view` reads `config.view_id` and `briefing` reads `config.briefing_type` — without the plumbing both widgets render only their empty states. Fixed in **6 dispatch sites** (per Q1 confirmed scope: sweep ALL of them, not just PinnedSection): extended `WidgetRendererProps` in `widget-renderers.ts` with optional `config?: Record<string, unknown>` field; extended `WidgetState` in `focus-registry.ts` with the same field; updated `Canvas.tsx`, `StackRail.tsx`, `BottomSheet.tsx` (TWO dispatch sites — main + expanded view), `StackExpandedOverlay.tsx`, `PinnedSection.tsx`, and `WidgetGrid.tsx` to pass `config` through to the rendered component. Backward-compat verified: 2 new `PinnedSection.test.tsx` regression tests cover `pin.config` round-trip + null-default; full vitest 636/636 unchanged post-fix.

**Commit 1 — `saved_view` widget (config-driven user-authored widget catalog).** Generic widget rendering any tenant saved view via `config: {view_id: <uuid>}` — establishes the **user-authored widget catalog without widget code** pattern. Single widget definition + per-instance config turns every saved view in `vault_items.metadata_json.saved_view_config` into a widget instance. Tenants extend their effective widget catalog by authoring saved views; no code ship required. Brief + Detail + Deep variants per §12.10 — **NO Glance** because saved views need at minimum a list to be informative; surface compatibility excludes `spaces_pin` for the same reason (sidebar requires Glance per §12.2 compatibility matrix). Per Q2 confirmed scope: thin wrapper around the existing V-1c `SavedViewWidget` (`frontend/src/components/saved-views/SavedViewWidget.tsx`) — zero changes to V-1c, full reuse of its 7 presentation modes (list / table / kanban / calendar / cards / chart / stat) + visibility checks + cross-tenant masking. Brief variant calls V-1c with `showHeader=false` (widget framework chrome provides card surface); Detail + Deep call with `showHeader=true`. Empty state per Q4 fallback (b): when `config.view_id` missing or invalid, renders `Layers` icon + "No saved view configured" + "Pick a saved view from the library to display it here." + "Open saved views library →" link to `/saved-views`. Inline picker dropdown deferred until `PATCH /spaces/{space}/pins/{pin}` endpoint ships; not built as part of W-3b per scope discipline ("widget shipping, not infrastructure expansion"). **Sidebar pin rejection (canonical guard)**: Phase W-2 add_pin surface check rejects `pin_type="widget" + target_id="saved_view"` against a sidebar; defensive fallback in dispatcher renders Detail rather than crashing if a pre-W-2 layout slips through. 4 backend catalog tests + 14 frontend tests passing.

**Commit 2 — `briefing` widget (per-user scoped narrative — Phase 6 BriefingCard promoted to widget contract).** Promotes the existing Phase 6 `BriefingCard` (mounted as a dashboard element on manufacturing-dashboard.tsx + order-station.tsx) to the widget catalog without disturbing the data path. Glance + Brief + Detail variants per §12.10 — **NO Deep** because briefing detail is informationally complete; Deep would just re-render the dedicated `/briefing` page in widget chrome, which §12.6a discourages (heavy actions belong on the page, not the widget). Surface compatibility includes `spaces_pin` (Glance) + `pulse_grid` + `dashboard_grid` + `focus_canvas`; **excludes `peek_inline`** because briefing is per-user content, not entity-scoped — peek panels compose around an entity, briefing has none. Reuses Phase 6 `useBriefing` hook unchanged; per-user scoping enforced server-side by `/briefings/v2/latest` (which filters by `user_id == current_user.id`). The widget never sees other users' briefings — endpoint contract is the security boundary, not the widget. Per-instance briefing-type via `config.briefing_type` ("morning" | "evening", default "morning") so future tenants can pin a Glance "End of day summary" alongside the morning briefing. **Glance variant** (Pattern 1 sidebar treatment): single-line strip with Sunrise/Sunset icon + briefing-type label + unread accent dot. **Brief variant** (Pattern 2 grid treatment): icon + title + narrative excerpt truncated to 320 chars at last-word boundary + active space pill + Unread pill + "Read full briefing →" link. **Detail variant**: full narrative (no truncation) + structured-section preview cards (Queues, Flags, Pending decisions — top 5 each, severity dot per flag) + Read full link. Renders only known structured-section keys; unknown keys silently skipped per the Phase 6 contract. **Coexist-with-legacy discipline (canonical pattern)**: Phase 6 `BriefingCard` stays alive as a page-mounted component; the W-3b `BriefingWidget` is the catalog-citizen widget contract. Same content, different consumers. Future natural-touch refactors may migrate page mounts onto the widget; not a W-3b deliverable. 5 backend catalog tests + 27 frontend tests passing.

**Commit 3 — Integration tests + canon doc updates.** New `test_widget_library_w3b_integration.py` — 13 tests across 5 classes:
- `TestW3bCatalog` — both widgets in catalog; cross-vertical visibility verified for manufacturing + funeral_home + cemetery + crematory
- `TestFiveAxisFilterConformance` — both declare `["*"]` on both vertical + product_line axes
- `TestW3bVariantDeclarations` — parametrized check that variants match §12.10 reference exactly (saved_view: Brief+Detail+Deep, briefing: Glance+Brief+Detail). Explicit regression guards: `test_saved_view_explicitly_has_no_glance` + `test_briefing_explicitly_has_no_deep`
- `TestSidebarPinCompatibility` — saved_view pin to sidebar REJECTED (no Glance); briefing pin to sidebar ACCEPTED with `variant_id="glance"`. Same canon (§12.2 + §12.10), opposite outcomes per widget — both correct, both verified
- `TestConfigPlumbingPersistence` — config JSONB round-trips through pin creation + listing for briefing widget. Closes the Commit 0 plumbing fix at the integration level
- `TestW3bCrossSurfaceCoverage` — both widgets declare grid surfaces; neither declares `peek_inline` (saved_view is multi-row, briefing is per-user — neither is entity-scoped)

DESIGN_LANGUAGE.md §12.10 expanded from 9 → 11 reference implementations covering the W-3b infrastructure widgets. Reference entries 10 + 11 follow the established §12.10 shape (cold-start catalog id, variants, surface compatibility, vertical + product line scope, reference component file path, demonstrates clause, data source, per-variant content + interactions, NOT-supported list, notable design decisions, empty state, coexist-with-legacy discipline note where applicable).

**Architectural patterns established this phase (cross-cluster):**

1. **Config plumbing as load-bearing infrastructure** — pin config carries through every dispatch site uniformly. Without the Commit 0 sweep, both W-3b widgets ship as empty-state-only. Pattern: when a contract claims "X carries through" and adding a feature depends on it, verify with a regression test before assuming the prior phase's claim is implementation, not aspiration.

2. **Config-driven user-authored widget catalog (saved_view)** — single widget definition + per-instance config turns every saved-view-shaped artifact into a widget instance. Tenants extend their effective widget catalog without code ship. Future widgets that surface user-authored content (e.g., dashboards over user-defined queries, custom report widgets) follow the same pattern: catalog-side widget definition + config schema + thin wrapper around the existing rendering primitive.

3. **Promotion-of-existing-surface-to-widget-contract (briefing)** — when an existing primitive renders the right content, prefer thin variant-aware wrapper over rebuild. The Phase 6 `BriefingCard` was already complete-enough; W-3b wraps it in a variant-aware dispatcher without disturbing the data path. Pattern: the widget contract is a presentation contract, not a data contract — existing data paths can stay untouched.

4. **Per-user scoping via endpoint contract, not widget filtering** — the briefing widget itself does no user filtering. It calls a hook which calls an endpoint which enforces `user_id == current_user.id` server-side. The widget can't leak briefings between users because the endpoint won't return them. Pattern: when a widget surfaces per-user data, the security boundary is the endpoint, not the widget — keeps widgets dumb-render and pushes contract enforcement to the trustworthy layer.

5. **Coexist-with-legacy discipline made explicit (briefing)** — Phase 6 `BriefingCard` stays alive as a page-mounted component; W-3b `BriefingWidget` is the catalog-citizen widget contract. Different consumers, same content. Pattern formalized: phase work that "promotes" an existing surface to a new contract should NOT delete the original surface unless explicitly scoped to migrate consumers. Migration-by-natural-touch keeps phase scope tight + avoids breaking active consumers.

6. **Same canon, opposite per-widget outcomes (sidebar pin compatibility)** — saved_view rejected for sidebar pin (no Glance), briefing accepted (declares Glance + spaces_pin). §12.2 + §12.10 produce different outcomes per widget; both correct, both verified at the integration level. Pattern: §12.2's compatibility matrix is the gate; widgets self-declare; the gate enforces; per-widget tests verify.

**Final regression posture:**
- Backend: **148 passed** across W-1 + W-2 + W-3a + W-3b widget library suite (W-3a 19 + W-3b 13 + W-3a per-widget 60 + W-3b per-widget 9 + W-1/W-2 47). 0 regressions.
- Frontend: **677 vitest tests passing** (up from 634 pre-Phase-W-3b: +14 SavedViewWidget + 27 BriefingWidget + 2 PinnedSection config-plumbing regression).
- tsc: 0 errors. vite build clean (4.55s).
- Migration head: `r60_backfill_tenant_product_lines_vault` (unchanged — W-3b ships zero schema changes; widget definition seed + config plumbing only).

**Patterns unblocked for next clusters:**
- W-3c (FH `arrangement_pipeline`) — first vertical-scoped W-3 widget (`required_vertical: ["funeral_home"]`); same three-component shape; can compose `saved_view` widget instances if FH-shaped saved views serve the data path, OR ship dedicated catalog widget per the canon decision when investigation lands
- W-3d (manufacturing per-line widgets `vault_schedule`, `line_status`, `urn_catalog_status`) — same patterns; mode-aware rendering hooks; per-line builder pattern (proven by today widget) extends to per-line schedule widgets
- Future narrative-widget promotions (briefing pattern generalizes) — any existing dashboard component that renders informationally-complete content can be promoted to widget contract via thin variant-aware wrapper

**Sequencing after Phase W-3b:** W-3c (FH arrangement_pipeline) ships next, then W-3d (manufacturing per-line widgets). Phase W-4 (Pulse surface) ships post-W-3 with role-driven default layouts incorporating the full W-3 catalog (4 cross-vertical foundation + 2 cross-surface infrastructure + arrangement_pipeline + per-line schedule widgets + line_status). Phase 4.4.4 (slide animation + multi-day Focus rendering) and Aesthetic Arc Sessions 5-9 still unblocked per the Phase W-2 entry.

---

### Spaces and Pulse Architecture Canon Session (✅ Documented, 2026-04-27)

**Context.** Phase W-3 widget catalog work nearly complete (W-3c FH widget intentionally deferred per manufacturing-vertical focus). Phase W-4 Pulse surface preparation surfaced fundamental architectural question: was Pulse "widget grid per Space" or genuinely intelligent composition?

User clarified: only Home Space has Pulse. Other Spaces have standard dashboards. Pulse aggregates everything relevant across user's work; well-composed Pulse means user rarely needs custom Spaces. Custom Spaces are fallback when Pulse fails to surface what user needs.

This insight made clear that Phase W-4 as drafted (widget-grid-per-Space) was wrong architecture. Canon session ran to lock Spaces taxonomy + Pulse mechanics before Phase W-4 implementation propagated wrong mental model.

**Decisions locked.**

**Six Space types:**
1. Home Space (Pulse — intelligent)
2. My Stuff Space (user-personal — standard dashboard)
3. Custom Spaces (user-created operational — standard dashboard, optional, multiple)
4. Settings Space (its own Space, separate canon TBD)
5. Cross-tenant Spaces (separate canon TBD)
6. Portal Spaces (Family / Driver / CPA / etc. — Spaces with constrained permissions, separate canon per portal type)

**Pulse architecture:**
- Tetris composition (intelligence-driven sizing + position, not widget grid)
- Two content primitives:
  - Pinable widgets (Widget Library catalog) — bounded, multi-surface, user-pinable in My Stuff/Custom
  - Pulse intelligence streams (Pulse-specific) — intelligence-generated, not pinable, render in Pulse only
- Layered composition (Personal / Operational / Anomaly / Activity) with multi-stream support per layer
- Three intelligence tiers: rule-based (Tier 1) + signal-driven (Tier 2) + synthesized (Tier 3)
- Compact viewport-fit content density
- Subtle "composed" visual affordance (brass-thread accents on intelligence stream pieces)

**Onboarding model:**
- Work areas multi-select (Accounting / HR / Production Scheduling / Delivery Scheduling / Inside Sales / Inventory Management / Customer Service / Family Communications / Cross-tenant Coordination / [extensible])
- Natural-language responsibilities description (free text)
- Replaces traditional role-based provisioning
- Both stored at user level
- Work areas drive Tier 1 rule-based composition; responsibilities feed Tier 2+ intelligence

**Implementation sequencing (structurally correct order):**
1. **Phase W-4a — Pulse Infrastructure** (independent of communication primitives)
2. **Layer 1 — Native Primitives**: Email + Calendar + SMS (parallel-able cluster)
3. **Layer 2 — Document Creation Surface** (parallel with Email completion)
4. **Layer 3 — Onboarding Work Areas + Responsibilities** (parallel)
5. **Phase W-4b — Pulse Intelligence Streams** (lights up against real Layer 1/2/3 data)
6. **Phase W-5 — Standard Spaces Dashboards** (My Stuff + Custom)
7. **Command Bar** (plugin architecture against complete primitives)
8. **Polish + Demo Preparation** (Phase 4.4.4, Aesthetic Arc 5-9, demo data, rehearsal)

**Native Calendar primitive identified.** Initially missed; user surfaced it. Calendar joins Email + SMS in Layer 1 native primitives. Composes with: scheduling Focus, vault_schedule widget purchase mode, sales order Focus, future portals, Pulse intelligence streams. Built for composition from start.

**Strategic principles:**
- Pulse as differentiator (not standard SaaS dashboard pattern)
- Custom Space creation rate = Pulse health metric
- Communication-prerequisites discipline (Pulse intelligence depends on communication primitives existing)
- Compose-first primitive design (Calendar/Email/SMS designed for composition, not standalone)
- Build maximally, structurally correctly (scope set by demo vision, not timeline anxiety)
- 20-week timeline (April 27 → late September) achievable at current velocity with disciplined parallelization

**Architectural significance.** This canon session resolved Spaces architecture at Section 12-equivalent depth — same level of architectural commitment as Widget Library Architecture canon. Future Pulse, Spaces, primitive, and composition decisions inherit from this canon.

Same pattern as Product Line + Operating Mode canon (April 26) and SalesOrder vs Delivery + Ancillary Independence canon (April 27): user surfaced architectural question before implementation propagated wrong assumption; investigation + thinking-through resolved direction; canon locked; implementation proceeds correctly.

Cumulative pattern across the past few days: founder architectural intuition + investigation discipline + canon locking = platform coherence at scale most solo founders never achieve.

**Documentation output:**
- **BRIDGEABLE_MASTER.md §3.26 — Spaces and Pulse Architecture** (new major section under the §3.x architecture cluster, immediately after §3.25 Widget Library Architecture)
- **DESIGN_LANGUAGE.md §13 — Spaces and Pulse Visual System** (new section)
- **AESTHETIC_ARC.md — this entry**

**Phase W-4a implementation unblocked.** Phase W-4a Pulse infrastructure can now proceed against locked architecture. Implementation prompt drafted in next session against this canon as authoritative reference.

**Sequencing forward.** Phase W-4a (Pulse infrastructure) is the next implementation cluster. Multi-session work estimated 2-3 weeks. After Phase W-4a lands, Layer 1 communication + temporal primitives sequence begins (Email → Calendar overlap → SMS finishing parallel).

Calendar primitive joins Layer 1 — substantial addition to original sequencing, identified mid-session via user surfacing.

September Wilbert demo timeline: 20 weeks of work in 20 weeks of calendar. Achievable.

---

### Phase W-4a Step 6 — Pulse Viewport-Responsive Architecture Canon Session (📐 Canon locked, 2026-05-03)

**Canon-only session.** No code shipped. Canon settled before implementation. Implementation follows in scoped multi-commit session(s) post-canon-lock.

User feedback after Step 5 visual verification: Pulse should fill viewport. Pieces should scale with viewport (same composition, same info, but visual size scales linearly). Larger viewport → bigger pieces (readable). Smaller viewport → smaller pieces (still readable). No empty space at bottom.

This was a meaningful architectural reframe. Pre-Step-6 §13.3.1 canon ("auto-fit collapse intentional, not regression") proved insufficient against canonical user perception. The locked-Apr-28 canon was correct against test-data verification at the time of W-4a Commit 5 ship — PulseSurface tests confirmed the auto-fit math, dev DOM measurements confirmed the layout. But production usage with actual tenant data + actual operator workflows surfaced the perception model the test data couldn't reveal: operators expect Pulse to fill the viewport, the way a Bloomberg Terminal or a calendar app fills its window. Whitespace at the bottom of a "primary monitor surface" reads as "this isn't ready" rather than as "deliberate composition."

**Canon revision discipline.** Locked canon CAN be invalidated by production usage feedback. The Step 5 + Step 6 revisions establish the post-September pattern: locked canon is the working state at the time of lock; production-usage feedback after a real-world cycle of dogfooding is the next gate. Canon revision is not failure — canon revision after production-usage signal is the system working. The discipline: when locked canon needs revision, run a fresh canon session (this one) with full proposal + trade-off analysis + amendment scope, then ship doc updates as a single canon-lock session before code work begins. Don't piecemeal-amend canon during implementation; the implementation path is brittle if it depends on shifting canon.

**Canon-vs-implementation drift detection (extended from Step 5)**. Step 5 established the live-DOM-measurement pattern for canon-vs-implementation audits. Step 6 extends: also measure against **user-perception canon**, not just visual-canon. The visual canon was honored (Pattern 2 chrome present, brass-thread divider rendering, layer ordering correct) but the user-perception canon (Pulse fills its primary surface viewport) was implicit + unspoken until production usage surfaced it. Future canon work should articulate user-perception expectations explicitly, not just visual-token expectations.

**8 canon questions resolved** (full proposal in session log):
1. Sizing model: tiered fixed columns (2/4/6) + fractional viewport-derived rows
2. Layer height allocation: row-count-weighted with empty-layer fixed allowance
3. Widget scale-awareness: `--pulse-scale` CSS variable + container queries for density tiers
4. Reserved chrome budget: client-computed via observer pattern (hard-coded constants for September; dynamic ResizeObserver canonical post-September)
5. Minimum readable threshold: mobile (`< 600 px`) falls back to natural-height scroll; tier-three threshold (`cell_height < 80 px`) also falls back
6. Maximum scale ceiling: `--pulse-scale` clamps at 1.25× — additional viewport space → breathing room (Apple Pro app discipline)
7. Empty slot handling: agency-dictated — Pulse silently filters (Philosophy A); PinnedSection shows `MissingWidgetEmptyState` (Philosophy B). CI parity test mandatory.
8. Content truncation: container queries select default / compact / ultra-compact density per cell size; workspace-core widgets exempt from aggressive compaction (preserve workspace shape per §13.3.2.1, fall back to scroll within piece if can't fit).

**Canon updates locked (this session)**:
- DESIGN_LANGUAGE §13.3.1 — REWRITE viewport behavior (tier-based 2/4/6 cols, viewport-fit canon, mobile + tier-three fallback to scroll)
- DESIGN_LANGUAGE §13.3.2 — AMEND cell-height consistency across layers + 300ms ease-out transition discipline + empty-layer advisory fixed allowance (32px)
- DESIGN_LANGUAGE §13.3.4 — NEW viewport-fit math (chrome budget formula, `--pulse-content-height`, `--pulse-scale` clamp formula, layer row-count weighting, transition timing, full constants table)
- DESIGN_LANGUAGE §13.4.1 — AMEND container queries canonical for Pulse density; surface prop for non-Pulse surfaces; per-widget density tier opt-in; workspace-core exemption
- DESIGN_LANGUAGE §13.4.3 — NEW agency-dictated error surface (platform-composed silent filter; user-composed visible placeholder; CI parity test mandatory)
- BRIDGEABLE_MASTER §3.26.2.1 — minor amendment (tetris composition viewport-fit implementation note)

**Implementation scope** (separate session(s), 6-commit boundary):
1. Chrome budget + grid math foundation (PulseSurface ResizeObserver + `--pulse-content-height` + `grid-template-rows: repeat(N, 1fr)`)
2. Tier-based columns + container queries on opt-in widgets
3. Mobile fallback + scroll edge case + tier-three threshold
4. Empty slot filter at PulseLayer level + console.warn + CI parity test
5. Per-widget density tier rendering (anomalies / line_status / today / etc opt-in)
6. §13.8 reference implementations at 5 viewport sizes (10 screenshots) + final canon doc verification

Realistic estimate: **~10-12 hr implementation + ~3 hr canon docs (this session) + ~3 hr visual verification = ~16-18 hr total**. Scoped per natural commit boundary, multi-session feasible.

§13.8 reference implementations DEFERRED until implementation completes. Final doc verification (post-implementation) confirms canon + implementation aligned.

---

### Phase W-4a Step 5 — Pulse Pattern 2 chrome + missing-widget honesty (✅ Shipped, 2026-05-02)

**Implementation-drift-from-canon** session. The chrome was correct in canon; implementation drifted. Specifically: §11 Pattern 2 + §13.4.1 specify Pattern 2 chrome (rounded-[2px] + bg-surface-elevated + border-border-subtle + shadow-level-1) for pinable widget pieces. PulsePiece's docstring claimed "the widget renderers carry their own Pattern 2 chrome" — that was an incorrect assumption made during Phase W-4a Commit 5. Only `WidgetWrapper` (dashboard surface) applied chrome; widget renderer roots had only content layout (`flex flex-col h-full p-4`). Pulse pieces rendered without ANY chrome at all, producing the user-reported "scattered" perception. Step 5 ships PulsePiece as the chrome-applying surface (mirrors WidgetWrapper for dashboard), retires AnomalyIntelligenceStream's previously-duplicated chrome (single source of truth), and locks the chrome-is-surface-responsibility convention into DESIGN_LANGUAGE §13.4.1.

Plus a related bug surfaced in the same investigation: `MockSavedViewWidget` was the fallback for ALL `getWidgetRenderer` misses including registered-but-unmapped widget keys. In production this masked a real widget-id mismatch (`scheduling.ancillary-pool` backend / `funeral-scheduling.ancillary-pool` frontend) by silently substituting fake "Recent Cases" mock data. New `MissingWidgetEmptyState` component splits the fallback: undefined widgetType → MockSavedViewWidget (legacy/test path); set-but-unmapped → honest "Widget unavailable" empty state in status-warning palette. Dev fixtures should fail visibly in production, not substitute as content.

**Pattern lesson canonicalized for future drift**: when a docstring claims a contract that the implementation doesn't fulfill, the gap is invisible until something forces the contract to be exercised. PulsePiece's Pattern 2 chrome contract was claimed for ~5 weeks before user observation surfaced the drift. AESTHETIC ARC implementation work should periodically audit chrome contracts against actual rendering DOM (`getComputedStyle(piece).backgroundColor` vs declared canon). Step 5's investigation method (live DOM measurement of actual border/background/shadow values) becomes the canonical audit pattern for future canon-vs-implementation reviews.

**Architectural debt surfaced for separate follow-up**: AncillaryPoolPin currently only renders inside Funeral Scheduling Focus subtree (depends on `SchedulingFocusDataProvider`). Backend declares `supported_surfaces: ["pulse_grid", ...]` for the widget — a contract the frontend can't fulfill. Phase W-3d's "First workspace-core widget canonical reference" promise needs the cross-surface portability the canon implies (Phase W-3d entry, line 808). Refactor scope: switch to `useSchedulingFocusOptional`, add `/widget-data/ancillary-pool` backend endpoint, surface-aware rendering (no drag handles in pulse_grid per §12.6a). Earns its own session.

---

### Phase W-4a — Pulse Infrastructure (✅ Shipped, 2026-04-28)

Six commits shipped end-to-end against the Spaces and Pulse Architecture canon (April 27). Phase W-4a delivers **Home Pulse infrastructure** as the first concrete realization of BRIDGEABLE_MASTER §3.26 — composition engine, four layer services, V1 anomaly intelligence stream, signal collection, frontend tetris layout, first-login banner, and the canonical Sunnycrest dispatcher demo composition end-to-end. Three load-bearing references locked for downstream phases (W-4b, W-5, communication primitives, Tier 2): work-area-to-widget mapping, two-content-primitive contract, standardized signal metadata shapes.

**Strategic significance.** Phase W-4a is the platform's most distinctive product feature — the Pulse — shipped to production-ready depth ahead of the September Wilbert demo. Custom Spaces and My Stuff exist as fallback for when Pulse fails to surface what users need; Pulse is the differentiator competitors cannot easily replicate without similarly-deep platform-level intelligence infrastructure (per §3.26.7.1). The infrastructure-first sequencing per §3.26.7.2 means Pulse intelligence streams ship against real Layer 1/2/3 communication primitives in W-4b; nothing in W-4a is stub work that gets refactored when primitives land.

**Six D-decisions resolved before Commit 1 began.** Pre-build investigation phase ran three parallel sub-agents to lock six architectural questions into canonical contracts: D1 composition cache strategy (in-memory dict, 5-min TTL, work_areas-hash key), D2 tetris layout engine (custom CSS Grid, no third-party dependency), D3 layer ordering enforcement (both backend + defensive frontend re-sort), D4 first-login fallback (vertical-default with `metadata.vertical_default_applied=true` flag), D5 Sunnycrest dispatcher canonical composition (locked verbatim), D6 V2 Haiku-cached anomaly synthesis (deferred to W-4b; V1 deterministic ships now), D7 legacy `spaces/pulse_compositions.py` retirement (retired with grep-verified zero importers).

**Commit 1 — Schema + Home system space + onboarding (25 backend tests).** Migration `r61_user_work_areas_pulse_signals` adds `User.work_areas` (JSONB array, nullable) + `responsibilities_description` (text, nullable) + `pulse_signals` table with standardized JSONB metadata column + composite indexes for the aggregation hot paths. Home system space added to `SYSTEM_SPACE_TEMPLATES` — gate-less, leftmost in DotNav, `default_home_route="/home"`, `is_system=True`. Login defensive re-seed in `auth_service.login_user` widened to fire on missing-Home as well as missing-Settings (closes a Phase 8e.2.2-shape gap proactively — no active user can have an empty `preferences.system_spaces_seeded`). Operator profile editor service + `GET / PATCH /api/v1/operator-profile` endpoint with partial-update semantics + canonical `WORK_AREAS` vocabulary list returned in every response.

**Commit 2 — Four layer composition services + work-area mapping locked (28 backend tests).** `personal_layer_service` (assigned tasks + approvals waiting from Phase 5 task system + approval gate), `operational_layer_service` (work-area-to-widget mapping authoritative for §3.26.3.1 vocabulary; vertical-default fallback per D4), `anomaly_layer_service` (raw `agent_anomalies` widget + intelligence stream pointer), `activity_layer_service` (V-1c recent activity feed). Mapping documented inline in `operational_layer_service.py` as the canonical work-area-vocabulary source of truth. Tenant + extension awareness via 5-axis widget filter pre-check.

**Commit 3 — Composition engine + Pulse API + V1 anomaly intelligence + cache + retire pulse_compositions.py (27 backend tests).** `composition_engine.compose_for_user` orchestrates the four layer services + synthesizes the V1 anomaly intelligence stream (deterministic — frequency-weighted severity ordering + canonical title + narrative prose). 5-minute composition cache with work_areas-hash-aware key (`pulse:{user_id}:{work_areas_hash}:{minute_window}`) — work_areas update changes the key + next request misses + recomputes. `GET /api/v1/pulse/composition[?refresh=true]` single endpoint per D1; tenant + user scoping forced server-side. Legacy `spaces/pulse_compositions.py` retired with grep-verified zero importers + a regression test pinning the retirement.

**Commit 4 — Signal tracking endpoints + service + 3 aggregation helpers (26 backend tests).** `POST /pulse/signals/dismiss` + `/pulse/signals/navigate` with standardized JSONB metadata shapes (`{component_key, time_of_day, work_areas_at_dismiss}` and `{from_component_key, to_route, dwell_time_seconds}` respectively — load-bearing for Tier 2 algorithms). Three aggregation helpers ready for Tier 2 consumption: `get_dismiss_counts_per_component`, `get_navigation_targets`, `get_engagement_score`. Phase W-4a does NOT consume them; battle-tested + ready so Tier 2 algorithm work post-September iterates against accumulated production data, not unproven helpers. Tenant + user scoping enforced server-side at every layer.

**Commit 5 — Frontend Pulse rendering (26 vitest tests, 757 total frontend regression).** `frontend/src/components/spaces/PulseSurface.tsx` consumes the API; `PulseLayer.tsx` renders pieces in a custom CSS Grid (`grid-cols-[repeat(auto-fit,minmax(160px,1fr))] auto-rows-[80px] gap-3`) honoring per-piece `cols / rows` from the composition engine; `PulsePiece.tsx` dispatches the two content primitives via `LayerItem.kind`; `AnomalyIntelligenceStream.tsx` is the V1 reference for §13.4.2 chrome treatment with brass-thread top edge via `before:` pseudo-element; `PulseFirstLoginBanner.tsx` renders inline above all layers when `metadata.vertical_default_applied && shouldShow` per §13.6, dismissal cross-device via `useOnboardingTouch` hook. Brass-thread divider above Operational layer per §13.3.2 (1px solid terracotta accent at 30% alpha — passes cover-with-hand test). Empty-layer advisories in italic content-muted typography. Visual verification both modes coherent (warm cream ↔ warm charcoal substrate; single-value accent across modes per Aesthetic Arc Session 2).

**Commit 6 — Sunnycrest demo State B + integration tests + canon docs (18 integration tests, 124 total backend regression).** Sunnycrest dispatcher composition verified end-to-end: `work_areas = ["Production Scheduling", "Delivery Scheduling", "Inventory Management"]` + responsibilities text → vertical_default_applied=false → operational layer matches the canonical D5 set (`vault_schedule` Detail + `scheduling.ancillary-pool` Brief + `line_status` Brief + `today` Glance; `urn_catalog_status` Glance only when `urn_sales` extension active — verified live via the `/api/v1/pulse/composition` endpoint against testco demo tenant). Integration tests at `backend/tests/test_phase_w4a_integration.py` cover four shapes — composition end-to-end through the API, signal collection flow, Sunnycrest dispatcher composition specifically, first-login flow including cache-invalidation through `PATCH /operator-profile`. **DESIGN_LANGUAGE §13.8 expanded with eight locked Phase W-4a reference implementations** (Home Pulse Sunnycrest dispatcher canonical State A + State B; PulseSurface tetris grid; brass-thread divider; PulsePiece two primitives; AnomalyIntelligenceStream V1; PulseFirstLoginBanner; signal collection chrome; empty-layer advisory pattern). **BRIDGEABLE_MASTER §3.26.8 added with seven subsections** (six-commit ship sequence; six D-decisions resolved; canonical work-area-to-widget mapping; two content primitives locked contract; signal collection metadata shapes; implementation deviations from §3.26.6.1; what's wired now vs deferred to W-4b).

**Architectural patterns established this phase.**

1. **Two-content-primitive Pulse**: every Pulse piece is `kind="widget"` (registry-dispatched widget renderer with surface=pulse_grid + variant + config + cols + rows) or `kind="stream"` (registry-dispatched intelligence stream renderer with stream_id matching synthesized content at composition top level). Future Pulse content extends the registry, not the primitive set.
2. **Work-area mapping as authoritative vocabulary**: `operational_layer_service.WORK_AREA_WIDGET_MAPPING` is the single source of truth for §3.26.3.1 work-area vocabulary → §3.26.2.4 composition rules. New work areas land here; new widget surfacings land here; the layer service file is THE reference.
3. **Standardized signal metadata as Tier 2 contract**: dismiss + navigation signal metadata shapes documented in the migration AND signal_service module — load-bearing for Tier 2 pattern matching. Any new signal type post-W-4a must define its shape in both places.
4. **Vertical-default fallback flag as banner gate**: `metadata.vertical_default_applied` is the single discriminator the frontend uses to decide whether to render `PulseFirstLoginBanner`. Tier 2 may eventually adjust composition based on engagement; the banner gate stays this single boolean.
5. **Shared persistence + distinct visual treatment**: `PulseFirstLoginBanner` shares the `useOnboardingTouch` hook with Phase 7's `OnboardingTouch` tooltip primitive but renders inline-with-content. When the same conceptual signal needs different chrome on different surfaces, share persistence + ship distinct visual primitives.
6. **Cache-invalidation through key shape, not active eviction**: composition cache invalidates because the work_areas hash changes the key, not because anyone explicitly evicts the old key. Same shape works for any per-user-derived cache where the derivation inputs are part of the key.
7. **`/home` route, not `/pulse`**: Home Space is the user-facing concept; Pulse is its content per §3.26.1.1. Route names follow user concepts, not implementation primitives.
8. **Build infrastructure-first per §3.26.7.2**: V1 anomaly intelligence stream ships now (deterministic synthesizer); communication-dependent streams (smart email, briefing, cross-tenant coordination, conflict detection) wait for Layer 1 + Layer 2 primitives. The structurally correct sequence avoided ~3 weeks of stub-work-then-refactor cost.

**Final Phase W-4a regression posture.** **124 backend tests passing** (Commit 1: 25 + Commit 2: 28 + Commit 3: 27 + Commit 4: 26 + Commit 6 integration: 18 = 124). **Frontend 757/757 vitest passing** (+26 PulseSurface tests). **tsc 0 errors. vite build clean.** Visual verification both light + dark mode (warm cream ↔ warm charcoal substrate; single-value terracotta accent across modes; brass-thread divider passes cover-with-hand subtlety test; breathing-room composition functional). **No regressions** across Widget Library W-1 + W-2 + W-3a + W-3b + W-3d + Spaces Phases 1-8e.2.3 + Aesthetic Arc Sessions 1-4 + Phase II Batches 0/1a/1b. Migration head: `r61_user_work_areas_pulse_signals` (unchanged from Commit 1 — no further schema changes through Commits 2-6).

**Sequencing forward.** Layer 1 communication + temporal primitives cluster begins (Email → Calendar overlap → SMS finishing parallel) per §3.26.6.2. Phase W-4b ships the remaining intelligence streams against real Layer 1/2 data. Phase W-5 ships My Stuff + Custom Spaces dashboards. Aesthetic Arc Sessions 5-9 + Phase 4.4.4 (slide animation + multi-day Focus rendering) remain unblocked.

**The Pulse is shipped.** What competitors cannot easily replicate is now production-ready against real testco data. State A + State B both verified visually + end-to-end. The September Wilbert demo's most distinctive product feature exists today.

---

### Widget Library Phase W-3d — Manufacturing Per-Line Widgets (✅ Shipped, 2026-04-27)

Four commits shipped end-to-end. Phase W-3d delivers the **manufacturing per-line widget cluster** — three widgets (`vault_schedule`, `line_status`, `urn_catalog_status`) plus the **ancillary-independence + SalesOrder-vs-Delivery canon** captured in BRIDGEABLE_MASTER §5.2.5 to prevent future drift. **First cluster activating the 5-axis filter end-to-end** — vertical + product_line + extension axes all exercised concretely (W-3a + W-3b cross-vertical clusters all used `"*"`). **First workspace-core widget canonical reference** (`vault_schedule`) per DESIGN_LANGUAGE §12.6. **First cross-line aggregator using the multi-line builder pattern** (`line_status`). **First widget testing `required_extension` axis** (`urn_catalog_status`).

**Pre-build investigation surfaced foundational architectural question.** User asked: "shouldn't kanban + scheduling widgets reference the actual SalesOrder rather than a separate Delivery entity? Dragging in kanban should just update a driver field on the SalesOrder." Three parallel agents audited; all three converged on the same answer: **Delivery is the canonical logistics entity, SalesOrder is the canonical commercial entity, and they are intentionally distinct concerns.** User's clarification that ancillaries are INDEPENDENT SalesOrders (not line items / sub-orders) sharpened the canon and was captured in BRIDGEABLE_MASTER §5.2.5 to prevent future Sonnet sessions from inferring nested commercial semantics. The SalesOrder vs Delivery investigation became a load-bearing canon-clarification for the entire scheduling stack going forward.

**Commit 1 — `vault_schedule` widget (workspace-core canonical reference + mode-aware rendering).** First concrete workspace-core widget per DESIGN_LANGUAGE §12.6 — renders the SAME data the scheduling Focus kanban core consumes with a deliberately abridged interactive surface (mark hole-dug, drag delivery between drivers, attach/detach ancillary, update single ETA per §12.6a; finalize / day-switch / bulk reassignment remain Focus-only). Glance + Brief + Detail + Deep variants — full set, since workspace-core widgets are first-class. **Mode-aware rendering** per BRIDGEABLE_MASTER §5.2.2: production mode reads `Delivery` rows (kanban shape), purchase mode reads incoming `LicenseeTransfer` rows (this tenant as `area_tenant_id`), hybrid composes both stacked. Backend service `vault_schedule_service.py` reads `TenantProductLine(line_key="vault").config["operating_mode"]` and dispatches per mode. New endpoint `GET /api/v1/widget-data/vault-schedule?target_date=...`. Frontend `VaultScheduleWidget.tsx` three-component shape per established Phase W-3a/W-3b precedent (presentation tablets + dispatcher); per-section rendering for production driver lanes + purchase incoming buckets; ancillary attachment count surfaced inline as ride-along signal (canon §5.2.5: pure logistics, no commercial nesting). Empty states: "Vault not enabled" (no product line) + "Nothing scheduled" (line enabled, no work). 17 backend tests + 24 frontend tests passing.

**Commit 2 — `line_status` widget (cross-line aggregator + multi-line builder pattern).** First concrete cross-line aggregator + canonical multi-line builder pattern (mirrors `today_widget_service.py`). Brief + Detail variants — NO Glance per §12.10 (operational health doesn't compress to count-only). Cross-line scope (`required_product_line=["*"]`) — renders for whichever lines the tenant has activated. Per-line health vocabulary canonical: `on_track / behind / blocked / idle / unknown`. Vault health real today (composes `Delivery` count + driver assignment distribution per mode); redi_rock / wastewater / urn_sales / rosetta render placeholder rows with `status="unknown"` until each line's metrics aggregator ships — multi-line builder pattern keeps the dispatcher clean while future lines plug in. Backend service `line_status_service.py` with per-line builders. Frontend `LineStatusWidget.tsx` renders per-line breakdown with status icons + headline metrics + per-row click-through. `data-attention="true"` widget-root attribute when any line is `behind / blocked` for visual emphasis hooks. 11 backend tests + 16 frontend tests passing.

**Commit 3 — `urn_catalog_status` widget (first extension-gated widget).** First widget exercising `required_extension="urn_sales"` — Phase W-1 implemented extension gating in `widget_service.get_available_widgets`; W-3a + W-3b cross-vertical widgets all used `"*"`. urn_catalog_status is the first concrete activation: visible only to tenants with the `urn_sales` extension activated AND the urn_sales product line enabled. Glance + Brief variants — catalog management lives at `/urns/catalog` (the page); widget surfaces health (SKU counts, low-stock identification, recent order count). Backend service `urn_catalog_status_service.py` aggregates `UrnProduct` (active + non-discontinued counts split by `source_type`), `UrnInventory` (low-stock: `qty_on_hand <= reorder_point AND reorder_point > 0`; reorder_point=0 means "no monitoring" and is excluded), `UrnOrder` (recent orders over last 7 days). Frontend `UrnCatalogStatusWidget.tsx` four metric rows (Stocked / Drop-ship / Low stock / Orders 7d) + low-stock list with format `{sku} {name} {qty_on_hand}/{reorder_point}` + click-through to catalog. 10 backend tests (including 3 dedicated extension-gating end-to-end tests proving the filter actually gates) + 14 frontend tests passing.

**Commit 4 — Integration tests + canon doc updates.** New `test_widget_library_w3d_integration.py`: 20 tests across 7 test classes:
- `TestW3dCatalog` — all 3 widgets in catalog for full mfg+vault+urn_sales tenant; vault_schedule invisible to FH
- `TestFiveAxisFilterEndToEnd` — extension axis filters urn_catalog_status (invisible without extension, visible with extension); product_line axis filters vault_schedule without vault line; vertical axis filters all 3 for non-mfg
- `TestW3dVariantDeclarations` — parametrized check that variants match §12.10 reference exactly + explicit regression guard `test_line_status_explicitly_has_no_glance`
- `TestW3dSidebarPinCompatibility` — vault_schedule + urn_catalog_status accepted (Glance + spaces_pin); line_status rejected (no Glance)
- `TestWorkspaceCoreCanon` — vault_schedule supports all grid surfaces + has full variant set per §12.6 reference
- `TestCrossClusterRegression` — W-3a + W-3b widgets still present after W-3d additions
- `TestW3dEndpointContracts` — all 3 endpoints respond with expected shape

DESIGN_LANGUAGE.md §12.10 expanded from 11 → 14 reference implementations covering the W-3d manufacturing per-line widgets. Reference entries 12 (vault_schedule), 13 (line_status), 14 (urn_catalog_status) follow the established §12.10 shape with the additional canonical content: vault_schedule explicitly references the SalesOrder vs Delivery investigation + ancillary-independence canon (BRIDGEABLE_MASTER §5.2.5); line_status documents the per-line health vocabulary + multi-line builder pattern as canonical reference; urn_catalog_status explicitly flags itself as the first widget exercising the `required_extension` axis end-to-end.

**BRIDGEABLE_MASTER §5.2.5 — new canonical section** capturing SalesOrder vs Delivery distinction + ancillary independence. Load-bearing for future Sonnet sessions: prevents drift to the (incorrect) inference that ancillaries are line items / sub-orders of a parent vault SalesOrder. Explicit articulation: "each item type is sold independently. A funeral home customer ordering a vault, an urn, and a cremation tray creates THREE SalesOrders (one per item type), each with its own commercial lifecycle. Each SalesOrder produces at least one Delivery work unit; sometimes multiple. The ancillary `attached_to_delivery_id` relationship is logistics-only — when an urn Delivery is 'attached' to a vault Delivery, the two Delivery work units ride the same truck; the two SalesOrders remain entirely independent commercially." Two minor follow-ups flagged for post-W-3d cleanup (FK constraint on `Delivery.order_id`; SalesOrder→Delivery one-way sync semantics review).

**Architectural patterns established this phase (cross-cluster):**

1. **5-axis filter activated end-to-end** — vertical + product_line + extension axes all exercised concretely. Test: `TestExtensionGatingEndToEnd` with three scenarios (no extension → invisible; extension activated → visible; extension activated + product_line missing → invisible) proves AND-wise filter semantics. Future widgets gating on extension axis follow this exact test pattern.

2. **Workspace-core widget canonical pattern (§12.6)** — vault_schedule is the reference implementation. Renders the SAME data as the Focus core, deliberately abridged interactive surface. Bounded edits per §12.6a; heavy actions remain Focus-required; "Open in Focus" affordance always present in Brief / Detail / Deep. Future workspace-core widgets (case kanban widget, intake queue widget, etc.) follow this exact shape.

3. **Mode-aware rendering pattern** — vault_schedule reads `TenantProductLine.config["operating_mode"]` and dispatches per mode (production / purchase / hybrid). Future per-line widgets where operating mode varies follow this dispatcher pattern. Mode-specific data sources isolated to per-mode builder functions; widget-level dispatcher stays mode-agnostic.

4. **Multi-line builder pattern as canonical** — line_status mirrors `today_widget_service.py`'s per-(vertical, line) builder pattern. Vault metrics real today; other lines surface placeholder rows with `status="unknown"` until their per-line aggregators ship. Pattern keeps the dispatcher clean across line activations without restructuring; future Phase W-3+ work plugs in per-line builders alongside.

5. **SalesOrder vs Delivery + ancillary-independence canon** — load-bearing for the entire scheduling stack. Investigation was triggered by user's good architectural question; resulting canon prevents drift in future sessions. Captured in BRIDGEABLE_MASTER §5.2.5 + DESIGN_LANGUAGE §12.10 entry 12 (vault_schedule).

6. **Investigation-before-code discipline (validated)** — three parallel investigation agents converged on the same architectural answer before any W-3d code shipped. The investigation surfaced (a) D1 data layer approach, (b) D2 demo data scope, (c) D3 hybrid mode scope, (d) D4 purchase mode depth. Then the user's follow-up clarification (ancillaries are independent SalesOrders) sharpened the canon further. The pattern: "no code without architectural clarity" pays off when the foundational question deserves resolution.

**Final regression posture:**
- Backend: **206 widget tests passing** across W-1 + W-2 + W-3a + W-3b + W-3d (W-3a 19 + W-3b 13 + W-3d 20 + W-3a per-widget 60 + W-3b per-widget 9 + W-3d per-widget 38 + W-1/W-2 47). 0 regressions.
- Frontend: **731 vitest tests passing** (up from 677 pre-W-3d: +24 VaultScheduleWidget + 16 LineStatusWidget + 14 UrnCatalogStatusWidget).
- tsc: 0 errors. vite build clean (4.64s).
- Migration head: `r60_backfill_tenant_product_lines_vault` (unchanged — W-3d ships zero schema changes; widget definition seeds + service-layer logic only).

**Patterns unblocked for next clusters:**
- W-3c (FH `arrangement_pipeline`) — first vertical-scoped W-3 widget for funeral_home; same workspace-core canonical reference pattern (vault_schedule provides the architectural template); ancillary-independence canon is FH-specific too (multiple Deliveries per case → multi-line, multi-product fulfillment for one funeral)
- Phase W-4 (Pulse surface) — full W-3 catalog (4 cross-vertical foundation + 2 cross-surface infrastructure + 3 manufacturing per-line; W-3c pending) ready to compose into role-driven default layouts. Sunnycrest production demo lights up with Pulse showing every widget in its right place.

**Phase W-3 is COMPLETE for manufacturing tenants.** vault_schedule + line_status + urn_catalog_status alongside the 4 W-3a foundation widgets and 2 W-3b infrastructure widgets gives Sunnycrest a fully populated widget catalog (9 widgets visible to mfg+vault+urn_sales tenants). FH-specific work (W-3c arrangement_pipeline) sequences after as a separate FH-focused session.

---

### Widget Library Phase W-2 — Spaces sidebar widget pin integration (✅ Shipped, 2026-04-27)

First Phase W-2 implementation session. Spaces sidebar absorbs widget pins per Decision 2 of the Specification session. Widget pins join `saved_view` / `nav_item` / `triage_queue` as a first-class pin type. `pin_type: "widget"` carries `target_id` (widget_id) + optional `variant_id` (defaults to `"glance"` per §12.2 sidebar compatibility) + optional `config` (per-instance widget config). 5 commits shipped end-to-end.

**Backend (4 files):**
- `backend/app/services/spaces/types.py` — extended `PinType` Literal with `"widget"`; added `variant_id` + `config` fields to `PinConfig` and `widget_id` + `variant_id` + `config` to `ResolvedPin`. Round-trip `to_dict`/`from_dict` preserves new fields.
- `backend/app/services/spaces/crud.py` — `add_pin()` validates widget pins with **defense-in-depth at three layers**: pin time (catalog existence + `spaces_pin` surface check + 4-axis filter via `get_available_widgets`), resolve time (`_resolve_pin` re-runs filter so role/vertical changes degrade gracefully), render time (frontend `getWidgetRenderer` falls back to MockSavedViewWidget if registration missing). Default `variant_id="glance"` when omitted.
- `backend/app/services/widgets/widget_service.py` — new `get_widgets_for_surface(db, tenant_id, user, surface)` function for the surface-scoped catalog. Sidebar pinning is page-context-independent; this function evaluates the 4-axis filter against the union of each widget's declared page_contexts (visible iff at least one context passes). Memoizes per-context lookups.
- `backend/app/api/routes/widgets.py` — new `GET /widgets/available-for-surface?surface=spaces_pin` endpoint. Same response shape as `/widgets/available` so the WidgetPicker consumes both interchangeably.

**Frontend (5 files):**
- `frontend/src/types/spaces.ts` — extended `PinType` Literal + `ResolvedPin` + `AddPinBody` with W-2 fields.
- `frontend/src/components/dispatch/scheduling-focus/AncillaryPoolPin.tsx` — restructured into clean three-component shape: `AncillaryPoolGlanceTablet` (presentation, accepts `poolCount` + `poolLoading`), `AncillaryPoolGlanceVariant` (data-piping wrapper using `useSchedulingFocusOptional` for graceful degradation outside Focus), `AncillaryPoolDetailVariant` (existing rich list with `useSchedulingFocus` hard contract). Top-level `AncillaryPoolPin(props)` calls no hooks itself — selects between Glance and Detail based on `surface === "spaces_pin"` OR `variant_id === "glance"`. Glance tablet uses same Pattern 1 frosted-glass + composite shadow + bezel-grip surface treatment as Detail (cross-surface visual continuity); differs in CONTENT density: 60px tall single-row, eyebrow + count chip + subtext, role=button + tabIndex=0 keyboard summon affordance per §12.6a.
- `frontend/src/components/focus/canvas/widget-renderers.ts` — extended `WidgetRendererProps.surface` Literal to include `"spaces_pin"` alongside `"focus_canvas"` / `"focus_stack"`.
- `frontend/src/components/spaces/PinnedSection.tsx` — new `WidgetPinRow` component renders widget pins via `getWidgetRenderer(widget_id, variant_id)` with `surface="spaces_pin"`. Click summons matching Focus via `WIDGET_FOCUS_SUMMON` lookup table (`scheduling.ancillary-pool` → `"funeral-scheduling"`). Keyboard summon via Enter/Space. Unavailable widgets render icon-row fallback. Unpin X absolute-positioned over tablet's top-right with hover-to-reveal opacity. Drag-to-reorder shared with non-widget pins. New "+ Pin widget" entry-point button at bottom of pinned list opens WidgetPicker (`destination="sidebar"`); already-pinned widgets filtered out via `currentWidgetIds`.
- `frontend/src/components/widgets/WidgetPicker.tsx` — added optional `destination?: "dashboard" | "sidebar"` prop (defaults `"dashboard"` for back-compat). Sidebar destination filters widgets to those declaring `spaces_pin` in supported_surfaces; header reads "Pin widget to sidebar"; CTA reads "Pin" instead of "Add"; empty-state copy adapted.

**Architectural decisions canonicalized in code:**
1. Defense-in-depth at three layers (pin / resolve / render).
2. Sidebar always renders Glance variant per §12.2 compatibility matrix; backend defaults `variant_id="glance"` when omitted.
3. Click summon — Glance is summon affordance, not passive readout. Section 12.6a Widget Interactivity Discipline: state changes widget-appropriate, decisions belong in Focus.
4. Surface-scoped catalog endpoint is page-context-independent — sidebar pinning is genuinely page-context-independent and the new endpoint reflects that without inventing a "sidebar context" pseudo-page.
5. Affinity write deferred for widget pins — widget summons are Focus opens (not navigates), and the Phase 8e.1 affinity model is conceptually distinct. Adding "widget" to `AffinityTargetType` whitelist requires separate scope-expansion audit per `SPACES_ARCHITECTURE.md §9.4`.
6. `WIDGET_FOCUS_SUMMON` map is inline today; promoted to focus-registry when a second widget declares `spaces_pin` support (natural-touch refactor).
7. `AncillaryPoolPin` three-component refactor (tablet / variant wrapper / dispatcher) cleanly separates render-only presentation from data hooks, avoids rules-of-hooks violations across variant branches.
8. `VariantId` type from W-1 (`glance | brief | detail | deep`) accepted on the props interface for registry compatibility; component renders Glance + Detail today, Brief + Deep fall through to Detail per Decision 10.

**Surface-naming corrected.** During Commit 1 the validation initially used `"sidebar_pin"` as the surface name; the canonical name from §12.5 is `"spaces_pin"` (matches the 7-surface enum). Caught + corrected before tests ran.

**Tests shipped (47 new, all passing):**
- 27 backend tests (14 unit + 4 surface catalog + 9 integration). Integration suite covers full lifecycle through real API client + auth: pin/unpin cycle, idempotent re-pin, per-instance config round-trip through JSONB, cross-vertical widget rejected at API surface, unknown widget rejected, surface-scoped catalog returns spaces_pin widgets, response shape matches `/widgets/available`, mixed widget + nav pins coexist regression guard.
- 11 frontend PinnedSection vitest tests covering renders widget via `getWidgetRenderer`, variant_id passed through, default "glance" when null, click summons matching Focus, no affinity write, nav pin click still records affinity (regression guard), unknown summon mapping graceful no-op, unavailable widget renders icon-row fallback, data attributes for Playwright drag tests, mixed widget + nav coexist, MockSavedViewWidget fallback.
- 9 AncillaryPoolPin Glance variant vitest tests covering renders Glance when surface=spaces_pin, renders Glance when variant_id=glance, renders Detail by default, count chip with item count, "Pool clear" subtext when empty, singular "1 item" wording, role=button + tabIndex=0 a11y, eyebrow + bezel-grip continuity with Detail, graceful sidebar mounting outside Focus provider.

**Final regression verification:**
- Backend: 194 passed + 2 skipped across W-1 foundation + W-1 integration + W-2 unit + W-2 integration + spaces unit + spaces API + Phase 8e + 8e.1 + 8e.2.3 + invariants. No regressions.
- Frontend: 558/558 vitest pass.
- tsc 0 errors. vite build clean in 4.87s.

**User flow now works end-to-end:**
1. FH director opens any space (Arrangement / Administrative / Ownership).
2. Clicks "+ Pin widget" at the bottom of the Pinned section.
3. WidgetPicker slide-in opens with the surface-scoped catalog (only widgets declaring `spaces_pin` + visible to the user via 4-axis filter).
4. Clicks "Pin" on AncillaryPoolPin.
5. Widget appears in sidebar as Glance tablet showing pool item count + summon affordance.
6. Clicks the tablet → funeral-scheduling Focus opens with the same widget rendered as Detail variant (full pool list with drag-source affordance).
7. Hover the sidebar tablet → unpin X reveals → click X removes the pin.

**Phase W-3 prep.** Phase W-3 (cold-start widget catalog) ready to begin. W-3a in progress (cross-vertical widgets); W-3d pending and includes the per-line `vault_schedule` widget — see Product Line + Operating Mode canon entry below for the architectural canon W-3d builds against.

---

### Product Line + Operating Mode canon (✅ Documented, 2026-04-27)

**NO CODE — pure canonical documentation session.** Surfaced an architectural error in pre-canon platform documentation: operating mode (production / purchase / hybrid) was implicitly framed as tenant-level (concretely: `Company.vault_fulfillment_mode`). It must be **per-product-line** because a single Wilbert licensee may simultaneously run vault in production mode + Redi-Rock in production mode + urn sales in purchase mode + wastewater not activated. Tenant-level mode is wrong abstraction.

**Investigation findings (load-bearing for the rest of the session):**

1. **`TenantProductLine` model already exists** (`backend/app/models/tenant_product_line.py:12-29`) with `(company_id, line_key)` unique key + `is_enabled` + `config` JSONB + `sort_order`. Schema is ready; service layer is not yet built. **Not adding a new primitive — activating one that's been waiting.**
2. **`Company.vault_fulfillment_mode` already exists** (`company.py:83`) with `'produce' | 'purchase' | 'hybrid'`. **This is the canonicalize-away-from anti-pattern.** Works for Sunnycrest (vault is their only line) but breaks for any multi-line tenant.
3. **Extension model is mature with implicit product-line recognition.** `extension_service.py` has `_PRODUCT_LINE_EXTENSIONS = {"urn_sales", "wastewater", "redi_rock", "rosetta"}` already separating product-line extensions from feature extensions. The codebase has been waiting for this formalization.
4. **Cross-tenant infrastructure is ~80% built.** `LicenseeTransfer` + `InterLicenseePricing` (mature, in production), `PlatformTenantRelationship` (consent registry), `DocumentShare` (Phase D-6), `cross_tenant_vault_service` (FH→Mfr orders), `VaultItem.shared_with_company_ids`. The gap is the purchase-mode UX layer (browse supplier inventory, place B2B order, track POs against incoming deliveries) — primitives exist; UX surfaces don't.
5. **Vault is special-cased everywhere.** `inventory_items.spare_covers/spare_bases`, `production_mold_configs.product_category="burial_vault"`, `personalization_tier='wilbert_standard'`, `vault_fulfillment_mode`, `cross_tenant_vault_service`. Vault is the implicit baseline; other lines are extension-gated. The asymmetry is the bug.
6. **`pour_schedule` doesn't exist anywhere.** Only one mention in an AI prompt narrative. Clean slate for the W-3d widget naming decision — no migration debt.
7. **Product classification is fragmented across 4 fields** (`Product.product_line` scalar, `Product.category_id`, `Product.visibility_requires_extension`, `Product.personalization_tier`). Unifying is post-September data hygiene.

**8 decisions resolved (all confirmed by user, all canonicalized in this session's deliverables):**

| # | Decision | Resolution |
|---|---|---|
| 1 | ProductLine formalization | **Hybrid: `TenantProductLine` as canonical data model + extensions as activation surface + vault auto-seeded as baseline.** Mental model: "Extension = how a line gets installed (or not — vault is built-in). Product line = operational reality once installed." |
| 2 | Vault as baseline or extension | **Baseline.** `TenantProductLine(line_key="vault")` auto-seeds for manufacturing-vertical tenants, not extension-gated. Migration: copy `Company.vault_fulfillment_mode` → `TenantProductLine.config["operating_mode"]`. Deprecate Company column post-September. |
| 3 | Cross-tenant scope for September | **Demo-functional stub.** `TenantProductLine.config["operating_mode"]` is canonical mode field. `vault_schedule` widget reads operating_mode + renders production OR purchase appropriately using existing data (`work_orders` / `production_log` for production; `licensee_transfers` for purchase). Full B2B marketplace UX deferred post-September. |
| 4 | `pour_schedule` → `vault_schedule` rename | **Use `vault_schedule` from W-3d inception.** Mode-agnostic + line-specific. Sets convention for `redi_rock_schedule`, `wastewater_schedule`. |
| 5 | Mutual connection | **Canonize: cross-tenant purchase relationships ARE the Mutual data foundation.** Same `PlatformTenantRelationship` consent registry, same data flows, same VaultItem + cross-tenant share primitives. The network effects building (licensees sharing inventory + orders + relationships) ARE the underwriting foundation. Same infrastructure, two strategic outcomes. |
| 6 | September demo scope | **Hybrid Sunnycrest scenario.** Production-mode for most vault types + purchase from fictional neighbor "Empire State Vault Co." for cremation vaults. Demonstrates platform's adaptive nature. Speaks to both production and purchase licensees in Wilbert audience. 1 dedicated session of demo data work for fictional neighbor + read-mostly preview B2B surface. |
| 7 | 4-axis or 5-axis widget filter | **5-axis.** Add `required_product_line` as 5th axis distinct from `required_extension`. Vault baseline isn't an extension; product-line scoping is operational context distinct from feature unlock. 5 axes: permission + module + extension + vertical + product_line. |
| 8 | `production_status` widget naming | **`line_status`** — mode-agnostic, per-line health, cross-line aggregator. Production tenant sees pour status; purchase tenant sees incoming-supply status; hybrid sees both. Optional cross-line `operations_status` aggregator can land later if explicit need surfaces. |

**Deliverables (5 docs):**

1. **BRIDGEABLE_MASTER.md** — extended §5.2 Product Line Activation Model with new sub-sections:
   - **§5.2.1 Extension vs. Product Line — the canonical distinction.** Captures the mental-model framing verbatim per user direction.
   - **§5.2.2 Per-Line Operating Mode Model.** Three-mode taxonomy (production / purchase / hybrid), `TenantProductLine.config["operating_mode"]` storage, `Company.vault_fulfillment_mode` flagged for deprecation.
   - **§5.2.3 Cross-Tenant Purchase Relationships.** Inventory of existing infrastructure (`PlatformTenantRelationship`, `LicenseeTransfer`, `InterLicenseePricing`, `cross_tenant_vault_service`, `DocumentShare`); identifies the purchase-mode UX layer as the gap; canonicalizes demo-functional stub for September scope.
   - **§5.2.4 The Mutual Connection.** Strategic insight captured prominently: "The network effects building (licensees sharing inventory + orders + relationships through Bridgeable) ARE the Mutual underwriting foundation. Same infrastructure, two strategic outcomes." Cross-references §1.7 GEICO Model + §1.8–1.13 Financial Services + §3.23 Cross-Tenant Feature Landscape.
2. **PLATFORM_ARCHITECTURE.md** — §9.3 renamed "The 4-axis filter" → "The 5-axis filter" with `required_product_line` as the new 5th axis. New §9.8 covers the architectural mechanics: `TenantProductLine` primitive shape, operating mode storage + readers, vault auto-seed flow, three product-line activation pathways (auto-seed / extension / direct admin), cross-tenant purchase relationship infrastructure inventory, Mutual connection at architectural level (downstream of `PlatformTenantRelationship`), implementation scope table (pre-September vs post-September).
3. **DESIGN_LANGUAGE.md** — §12.4 extended to 5 axes with `required_product_line` semantics + the mode-aware-rendering-vs-mode-aware-visibility distinction (operating mode is NOT a 6th axis; it's a render-time branch). §12.5 noted catalog filtering carries through every surface uniformly. §12.6 Pour Schedule reference renamed to Vault Schedule + mode-aware annotation. §12.10 added two new reference implementations: **Vault Schedule Widget** (per-line + mode-aware reference) and **Line Status Widget** (cross-line aggregator + mode-aware reference). New "Per-line widget naming convention" subsection codifies the `<line_key>_*` pattern. Cold-start catalog matrix updated: `pour_schedule` → `vault_schedule`, `production_status` → `line_status`.
4. **PLATFORM_INTERACTION_MODEL.md** — new "Line-aware widget materialization" subsection in the Widgets-as-canonical-tablet-realization section. Two dimensions: catalog visibility (5th-axis filter applied to summon catalog) + mode-aware rendering (same widget, different content per line's operating_mode). Compounding effect captured: as purchase relationships deepen, same widget surfaces progressively richer cross-tenant content. Naming discipline carries through to voice/text invocation.
5. **AESTHETIC_ARC.md** — this entry.

**Strategic framing (load-bearing for future Sonnet sessions):**

> Many architectural primitives have been waiting in the codebase. This canon activates them by canonicalizing the model that connects them — `TenantProductLine`, per-line operating mode, 5-axis filter, cross-tenant purchase as Mutual foundation. The infrastructure is ~80% built; this work makes it coherent.

Future Sonnet sessions reading these docs should understand:
1. **WHY** product lines are distinct from extensions
2. **HOW** vault is baseline without being extension-gated
3. **WHAT** operating mode means and where it lives (per-line, in `TenantProductLine.config`)
4. **HOW** cross-tenant purchase relationships connect to Bridgeable Mutual
5. **WHEN** each piece gets built (September scope vs. post-September)

**Surfaced architectural conflicts logged as deferred work:**

- `Company.vault_fulfillment_mode` deprecation (post-September hygiene)
- Product classification fragmentation (`Product.product_line` + `category_id` + `visibility_requires_extension` consolidation, post-September)
- `_PRODUCT_LINE_EXTENSIONS` set in `extension_service.py` should reference `TenantProductLine` going forward (post-September)
- Cross-tenant browsing UX surfaces (full B2B marketplace post-September)

**Implications for W-3d.** Phase W-3d builds `vault_schedule` + `line_status` widgets against this locked canon:
- Both gate visibility via `required_product_line: ["vault"]` (vault_schedule) and `required_product_line: "*"` (line_status cross-line aggregator).
- Both render mode-aware per `TenantProductLine.config["operating_mode"]`.
- Production-mode render path uses existing `work_orders` / `production_log` / `production_mold_configs` data sources.
- Purchase-mode render path uses existing `licensee_transfers` data source.
- Hybrid-mode render path merges both, ordered by date, annotates each row with mode source.
- Demo data: 1 dedicated session seeds the fictional "Empire State Vault Co." neighbor + active `PlatformTenantRelationship` between Sunnycrest and Empire State + sample purchase orders for cremation vaults.

**Implications for post-September Bridgeable Mutual work.** When Mutual ships, it consumes existing read-paths: `licensee_transfers` (delivery reliability), `cross_tenant_statement_service` (payment behavior), `PlatformTenantRelationship` (counterparty diversity), `TenantProductLine.config["operating_mode"]` (operational mode as risk signal), `intelligence_executions` (operational signal density). **No new platform infrastructure required.** Mutual is downstream of the cross-tenant infrastructure built for purchase relationships. Same substrate, two strategic outcomes.

**Sequencing after this canon session:** Phase W-3a (cross-vertical widgets) continues; W-3b (FH widgets) + W-3c (cross-surface infrastructure) follow; W-3d (manufacturing widgets including `vault_schedule` + `line_status`) builds against this locked canon. Phase W-4 (Pulse surface) ships post-W-3 with role-driven defaults that incorporate per-line awareness.

---

### Session 4.8 — Sharp Corner Sweep + Widget Elevation Amplification (✅ Shipped, 2026-04-27)

Closes the two remaining items after Session 4.7 visual verification: DateBox corners not architectural-sharp + AncillaryPoolPin reading as elevated card vs floating tablet. Final aesthetic-foundation calibration before declaring lock.

**Critical methodology learning canonicalized:** Across Sessions 4 → 4.5 → 4.6 → 4.7 each ship was DOM-verified but the user repeatedly verified the rendered output didn't match what DOM-computed values claimed. Session 4.8's investigation found the root cause for the most recent recurrence (pin corners reading soft despite `borderRadius: 2px` in DOM): **the frosted-glass surface treatment fundamentally softens visible edges regardless of border-radius value**. Semi-transparent + blurred fill blends the perimeter into substrate, and DOM-computed-style sampling cannot detect this perceptual softening. **Visual verification at zoom is the canonical methodology**; DOM verification supplementary only. Future Aesthetic Arc sessions: take screenshots at production viewport, inspect at zoom, compare side-by-side against reference components — declare ship only when visually correct, not when DOM-correct.

**Two items addressed:**

**Item 1 — Sharp corner sweep:**
- DateBox: `rounded-sm` (Tailwind v4 resolved to 6px) → `rounded-[2px]`. Architectural sharp matching cards.
- DeliveryCard inner body button (focus-ring outline target): `rounded-md` → `rounded-[2px]` for consistency with outer card 2px.
- SchedulingKanbanCore drag-overlay preview: `rounded-md` → `rounded-[2px]` (preserves card chrome during drag).
- AncillaryPoolPin: `rounded-[2px]` → `rounded-none` (0px). DOM audit confirmed 2px applied; visual verification revealed the frosted-glass surface treatment (`bg /85` + `backdrop-blur(8px)`) inherently softens any corner. 0px is the irreducible minimum sharpness within Pattern 1's canonical frosted-glass treatment. Pattern 1 vs Pattern 2 corner-spec distinction now explicitly documented in DL §11.

**Pattern 2 explicit surface list locked (DL §11 Pattern 2):**
- Surfaces inheriting 2px architectural corner: DeliveryCard, AncillaryCard (when refactored), DateBox, future operational cards (Pulse / peek / command-bar / briefing breakdown), DeliveryCard inner button, drag overlay preview
- Pattern 1 frosted-glass tablets: 0px (different surface treatment requires different corner value to produce equivalent perceptual sharpness)
- Touchable controls (buttons, inputs, popovers, dialogs): retain their primitive-defined corners (typically `rounded-md`) per Section 0 chef's-knife analogy

**Item 2 — Widget elevation amplification:**
- Pre-Session-4.8: `--widget-ambient-shadow` was single-shadow (`0 12px 28px -6px black-25%` light / `0 12px 32px -6px black-55%` dark). Read as "elevated card."
- Session 4.8: layered atmospheric shadow (3 layers per mode) — inner tight halo + mid-distance lift + atmospheric haze:
  - Light: `0 4px 12px -2px black-10%, 0 16px 32px -4px black-25%, 0 32px 56px -8px black-30%`
  - Dark: `0 4px 12px -2px black-30%, 0 16px 32px -4px black-55%, 0 32px 56px -8px black-65%`
- New `--widget-tablet-transform: translateY(-2px)` token applied via inline style on AncillaryPoolPin outer element. Static physical lift offset combined with layered shadow creates "summoned object hovering" register (PLATFORM_INTERACTION_MODEL canonical).
- AncillaryPoolPin doesn't itself drag (only PoolItem rows drag via dnd-kit) — no transform conflict with drag mechanics.

**Visual verification (post-Session-4.8, both modes, canvas-tier 1400x900):**
- DARK: Pin corners read sharp (post-rounded-none); pin atmospheric shadow halo extends visibly into charcoal substrate; pin clearly hovers vs cards. DateBoxes architectural. Cards architectural. All three surfaces share architectural-corner family identity.
- LIGHT: Pin corners sharp; atmospheric shadow halo extends visibly into cream substrate (lighter alpha, but present); pin floats above cards. DateBoxes + cards architectural family.
- Methodology: visual-first inspection at zoom; DOM verification supplementary only.

**Calibration arc complete (Sessions 4 → 4.5 → 4.6 → 4.7 → 4.8):**
- S4: shadow-level-1 only
- S4.5: 4 single-value material tokens
- S4.6: mode-aware material tokens
- S4.7: 3px flag + 2px corners + jewel-set bg-surface-base + widget-tier elevation
- **S4.8: rounded-none on Pattern 1 frosted-glass + layered widget shadow + translateY transform + Pattern 2 surface list lock + visual-verification methodology canonicalization**

**Aesthetic foundation declared LOCKED.** Reference components (DeliveryCard + AncillaryPoolPin + DateBox) calibrated as Pattern 1/2/3 anchors. Subsequent work resumes:
- Widget Library Investigation (next strategic milestone)
- Phase 4.4.4 (slide animation + multi-day functional work)
- Aesthetic Arc Sessions 5-9 component-by-component refinement against the locked references

---

### Session 4.7 — Final Reference Component Locking (✅ Shipped, 2026-04-27)

Closes the three remaining gaps surfaced in user verification of Sessions 4 + 4.5 + 4.6 material work, plus introduces the architectural widget-elevation tier.

**Three gaps closed:**

1. **Left-edge flag width 2px → 3px** (Pattern 3). Visual verification confirmed 2px on production-density cards (178-280px wide) was perceptually invisible. 3px reads as a clear architectural-edge accent. DL §11 Pattern 3 spec updated; calibration history documented.

2. **Jewel-set indicator visibly recessed** (Pattern 3). Pre-Session-4.7 the HoleDugBadge used `bg-status-*-muted` backgrounds (only ~0.04 OKLCH lightness delta from card surface) — the badge looked like a colored chip, not a jeweled inlay. Session 4.7 swaps badge fill to `bg-surface-base` (~0.12 delta below card surface) AND strengthens `--shadow-jewel-inset` (0.15→0.25 light, 0.30→0.50 dark). Together: visible recessed well with icon-as-inlay. Icon color maps to status semantic (`text-accent` for needs-attention, `text-accent-confirmed` for confirmed, `text-content-muted` for explicit no).

3. **Card corner radius `rounded-md` (8px) → `rounded-[2px]`** (Pattern 2 + Pattern 1). Per Section 0 "sharp at architectural scale, soft at touchable" — operational cards + tablet widgets are architectural elements (not touchable affordances). Pre-Session-4.7 8px corners read pillowy; 2px reads architectural. Cross-surface consistency: DeliveryCard + AncillaryPoolPin both use `rounded-[2px]` post-4.7.

**Architectural addition: widget elevation tier.**

Per PLATFORM_INTERACTION_MODEL, widgets are summoned manipulable tablets ON TOP of operations — not equivalent to the work surface. Visual verification confirmed AncillaryPoolPin (Pattern 1 widget) and DeliveryCard (Pattern 2 card-within-core) appeared at similar elevation levels — but they shouldn't. Session 4.7 introduces:

- New `--widget-ambient-shadow` mode-aware token (light `0 12px 28px -6px rgba(0,0,0,0.25)`, dark `0 12px 32px -6px rgba(0,0,0,0.55)`) — wider blur + larger y-offset + stronger alpha than `--card-ambient-shadow`
- New `--shadow-widget-tablet` composite token (`var(--shadow-level-1), var(--widget-ambient-shadow)`) for clean Tailwind arbitrary-value usage by Pattern 1 tablets
- AncillaryPoolPin migrates from `shadow-level-1` (card-tier) to `shadow-[var(--shadow-widget-tablet)]` (widget-tier)
- Documented hierarchy: Substrate → Core element → Cards within core → Widgets (each tier visibly higher than the one below)
- DL §3 + §11 Pattern 1 fully document the elevation hierarchy + token block

Future floating widgets (drive-time matrix pins, staff availability pins, future Pulse cards) inherit `--shadow-widget-tablet` via Pattern 1 tablet treatment.

**Reference component lock:** DeliveryCard + AncillaryPoolPin become the canonical Pattern 1/2/3 reference implementations with calibration history documented in DL §11 reference-implementation notes. Future Session 5+ component refinement compares against these references rather than re-deriving from Section 0.

**Visual verification (DOM-confirmed both modes):**
- Card flag: 3px solid terracotta (`oklch(0.46 0.1 39)` for unknown), visibly tagged-edge accent
- Card corners: 2px architectural radii
- Card jewel-set badge: bg-surface-base fill (substantially darker than card), `--shadow-jewel-inset` inset (0.25 light / 0.50 dark), terracotta `?` icon as inlay — visibly recessed well
- Pin: rounded-[2px] + composite `shadow-level-1 + widget-ambient` — visibly more atmospheric halo than cards (wider 32px blur dark / 28px light, deeper 0.55 alpha dark / 0.25 light, larger 12px y-offset)

**Tests + regression:** tsc 0 errors, vitest 527/527 passing, 148/148 dispatch passing, 84/84 dispatch backend (test_dispatch_schedule + test_focus_session). DeliveryCard.test.tsx existing assertions pass without modification (Session 4.7 changes are in inline-style + className; wrapper data attributes preserved).

**Calibration arc complete (Sessions 4 → 4.5 → 4.6 → 4.7):**
- Session 4: shadow-level-1 only (flat panel)
- Session 4.5: 4 single-value material tokens (still flat in light mode + 2px flag invisible)
- Session 4.6: mode-aware material tokens (cards lift correctly in both modes)
- Session 4.7: 3px flag + 2px corners + visible jewel-set + widget-tier elevation (reference components locked)

**After Session 4.7:** declare aesthetic foundation locked. Next strategic milestone = Widget Library Investigation. Session 5+ component refinement (AncillaryCard internals, Driver column header, Funeral Schedule widget, etc.) compares against the Session 4.7 reference components.

---

### Session 4 — Material Treatment Patterns + Type System Migration + Dual Reference Components (current)

**Date:** 2026-04-26  
**Scope:** Foundational session establishing platform-wide design vocabulary at the surface-treatment layer + replacing the IBM Plex typeface family with Fraunces (display) + Geist (body) + Geist Mono (data) + delivering two canonical reference components (DeliveryCard + AncillaryPoolPin) that realize the new patterns.

**Three foundational artifacts:**

1. **DESIGN_LANGUAGE.md Section 11 — Material Treatment Patterns (NEW)**. Eight canonical patterns:
   - Pattern 1 — Tablet treatment (floating widgets) — drawn edges, ambient shadow, surface lift, bezel + grip indicator (left side, always visible), mono label header, terracotta count chip
   - Pattern 2 — Card material treatment — Fraunces engraving on proper nouns, mono numerals, mid-dot hierarchy, jewel-set status indicators, left-edge flags, document badges
   - Pattern 3 — Status indicator system (two-channel) — left-edge flag (color signal) + jewel-set indicator (recessed ring with inset shadow)
   - Pattern 4 — Numeric mono treatment — all numerals in Geist Mono, eyebrow uppercase tracking included
   - Pattern 5 — Mid-dot separators with hierarchy — primary value strong, secondary muted, tertiary faint
   - Pattern 6 — Day switcher with anchor hierarchy — eyebrow + center Fraunces day + flanking peek/slide DateBoxes
   - Pattern 7 — Column header treatment — name + hairline divider + mono count + accent italic for "different" columns
   - Pattern 8 — Schedule status with jewel-style indicators — status mark + recessed ring + interactive-consequence dotted underline

   Each pattern documented with composition, when-to-apply, when-NOT-to-apply, reference implementation. Pattern library cross-referenced from Section 0 + Section 3 + INTERACTION_MODEL Pattern 1 reference.

2. **Section 4 typeface migration**. IBM Plex → Fraunces / Geist / Geist Mono. Atomic swap with one-release legacy alias retention (`--font-plex-sans` → `var(--font-geist)` etc.) for migration-window safety. Section 4 narrative updated: prior single-family Plex coherence retired in favor of role-specific voice (Fraunces engraving + Geist restrained + Geist Mono precision). Size-weight pairings table revised. "When to use each face" rules revised. Existing weight discipline (3 weights only — Regular/Medium/Semibold) preserved across all three families.

3. **PLATFORM_INTERACTION_MODEL.md tablet pattern formalized**. The "Materialization unit — floating tablets" section gains a callout block referencing Section 11 Pattern 1 as the canonical visual treatment. Reference implementation: AncillaryPoolPin post-Session-4.

**Type system migration shape:**
- `@fontsource-variable/fraunces` + `@fontsource-variable/geist` + `@fontsource-variable/geist-mono` packages installed
- `tokens.css` adds `--font-fraunces` / `--font-geist` / `--font-geist-mono` family tokens + role aliases (`--font-display`, default `--font-sans` → Geist, default `--font-mono` → Geist Mono)
- `index.css` `@theme inline` block exposes `font-display` / `font-sans` / `font-mono` Tailwind utilities + retains `font-plex-*` aliases pointing at new families during migration window
- Codebase sweep: 118 `font-plex-*` utility usages across 67 files migrated per locked semantic mapping (proper nouns + display → font-display Fraunces; body/labels/controls → font-sans Geist; numerals + eyebrows → font-mono Geist Mono)

**Reference components shipped:**

- **DeliveryCard** — Patterns 2 + 3 + 4 + 5 applied. Funeral home name in Fraunces (engraving register), times in Geist Mono with tabular alignment, mid-dot hierarchy on cemetery/city + vault/equipment, jewel-set hole-dug indicator with inset-shadow recessed ring, left-edge flag wired to hole-dug semantic (unknown=terracotta-attention, yes=success-green, no=neutral). The canonical card reference for the platform.

- **AncillaryPoolPin** — Pattern 1 applied fully. Drawn edges via WidgetChrome's existing border, ambient shadow (Tier-4 multi-layer), surface lift (`bg-surface-elevated/85` + `backdrop-blur-sm`), bezel + grip indicator on left edge (always visible structural element), mono label header (`ANCILLARY POOL` text-micro uppercase tracking-wider Geist Mono), brass count chip with Geist Mono numeral. The canonical floating-tablet reference.

**Phased rollout for subsequent Aesthetic Arc sessions:**
- Session 5: AncillaryCard internals (Pattern 2 inheritance) + Driver column header refinement (Pattern 7 full application)
- Session 6: Funeral Schedule Monitor widget — Pattern 1 (tablet) + Pattern 2 (card) + Pattern 3 (status) integration  
- Session 7: Command bar entity cards — Pattern 1 + Pattern 2
- Session 8: QuickEdit + dialog patterns — material treatment for input affordances
- Session 9: Pulse dashboards (when built) — apply patterns from inception

Each subsequent session is bounded; Session 4 establishes the canonical reference; everything else compounds against it.

**Cross-arc context:** This dispatch-focus Session 4 lands during platform-wide Phase II Batch 1b queue. The pattern library + type migration are platform-wide; the reference components are dispatch-scoped. Phase II batches continue independently against the same Section 0 + new Section 11 vocabulary.

---

## Cross-arc integration with Workflow Arc

Aesthetic Arc and Workflow Arc run in parallel. The integration rule: **every Workflow Arc session ships with design-language-consistent styling** — using DESIGN_LANGUAGE tokens where components are refactored or created fresh, and carrying forward shadcn-token styling where components are simply extended.

Concretely:

- **Workflow Arc Phase 8d (vertical workflow migrations)** may coincide with Aesthetic Session 2 (core component refresh). If a vertical workflow ships a new component, it uses DESIGN_LANGUAGE tokens from the start. If it modifies an existing component, shadcn-token-style continues until Aesthetic Session 2–3 refactors that component class.
- **Workflow Arc Phase 8e (spaces + default views)** will encounter the Phase 3 Spaces accent question. That gets resolved alongside 8e design work, not before.
- **Workflow Arc Phase 8g (dashboard rework, saved-view-backed grid)** benefits from Aesthetic Session 5's motion pass — dashboard widgets reflow with `duration-considered` / `ease-settle`.
- **Workflow Arc Phase 8h (arc finale)** closes out before Aesthetic Session 6; final WCAG audit covers everything.

There is no circular dependency: the arcs compose. Either arc can ship any phase or session without waiting on the other, except for the Phase 3 Spaces / brass accent question — which is neither arc's scope individually.

---

## Phase W-4b Canon Expansion Session (canon locked, 2026-05-04)

**Canon-only session. No code shipped.** User-directed expansion of Phase W-4b architecture + canonical-quality discipline lock. Closes the W-4b scope question opened during the Step 6 viewport-responsive canon session (which resolved the Pulse rendering substrate; this session resolves what content composes onto that substrate).

### What was canonicalized

Four architectural shifts locked:

1. **Communications layer replaces Personal layer.** "Personal" implied agency; the question users actually open Pulse to answer is the interpersonal one ("who needs me?"). Tasks + approvals migrate to Operational where they belong cognitively. Communications takes the layer-zero slot, aggregating signals across email + SMS + phone (Call Intelligence) + in-platform messaging + cross-tenant communications.
2. **Pattern C composition pattern (stream + supporting widgets).** New layer-composition pattern distinct from material chrome Patterns 1-8. Composes one primary intelligence stream piece (full-width narrative) + N per-primitive Glance widgets (compact state-scan row beneath stream). Stream is the primary cognitive surface; widgets are confirmation/drill-down. Canonical at the Communications layer.
3. **Per-primitive 4-aspect decomposition canonical for each communication primitive.** Email, SMS, phone, in-platform messaging — each gets canonical (a) signals contributed to layer, (b) Glance widget shape with default/compact/ultra-compact density tiers, (c) briefing surfacing rules for morning + evening, (d) Triage Focus shape when user opens primitive's full triage flow.
4. **Triage Focus migration pattern.** Phase 5 Triage primitive (anomalies, approvals, tasks queues) migrates to render INSIDE Phase A Focus primitive — anchored modal core + canvas peripheral panels. Same Triage queue logic preserved; rendering shell changes from dedicated route to summoned Focus session. Matches PLATFORM_INTERACTION_MODEL.md Tony Stark / Jarvis interaction language.

### Strategic discipline locked: canonical quality over demo timeline

**Build at canonical quality. Demo timelines do not drive architecture.** Phase W-4b ships when complete (per the 16-step sequence). The September 2026 Wilbert demo shows whatever is complete at that point — honest checkpoint, not deadline.

This is the Aesthetic Arc's discipline applied to Workflow Arc scope: same principle that produced Sessions 4-4.8's measurement-driven calibration applies to feature sequencing. Cuts compound as technical debt; canonical quality compounds across years.

**What this discipline rules out:**
- "MVP" cuts to features (e.g., shipping email primitive without inbound handling to make September). The cut compounds as debt; the demo shows incomplete-feeling email.
- "Demo-essential subset" sequencing that re-orders the 16 steps to front-load demoable surfaces while back-burning structurally prerequisite work. The reordering creates dependency violations that surface as bugs.
- "Polish at the end" assumptions. Polish is integral; primitives ship at canonical quality the first time.

**What this discipline enables:**
- Each step shipped is permanent foundation. Post-September Phase W-4b continues at sustainable pace; nothing built before September gets rebuilt.
- The demo narrative is honest: "here's what we've built; here's the platform vision; here's what continues to ship through Q4 and beyond." Wilbert sees real depth + real roadmap, not vaporware.
- Engineering velocity stays sustainable. No demo-deadline crunch costs morale or burns runway.

### Phase W-4b implementation sequence (canonical)

16 steps, sequencing by architectural dependency, total estimate 27-43 weeks. Full table at BRIDGEABLE_MASTER §3.26.6.4. Summary:

1. Layer 1 email primitive (~5-6 weeks)
2. Layer 1 calendar primitive (~3-4 weeks, parallel with email)
3. Layer 1 SMS primitive (~1-2 weeks, after email infra)
4. Layer 1 phone / Call Intelligence primitive (~3-4 weeks, parallel-able)
5. Layer 1 in-platform messaging primitive (~2-3 weeks)
6. Communications layer service + Pattern C composition (~2-3 weeks)
7. Per-primitive intelligence streams (~2-3 weeks)
8. Communications cross-primitive intelligence stream (~1-2 weeks)
9. Morning briefing pipeline + 3-state machine (~2-3 weeks)
10. Evening briefing pipeline (~1-2 weeks)
11. Tenant briefing config UI (~1-2 weeks)
12. Anomalies → Triage Focus migration (~1-2 weeks)
13. Approvals → Triage Focus migration (~1-2 weeks)
14. Tasks → Triage Focus migration (~1-2 weeks)
15. Cross-tenant communications surface (~2-3 weeks)
16. Tests + visual verification + canon doc updates (parallel throughout)

### Canon doc updates locked this session

**BRIDGEABLE_MASTER.md:**
- §3.26.2.3 + §3.26.2.4 amended (Communications replaces Personal; canonical layer order; layer-vs-question framing)
- §3.26.6.4 expanded (Phase W-4b full 16-step sequence, no MVP cuts)
- §3.26.7.5 NEW (canonical-quality discipline lock — three forces in tension framing; rules out + enables analysis)
- §3.26.9 NEW (Communications Layer Architecture — full canon, 11 D-decisions resolved)
- §3.26.10 NEW (Briefings Architecture — three-state machine + generation pipeline + tenant config)
- §3.26.11 NEW (Triage Focus Canonical Pattern — 4 D-decisions resolved)

**DESIGN_LANGUAGE.md:**
- §11 extended (Layer Composition Patterns A/B/C subsection — distinct from material chrome Patterns 1-8)
- §13.4.1 extended (Pattern C density-tier opt-in canonical reference + per-tier behavior table)
- §14 NEW (Communications Layer Visual Canon — per-primitive icon canon Mail/MessageSquare/Phone/AtSign + count typography + per-primitive default/compact/ultra-compact compositions)
- §15 NEW (Briefing Visual System — three states visual mapping + per-state composition + typography per state + Pattern C integration + briefing page editorial-scale + tenant config UI canon)
- §16 NEW (Triage Focus Visual System — anchored core composition + canvas peripheral panels + per-queue specialization + action palette typography + push-back + return pill + queue-exhausted empty state)

**CLAUDE.md §14**: Phase W-4b canon expansion entry summarizing the 4 architectural shifts + discipline lock + 16-step sequence + canon doc updates.

### What changes for the Aesthetic Arc going forward

**Aesthetic Arc Session 5+ scope unchanged.** Motion pass + final QA proceed independently of Workflow Arc Phase W-4b. Both arcs run in parallel per existing cross-arc integration rule (line 1217+).

**Cross-arc check at Session 5/6 boundary:** verify the Pattern C composition + Communications layer visual canon don't introduce motion patterns Aesthetic Arc Session 5 needs to absorb. Expected: Pattern C inherits §13.3.4 transition discipline (350ms cubic-bezier on grid-template-* changes); briefing 3-state machine inherits §6 motion canon (skeleton pulse → shimmer → fade-in over 350ms cubic-bezier). No new motion vocabulary needed.

### Cross-arc check: Workflow Arc + Aesthetic Arc Phase II Batch sequencing

Phase II Batch 1c-i (Order Station) + 1c-ii (long-tail pages) continue as-planned. Phase W-4b email primitive build (step 1) ships fresh code at DESIGN_LANGUAGE-token canonical quality from inception — no shadcn-aesthetic carryover that would need post-W-4b refactor. Phase II Batch 6 (deferred long-tail) absorbs any pages that ship behind aesthetic-token migration during the long W-4b runway.

### Discipline lock summary

> **"Build at canonical quality. Demo timelines don't drive architecture. Platform completeness compounds across years; cuts compound as technical debt. Phase W-4b ships when complete; September Wilbert demo shows whatever's complete at that point. Honest checkpoint over over-promised demo."**

This discipline becomes the cross-arc anchor for any future scope decision during W-4b (and beyond). When future sessions face timeline-vs-scope tension, the canonical-quality framing wins.

---

## Changelog

- **2026-05-04 (Phase W-4b Canon Expansion Session — canon locked, no code):** Communications layer replaces Personal layer; Pattern C composition pattern; per-primitive 4-aspect decomposition for email/SMS/phone/messaging; Triage Focus migration pattern. Canonical-quality discipline locked. 16-step Phase W-4b implementation sequence (27-43 weeks, dependency-driven not timeline-driven). 18 architectural D-decisions resolved. Canon docs updated: BRIDGEABLE_MASTER §3.26.2.3 + §3.26.2.4 + §3.26.6.4 + §3.26.7.5 + §3.26.9 + §3.26.10 + §3.26.11; DESIGN_LANGUAGE §11 + §13.4.1 + §14 + §15 + §16. CLAUDE.md §14 entry. September Wilbert demo framed as honest checkpoint, not deadline. Implementation begins with Layer 1 email primitive in scoped session(s).
- **2026-04-21 (Session 1 shipped):** Token foundation + Plex fonts + Tailwind v4 `@theme inline` extensions + `[data-mode="dark"]` mechanism + flash-prevention inline script + `theme-mode.ts` runtime API. No visual regression (status-color hex→oklch drift accepted).
- **2026-04-21 (Session 2 shipped):** Core component refresh across 14 files (~480 LOC modified). 8 UI primitives (Button, Label, Input, Textarea, Select, Card, Dialog, DropdownMenu, SlideOver) + 6 navigation components (sidebar, DotNav, breadcrumbs, mobile tab bar, app-layout header, notification dropdown) on DESIGN_LANGUAGE tokens. `--font-sans` flipped from Geist to `var(--font-plex-sans)` in one line — entire platform renders in IBM Plex Sans. Geist `@fontsource-variable/geist` package uninstalled. Brass focus ring replaces gray everywhere. Tests: 165/165 vitest + 171/171 backend regression, tsc clean, build clean. Mixed-aesthetic pages expected during Session 2–3 window (213 pages still reference shadcn tokens; Session 3 closes extended-component gap).
- **2026-04-21 (Session 3 shipped):** Extended components + status treatment across 23 files (~1,200 LOC touched). **6 net-new primitives** (Alert, StatusPill, Tooltip, Popover, FormSection + FormStack + FormFooter, FormSteps) — ~630 new LOC. **11 primitive refreshes** onto DESIGN_LANGUAGE tokens (Badge with 4 new status variants + destructive alias; Table + Tabs + Separator + Avatar + Switch + Radio + Skeleton + EmptyState + InlineError + Sonner) — ~400 LOC. **6 ad-hoc surface refreshes** (accounting-reminder-banner, kb-coaching-banner, agent-alerts-card with new status-key-keyed dict pattern, peek StatusBadge → StatusPill, App ErrorBoundary, WidgetErrorBoundary) — ~180 LOC. `next-themes` removed from package.json (single consumer; confirmed). **0 UI primitives remain in shadcn aesthetic.** ~213 pages still carry shadcn page-chrome (accepted per audit §9); migration recipe documented in CLAUDE.md for natural-refactor adoption. 5 flagged settings pages deferred to Phase 8e per audit §2. Tests: 165/165 vitest + 171/171 backend, tsc clean, build clean 4.94s.
- **2026-04-21 (Session 4 shipped):** Dark mode verification pass. **Surgical token adjustments** (8 values + 1 new `--focus-ring-alpha` composable token) + **3 targeted component fixes** for Sessions 1-3 misses + **1 new tenant-facing feature** (branding-editor preview Light/Dark toggle + WCAG contrast readout). M1 status-muted L 0.28/0.30 → 0.22/0.24 (chroma eased) — clears WCAG AA 4.5:1 for status-text-on-muted-bg in dark mode (was 3.83–4.32:1 FAIL, now 5.0–5.4:1). m2 new `--focus-ring-alpha` token (light 0.40 default, dark 0.48 override) — lifts focus-ring contrast on `--surface-raised` from ~3.00:1 WCAG edge to ~3.5:1. M2 portal fg fallback (6 sites across PortalLayout/PortalLogin/PortalResetPassword) migrated from literal `white` to `var(--content-on-brass)` — mode-aware fallback matches DL §3 "brass button as glowing pill with dark text" in dark mode. M5 NotificationDropdown status icons (4 hardcoded Tailwind primaries) migrated to DESIGN_LANGUAGE warm status palette. m3 PortalLayout logout focus ring migrated from `focus:ring-white/50` hardcoded to brand-color-aware ring. M3 branding editor preview gains Light/Dark toggle (scoped `data-mode` on preview subtree only) + two WCAG contrast readouts (brand→fg with AA pass/fail, brand→page-surface visibility advisory). Proper WCAG sRGB-gamma luminance. Tenant brand color Option A confirmed (identical hex in both modes + preview helper). Mirror discipline canonicalized (tokens.css + DL §3 synchronized in same commit). BT.601 vs WCAG luminance divergence in PortalBrandProvider noted as minor known item; deferred. m1 focus-ring gap-color question deferred to Session 6. m4 OfflineBanner hardcoded amber deferred to natural refactor. **No new tests** — token value changes aren't testable via unit tests. Tests: 165/165 vitest, tsc clean (clean-cache verified), build clean. LOC: ~180. 4/6 Phase I sessions complete. Ready for Session 5: Motion pass.
- **2026-04-21 (Phase II Audit shipped):** Platform-wide page-level aesthetic audit. Arc restructured: Phase I (4 sessions) complete → Phase II (audit + 6 batches) → Phase III (Sessions 5+6 Motion + QA). User-reported rendering bugs (bg-white cards, bg-slate-50/50 unreadable panels, hardcoded red error, emoji, pastel icon cards) verified code-side. 208 tenant + 6 portal + 8 admin routes audited via systematic grep analysis across 305 page files. Platform-wide pattern counts: 414 `bg-white`, 2,886 `text-muted-foreground`, 5,000+ Tailwind color utilities, 109 emoji, 3,596 shadcn-default consumers. Batches structured: Batch 0 hotfix (shadcn aliasing), Batch 1 user-reported broken pages, Batches 2-5 demo-critical + P1/P2 surfaces, Batch 6 deferred long-tail. Migration recipes documented. No code changes this session.
- **2026-04-21 (Nav Bar Completion micro-session shipped):** Between Batch 1a and Batch 1b. Two gaps closed: DotNav comment-code mismatch from Phase 8a (`spaces.length === 0 → return null` survived 14 months because populated-spaces path was only-tested branch), and visible mode toggle (Aesthetic Arc Session 1 infrastructure complete, UI button never shipped). New files: `ModeToggle.tsx`, `ModeToggle.test.tsx`, `theme-mode.test.ts`. Extended `theme-mode.ts` with `useMode()` ergonomic alias returning `{mode, toggle}`. Reused existing `bridgeable-mode` hyphen localStorage key (audit flagged that user prompt's dot-separated key would desync flash-mitigation script). jsdom polyfills added to `test/setup.ts` for `matchMedia` + `localStorage` (vitest v4 internal flag quirk). Comment-code discipline note added to CLAUDE.md. Verification methodology updated: all Phase II batches from now on verified in both light and dark mode. Tests: 165 → 181. tsc clean. vite build clean.
- **2026-04-21 (Phase II Batch 1a shipped):** Infrastructure + user-reported + agents family refresh. 8 files: WidgetWrapper + WidgetPicker + WidgetSkeleton + operations-board-desktop + AgentDashboard + ApprovalReview + manufacturing-dashboard + funeral-home-dashboard. ~450 LOC. WidgetWrapper flip single-handedly migrated Operations Board + Vault Overview widget chrome. AgentDashboard + ApprovalReview migrated from 12 hardcoded `bg-white` cards total to `<Card>` primitives; status pill color maps migrated to `<StatusPill>`; native `<input type="date">` + `<textarea>` migrated to primitives. MFG + FH dashboards migrated widget icon pastel backgrounds + status traffic-light colors to DL status palette; `text-blue-600` links → `text-brass`; onboarding banner stone-palette → brass. Zero runtime Tailwind bypass across all 8 files post-batch (remaining grep hits in migration-documentation comments). Pre-existing `.focus-ring-brass` WCAG 2.4.7 light-mode failure (~1.26:1 on cream) flagged for Session 6 deferred fix. Severity attribution methodology documented in CLAUDE.md (grep-only audits under-estimate impact; infrastructure components have disproportionate severity). tsc clean (force-cache). vitest 165/165 unchanged. vite build clean 5.26s. Ready for user visual verification post-commit.
- **2026-04-21 (Phase II Re-audit shipped):** Post-Batch-0 visual verification by user surfaced 7 additional blocking pages (Operations Board desktop, AgentDashboard, ApprovalReview, order-station, financials-board, team-dashboard, plus WidgetWrapper as infrastructure blast-radius fix). Re-audit expanded Batch 1 scope and split into 1a/1b/1c-i/1c-ii for scope discipline. Severity attribution insight added: grep-only audits under-estimate user-visible impact because they don't weight by UI prominence or compositional failure mode. Future audits should attempt visual verification in parallel with grep.
- **2026-04-21 (Phase II Batch 0 shipped):** Shadcn default aliasing micro-session. One file touched (`frontend/src/index.css`), ~50 lines modified in `:root` + `.dark` blocks. Every shadcn semantic token aliased to DESIGN_LANGUAGE equivalents via `var(...)` references: `--background` → `surface-base`, `--foreground` → `content-base`, `--card` → `surface-elevated`, `--popover` → `surface-raised`, `--primary` → `accent-brass`, `--muted` → `surface-sunken`, `--muted-foreground` → `content-muted`, `--accent` → `accent-brass-subtle`, `--destructive` → `status-error`, `--border` → `border-subtle`, `--input` → `border-base`, all `--sidebar*` → DL sidebar equivalents. Platform-wide effect: 3,596 shadcn-default consumers now render in DL warm palette without touching component code. **User-reported MFG dashboard onboarding banner resolved via aliasing alone** (`bg-primary/10 text-primary border-primary/20` now brass). `text-muted-foreground` usages flip platform-wide (2,886 sites) to warm content-muted. Preserved as-is: `--radius` (shadcn radius scale), `--chart-*`, `--brand-*` (legacy), `--status-*-{light,dark}` hex, `--ring` (WCAG 2.4.7 concern — brass solid fails 3:1 in light mode on cream; `.focus-ring-brass` utility remains the opt-in). **Pre-existing WCAG issue surfaced** (deferred to Session 6): `.focus-ring-brass` 40% alpha composed over cream ≈ 1.26:1 in light mode (fails 3:1). Session 4 verified dark mode only. **Scheduling-board family NOT resolved by aliasing** (those files have 0-2 shadcn-default usages each; issues are entirely hardcoded Tailwind — Batch 1 scope unchanged for them). No new tests. vitest 165/165, tsc clean, vite build clean 5.24s. Ready for Phase II Batch 1 (user-reported broken pages + children).
