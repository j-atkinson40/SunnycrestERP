# Bridgeable Aesthetic Arc

Companion arc to the Workflow Arc. Where Workflow Arc ships functional capability, Aesthetic Arc ships the design language — the felt quality of the platform. Both run in parallel and compose cleanly at the seam.

**Source of truth:** [`DESIGN_LANGUAGE.md`](DESIGN_LANGUAGE.md) at project root. Every value in this arc's implementation derives from that document. When prose in DESIGN_LANGUAGE.md and prose here disagree, DESIGN_LANGUAGE.md wins.

---

## Purpose and scope

Bridgeable's design language is **not** a theme — it's the platform's identity expressed visually. Two moods (Mediterranean garden morning and cocktail lounge evening), one material thread (aged brass across both), and an underlying meta-anchor of deliberate restraint.

The Aesthetic Arc's job is to take DESIGN_LANGUAGE.md from document to shipped surface. Six sessions. Each session is infrastructure, visual, or verification — distinct from the others so scope stays clean and regressions stay localized.

**What the arc does NOT do:**
- Workflow Arc migrations (those have their own arc; 8a–8h).
- Functional capability changes (no new features).
- Feature parity breaks for existing components (component visual refresh is progressive; existing surfaces may look and behave unchanged through Session 3).
- Rewrites of the application layer.

---

## Six-session plan

| Session | Status | Scope |
|---|---|---|
| 1 — Token foundation | ✅ Shipped | CSS variables, Plex fonts, Tailwind v4 `@theme inline` extensions, mode-switching mechanism. Infrastructure only; no visual refresh. |
| 2 — Core component refresh | ✅ Shipped | Buttons, inputs, cards, modals, dropdowns, navigation + `--font-sans` flip to Plex + Geist removal. First observable visual change; entire platform now renders in IBM Plex Sans. |
| 3 — Extended component refresh + status treatment | ✅ Shipped | 6 net-new primitives (Alert, StatusPill, Tooltip, Popover, FormSection, FormSteps) + 11 primitive refreshes (Badge+status, Table, Tabs, Separator, Avatar, Switch, Radio, Skeleton, EmptyState, InlineError, Sonner) + 6 ad-hoc surface refreshes (accounting-reminder-banner, kb-coaching-banner, agent-alerts-card, peek StatusBadge, App ErrorBoundary, WidgetErrorBoundary). `next-themes` removed. 0 primitives remain in shadcn aesthetic. |
| 4 — Dark mode verification | ✅ Shipped | Every refreshed component verified in dark mode + WCAG 2.2 AA verified. Surgical token adjustments (status-muted backgrounds, focus-ring alpha) + 3 component fixes (portal fg fallback, NotificationDropdown status icons, PortalLayout logout focus ring) + 1 new feature (branding editor Light/Dark preview toggle + WCAG readout). |
| 5 — Motion pass | ⬜ Not started | Apply `ease-settle` / `ease-gentle` + named durations consistently. Hover, focus, modal/dropdown entrances, toast arrivals. |
| 6 — Accessibility + QA across all surfaces | ⬜ Not started | Full WCAG 2.2 AA verification. Contrast automation. Keyboard navigation. Reduced-motion spot checks. Screen reader pass on refreshed components. |

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
- **2026-04-21 (Session 4 shipped):** Dark mode verification pass. **Surgical token adjustments** (8 values + 1 new `--focus-ring-alpha` composable token) + **3 targeted component fixes** for Sessions 1-3 misses + **1 new tenant-facing feature** (branding-editor preview Light/Dark toggle + WCAG contrast readout). M1 status-muted L 0.28/0.30 → 0.22/0.24 (chroma eased) — clears WCAG AA 4.5:1 for status-text-on-muted-bg in dark mode (was 3.83–4.32:1 FAIL, now 5.0–5.4:1). m2 new `--focus-ring-alpha` token (light 0.40 default, dark 0.48 override) — lifts focus-ring contrast on `--surface-raised` from ~3.00:1 WCAG edge to ~3.5:1. M2 portal fg fallback (6 sites across PortalLayout/PortalLogin/PortalResetPassword) migrated from literal `white` to `var(--content-on-brass)` — mode-aware fallback matches DL §3 "brass button as glowing pill with dark text" in dark mode. M5 NotificationDropdown status icons (4 hardcoded Tailwind primaries) migrated to DESIGN_LANGUAGE warm status palette. m3 PortalLayout logout focus ring migrated from `focus:ring-white/50` hardcoded to brand-color-aware ring. M3 branding editor preview gains Light/Dark toggle (scoped `data-mode` on preview subtree only) + two WCAG contrast readouts (brand→fg with AA pass/fail, brand→page-surface visibility advisory). Proper WCAG sRGB-gamma luminance. Tenant brand color Option A confirmed (identical hex in both modes + preview helper). Mirror discipline canonicalized (tokens.css + DL §3 synchronized in same commit). BT.601 vs WCAG luminance divergence in PortalBrandProvider noted as minor known item; deferred. m1 focus-ring gap-color question deferred to Session 6. m4 OfflineBanner hardcoded amber deferred to natural refactor. **No new tests** — token value changes aren't testable via unit tests. Tests: 165/165 vitest, tsc clean (clean-cache verified), build clean. LOC: ~180. 4/6 sessions complete. Ready for Session 5: Motion pass.
