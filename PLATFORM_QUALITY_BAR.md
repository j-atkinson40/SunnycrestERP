# PLATFORM_QUALITY_BAR.md

**The quality standard for Bridgeable: Apple Pro era across the entire platform, not just specific surfaces.**

This is **Layer 3 of the three-layer design thesis** ([`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md)). Layer 1 (visual values) lives in [`DESIGN_LANGUAGE.md` §0](DESIGN_LANGUAGE.md). Layer 2 (interaction model) lives in [`PLATFORM_INTERACTION_MODEL.md`](PLATFORM_INTERACTION_MODEL.md). This doc is the execution standard — *how well-made is Bridgeable, at a craft level?*

Escalated from a canvas-specific standard to platform-wide per the April 22, 2026 decision. Apple Pro era as the explicit reference articulated April 25, 2026 (Phase 4.4.3a-bis). Reasoning: if the long-term vision is to be foundational software for the physical economy, peak-Apple-craft quality has to be the bar from day one — every interaction shapes the user's relationship with the product, and cumulative quality compounds. Every shortcut compounds in the opposite direction.

Canonical in repo. Referenced from [CLAUDE.md §1c Canonical Platform Specs](CLAUDE.md). Every user-facing commit is evaluated against this document.

---

## The reference frame — Apple Pro era

**The "Apple Pro" reference means Apple at peak considered restraint.** Not current-decade Apple. Specifically:

- **Jony Ive era hardware** (2007–2017). Original iPhone, unibody MacBook, iPod nano (4th–6th gen), iPad mini (2012), Apple Watch (2014), AirPods Pro (2019). Products that say almost nothing on their surface — single button, clean type, no decoration. The product is the statement.
- **Pro app discipline at peak.** Final Cut Pro at its peak. Logic Pro at its peak. Aperture in its maturity. Apps that respect the user's attention, deliver serious craft, and don't perform. Pro app interfaces from the Cocoa-mature era (2012–2018).
- **Original iPod and iPhone clarity.** Single-purpose hardware whose interaction model is so clean that the platform vanishes and only the work remains.

This reference contributes the **execution standard**: how well-made every detail is. Type meticulously chosen. Animations precisely timed. Edges crisply rendered. Materials honestly represented. Performance buttery. Every interaction considered.

### What this reference does NOT mean — current-decade Apple drift

Apple's design language has shifted in recent years toward softer, more decorative direction. The "Apple Pro" reference explicitly **rejects current-decade Apple drift**:

| Current Apple drift | What we reject |
|---|---|
| **Liquid Glass aesthetics** | Translucent layered surfaces, parallax depth, skeuomorphic glass |
| **Soft luminance everywhere** | Overly-rounded corners, soft shadows, gradient-heavy interfaces |
| **Decorative animations** | Bounce on every tap, spring physics on hovers, animated icons |
| **Skeleton loaders that linger** | Cinematographic content reveals instead of just appearing |
| **Optimistic UI that pretends** | Showing fake progress on operations that haven't happened |
| **iOS 17+ ornamental flourishes** | Wobble effects, parallax tilt, decorative motion |

**Take the quality bar from peak Apple. Take the discipline. Don't take the current style.**

The reference is *Apple at peak*, not *Apple now*. When in doubt, ask: "Would this ship in Final Cut Pro at peak Apple form?" — not "Would this ship in iOS 17?"

---

## Comparison Standards

### Primary reference — Apple Pro era

The execution standard is calibrated against Apple's Pro app discipline at its peak (Cocoa-mature era, 2012–2018):

- **Final Cut Pro X** (2011–2017 mature releases) — pro video editor, restrained chrome, professional-grade information density, every interaction considered for editor workflow
- **Logic Pro** (2013+ Logic Pro X mature releases) — pro audio production environment, density-without-clutter, deep keyboard support, instrument-grade precision
- **Aperture** (RIP 2014, but reference example for what photo-pro UX should be) — calm, considered, no decoration
- **Original iPhone hardware era** (2007–2010) — clarity through restraint, single-button discipline
- **unibody MacBook** (2008–2012) — material honesty in hardware translated to software (no decoration, materials at their full strength)

### Surface-specific references

For specific surfaces, additional references apply (these are subordinate to Apple Pro era):

| Surface | Compare to | Notes |
|---|---|---|
| Canvas / Focus interactions | Apple Freeform | Direct manipulation, smooth physics |
| Lists / tables | Notion databases, Apple Notes lists | Density, inline editing |
| Forms | Apple System Settings, Apple Pages | Restrained, considered |
| Command bar | Spotlight, Apple Notes search | Speed, forgiveness, intent-resolution |
| Navigation | Apple Music sidebar, Arc browser sidebar | Hierarchy without clutter |
| Animations | Apple Music transitions (peak era), Notion block animations | Functional, not decorative |
| Performance | Native iPad apps, Linear web app | 60fps, sub-100ms input-to-response |
| Text input | Apple Mail compose, Notion inline editor | Crisp, immediate, forgiving |
| Pro tool density | Final Cut Pro, Logic Pro | Density at scale, expert-targeted |

### Why these and not others

- **Linear** — keyboard-first for power users, instant interactions, restrained UI. Aligns with Layer 2 interaction model + Layer 3 craft. **Ship-quality reference for B2B web app craft at our scale.**
- **Figma** — canvas interactions with many objects, smart alignment, performance at scale. Reference for Focus canvas surfaces specifically.
- **Notion** — block manipulation, slash-command UX, inline editing, drag-to-reorder. Reference for editing surfaces; lighter on the Apple Pro craft bar than Linear or Figma.
- **Arc browser** — sidebar interactions, command palette, smooth transitions. Reference for sidebar / nav patterns specifically.
- **Claude.ai** — chat UX, contextual surfaces, long-form reading. Reference for Q&A and conversational surfaces.

### NOT the bar

Salesforce, NetSuite, traditional B2B SaaS — page reloads, modal stacks, form-heavy. Even modern SaaS competitors like Monday and Asana — better than enterprise but not Apple-Pro-grade.

**Also not the bar: current-decade Apple consumer surfaces.** iOS 17+, recent macOS, the Liquid Glass / Vision Pro aesthetic. These are explicit drift references — what we *don't* want to ship. See "What this reference does NOT mean" above.

---

## Quality Dimensions

### 1. Performance

- **60fps** for all visible motion: drag, scroll, animation, transition.
- **<100ms perceived latency** for any user interaction (typing, clicking, hovering).
- **No perceptible lag** anywhere in the product.
- **Smooth with scale** — 100+ rows, 20+ widgets, complex Pulse compositions all stay snappy.
- **Lazy load only when invisible** to the user. Don't show loading states for things already in viewport.
- **Optimistic updates** where they make sense; graceful rollback on failure.

### 2. Animation

- **Spring physics** for natural motion (not linear / ease curves where physics applies — drag-drop, dismiss, layout transitions).
- **Weight and momentum** — objects have inertia; decelerate on release.
- **Intentional motion** — every animation conveys meaning: entry, exit, state change.
- **Subtle scale on grab** — 1.02 to 1.04 typical lift.
- **Shadow intensification during interaction** — pickup signal (level-1 → level-2 during drag).
- **Smooth state transitions** — no jarring jumps.
- **Apple-style curves where applicable** — `cubic-bezier(0.32, 0.72, 0, 1)` is a good starting point for many cases. DESIGN_LANGUAGE.md §9 `--ease-settle` + `--ease-gentle` are platform defaults.

### 3. Direct manipulation

- **Click anything, drag it.** No special handles required for most cases. Grip icons are decorative, not required.
- **Resize from edges and corners** via cursor affordance. No resize-corner icons.
- **Inline editing** where it makes sense — click cell to edit, not "click pencil to edit cell."
- **Native gestures work as expected** — right-click context, double-click drill-in, keyboard shortcuts.
- **Multi-select via shift+click** or lasso via drag-select rectangle where conceptually meaningful.
- **Drag-and-drop universally** where it matches the mental model (kanban, files, block reorder, etc.).

### 4. Visual restraint

- **Chrome appears when needed, disappears when not.** Per DESIGN_LANGUAGE §6.
- **Content is the focus.** UI is invisible scaffolding.
- **No persistent toolbars** where contextual affordances suffice.
- **No labels for universal affordances** — close button doesn't need "Close" text.
- **Whitespace generous, density purposeful.**
- **Color used for meaning**, not decoration.

### 5. Consistency

- **Same gesture = same behavior** everywhere.
- **Same component = same appearance** everywhere.
- **Mental model predictable** across surfaces.
- **Keyboard shortcuts consistent** — Cmd+K command bar, ESC to dismiss, Cmd+Z undo, Cmd+D duplicate.
- **Animation timing consistent** across surfaces (shared `--duration-*` + `--ease-*` tokens).

### 6. Affordance through interaction

- **Cursor changes signal possibilities** — resize cursors, grab cursors, pointer cursors.
- **Hover reveals additional affordances** — chrome, action buttons, tooltips.
- **Discoverability through natural exploration**, not requiring docs.
- **First-time users** can figure out core interactions without a manual.
- **Power users** develop muscle memory through consistent patterns.

### 7. Polish under pressure

- **Edge cases handled gracefully** — empty states, error states, slow networks.
- **Loading states feel intentional**, not "the app is broken."
- **Errors recover smoothly** with clear paths forward.
- **Network failures don't break** the experience — retry, queue, degrade.
- **Concurrent updates** handled without data loss.

### 8. Touch-grade detail

- **Pixel-perfect alignment** — 8px grid is the minimum; sub-pixel attention where it matters.
- **Typography hierarchy crisp** — DESIGN_LANGUAGE §4 type scale.
- **Color relationships intentional** — DESIGN_LANGUAGE §3 surface tokens, not arbitrary palettes.
- **Iconography consistent** in stroke weight + style — Lucide is the canonical set.
- **Spacing rhythmic** — 8px grid; consistent gaps.
- **Border radius consistent** — defined radius tokens, not ad-hoc.

---

## Test Method

For every commit, ask: **"Would this ship in an Apple Pro app at peak Apple form?"** If no, push for better before shipping.

This is the canonical Test 3 from [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md). Specific sub-questions:

- Would Final Cut Pro X ship this animation timing?
- Would Logic Pro ship this type rendering?
- Would the original iPhone team ship this latency?
- Would the unibody MacBook designers approve this edge weight?
- Would Aperture ship this color calibration?

If the answer to any of these is "no — they'd raise the bar," the surface needs work before shipping.

### Surface-specific reference comparisons

The Apple Pro era reference applies platform-wide. For specific surfaces, additional references inform what "great" looks like:

| Surface | Compare against |
|---|---|
| Canvas / Focus interactions | Apple Freeform (peak era) |
| Lists / tables | Notion databases, Apple Notes lists, Linear list views |
| Forms | Apple System Settings (peak era), Apple Pages |
| Command bar | Spotlight, Linear command palette, Apple Notes search |
| Navigation | Apple Music sidebar (peak era), Arc browser sidebar |
| Animations | Apple Music transitions (peak era), Linear's instant feel |
| Performance | Native iPad apps, Linear web app, Figma canvas |
| Text input | Apple Mail compose, Notion inline editor |
| Pro tool density | Final Cut Pro, Logic Pro, Bloomberg Terminal (with Bloomberg's typography discipline) |

---

## Process Discipline

### During build

- Sonnet evaluates each interaction against the bar before declaring complete.
- If something feels even slightly off, flag and improve before commit.
- **"Working" is not the bar. "Feeling great" is the bar.**
- When uncertain, prefer "spend extra time getting it right" over "ship it good enough."

### During review

- User verifies against the bar during manual-verification steps.
- Specific feedback like "feels jarring" or "feels sluggish" warrants investigation — don't dismiss as subjective.
- **"Feels almost right but..."** is signal to dig deeper, not to ship.

### During discovery

- Mid-build discoveries that affect quality bar surface immediately.
- Architectural shortcuts that compromise feel are escalated, not silently taken.
- Quality bar may inform architectural decisions — e.g., Phase A Session 3.5's zone-relative positioning was chosen partly for resize-feel reasons.

---

## Examples of "Apple-Grade Done Right"

(Populated as we ship — examples become institutional memory.)

- **Phase A Session 3.5 (2026-04-22)** — zone-relative positioning chosen over absolute pixels for resize-feel and viewport-resilience reasons. 8-zone resize with cursor-only affordance (no visible icon) matches Freeform resize feel. Drag-from-anywhere matches native canvas app expectations.
- **Phase A Session 3.6 (2026-04-22)** — chrome elements (grip + dismiss X) hidden during active drag/resize. Cursor change is the only affordance needed during interaction — same reasoning that removed the static resize icon in 3.5. In-widget visual indicators during a gesture are noise; the cursor is already telling the user what's happening.
- **Phase A Session 3.7 (2026-04-22)** — three-tier responsive cascade (canvas → stack → icon). Widget state is canonical and tier-independent; tier change flips the render path without mutating positions. User drags a widget in canvas mode, narrows browser to stack tier, widens back to canvas — widget is exactly where they left it. Matches Apple's behavior where Today View widgets and Smart Stack are different presentations of the same underlying content. One primitive, architecturally mobile-ready. Native CSS `scroll-snap-type: y mandatory` + momentum scrolling delivers close-to-Smart-Stack feel on iOS/Safari without a physics library — pragmatic pick that preserves Apple-grade feel at the 80% mark while deferring the final 20% to the mobile polish session rather than blocking Focus persistence work.
- **Phase A Session 3.7 post-verification (2026-04-22)** — content-aware tier detection. Canvas-vs-stack decision now checks whether widgets actually fit in canvas reserved space at their canonical sizes via `widgetsFitInCanvas(widgets, vw, vh)`. Widgets that don't fit auto-transition to stack where they DO fit cleanly — matches Apple Freeform, which adapts workspace presentation to object sizes rather than clipping objects at edges. Viewport dimensions remain necessary (icon-tier threshold at vw<700) but are no longer sufficient for canvas-vs-stack; content drives the decision.
- **Phase A Session 3.8 continuous cascade (2026-04-22)** — discrete tier thresholds replaced with geometric constraint solving. Layout responds continuously to viewport changes — core contracts, widgets pull in, tier transitions happen exactly when geometry forces them. The icon-tier gate moved from the fixed `vw < 700` pixel threshold to `stackFitsAlongsideCore(vw, vh)` — a geometric check that derives the ~928×432 floor from CORE_MIN + rail + margins. Renderers crossfade simultaneously (canvas widgets fade out AS stack rail fades in) over `--duration-settle`, not sequential step-replacements. Widgets glide to their new anchor-resolved positions on viewport resize via `transition-[left,top,width,height]`, suppressed during drag/resize via the existing `data-chrome-active` guard. Core formulas at the canvas↔stack boundary now both cap at CORE_MAX so the boundary converges at wide viewports — no pop above the cap. User experience: drag window slowly from desktop wide to phone narrow → everything flows, no discrete mode switch. Matches macOS/iOS window-resize feel where content flows continuously with window size. Architectural correction identified during Session 3.7.2 verification: "full canvas view down to mobile-sized state...smooth fluid cascade from desktop down." **Lesson (institutional):** discrete thresholds are a code smell in responsive UI — look for the underlying geometric constraint and let the constraint drive the transition. Tiers should emerge from what fits, not from pre-configured breakpoints.
- **Phase A Session 3.8.1 layering + fit-check correction (2026-04-22)** — same-day fix on Session 3.8 after user verification surfaced three quality-bar failures that shared one surface and two root causes. (1) Canvas widgets never left stack mode at wide-but-short viewports (e.g. 2560×1300) because `widgetsFitInCanvas` used AND logic for corner anchors, failing a 240-tall top-left widget that had 580px of horizontal slack. Corner anchors have an L-shaped reserved area — a widget fits if it avoids overlapping core in EITHER dimension, not both. Rewritten to anchor-aware per-class logic: OR for corners, horizontal-only for rail, vertical-only for center; all offset-aware. (2) Stack rail appeared "under" growing core during stack↔canvas transitions. (3) Icon button was painted behind core in icon tier — hit-test at icon center returned the core's footer, not the icon. Both 2 + 3 traced to a single stacking-context bug: Canvas and Popup both at `z-index: var(--z-focus)`, DOM order decides paint order at equal z-index, Canvas rendered BEFORE Popup. Popup won paint order and covered widgets/stack/icon. Fix: swapped DOM order so Canvas renders AFTER Popup. Plus asymmetric crossfade — inactive renderer fades out in `--duration-quick` (200ms) while active renderer fades in over `--duration-settle` (300ms) — so stale spatial positions are invisible before the growing core reaches them. **Lesson (institutional):** when three visual-quality bugs report from different symptoms, look for the shared root cause before reaching for three separate fixes. Two of the three issues here collapsed into one DOM-order swap; the third was a fit-check axiom that had been correct at small scales but wrong at wide ones. The pattern to notice: discrete bugs with different surfaces but one underlying structure (here: paint order at equal z-index).
- **Phase A Session 4 optimistic loading for Focus persistence (2026-04-22)** — first paint is always instant. On Focus open, the frontend renders from the in-code registry default immediately (<100ms, no loading state visible) and fires POST /focus/{type}/open in parallel. When the server resolves the 3-tier cascade (active session → recent closed within 24h → tenant default → null), the frontend swaps to the persisted layout. Persistence failure is non-blocking — UX continues on the optimistic default; the failure is logged, not surfaced. Layout writes debounce 500ms with most-recent-wins cancellation. Ownership enforced server-side via existence-hiding 404 on cross-user access. Pattern candidate for other Focus-adjacent primitives that want "instant entry + eventual consistency" feel (hub dashboards, Space templates, future per-user Focus customization). **Lesson (institutional):** for primitives with a measurable "first paint to useful" budget, optimistic loading with a server-resolved swap-in is cheaper (in UX terms) than a skeleton + fetch. The registry default is a known-good starting point; the server resolve is a polish that makes the NEXT interaction correct. Users never see a spinner because there's nothing to wait for.
- **Phase A Session 3.8.2 viewport-synchronous layout (2026-04-22)** — same-day fix on 3.8.1 after user verification confirmed layering was fixed but resize still felt choppy relative to macOS Finder. Profiling showed 60fps composition was maintained, but the *subjective* choppiness came from CSS transitions on `left/top/width/height` adding second-order interpolation on top of the viewport's first-order motion. Each resize event set a new target and CSS started a fresh 300-400ms ease toward it; at 60Hz resize, widgets + core were always ~100-200ms behind where they should be, easing into new positions — the "choppy chase" feel. Fix: layout properties follow viewport synchronously per-frame. WidgetChrome's `transition-[left,top,width,height]` removed; Focus Popup's `transition-[width,height,left,top]` removed AND `transition-none` added explicitly (because the remaining `duration-arrive` set `transition-duration: 0.4s` while `transition-property` defaulted to `all`, which would still animate layout props without the explicit disable). `useViewportTier` resize handler rAF-throttled so multiple resize events within one animation frame collapse to one re-render. Preserved transitions (all GPU-composited or cheap non-layout): tier-renderer `opacity`, widget `box-shadow`, chrome children `opacity`. Tier-boundary visual continuity carried by the opacity crossfade, not by a size-transition underneath. **Lesson (institutional):** CSS transitions on layout properties are an anti-pattern for viewport-driven layout. They make sense when the SOURCE of change is discrete (state mutation that doesn't smoothly interpolate on its own) but become a liability when the source IS already a smooth signal (viewport resize, drag gesture). If your layout is driven by an input that's already per-frame-smooth, animations on top of it will lag the input. Reserve CSS transitions for GPU-composited properties (opacity, transform) and for state changes that need visual interpolation the input doesn't provide. For viewport-driven layout, follow the input synchronously — the browser handles the per-frame cadence, your code just needs to apply the current values without getting in the way.
- **Phase A Session 3.8.3 position via transform — composite-only updates (2026-04-23)** — continuation of Sessions 3.8.x performance line. After 3.8.2 removed transitions on layout props, window resize still read as choppy relative to tldraw.com + macOS Finder. Pre-build research mapped tldraw's three-layer stack (transform for position, signals + useQuickReactor bypassing React, memoized per-property diff). At our scale (3-10 widgets per Focus, not 10000 shapes), only layer 1 provides a perceptible improvement — layers 2-3 save ~0.5ms/frame, below the perceptual threshold, and cost a full state-management rewrite. Shipped the calibrated 30-LOC fix: `WidgetChrome` + Focus core position via `transform: translate3d(x, y, 0)` instead of `left/top`. Per-frame position updates during resize become composite-only (GPU layer push, no layout, no paint) vs. the pre-fix ~2-5ms/widget/frame of layout + paint. Width/height stay inline — they're stable during window resize (only change during user-initiated widget resize, a rare event). Implementation detail: Focus.Popup wrapped in a positioner `<div>` because the Popup's `data-open:animate-in zoom-in-95` keyframes override inline transform during the 400ms open/close window (CSS Animations L1 spec: animation transform replaces inline transform during runtime); the wrapper owns position, the Popup owns its zoom animation — two elements, two concurrent transforms, no conflict. **Lesson (institutional):** when comparing performance to a reference implementation (tldraw, Figma), decompose their stack into layers and evaluate each against your own scale. Copying a full optimization stack designed for orders-of-magnitude more elements can look disciplined but is actually over-engineering that locks you into more complexity than the scale justifies. Layer 1 (transform for position) is universal — applies at 3 widgets, applies at 30000. Layers 2-3 (signals + direct DOM writes) only start paying rent past ~100 moving elements. Ship the scale-calibrated subset, not the full pattern.

---

## Examples of "Almost But Not Quite"

(Populated as we discover — these become learning material.)

- **Phase A Session 3 initial** — drag from grip handle only. Felt restrictive vs Apple's "drag from anywhere" pattern. Refactored in 3.5. **Lesson:** pattern choices that feel "safer" architecturally can cost feel. Evaluate against the bar before shipping.
- **Phase A Session 3.7 — stack scroll physics (deferred, not regression).** Stack tier ships with native CSS `scroll-snap-type: y mandatory` rather than a spring-physics library. Native scroll-snap is close to Smart Stack feel — momentum on iOS/Safari; snap-to-tile on scroll release — but doesn't match the subtle spring overshoot + rubber-band behavior Apple uses on Today View widgets. Bottom-sheet swipe-dismiss uses a linear 150px threshold; Apple's sheet uses velocity-weighted dismissal. **Tracked for mobile polish session** (post-Phase-A), not a Session 3.7 regression — shipping a physics library (`react-spring` or `framer-motion`) for one primitive when the rest of the overlay family uses CSS-based `data-open:animate-*` would fork the animation pipeline. Spring physics lands when we do the full iOS behavior pass + device verification. **Lesson:** the bar has tiers. Native CSS delivers 80% of Apple-grade feel at 0% architectural cost; the final 20% is worth a separate session, not a parallel pipeline shipped mid-phase.
- **Phase A Session 3.7 initial — viewport-only tier threshold (fixed 2026-04-22).** The first Session 3.7 ship used fixed viewport breakpoints for canvas-vs-stack (`vw < 1000 OR vh < 700 → stack`). User visual verification surfaced widgets clipping at viewport edges in canvas mode: three 320px-wide widgets need 320px of reserved space per side, but at vw=1400 canvas mode only reserves 100px per side. Tier detection said "viewport wide enough → canvas" while widgets were actually overflowing reserved space. **Fixed same-day** by rewriting `determineTier` to be content-aware: `widgetsFitInCanvas(widgets, vw, vh)` checks per-anchor that each widget's dimensions fit in its reserved band; any failure → stack. Viewport-only heuristic retained for the icon-tier threshold (vw < 700 is structurally unusable regardless of content) but removed for canvas-vs-stack. This matches Apple Freeform's behavior: if objects don't fit cleanly in the workspace, present them differently rather than clipping. **Lesson:** responsive tier logic must consider what's being placed, not just available space. Viewport dimensions are necessary but not sufficient — reserved space shrinks linearly with viewport, but widget sizes stay fixed, so "viewport is wide enough" isn't a reliable proxy for "content fits." Content-aware detection is the right architectural shape the first time; the initial ship missed it and paid in a same-day fix + regression test.
- **Phase A Sessions 3.7–3.7.2 — discrete tier threshold model (corrected in 3.8, 2026-04-22).** Sessions 3.7–3.7.2 built the three-tier responsive cascade with the canvas↔stack boundary on a content-aware check (correct) but kept a fixed `vw < TIER_ICON_MAX_WIDTH = 700` pixel threshold for the stack↔icon gate. The cascade worked — tests passed, no regressions — but it read as discrete mode switches at the boundaries rather than continuous flow. Renderers unmounted + mounted instantly at tier changes (no fade), widget positions snapped to new resolved rects on viewport resize (no transition), and the 700px stack↔icon threshold was arbitrary against the actual geometric requirement. User caught the model error during Session 3.7.2 verification: "full canvas view down to mobile-sized state...smooth fluid cascade from desktop down." **Corrected in Session 3.8** via a coherent refactor: geometric icon gate (`stackFitsAlongsideCore` — derives ~928×432 floor from CORE_MIN + rail + margins, replacing the arbitrary 700), simultaneous crossfade between renderers over `--duration-settle`, smooth widget-position transitions on viewport resize (suppressed during drag via existing chrome-active guard), and CORE_MAX cap on stack formula so canvas↔stack boundary converges at wide viewports. **Lesson (institutional):** discrete pixel thresholds in responsive UI hide the underlying geometric constraint behind an arbitrary number. Look for what structurally fits, derive the threshold from that, and let transitions ride on geometric constraints — not configured breakpoints. Sessions 3.7–3.7.2 were technically functional but missed the "flows continuously" quality bar; the session that caught this did so against macOS window-resize feel, which is exactly the comparison standard this doc sets.

---

## Calibration Against Existing Surfaces (April 2026)

These surfaces are at the Apple Pro bar today (or close enough that they serve as in-house calibration points). New surfaces compared against these should feel like they belong; surfaces that feel different need refinement.

**At-bar surfaces:**

- **Funeral Schedule kanban DeliveryCard** ([`frontend/src/components/dispatch/DeliveryCard.tsx`](frontend/src/components/dispatch/DeliveryCard.tsx)) — Phase 3.1 + 3.2 + 4.2.4 work. Whole-card drag, restrained typography hierarchy, brass for status emphasis only, no perimeter border. Cards float on the lane background as material objects. **Canonical card surface for the platform.**
- **Scheduling Focus core after Phase 4.4.2 container removal** ([`frontend/src/components/focus/Focus.tsx`](frontend/src/components/focus/Focus.tsx)) — content floats directly on dimmed-blurred backdrop. No container chrome. Each child element provides its own visual weight. "Focus is a mode, not a modal."
- **AncillaryPoolPin** ([`frontend/src/components/dispatch/scheduling-focus/AncillaryPoolPin.tsx`](frontend/src/components/dispatch/scheduling-focus/AncillaryPoolPin.tsx)) — workshop-tool register at small scale. Whole-row drag, no handle, brass count chip. Compact rows, no decorative chrome.
- **DateBox flanking affordance (Phase 4.4.3)** ([`frontend/src/components/dispatch/scheduling-focus/DateBox.tsx`](frontend/src/components/dispatch/scheduling-focus/DateBox.tsx)) — first surface built against locked DESIGN_LANGUAGE Section 0. Square-shouldered, brass-on-active jewelry signal, restrained at rest. Calibration surface for all three layers passing simultaneously.
- **QuickEditDialog** — section-grouped form with eyebrows, canonical input shells, no celebration on save, no decorative chrome. Restrained, considered, operator-grade.
- **Brass primary buttons platform-wide** — single-color functional emphasis. Same button reads native to both light and dark mode. Material continuity across modes.
- **Phase A Session 3.5 zone-relative canvas positioning** — 8-zone resize with cursor-only affordance. Drag-from-anywhere matches native canvas app expectations (Freeform-grade interaction feel).
- **Phase 4.2.4 whole-card drag with PointerSensor activation distance: 8** — clean separation of click vs drag through gesture distinguishing, not through dedicated handles. Apple Pro pattern: the affordance IS the cursor change, not a visible icon.

**Drift surfaces (flagged for refactor when next touched):**

- **WidgetChrome decorative grip icon** — retained from Phase A Session 3.5 as `pointer-events: none` decoration. Per the post-4.3b.3.2 platform principle ("drag handles are an anti-pattern"), this icon now violates Layer 1 Considered Materiality + Layer 2 whole-element drag rule. Tracked in [`PLATFORM_PRODUCT_PRINCIPLES.md` "Drag interactions"](PLATFORM_PRODUCT_PRINCIPLES.md) as tech debt.
- **BlockLibrary grip icon** — same pattern, same rationale to retire.
- **Legacy pages still on shadcn defaults** (~213 pages per Aesthetic Arc Phase II audit, pre-batch-1) — most render coherently because their primitives have been refreshed (Sessions 2–3), but page-level chrome still uses generic shadcn classes. Long-tail natural-touch refactor.
- **Status-pill ad-hoc rendering sites** (~1305 ad-hoc Tailwind status-color usages noted in Aesthetic Arc Phase II audit) — should migrate to `<StatusPill>` or `<Badge variant="info|warning|success|error">`. Long-tail.

These calibration points are not aspirational — they exist in the codebase today. New surfaces should compare against them; refactor passes should pull drift surfaces toward the in-register surfaces.

---

## Relationship to the Three-Layer Design Thesis

This doc is **Layer 3** of the synthesis articulated in [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md):

> *Bridgeable looks like a Range Rover, behaves like Tony Stark's workshop, and is built like an Apple Pro app.*

| Layer | Doc | Question it answers |
|---|---|---|
| 1 — Range Rover | [`DESIGN_LANGUAGE.md` §0](DESIGN_LANGUAGE.md) | What does it look like? |
| 2 — Tony Stark / Jarvis | [`PLATFORM_INTERACTION_MODEL.md`](PLATFORM_INTERACTION_MODEL.md) | How does it behave? |
| 3 — Apple Pro | This doc | How well-made is it? |

All three tests must pass before ship. This doc owns Test 3:

> *Would this ship in an Apple Pro app at peak Apple form?*

When this doc and another canonical doc appear to disagree, [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md) "Where the layers would conflict, and how to resolve" articulates the resolution. Most apparent conflicts dissolve when the question of "which layer is being asked?" is clarified.

---

## Long-term Vision Alignment

Per [BRIDGEABLE_MASTER.md](BRIDGEABLE_MASTER.md), the platform aims to be foundational software for the physical economy. That scale requires peak-Apple-Pro-grade quality from day one — every interaction every user has shapes their relationship with the product.

The September 2026 Wilbert demo is the first public test. Subsequent vertical rollouts (precast, wastewater, Redi-Rock, cemetery, crematory, funeral home, and beyond) build on the same foundation. **Every primitive shipped to spec compounds; every shortcut compounds in the opposite direction.**

The strategic positioning: the design moat is the **three-layer coherence**. Competitors can copy individual features. They cannot easily copy a coherent three-layer design identity rooted in references they don't share, applied with discipline they don't have. Hold the bar.

---

_Evolving document. Future commits add examples to both "Done Right" and "Almost But Not Quite" sections — these are the institutional memory of what the bar means in practice._
