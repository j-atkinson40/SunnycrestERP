# Bridgeable Design Language

**Status:** In authoring. Section 1 drafted; remaining sections to follow.

**Purpose:** This document defines the visual and sensory design language for the Bridgeable platform. It is the source of truth for how Bridgeable looks and feels across all verticals and all components. Component patterns (layouts, interaction flows, specific component behavior) live in `COMPONENT_PATTERNS.md`. This document changes slowly; that one changes as patterns evolve.

**Audience:**
- **Primary:** Sonnet, executing build prompts. Needs unambiguous, implementable rules.
- **Secondary:** James, reviewing shipped UI against intent.
- **Tertiary:** Future contributors who need to understand aesthetic intent without re-deriving it.

**Format:** Each rule appears in three layers — **rule**, **rationale**, **implementation**. Sonnet can skip to implementation; humans read rationale to understand why the rule exists.

---

## Section 1 — Philosophy & The Two Moods

Bridgeable presents in two modes: **light** and **dark**. These are not generic themes. They are two specific felt experiences, each with its own sensory character. They share a platform identity but express it at two different times of day.

### The two moods

**Light mode — Mediterranean garden morning.**
A stone terrace in a European garden, high above the Mediterranean. Clear morning air. Warm sun filtered through olive branches or a stone archway. A cappuccino on a linen-covered table. The light is bright but warm, the air is crisp, and everything has been placed with care. Refined, not rustic. Unhurried, not sleepy.

**Dark mode — cocktail lounge evening.**
A high-end lounge in low warm light. Deep charcoal surfaces with presence, not absence. Pools of warm light catching the tops of surfaces. Aged brass details. The dark is intimate, considered, and adult. Focused, not gloomy. Weighted, not heavy.

These two moods are **the same platform observed at two times of day.** The continuity is not visual similarity — morning and evening don't look alike — but material and intent. The same aged brass catches morning sun and evening lamplight. The same restraint governs both. A user who shifts from light to dark should feel they have stayed in the same place as the hour changed, not traveled to a different app.

### The meta-anchor: deliberate restraint

Both moods share a single underlying quality: **deliberate restraint.** Every element justifies its presence. Nothing is accidental, decorative-for-decoration's-sake, or generic.

**Rule:** Every visible element must earn its place. If a color, border, shadow, or flourish cannot be justified against the mood or the information it carries, remove it.

**Rationale:** Both moods — refined morning garden and intimate evening lounge — are restrained environments. Neither is cluttered, busy, or showy. Restraint is what makes each mood legible as *curated* rather than generic. Without this rule, the two moods drift toward decoration (morning becomes "sunny and cute"; evening becomes "dark and moody") instead of holding their felt character.

**Implementation:**
- Rules out: stock color choices ("default blue"), decorative gradients that serve no purpose, density that signals inability to decide what to remove, anything that looks accidentally generated rather than deliberately chosen.
- Rules in: specific colors for specific reasons, components that feel substantial (not flimsy, not over-engineered), empty space treated as a design element, choices that look obvious in retrospect but required taste to make.

### Light mode anchors

Five sensory anchors define light mode. Every downstream decision — color tokens, shadow specs, spacing — derives from these and should be verifiable against them.

**1. Warm cream linen base.**
- **Rule:** The primary surface color is a warm cream with noticeable material presence — like pale linen or washed pale stone in morning light. Not pure white. Not clinical. Not gray. The page reads as "warm material catching morning sun."
- **Rationale:** Pure white reads as clinical, sterile, or generic web-default. Gray reads as cold or corporate. A near-white off-white reads as cautious. A cream with genuine warmth and slight material presence establishes morning character in the single most-visible element on screen — the background itself. The canonical garden reference (see references below) anchors this as cream linen, not as near-white.
- **Implementation:** High-but-not-maximum lightness, low-but-noticeable chroma, warm hue. Specific values locked in Section 3.

**2. Clear warm diffuse light.**
- **Rule:** Shadows are warm-tinted, low-contrast, with slightly more edge definition than a fully diffuse overcast shadow. The mood is "shade under an olive tree on a stone terrace in clear morning air" — not "cloudy overcast" and not "hard noon sun."
- **Rationale:** Shadows carry most of the atmospheric character of a mode. Cool gray shadows would contradict the warm light. Fully diffuse shadows would read as sleepy or hazy. Hard-edged shadows would read as harsh. The target is clear-but-warm — legible edges, warm tint, restrained contrast.
- **Implementation:** Shadow color uses a warm hue (same family as brass/surface warmth), low opacity, medium blur, small-to-medium offset. Specific values locked in Section 6.

**3. Aged brass as the primary warm accent.**
- **Rule:** Primary actions, focus states, emphasis, and active indicators use aged brass. Not bright gold. Not yellow. Aged brass — warm, slightly muted, with the character of worn metal in warm light.
- **Rationale:** Brass is the material thread that ties morning to evening. The same metal catches morning sun and evening lamplight, which is what makes "same platform, different hour" legible across modes. Brass is also refined rather than rustic — it belongs on a European garden terrace as much as in a cocktail lounge, whereas terracotta would lock the platform into one tier of formality.
- **Implementation:** Warm hue in the gold-amber family, moderate lightness, moderate chroma. Specific values locked in Section 3. Secondary/supporting accents deferred to Section 3 when palette is specified in context.

**4. Unhurried motion.**
- **Rule:** Animations settle rather than snap. The motion character is considered, not snappy. Easing favors ease-out; things arrive gently.
- **Rationale:** Morning garden mood is unhurried. Fast snappy motion contradicts the felt target. But motion must still feel responsive — unhurried is not slow-for-slowness's-sake.
- **Implementation:** Specific durations and easing curves locked in Section 6. Durations expressed as a named scale, not ad-hoc millisecond values.

**5. Generous breathing room.**
- **Rule:** Padding, line height, and spacing between elements are generous by default. Content has space around it. The implicit message is "we have time, this is considered, you are not being rushed."
- **Rationale:** Cramped layouts contradict the refined-morning mood. A European garden terrace is not crowded. Space around elements signals that each element was placed deliberately — which reinforces deliberate restraint.
- **Implementation:** Base spacing scale and line-height defaults locked in Section 5. Density exceptions (data tables, scheduling boards) addressed in the density note below.

### Dark mode anchors

Five sensory anchors define dark mode. Same derivation principle as light mode.

**1. Deep warm cozy charcoal base.**
- **Rule:** The primary surface color is a deep warm charcoal that leans toward leather, warm wood, or lamplit plaster. Not pure black. Not blue-gray. Not neutral charcoal. A warm amber undertone, cozier than a generic dark mode.
- **Rationale:** Pure black reads as OLED-generic or as void. Blue-gray dark modes read as cold or corporate. Neutral warm charcoal is closer but still reads as "office at night." The cozy lounge mood requires the dark itself to feel like warm material — like leather or aged wood in lamplight — which means more warm chroma and a hue in the amber-brown family, not the neutral-warm family. The canonical lounge reference (see references below) shows the direction; "cozier than the reference" pushes slightly further.
- **Implementation:** Low lightness, low-but-noticeable chroma, hue in the amber-brown range (warmer than light-mode surfaces, per the warm-family asymmetry principle in Section 2). Specific values locked in Section 3.

**2. Concentrated warm light pools.**
- **Rule:** Elevated surfaces catch warm-tinted highlights from above, suggesting focused light sources. Flat surfaces fade into the dark. Elevation is communicated by light, not by outline.
- **Rationale:** Cocktail lounge lighting is pooled and directional — table lamps, recessed spots, candle-level warmth on select surfaces. Diffuse overall lighting would read as "office at night," not "lounge." This anchor is what makes the dark feel intimate rather than institutional.
- **Implementation:** Elevated surfaces use a subtle top-edge highlight and/or a slightly lifted surface color. Non-elevated surfaces do not. The gradient is meaningful (signals elevation), not atmospheric (applied to everything). Specific treatment locked in Section 6.

**3. Aged brass and amber as accent metals.**
- **Rule:** Accents are the same aged brass as light mode, observed in warm evening light. Active states and emphasis may shade toward amber — the brass glowing rather than reflecting.
- **Rationale:** Brass continuity across modes is the primary material thread of the platform. Amber is brass catching warm evening light, the same way brass in morning mode catches warm morning light. The metal does not change; the light on it does.
- **Implementation:** Same base brass hue as light mode, adjusted for lightness against the dark background to maintain legibility and mood. Active states shift hue slightly toward amber. Specific values locked in Section 3.

**4. Material, not paint.**
- **Rule:** Surfaces feel like material — leather, wood, brushed metal, stone in low light — rather than flat paint. Elevation on dark surfaces is communicated through **two cooperating cues**: (1) a **surface-lightness lift with a hue shift toward warmer amber** — cards sit at a higher-lightness, warmer-hue surface value than the page beneath them (the metal of the bar rail feels warmer where the pendant light catches it), and (2) a **wider dim top-edge highlight** that reads as focused light from above (the pendant itself catching the top edge of the material). The platform does not use discrete perimeter borders on elevated cards — edges emerge from the lift + shadow-halo + highlight stack. Borders are used selectively on components where the edge carries structural meaning (inputs, table rules, focus indicators).
- **Rationale:** Cocktail lounge surfaces are material. You can feel the wood of the bar, the leather of the seat, the brass of the rail. "Material, not paint" is the durable principle. In the lounge, surfaces don't have painted outlines around them — they have light that falls on them and material that catches it. Mapping that to UI: cards are differentiated by how they **absorb and reflect the warm light**, not by lines drawn around them. Light mode uses a lift cue alone (morning light is ambient-and-diffuse, no focused highlight) plus a warm shadow halo; dark mode adds the top-edge highlight because evening light is directional (pendants, spots) and surfaces catch it on a specific edge.
- **Implementation:** Cards carry `bg-surface-elevated` (the warmer-hue lifted surface) and `shadow-level-1` (the three-layer composition: tight ground shadow + soft atmospheric halo + dark-mode-only 3px inset top-edge highlight via `--shadow-highlight-top`). Overlays (dialogs, popovers) use the same treatment scaled up via `shadow-level-2`. NO `border border-border-subtle` on the card perimeter — the material cues carry the full edge-signaling load. Specific treatments locked in Section 6.
- **History note:** The original anchor-4 prose listed three cue OPTIONS ("top-edge highlight, surface gradient, OR warm hairline border") as equally-valid material-not-paint techniques. A Tier-2 inference-based adjustment (April 2026) misread this as "cards apply all three" and added a canonical perimeter border to the Card primitive. Tier-4 measurement of the approved reference (`docs/design-references/IMG_6085.jpg`) showed the canonical design uses only two cues (lift + highlight); the perimeter border was removed. The learning: when a canonical reference exists, sample it directly before inferring from prose. "Images win over prose" applies to diagnosis as well as design authority.

**5. Deliberate, weighted motion.**
- **Rule:** Motion character is the same as light mode — unhurried, ease-out, settles rather than snaps — but with a slightly more weighted feel. Evening tempo. Like settling into a chair rather than moving through a doorway.
- **Rationale:** Evening mood is more deliberate than morning mood. Motion should reflect this without becoming sluggish. The difference is felt in character, not in dramatic timing differences.
- **Implementation:** Shared motion system with mode-scoped adjustments where needed. Specific durations and easing locked in Section 6.

### Density is allowed; clutter is not

Both moods default to breathing room, but Bridgeable has legitimately dense views — scheduling boards, case lists, quote tables, the full-plant yard display. The moods must survive density.

**Rule:** Dense views retain the mood. They earn their density by making every element legible and purposeful. Density is not an excuse for clutter; clutter is what happens when density is not designed.

**Rationale:** A scheduling board with 40 entries can still feel like Mediterranean morning if the entries are well-typed, well-spaced within their constraints, and the surrounding chrome stays calm. A case list can still feel like evening lounge if the typography is restrained and the background stays warm. Density without design produces clutter, which breaks both moods by violating deliberate restraint. The anchors apply at all densities — the implementation varies.

**Implementation:**
- Dense views may compress the base spacing scale, but do not abandon it. Compressed spacing is still proportional.
- Dense views do not add decorative elements to fill perceived emptiness. Empty cells, quiet rows, and calm chrome are correct.
- Dense views still use the mode's shadow, border, and accent treatments. The brass still appears where brass belongs; it just appears smaller.
- The test: zoom out on a dense view. Does it still read as morning garden (or evening lounge) at a glance? If yes, the mood survived. If it reads as "dashboard" or "data table," the mood was lost to density.

### The aged-brass thread

**Rule:** Aged brass is the single material that appears in both modes as the primary warm accent. It is the platform's material signature.

**Rationale:** Without a material thread across modes, light and dark become two unrelated themes. With the brass thread, they become two expressions of the same place. A user moving between modes should feel that the brass is the same brass — the light on it changed, the metal did not. This is the single most important continuity decision in the document.

**Implementation:** The base brass hue is consistent across modes. Lightness and chroma adjust to maintain legibility and mood against each background. Exact values locked in Section 3. The brass is not used decoratively; it marks primary action, focus, and emphasis in both modes. It is the thing the eye goes to, in both morning and evening.

### Canonical mood references

Two images serve as the canonical anchors for the two moods. They should be stored in project knowledge alongside this document and referenced whenever this section's prose leaves ambiguity.

**Light mode — `design-ref-light.png`:** A stone terrace in a European garden, high above the Mediterranean. Pergola with climbing bougainvillea, aged brass lantern, terracotta tile floor, warm stone walls, a table set with pale linen, potted olives and herbs, the sea visible beyond a wrought-iron railing. This image is the canonical anchor for the light-mode mood. When a prose rule in this document could be interpreted two ways, default to the interpretation closer to this image.

Specific anchor points in the reference:
- The linen tablecloth is the closest analog to the base surface color.
- The aged brass of the lantern and chair frames is the canonical brass hue.
- The shadows under the pergola and under the table show the target shadow character: warm, low-contrast, softly edged.
- The terracotta floor is an example of a warm *structural* material, not a UI accent. It confirms that terracotta belongs to floor/foundation, not to emphasis or action.
- The sea blue in the distance is a muted atmospheric cool note, deferred for now per Section 3.

**Dark mode — `design-ref-dark.png`:** A high-end cocktail lounge in low warm light. Walnut bar top, aged brass pendants in a row, a warm charcoal textured wall with a brass sun sculpture, leather club chairs, distant city view through mullioned windows. This image is the canonical anchor for the dark-mode mood, with the following correction: our dark mode should feel **cozier** than this image — warmer overall, more absorbed light, smaller implicit scale. The grand lounge in the reference is the direction; a smaller warmer version is the target.

Specific anchor points in the reference:
- The brass pendant lamp interiors and the sun sculpture are the canonical brass-in-evening-light hue. Note that they read as the same metal as the morning-light brass in the light-mode reference.
- The charcoal wall is the direction for the base surface, pulled slightly warmer and browner for the cozy target.
- The wood of the bar top and the leather of the chairs are examples of the "material, not paint" principle applied at full intensity. UI surfaces should echo this in restraint — they should feel like material without mimicking specific textures.
- The pools of light from the pendants are the elevation logic: light where attention belongs, warm dark elsewhere.

### Canonical scope — what counts as a reference, what doesn't

`docs/design-references/` contains **exactly two canonical mood-anchor files:**

- `design-ref-light.png` — the Mediterranean garden terrace photograph
- `design-ref-dark.png` — the cocktail lounge photograph

These are the platform's external mood anchors. They are **photographs of real spaces**, not UI renders, and that is load-bearing: their value comes from being grounded in physical material reality that the design language is translating into pixels. Their warmth, their shadow character, their brass patina — these are observed from reality, not specified.

Other files in `docs/design-references/` fall into two non-canonical categories:

**Pattern references** (e.g., `card-pattern-reference-*.png`) — renderings of UI compositions approved during design work. Used for structural decisions: card shape, spacing, radius, typography hierarchy, component composition. **Never measured for color values** — doing so closes a circular calibration loop because the rendering was produced from the tokens being calibrated. Pattern references answer "what should this look like structurally"; mood anchors answer "what should this feel like materially."

**Archive** (in the `archive/` subfolder) — historical mockups, superseded designs, work-in-progress captures. Kept for history; not authoritative for anything current.

**Conflict resolution:** when mood anchor and pattern reference disagree, **mood anchor wins** for color, material character, atmosphere, elevation feel, shadow character, and brass hue. **Pattern reference wins** for layout, composition, spacing, radius, and typography hierarchy. This split is non-negotiable: reversing it re-introduces the circular calibration problem.

### The calibration chain

When the design language requires token calibration — because a prose rule is ambiguous, or a perceived drift needs measurement — the calibration chain must be:

```
External mood anchor (design-ref-*.png)
    ↓ sample directly (e.g. PIL)
    ↓ identify the photographed material that maps to the UI surface
    ↓ (per prose analogies above: "the charcoal wall is the direction
    ↓  for the base surface"; "the walnut bar top is the direction for
    ↓  elevated surfaces catching warm light")
    ↓
Token values (tokens.css + DL §3, mirror-synchronized)
    ↓
UI rendering (primitives + pages)
    ↓
Pattern reference (card-pattern-reference-*.png)
    — captures approved UI composition at a point in time
    — feeds back into structural decisions (spacing, layout, radius)
    — NEVER feeds back into color calibration
```

Never this:

```
UI mockup / pattern reference (derivation — already downstream of tokens)
    ↓ sample the mockup
    ↓
Token values ← CIRCULAR — calibrates tokens against their own output
```

### When the mood anchors don't cover a UI concern

The mood photographs depict physical spaces, not UI. They don't show stat cards, tables, form controls, modals, or any other software composition. When a UI decision must be made that the mood anchors don't demonstrate, the correct method is **derivation via §2 translation principles**, not approximation via pattern references.

Example: the mood anchor shows a walnut bar top catching pendant light — that's the elevation principle in its natural form. A stat card doesn't exist in the photo, but the principle applies: a card surface catches implied warm light relative to the ambient dark. Derive the card treatment from the principle, not from an existing mockup of what a card "should" look like. Pattern references may confirm the composition *after* the principle-derived treatment is applied, but they don't originate color or material decisions.

This matters because pattern references feel tempting when mood anchors seem "not specific enough" to answer a UI question. That temptation is exactly where circular calibration enters. The correct response to "the mood anchor doesn't show this exact UI element" is to derive from §2 principles, not to reach for an internal artifact that does show the element.

### How to use the references

- When writing a new component, compare it to the mood anchors first. Does the light-mode version feel like it could exist on that terrace? Does the dark-mode version feel like it could exist in that lounge (but cozier)?
- When specifying a new color, verify via PIL sampling against the mood anchor, then adjust per §2 translation principles.
- When specifying a new layout, structure, or composition, verify against pattern references (if one exists for that component) and §5 spacing principles.
- When in doubt about warmth, density, or material character, the **mood anchors** win over prose.
- When in doubt about layout, structure, or composition, the **pattern references** win over ad-hoc design.
- When both are silent, derive from §2 translation principles. Do not reach for an internal artifact that appears to answer the question; that path is where the circular calibration anti-pattern (§10) enters.

### Calibration history

**Tier 5 (April 2026)** — first calibration of tokens against the external mood photographs per the calibration chain above. PIL-sampled `design-ref-dark.png` (cocktail lounge) and `design-ref-light.png` (Mediterranean garden) at the material analogs named in the "specific anchor points" sections above (charcoal wall / walnut bar top / pendant interiors / under-pergola shadows / linen tablecloth / lantern), converted to OKLCH, compared to then-current tokens, and corrected three sets:

- **`--surface-elevated` (dark)** L=0.20 → L=0.28. Prior value sat in the walnut-grain-dark range; corrected to the "catching pendant light" range per §1 dark anchor 2.
- **`--surface-base` (light)** chroma 0.018 → 0.030. Photo measured linen at C=0.037; backed off slightly because token→UI-at-scale amplifies perceived warmth.
- **`--shadow-color-{subtle, base, strong}`** (both modes) — lifted L, doubled C, hue shifted 3–5° warmer. Prior tokens composited darker + cooler than the anchors' photographed shadows.
- **`--surface-raised` (dark)** L=0.24 → L=0.32 derived proportionally from the elevated lift.

Prior tiers 2–4 attempted calibration against an approved UI mockup (`IMG_6085.jpg`, now in `archive/`) which was itself downstream of the then-current tokens — a circular calibration loop (§10). Tier 5 anchors to the external mood photographs per §1's calibration chain; the circular-calibration anti-pattern and this calibration-chain requirement were formalized in the same arc.

Explicit non-corrections (values held against photo deltas with specific rationale):

- **`--surface-base` (dark)** L=0.16 held. Photo measured charcoal wall at L=0.21 (bright), but §1 prose specifies "pulled slightly warmer and browner for the cozy target" — cozier = darker + more absorbed. Token sits at the dark "cozy" end of the wall's variance.
- **`--surface-base` (dark)** hue 59 held. Photo measured h=114 (olive-tinted charcoal), token at h=59 (warmer amber). Direction-correct per §1 "warmer and browner" correction.
- **Dark brass** (L=0.70) held. Photo's pendant-interior measurement (L=0.80) was of the directly-illuminated bright interior — closer to an active/hover brass state than a base state.
- **Light brass** held. Measurement unreliable (sampling hit aged-wood frame rather than polished metal).

Future calibrations should cite this history when making further adjustments.

---

## Section 2 — Translation Principles

Section 1 defines the moods as felt experiences. Section 3 will define exact token values. This section is the bridge: the rules that connect anchors to values, so that anchors are verifiable against implementation and future decisions have a principled derivation path rather than arbitrary choice.

**How to use this section:**
- Sonnet reads this section to understand the *rules* that govern color, shadow, and material decisions.
- Sonnet reads Section 3 to get *the specific values* that comply with those rules.
- Section 3 values must fall within Section 2 ranges. If they don't, one of the two sections is wrong.
- When a new color, shadow, or material treatment is needed and doesn't exist in Section 3, this section tells Sonnet how to derive it.

### Color space: oklch

**Rule:** All color values are expressed in oklch. Hex, rgb, and hsl are not used in tokens. CSS may compile to rgb/hex at the browser level, but the design system authors in oklch exclusively.

**Rationale:** oklch gives us three things the design language needs and that hsl/rgb don't: perceptually uniform lightness (L=0.5 looks equally bright regardless of hue, which is false in hsl), independent hue/chroma/lightness axes (we can adjust one without the others shifting), and a predictable chroma axis that corresponds to how saturated a color actually appears. This matters most for the aged-brass thread — the same brass hue has to work at different lightness values in light and dark modes, and only oklch lets us lock hue while adjusting lightness without the color drifting.

**Implementation:** All tokens in Section 3 are authored as `oklch(L C H)` values. CSS custom properties use the `oklch()` function directly. Tailwind config references oklch. When communicating colors in documentation or prompts, oklch is the canonical form.

### The warm-hue family

**Rule:** All surface colors, shadow colors, and neutral tokens sit in a warm hue family — hue angle between **70 and 95** in oklch. This applies in both light and dark modes. Accents may sit outside this range (brass is in this range; a future cool supporting accent would not be); surfaces and their shadows do not.

**Rationale:** Coherence across the platform requires that the backgrounds and shadows share a hue family. If the light-mode background is warm (hue ~85) but the light-mode shadow is neutral gray (hue effectively undefined or cool), the shadow contradicts the mood. Same for dark mode: if the charcoal is warm but the card elevation shadow is cool, the lounge mood breaks. Locking the surface-and-shadow hue family is the single most important coherence rule in the platform — it's what makes morning feel like morning in every corner of the UI, not just on the page background.

**Implementation:**
- Light-mode base surface: hue 75–90
- Dark-mode base surface: hue 70–90
- All shadow colors: hue 60–90
- All neutral text colors (which are tinted, not pure): hue 70–95
- Accents are not bound by this rule but brass happens to fall in it (hue ~75–85), which is why brass reads as belonging rather than as an accent bolted onto neutral chrome.

### Translation rules per anchor

Each anchor from Section 1 translates to oklch ranges. Section 3 picks specific values within these ranges.

**Warm cream linen base (light mode, anchor 1)**
- **Lightness:** 0.94–0.97
- **Chroma:** 0.008–0.020
- **Hue:** 80–92
- **Verification test:** Place a pure white (`oklch(1 0 0)`) patch next to the chosen base. The base should read as "cream linen" or "pale warm stone" against the pure white, not as "off-white gray" and not as "bright white." If the chosen base reads as gray next to pure white, chroma is too low or hue is too cool. If it reads as near-white, lightness is too high — the base should have noticeable material presence, not clinical brightness.
- **Reference correction note:** An earlier draft of this range specified lightness 0.97–0.99 and chroma 0.005–0.015. The canonical garden reference (see Section 1 references) shows that the closest analog surface — the linen tablecloth — has more warmth and more material presence than near-white. This range was adjusted to match the reference, moving from "warm off-white" to "cream linen."

**Clear warm diffuse shadow (light mode, anchor 2)**
- **Shadow color lightness:** 0.25–0.45 (shadows are not black; they are dark warm tones at low opacity)
- **Shadow color chroma:** 0.02–0.05 (some color, not neutral)
- **Shadow color hue:** 60–85 (warm, possibly slightly more orange than the surface hue to read as "sunlit shadow")
- **Shadow opacity:** 0.06–0.14 (low contrast; shadows are felt, not stamped)
- **Shadow blur:** medium — specific values in Section 6
- **Verification test:** A shadow should look warm-tinted when isolated on a neutral background. If a card's shadow looks gray when you screenshot it against white, it's wrong.

**Aged brass (both modes, light-mode anchor 3 and dark-mode anchor 3)**
- **Hue:** 70–78 (narrow, locked across modes; amber-leaning aged brass, not yellow-gold)
- **Light mode lightness:** 0.62–0.72
- **Light mode chroma:** 0.10–0.14
- **Dark mode lightness:** 0.68–0.78
- **Dark mode chroma:** 0.11–0.15
- **Active/glowing state (dark mode):** lightness may rise to 0.76–0.82 and chroma to 0.13–0.16. Hue does not shift — active brass glows through lightness and chroma, not through hue change. This is how actual brass glows in warm light: brighter and more intense, not more orange.
- **Verification test:** The light-mode brass and dark-mode brass, placed side by side, should read as the same metal observed under different light. If they read as two different colors, the hue has drifted. If dark-mode active brass reads as orange or copper, the hue shifted — pull it back to the base brass hue.
- **Reference correction note:** An earlier draft specified hue 75–85 and a 5° amber shift for active states. After pick-validation, the range tightened to 70–78 (amber-leaning) and the amber shift was replaced with a lightness/chroma lift, because the base brass is already in the amber family and a further amber shift reads as copper rather than glowing brass.

**Deep warm cozy charcoal base (dark mode, anchor 1)**
- **Lightness:** 0.14–0.20
- **Chroma:** 0.008–0.020
- **Hue:** 55–75
- **Verification test:** Place pure black (`oklch(0 0 0)`) next to the chosen base. The base should read as "warm leather" or "cozy lamplit dark material" against pure black, not as "almost black" and not as "gray." If it reads as near-black, lightness is too low. If it reads as gray or blue-gray, chroma is too low or hue is outside the warm-amber range.
- **Reference correction note:** Earlier drafts specified lightness 0.18–0.24 and less chroma. After two rounds of in-context verification against the lounge reference, the range was pulled deeper (accommodating a locked value at 0.16) to support the cozier-than-reference direction. The dark mode reads as properly-evening lamplit rather than early-evening dimmed.

**Concentrated warm light pools (dark mode, anchor 2)**
- Elevated surfaces use a lifted base: lightness +0.03 to +0.06 from the base charcoal, same hue family, same low chroma.
- Top-edge highlight (where used): a 1px line at lightness 0.35–0.45, hue 75–85, low chroma 0.01–0.03, opacity 0.3–0.6. The highlight reads as reflected warm light, not as a border.
- **Verification test:** Raise a card on the dark background. Does it feel lit from above, or does it feel outlined? If outlined, the treatment failed — outlines are not how this mood expresses elevation.

**Material, not paint (dark mode, anchor 4)**
- Not a color range — a treatment principle. Implementation in Section 6.
- Constraint: any material treatment (gradient, highlight, hairline edge) must be subtle enough that it doesn't read as decoration. If a user notices the gradient, it's too strong. The correct level is "feels like material" without being able to point to what makes it so.

### Warm-family asymmetry across modes

**Rule:** Light mode's warm family centers on hue 80–92 (warm cream, pale stone, clear morning light). Dark mode's warm family centers on hue 55–75 (lamplight, leather, warm wood, evening amber). The family is warm in both modes but leans noticeably more orange-amber in dark mode. Brass locks to a single hue across modes (per the cross-mode rule below) and sits at the warm edge of the light-mode family and the cooler edge of the dark-mode family — which is why brass reads as native to both.

**Rationale:** Symmetric hues across modes produce a dark mode that reads as "daylight dimmed" rather than "evening lamplight." The cozy lounge mood requires that the ambient warmth shift, not just the lightness. Morning sun filtered through garden air has a different color temperature than evening lamps through leather-lined walls. The asymmetry encodes this difference.

**Implementation:**
- Non-brass surfaces in light mode use hues in 80–92.
- Non-brass surfaces in dark mode use hues in 55–75.
- Brass uses a single fixed hue across modes (locked per the cross-mode rule).
- When deriving a new surface color for dark mode, pull its hue toward 55–75 even if the light-mode equivalent is at 85. Do not copy the light-mode hue into dark mode.

### Shadows persist in dark mode

**Rule:** Dark mode has shadows. Elevated elements cast warm-tinted shadows on the base surface, low-contrast but visible as atmosphere. Shadows in dark mode are not dropped, not replaced by borders, and not replaced solely by top-edge highlights.

**Rationale:** A common dark-mode pattern drops shadows entirely and communicates elevation via color lightness and borders only. This pattern produces "flat dark UI" — legible but cold. The cozy lounge mood depends on soft warm shadows filling the space between elements, the way real shadows fill the space under and around objects in lamplight. A dark mode without shadows reads as institutional; a dark mode with warm low-contrast shadows reads as intimate.

**Implementation:**
- Dark-mode shadow color: lightness 0.08–0.16, chroma 0.005–0.015, hue 50–70, opacity 0.30–0.55.
- Dark-mode shadows are *larger and softer* than light-mode shadows — shadows in low light naturally diffuse more. Blur is higher, offset is similar.
- The top-edge highlight (where used on elevated surfaces) is an *additional* cue, not a replacement for the shadow. Elevated surfaces get both: a warm top-edge highlight and a warm soft shadow below.
- Verification test: screenshot an elevated card on the dark base. Can you see the shadow as a warm slightly-darker patch around and below the card? If the shadow is invisible, opacity is too low. If it reads as gray or black, hue is wrong.

### The aged-brass cross-mode rule

**Rule:** Aged brass is one color, expressed at two lightness values. The hue is locked across modes at a single value: **73** (amber-leaning aged brass). Chroma varies minimally. Only lightness shifts meaningfully, and only enough to maintain legibility against the mode's background. Active/glowing states shift lightness and chroma; they do not shift hue.

**Rationale:** This is what operationalizes the aged-brass thread from Section 1. Without a locked hue, the "same brass in different light" claim collapses — you just have two yellows. With a locked hue and shifting lightness, the brass genuinely behaves like a single metal observed at two times of day. The no-hue-shift rule for active states is important because the locked hue already sits in the amber family; shifting further toward amber produces copper or bronze, not glowing brass.

**Implementation:**
- Brass hue is `73` — a single locked value, not a range. This is *the* brass hue of the platform.
- The light-mode brass token and dark-mode brass token both use hue 73.
- Lightness and chroma shift per mode within the ranges specified above.
- Active/glowing states in both modes adjust via lightness and chroma. Hue stays at 73.
- Any new brass-adjacent accent (e.g., a copper variant, a darkened-brass variant) must also sit at hue 73 unless it is explicitly a different metal — in which case it requires its own accent entry in Section 3, not a brass variant.

### Deriving a new color

When a new color is needed — a new status color for a new vertical, a new informational accent, a visualization palette — use this derivation procedure:

**Step 1: Identify the nearest anchor.**
Is this color a surface? A shadow? An accent? A status indicator? Map it to the closest anchor concept. If it doesn't map to any existing anchor, stop and ask whether a new anchor is needed (this is a design language change, not a token addition).

**Step 2: Start from the anchor's oklch range.**
Use the anchor's lightness, chroma, and hue ranges as the starting point.

**Step 3: Adjust the minimum necessary axis.**
If the new color needs to be distinguishable from the anchor (e.g., a new status color distinct from brass), adjust the single axis that carries the distinction and leave the others alone. For semantically distinct colors (error, warning, success), adjust hue. For variants of the same semantic role (hover, active, disabled), adjust lightness.

**Step 4: Verify against both modes.**
The new color must work in both light and dark modes. If it's a single token, it needs two values (one per mode). Apply the cross-mode consistency principle: lock hue, shift lightness.

**Step 5: Verify against the mood.**
Place the new color against the mode's base surface and a sample component. Does it feel like it belongs in the garden / lounge, or does it feel bolted on? If bolted on, the chroma is likely too high or the hue is outside the warm family. Pull it back toward the warm family and lower the chroma until it feels native.

**Anti-rule:** Do not pick a new color by starting from a generic palette (Material, Tailwind defaults, Bootstrap) and "warming it up." Start from the anchor. Generic palettes carry generic mood, and warming them after the fact produces colors that read as "slightly warmed generic" rather than as native to Bridgeable.

### Verification posture

Every color decision in Section 3 and beyond should be verifiable by reading this section. The test:

1. Pick any token from Section 3.
2. Identify which translation rule governs it.
3. Confirm the token's oklch values fall within the rule's ranges.
4. Confirm the token passes the rule's verification test (the "looks like X against Y" checks above).

If any step fails, either the token is wrong or this section is wrong. Both are fixable; silent drift is not.

## Section 3 — Color System

This section commits to specific oklch values for every semantic color token in the platform. All values fall within the ranges specified in Section 2 and are verifiable against Section 2's rules. Section 3 is the *answer*; Section 2 is the *test*.

**Mirror discipline:** The values in this section and `frontend/src/styles/tokens.css` **must stay synchronized**. A change to either requires a same-commit update to the other. Documentation drift between this canonical reference and the implementation is treated as a defect. Sonnet should verify this invariant before committing any token change.

**Structure:**
- The three anchor tokens are locked explicitly.
- Derived tokens (elevated surfaces, text, borders, muted variants) are derived from anchors per Section 2's translation rules.
- Status colors (error, warning, success, info) are derived using Section 2's "Deriving a new color" procedure.
- The full token table lists every CSS variable name and its light-mode and dark-mode values.

### Anchor tokens (locked)

These are the three decisions that everything else in the color system derives from. Changing one of these values invalidates every derived token and requires a full re-derivation.

| Token | Light mode | Dark mode |
|---|---|---|
| **Surface base** | `oklch(0.94 0.018 82)` | `oklch(0.16 0.012 65)` |
| **Brass (primary accent)** | `oklch(0.66 0.12 73)` | `oklch(0.70 0.13 73)` |

Brass hue locked at **73** across modes. Surface base hue asymmetric across modes (82 in light, 65 in dark) per Section 2's warm-family asymmetry rule.

### Semantic token naming convention

Tokens use the pattern `--{role}-{variant}` where role describes what the color is *for* (surface, content, accent, status) and variant describes its specific use (base, elevated, muted, strong).

- **surface** — backgrounds, cards, panels, anything that content sits on
- **content** — text, icons, anything that sits on a surface
- **accent** — brass and any future accents, used for emphasis and action
- **border** — lines that separate or outline surfaces
- **shadow** — shadow colors (not opacities, which are separate)
- **status** — semantic state colors (error, warning, success, info)

Variants:
- **base** — default state
- **elevated** — one step lifted above the surrounding surface (e.g., a card on a page)
- **raised** — two steps lifted (e.g., a modal on a card-filled page)
- **muted** — lower-contrast version for secondary use
- **subtle** — even lower contrast, for tertiary use
- **strong** — higher-contrast version for emphasis
- **hover / active / focus / disabled** — interactive state modifiers

Not every token has every variant. The table below lists all defined tokens.

### Surface tokens

**Rationale:** Elevation in this platform is communicated by **two coordinated dimensions of color change**: lightness and hue. An elevated surface is lighter AND warmer-hued than the base. Light mode uses a uniform ~0.025 lightness step per elevation level — morning light is ambient-and-diffuse, so the delta stays small. Dark mode uses a **non-uniform step**: base→elevated is ~0.12 OKLCH (the big leap where surfaces begin "catching warm light"), elevated→raised is ~0.04 (overlays are one level more lifted than their containing context). Dark mode also shifts hue warmer at each elevation step — this is the second material dimension. The non-uniform dark-mode step and the hue progression together encode DL §1 dark-mode anchor 2 ("concentrated warm light pools"): flat base surfaces fade into the dark; elevated surfaces are where directional warm light lands.

| Token | Light mode | Dark mode |
|---|---|---|
| `--surface-base` | `oklch(0.94 0.030 82)` | `oklch(0.16 0.010 59)` |
| `--surface-elevated` | `oklch(0.965 0.014 82)` | `oklch(0.28 0.014 81)` |
| `--surface-raised` | `oklch(0.985 0.010 82)` | `oklch(0.32 0.016 85)` |
| `--surface-sunken` | `oklch(0.91 0.020 82)` | `oklch(0.13 0.010 55)` |

*Notes:*
- Chroma decreases slightly as lightness increases in light mode — the lightest surfaces approach near-white and carry less warmth. This is intentional: the raised surface feels like "paper catching more light" rather than "saturated pale." Tier-5 calibration (April 2026) against design-ref-light.png linen tablecloth raised `--surface-base` chroma 0.018 → 0.030; photo measured C=0.037, token backed off to 0.030 because token→UI-at-scale amplifies perceived warmth.
- Chroma increases slightly as lightness increases in dark mode — elevated surfaces carry *more* warmth, because they're catching more of the implied warm lamplight. This is the cocktail lounge material logic.
- **Dark-mode hue progression** is the second material-not-paint dimension: `base` sits at h=59 (the cool-amber foundation), `elevated` shifts to h=81 (the warmer-amber "catches more lamplight" treatment), `raised` continues to h=85 (most-elevated, most-directly-lit). `sunken` drops to h=55 (cooler, recessed-from-light). The hue shift IS what makes a dark elevated surface feel like "warm metal catching pendant light" rather than just "a lighter shade of the same surface." Without the hue shift, lightness-lift alone reads as monotone grading and doesn't deliver the "material, not paint" anchor.
- **Dark-mode non-uniform step (Tier-5):** base→elevated L=0.12 is deliberately larger than elevated→raised L=0.04. The mood-anchor scenario (walnut bar top catching pendant light) shows a dramatic luminance difference between the charcoal wall (base, ~L=0.21 measured, pulled darker to L=0.16 per §1 "cozier than reference" correction) and the walnut surface directly under the pendant (elevated, measured L=0.40-0.52 at bulk, L=0.91 at highlight). Token L=0.28 sits deliberately below the bulk-walnut value because a UI card at pixel-coverage scale reads brighter than a textured material sample in a photo; L=0.28 preserves the catching-light signal without over-brightening the card. Elevated→raised then uses the smaller 0.04 step because "raised" is overlay-level hierarchy, not material-level hierarchy — one step more lifted, not "catching fundamentally different light."
- `surface-sunken` is used for deep-recessed areas (inset panels, code blocks, sidebar backgrounds that sit below the page level). Not commonly used; defined for consistency.
- **Reconciliation history (April 2026):** pre-Tier-4, dark-mode tokens used a static h=65 across the elevation stack. Tiers 2–4 attempted progressive calibration against an approved UI mockup (IMG_6085.jpg, now archived). Tier-5 sampled the external mood anchors directly (`design-ref-dark.png` cocktail lounge + `design-ref-light.png` Mediterranean garden) per the §1 calibration chain and corrected `--surface-elevated` (dark) L=0.20→0.28, `--surface-raised` (dark) L=0.24→0.32, `--surface-base` (light) C=0.018→0.030, and the three shadow-color tokens in both modes. Tier-4 hue progression (59→81→85) retained — directionally correct. Tier-2 three-layer shadow composition (tight ground + soft halo + 3px inset highlight) retained — architecturally correct.

### Content tokens (text and icons)

**Rationale:** Text is never pure black on light mode or pure white on dark mode. Both are tinted with warm hue to belong to the platform's warm family. Contrast against surfaces is tuned to meet WCAG AA at minimum for body text; `content-base` and `content-strong` meet AAA on `surface-base`.

| Token | Light mode | Dark mode |
|---|---|---|
| `--content-strong` | `oklch(0.22 0.015 70)` | `oklch(0.96 0.012 80)` |
| `--content-base` | `oklch(0.30 0.015 70)` | `oklch(0.90 0.014 75)` |
| `--content-muted` | `oklch(0.48 0.014 70)` | `oklch(0.72 0.014 70)` |
| `--content-subtle` | `oklch(0.62 0.012 70)` | `oklch(0.55 0.012 68)` |
| `--content-on-brass` | `oklch(0.98 0.006 82)` | `oklch(0.18 0.015 60)` |

*Notes:*
- `content-strong` is for headings and critical emphasis. `content-base` is body text.
- `content-muted` is secondary text (captions, metadata). `content-subtle` is tertiary (placeholder text, disabled states).
- `content-on-brass` is the color used for text/icons placed *on* brass surfaces (e.g., label on a brass button). Light mode uses near-white with warm tint; dark mode uses the deep warm charcoal family so brass buttons read as "glowing pill with dark text" rather than "bright button with white text."

### Border tokens

**Rationale:** Borders are subtle by default. Bridgeable does not rely on hard borders to create structure — elevation and spacing do most of the structural work, and borders provide gentle definition where needed. In dark mode, borders can also serve as "warm metal edges" per the material-not-paint anchor.

| Token | Light mode | Dark mode |
|---|---|---|
| `--border-subtle` | `oklch(0.88 0.012 80) / 0.6` | `oklch(0.35 0.015 65) / 0.5` |
| `--border-base` | `oklch(0.82 0.015 78) / 0.8` | `oklch(0.42 0.018 68) / 0.7` |
| `--border-strong` | `oklch(0.70 0.020 76)` | `oklch(0.55 0.025 70)` |
| `--border-brass` | `oklch(0.66 0.12 73) / 0.7` | `oklch(0.70 0.13 73) / 0.7` |

*Notes:*
- Borders use alpha compositing (noted with `/ N`) by default so they adapt subtly to the surface they're on.
- `border-brass` is used sparingly — for focus rings, selected states, and brass-edged emphasis. Not a general-purpose border.
- `border-strong` is the only border that uses a solid color (no alpha). Used for table rules, divider lines that need to hold their weight.

### Shadow tokens

**Rationale:** Shadows are warm-tinted in both modes per Section 2's warm-hue family rule. Dark mode shadows persist (they don't disappear) per the "shadows persist in dark mode" principle, but they're lower contrast and warmer than light mode.

| Token | Light mode | Dark mode |
|---|---|---|
| `--shadow-color-subtle` | `oklch(0.40 0.045 78) / 0.06` | `oklch(0.11 0.020 65) / 0.35` |
| `--shadow-color-base` | `oklch(0.40 0.045 78) / 0.10` | `oklch(0.09 0.020 65) / 0.45` |
| `--shadow-color-strong` | `oklch(0.37 0.050 75) / 0.16` | `oklch(0.08 0.020 65) / 0.55` |
| `--shadow-highlight-top` | *not used* | `oklch(0.32 0.010 61) / 0.9` |

*Notes:*
- `shadow-highlight-top` is the top-edge highlight used on elevated surfaces in dark mode per Section 2's "material, not paint" anchor. It's a thin (1px) inset highlight that reads as reflected warm light. Not used in light mode.
- Shadow composition (blur, offset) is specified separately in Section 6.

### Accent tokens

**Rationale:** Brass is the only locked accent. A supporting accent (potentially a muted cool note) is deferred per earlier scope decisions. Sections 2 and 3 are authored to accommodate a cool supporting accent in the future if needed; no current tokens depend on one existing.

| Token | Light mode | Dark mode |
|---|---|---|
| `--accent-brass` | `oklch(0.66 0.12 73)` | `oklch(0.70 0.13 73)` |
| `--accent-brass-hover` | `oklch(0.62 0.13 73)` | `oklch(0.74 0.13 73)` |
| `--accent-brass-active` | `oklch(0.58 0.13 73)` | `oklch(0.78 0.14 73)` |
| `--accent-brass-muted` | `oklch(0.85 0.05 73) / 0.8` | `oklch(0.35 0.06 73) / 0.8` |
| `--accent-brass-subtle` | `oklch(0.92 0.025 73) / 0.6` | `oklch(0.26 0.04 73) / 0.6` |

*Notes:*
- **Light mode hover** darkens and slightly saturates (press-in feel).
- **Dark mode hover** lightens (glow feel) — opposite direction because the interactive affordance in each mode is different.
- **Active** is the fully pressed/engaged state: even darker in light mode, even brighter in dark mode.
- **Muted** is brass at low chroma for backgrounds that need to signal brass-adjacency without being brass itself (e.g., a brass-tinted badge background, the background of a selected row). Alpha allows it to compose with whatever surface it sits on.
- **Subtle** is the barest brass tint, used for very quiet brass signals (e.g., the fill of a hover state on a menu item).
- All variants lock hue to 73. No exceptions.

### Status tokens

**Rationale:** Status colors (error, warning, success, info) are derived per Section 2's "Deriving a new color" procedure. They must feel native to the platform's warm family — not bolted-on generic red/yellow/green/blue. Each status hue is chosen to be distinguishable from the others and from brass while sitting within the platform's overall warmth.

Derivation approach:
- **Error (red)** — hue in the warm-red family (20–30), distinct from brass (73). Chroma moderate-high for urgency.
- **Warning (amber)** — hue adjacent to brass (60–65). Distinguishable from brass but clearly in the same warm family.
- **Success (green)** — hue in the warm-olive-green family (130–140), pulling slightly yellow rather than blue-green. This ties to the living-green garden anchor from the light-mode reference.
- **Info (blue-gray)** — hue in the muted-Mediterranean range (220–230), low chroma to stay restrained. This is also the place where the deferred "cool supporting accent" partially appears, as an informational cue rather than a structural accent.

| Token | Light mode | Dark mode |
|---|---|---|
| `--status-error` | `oklch(0.55 0.18 25)` | `oklch(0.68 0.17 25)` |
| `--status-error-muted` | `oklch(0.92 0.04 25)` | `oklch(0.22 0.07 25)` |
| `--status-warning` | `oklch(0.70 0.14 65)` | `oklch(0.76 0.14 65)` |
| `--status-warning-muted` | `oklch(0.94 0.04 65)` | `oklch(0.24 0.06 65)` |
| `--status-success` | `oklch(0.58 0.12 135)` | `oklch(0.70 0.13 135)` |
| `--status-success-muted` | `oklch(0.93 0.04 135)` | `oklch(0.22 0.05 135)` |
| `--status-info` | `oklch(0.55 0.08 225)` | `oklch(0.70 0.09 225)` |
| `--status-info-muted` | `oklch(0.93 0.03 225)` | `oklch(0.22 0.04 225)` |

*Notes:*
- Status `muted` variants are backgrounds for status callouts (the yellow tint behind a warning message). Status `base` is the foreground (border, icon, bold text).
- Warning is close to brass hue (65 vs 73) but meaningfully different. The 8° gap is enough that they don't confuse; use warning for *transient* state signals (form validation, inline warnings) and brass for *affordance* (actionable emphasis). They should not appear adjacent in the same component.
- Info chroma is noticeably lower than the others. This is deliberate — info is the coolest color in the system and needs restraint to avoid reading as out-of-place against the warm platform.
- Success hue (135) is yellow-green, not blue-green. This matches the olive/garden green of the light-mode reference and reads as organic rather than synthetic.
- **Aesthetic Arc Session 4 (M1) adjustment — dark-mode `status-*-muted` backgrounds.** Pre-Session-4 dark-mode muted lightness values were 0.28/0.30 with chroma 0.05–0.08. That placed `text-status-{X}` on `bg-status-{X}-muted` at 3.83–4.32:1 — below WCAG AA 4.5:1 for body text. Current values (L 0.22/0.24, chroma eased) clear 5.0–5.4:1. Visually aligns with Section 2 dark-mode anchor "concentrated warm light pools" — status callouts read as lamplight at low angle rather than a washed-out tinted rectangle.

### Full CSS variable list

The final CSS variables for implementation. Sonnet uses these exact names.

```css
:root {
  /* Surfaces */
  --surface-base: oklch(0.94 0.030 82);
  --surface-elevated: oklch(0.965 0.014 82);
  --surface-raised: oklch(0.985 0.010 82);
  --surface-sunken: oklch(0.91 0.020 82);

  /* Content */
  --content-strong: oklch(0.22 0.015 70);
  --content-base: oklch(0.30 0.015 70);
  --content-muted: oklch(0.48 0.014 70);
  --content-subtle: oklch(0.62 0.012 70);
  --content-on-brass: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.88 0.012 80 / 0.6);
  --border-base: oklch(0.82 0.015 78 / 0.8);
  --border-strong: oklch(0.70 0.020 76);
  --border-brass: oklch(0.66 0.12 73 / 0.7);

  /* Shadows */
  --shadow-color-subtle: oklch(0.40 0.045 78 / 0.06);
  --shadow-color-base: oklch(0.40 0.045 78 / 0.10);
  --shadow-color-strong: oklch(0.37 0.050 75 / 0.16);

  /* Accents */
  --accent-brass: oklch(0.66 0.12 73);
  --accent-brass-hover: oklch(0.62 0.13 73);
  --accent-brass-active: oklch(0.58 0.13 73);
  --accent-brass-muted: oklch(0.85 0.05 73 / 0.8);
  --accent-brass-subtle: oklch(0.92 0.025 73 / 0.6);

  /* Status */
  --status-error: oklch(0.55 0.18 25);
  --status-error-muted: oklch(0.92 0.04 25);
  --status-warning: oklch(0.70 0.14 65);
  --status-warning-muted: oklch(0.94 0.04 65);
  --status-success: oklch(0.58 0.12 135);
  --status-success-muted: oklch(0.93 0.04 135);
  --status-info: oklch(0.55 0.08 225);
  --status-info-muted: oklch(0.93 0.03 225);

  /* Focus ring alpha — default (Session 4, m2).
     Composed into the brass focus ring via
     `color-mix(in oklch, var(--accent-brass) calc(var(--focus-ring-alpha) * 100%), transparent)`. */
  --focus-ring-alpha: 0.40;
}

[data-mode="dark"] {
  /* Surfaces — Tier-4 measurement-based correction (April 2026):
     calibrated to IMG_6085.jpg sampled values. Hue progresses with
     elevation (h=59→81→85) per §1 anchor 4 "Material, not paint" —
     this is the second material dimension the prior tokens missed.
     Tier-3's lightness bumps (L=0.22 / L=0.27) reverted to pre-
     Tier-3 values (L=0.20 / L=0.24) which match reference. */
  --surface-base: oklch(0.16 0.010 59);
  --surface-elevated: oklch(0.28 0.014 81);
  --surface-raised: oklch(0.32 0.016 85);
  --surface-sunken: oklch(0.13 0.010 55);

  /* Content */
  --content-strong: oklch(0.96 0.012 80);
  --content-base: oklch(0.90 0.014 75);
  --content-muted: oklch(0.72 0.014 70);
  --content-subtle: oklch(0.55 0.012 68);
  --content-on-brass: oklch(0.18 0.015 60);

  /* Borders */
  --border-subtle: oklch(0.35 0.015 65 / 0.5);
  --border-base: oklch(0.42 0.018 68 / 0.7);
  --border-strong: oklch(0.55 0.025 70);
  --border-brass: oklch(0.70 0.13 73 / 0.7);

  /* Shadows — Tier-4 correction (April 2026):
     --shadow-highlight-top calibrated to reference measurement.
     Reference shows 3-pixel top-edge band at L≈0.30; value below
     matches the dimmer-per-pixel, wider band (see §6 Shadow
     specifications for the 3px inset width). */
  --shadow-color-subtle: oklch(0.11 0.020 65 / 0.35);
  --shadow-color-base: oklch(0.09 0.020 65 / 0.45);
  --shadow-color-strong: oklch(0.08 0.020 65 / 0.55);
  --shadow-highlight-top: oklch(0.32 0.010 61 / 0.9);

  /* Accents */
  --accent-brass: oklch(0.70 0.13 73);
  --accent-brass-hover: oklch(0.74 0.13 73);
  --accent-brass-active: oklch(0.78 0.14 73);
  --accent-brass-muted: oklch(0.35 0.06 73 / 0.8);
  --accent-brass-subtle: oklch(0.26 0.04 73 / 0.6);

  /* Status (Session 4 M1: muted backgrounds tightened for WCAG AA) */
  --status-error: oklch(0.68 0.17 25);
  --status-error-muted: oklch(0.22 0.07 25);
  --status-warning: oklch(0.76 0.14 65);
  --status-warning-muted: oklch(0.24 0.06 65);
  --status-success: oklch(0.70 0.13 135);
  --status-success-muted: oklch(0.22 0.05 135);
  --status-info: oklch(0.70 0.09 225);
  --status-info-muted: oklch(0.22 0.04 225);

  /* Focus ring alpha — dark-mode override (Session 4, m2).
     0.40 → 0.48 lifts contrast on `--surface-raised` from
     ~3.00:1 (WCAG 2.4.7 edge) to ~3.5:1. */
  --focus-ring-alpha: 0.48;
}
```

### Verification note

Every value in the table above should pass Section 2's verification tests. Anyone auditing this section can:
1. Take any token
2. Look up its governing rule in Section 2
3. Confirm the oklch value falls inside the rule's range
4. Run the verification test (e.g., "place against pure white, does it read as cream?")

If any token fails, either the token is wrong or Section 2 is wrong. Both are fixable; silent drift is not.

## Section 4 — Typography

Typography carries as much mood as color. The wrong typeface on the right palette produces an interface that feels incoherent — the colors say "Mediterranean morning" and the letters say "generic SaaS." This section picks the typefaces and specifies how they're used.

### Typeface family

Bridgeable uses the **IBM Plex** family across sans, serif, and monospace. One family, three faces, unified by a single designer's voice.

**Rationale:** Humanist sans-serifs carry warmth in their letterforms that geometric sans-serifs don't. Plex Sans specifically has a slight mechanical-but-warm character — the letterforms read as designed metal rather than drawn ink, which reinforces the "material, not paint" anchor from Section 1. Using one family across all three faces (Sans, Serif, Mono) produces coherence without effort: a case number in Plex Mono sits naturally next to a heading in Plex Sans next to a decedent name in Plex Serif, because they share proportion, stroke philosophy, and spacing rhythm. This is the single-designer-voice principle and it matters more than picking the "best" sans and the "best" serif and the "best" mono separately.

**Implementation:**
- **IBM Plex Sans** — primary UI typeface. Body text, labels, navigation, most headings.
- **IBM Plex Serif** — display typeface, used for gravitas moments only (see rules below).
- **IBM Plex Mono** — structured data. Case IDs, order numbers, timestamps, step identifiers, code, tabular numbers where alignment matters.
- **Loading:** Self-host via `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-serif`, `@fontsource/ibm-plex-mono`. Subset to Latin. Preload the three primary weights (400, 500, 600 for Sans; 500 for Serif display; 400 for Mono). Avoid the Google Fonts CDN because of third-party latency.

### When to use each face

**Plex Sans** is the default. Use it for everything unless a rule below specifies otherwise.

**Plex Serif** appears only in gravitas moments. It is not decorative; it carries specific semantic weight. Serif is correct for:
- **Decedent names** on case detail pages (funeral home vertical). A decedent's name is not a form field value — it carries the weight of a person. Rendering it in serif acknowledges that.
- **Primary page titles on high-stakes pages.** The top of a case detail, a vault order, a signed certificate. Serif signals "this is the thing."
- **Signature moments on marketing and portal surfaces.** Welcome messages, farewell messages, gratitude language on family portals.
- **Quoted language.** Pull-quotes, testimonials, memorial language.

Serif is wrong for:
- Dashboard metrics (those are data, not gravitas).
- Navigation, buttons, form labels, or any UI chrome.
- Marketing headlines that are selling a product rather than honoring a moment.
- Long-form body text (Plex Serif is a display serif; extended reading should stay in Plex Sans).

**Plex Mono** is used for structured data that benefits from fixed-width alignment:
- Case numbers (`FC-2026-0001`), order numbers, invoice numbers, migration names (`fh_02_cross_tenant`).
- Timestamps and durations where alignment aids scanning.
- Code blocks, command-bar input, any literal system language.
- Columns of numbers in tables where decimal alignment matters.

Mono is wrong for:
- Regular numbers in prose or body text.
- Phone numbers, addresses, dates (these read more naturally in Sans).
- Decorative use where the typewriter feel is aesthetic rather than functional.

### Type scale

The scale is modular, based on a 1.25 ratio (major third). Every size is expressed in rem with a 16px root. Sonnet implements sizes via Tailwind's `text-{size}` classes; the classes below map to the design language names.

| Token | Size (rem) | Size (px at 16px root) | Line height | Use |
|---|---|---|---|---|
| `text-display-lg` | 3.052 | 48.83 | 1.1 | Signature display moments only (hero surfaces, major page titles on marketing) |
| `text-display` | 2.441 | 39.06 | 1.15 | Display serif page titles on case detail, vault order, signature pages |
| `text-h1` | 1.953 | 31.25 | 1.2 | Primary page titles |
| `text-h2` | 1.563 | 25.00 | 1.25 | Section headings |
| `text-h3` | 1.25 | 20.00 | 1.3 | Subsection headings, card titles |
| `text-h4` | 1.125 | 18.00 | 1.35 | Small section labels, prominent list items |
| `text-body` | 1.0 | 16.00 | 1.55 | Default body text |
| `text-body-sm` | 0.875 | 14.00 | 1.5 | Secondary text, compact layouts, form helper text |
| `text-caption` | 0.75 | 12.00 | 1.45 | Metadata, timestamps, tertiary labels |
| `text-micro` | 0.6875 | 11.00 | 1.4 | Floor size — badge labels, very small indicators |

**Rationale:**
- The 1.25 ratio is more conservative than the 1.333 "perfect fourth" ratio common in display-heavy design. Conservative ratio suits Bridgeable because most content is utility-oriented; dramatic size contrast would fight the deliberate-restraint meta-anchor.
- Line heights decrease as size increases, per normal typographic practice. Body text at 1.55 gives the generous breathing room specified in Section 1, anchor 5 (light mode) without becoming loose.
- `text-micro` is a floor. Nothing smaller. If something needs to be smaller than 11px, the information architecture is wrong — you're trying to cram something into a space that's too small.

### Weight discipline

Bridgeable uses **three weights only**: Regular (400), Medium (500), Semibold (600). No bold. No light. Hierarchy is created by size, color, and size-weight pairing — not by piling on weights.

**Weight rules:**
- **Regular (400)** — body text, UI labels, form input values, navigation items, secondary text, captions.
- **Medium (500)** — headings (H1 through H4), primary action labels on buttons, active navigation, table column headers, card titles, emphasized inline text.
- **Semibold (600)** — reserved for critical emphasis only. Primary page titles on high-stakes pages (when paired with Plex Serif Semibold), brass buttons that represent the primary action on a screen, status labels that require attention (errors, warnings in active state).

**Rationale:** Fewer weights produces more consistent hierarchy. Three weights is enough to create clear emphasis without inviting weight-soup (the UI problem where every element has been bolded to "emphasize" it, producing a page where nothing emphasizes anything). The discipline is hard but the payoff is a platform that reads as considered rather than urgent.

**Italic usage:** Italics are allowed but used sparingly. Correct uses: titles of works, foreign-language terms, genuine emphasis inline (rare). Wrong uses: decorative emphasis, UI labels, button text, headings. Italic is a semantic tool, not a style tool.

### Size-weight pairings

The type scale pairs with weights in specific combinations. Deviation from these pairings requires explicit design justification.

| Role | Size token | Face | Weight | Notes |
|---|---|---|---|---|
| Display page title | `text-display` | Plex Serif | 500 | Case detail, vault order, signature pages |
| Primary page title | `text-h1` | Plex Sans | 500 | Standard page titles |
| Section heading | `text-h2` | Plex Sans | 500 | Section breaks within a page |
| Subsection heading | `text-h3` | Plex Sans | 500 | Card titles, form section headers |
| Compact heading | `text-h4` | Plex Sans | 500 | Small headers, labels, list item titles |
| Body default | `text-body` | Plex Sans | 400 | Paragraphs, descriptions, most content |
| Body emphasis | `text-body` | Plex Sans | 500 | Emphasized inline text (use sparingly) |
| Body secondary | `text-body-sm` | Plex Sans | 400 | Helper text, metadata in body context |
| UI label | `text-body-sm` | Plex Sans | 500 | Form labels, button text, navigation |
| Primary action button | `text-body-sm` | Plex Sans | 600 | Brass buttons representing the primary screen action |
| Caption | `text-caption` | Plex Sans | 400 | Timestamps, author attribution, metadata |
| Caption emphasis | `text-caption` | Plex Sans | 500 | Metadata requiring attention |
| Data — identifier | varies | Plex Mono | 400 | Case numbers, IDs, migration names |
| Data — timestamp | `text-caption` | Plex Mono | 400 | Timestamps in tabular context |
| Data — code | `text-body-sm` | Plex Mono | 400 | Code blocks, command-bar input |

### Paragraph rules

**Line length:** Body text wraps at **62–72 characters per line** as a comfortable reading measure. Enforce with a max-width around `34rem` (545px at 16px root). Wider measures produce reading strain; narrower measures produce rag that looks nervous.

**Line height:** Body text uses 1.55. Captions use 1.45. Headings use 1.2–1.35 per the scale above. Deviation requires justification.

**Paragraph spacing:** Between paragraphs, use `margin-bottom` equal to the line height — roughly 1.55em for body text. Do not use double line breaks or larger gaps; the visual rhythm should feel like continued thought, not "new section."

**Letter spacing (tracking):** Plex Sans does not need tracking adjustment at most sizes. Exceptions:
- Micro text (11px) — add `+0.01em` tracking to improve legibility at small sizes.
- All-caps text — add `+0.05em` tracking (all-caps always needs more tracking). Use sparingly; all-caps is not a Bridgeable pattern for body content, only for very specific small labels (e.g., section eyebrows).

### Numerals

Plex Sans ships with both proportional and tabular figures. Use:
- **Proportional figures** in running text (most uses).
- **Tabular figures** in tables, data columns, financial displays, anywhere numbers align vertically.

CSS: `font-variant-numeric: tabular-nums` for the tabular case.

Plex Mono is inherently tabular — all characters are fixed-width — so numeric alignment is automatic in mono contexts.

### Text color

Text colors are defined in Section 3 (`content-strong`, `content-base`, `content-muted`, `content-subtle`, `content-on-brass`). Typography does not redefine them; it specifies *when* each is used.

**Content-strong** — headings, display text, primary page titles, critical emphasis. The darkest content color in each mode.

**Content-base** — default body text. Used for the bulk of reading content. Meets WCAG AAA against `surface-base`.

**Content-muted** — secondary information: metadata, helper text, captions, less-important labels. Still legible but visually recessed.

**Content-subtle** — tertiary information: placeholder text, disabled state, timestamps in de-emphasized contexts, informational background.

**Content-on-brass** — text rendered *on* brass surfaces (buttons, brass-filled badges). Never used for text rendered on any other surface.

### Dark-mode typography adjustments

Per Section 2's warm-family asymmetry, text colors shift hue across modes (75 in light, 80 in dark for strong text). Typography itself — size, weight, line height, face — does not change between modes. One exception:

**Font smoothing:** In dark mode, enable `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale`. This reduces the perceived weight of light text on dark backgrounds, which otherwise reads too bold because of the eye's tendency to flare bright text into surrounding dark. Without this, dark-mode text can feel like it's wearing more weight than it should.

In light mode, leave font smoothing at browser default (subpixel antialiasing). This preserves sharpness at small sizes.

### Anti-patterns specific to typography

- **Using Plex Serif for body text or form labels.** It's a display face. Extended reading in a display serif is fatiguing and signals "trying hard."
- **Using Plex Mono for regular numbers.** Prices in running prose, dates in sentences, and percentages in body text should stay in Plex Sans. Mono is for *alignment-requiring* data.
- **Piling on weight for emphasis.** A semibold heading followed by a semibold subhead followed by semibold emphasis within body text is weight-soup. Pick one level of emphasis per visual region.
- **All-caps body text.** All-caps is for tiny labels (eyebrows, section tags), never for paragraphs or headings longer than a few words.
- **Mixing non-Plex fonts.** No exceptions. Adding a third font family breaks the single-voice principle and produces incoherence that takes real work to notice but real time to fix.
- **Italic for decorative emphasis.** Italics carry semantic meaning (titles of works, foreign terms, genuine emphasis). Decorative italic reads as trying hard and usually just weakens the emphasis it's trying to create.

## Section 5 — Spacing & Layout

Spacing carries the breathing room anchor from Section 1. Layout carries the structural decisions that determine how content is arranged on screen. Both are mostly mechanical once the base unit and scale are set — but the mechanical rules have to be explicit, because spacing inconsistency is the single easiest way for a system to drift into incoherence.

### Base unit

The atomic spacing value is **4px**. Every spacing, sizing, and layout value in the system is a multiple of 4.

**Rationale:** 4px gives enough granularity for dense data views (case lists, scheduling boards, tables) where the difference between 8px and 12px row gaps matters, while remaining disciplined enough that the scale doesn't become chaotic. 8px would force coarser choices that are wrong for dense content; 2px or 1px would invite arbitrary values. 4px is the standard default in modern systems (matches Tailwind's default scale) and is enough granularity without license.

**Implementation:**
- Every spacing, padding, margin, gap, sizing token is a multiple of 4px.
- Tailwind's default spacing scale is used directly: `p-1` (4px), `p-2` (8px), `p-3` (12px), `p-4` (16px), `p-5` (20px), `p-6` (24px), `p-8` (32px), `p-10` (40px), `p-12` (48px), `p-16` (64px), `p-20` (80px), `p-24` (96px).
- Non-multiples are forbidden. A developer needing 15px has mis-specified; the right answer is 12 or 16.

### Spacing scale

The system uses a named scale keyed to semantic purpose, not just to raw pixel values. Sonnet picks from the scale by purpose, not by guessing pixel values.

| Token | Value | Purpose |
|---|---|---|
| `space-0` | 0 | No spacing. Explicit zero. |
| `space-0.5` | 2px | Hairline. Almost never used; reserved for micro-adjustments. |
| `space-1` | 4px | Tight spacing — icon-to-label gaps, tightly-coupled elements. |
| `space-2` | 8px | Close spacing — related items within a component, form field gaps in dense forms. |
| `space-3` | 12px | Compact spacing — secondary padding, row gaps in dense tables. |
| `space-4` | 16px | **Default component padding.** The base unit for most UI padding. |
| `space-5` | 20px | Comfortable spacing — padding inside cards, gaps between form fields in standard forms. |
| `space-6` | 24px | Generous component spacing — padding inside larger cards, vertical rhythm between paragraphs. |
| `space-8` | 32px | Section spacing — gap between related sections within a page. |
| `space-10` | 40px | Region spacing — gap between distinct content regions. |
| `space-12` | 48px | Major section spacing — gap between major page sections. |
| `space-16` | 64px | Hero spacing — top/bottom padding on major page-top regions. |
| `space-20` | 80px | Rare — used for hero surfaces on marketing pages. |
| `space-24` | 96px | Rare — reserved for signature moments on external-facing pages. |

**The density-default bias:** Spacing defaults favor the generous side of the scale. A new card's default padding is `space-5` (20px), not `space-4` (16px). A new page's default region spacing is `space-10` (40px), not `space-8` (32px). This encodes the "generous breathing room" anchor from Section 1 by default; tightening requires deliberate choice.

**Dense overrides:** Dense views (data tables, scheduling boards, yard displays, case lists with many rows) use an explicit tighter scale:
- Row padding: `space-2` or `space-3` instead of `space-4`.
- Inter-row gaps: `space-1` or `space-2`.
- Card padding in dense contexts: `space-4` instead of `space-5` or `space-6`.

Dense overrides are compressions of the same scale — they do not introduce new values. A dense row padded at 12px is still on the scale; a dense row padded at 14px is a violation.

**Verification test for any component:** Does the spacing feel deliberate, or does it feel like someone picked whatever looked "about right"? The test is whether every padding, margin, and gap in the component maps to a named scale value. If a spacing value is off-scale, it's wrong, even if it looks correct.

### Component padding conventions

These are the default paddings for common component types. They establish the system's rhythm.

| Component | Default padding | Dense variant |
|---|---|---|
| Button | `py-2.5 px-5` (10px / 20px) | `py-2 px-3` (8px / 12px) |
| Text input | `py-2.5 px-4` (10px / 16px) | `py-2 px-3` (8px / 12px) |
| Card | `p-6` (24px) | `p-4` (16px) |
| Hero card (e.g., case detail) | `p-8` or `p-10` (32px or 40px) | *not applicable* |
| Modal | `p-6` (24px) | `p-4` (16px) |
| Table cell | `py-3 px-4` (12px / 16px) | `py-2 px-3` (8px / 12px) |
| Table header cell | `py-2.5 px-4` (10px / 16px) | `py-2 px-3` (8px / 12px) |
| List item | `py-3 px-4` (12px / 16px) | `py-2 px-3` (8px / 12px) |
| Navigation item | `py-2.5 px-3` (10px / 12px) | — |
| Page container | `p-8` or `p-10` (32px or 40px) | `p-4` or `p-6` (16px or 24px) |

Button note: the 10/20 padding produces a button that feels substantial rather than squeezed. Buttons too-small are a common SaaS anti-pattern; Bridgeable's buttons feel like they were placed deliberately, which matches the meta-anchor.

### Layout approach: flexible with max-widths

Bridgeable does not use a global column grid. Pages use content-appropriate max-widths. Components that need internal grids (dashboards with resizable widgets) define their own — at the component level, not the page level.

**Rationale:** A global 12-column grid is the right tool for marketing and editorial layouts, where content flows within predetermined column boundaries. It is the wrong tool for application UI, where content dictates the layout — a case detail page, a scheduling board, and a command-bar overlay have nothing in common structurally, and forcing them into a shared 12-column grid produces rigid layouts that fight the content. Bridgeable is primarily application UI, so the default is flexible layout with max-widths. Dashboards get their own internal grid because drag-to-resize widgets require a column substrate, but that is a dashboard-component concern, not a page-layout concern. This distinction must be explicit because design systems routinely conflate the two.

**Page-level layout:**
- Pages have a single primary content container with a max-width appropriate to the content.
- The container is centered horizontally with even left/right padding (`p-8` or `p-10` typical).
- Navigation (top bar, side bar) sits outside the content container and spans the viewport.
- No global column grid. Each page decides its own structure.

### Max-width tokens

Max-width tokens define the common page widths. Sonnet picks a token by content type, not by guessing pixel widths.

| Token | Value | Use |
|---|---|---|
| `max-w-reading` | 34rem (544px) | Reading content — body prose, long-form text, articles. Matches the 62–72 character reading measure from Section 4. |
| `max-w-form` | 40rem (640px) | Single-column forms — case creation, vault order entry, contact forms. |
| `max-w-content` | 56rem (896px) | Standard content pages — case detail, order detail, most app pages with mixed content. |
| `max-w-wide` | 72rem (1152px) | Wide content pages — pages with multiple content regions side-by-side. |
| `max-w-dashboard` | 96rem (1536px) | Dashboard and data-dense views — hubs, scheduling boards, list views. |
| `max-w-full` | 100% | Full-viewport pages — yard display, plant floor view, anything that consumes available space. |

**Default:** If no max-width token is specified for a page, `max-w-content` is the default.

**Selection logic for Sonnet:**
- Long-form prose → `max-w-reading`
- Single-column form with a handful of fields → `max-w-form`
- Case detail, order detail, standard mixed-content page → `max-w-content`
- Page with a primary region plus a secondary sidebar → `max-w-wide`
- Dashboard, hub, scheduling board, data-dense list → `max-w-dashboard`
- Plant floor, yard display, kiosk → `max-w-full`

### Dashboards — internal 12-column widget grid

Dashboards are the one place a column grid exists in Bridgeable, and it is strictly a **component-level** concern: the widget substrate inside a dashboard container. It is not a page layout grid.

**Rule:** Dashboard widgets sit in a 12-column internal grid that supports drag-to-resize widget sizing. Each widget declares a column span (1–12) and a row span (1–N). The grid exists to enable resize and reflow, not to govern page layout.

**Rationale:** Drag-to-resize widgets require a column substrate because users need snap targets — continuous-pixel resizing produces unusable jitter. A 12-column grid provides enough granularity that widgets can be sized meaningfully (full-width = 12, half = 6, third = 4, quarter = 3) without creating an infinite number of layout permutations. This is a Workflow Arc commitment and is scoped to dashboard widgets only.

**Implementation:**
- Dashboard containers define `grid-template-columns: repeat(12, minmax(0, 1fr))` with `gap: space-4` (16px) between widgets.
- Widgets specify `grid-column: span N` and `grid-row: span M`.
- The grid is inside the dashboard container. The dashboard container itself sits inside a page layout that uses a max-width per the table above (typically `max-w-dashboard`).
- Widgets may contain their own internal layouts — lists, tables, charts, mini-forms — and those internal layouts do not participate in the dashboard grid.

**Non-dashboard pages:** Do not use a 12-column grid. Do not add `grid-template-columns: repeat(12, ...)` to non-dashboard layouts "for consistency." The consistency is across dashboards, not across all pages.

### Vertical rhythm

Spacing between stacked content follows predictable vertical rhythm.

- **Paragraph-to-paragraph within prose:** `space-4` (16px) — roughly one line of body text, producing "continued thought" rhythm.
- **Subsection heading to body content:** `space-3` (12px) — tight, because the heading and the content it introduces belong together.
- **Body content to next subsection heading:** `space-6` (24px) — generous, because the transition is a new subsection.
- **Section heading to body content:** `space-4` (16px).
- **Section to next section:** `space-10` (40px).
- **Major region to next major region:** `space-12` (48px) or `space-16` (64px).

The asymmetric rhythm (tight below headings, generous above them) is important — it visually associates headings with the content they introduce rather than treating the heading as equidistant between its content and the content above.

### Responsive behavior

Bridgeable is primarily a desktop-first application. Mobile responsiveness is supported for specific use cases (family portals, mobile-dispatch views for plant operators, driver apps) but most admin UI assumes a desktop viewport.

**Breakpoints:**
- `sm`: 640px — phone landscape, small tablet
- `md`: 768px — tablet portrait
- `lg`: 1024px — tablet landscape, small laptop
- `xl`: 1280px — standard laptop
- `2xl`: 1536px — large desktop

**Responsive spacing behavior:**
- Below `md` (768px), page container padding compresses from `p-8` / `p-10` to `p-4` / `p-6`.
- Below `md`, dense views compress further into their dense variants.
- Card padding compresses one step in the scale (space-6 → space-4) below `md`.
- Max-widths do not change; smaller viewports simply hit the viewport edge with appropriate padding.

Mobile is explicitly scoped: the family portal (public-facing mobile), the plant operator mobile dispatch, and the driver app. All other Bridgeable UI may degrade gracefully on mobile but is not designed for it. A user who opens the admin dashboard on their phone gets a readable but unoptimized experience; this is intentional, not a failure.

### Anti-patterns

- **Using arbitrary spacing values** (13px, 14px, 18px, etc). If the value is not on the scale, it is wrong.
- **Introducing a global 12-column grid** for non-dashboard pages. The 12-column grid is a dashboard widget substrate; bringing it to page layout rigidifies UI that should be content-driven.
- **Packing dense views without using the dense scale.** Dense views use smaller but still on-scale values. "Just tighten the padding by a couple px" produces off-scale values.
- **Inconsistent page-to-page max-widths** for similar content types. If two pages show case details, they use the same max-width. Drift produces platforms that feel inconsistent even when individual pages look fine.
- **Heroic hero sections.** Pages starting with 160px of empty vertical space before any content. The generous-default bias applies within the scale; `space-24` (96px) is the ceiling for rare signature moments, not the default.

## Section 6 — Surface and Behavior

This section specifies how surfaces express physical presence (elevation, shadows, borders, material treatments) and how they respond to interaction (motion, timing, easing). Surface and behavior are grouped because they together create "how things feel physically" — separating them into different sections would scatter the co-creators of that feel.

The color values used here are specified in Section 3; this section specifies how they're *applied* — the geometry, the composition, the timing.

### Elevation system

Bridgeable uses four levels of elevation. Elevation communicates depth and hierarchy: what's primary, what's lifted, what's recessed.

| Level | Name | Use |
|---|---|---|
| 0 | Base | Page background, default surface. Everything starts here. |
| 1 | Elevated | Cards, panels, grouped content. The default "lifted" level. |
| 2 | Raised | Modals, dropdown menus, popovers. One level above the surrounding UI. |
| 3 | Floating | Command bar, toasts, tooltips. Temporary overlays that sit above everything. |

A level-1 card on a level-0 page is the default case. A level-2 modal over a level-1 card means the modal reads as "above the page." A level-3 floating element sits above all other levels.

**Rule:** Elevation is monotonic within a visible region. A level-1 card should not contain a level-2 element (except modals/popovers triggered from within it). Mixing elevation levels inside the same visual region produces incoherent depth perception.

### Shadow specifications

Shadows are the primary mechanism for communicating elevation in light mode and a co-mechanism (with surface lightness and top-edge highlights) in dark mode. Per Section 2, all shadow colors are warm-tinted.

**Light mode shadows:**

| Level | Shadow composition |
|---|---|
| 0 (base) | *no shadow* |
| 1 (elevated) | `0 2px 8px var(--shadow-color-base)` |
| 2 (raised) | `0 8px 24px var(--shadow-color-base), 0 2px 6px var(--shadow-color-subtle)` |
| 3 (floating) | `0 16px 40px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base)` |

**Dark mode shadows (three-layer composition — finalized in Tier-4, April 2026):**

| Level | Shadow composition |
|---|---|
| 0 (base) | *no shadow* |
| 1 (elevated) | `0 1px 3px var(--shadow-color-strong), 0 4px 16px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top)` |
| 2 (raised) | `0 2px 4px var(--shadow-color-strong), 0 12px 32px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top)` |
| 3 (floating) | `0 3px 6px var(--shadow-color-strong), 0 24px 56px var(--shadow-color-strong), 0 8px 20px var(--shadow-color-strong), inset 0 3px 0 var(--shadow-highlight-top)` |

**Notes on the composition:**

- Dark-mode shadows are larger and softer than light-mode shadows — shadows in low light naturally diffuse more. The blur is roughly 2x the light-mode equivalent at each level.
- **Dark mode uses a three-layer composition for every elevation level** (tight grounding shadow + soft atmospheric halo + 3px inset top-edge highlight). The tight grounding shadow roots the element on the page surface. The soft halo provides atmospheric depth. The inset highlight catches implied lamplight on the top edge. Three layers are necessary because low-lightness surface deltas are perceptually compressed in dark mode — the warm base color alone doesn't carry enough elevation signal.
- Light-mode shadows use a one-shadow composition at level 1 and a two-shadow composition at levels 2–3. Material presence in light mode comes from the warm base color itself and the shadow warmth, not from explicit reflection + grounding.
- Dark-mode shadows include a **3px** `inset 0 3px 0` top-edge highlight using `--shadow-highlight-top` (`oklch(0.32 0.010 61 / 0.9)`). The 3px width is measurement-calibrated (reference IMG_6085.jpg shows a 3-pixel highlight band at L≈0.30 — a wider dimmer band reads as a focused light pool catching the top edge, a 1-pixel hairline does not). This is the "material, not paint" anchor (§1 dark-mode anchor 4) expressed concretely: elevated surfaces catch implied lamplight on their top edge. The highlight reads as focused light caught on a warm surface, not as a border outline.
- **Reconciliation history (April 2026):** pre-Tier-2, dark-mode shadows used a simpler two-layer composition (soft halo + inset highlight only) with L=0.42 α=0.45 highlight. Live rendering read less-distinct than the approved reference. Tier 2 added tight grounding shadows + strengthened the highlight to L=0.48 α=0.65, AND inferred from §1 anchor 4 prose that a canonical perimeter border on the Card primitive would help. Tier 3 further bumped dark-mode surface lightness. User visual verification after Tier 3 still didn't match the reference. Tier 4 sampled the reference directly via PIL (`docs/design-references/IMG_6085.jpg`) — a UI mockup, not the mood anchor — and calibrated tokens to it. **Tier 5** then sampled the external mood anchors (`design-ref-dark.png` cocktail lounge + `design-ref-light.png` Mediterranean garden) per the §1 calibration chain, and corrected three axes Tier 4 had left wrong:
    - **Dark elevated surface lightness** lifted L=0.20 → 0.28 (Tier 4 sat in walnut grain-dark; Tier 5 moved to walnut catching-light range).
    - **Dark raised surface lightness** lifted L=0.24 → 0.32 proportionally.
    - **Light base chroma** increased 0.018 → 0.030 (photo-calibrated linen tablecloth warmth).
    - **Shadow-color tokens** (all three, both modes) lifted L + doubled C + hue-shifted 3-5° warmer — photo shadows are warmer and softer than prior tokens composited.
  Tier-4 hue progression (dark mode h=59→81→85) was directionally correct and retained. Tier-2 three-layer shadow composition (tight ground + soft halo + 3px inset highlight) was architecturally correct and retained; only the shadow-color and highlight parameters changed.
- **Learning (canonicalized in CLAUDE.md + §10 anti-pattern):** when a canonical reference exists in `docs/design-references/`, sample it directly via PIL before inferring tuning values from prose anchors. §1 "images win over prose" applies to diagnosis as well as design authority. **The reference must be EXTERNAL** to the implementation chain (a photograph, not a UI mockup that was itself generated against the current tokens) — sampling a downstream artifact creates a circular calibration loop (§10). Tiers 2–3 inferred from prose alone and accumulated drift. Tier 4 measured against a UI mockup and closed a circular loop. Tier 5 measured against the external mood photograph and corrected to the actual anchor.

### Border treatment

Borders in Bridgeable are subtle by default. Structural hierarchy comes from elevation and spacing, not from hard borders. Borders provide definition where needed without dominating.

**Default border usage:**
- Surfaces use `--border-subtle` when a border is needed at all.
- Interactive elements (inputs, dropdowns) use `--border-base` for visible definition.
- `--border-strong` is reserved for content that needs to hold its weight (table column rules, section dividers that carry real structural meaning).
- `--border-brass` is used for focus states and selected states only. Not a general-purpose border.

**Card perimeter: no border.**
Cards in this platform do not carry a discrete perimeter border. Card edges emerge from the composition of (a) **surface lightness + hue lift** (`--surface-elevated` at the warmer-amber hue per §3 dark-mode progression), (b) **shadow halo** (the soft atmospheric shadow that darkens the page surface just outside the card), and (c) **top-edge highlight** in dark mode (the 3px inset catching implied lamplight on the top edge). This three-mechanism stack delivers the "material, not paint" anchor (§1 dark-mode anchor 4) without the line-drawn outline that a perimeter border would imply. A painted outline suggests "this is a drawn shape on a surface"; the composition suggests "this is a material object sitting on another surface."

The canonical reference (`docs/design-references/IMG_6085.jpg` dark, `IMG_6084.jpg` light) shows no visible perimeter border pixel on the card — edge transitions are shadow-halo-mediated, not border-mediated.

**Reconciliation history (April 2026):** Tier-2 (inference-based) added `border border-border-subtle` to the Card primitive, reading §1 anchor 4 prose to mean "apply all three cues including hairline border." Tier-4 (measurement-based) sampled the reference directly and found no perimeter border pixel. Border addition was reverted in Tier 4 for both modes (light and dark).

**Overlay perimeter: no border.**
Dialogs, popovers, dropdown menus, and slide-overs do not carry a perimeter border either. Same rationale as cards: the shadow + surface composition carries the elevation signal; a border would over-specify.

**Where borders DO apply:**
- **Inputs, textareas, select triggers**: need a definite interactable-edge signal. Use `--border-base` (solid, visible); transitions to `--border-brass` on focus.
- **Table column/row rules**: structural dividers inside a table. Use `--border-subtle` for light rules, `--border-base` for column separators that need weight.
- **Focus indicators**: brass focus rings via the `.focus-ring-brass` utility (separate from border; uses `box-shadow` ring composition per Focus states section).
- **Explicit status-bordered callouts**: Alert / StatusPill / Badge status variants may use `border-status-*` colors as part of their status-family expression. These are component-specific, not a general surface-edge rule.
- **Section dividers inside cards**: `border-t border-border-subtle` on CardFooter separates the footer zone from the card body. This is an INTERNAL divider (one line inside a surface), not a perimeter outline.

**What NOT to add borders to:**
- Page backgrounds (the page IS the surface, not an element on a surface).
- Card perimeters (canonical rule above).
- Overlay perimeters (canonical rule above).
- Row items in lists — rely on row padding + horizontal divider `border-b border-border-subtle` where rules are needed.
- Badge/pill primitives — they use `bg-*-muted` color fill; adding a border would conflict with the pill shape's visual weight.
- Buttons — the button has its own chrome (background + text color + shadow on hover). A perimeter border on brass primary would be visually redundant.

**Border radius scale:**

| Token | Value | Use |
|---|---|---|
| `radius-none` | 0 | Flush elements, edge-to-edge content. |
| `radius-sm` | 4px | Badges, small pills, compact inline elements. |
| `radius-base` | 6px | Buttons, inputs, compact cards. **Default.** |
| `radius-md` | 8px | Standard cards, dropdown menus, popovers. |
| `radius-lg` | 12px | Large cards, modals, signature surfaces. |
| `radius-xl` | 16px | Hero surfaces, marketing cards. |
| `radius-full` | 9999px | Circular elements, fully-rounded pills. |

**Rationale:** The scale is conservative. Aggressive rounding (20px+) reads as playful or consumer-app; the cocktail lounge and Mediterranean garden moods both favor moderate, considered rounding. 6px as the default produces buttons and inputs that feel substantial without being either squared (too formal) or pill-shaped (too casual).

### Focus states

Focus indicators must be visible, substantial, and on-brand. They use brass for recognition — the focus ring is *the* brass signal for "this element has your attention."

**Focus ring specification:**
- **Color:** `--accent-brass` with 40% opacity for the ring itself.
- **Width:** 3px outside the element.
- **Offset:** 2px from the element edge.
- **Composition:** `box-shadow: 0 0 0 2px var(--surface-base), 0 0 0 5px color-mix(in oklch, var(--accent-brass) 40%, transparent)`. The first shadow creates a gap between the element and the ring; the second shadow is the ring itself.
- **Radius:** Matches the element's own radius.
- **Transition:** Fades in with `duration-quick` and `ease-settle`.

**Rule:** Every focusable element must have a visible focus state. Removing focus rings for aesthetic reasons is forbidden. A focus state may be styled to match the component (e.g., a button's focus ring might be slightly tighter), but it must always be visible and must always use brass.

**Rationale:** Focus states are an accessibility floor (WCAG 2.4.7) and also a platform signal — the brass focus ring is the platform saying "I see you." Generic outline focus rings read as browser-default; branded focus rings read as "this app was designed."

### Motion timing scale

Bridgeable uses five named durations. Sonnet picks a duration by motion type, not by guessing millisecond values.

| Token | Value | Use |
|---|---|---|
| `duration-instant` | 100ms | Micro-transitions — color changes, small opacity shifts, immediate hover feedback. |
| `duration-quick` | 200ms | Standard hovers, focus ring appearance, small UI reactions. |
| `duration-settle` | 300ms | Dropdowns opening, tooltips, small overlays, most UI transitions. |
| `duration-arrive` | 400ms | Modals entering, side panels opening, major element appearances. |
| `duration-considered` | 600ms | Page transitions, significant state changes, dashboard widget reflows. |

**Mode parity:** Light and dark mode use the same duration scale. Section 1 described dark mode as "slightly slower" in character; this is achieved through easing curves and visual weight (larger shadows, more material presence), not through longer durations. Durations under ~50ms different are below perceptual threshold, and varying them per mode adds implementation complexity without felt benefit.

**Duration selection logic for Sonnet:**
- Is this a hover, focus, or tiny state change? → `duration-quick` (or `duration-instant` for especially small changes)
- Is this a dropdown, tooltip, or small overlay? → `duration-settle`
- Is this a modal, side panel, or large appearance? → `duration-arrive`
- Is this a page transition or significant layout shift? → `duration-considered`

### Easing curves

Bridgeable uses two named easing curves. Both are ease-out-dominant, producing the "settles rather than snaps" feel from Section 1.

| Token | Curve | Use |
|---|---|---|
| `ease-settle` | `cubic-bezier(0.2, 0, 0.1, 1)` | Entrances, arrivals, appearances. Aggressive deceleration at the end — things *arrive* rather than fade in. |
| `ease-gentle` | `cubic-bezier(0.4, 0, 0.4, 1)` | Exits, dismissals, fades. More symmetric, less dramatic. |

**Rule:** Entrances use `ease-settle`; exits use `ease-gentle`. Do not use browser-default `ease` or linear transitions. Those read as unstyled and break the considered-motion character of the platform.

**Rationale:** The two-curve system mirrors the real-world asymmetry of how things enter and leave attention. Something arriving in your field of view demands notice; something leaving should recede quietly. Using the same curve for both produces motion that feels mechanical; distinguishing them produces motion that feels considered.

### Specific motion patterns

Common UI transitions specify both duration and easing. These are the defaults; deviation requires justification.

| Pattern | Duration | Easing | Notes |
|---|---|---|---|
| Hover color change | `duration-quick` | `ease-settle` | |
| Focus ring appearance | `duration-quick` | `ease-settle` | |
| Button press feedback | `duration-instant` | `ease-settle` | Slight scale down (e.g., `scale-97`) on active. |
| Dropdown opening | `duration-settle` | `ease-settle` | Opacity fade + slight Y translate (4px). |
| Dropdown closing | `duration-quick` | `ease-gentle` | Opacity fade only. |
| Tooltip appearance | `duration-settle` | `ease-settle` | With a short delay (150ms) before triggering. |
| Modal entering | `duration-arrive` | `ease-settle` | Opacity fade + slight scale (0.98 → 1.0). Backdrop fades with same duration. |
| Modal exiting | `duration-settle` | `ease-gentle` | Opacity fade only. |
| Side panel opening | `duration-arrive` | `ease-settle` | X translate from edge. |
| Side panel closing | `duration-settle` | `ease-gentle` | X translate back to edge. |
| Toast appearance | `duration-settle` | `ease-settle` | Opacity fade + slight Y translate. |
| Page transition | `duration-considered` | `ease-settle` | Content fades; new content fades in. |

**Button press note:** The slight scale-down on active (`scale-97`, roughly 97% of original size) provides tactile feedback without being cartoonish. This is the one place the "material, not paint" anchor shows up in motion — buttons feel like they can be pressed.

**Tooltip delay note:** The 150ms delay before tooltips appear prevents "drive-by tooltips" when the user's cursor transits across elements. Without the delay, tooltips flash on and off during normal mouse movement.

### Reduced motion

Per accessibility requirements (see Section 8), the system respects `prefers-reduced-motion: reduce`.

**Rule:** When reduced motion is requested, all duration tokens collapse to `duration-instant` (100ms) or zero, and translate/scale animations are removed. Opacity fades are retained because they do not cause motion sickness.

**Implementation:**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 100ms !important;
    transition-duration: 100ms !important;
    scroll-behavior: auto !important;
  }

  /* Remove specific motion-intensive transforms */
  .modal-enter, .panel-enter, .toast-enter {
    transform: none !important;
  }
}
```

Reduced motion does not remove all transitions — it removes motion-intensive ones (translate, scale, slide). Color changes and opacity fades remain, because they are not motion in the vestibular sense.

### Surface composition patterns

Common surface patterns combine elevation, shadow, border, radius, and (in dark mode) top-edge highlight. These are the canonical compositions.

**Card (level 1):**
```css
background: var(--surface-elevated);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-1);
padding: var(--space-6);
```

**Modal (level 2):**
```css
background: var(--surface-raised);
border-radius: var(--radius-lg);
box-shadow: var(--shadow-level-2);
padding: var(--space-6);
max-width: var(--max-w-form);
```

**Dropdown / popover (level 2):**
```css
background: var(--surface-raised);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-2);
padding: var(--space-2);
border: 1px solid var(--border-subtle); /* Subtle definition at small sizes where shadow alone isn't enough */
```

**Toast (level 3):**
```css
background: var(--surface-raised);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-3);
padding: var(--space-4) var(--space-5);
```

**Floating command bar (level 3):**
```css
background: var(--surface-raised);
border-radius: var(--radius-lg);
box-shadow: var(--shadow-level-3);
border: 1px solid var(--border-brass); /* Brass edge signals primary interaction surface */
padding: var(--space-4);
```

### Tooltip patterns

Tooltips are labels on hover and accessible names for assistive tech (`aria-label`). They are not secondary text, not tutorials, and not replacements for visible labels. Keep them short — under 10 words is ideal.

**Describe state, not action, when state matters.** Toggle-like elements with a meaningful active state should carry state-aware labels:

- Active: `"Active: {name}"` or `"Currently viewing {name}"` — describes what the user sees
- Inactive: `"Switch to {name}"` or `"Open {name}"` — describes the action a click would take

The anti-pattern: a toggle with the same tooltip on every state. Example: a DotNav dot labeled `"Switch to Operations"` when Operations is already the active space. The label is a misdirection — it promises an action that either doesn't fire (user is already there) or does nothing visible.

This pattern applies to: space switchers, tab selectors, sidebar navigation items, toggle buttons, mode toggles. It does NOT need to apply to links that navigate to new contexts (a "Customers" nav link can say "Customers" in every state — navigating to a page you're already on is a well-understood no-op).

**Hover vs. click vs. focus.** Tooltips appear on hover AND focus (WCAG 2.2 requires focus visibility). They must not require hover to read — screen readers already have `aria-label`. The visible tooltip is a bonus for pointer users.

**Don't duplicate visible labels.** A button with visible "Save" text and a tooltip that says "Save" is noise. Tooltips augment labels that are icons, truncated, or elided for density.

### Anti-patterns

- **Hard drop shadows** (`box-shadow: 2px 2px 0 black`). These read as "brutalist web design" or "MS Paint." Bridgeable shadows are soft, warm, atmospheric.
- **Neutral gray shadows.** Violates the warm-hue family rule from Section 2. All shadows are warm-tinted.
- **Dark mode without shadows.** Violates the "shadows persist in dark mode" rule. Dark mode UI without shadows reads as flat institutional software, not as cozy lounge.
- **Over-rounded surfaces.** Radius above 16px on standard UI elements reads as consumer-app or playful. Bridgeable favors moderate, considered rounding.
- **Sharp 90° corners on interactive elements.** Buttons and inputs with no rounding read as utilitarian or cold. Even a 4px radius signals considered design.
- **Motion with `ease` or `linear` timing.** These read as browser-default. The platform uses `ease-settle` or `ease-gentle`.
- **Excessive motion.** Every UI change animated, every hover with a transition, every element bouncing on load. Bridgeable's motion is considered — used where it aids comprehension, absent where it would be noise.
- **Removing focus rings.** Never. Focus rings are an accessibility requirement and a platform signal.
- **Elevation inversions.** A card with a shadow sitting on top of a modal (which should have a larger shadow). The monotonic elevation rule prevents this.

## Section 7 — Iconography & Imagery

Icons and imagery are the visual vocabulary of the platform beyond type and color. They communicate actions, entities, and status without language. This section specifies the icon library, how icons are used, and how images are treated.

### Icon library

Bridgeable uses **Lucide** for all UI icons. No other icon library is used anywhere in the platform.

**Rationale:** Lucide's 2px-stroke rounded-line character sits naturally against the warm palette and the Plex letterforms — both carry that "considered, slightly warm, engineered" quality. The ~1,500-icon set is wide enough that Sonnet can find a specific icon for a specific concept (vault, cemetery, workflow, tenant, product line) rather than forcing generic substitutes. Using a single library across the entire platform enforces visual consistency without effort; mixing libraries produces visible inconsistency that takes real work to notice and real time to fix.

**Implementation:**
- React: `import { IconName } from "lucide-react"` — version `0.383.0` is already available in the artifact environment.
- Non-React contexts: `lucide` for vanilla JS, `lucide-static` for static SVGs.
- Do not import individual icons from other libraries for "one-off" needs. If Lucide does not have an icon for a specific concept, the right answer is to adapt or omit — not to reach for another library.

### Icon sizing scale

Icons use a named size scale keyed to their surrounding context. Sonnet picks by context, not by guessing pixel values.

| Token | Size | Stroke | Use |
|---|---|---|---|
| `icon-xs` | 12px | 1.5px | Micro labels, inline indicators, tight badge contexts. |
| `icon-sm` | 14px | 1.5px | Icons inside dense UI (table rows, list items, form field adornments). |
| `icon-base` | 16px | 2px | **Default.** Icons in buttons, navigation items, standard UI. |
| `icon-md` | 20px | 2px | Primary action icons, card header icons, section headers. |
| `icon-lg` | 24px | 2px | Hero icons, empty-state illustrations, prominent UI icons. |
| `icon-xl` | 32px | 2px | Large feature icons, onboarding, major status indicators. |
| `icon-2xl` | 48px | 2px | Signature moments — major empty states, hero illustrations. |

**Stroke width rules:**
- Icons at 16px and above use Lucide's default 2px stroke.
- Icons at 14px and below use 1.5px stroke — Lucide's default 2px stroke looks too heavy at small sizes.
- Set via `strokeWidth` prop: `<IconName size={14} strokeWidth={1.5} />`

### Icon color

Icons inherit color from their context via `currentColor` (Lucide's default behavior). This means icons automatically adopt the appropriate content color from Section 3 based on where they sit.

**Default icon colors:**
- Icons in body text or default UI → `content-base`
- Icons in muted contexts (captions, helper text) → `content-muted`
- Icons in primary actions (brass buttons) → `content-on-brass`
- Icons in brass-accented contexts (selected states, focused items) → `accent-brass`
- Icons communicating status → the corresponding status color (`status-error`, `status-warning`, `status-success`, `status-info`)

**Rule:** Icons do not use decorative colors. An icon is colored by what it *means*, not by what would look pretty. A status icon is colored by status semantics; a navigation icon is colored by whether the item is active; a brass icon indicates primary action or active focus. Arbitrary color choice on icons produces the "which icon is colored and why" confusion that degrades UI legibility.

### Icon usage patterns

**Buttons:** Icons may appear alone (icon-only buttons) or paired with text. When paired, the icon sits before the text with `space-2` (8px) gap.

```jsx
<Button>
  <Check size={16} strokeWidth={2} />
  Approve All
</Button>
```

**Navigation items:** Icons appear before labels with `space-3` (12px) gap. Active navigation items use brass color for both icon and label; inactive items use `content-muted` for the icon and `content-base` for the label.

**Form field adornments:** Icons inside input fields (search icons, status indicators, unit markers) use `icon-sm` (14px) and `content-muted`. They sit with `space-3` (12px) padding from the field edge.

**Status indicators:** Status icons appear before status labels with `space-2` gap. Icon color matches the status (`status-error`, etc); label uses a darker shade of the same hue for contrast.

**Decorative icons in prose:** Generally avoided. Icons should earn their place by communicating something language doesn't. Pure decoration fights deliberate restraint.

### Icon selection principles

- **Prefer recognizable over clever.** A ✉ icon for messaging is better than a novel metaphor, even if the novel metaphor is more interesting. Users should not have to decode icons.
- **One concept per icon; one icon per concept.** A "trash" icon means "delete" — not also "archive" or "clear." Using the same icon for multiple concepts produces ambiguity; using different icons for the same concept produces inconsistency.
- **Prefer action icons to noun icons for buttons.** A button labeled "Save" with a disk icon is worse than a button labeled "Save" with a check icon, because the check communicates completion (the *result* of saving) while the disk communicates storage medium (an implementation detail users don't care about).
- **Avoid icon-only buttons except for universally-recognized actions.** Close (×), menu (☰), search (🔍), settings (⚙) are safe. "Approve" and "Reject" should have labels. When in doubt, label the button; icons alone force users to guess.

### Platform-specific icon mappings

For recurring Bridgeable concepts, use these specific Lucide icons to avoid drift across the platform:

| Concept | Icon | Rationale |
|---|---|---|
| Vault (burial) | `Box` | Evokes the physical object; used consistently for vault-related features. |
| Case (funeral home) | `FileText` | A case is fundamentally a document-rooted entity. |
| Cemetery | `Trees` | Evokes the physical location; more specific than a generic "location" pin. |
| Tenant | `Building2` | Organizations as buildings; consistent with industry conventions. |
| Workflow step | `Circle` (completed: `CheckCircle2`, active: `Circle` with brass ring, pending: `Circle` muted) | The step progression pattern. |
| Approve / confirm | `Check` | Universal completion indicator. |
| Reject / cancel | `X` | Universal negation. |
| Edit | `PenLine` | More specific than a generic pencil; signals content editing. |
| Delete | `Trash2` | Lucide's trash icon; the "2" suffix is the updated glyph. |
| Settings | `Settings` | Standard cog. |
| Search | `Search` | Standard magnifier. |
| Command bar | `Command` | The "⌘" glyph; reinforces the keyboard-first Cmd+K affordance. |
| User / person | `User` | Individual person. |
| Team / multiple users | `Users` | Group of people. |
| Time / schedule | `Clock` | Time-specific events. |
| Calendar | `Calendar` | Date-specific or calendar-view contexts. |
| Notification | `Bell` | Standard bell. |
| Error / alert | `AlertCircle` | Status-error contexts. |
| Warning | `AlertTriangle` | Status-warning contexts. |
| Success | `CheckCircle2` | Status-success contexts. |
| Info | `Info` | Status-info contexts. |
| External link | `ExternalLink` | Links that leave the platform or open a new surface. |
| Add / new | `Plus` | Creation actions. |
| Close | `X` | Close modal, dismiss panel. |
| Menu | `Menu` | Hamburger for mobile or collapsed navigation. |
| Arrow forward | `ArrowRight` | Proceed, continue, advance step. |
| Arrow back | `ArrowLeft` | Return, previous step. |
| Chevron (expand/collapse) | `ChevronRight`, `ChevronDown` | Collapsible sections, accordion indicators. |

This mapping is not exhaustive. When a new concept needs an icon, pick from Lucide, document the mapping in this table (via update to this document), and use it consistently across the platform.

### Imagery

Bridgeable uses real imagery sparingly. The platform is utility software; imagery appears in specific contexts, not as decoration.

**Where imagery appears:**
- **User/contact avatars.** Person photos, initials fallback.
- **Tenant logos.** Organization logos in tenant-specific contexts (funeral home branding on family portals, plant branding on manufacturing dashboards).
- **Product photography.** Vault product images, precast product images, Redi-Rock block images — for resale catalogs, product configurators, and quote generation.
- **Empty states.** Illustrated empty states where a concept is easier to communicate visually than linguistically.
- **Marketing and external surfaces.** Family-facing portals, public websites, onboarding flows.

**Where imagery does not appear:**
- Decorative photography on admin UI pages. No "office workers smiling at laptops" stock photography anywhere in the platform.
- Hero banners on internal pages. The admin UI has no need for hero imagery.
- Illustrated headers on dashboards or hubs. The warmth of the palette and typography is enough atmosphere; illustrations would fight deliberate restraint.

### Image treatment

**Avatars:**
- Square source images rendered as circles (`radius-full`).
- Fallback: initials on a `accent-brass-muted` background with `content-on-brass` text color.
- Sizes: `avatar-sm` (24px), `avatar-base` (32px), `avatar-md` (40px), `avatar-lg` (56px), `avatar-xl` (80px).

**Tenant logos:**
- Preserve aspect ratio; do not crop or distort.
- Contained within a fixed bounding box; whitespace within the box is the tenant's responsibility in their logo asset.
- For tenants without a logo asset, use the tenant name in Plex Sans Medium as a wordmark placeholder.

**Product photography:**
- Photographed against neutral backgrounds (warm off-white or transparent, never stark white or gray).
- Rendered at product catalog contexts with `radius-md` rounded corners.
- Ratio-preserving; never cropped to square except in grid views where consistency requires it.

**Empty-state illustrations:**
- Use Lucide icons at `icon-2xl` (48px) or larger, centered, in `content-muted` color, rather than custom illustrations.
- The illustration is the icon plus the accompanying copy — not a separate drawn image. This keeps the visual language of empty states aligned with the rest of the platform.

**Rationale for icon-only empty states:** Custom illustrations introduce a new visual style that has to be maintained alongside Lucide, Plex, and the color system. Unless Bridgeable commits to a specific illustration style (which is a major design undertaking), icon-based empty states provide appropriate visual presence without opening a new surface-area of design decisions. If at some future point the platform commits to an illustration style, that is an addition to this document, not a side-decision.

### Image quality and loading

- Product and marketing imagery loads at 2x pixel density (retina) with appropriate srcsets for smaller viewports.
- All `<img>` elements include meaningful `alt` text; decorative images use `alt=""` explicitly.
- Images above the fold use `loading="eager"`; images below use `loading="lazy"`.
- Avatars have a placeholder fallback that renders immediately while the image loads (initials on brass-muted background) — never blank circles.

### Anti-patterns

- **Mixing icon libraries.** Under no circumstances. Lucide for everything.
- **Colored icons for decoration.** Icons are colored by semantic meaning. A "blue trash icon" because blue looks nice is wrong; a "status-error trash icon" because deletion is destructive is correct.
- **Stock photography on admin UI.** Generic smiling-office-worker imagery is never appropriate for Bridgeable admin surfaces.
- **Novel icon metaphors for standard actions.** "Save" is a check or a disk. "Delete" is a trash can. Novel metaphors for standard actions produce guessing games.
- **Icon-only buttons for non-universal actions.** Icon-only "Approve" buttons are ambiguous. Approve, reject, delete, archive all require labels. Only universal actions (close, menu, search) are safe as icon-only.
- **Oversized decorative icons.** Icons at 64px+ used purely for decoration on a standard page read as consumer-app. The 48px `icon-2xl` is the ceiling for most UI; larger sizes are reserved for true signature moments.
- **Inconsistent icon sizes within a single UI region.** A list of items where each has an icon should use the same icon size across all items, even when the items have different content lengths.

## Section 8 — Accessibility Floor

Accessibility is not a post-hoc audit concern for Bridgeable. It is a baseline quality that shipped UI must meet. This section specifies the minimum requirements — the *floor* — below which no shipped component is allowed to sit. Individual components may exceed these requirements; none may fall below them.

This section is mechanical synthesis of rules established earlier in the document plus the specific WCAG requirements every UI ships with. Sonnet should read this section as a checklist to verify against during every component build.

### Target: WCAG 2.2 Level AA

Bridgeable targets **WCAG 2.2 Level AA** as its baseline. Specific requirements are called out below; the full WCAG document governs any case not explicitly addressed here.

**Why AA and not AAA:** AAA requirements (e.g., 7:1 contrast for body text, sign-language alternatives for prerecorded video) are appropriate for specific domains (government, healthcare-direct-care) but add cost that does not materially improve usability for Bridgeable's user base. AA is the widely-accepted professional floor for business software. Specific tokens in the system exceed AA and approach AAA where it's cheap to do so (e.g., `content-strong` on `surface-base` is near-AAA in both modes).

### Color contrast

Per Section 3, the content color tokens were designed with contrast ratios in mind. The specific requirements:

**Body text:**
- `content-base` on `surface-base` — must meet 4.5:1 (AA body text)
- `content-base` on `surface-elevated` — must meet 4.5:1
- `content-base` on `accent-brass` — addressed by the dedicated `content-on-brass` token

**Large text (18pt+ or 14pt+ bold):**
- `content-muted` on `surface-base` — must meet 3:1 (AA large text)

**UI components and graphical objects:**
- Interactive element boundaries (button borders, input borders, focus indicators) — must meet 3:1 against adjacent colors (AA non-text contrast)
- Icon colors that convey meaning — must meet 3:1 against their background

**Status colors:**
- Status colors used for text or icons must meet 4.5:1 (text) or 3:1 (non-text) against their backgrounds. Status `muted` variants are backgrounds, so the pairing of status foreground color on status-muted background must itself meet contrast requirements.

**Rule:** Any proposed color pairing must be verified against these ratios before shipping. Sonnet verifies using a contrast-checking tool (the oklch values make this straightforward via any WCAG contrast calculator) and documents the verified ratio in the component's implementation notes.

**What not to rely on:** Color alone to communicate state. A red status label must also include a word ("Error") or an icon (`AlertCircle`). A required form field must not be marked only by red asterisk color — it needs a text marker. This is WCAG 1.4.1 (Use of Color) and it applies everywhere in the platform.

### Focus indication

Per Section 6, every focusable element has a visible focus state using the brass focus ring. This is the single most important accessibility rule in the platform and the one most often violated in SaaS UI.

**Requirements:**
- Every interactive element (buttons, links, inputs, checkboxes, radios, custom controls) must have a visible focus state.
- The focus state must meet 3:1 contrast against the adjacent background.
- The focus ring must not be removed via `outline: none` without providing an equivalent replacement (which Bridgeable's brass focus ring satisfies).
- Focus state must be visible via keyboard navigation, not just mouse clicks.
- Focus moves in a logical order — roughly top-to-bottom, left-to-right for LTR content — and never traps the user in a sub-region without an escape path.

**Rule:** If Sonnet writes `outline: none` in any component, the very next rules must define the brass focus ring. Removing focus rings for aesthetics is a violation regardless of how the design is styled otherwise.

### Keyboard navigation

Every workflow in Bridgeable must be completable via keyboard alone. The Command Bar (Cmd+K) is a primary keyboard affordance and should always be reachable without a mouse.

**Keyboard requirements:**
- All interactive elements are focusable via Tab (and reachable by Shift+Tab for reverse order).
- Modals trap focus until dismissed; focus returns to the trigger element on close.
- Dropdown menus respond to Arrow keys for navigation and Enter/Space to select.
- Escape dismisses modals, dropdowns, popovers, and tooltips.
- Tab order follows visual order.
- The Command Bar opens with `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux) from anywhere in the app.
- Skip-to-content links are provided on pages with significant navigation chrome.

**Custom interactive elements:** Any custom-built control (e.g., a custom dropdown, a custom date picker) must replicate standard keyboard behavior of its HTML equivalent. A custom dropdown responds to Arrow keys, Home/End, typeahead, and Escape like a native `<select>`. Shortcuts exist; replicating expected behavior is not optional.

### Screen reader support

Bridgeable uses semantic HTML first, ARIA where necessary.

**Requirements:**
- Use semantic HTML elements (`<button>`, `<nav>`, `<main>`, `<header>`, `<article>`, `<section>`, `<label>`) rather than styled `<div>`s.
- All form inputs have associated `<label>` elements (or `aria-label` for cases where a visible label is truly inappropriate).
- Buttons use `<button>`, links use `<a>`. Clickable `<div>`s are forbidden.
- Images have meaningful `alt` text; decorative images use `alt=""` explicitly.
- Icon-only buttons include `aria-label` describing the action.
- Status regions that update dynamically use `aria-live` ("polite" for non-urgent, "assertive" for critical).
- Form validation errors are announced via `aria-describedby` pointing to the error text.
- Modal dialogs use `<dialog>` or `role="dialog"` with `aria-modal="true"` and an `aria-labelledby` pointing to the dialog title.

**ARIA philosophy:** The first rule of ARIA is not to use ARIA. Prefer semantic HTML. Use ARIA only when semantic HTML cannot express what's needed (e.g., for custom controls or dynamic regions). Incorrect ARIA is worse than no ARIA.

### Reduced motion

Per Section 6, the system respects `prefers-reduced-motion: reduce`. This is repeated here because it is an accessibility floor requirement, not just a motion design preference.

**Requirements:**
- Motion-intensive animations (translate, scale, slide, rotate) are removed when reduced motion is requested.
- Opacity fades and color transitions are retained — they do not cause vestibular issues.
- Parallax scrolling, auto-playing video, and autoplay carousels respect reduced motion and stop automatic playback.
- Durations collapse to `duration-instant` (100ms) or zero.

### Touch target size

Per WCAG 2.2 (Target Size Level AA = 24×24 CSS pixels):

**Requirements:**
- Interactive targets are at least 24×24 CSS pixels.
- Preferred minimum: 44×44 CSS pixels (Apple HIG guideline, broadly adopted).
- Buttons with `py-2.5 px-5` padding (per Section 5) exceed both thresholds for any text label.
- Icon-only buttons must be explicitly sized to meet the minimum — e.g., a 16px icon in a button with enough padding that the button itself is at least 44×44 (realistically 16px icon + 12px padding each side = 40px, which rounds acceptably close; use 14px padding to land solidly at 44).

**Rule:** Any interactive element smaller than 24×24 CSS pixels is a violation. Targets crowded close together need at least 8px of spacing between them to avoid accidental activation.

### Form accessibility

Forms are particularly accessibility-sensitive. Bridgeable forms meet these requirements:

- Every input has a visible, persistent label (not placeholder-as-label).
- Labels are clickable and focus the associated input (via `<label>` element).
- Required fields are indicated with both a visible marker (e.g., asterisk) and `required` / `aria-required="true"` attributes.
- Error messages are associated with inputs via `aria-describedby` and announced on submit (not on every keystroke, which is noisy for screen readers).
- Error messages explain what's wrong and what to do, not just "Invalid." (e.g., "Email must contain @ and a domain" rather than "Invalid email.")
- Field-level validation errors appear adjacent to the field (below it) with a clear visual indicator (status-error color + `AlertCircle` icon) and associated text.
- Fieldsets group related fields (address fields, date components) with a `<legend>` describing the group.
- Autocomplete attributes are used for common fields (`autocomplete="email"`, `autocomplete="given-name"`, etc.) so password managers and browser autofill work correctly.

### Responsive and zoom support

- The platform functions correctly at 200% browser zoom (WCAG 1.4.4 Resize Text).
- Text reflows rather than truncating or horizontal-scrolling at 200% zoom.
- The platform is usable at viewports down to 320px wide for the explicitly mobile-scoped surfaces (per Section 5).
- No fixed-height text containers that prevent text from reflowing.

### Language and internationalization

- The root `<html>` element declares the content language (`<html lang="en">`).
- Alternate-language content uses `lang` attributes on the containing element.
- Bridgeable does not currently support internationalization, but UI strings are structured to allow future localization (strings in a translation table, not hardcoded in components).
- RTL (right-to-left) language support is deferred. When added, layouts will flip with CSS logical properties (`margin-inline-start` rather than `margin-left`).

### Testing and verification

Every shipped component is verified against:

1. **Automated contrast checking** — all color pairings meet required ratios.
2. **Keyboard-only navigation** — the component is fully usable without a mouse.
3. **Screen reader testing** — VoiceOver (macOS), NVDA (Windows), or equivalent announces the component correctly.
4. **Focus visibility** — the brass focus ring appears on every focusable element.
5. **Reduced motion** — component degrades correctly when `prefers-reduced-motion: reduce` is set.
6. **Zoom test** — component functions at 200% browser zoom.

**Rule:** Sonnet treats this as a shipping gate. A component that fails any of the six checks is not ready to ship, regardless of visual polish.

### Anti-patterns

- **Removing focus rings** (`outline: none` without replacement). The single most common accessibility failure. Forbidden.
- **Placeholder-as-label forms.** The placeholder disappears when the user types, leaving no indication of what the field is. Use visible labels.
- **Color-only status indication.** Status communicated purely by color (e.g., a red border around a field) fails users who can't distinguish that color and screen reader users. Always pair color with text or icon.
- **Clickable divs.** `<div onClick={...}>` is not a button. Use `<button>`.
- **Icon-only buttons without `aria-label`.** The visual icon doesn't exist for screen readers.
- **Auto-playing animations without pause.** Violates WCAG 2.2.2. All motion that plays for longer than 5 seconds must have a pause control.
- **Disabling zoom** (`<meta name="viewport" content="user-scalable=no">`). Forbidden. Users must be able to zoom.
- **Tab traps without escape.** A modal or overlay that takes focus but has no way to dismiss via keyboard traps screen reader and keyboard users.

## Section 9 — Implementation

This section translates everything above into the concrete code structure Sonnet uses to implement the design language. The goal is that Sonnet can read this section and immediately set up or modify the design system without needing to re-derive anything from earlier sections.

### Technology stack

The Bridgeable design system is implemented using:

- **CSS custom properties (CSS variables)** as the primary token mechanism. All tokens from Section 3 are defined as CSS variables at `:root` and overridden for `[data-mode="dark"]`.
- **Tailwind CSS** as the utility framework. Tailwind config consumes the CSS variables so Tailwind classes resolve to design tokens.
- **PostCSS** for CSS processing.
- **`@fontsource`** packages for self-hosted Plex fonts.
- **`lucide-react`** for icons.

No CSS-in-JS libraries (styled-components, emotion). Tailwind + CSS variables handles all styling.

### File structure

Design system files live under `/app/styles/` in the Bridgeable repo:

```
/app/styles/
├── tokens.css          # All CSS custom properties (Section 3)
├── base.css            # Reset, body defaults, Plex loading
├── fonts.css           # @fontsource imports, font-face declarations
├── utilities.css       # Custom utility classes beyond Tailwind
└── globals.css         # Entry point that imports the above + Tailwind
```

**Import order in `globals.css`:**

```css
@import "./fonts.css";
@import "./tokens.css";
@import "./base.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

@import "./utilities.css";
```

Tokens load before Tailwind base so Tailwind can reference them in the config. Custom utilities load after Tailwind utilities so they can override or extend them.

### Mode switching

Light mode is the default. Dark mode is activated by setting `data-mode="dark"` on the `<html>` element.

**CSS structure:**

```css
:root {
  /* Light mode tokens (defaults) */
  --surface-base: oklch(0.94 0.030 82);
  /* ... all light tokens ... */
}

[data-mode="dark"] {
  /* Dark mode overrides */
  --surface-base: oklch(0.16 0.012 65);
  /* ... all dark tokens ... */
}
```

**Mode switching logic (React):**

```jsx
// In the root layout component
function setMode(mode) {
  document.documentElement.setAttribute('data-mode', mode);
  localStorage.setItem('bridgeable-mode', mode);
}

// On initial load, before any component renders
const savedMode = localStorage.getItem('bridgeable-mode');
if (savedMode) {
  document.documentElement.setAttribute('data-mode', savedMode);
} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.documentElement.setAttribute('data-mode', 'dark');
}
```

**Flash-of-wrong-mode prevention:** The mode attribute must be set before React hydration to prevent a flash of light mode when dark is the user's preference. Use a synchronous inline `<script>` in the document head that reads localStorage and sets `data-mode` before any CSS is applied.

**User-facing mode toggle (Nav Bar Completion, April 2026):** The visible UI control is a Sun/Moon button rendered in the AppLayout top header (`components/layout/ModeToggle.tsx`), mounted immediately before the `NotificationDropdown`. The icon represents the *destination* state, not the current state — in light mode, the button shows `<Moon />` (click to go dark); in dark mode, `<Sun />` (click to go light). This matches the GitHub / Linear / Vercel convention and the common user intuition that a button icon signals what will happen, not what is already happening.

Accessibility rules for the toggle:
- `aria-label` describes the *action* ("Switch to dark mode"), not the state ("Dark mode: off"). Per WCAG recommendation for toggle buttons.
- `aria-pressed` reflects the *current* toggle state (`true` when dark, `false` when light). Screen readers announce both the available action and the current state.
- `focus-ring-brass` utility for keyboard focus (see Section 6 focus-state spec).

Runtime wiring: the toggle consumes `useMode()` from `lib/theme-mode.ts`, which returns `{mode, toggle}` and delegates to `useThemeMode` (the underlying `[mode, setter]` tuple). Shared state — no duplication.

```jsx
// ModeToggle usage (simplified):
import { useMode } from "@/lib/theme-mode";

function ModeToggle() {
  const { mode, toggle } = useMode();
  const isDark = mode === "dark";
  const Icon = isDark ? Sun : Moon;
  const next = isDark ? "light" : "dark";
  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} mode`}
      aria-pressed={isDark}
      title={`Switch to ${next} mode`}
      className="... focus-ring-brass"
    >
      <Icon aria-hidden="true" />
    </button>
  );
}
```

Once the toggle ships, **all aesthetic verification for subsequent sessions must cover both modes**, not just the mode currently in focus. The toggle is the primary channel users have to experience both moods; bugs that only surface in one mode are disproportionately impactful.

### Full `tokens.css`

The complete token definitions from Section 3, plus the tokens introduced in Sections 4–7:

```css
:root {
  /* ============ COLOR TOKENS ============ */

  /* Surfaces */
  --surface-base: oklch(0.94 0.030 82);
  --surface-elevated: oklch(0.965 0.014 82);
  --surface-raised: oklch(0.985 0.010 82);
  --surface-sunken: oklch(0.91 0.020 82);

  /* Content */
  --content-strong: oklch(0.22 0.015 70);
  --content-base: oklch(0.30 0.015 70);
  --content-muted: oklch(0.48 0.014 70);
  --content-subtle: oklch(0.62 0.012 70);
  --content-on-brass: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.88 0.012 80 / 0.6);
  --border-base: oklch(0.82 0.015 78 / 0.8);
  --border-strong: oklch(0.70 0.020 76);
  --border-brass: oklch(0.66 0.12 73 / 0.7);

  /* Shadows */
  --shadow-color-subtle: oklch(0.40 0.045 78 / 0.06);
  --shadow-color-base: oklch(0.40 0.045 78 / 0.10);
  --shadow-color-strong: oklch(0.37 0.050 75 / 0.16);

  /* Accents */
  --accent-brass: oklch(0.66 0.12 73);
  --accent-brass-hover: oklch(0.62 0.13 73);
  --accent-brass-active: oklch(0.58 0.13 73);
  --accent-brass-muted: oklch(0.85 0.05 73 / 0.8);
  --accent-brass-subtle: oklch(0.92 0.025 73 / 0.6);

  /* Status */
  --status-error: oklch(0.55 0.18 25);
  --status-error-muted: oklch(0.92 0.04 25);
  --status-warning: oklch(0.70 0.14 65);
  --status-warning-muted: oklch(0.94 0.04 65);
  --status-success: oklch(0.58 0.12 135);
  --status-success-muted: oklch(0.93 0.04 135);
  --status-info: oklch(0.55 0.08 225);
  --status-info-muted: oklch(0.93 0.03 225);

  /* ============ ELEVATION SHADOWS ============ */
  --shadow-level-1: 0 2px 8px var(--shadow-color-base);
  --shadow-level-2: 0 8px 24px var(--shadow-color-base), 0 2px 6px var(--shadow-color-subtle);
  --shadow-level-3: 0 16px 40px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base);

  /* ============ TYPOGRAPHY TOKENS ============ */
  --font-sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-serif: "IBM Plex Serif", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  --text-display-lg: 3.052rem;
  --text-display: 2.441rem;
  --text-h1: 1.953rem;
  --text-h2: 1.563rem;
  --text-h3: 1.25rem;
  --text-h4: 1.125rem;
  --text-body: 1rem;
  --text-body-sm: 0.875rem;
  --text-caption: 0.75rem;
  --text-micro: 0.6875rem;

  /* ============ BORDER RADIUS ============ */
  --radius-none: 0;
  --radius-sm: 4px;
  --radius-base: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  /* ============ MOTION ============ */
  --duration-instant: 100ms;
  --duration-quick: 200ms;
  --duration-settle: 300ms;
  --duration-arrive: 400ms;
  --duration-considered: 600ms;

  --ease-settle: cubic-bezier(0.2, 0, 0.1, 1);
  --ease-gentle: cubic-bezier(0.4, 0, 0.4, 1);

  /* ============ MAX-WIDTHS ============ */
  --max-w-reading: 34rem;
  --max-w-form: 40rem;
  --max-w-content: 56rem;
  --max-w-wide: 72rem;
  --max-w-dashboard: 96rem;
}

[data-mode="dark"] {
  /* Surfaces — Tier-4 measurement-based correction (April 2026):
     calibrated to IMG_6085.jpg sampled values. Hue progresses with
     elevation (h=59→81→85) per §1 anchor 4 "Material, not paint" —
     this is the second material dimension the prior tokens missed.
     Tier-3's lightness bumps (L=0.22 / L=0.27) reverted to pre-
     Tier-3 values (L=0.20 / L=0.24) which match reference. */
  --surface-base: oklch(0.16 0.010 59);
  --surface-elevated: oklch(0.28 0.014 81);
  --surface-raised: oklch(0.32 0.016 85);
  --surface-sunken: oklch(0.13 0.010 55);

  /* Content */
  --content-strong: oklch(0.96 0.012 80);
  --content-base: oklch(0.90 0.014 75);
  --content-muted: oklch(0.72 0.014 70);
  --content-subtle: oklch(0.55 0.012 68);
  --content-on-brass: oklch(0.18 0.015 60);

  /* Borders */
  --border-subtle: oklch(0.35 0.015 65 / 0.5);
  --border-base: oklch(0.42 0.018 68 / 0.7);
  --border-strong: oklch(0.55 0.025 70);
  --border-brass: oklch(0.70 0.13 73 / 0.7);

  /* Shadows — Tier-4 correction (April 2026):
     --shadow-highlight-top calibrated to reference measurement. */
  --shadow-color-subtle: oklch(0.11 0.020 65 / 0.35);
  --shadow-color-base: oklch(0.09 0.020 65 / 0.45);
  --shadow-color-strong: oklch(0.08 0.020 65 / 0.55);
  --shadow-highlight-top: oklch(0.32 0.010 61 / 0.9);

  /* Accents */
  --accent-brass: oklch(0.70 0.13 73);
  --accent-brass-hover: oklch(0.74 0.13 73);
  --accent-brass-active: oklch(0.78 0.14 73);
  --accent-brass-muted: oklch(0.35 0.06 73 / 0.8);
  --accent-brass-subtle: oklch(0.26 0.04 73 / 0.6);

  /* Status */
  --status-error: oklch(0.68 0.17 25);
  --status-error-muted: oklch(0.28 0.08 25);
  --status-warning: oklch(0.76 0.14 65);
  --status-warning-muted: oklch(0.30 0.07 65);
  --status-success: oklch(0.70 0.13 135);
  --status-success-muted: oklch(0.28 0.06 135);
  --status-info: oklch(0.70 0.09 225);
  --status-info-muted: oklch(0.28 0.05 225);

  /* Dark mode shadows — Tier-2 three-layer composition:
     tight grounding shadow + soft halo + inset top-edge highlight. */
  --shadow-level-1: 0 1px 3px var(--shadow-color-strong), 0 4px 16px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top);
  --shadow-level-2: 0 2px 4px var(--shadow-color-strong), 0 12px 32px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top);
  --shadow-level-3: 0 3px 6px var(--shadow-color-strong), 0 24px 56px var(--shadow-color-strong), 0 8px 20px var(--shadow-color-strong), inset 0 3px 0 var(--shadow-highlight-top);
}
```

### Tailwind configuration

Tailwind is configured to consume the CSS variables. The config extends rather than replaces the default theme, keeping Tailwind's spacing scale (which matches the 4px base from Section 5) while adding semantic tokens.

> **Implementation note — Tailwind v4 vs. v3:** Bridgeable uses **Tailwind v4** via `@tailwindcss/vite`, where theme configuration lives in an `@theme inline { ... }` block inside CSS, not in a separate `tailwind.config.js` file. The JS config example below is illustrative of the semantic tokens Tailwind should expose; the live implementation is in `frontend/src/index.css` (Aesthetic Arc Session 1). Translation rules:
> - `colors.surface.base = 'var(--surface-base)'` → `--color-surface-base: var(--surface-base);`
> - `fontSize['display-lg'] = [size, { lineHeight, fontWeight }]` → three lines: `--text-display-lg: ...;` + `--text-display-lg--line-height: ...;` + `--text-display-lg--font-weight: ...;`
> - `boxShadow['level-1'] = '...'` → `--shadow-level-1: var(--shadow-level-1);`
> - `transitionTimingFunction.settle` → `--ease-settle: var(--ease-settle);`
> - `maxWidth.reading` → `--container-reading: var(--max-w-reading);` (v4's `--container-*` generates `max-w-*` + `@container`)
> - `transitionDuration.quick` → `@utility duration-quick { transition-duration: var(--duration-quick); }` — Tailwind v4's `--duration-*` is NOT an auto-utility namespace, so explicit `@utility` declarations are required.
>
> The v3 JS config below is retained because it's the clearest semantic description of what Tailwind exposes; read it as intent, not as a file to author. See `frontend/src/index.css` + `frontend/src/styles/base.css` for the live mapping.

```js
// tailwind.config.js
import { fontFamily } from 'tailwindcss/defaultTheme';

export default {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['selector', '[data-mode="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: 'var(--surface-base)',
          elevated: 'var(--surface-elevated)',
          raised: 'var(--surface-raised)',
          sunken: 'var(--surface-sunken)',
        },
        content: {
          strong: 'var(--content-strong)',
          base: 'var(--content-base)',
          muted: 'var(--content-muted)',
          subtle: 'var(--content-subtle)',
          'on-brass': 'var(--content-on-brass)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          base: 'var(--border-base)',
          strong: 'var(--border-strong)',
          brass: 'var(--border-brass)',
        },
        brass: {
          DEFAULT: 'var(--accent-brass)',
          hover: 'var(--accent-brass-hover)',
          active: 'var(--accent-brass-active)',
          muted: 'var(--accent-brass-muted)',
          subtle: 'var(--accent-brass-subtle)',
        },
        status: {
          error: 'var(--status-error)',
          'error-muted': 'var(--status-error-muted)',
          warning: 'var(--status-warning)',
          'warning-muted': 'var(--status-warning-muted)',
          success: 'var(--status-success)',
          'success-muted': 'var(--status-success-muted)',
          info: 'var(--status-info)',
          'info-muted': 'var(--status-info-muted)',
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', ...fontFamily.sans],
        serif: ['IBM Plex Serif', ...fontFamily.serif],
        mono: ['IBM Plex Mono', ...fontFamily.mono],
      },
      fontSize: {
        'display-lg': ['var(--text-display-lg)', { lineHeight: '1.1', fontWeight: '500' }],
        'display': ['var(--text-display)', { lineHeight: '1.15', fontWeight: '500' }],
        'h1': ['var(--text-h1)', { lineHeight: '1.2', fontWeight: '500' }],
        'h2': ['var(--text-h2)', { lineHeight: '1.25', fontWeight: '500' }],
        'h3': ['var(--text-h3)', { lineHeight: '1.3', fontWeight: '500' }],
        'h4': ['var(--text-h4)', { lineHeight: '1.35', fontWeight: '500' }],
        'body': ['var(--text-body)', { lineHeight: '1.55' }],
        'body-sm': ['var(--text-body-sm)', { lineHeight: '1.5' }],
        'caption': ['var(--text-caption)', { lineHeight: '1.45' }],
        'micro': ['var(--text-micro)', { lineHeight: '1.4', letterSpacing: '0.01em' }],
      },
      borderRadius: {
        'sm': 'var(--radius-sm)',
        'DEFAULT': 'var(--radius-base)',
        'md': 'var(--radius-md)',
        'lg': 'var(--radius-lg)',
        'xl': 'var(--radius-xl)',
        'full': 'var(--radius-full)',
      },
      boxShadow: {
        'level-1': 'var(--shadow-level-1)',
        'level-2': 'var(--shadow-level-2)',
        'level-3': 'var(--shadow-level-3)',
      },
      transitionDuration: {
        'instant': 'var(--duration-instant)',
        'quick': 'var(--duration-quick)',
        'settle': 'var(--duration-settle)',
        'arrive': 'var(--duration-arrive)',
        'considered': 'var(--duration-considered)',
      },
      transitionTimingFunction: {
        'settle': 'var(--ease-settle)',
        'gentle': 'var(--ease-gentle)',
      },
      maxWidth: {
        'reading': 'var(--max-w-reading)',
        'form': 'var(--max-w-form)',
        'content': 'var(--max-w-content)',
        'wide': 'var(--max-w-wide)',
        'dashboard': 'var(--max-w-dashboard)',
      },
    },
  },
  plugins: [],
};
```

### Font loading

Plex is self-hosted via `@fontsource` packages. The subset-latin variants are used; full Unicode subsets are not needed for Bridgeable's English-only current scope.

**Install:**

```bash
npm install @fontsource/ibm-plex-sans @fontsource/ibm-plex-serif @fontsource/ibm-plex-mono
```

**Import in `fonts.css`:**

```css
/* IBM Plex Sans — 400 (Regular), 500 (Medium), 600 (Semibold) + 400 italic */
@import "@fontsource/ibm-plex-sans/400.css";
@import "@fontsource/ibm-plex-sans/400-italic.css";
@import "@fontsource/ibm-plex-sans/500.css";
@import "@fontsource/ibm-plex-sans/600.css";

/* IBM Plex Serif — 500 (Medium) only; display use */
@import "@fontsource/ibm-plex-serif/500.css";

/* IBM Plex Mono — 400 only */
@import "@fontsource/ibm-plex-mono/400.css";
```

**Preload the most-used weights** via Next.js / framework font preloading or manual `<link rel="preload">` tags. The most-used weights are Plex Sans 400 (body) and 500 (headings).

### `base.css`

Global resets and body defaults:

```css
*, *::before, *::after {
  box-sizing: border-box;
}

html {
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.55;
  color: var(--content-base);
  background: var(--surface-base);
  -webkit-text-size-adjust: 100%;
}

[data-mode="dark"] {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  min-height: 100vh;
}

h1, h2, h3, h4, h5, h6 {
  font-weight: 500;
  color: var(--content-strong);
  margin: 0;
}

p {
  margin: 0;
}

button {
  font-family: inherit;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: var(--duration-instant) !important;
    transition-duration: var(--duration-instant) !important;
    scroll-behavior: auto !important;
  }
}

/* Focus-visible default (components override with the brass ring) */
:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--surface-base),
    0 0 0 5px color-mix(in oklch, var(--accent-brass) 40%, transparent);
  transition: box-shadow var(--duration-quick) var(--ease-settle);
}
```

### Component patterns — code examples

These are canonical implementations of common components. Sonnet uses these as starting points.

**Primary button:**

```jsx
function PrimaryButton({ children, ...props }) {
  return (
    <button
      className="
        inline-flex items-center gap-2
        px-5 py-2.5
        bg-brass hover:bg-brass-hover active:bg-brass-active
        text-content-on-brass
        font-medium text-body-sm
        rounded
        shadow-level-1
        transition-colors duration-quick ease-settle
        active:scale-[0.97] transition-transform
        focus-visible:outline-none
      "
      {...props}
    >
      {children}
    </button>
  );
}
```

**Card (level 1):**

```jsx
function Card({ children, className = '' }) {
  return (
    <div
      className={`
        bg-surface-elevated
        rounded-md
        shadow-level-1
        p-6
        ${className}
      `}
    >
      {children}
    </div>
  );
}
```

**Form input:**

```jsx
function Input({ label, error, id, ...props }) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="text-body-sm font-medium text-content-base"
      >
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className="
          px-4 py-2.5
          bg-surface-raised
          border border-border-base
          rounded
          text-body text-content-strong
          transition-colors duration-quick ease-settle
          focus-visible:outline-none focus-visible:border-brass
        "
        {...props}
      />
      {error && (
        <span
          id={`${inputId}-error`}
          className="flex items-center gap-1.5 text-caption text-status-error"
        >
          <AlertCircle size={14} strokeWidth={1.5} />
          {error}
        </span>
      )}
    </div>
  );
}
```

**Modal:**

```jsx
function Modal({ open, onClose, title, children }) {
  // Focus trap, escape to close, backdrop click to close all handled
  // by Radix UI Dialog or equivalent — not re-implemented per component.

  return (
    <Dialog.Root open={open} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay className="
          fixed inset-0
          bg-black/40
          transition-opacity duration-arrive ease-settle
        " />
        <Dialog.Content className="
          fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
          w-full max-w-form
          bg-surface-raised
          rounded-lg
          shadow-level-2
          p-6
          transition-[opacity,transform] duration-arrive ease-settle
        ">
          <Dialog.Title className="text-h3 font-medium text-content-strong mb-2">
            {title}
          </Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### Utility classes beyond Tailwind

A few patterns warrant custom utilities in `utilities.css`:

```css
@layer utilities {
  /* Reading measure — body prose */
  .prose-reading {
    max-width: var(--max-w-reading);
    font-size: var(--text-body);
    line-height: 1.55;
  }

  /* Tabular numerals for tables and financial displays */
  .tabular {
    font-variant-numeric: tabular-nums;
  }

  /* Elevation utilities */
  .elevated-card {
    background: var(--surface-elevated);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-level-1);
  }

  /* Brass focus ring — explicit utility for custom controls */
  .focus-ring-brass:focus-visible {
    outline: none;
    box-shadow:
      0 0 0 2px var(--surface-base),
      0 0 0 5px color-mix(in oklch, var(--accent-brass) 40%, transparent);
    transition: box-shadow var(--duration-quick) var(--ease-settle);
  }
}
```

### Do / Don't examples

**DO: Use semantic tokens.**
```jsx
<div className="bg-surface-elevated text-content-base">
```

**DON'T: Use raw color values.**
```jsx
<div className="bg-[oklch(0.965_0.014_82)] text-[oklch(0.30_0.015_70)]">
```

**DO: Use the elevation shadow tokens.**
```jsx
<div className="shadow-level-1">
```

**DON'T: Compose shadows manually.**
```jsx
<div className="shadow-[0_2px_8px_rgba(0,0,0,0.1)]">
```

**DO: Use named durations and easings.**
```jsx
<div className="transition-colors duration-quick ease-settle">
```

**DON'T: Hardcode timing.**
```jsx
<div className="transition-colors duration-[180ms] ease-[cubic-bezier(0,0,0.2,1)]">
```

**DO: Use Plex Serif only for gravitas moments.**
```jsx
<h1 className="font-serif text-display">John Michael Smith</h1>
```

**DON'T: Use Plex Serif for UI chrome.**
```jsx
<button className="font-serif">Save</button>
```

**DO: Scale icon stroke with size.**
```jsx
<Check size={14} strokeWidth={1.5} />
<Check size={20} strokeWidth={2} />
```

**DON'T: Use default stroke at small sizes.**
```jsx
<Check size={12} />  {/* Lucide default 2px stroke is too heavy at 12px */}
```

### CI and tooling

Recommended tooling to enforce the design language mechanically:

- **ESLint rule** against arbitrary Tailwind values (e.g., `text-[#123456]`, `p-[17px]`). Forces tokens.
- **Stylelint** to forbid raw hex/rgb/hsl values in CSS files; oklch only.
- **Axe-core** integration tests on rendered components to catch accessibility regressions.
- **Visual regression testing** (Playwright snapshots) to catch unintended visual drift after design system changes.

These are recommendations, not currently enforced. They become increasingly valuable as the codebase grows past the single-developer stage.

## Section 10 — Anti-Patterns

This section consolidates anti-patterns from every prior section into one reference. It is the document's diagnostic layer: when shipped UI feels wrong, this is where to look for what specifically broke.

Anti-patterns are organized by what they break. Each entry names the violation, the specific rule it breaks (with the section it comes from), and why it matters.

### Anti-patterns that break the warm-hue coherence

**Neutral gray backgrounds or shadows.** Violates the warm-hue family rule (Section 2). A single neutral gray element in an otherwise warm platform reads as "out of place" even when no one can articulate why. This is the single most common subtle drift — developers reach for neutral gray by reflex. The fix is always to pull the hue into the 70–95 warm family.

**Pure white or pure black.** Violates anchors 1 in both modes (Section 1). Pure white reads as clinical; pure black reads as void. Both break the material presence the platform depends on. No component should use `#fff`, `#000`, or their oklch equivalents. Light surfaces live in the warm-cream family; dark surfaces live in the warm-charcoal family.

**Blue-gray dark mode.** Violates dark-mode anchor 1 (Section 1) and the warm-family asymmetry rule (Section 2). A blue-gray dark mode reads as "office at night" — cold, institutional, generic. Bridgeable's dark mode is warm — leather, wood, lamplit. If the dark mode reads as cold, the hue has drifted out of the 55–75 range.

**Decorative color for its own sake.** Violates deliberate restraint (Section 1 meta-anchor). A button colored blue because blue looks friendly, an icon colored green because green looks fresh, a background tinted purple because purple looks sophisticated. Every color decision must be justified by what it communicates, not by aesthetic appeal in isolation.

### Anti-patterns that break the brass thread

**Multiple accent colors competing for primary emphasis.** Violates the aged-brass cross-mode rule (Section 2). Brass is *the* primary accent. If another color is competing for primary emphasis — a blue "Save" button next to a brass "Approve" button, for example — one of them is miscast. Brass marks primary action, focus, and emphasis. A secondary accent may exist but it does not compete for primary attention.

**Brass that shifts hue across modes.** Violates the locked brass hue (Section 2). If the light-mode brass and dark-mode brass read as different metals (one more yellow, one more orange), the hue has drifted. Both must sit at hue 73. Only lightness and chroma adjust across modes.

**Brass for active states via hue shift toward orange/copper.** Violates the no-hue-shift active-state rule (Section 2). Active brass in dark mode glows via lightness and chroma. Pushing the hue toward orange produces copper, not glowing brass.

**Brass used decoratively.** Violates deliberate restraint. Brass marks primary action, focus, emphasis, or the brass-muted backgrounds derived from it. Brass sprinkled through a UI for visual warmth — a brass border here, a brass divider there — dilutes the meaning of brass. When brass appears, the eye should go there. Decorative brass stops being signal and becomes noise.

### Anti-patterns that break deliberate restraint

**Density that signals inability to decide what to remove.** Violates the meta-anchor (Section 1) and the density-is-allowed-but-clutter-is-not rule (Section 1). Dense views earn their density by making every element legible and purposeful. Cramming a dashboard full of elements because removing any felt arbitrary produces clutter. When density is necessary, it must be designed; when it's not, it must be removed.

**Decorative flourishes that serve no purpose.** Violates deliberate restraint. Gradients applied to cards for visual interest, subtle patterns in the background, "hero" animations on dashboard load. Every element must justify its presence. If the answer to "why is this here?" is "it looks nice," the element is a violation.

**Generic stock imagery.** Violates deliberate restraint and Section 7's imagery rules. Office workers smiling at laptops, handshakes, generic cityscapes. These read as stock and undermine the "curated, intentional, adult" character the platform depends on. No decorative photography on admin UI.

**Default Bootstrap / Material / Tailwind aesthetics.** Violates the generic-palette anti-rule from Section 2's "Deriving a new color" procedure. Default blue, default gray borders, default shadow stacks from generic libraries produce interfaces that look like every other SaaS platform. The whole point of this design language is that Bridgeable doesn't look generic.

### Anti-patterns that break mood coherence between modes

**Symmetric hues across modes.** Violates the warm-family asymmetry rule (Section 2). If light mode and dark mode use the same hue values for surfaces, dark mode reads as "daylight dimmed" rather than "evening lamplight." Light mode surfaces live at hue 80–92; dark mode surfaces live at hue 55–75. This asymmetry encodes the morning/evening difference.

**Dropping shadows in dark mode.** Violates the "shadows persist in dark mode" principle (Section 2 and Section 6). Dark mode shadows are warm, soft, low-contrast — but they exist. Flat dark UI reads as cold institutional; warm shadowed dark UI reads as intimate lounge.

**Light mode that reads as sterile.** Violates light anchor 1 (Section 1). If the light mode reads as clinical or near-white rather than as warm cream with material presence, the base surface has drifted toward pure white or its chroma is too low. Pull the base back toward the cream linen anchor.

**Material-as-decoration.** Violates the "material, not paint" anchor (Section 1) and the top-edge highlight rule (Section 2). Gradient surfaces applied to every card, glossy reflections on buttons, skeuomorphic textures. Material presence is subtle — it's the inset 1px top-edge highlight on elevated dark-mode surfaces, not a decorative gradient. If a user notices the material effect, it's too strong.

### Anti-patterns that break typography

**Plex Serif used for body text or UI chrome.** Violates Section 4's serif usage rules. Serif is a display face for gravitas moments. Using it for form labels, button text, or extended body prose produces interfaces that look like they're trying hard. The rule: serif only for decedent names, primary titles on high-stakes pages, signature moments.

**Plex Mono for regular numbers.** Violates Section 4. Prices in prose, dates in sentences, percentages in body text read better in Plex Sans with tabular figures. Mono is for alignment-required data (case IDs, timestamps in tables, code).

**Weight-soup.** Violates the three-weight discipline (Section 4). Semibold headings followed by semibold emphasis in body text followed by semibold labels in forms. Every piece of text fighting for attention means no piece of text gets it. Pick one level of emphasis per visual region.

**All-caps paragraphs.** Violates the typography anti-pattern list (Section 4). All-caps is for small labels (eyebrows, section tags). Longer all-caps text reads as shouting and becomes unreadable. Even all-caps headings should be short.

**Decorative italic.** Italic carries semantic meaning (titles of works, foreign terms, genuine emphasis). Italicizing for visual variety weakens the emphasis it's trying to create and produces interfaces that feel fussy.

**Wide reading measures.** Violates the 34rem / 62–72-character rule (Section 4, Section 5). Body text that stretches across the full width of a wide viewport is fatiguing to read. Every prose container has a max-width; no exceptions.

**Mixing non-Plex fonts.** Violates the single-voice principle (Section 4). Adding a third font family because "this heading would look nice in a different serif" breaks the coherence the whole type system depends on.

### Anti-patterns that break spacing and layout

**Off-scale spacing values.** Violates Section 5's 4px-base rule. 13px padding, 22px margin, 18px gap. If the value isn't a multiple of 4, it's wrong, regardless of how it looks.

**Global 12-column grid for non-dashboard pages.** Violates Section 5's layout approach. The 12-column grid is strictly a dashboard-component substrate. Applying it to page layouts produces rigid, form-fits-function UI that fights content-driven layouts.

**Cramped defaults.** Violates the generous-default bias (Section 5) and the "generous breathing room" anchor (Section 1). New components defaulting to the tight end of the spacing scale produce platforms that feel cramped even when spacing values are individually correct. The default is generous; tightening requires deliberate choice.

**Inconsistent max-widths for similar content.** Violates Section 5's max-width token system. Two case detail pages with different max-widths produce platforms that feel inconsistent even when individual pages look fine.

**Hero sections with excessive vertical padding.** Violates the deliberate-restraint meta-anchor. Pages starting with 160px of empty space before any content. `space-24` (96px) is the ceiling for rare signature moments, not a routine choice.

### Anti-patterns that break surface and behavior

**Hard drop shadows.** Violates Section 6's shadow specifications. `box-shadow: 2px 2px 0 black` reads as brutalist or MS Paint. Bridgeable shadows are soft, warm, and atmospheric.

**Over-rounded surfaces.** Violates Section 6's border radius scale. Radius above 16px on standard UI elements reads as consumer-app or playful. Bridgeable favors moderate rounding; 6px is the default.

**Sharp 90-degree corners on interactive elements.** Violates the restraint principle. Even 4px radius signals considered design; raw corners read as utilitarian.

**Browser-default easing.** Violates Section 6's motion rules. `transition: all 0.3s ease` produces generic motion. The platform uses `ease-settle` and `ease-gentle`.

**Excessive motion.** Violates deliberate restraint. Every hover transitioning, every element fading in on scroll, every UI state change animated. Motion is used where it aids comprehension, absent where it would be noise.

**Removing focus rings.** Violates Section 6 and Section 8. The single most common accessibility failure. `outline: none` without an equivalent replacement is forbidden.

**Elevation inversions.** Violates Section 6's monotonic elevation rule. A card with shadow depth greater than the modal it sits under produces incoherent depth perception.

### Anti-patterns that break iconography

**Mixing icon libraries.** Violates Section 7. One library (Lucide) across the entire platform. Under no circumstances is a second library imported "just for this one icon."

**Decorative icon colors.** Violates Section 7. Icons are colored by semantic meaning — status, interactivity, brand role — not by aesthetic preference. A blue trash icon because blue looks nice is wrong.

**Icon-only buttons for non-universal actions.** Violates Section 7 and Section 8. Approve, Reject, Delete, Archive all require labels. Only universal actions (close, menu, search) are safe as icon-only.

**Novel icon metaphors for standard actions.** Violates Section 7. Save is a check. Delete is a trash can. Inventing new metaphors for established actions forces users to guess.

**2px stroke at 12px size.** Violates the stroke-width rules in Section 7. Small icons use 1.5px stroke. Default stroke at small sizes reads as overweight.

**Inconsistent icon sizes within a single region.** Violates Section 7. A list where each item has an icon uses the same icon size across all items.

### Anti-patterns that break accessibility

**Removing focus rings.** Named again because it's the single most common violation. Forbidden. Section 6 and Section 8.

**Placeholder-as-label forms.** Violates Section 8. Placeholders disappear when users type, leaving no indication of what the field is. Use visible labels.

**Color-only status indication.** Violates WCAG 1.4.1 (Section 8). Red border with no text or icon fails users who can't distinguish color and screen reader users. Always pair color with text or icon.

**Clickable divs.** Violates Section 8. `<div onClick={...}>` is not a button. Use `<button>`.

**Icon-only buttons without `aria-label`.** Violates Section 8. The visual icon doesn't exist for screen readers.

**Disabling zoom.** Violates Section 8. Users must be able to zoom. `user-scalable=no` is forbidden.

**Tab traps without escape.** Violates Section 8. Modals and overlays that take focus but provide no keyboard dismiss path trap keyboard and screen reader users.

### Anti-patterns that break implementation

**Arbitrary Tailwind values.** Violates Section 9. `bg-[#f5f5f5]`, `p-[17px]`, `text-[14.5px]` bypass the token system. Every value should resolve to a design token.

**Raw color values in CSS.** Violates Section 9. Hex, rgb, and hsl are not used in tokens. oklch only. Values in CSS files outside the token definitions should reference variables, not raw values.

**Manual shadow composition.** Violates Section 9. Use `shadow-level-1`, `-2`, `-3`. Hand-composing shadows produces inconsistency and misses the dark-mode top-edge highlight.

**Hardcoded transition durations.** Violates Section 9. Named durations (`duration-quick`, `duration-settle`, etc.) only.

**Flash of wrong mode.** Violates Section 9's mode-switching requirements. Dark mode users seeing light mode flash on page load is a mode-switching implementation bug. The synchronous inline script in document head is required.

**Circular calibration — measuring rendered output against itself.**

Violates §1's reference-images-win-over-prose discipline. When calibrating tokens to a reference, the reference must be external to the implementation chain. Sampling a rendered UI artifact to calibrate the tokens that produced it creates a self-consistent measurement loop: the tokens will match the artifact, but that only proves consistency with the artifact, not fidelity to the mood anchor upstream. The artifact is already downstream of the tokens; reaching back to it for calibration closes the loop against itself.

**Rule:** When sampling for token calibration, the reference must be external to the platform's implementation chain — a photograph of a real space, a physical material swatch, a printed color card, an object the design language was originally derived from. Never a UI render, a Figma mockup generated against the current tokens, or a screenshot of the live platform.

**Detection questions (must answer all three before measuring):**

1. *Where did this image come from?* If it was generated in a chat session, rendered by the platform, or exported from a design tool configured against the current palette — it's inside the loop.
2. *Could this image have been produced without the current tokens existing?* If no, it's downstream of the tokens and unsuitable for calibration.
3. *Does this image depict physical material reality (a photograph of a real space/object) or does it depict a UI rendering?* Only the former is valid as a mood anchor.

If any answer puts the image inside the implementation chain, it cannot be used for color calibration. It may still be valid as a pattern reference (see §1) — but color decisions must come from external mood anchors only.

---

### How to use this section

**When reviewing shipped UI:**
- Scan the anti-pattern list mentally. Does anything on the page match an entry?
- If something feels off but no specific anti-pattern matches, the feel is probably tied to a Section 1 anchor — review those.
- If a component is failing multiple anti-patterns, it probably needs rebuilding, not patching.

**When building new components:**
- Don't consult this section proactively during every build — that produces defensive, generic work.
- Consult it when something feels off during review and you want to localize what's wrong.

**When updating this document:**
- New anti-patterns discovered through shipped experience belong here.
- Anti-patterns that turn out to have legitimate exceptions should be updated with the exception noted, not removed.
- This section grows as the platform grows; it's the accumulated diagnostic wisdom of the design language.

---

*End of DESIGN_LANGUAGE.md v1.0.*
