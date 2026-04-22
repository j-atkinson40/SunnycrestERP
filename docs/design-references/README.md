# Design References

Canonical approved visuals from the design-language creation session. When
`DESIGN_LANGUAGE.md` prose and these images ever disagree, **the images win**
(per DL §1 canonical-mood-references clause).

Future Claude instances working on aesthetic or UI decisions SHOULD inspect
these images directly (via the Read tool) before tuning tokens or adjusting
primitives. The spec is a transcription of what these images demonstrate; if
live rendering doesn't match them, the correct fix is usually to adjust the
spec + tokens to match, not to debate whether the reference is "correct."

## Files

| File | Represents | Used for |
|---|---|---|
| `IMG_6084.jpg` | John Michael Smith case card — **light mode** | Canonical card chrome reference in light mode. Shows warm-cream card surface lifted from warm-stone page, generous serif display + mono metadata + sans body typography, brass "Approve All" CTA, atmospheric-weight perimeter border, soft warm shadow halo. |
| `IMG_6085.jpg` | John Michael Smith case card — **dark mode** | Canonical card chrome reference in dark mode. Shows warm-charcoal card surface visibly lifted from dark-warm page, same typography system, same brass CTA, warm-metal-edge perimeter border, top-edge highlight catching implied lamplight, shadow grounding on page. This is the reference that drove the **Tier 2 + Tier 3 spec-reconciliation** series (April 2026). |

## How to use these references

### During aesthetic work

1. **Before changing a surface / shadow / border token**, read the relevant
   reference image(s) with the Read tool. The Read tool renders JPG content
   visually inside the Claude session.
2. Compare the current live rendering (via Playwright screenshot, browser
   devtools, or user-provided live capture) to the reference.
3. If they disagree, the fix direction is: update spec + tokens to match
   the reference, not the other way around.

### During new-feature work

1. Any new UI surface that renders as a card should inspect `IMG_6085.jpg`
   (dark) + `IMG_6084.jpg` (light) to understand the canonical card chrome.
2. If the new surface introduces something the references don't show
   (e.g. a new interactive state, a new size), derive from the references'
   principles: warm surface family, three-cue material treatment in dark
   mode, atmospheric weight in light mode, generous typography spacing,
   brass for primary CTA.

### During audits

When auditing a page for aesthetic correctness:
- Does card chrome match the reference in both modes?
- Does the surrounding page use `--surface-base` (matching reference page bg)?
- Does typography hierarchy follow the reference's display/metadata/body
  pattern (when the surface is a detail card)?

## Reference observations (for quick context without opening the files)

**Both modes share:**
- Generous corner radius (approximately 16px — `rounded-lg` range; Card
  primitive's default `rounded-md` at 8px is the dense-card variant; signature
  detail cards should opt up to `rounded-lg` via className override).
- Three typographic tiers:
  - Eyebrow: micro caps tracking-wider in muted tone (small caps "HOPKINS
    FUNERAL HOME · CASE")
  - Display: serif display, heavy weight, very large (the "John Michael
    Smith" title)
  - Metadata: mono, muted, fixed-grid (the ID + DOB–DOD + age row)
  - Body: sans, comfortable line-height, warm content-base tone
- Brass primary CTA (the "Approve All" pill button)
- No ornamentation beyond the three material cues for surface elevation

**Light-mode specifics (IMG_6084.jpg):**
- Warm stone/cream page background (approximately `--surface-base` L=0.94)
- Slightly-lifted warm cream card body (approximately `--surface-elevated`
  L=0.965)
- Atmospheric-weight perimeter border (`--border-subtle` computes to a
  whisper on cream)
- Soft warm shadow halo grounds the card on the page

**Dark-mode specifics (IMG_6085.jpg):**
- Deep warm charcoal page background (approximately `--surface-base` L=0.16)
- Visibly-lifted warm charcoal card body (approximately `--surface-elevated`
  L=0.22 — this is the Tier-3 value; pre-Tier-3 L=0.20 did not match the
  reference)
- Warm-metal-edge perimeter border (`--border-subtle` in dark mode —
  `oklch(0.35 0.015 65 / 0.5)` composited over surface-base produces a
  visible 1px warm line)
- Top-edge highlight catching implied lamplight (1px inset highlight via
  `--shadow-highlight-top` L=0.48 α=0.65)
- Three-layer shadow composition grounds + atmospheres + catches light
  (per §6 Shadow specifications Tier-2 composition)

## History

- **April 2026** — Tier-2 spec reconciliation + Tier-3 surface-lift landed.
  Three convergent token adjustments brought live rendering in line with
  `IMG_6085.jpg`: (1) shadow highlight strengthened, (2) three-layer shadow
  composition in dark mode, (3) perimeter border on Card primitive,
  (4) dark-mode surface-elevated / surface-raised lightness lifted.
  Full history in `CLAUDE.md §14 Recent Changes` + `FEATURE_SESSIONS.md`.

## Adding new references

When a new canonical visual needs to land here:
1. Save the image file (PNG or JPG) to this directory.
2. Add a row to the Files table above describing what it represents.
3. Add a "Reference observations" sub-section for quick-context scanning.
4. Commit the image + README update together.
5. Update `DESIGN_LANGUAGE.md §1 canonical mood references` section if the
   new reference is a mood-anchor (rather than a component-chrome reference).
