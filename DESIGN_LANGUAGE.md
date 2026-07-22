# DESIGN_LANGUAGE.md

> ⚠️ MIRROR DISCIPLINE — READ FIRST
> The token mirrors are CANONICAL:
>   frontend/src/styles/tokens.css   (source of truth for exact identifiers)
>   frontend/src/lib/visual-editor/themes/token-catalog.ts
>   frontend/src/lib/visual-editor/themes/base-tokens.ts
> The §3–7 value tables below MIRROR those files for human reference and to record
> the calibration. On ANY divergence the mirrors win and this doc is re-synced.
> Last synced: 2026-07-22 @ d50f9cab (console/Braun calibration).
>
> CALIBRATION PROVENANCE: values are EYEBALLED to the approved console (dark) and
> Braun (light) directional previews — NOT calibrated against real-world reference
> photographs. A strong v1, not ground truth. Photo-dial refinement against actual
> anchor photos remains DEFERRED and available; it was not performed. Do not
> represent these as photo-calibrated.

> Supersedes the aged-brass / terracotta / IBM Plex language in full.
> Status: canonical. Material thread: **brushed steel, caught light.**
> The superseded brass-era document is archived at
> `docs/design-archive/DESIGN_LANGUAGE_brass-era_superseded-2026-07-21.md`
> — consult it ONLY for the two-easing-curve motion spec retained by §10
> and for historical context. Its color, type, and surface rules are dead.

## 1. Philosophy (unchanged intent, new key)

Bridgeable still looks like a Range Rover, behaves like Tony Stark's
workshop, and is built like an Apple Pro app — but the visual target
is now the *Pro app itself*: Logic, Final Cut, Xcode. Dense, neutral-
chromed, materially honest, color used only as information. Premium is
earned through craft (depth, spacing, type, restraint), not through a
signature hue. The UI is an instrument; the data is the only thing
allowed to light up.

## 2. Core color law

1. **Chrome is the accent.** Every interactive/active/primary state is
   a bright cool-neutral, not a hue. Buttons, active nav, active
   segmented control, the logo field.
2. **Steel blue is the signature — rationed.** Allowed ONLY in:
   focus/selection ring, link text, one row-hover accent, and the logo
   mark's inner detail. Never a button fill, never a large surface.
   If steel blue appears more than ~3 times on a screen, it's misused.
3. **All other color is functional.** Green = positive/ready.
   Terracotta = overdue/danger/attention. Nothing else is colored.

## 3. Substrate & elevation

Shipped identifiers first; the pivot doc's semantic names in parens.

```
                                  DARK (console, hero)        LIGHT (Braun, cooled)
--surface-base    (substrate)     oklch(0.13 0.004 255)       oklch(0.94 0.003 250)
--surface-sunken  ("surface-1",   oklch(0.16 0.005 255)       oklch(0.92 0.003 250)
                   rail/recessed)
--surface-elevated("surface-2",   oklch(0.21 0.006 255)       oklch(0.98 0.002 250)
                   panel)
--surface-raised  ("surface-3",   oklch(0.25 0.007 255)       oklch(1 0 0)
                   popover)
--edge-specular                   oklch(1 0 0 / 0.055)        oklch(1 0 0 / 0.65)
                                  (the machined catch-light)  (near-invisible on
                                                               near-white panels by
                                                               nature; light depth
                                                               reads from shadow +
                                                               hairline instead)
--border-subtle   ("border",      oklch(1 0 0 / 0.05)         oklch(0 0 0 / 0.08)
                   hairline)
(--shadow-panel composed into shadow-level-1/2/3)
```

Gradients (relationships, not literals):
- dark panel : surface-2 → oklch(0.17 0.005 255), via color-mix(elevated,sunken) @ 20%
- dark raised: surface-3 → surface-2
- light      : retains the swap's 88% color-mix formula (mirror is source of truth)

Every panel = surface fill + the barely-there vertical gradient toward
the recessed surface at the bottom + `--edge-specular` as a 1px inset
top highlight (composed into the shadow-level tokens) + the panel
shadow. That stack is the "machined" feel. Flat fills are banned for
panels; the stack is baked into the card-family primitives keyed by an
`elevation` prop (see CLAUDE.md design-system conventions).

## 4. Text

```
                                  DARK                        LIGHT
--content-base    (text-primary)  oklch(0.95 0.003 260)       oklch(0.22 0.004 260)
--content-muted   (text-secondary)oklch(0.63 0.010 255)       oklch(0.52 0.006 258)
--content-subtle  (text-muted)    oklch(0.52 0.008 255)       oklch(0.63 0.006 258)
(--content-strong = one step beyond text-primary, derived:
                                  oklch(0.97 0.003 260)       oklch(0.17 0.004 260))
```

## 5. Chrome accent — INVERTS to ink in light mode

```
                                  DARK (chrome)               LIGHT (ink)
--accent                          oklch(0.94 0.006 255)       oklch(0.22 0.004 260)
--accent-hover                    oklch(0.97 0.004 255)       oklch(0.30 0.005 260)
--accent-active                   oklch(0.87 0.007 255)       oklch(0.16 0.004 260)
--accent-disabled                 oklch(0.32 0.005 255)       oklch(0.80 0.004 250)
--content-on-accent (on-accent)   oklch(0.13 0.004 255)       oklch(0.98 0.002 250)
```

Rule: a near-white (dark) / near-black (light) accent cannot signal state with
chroma — state variants move on the LIGHTNESS axis. Hover lighter, active dimmer,
disabled low-contrast. Light mode inverts chrome→ink; same lightness logic inverted.
Washes (--accent-muted/-subtle/--border-accent) = accent RGB at fixed per-mode
alphas — dark .16/.08/.70, light .12/.06/.70 (mirror literals:
rgba(238,241,246,…) dark, rgba(23,24,26,…) light).

Primary buttons: `--accent` fill, `--content-on-accent` text, 1px inset
white @ 40% top highlight. At most ONE chrome-filled primary per view;
everything else is neutral outline or ghost. Nav active state rides
`--nav-active-indicator` (= var(--accent), 2px left border) +
`--nav-active-text`.

## 6. Signature steel — RATIONED

```
                                  DARK                        LIGHT (darkened for white)
--signature-steel                 oklch(0.68 0.10 256)        oklch(0.50 0.13 258)
--signature-steel-ring            = steel / 0.5 (both modes; the shadcn --ring and
                                    the .focus-ring-accent utility ride steel)
```

Ration law: ≤ ~3 appearances per screen — focus/selection ring, link text, one
hover accent, logo detail. Never a button fill, never a large surface.

## 7. Functional color — MEANING ONLY

```
                                  DARK                        LIGHT
--status-success (fn-positive)    oklch(0.79 0.14 158)        oklch(0.56 0.11 156)
--status-error   (fn-negative)    oklch(0.68 0.14 38)         oklch(0.55 0.13 37)
--status-warning (fn-caution)     oklch(0.76 0.13 75)         oklch(0.63 0.11 78)
```

Muted variants = the deep-tint/pale-tint L/C pattern re-keyed to these hues.
--status-info is demoted to neutral chrome (no hue) so steel is the only blue.
--status-danger aliases --fn-negative. Keep fn-positive a true leaf-green so it
never blurs with steel.

## 8. Typography

    --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                 "SF Pro Display", "Inter", system-ui, sans-serif;

SF renders natively on Apple hardware (legal, it's the OS font); Inter
is the licensed fallback for Windows/Android. **Do not bundle SF Pro as
a webfont** — not licensed for web distribution.

- Weights: 400 and 500 only. No 600/700 (too heavy against the chrome).
- Data & numerics: `font-variant-numeric: tabular-nums` everywhere.
- Micro-labels: uppercase, 10–11px, letter-spacing 0.1em, text-muted.
- Large display numerics: letter-spacing -0.02em.

## 9. Geometry

- Radii: cards 12px, controls 8–9px, pills full. Tighter than friendly.
- Grid: 4px base. Gaps 8 / 12 / 16 / 20. Panel padding 14–18px.
- Hairlines: dark oklch(1 0 0 / 0.05), light oklch(0 0 0 / 0.08).
  Separators same.

## 10. Motion

Retain the existing two-easing-curve system unchanged. Chrome/steel
does not alter timing; it alters what animates (prefer opacity + 2–3%
scale on surface reveals, per the Focus backdrop spec).

## 11. OPEN — resolve before the build dispatch

- **Light mode.** RESOLVED 2026-07-21/22 — light mode retained as a full
  parallel token set (Braun direction, cooled). See DECISIONS.md
  2026-07-22 arc-close entry.
- **Mood anchor.** RESOLVED 2026-07-22 — console (dark) / Braun-cooled
  (light) directional previews, eyeballed; ground-truth photo-dial
  deferred and available. See the mirror-discipline header's provenance
  note and DECISIONS.md 2026-07-22.
