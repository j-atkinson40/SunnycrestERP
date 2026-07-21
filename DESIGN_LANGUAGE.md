# DESIGN_LANGUAGE.md

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

## 3. Substrate & elevation (oklch, dark-first, hue anchor 255)

    --substrate-base   oklch(0.16 0.008 255)   /* page canvas        */
    --surface-1        oklch(0.18 0.008 255)   /* rail, recessed     */
    --surface-2        oklch(0.21 0.009 255)   /* panel / card       */
    --surface-3        oklch(0.24 0.010 255)   /* raised / popover   */
    --edge-specular    rgb(255 255 255 / 0.05) /* 1px inset top edge */
    --shadow-panel     0 6px 20px rgb(0 0 0 / 0.35)

Every panel = surface-2 fill + a barely-there vertical gradient toward
surface-1 at the bottom + `--edge-specular` as a 1px inset top highlight
+ `--shadow-panel`. That stack is the "machined" feel. Flat fills are
banned for panels.

## 4. Text

    --text-primary     oklch(0.95 0.004 255)   /* #EDEDF0 */
    --text-secondary   oklch(0.66 0.006 255)
    --text-muted       oklch(0.55 0.006 255)

## 5. Chrome accent

    --accent-chrome        oklch(0.93 0.004 255)  /* fill  */
    --accent-chrome-hover  oklch(0.97 0.004 255)
    --on-chrome            var(--substrate-base)  /* text on chrome */
    --nav-active-indicator var(--accent-chrome)   /* 2px left border */
    --nav-active-text      oklch(0.82 0.005 255)

Primary buttons: `--accent-chrome` fill, `--on-chrome` text, 1px inset
white @ 40% top highlight. At most ONE chrome-filled primary per view;
everything else is neutral outline or ghost.

## 6. Signature steel

    --signature-steel      oklch(0.62 0.08 255)   /* ~#5E86C4 */
    --signature-steel-ring oklch(0.62 0.08 255 / 0.5)

## 7. Functional color

    --fn-positive   oklch(0.74 0.11 155)   /* ready / up      */
    --fn-negative   oklch(0.70 0.09 40)    /* overdue / danger */
    --fn-caution    oklch(0.80 0.10 78)    /* use sparingly    */

Keep `--fn-positive` a true leaf-green so it never blurs with steel.

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
- Hairlines: `rgb(255 255 255 / 0.05)`. Separators same.

## 10. Motion

Retain the existing two-easing-curve system unchanged. Chrome/steel
does not alter timing; it alters what animates (prefer opacity + 2–3%
scale on surface reveals, per the Focus backdrop spec).

## 11. OPEN — resolve before the build dispatch

- **Light mode.** The old language was light-anchored; this one is
  dark-native. Website builder, tenant portals, and Jinja document
  emission may still need light. Decide: dark-only, or dark-first with
  a derived light mode.
- **Mood anchor.** Cannot calibrate these tokens against the old
  Mediterranean-garden / cocktail-lounge photos (circular-calibration
  anti-pattern). New anchors needed — candidates: machined aluminum
  (Braun / Teenage Engineering OP-1), a pro mixing console, a darkroom.
