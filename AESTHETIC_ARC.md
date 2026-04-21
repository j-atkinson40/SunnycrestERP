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
| 2 — Core component refresh | ⬜ Not started | Buttons, inputs, cards, modals, dropdowns, navigation. First session that creates observable visual change. |
| 3 — Extended component refresh + status treatment | ⬜ Not started | Toasts, alerts, badges, tables, forms. Dedicated pass on status colors + error/warning/success/info UI. |
| 4 — Dark mode verification | ⬜ Not started | Every refreshed component verified in dark mode. Fixes dark-mode-only regressions. |
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
