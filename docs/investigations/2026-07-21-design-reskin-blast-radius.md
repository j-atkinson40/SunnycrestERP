# Chrome/Steel Reskin — Blast Radius Findings
2026-07-21 · read-only investigation · repo @ `cd905270`

**Verdict up front: two-tier answer.** For everything that is DL-token-mediated (all UI primitives, WidgetChrome, ~229 Card importers, the Studio/visual-editor chrome, everything refreshed in Aesthetic Sessions 2–4.8), this IS a clean token-layer swap — the token architecture is genuinely load-bearing and the swap lands in ~8 files plus their drift-gate tests. But full conformance to the new language's laws (functional-color-only, no-flat-panels, single-typeface) collides with **4,629 legacy Tailwind palette class usages** and **~380 `bg-white` literals** that were *already out-of-register debt in the brass era* and were explicitly deferred to natural-refactor. Recommendation: ship the token swap as parity-with-current-coverage (the platform flips to chrome/steel wherever it is currently in-register), and treat the legacy-palette sweep as the same long-tail debt it already was — not a blocker, but the reskin does not magically fix it and the new "all other color is functional" law makes it more visible. **This does not trip the STOP criterion** for the token-layer work itself; it trips it only if "reskin" is defined as full-conformance-everywhere, which would be a component-by-component sweep of 200+ pages. No reskin was attempted (read-only).

---

## 1. Token layer — where tokens actually live

Nine surfaces, in dependency order:

| # | File | Role |
|---|---|---|
| 1 | `frontend/src/styles/tokens.css` (543 lines) | **Canonical.** All DL tokens: light values at `:root`, dark overrides in a `[data-mode="dark"]` block. ~90 custom properties across surface/content/border/shadow/accent/status/focus-ring/card-material/widget-elevation/typography/radius/motion/max-width/z-index families. |
| 2 | `frontend/src/index.css` | Shadcn→DL aliases (`--background: var(--surface-base)` etc., duplicated in `:root` + legacy `.dark`), plus the Tailwind v4 `@theme inline` block that binds every token to utilities (`--color-surface-base`, `--text-h1`, `--shadow-level-1`, `--container-*`). Also holds stragglers NOT DL-mediated: `--ring` (hardcoded neutral oklch), `--chart-1..5` (blue family), `--brand-*` (legacy teal hex), `--status-*-{light,dark}` legacy hex. |
| 3 | `frontend/src/styles/base.css` | `.focus-ring-accent` utility (composes `--accent` + `--focus-ring-alpha` via `color-mix`), `@utility duration-*` declarations, reduced-motion, dark-mode font smoothing, Focus push-back. |
| 4 | `frontend/src/styles/fonts.css` | `@fontsource` imports: **fraunces + geist + geist-mono AND all three IBM Plex packages still imported** (plex is dead weight — aliased away in Session 4 but never unimported; package.json still carries all 6 font packages). |
| 5 | `frontend/src/lib/visual-editor/themes/token-catalog.ts` (1,037 lines) | Themes-editor catalog: 80 token entries, 17 categories, `{light, dark}` defaults per entry, `derivedFrom` + `editable` flags. A vitest catalog-completeness test parses tokens.css and asserts 1:1 coverage — **any token rename/addition must land here in the same commit or CI fails.** |
| 6 | `frontend/src/lib/visual-editor/themes/base-tokens.ts` | Second mirror: platform-default token map (light+dark) used by the Studio chrome inspector / cascade preview / TokenSwatchPicker. Own drift-gate test (`base-tokens.test.ts`). Contains terracotta literals (`oklch(0.46 0.10 39)`, `rgba(156, 86, 64, …)`). |
| 7 | Backend `platform_themes` (`backend/app/services/platform_themes/theme_service.py`) | Stores *overrides only*, keyed by token-name string. **No token-name whitelist** — `_validate_overrides` checks only that keys are non-empty strings. New token roles need zero backend schema/validation change. |
| 8 | Backend hardcodes | `documents/block_composer.py` (`--doc-accent: #9C5640` in composed-template CSS boilerplate), `documents/block_registry.py` (header-block `accent_color` default `#9C5640` ×2), `email/html_sanitization.py` (IBM Plex font stack + `#9C5640` link color), `documents/_template_seeds.py` — **219 hex-color occurrences** across those 4 files; plus 11 hex occurrences in 3 alembic email-template migrations (r43, r45, z9g4). |
| 9 | `DESIGN_LANGUAGE.md` §3/§9 | Mirror-discipline partner of tokens.css (same-commit sync rule, per CLAUDE.md). The new doc replaces this side; tokens.css must follow. |

### Themes-editor slots today vs. new §3–7 names

**Ride existing slots cleanly (re-value, optionally rename):**

| New token (§3–7) | Existing slot |
|---|---|
| `--substrate-base` | `--surface-base` |
| `--surface-1` (rail/recessed) | `--surface-sunken` |
| `--surface-2` (panel/card) | `--surface-elevated` |
| `--surface-3` (raised/popover) | `--surface-raised` |
| `--text-primary/secondary/muted` | `--content-strong`/`-base`+`-muted`/`-subtle` (4 slots absorb 3 roles) |
| `--accent-chrome` / `-hover` | `--accent` / `--accent-hover` |
| `--on-chrome` | `--content-on-accent` |
| `--fn-positive` | `--status-success` |
| `--fn-negative` | `--status-error` (terracotta hue 40 — new value ≈ old brand thread, amusingly) |
| `--fn-caution` | `--status-warning` |
| `--edge-specular` | closest analogs already exist: `--shadow-highlight-top` (dark-mode 3px inset top-edge highlight — the *mechanism* for a specular edge is already wired into `--shadow-level-1..3` compositions) and `--card-edge-highlight` |
| `--shadow-panel` | `--shadow-level-1/2/3` compositions (currently `editable: false`, derived from `--shadow-color-*`) |
| `--font-sans` (SF Pro/Inter) | `--font-geist` (and the `--font-plex-sans` alias chain) — one value swap cascades platform-wide via `--font-sans: var(--font-geist)` in index.css |

**Missing — no slot exists; new catalog entries + tokens.css additions required:**
- `--signature-steel`, `--signature-steel-ring` — nothing steel-shaped exists. Closest incumbents: `--border-accent` (rgba terracotta), `--focus-ring-alpha` (alpha-only), `--ring` (index.css, neutral gray, not even in the catalog). See Type B call #1.
- `--nav-active-indicator`, `--nav-active-text` — nav chrome today rides `--accent-subtle`/space-accent CSS vars; no dedicated nav tokens.
- `--edge-specular` *as a first-class editable token* (today's analogs are `editable: false` compositions).
- No slot for the §3 **panel vertical gradient** — and structurally there can't be one under current wiring: Tailwind `bg-surface-elevated` emits `background-color`, which cannot hold a `linear-gradient`. See Type B call #3.

**Existing slots the new language orphans (decide fate):** `--status-info` (+muted) — new law has no blue "info"; blue is now the rationed signature (collision risk). `--accent-confirmed` (sage stamp). `--surface-frosted`. `--font-fraunces` / display-serif role (21 `font-display` usages). `--accent-muted`/`--accent-subtle` (10–20% alpha fills of the accent — near-invisible when the accent is near-white chrome; semantics need re-derivation, not re-valuing). Card-material + widget-elevation token families (9 tokens, Session 4.5–4.8) — superseded by the single §3 panel stack but heavily wired into DeliveryCard/AncillaryPoolPin.

## 2. Hardcode audit

Counts are line-occurrences in `frontend/src` unless noted.

| Class of hardcode | Count | Where (top offenders) | Token-mediated? |
|---|---|---|---|
| `brass` identifier, all mentions | 94 lines / ~60 files | mostly comments/history notes | n/a |
| **`--accent-brass` / `bg-brass` / `focus-ring-brass` etc. — real code usages** | **29 across 15 files** | `bridgeable-admin/components/visual-authoring/{TokenSwatchPicker(8), ScrubbableButton(2), ChromePresetPicker(2), SubstratePresetPicker(2), TypographyPresetPicker(2)}`, chrome-resolver(+test), substrate-resolver.test(3), tokens.css/base.css comments(4), `lib/utils.ts`(1), `CalendarAccountsPage`(1), `ChromePrimitivesDemoPage`(1) | **No — and worse: `var(--accent-brass,#9C5640)` fallbacks reference a token retired in Session 2, so these ~15 sites render the hex FALLBACK today. Latent bug; cleanup owed regardless of reskin.** |
| Terracotta literals (`#9C5640`, `rgba(156,86,64,…)`, `#B46A4D`) outside tokens.css/token-catalog | ~45 lines / ~20 files | base-tokens.ts(3), visual-authoring fallbacks (above), `moc/Ponder*` inline styles (7), `documents/blocks/index.tsx` + `document-blocks-config.ts` defaults (2), `ResizeHandleOverlay` fallback, `email/LabelManager` palette entry, ChromePrimitivesDemoPage brass gradient; rest are tests asserting the old value (`themes.test.ts` ×5, Tier1CoresEditor.test ×4, portal/email tests ×7) | No (though many are fallbacks/tests, not primary values) |
| `oklch(… 0.46 0.10 39)` accent literal | 9 | base-tokens.ts(4), themes.test.ts(5) | Mirror + tests |
| Warm-hue oklch literals (hues 39/59/65/70/75/78/80/81/82/85) outside token layer | 18 | **`workflow-canvas/node-families.ts` (16 — per-family node/stripe colors, light+dark, real UI)**, PortalBrandingSettings preview (2), card.tsx comment | No |
| `font-plex-*` Tailwind utility usages | **511** | spread across ~150 files (visual editor, widgets, email, calendar pages) | **Yes** — alias chain `--font-plex-* → var(--font-geist*)`; a value swap at tokens.css re-fonts all 511 without touching them. Class-name *cleanup* is the sweep, not the reskin. |
| Fraunces/Geist named refs | 65 (+21 `font-display` usages) | tokens.css, fonts.css, index.css, catalog, scattered comments | Token-mediated except fonts.css imports + package.json |
| `@fontsource` packages | 6 in package.json (3 Plex — dead, 3 Fraunces/Geist) + 7 import lines in fonts.css | New language wants **no bundled webfont** for SF (system stack) + Inter fallback only → all 6 retire, Inter enters | n/a |
| Backend brand hardcodes | `#9C5640` ×4 + IBM Plex stack ×1 in 3 service files; 219 hex total in documents/email services; 11 hex in 3 email-template migrations; 18 seeded Jinja `body_template`s carry their own inline CSS | No — document/email emission is a separate re-theme (and is light-mode, see §3) |
| **Legacy Tailwind palette classes `(bg|text|border)-(green|red|amber|blue|yellow|emerald|rose|sky|orange)-N`** | **4,629** (amber/orange alone: 1,092) | ~200+ page files | **No — pre-existing deferred debt** (CLAUDE.md: "1,305 ad-hoc status-color usages deferred to natural-refactor"; real count with all families is 4,629) |
| `bg-white` | 379 | pages, long tail | No |
| `bg-card` (shadcn alias) | 35 | legacy pages | Yes (via alias) |

**Reading:** the brass/terracotta-specific hardcode count is *small* (≈75 real code sites + ~20 test assertions + ~25 backend sites) — clean-swap territory. The big numbers (511 plex classes) are token-mediated aliases, and (4,629 palette classes) are pre-existing debt orthogonal to which language the tokens express. The number that decides "token swap vs rewrite" is the ~75, and it says **token swap**.

## 3. Dark/light mechanism

**Full parallel token set, not a transform.** Exactly:

- `tokens.css`: light values at `:root`; dark values in a complete `[data-mode="dark"]` override block (~90 pairs, independently hand-calibrated — dark even has extra tokens like `--shadow-highlight-top` and different shadow compositions).
- Mode switch: `frontend/src/lib/theme-mode.ts` (161 lines) sets `data-mode="dark"` on `<html>`; synchronous inline script in `index.html` prevents flash; `@custom-variant dark` in index.css matches both `.dark` and `[data-mode="dark"]`.
- Shadcn aliases resolve through `var(…)` so both `:root` and `.dark` blocks converge on whatever DL values are active.
- Visual editor: `TokenModeDefaults` **requires** `{light: string, dark: string}` on every catalog entry; the editor's mode toggle switches which row is edited.
- Backend: `platform_themes` — **mode is part of theme identity** (one row per `(scope, vertical?, tenant_id?, mode)`; light and dark are independent records; resolver takes `mode` as input).

**Cost implication for the §11 light-mode decision:** "dark-only" is not structurally free — the light half of the pair is mandatory in the catalog type, the editor UI, and the backend identity tuple. Options: (a) author a real derived light set (~90 values — authoring work, no code change anywhere); (b) dark-only would require type changes in token-catalog + editor + accepting degenerate light rows. Also note the light-mode consumers that can't go dark: Jinja document emission (18 seeded templates + block_composer boilerplate are light-paper documents), portal/tenant-branding surfaces, and email HTML. **(a) is the cheap path; the machinery for two modes already exists and costs nothing to keep.**

## 4. Depth — shared primitive or duplicated?

**Mostly one place, with a quantified long tail:**

- `ui/card.tsx` is the canonical panel: `bg-surface-elevated + shadow-level-1 + rounded-md`, **229 importing files**. No border; edge emerges from the shadow composition.
- `WidgetChrome.tsx` (canvas widgets): same recipe (`border-border-subtle bg-surface-elevated shadow-level-1`, level-2 when active).
- Studio surfaces route through `chrome-resolver.ts` presets (card/modal/dropdown/toast/floating/frosted) — a single pure resolver.
- Crucially, **the specular-edge mechanism already exists**: dark-mode `--shadow-level-1/2/3` compositions include `inset 0 3px 0 var(--shadow-highlight-top)`. The new `--edge-specular` (1px inset white 5%) is a re-value + light-mode enablement of an existing pattern — it lands in tokens.css alone for every shadow-level consumer.
- **The gradient does NOT land in one place**: Tailwind `bg-*` utilities emit `background-color`; a vertical gradient needs `background-image`. So the §3 machined stack (gradient + specular + shadow) can be fully delivered in card.tsx, WidgetChrome, chrome-resolver, Dialog/Popover/DropdownMenu/SlideOver (the overlay family, ~6 primitive files) — but the **278 ad-hoc `bg-surface-elevated` usages outside `components/ui/`** (+90 ad-hoc `shadow-level-1`, +379 `bg-white`) will render flat fills, which §3 explicitly bans for panels. Mitigation: ship a single `.panel-machined` utility (or extend the `@utility` pattern in base.css) and sweep opportunistically; primitives-first gets the dominant surfaces right on day one.

## 5. Type B architectural calls for James

1. **`--signature-steel` needs a new token *role*** — recommended, not riding an existing slot. Rationale: the ration law ("≤3 uses per screen") is a *semantic contract*; hiding steel inside `--border-accent` or `--ring` makes it indistinguishable from accent and unenforceable/unauditable. Concretely: add a new catalog category (e.g. `signature`) with `signature-steel` + `signature-steel-ring`; repoint `.focus-ring-accent` internals (base.css) at it; also fold in the orphan `--ring` from index.css (currently hardcoded neutral, not even catalog-tracked). Backend needs nothing (no token whitelist). Cost: catalog entries + tokens.css + completeness-test fixtures.
2. **Can the Themes editor express a near-monochrome accent? Yes.** `OklchPicker` sliders: L 0–1, C **0–0.4 with min 0, step 0.001**, H 0–360, optional alpha. `oklch(0.93 0.004 255)` is directly settable; no chroma floor, no saturated-hue assumption anywhere in the picker or resolver. Two real caveats: (a) `--accent-muted`/`--accent-subtle`/`--border-accent` are `valueType: "rgba"` hand-derived from the accent — with a near-white accent, 10–20% alpha fills invert their job on a dark substrate (they'd read as faint white washes, maybe fine, maybe not — needs a design pass, and possibly re-typing those slots to oklch-with-alpha); (b) `--on-chrome` = `var(--substrate-base)` is a *token reference as a value* — the catalog has no `derivedFrom`-editable reference type for color slots; simplest is to store the literal and note the coupling.
3. **Where the machined-panel stack lands**: decide between (a) primitives-only (card.tsx + WidgetChrome + overlay family + chrome-resolver — ~8 files, covers the 229-importer surface area, long tail stays flat) vs (b) a `.panel-machined` utility + sweep of the 278 ad-hoc panels. Specular edge rides shadow tokens for free; the gradient is the part that forces this call.
4. **Light mode** (§11 open item): mechanism is a full parallel set with mode baked into editor + backend identity — keeping two modes is free structurally; dark-only actually costs type/editor changes. Recommend dark-first + authored light set (~90 values), with documents/email/portal permanently light.
5. **`--status-info` / blue collision**: new law has no "info" blue, and steel-blue is the rationed signature. Decide: retire status-info (map to neutral chrome) or keep and accept two blues. Also decide `--accent-confirmed` (sage) fate.
6. **Typeface consolidation**: new language is single-family (SF/Inter). Fraunces display role dies → 21 `font-display` usages + `--font-fraunces`/`--font-plex-serif` chain. Cheap path: repoint all font tokens at the new system stack (zero component edits, all 511 plex-class usages follow), retire 6 @fontsource packages, sweep class names later. Weight law (400/500 only) is nearly free — the type scale's paired weights are already 500; `font-semibold`/`font-bold` usages would need a (separate, countable) sweep.
7. **Dead `--accent-brass` fallbacks** (~15 sites in `bridgeable-admin/components/visual-authoring/*` + ResizeHandleOverlay): these render `#9C5640` *today* because the token they reference was retired in April. Fix in the same pass (point at `--accent` or the new signature/chrome tokens).
8. **Scope ruling on the 4,629 legacy palette classes**: the new "all other color is functional" law converts pre-existing deferred debt into first-class violations. Recommend explicitly re-affirming the natural-refactor posture in the build dispatch so the reskin isn't judged against them.
9. **Backend document/email emission** (219 hex sites + 18 seeded Jinja templates + `--doc-accent`/Plex in composer/sanitizer): separate mini-arc; documents are customer-facing paper and likely stay light + get the new accent only.

## LOC floor — token-layer work only

| Work item | LOC touched (floor) |
|---|---|
| tokens.css full re-value (both modes) + new tokens | ~550 |
| token-catalog.ts re-value + new entries + descriptions | ~350 |
| base-tokens.ts mirror | ~120 |
| index.css (aliases audit, --ring, fonts, chart/brand token decisions) | ~60 |
| base.css (focus ring → signature steel; panel utility if chosen) | ~30 |
| fonts.css + package.json (retire 6 packages, add Inter) | ~30 |
| Drift-gate + literal-asserting tests (themes.test, base-tokens.test, catalog-completeness, Tier1CoresEditor.test, substrate-resolver.test, edit-mode-context.test) | ~150 |
| Dead-brass fallback cleanup (29 usages / 15 files) | ~60 |
| node-families.ts hue re-derivation | ~30 |
| Backend defaults (block_composer, block_registry, html_sanitization) | ~20 |
| DESIGN_LANGUAGE.md §3/§9 mirror sync (already done — new doc is source) | — |
| **Floor total** | **≈ 1,400 LOC** |

Excludes: primitive-file gradient/specular work (call #3, ~+200), light-mode authoring (~90 values), legacy-palette sweep (out of scope), document/email re-theme (separate arc).

---

## Warm-hue residue (Phase 2 build, item 8 — read-only triage, nothing fixed)

Scan: `bg-(amber|orange|yellow)-N` = **452 occurrences**; `(text|border)-(amber|orange|yellow)-N` = **825**. These are the subset of the 4,629 legacy palette classes that emit a WARM hue — the ones that read as brass-era splotches on the chrome UI. All are pre-existing deferred debt (out of scope for the token swap); flagged here so the residue is a ruled-on decision, not a silent ship.

**Flagged — warm fills on PRIMARY surfaces (would visibly splotch, especially in dark mode where pastel `bg-amber-50`-style washes glare against charcoal):**

| File | Warm bg fills | Character |
|---|---|---|
| `src/pages/financials-board.tsx` | **18** | Worst offender on a primary board: row-level washes (`bg-amber-50/30` on list rows), zone panels (`bg-amber-50/50`), badge chips (`bg-amber-100 text-amber-700`) |
| `src/pages/console/operations-board.tsx` | 5 | Includes SOLID warm button fills (`bg-amber-600 text-white`, `bg-amber-500 text-white`) — large fills, not chips |
| `src/components/morning-briefing-card.tsx` | 5 | Briefing card on the home surface |
| `src/pages/delivery/funeral-scheduling.tsx` | 5 | Scheduling Focus feeder page |
| `src/components/mobile/ops-context-card.tsx` | 9 | Mobile ops surface |
| `src/pages/delivery/operations.tsx` | 4 | `bg-yellow-100/-500/-50` status chips + dot |
| `src/pages/driver/route.tsx` | 4 | Driver portal surface (September demo narrative) |

Secondary-surface long tail (settings/WorkflowBuilder 7, platform-health 11, order-station 6, urn-catalog 5, safety-dashboard 5, team-dashboard 4, customers 4, ar-aging, vendors, etc.) — full counts reproducible via `grep -rcE "bg-(amber|orange|yellow)-[0-9]+" src --include="*.tsx"`.

**Character of the residue:** overwhelmingly warning/attention semantics (overdue chips, pending badges, caution rows) — semantically these map to `--status-warning` (`--fn-caution`, hue 78) or `--status-error` (`--fn-negative`, hue 40), so the *meaning* survives conversion; the standard migration recipe (CLAUDE.md status-color table) applies mechanically.

**Recommendation for James's ruling:** the natural-refactor posture stands for the long tail, but the two primary boards (financials-board's 18, operations-board's solid amber buttons) + morning-briefing-card will read as "mostly chrome, occasionally 2019" on day one of the reskin. A targeted 3-file warning-semantic sweep (~30 class substitutions via the migration recipe) is the cheap insurance; driver/route.tsx joins it if the September demo shows the driver portal in dark mode. Not fixed in the token-swap commit per scope protection.
