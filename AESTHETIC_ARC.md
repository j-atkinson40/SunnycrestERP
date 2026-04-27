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

## Changelog

- **2026-04-21 (Session 1 shipped):** Token foundation + Plex fonts + Tailwind v4 `@theme inline` extensions + `[data-mode="dark"]` mechanism + flash-prevention inline script + `theme-mode.ts` runtime API. No visual regression (status-color hex→oklch drift accepted).
- **2026-04-21 (Session 2 shipped):** Core component refresh across 14 files (~480 LOC modified). 8 UI primitives (Button, Label, Input, Textarea, Select, Card, Dialog, DropdownMenu, SlideOver) + 6 navigation components (sidebar, DotNav, breadcrumbs, mobile tab bar, app-layout header, notification dropdown) on DESIGN_LANGUAGE tokens. `--font-sans` flipped from Geist to `var(--font-plex-sans)` in one line — entire platform renders in IBM Plex Sans. Geist `@fontsource-variable/geist` package uninstalled. Brass focus ring replaces gray everywhere. Tests: 165/165 vitest + 171/171 backend regression, tsc clean, build clean. Mixed-aesthetic pages expected during Session 2–3 window (213 pages still reference shadcn tokens; Session 3 closes extended-component gap).
- **2026-04-21 (Session 3 shipped):** Extended components + status treatment across 23 files (~1,200 LOC touched). **6 net-new primitives** (Alert, StatusPill, Tooltip, Popover, FormSection + FormStack + FormFooter, FormSteps) — ~630 new LOC. **11 primitive refreshes** onto DESIGN_LANGUAGE tokens (Badge with 4 new status variants + destructive alias; Table + Tabs + Separator + Avatar + Switch + Radio + Skeleton + EmptyState + InlineError + Sonner) — ~400 LOC. **6 ad-hoc surface refreshes** (accounting-reminder-banner, kb-coaching-banner, agent-alerts-card with new status-key-keyed dict pattern, peek StatusBadge → StatusPill, App ErrorBoundary, WidgetErrorBoundary) — ~180 LOC. `next-themes` removed from package.json (single consumer; confirmed). **0 UI primitives remain in shadcn aesthetic.** ~213 pages still carry shadcn page-chrome (accepted per audit §9); migration recipe documented in CLAUDE.md for natural-refactor adoption. 5 flagged settings pages deferred to Phase 8e per audit §2. Tests: 165/165 vitest + 171/171 backend, tsc clean, build clean 4.94s.
- **2026-04-21 (Session 4 shipped):** Dark mode verification pass. **Surgical token adjustments** (8 values + 1 new `--focus-ring-alpha` composable token) + **3 targeted component fixes** for Sessions 1-3 misses + **1 new tenant-facing feature** (branding-editor preview Light/Dark toggle + WCAG contrast readout). M1 status-muted L 0.28/0.30 → 0.22/0.24 (chroma eased) — clears WCAG AA 4.5:1 for status-text-on-muted-bg in dark mode (was 3.83–4.32:1 FAIL, now 5.0–5.4:1). m2 new `--focus-ring-alpha` token (light 0.40 default, dark 0.48 override) — lifts focus-ring contrast on `--surface-raised` from ~3.00:1 WCAG edge to ~3.5:1. M2 portal fg fallback (6 sites across PortalLayout/PortalLogin/PortalResetPassword) migrated from literal `white` to `var(--content-on-brass)` — mode-aware fallback matches DL §3 "brass button as glowing pill with dark text" in dark mode. M5 NotificationDropdown status icons (4 hardcoded Tailwind primaries) migrated to DESIGN_LANGUAGE warm status palette. m3 PortalLayout logout focus ring migrated from `focus:ring-white/50` hardcoded to brand-color-aware ring. M3 branding editor preview gains Light/Dark toggle (scoped `data-mode` on preview subtree only) + two WCAG contrast readouts (brand→fg with AA pass/fail, brand→page-surface visibility advisory). Proper WCAG sRGB-gamma luminance. Tenant brand color Option A confirmed (identical hex in both modes + preview helper). Mirror discipline canonicalized (tokens.css + DL §3 synchronized in same commit). BT.601 vs WCAG luminance divergence in PortalBrandProvider noted as minor known item; deferred. m1 focus-ring gap-color question deferred to Session 6. m4 OfflineBanner hardcoded amber deferred to natural refactor. **No new tests** — token value changes aren't testable via unit tests. Tests: 165/165 vitest, tsc clean (clean-cache verified), build clean. LOC: ~180. 4/6 Phase I sessions complete. Ready for Session 5: Motion pass.
- **2026-04-21 (Phase II Audit shipped):** Platform-wide page-level aesthetic audit. Arc restructured: Phase I (4 sessions) complete → Phase II (audit + 6 batches) → Phase III (Sessions 5+6 Motion + QA). User-reported rendering bugs (bg-white cards, bg-slate-50/50 unreadable panels, hardcoded red error, emoji, pastel icon cards) verified code-side. 208 tenant + 6 portal + 8 admin routes audited via systematic grep analysis across 305 page files. Platform-wide pattern counts: 414 `bg-white`, 2,886 `text-muted-foreground`, 5,000+ Tailwind color utilities, 109 emoji, 3,596 shadcn-default consumers. Batches structured: Batch 0 hotfix (shadcn aliasing), Batch 1 user-reported broken pages, Batches 2-5 demo-critical + P1/P2 surfaces, Batch 6 deferred long-tail. Migration recipes documented. No code changes this session.
- **2026-04-21 (Nav Bar Completion micro-session shipped):** Between Batch 1a and Batch 1b. Two gaps closed: DotNav comment-code mismatch from Phase 8a (`spaces.length === 0 → return null` survived 14 months because populated-spaces path was only-tested branch), and visible mode toggle (Aesthetic Arc Session 1 infrastructure complete, UI button never shipped). New files: `ModeToggle.tsx`, `ModeToggle.test.tsx`, `theme-mode.test.ts`. Extended `theme-mode.ts` with `useMode()` ergonomic alias returning `{mode, toggle}`. Reused existing `bridgeable-mode` hyphen localStorage key (audit flagged that user prompt's dot-separated key would desync flash-mitigation script). jsdom polyfills added to `test/setup.ts` for `matchMedia` + `localStorage` (vitest v4 internal flag quirk). Comment-code discipline note added to CLAUDE.md. Verification methodology updated: all Phase II batches from now on verified in both light and dark mode. Tests: 165 → 181. tsc clean. vite build clean.
- **2026-04-21 (Phase II Batch 1a shipped):** Infrastructure + user-reported + agents family refresh. 8 files: WidgetWrapper + WidgetPicker + WidgetSkeleton + operations-board-desktop + AgentDashboard + ApprovalReview + manufacturing-dashboard + funeral-home-dashboard. ~450 LOC. WidgetWrapper flip single-handedly migrated Operations Board + Vault Overview widget chrome. AgentDashboard + ApprovalReview migrated from 12 hardcoded `bg-white` cards total to `<Card>` primitives; status pill color maps migrated to `<StatusPill>`; native `<input type="date">` + `<textarea>` migrated to primitives. MFG + FH dashboards migrated widget icon pastel backgrounds + status traffic-light colors to DL status palette; `text-blue-600` links → `text-brass`; onboarding banner stone-palette → brass. Zero runtime Tailwind bypass across all 8 files post-batch (remaining grep hits in migration-documentation comments). Pre-existing `.focus-ring-brass` WCAG 2.4.7 light-mode failure (~1.26:1 on cream) flagged for Session 6 deferred fix. Severity attribution methodology documented in CLAUDE.md (grep-only audits under-estimate impact; infrastructure components have disproportionate severity). tsc clean (force-cache). vitest 165/165 unchanged. vite build clean 5.26s. Ready for user visual verification post-commit.
- **2026-04-21 (Phase II Re-audit shipped):** Post-Batch-0 visual verification by user surfaced 7 additional blocking pages (Operations Board desktop, AgentDashboard, ApprovalReview, order-station, financials-board, team-dashboard, plus WidgetWrapper as infrastructure blast-radius fix). Re-audit expanded Batch 1 scope and split into 1a/1b/1c-i/1c-ii for scope discipline. Severity attribution insight added: grep-only audits under-estimate user-visible impact because they don't weight by UI prominence or compositional failure mode. Future audits should attempt visual verification in parallel with grep.
- **2026-04-21 (Phase II Batch 0 shipped):** Shadcn default aliasing micro-session. One file touched (`frontend/src/index.css`), ~50 lines modified in `:root` + `.dark` blocks. Every shadcn semantic token aliased to DESIGN_LANGUAGE equivalents via `var(...)` references: `--background` → `surface-base`, `--foreground` → `content-base`, `--card` → `surface-elevated`, `--popover` → `surface-raised`, `--primary` → `accent-brass`, `--muted` → `surface-sunken`, `--muted-foreground` → `content-muted`, `--accent` → `accent-brass-subtle`, `--destructive` → `status-error`, `--border` → `border-subtle`, `--input` → `border-base`, all `--sidebar*` → DL sidebar equivalents. Platform-wide effect: 3,596 shadcn-default consumers now render in DL warm palette without touching component code. **User-reported MFG dashboard onboarding banner resolved via aliasing alone** (`bg-primary/10 text-primary border-primary/20` now brass). `text-muted-foreground` usages flip platform-wide (2,886 sites) to warm content-muted. Preserved as-is: `--radius` (shadcn radius scale), `--chart-*`, `--brand-*` (legacy), `--status-*-{light,dark}` hex, `--ring` (WCAG 2.4.7 concern — brass solid fails 3:1 in light mode on cream; `.focus-ring-brass` utility remains the opt-in). **Pre-existing WCAG issue surfaced** (deferred to Session 6): `.focus-ring-brass` 40% alpha composed over cream ≈ 1.26:1 in light mode (fails 3:1). Session 4 verified dark mode only. **Scheduling-board family NOT resolved by aliasing** (those files have 0-2 shadcn-default usages each; issues are entirely hardcoded Tailwind — Batch 1 scope unchanged for them). No new tests. vitest 165/165, tsc clean, vite build clean 5.24s. Ready for Phase II Batch 1 (user-reported broken pages + children).
