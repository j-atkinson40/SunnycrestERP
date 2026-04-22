# Design References

This directory holds the canonical external mood anchors for Bridgeable's
design language. The full taxonomy lives in `DESIGN_LANGUAGE.md §1`; this
README is the quick index.

## Three-category taxonomy

**1. Mood anchors (canonical — exactly two files).** Photographs of real
spaces that ground the design language in physical material reality. Used
for color, material character, atmosphere, elevation feel, shadow
character, and brass hue. These win over prose when the spec is ambiguous.

**2. Pattern references.** Approved UI renderings captured during design
work. Used for layout, composition, spacing, radius, and typography
hierarchy. **Never measured for color values** — doing so closes a
circular calibration loop (see `DESIGN_LANGUAGE.md §10` anti-pattern).
None currently in the active directory; after Tier-5 completes, select
approved mockups will be restored here under `card-pattern-reference-*`
naming.

**3. Archive.** Historical mockups, superseded designs, work-in-progress
captures. Kept for history; not authoritative.

## Current files

| Path | Category | Purpose |
|---|---|---|
| `design-ref-light.png` | **Mood anchor (canonical)** | Mediterranean garden terrace photograph — light-mode mood anchor per `DESIGN_LANGUAGE.md §1` |
| `design-ref-dark.png` | **Mood anchor (canonical)** | Cocktail lounge photograph — dark-mode mood anchor per `DESIGN_LANGUAGE.md §1` |
| `archive/IMG_6084.jpg` | Archive | Historical UI mockup of the Hopkins Funeral Home case card, light mode. Approved during design work in a prior session; used as the reference in the Tier-2 through Tier-4 spec-reconciliation arc before the circular-calibration anti-pattern was identified and the canonical mood anchors were placed. Pending restoration under `card-pattern-reference-light.png` in Tier-5+ follow-up. |
| `archive/IMG_6085.jpg` | Archive | Same card, dark mode. Same history as IMG_6084. Pending restoration under `card-pattern-reference-dark.png` in Tier-5+ follow-up. |

## Conflict resolution

Per `DESIGN_LANGUAGE.md §1`:

- **Mood anchor wins** for color, material, atmosphere, elevation feel,
  shadow character, brass hue.
- **Pattern reference wins** for layout, composition, spacing, radius,
  typography hierarchy.
- Split is non-negotiable — reversing it re-introduces circular
  calibration.

## Usage note for future Claude instances

Before calibrating any color token, read `DESIGN_LANGUAGE.md §1` (canonical
scope + calibration chain) and `§10` (circular-calibration anti-pattern).
Color calibration samples the mood anchors; pattern references are
structural only. When the mood anchor doesn't cover the specific UI element
in question, derive from `§2` translation principles rather than reaching
for an internal artifact — that reach is the loophole that produces
circular calibration.

## History

- **April 2026** — three-category taxonomy introduced after the Tier 2-4
  reconciliation arc inadvertently calibrated tokens against an approved
  UI mockup (IMG_6085.jpg) rather than a mood anchor. Formalized as a §10
  anti-pattern. Mood anchors placed in this directory; prior artifacts
  moved to `archive/` pending re-categorization under pattern-reference
  names after Tier 5 measures the mood anchors directly.
