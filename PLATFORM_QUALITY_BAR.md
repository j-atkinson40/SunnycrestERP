# PLATFORM_QUALITY_BAR.md

**The quality standard for Bridgeable: Apple-grade across the entire platform, not just specific surfaces.**

Escalated from a canvas-specific standard to platform-wide per the April 22, 2026 decision. Reasoning: if the long-term vision is to be foundational software for the physical economy, Apple-grade quality has to be the bar from day one — every interaction shapes the user's relationship with the product, and cumulative quality compounds. Every shortcut compounds in the opposite direction.

Canonical in repo. Referenced from [CLAUDE.md §1c Canonical Platform Specs](CLAUDE.md). Every user-facing commit is evaluated against this document.

---

## Comparison Standards

### Primary North Star

Apple's **Freeform, Notes, Reminders, Calendar** — direct manipulation, smooth physics, visual restraint, consistent interaction language.

### Adjacent references

| App | What we borrow |
|---|---|
| **Figma** | Canvas interactions, performance with many objects, smart alignment guides |
| **Notion** | Block manipulation, slash-command UX, inline editing, drag-to-reorder |
| **Linear** | Keyboard-first for power users, instant interactions, restrained UI |
| **Arc browser** | Sidebar interactions, command palette, smooth transitions |
| **Claude.ai** | Chat UX, contextual surfaces, long-form reading |

### NOT the bar

Salesforce, NetSuite, traditional B2B SaaS — page reloads, modal stacks, form-heavy. Even modern SaaS competitors like Monday and Asana — better than enterprise but not Apple-grade.

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

For every commit, ask: **"would this feel as good as the Apple equivalent?"** If no, push for better before shipping.

Specific comparisons:

| Surface | Compare to |
|---|---|
| Canvas / Focus interactions | Apple Freeform |
| Lists / tables | Notion databases, Apple Notes lists |
| Forms | Apple System Settings, Apple Pages |
| Command bar | Spotlight, Apple Notes search |
| Navigation | Apple Music sidebar, Arc browser sidebar |
| Animations | Apple Music transitions, Notion block animations |
| Performance | Native iPad apps, Linear web app |
| Text input | Apple Mail compose, Notion inline editor |

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

---

## Examples of "Almost But Not Quite"

(Populated as we discover — these become learning material.)

- **Phase A Session 3 initial** — drag from grip handle only. Felt restrictive vs Apple's "drag from anywhere" pattern. Refactored in 3.5. **Lesson:** pattern choices that feel "safer" architecturally can cost feel. Evaluate against the bar before shipping.

---

## Long-term Vision Alignment

Per [BRIDGEABLE_MASTER.md](BRIDGEABLE_MASTER.md), the platform aims to be foundational software for the physical economy. That scale requires Apple-grade quality from day one — every interaction every user has shapes their relationship with the product.

The September 2026 Wilbert demo is the first public test. Subsequent vertical rollouts (precast, wastewater, Redi-Rock, cemetery, crematory, funeral home, and beyond) build on the same foundation. **Every primitive shipped to spec compounds; every shortcut compounds in the opposite direction.**

---

_Evolving document. Future commits add examples to both "Done Right" and "Almost But Not Quite" sections — these are the institutional memory of what the bar means in practice._
