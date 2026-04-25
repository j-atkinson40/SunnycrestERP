# Bridgeable Platform Interaction Model

**Status:** Canonical. Layer 2 of the three-layer design thesis.
**Established:** April 25, 2026 (Phase 4.4.3a-bis).
**Parent doc:** [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md).

This document articulates Bridgeable's interaction philosophy. It answers the question: *how does Bridgeable behave?* The visual register lives in [`DESIGN_LANGUAGE.md` §0](DESIGN_LANGUAGE.md). The execution standard lives in [`PLATFORM_QUALITY_BAR.md`](PLATFORM_QUALITY_BAR.md). The synthesis is in [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md).

---

## The reference frame — Tony Stark's workshop

Tony Stark's workshop in the Marvel films is a vivid demonstration of a specific interaction model. Strip away the cinematic theater (we'll come back to that) and what remains is a precise philosophy of how an expert works with their tools:

- Voice or text invokes objects into the workspace.
- Objects are directly manipulable — grab, move, push aside, pull back.
- Arrangement persists. When Tony throws a schematic to the side, it stays there until he changes it.
- Multiple objects coexist. Nothing is modal. He can have a schematic, a calendar, a parts list, and a conversation all open simultaneously.
- Precision tools used by an expert. No tutorial mode. The interface assumes competence and rewards fluency.

That model is the Layer 2 reference. **Bridgeable's interaction philosophy is Tony's workshop minus the cinematography.**

This is operational software for the physical economy. Its users are dispatchers, directors, owners, accountants, drivers — people whose work outlasts software fashions. The interaction model has to feel like *what an expert does with their tools*, not like *what a software application makes you click through*.

### What this rejects — cinematic theater

The films wrap the underlying model in visuals designed for cinema:

- Holograms swooping around with motion-trails
- Blue glow saturating every surface
- Particle effects on every interaction
- Dramatic flourishes on every materialization
- Sound effects telegraphing every state change

**That's theater. Take the model. Leave the theater.**

In Bridgeable, summoned objects appear quickly and quietly. They don't swoop. They don't glow. They don't trail particles. They appear because the user invoked them, and they disappear because the user dismissed them. The interactions are **quiet, fast, physical-feeling — not dramatic and glowing**.

The visual register stays Range Rover (Layer 1, calm, restrained, materially honest). The execution stays Apple Pro (Layer 3, peak craft, precise timing, no decoration). The interaction *philosophy* is Tony's workshop minus the cinematography.

---

## The four primary interactions

Every meaningful action in Bridgeable maps to one of four primary interactions. Memorize these. They are the verbs of the interaction model.

### Summon

> *Voice or text invocation materializes objects into the workspace.*

The user expresses intent. The platform produces the appropriate response — a record, a draft, a view, a Focus, a confirmation. **Summoning is the universal entry point** for almost everything.

Examples:
- *"new order Hopkins"* → command bar produces the order entity portal with Hopkins resolved as funeral home and an Order context chip
- *"schedule delivery Tuesday for the Smith case"* → command bar produces a delivery action surface with date + family pre-filled and a calendar/inventory context surface
- *"show today's deliveries"* → command bar produces a results list (or routes to the saved view if one matches)
- *"open the proof review queue"* → command bar opens a Focus; bounded-decision surface

Voice is equal-class with text. The command bar accepts both via the same input channel. Voice transcript flows through the same Intelligence layer as typed text. The interaction shape is identical regardless of input modality.

### Arrange

> *Direct manipulation positions objects in space.*

Once summoned, objects can be moved, resized, repositioned, organized. The user *arranges* their workspace as they work.

Examples in current Bridgeable:
- Drag a delivery card from the Unassigned lane to a driver lane (Phase 4.2.4)
- Drag a widget on the Focus canvas (Phase A Session 3.5)
- Drag an ancillary pool item onto a parent kanban delivery to attach it (Phase 4.3b.3)
- Drag a pinned item to reorder it in a Space's pinned section

Arrangement is **direct manipulation, not menu-driven**. The user grabs the object and moves it. No "choose action → action menu → select target → confirm" flow. **The object is the affordance.**

This is why Bridgeable canonicalized whole-element drag with no handles ([`PLATFORM_PRODUCT_PRINCIPLES.md` "Drag interactions"](PLATFORM_PRODUCT_PRINCIPLES.md)). Handles fragment the interaction model — they teach the user "this part drags, this other part doesn't." Whole-element drag teaches the universal verb: press-and-hold past 8px to grab anything.

### Park

> *Set objects aside without dismissing them; they remain available.*

This is the interaction the cinematic model captures most vividly — Tony throws a schematic to the side, returns to it later, throws it again. **Things persist.**

Park is distinct from dismiss. Parked objects are *available* without being *active*. They sit in the workspace's periphery (or in an explicit parking lot) until the user calls them back to attention.

Implementation status (April 2026):
- **Existing in current Bridgeable:** triage queue items in the AncillaryPoolPin sit in pool state until pulled into a driver lane or attached to a parent. Pinned items in a Space sit in the sidebar until clicked. The return pill on a closed Focus parks the Focus in a bounded countdown — 15 seconds to come back, then the Focus returns to its full-dismiss state.
- **Aspirational:** spatial parking lot for command-bar-summoned cards. Tony's workshop model would let the user say "actually, hold on this one for a moment" and have the card slide to a parking position. Bridgeable has the architecture for this (the command bar with a parking surface) but the spatial workspace with multi-tablet arrangement is post-September. The four-verb model still holds; the implementation surface evolves.

### Dismiss

> *Explicit removal returns the workspace to calm.*

Esc on a Focus. X on a peek panel. Click outside a popover. Cmd+K to close the command bar. Dismiss is **deliberate**, not accidental — and dismissed objects don't reappear without explicit re-invocation.

Dismiss vs Park:
- *Park* → object goes to periphery, remains available, comes back at a tap
- *Dismiss* → object is gone; user must re-summon to bring it back

Dismiss returns the workspace to calm. **Calm is the default.** The platform is *available*, not *engaging*. When the user dismisses everything, they should see a quiet workspace, not a chrome-laden interface demanding attention.

This is why Layer 1's Quietness translation principle ("a quiet workshop is intentional, not empty") and Layer 2's Dismiss verb work together. Dismissal returns to quietness. Quietness is the substrate that makes summoned objects feel intentional rather than chaotic.

---

## The materialization unit — floating tablets

Summoned objects in Bridgeable are **tablets**. The term is deliberate — borrowed from the cinematic Tony Stark imagery but emptied of its visual theater.

A tablet has these properties:
- **Floats over current context.** The user doesn't navigate away from where they were. The tablet appears on top of whatever they were doing.
- **Individually manipulable.** Drag it. Resize it. Pin it. Dismiss it.
- **Persists until dismissed.** Doesn't disappear because the user did something else.
- **Not modal.** Doesn't block. Doesn't require dismissal to proceed elsewhere. The user can ignore it, work past it, or come back.

This is fundamentally different from modal-dialog software. In modal software, the dialog blocks until dismissed. The user is forced to process it. The cognitive frame is "I am dealing with this thing right now."

Tablets invert that. The user summons the tablet *because they want it now*. They keep it open as long as it's useful. They dismiss it when they're done. The cognitive frame is "I have these tools to hand."

### Examples in current Bridgeable

- **Command bar contextual surfaces** ([`PLATFORM_ARCHITECTURE.md` §4.3](PLATFORM_ARCHITECTURE.md)): when the command bar resolves an entity (a contact, a case, a sales order), the entity card floats below or beside the input. Not a modal. Not full-screen. A tablet with a specific entity, available for the duration of the action.
- **Quote-beside-sales-order flow** (canonical example from interaction-design conversations): user is on a sales order, types *"new quote for this customer"* in command bar, the quote draft appears as a tablet beside the sales order. Both visible. User can copy fields between them, reference one while editing the other, dismiss the quote when done. The sales order never lost focus.
- **Calendar surface during scheduling** ([`PLATFORM_ARCHITECTURE.md` §4.3](PLATFORM_ARCHITECTURE.md)): user types *"schedule Tuesday"*, calendar appears as a contextual surface near the command bar. Visible while the user refines the time. Dismisses when the action completes.
- **Peek panels** ([CLAUDE.md "peek panels"](CLAUDE.md)): hover an entity reference to peek a slim card. Click to pin. The pinned peek is a tablet — dismissible, non-blocking, available.

### Aspirational evolution

The full Tony's workshop model — multiple coexisting tablets, drag-positionable, summonable from anywhere — is post-September. Bridgeable's spatial workspace currently surfaces tablets one at a time (command bar contextual surfaces are mostly single, peek panels are single, contextual cards near actions are bounded).

The architectural bones are in place: command bar can return any entity type as a card; contextual surfaces float over the current page; peek system can pin transient hovers. Generalizing to a multi-tablet arrangement with persistent positioning is a future evolution. **Build to the model; the model holds even when the surface is a single-tablet implementation today.**

---

## Voice/text invocation as primary verb

The command bar is the universal verb. **Type or speak the action; the right shape materializes.**

Some invocations produce records. Some produce drafts. Some produce views. Some produce Focuses. Some produce contextual surfaces. The command bar reads the intent and routes to the right shape — the user doesn't have to know which shape is coming.

### The intent-shape mapping

| Intent shape | Materializes as |
|---|---|
| *"Find X"* | Search results in command bar |
| *"Show me Y"* | Saved view (or new search → save) |
| *"Open the X portal"* | Entity card (contact, case, order, vendor) |
| *"Create / Schedule / Send Y"* | Action surface with parameters |
| *"Plan / Decide / Review / Process Z"* | Focus (bounded-decision surface) |
| *"What if / Why / How / When"* | Q&A response or saved view answering the question |

The user doesn't have to know which one is coming. The user types or speaks the action; the system produces the shape.

### Recognition-and-escalation

When a command bar request is decision-shaped (open-ended, multi-item, comparison-implying), the platform offers to escalate to a Focus. *"This sounds like more than one action — want me to open a Focus on it?"* One-click escalation; the command bar steps back; the user moves to the right primitive ([`PLATFORM_ARCHITECTURE.md` §4.5](PLATFORM_ARCHITECTURE.md)).

This pattern self-enforces the boundary between Act (command bar) and Decide (Focus). The command bar can be as forgiving as Intelligence allows; anything that gets too big naturally escalates. Users learn the difference between actions and decisions through the platform's gentle routing.

### Voice equal-class with text

Voice is not second-class. The command bar accepts text or voice with identical interaction shape. Voice transcript flows through the same Intelligence layer; the resolved intent triggers the same shape. **Voice is the natural channel for hands-busy situations** (a dispatcher on the phone, a director walking through a chapel, a driver in a vehicle pre-shift), and the platform respects that by making it equal-class.

Implementation: existing `useVoiceInput` hook handles speech-to-text via the Web Speech API; transcript flows into the same command bar input field; same NL extraction pipeline; same materialization shapes. Phase 1 of the UI/UX arc shipped this for command bar; broader voice-first surfaces are post-September.

---

## The chip pattern for parameters

When the user commits to an entity or parameter, **the typed text collapses into a chip on the left of the input, freeing the input for the next thing**.

This is one of Bridgeable's most distinctive interaction patterns ([`PLATFORM_ARCHITECTURE.md` §4.7](PLATFORM_ARCHITECTURE.md)). It implements the workshop model at small scale: each parameter is an object the user committed to; the chips are the workspace; the input is the place where the next thing gets summoned.

### The chip lifecycle

```
User types "John Smith" → picks family from disambiguation
↓
[John Smith] chip appears on left, input clears
↓
User types "schedule delivery"
↓
[John Smith] [schedule delivery] chips, input clears
↓
User types "Tuesday 10am"
↓
[John Smith] [schedule delivery] [Tuesday 10am] chips
↓
Confirmation surface appears with all parameters + safety context (calendar, inventory)
↓
User hits Enter to confirm
```

### Chip-ify on commitment, never on time

Triggers: picking a disambiguation option, accepting an autocomplete (Tab on single match), Enter on unambiguous match. While the user is still typing, no transformation. **Time-based clearing is always wrong** because it removes user agency over what's still working text.

### Walk-back via Shift+Tab

Shift+Tab walks back into chips. Chip slides back into input as editable text, cursor at end. Walks one chip at a time, most recent first. Tab moves forward. The user navigates the chip stack like a stack of completed thoughts — exactly like Tony pulling a piece off the workshop bench, refining it, putting it back.

### Interpretation chips (separate concept)

Distinct from commitment chips: **interpretation chips** are lighter-weight, outlined or muted, showing the system's *hypothesis* about what the user is doing without requiring commitment. ([`PLATFORM_ARCHITECTURE.md` §4.8.1](PLATFORM_ARCHITECTURE.md)).

A commitment chip is solid (brass border, full opacity) because the user committed. An interpretation chip is outlined or muted because the system formed a confident hypothesis (~70% confidence threshold) but the user hasn't confirmed.

Example: user types *"Ferguson Funeral Home Sacred Heart Cemetery Full Equipment"*. By the time *Full Equipment* is in, the system is confident this is an order — an `[Order]` interpretation chip appears (muted, outlined). The user can click it to see alternative interpretations the system considered, type a contradicting phrase to override, or hit Enter to confirm — at which point the interpretation chip becomes a commitment chip.

This pattern makes the system's interpretation visible *while* the user is typing, so the user can catch misinterpretations early and never be surprised by the result. **Most NL command bars are intent-opaque until they execute.** Bridgeable's is intent-visible during composition. That's the workshop model: an expert can see what the tool is doing as they use it.

### The pause sensor

The chip pattern needs a companion: when does the *full contextual information* (entity cards, order panels, calendar, inventory checks) appear? Not on every keystroke (flicker). Not only on Enter (too late). **The answer: when the user pauses.**

Threshold: ~500–700ms between keystrokes. Below ~400ms catches normal mid-typing rhythm pauses (flicker). Above ~1000ms feels unresponsive. The sweet spot is around half a second past last keystroke. Adaptive per user — the platform learns each user's typing rhythm over time via observe-and-offer ([`PLATFORM_ARCHITECTURE.md` §4.8.2 + §6.1](PLATFORM_ARCHITECTURE.md)).

The pause sensor is the workshop model's "the expert paused — now show them the context they need" rhythm. **Coaching shows up at the natural pause, not at every keystroke and not after submission.**

---

## Persistence of arrangement

> *When the user throws a schematic aside, it stays there until they return.*

This is the Tony Stark canonical: things stay where you put them.

### What persists

- **Pinned items in Spaces.** Once pinned, a saved view, a route, a triage queue stays in the Space's pinned section across sessions, across devices, across re-logins.
- **Layout state in a Focus.** Phase A Session 4 ([`PLATFORM_ARCHITECTURE.md` §5.15](PLATFORM_ARCHITECTURE.md)) shipped per-user per-focus layout persistence via `focus_sessions` table. The user arranges widgets in the Focus canvas; the arrangement persists; reopening the Focus puts everything back where they left it. 3-tier resolve cascade ensures graceful fallback (active session → recent closed within 24h → tenant default → registry default).
- **Affinity signals.** Phase 8e.1 added `user_space_affinity` — the platform learns which items the user actually engages with in each Space and boosts their command-bar visibility accordingly. The user's behavior compounds into a personal version of the platform without explicit configuration.
- **Date-box peek state in scheduling Focus.** Phase 4.4.3 added per-session expanded-flag tracking for the flanking DateBoxes. Phase 4.4.4 will persist this.

### What doesn't persist (intentionally)

- **Command bar state.** Closing and reopening the command bar starts fresh. The user isn't "returning to" anything in the command bar — that's the rule that keeps Command Bar from drifting into Focus ([`PLATFORM_ARCHITECTURE.md` §4.4](PLATFORM_ARCHITECTURE.md), Rule 2). Within an invocation, the chip stack persists; across invocations, fresh start.
- **Peek panels.** Hover-revealed peeks dismiss when the cursor leaves. Click-pinned peeks persist within a session but not across navigation away.
- **Toasts and ephemeral feedback.** Toast notifications, success messages, transient banners — all auto-dismiss after a short duration. The user isn't expected to manage them.

The discipline: **persistence aligns with the user's mental model of the object**. The Focus is a workspace they enter and exit — its layout persists. The command bar is a verb they invoke and complete — its state doesn't. Pinned items are deliberate placements — they persist. Hover peeks are transient inspections — they don't.

---

## Relationship to the Focus primitive

The spatial layer (the workshop) and the Focus primitive (the bounded-decision surface) are two distinct concepts that work together.

### Spatial layer = ambient

The spatial layer is **on top of the current Page/Space**. Lightweight. Dismissible. Non-exclusive. Things can be summoned, parked, arranged without committing to a focused mode. The user is still in the page they were in.

Pattern: command bar → contextual surface → done. Or: peek hover → click to pin → tablet floats above page until dismissed. Or (post-September): summon multiple tablets, arrange them in workspace.

### Focus = deliberate

The Focus primitive is **a deliberate "I'm now working through this specific decision" mode**. Full-screen-equivalent (the page beneath pushes back, the backdrop blurs). Backed by bounded-decision discipline ([`PLATFORM_ARCHITECTURE.md` §5.14](PLATFORM_ARCHITECTURE.md)) — every Focus must be bounded by a specific nameable decision.

Pattern: open Focus → core mode (kanban / single record / triage queue / etc.) → make decisions → exit. Return pill offers re-entry within 15 seconds.

### The escalation rule

When does spatial-layer work escalate to Focus?

- **Pin count crosses ~3.** Pinning more than 3 things to a session is a signal you're in Focus territory. The command bar's spatial layer is for "pull this up while I do that" — a few items at most. Pinning 5 things means you're really setting up a workspace.
- **Multiple-item review.** "Process today's proof review queue" needs Focus. "Look up one proof" doesn't.
- **Decision-bounded work.** "Plan tomorrow's deliveries" is a Focus. "Schedule one delivery for tomorrow" is a command-bar action.
- **Time-bounded by user, not by action.** Six rules from Command Bar discipline ([`PLATFORM_ARCHITECTURE.md` §4.4](PLATFORM_ARCHITECTURE.md)). If the work isn't bounded by a single action's lifecycle, it's a Focus.

Recognition-and-escalation (Section above) makes this transition smooth. The command bar offers escalation when its Intelligence detects decision-shaped requests. Users learn the boundary through the platform's routing.

### The bounded-decision discipline

Every Focus must be bounded by a specific nameable decision. Tests:

- *"What decision does this close out?"*
- *"When does the user exit?"*

If the answer is "when they're done looking around," the wrong primitive was chosen. ([`PLATFORM_ARCHITECTURE.md` §5.14](PLATFORM_ARCHITECTURE.md)).

This discipline is what keeps the workshop model from collapsing into chaos. The spatial layer can be loose because the Focus catches the bounded decisions. Without Focus as a release valve, the spatial layer would have to be everything — and would become a jumble.

---

## What this rejects

The interaction model has firm rejections. They are as load-bearing as the endorsements.

### Cinematic theater

Already covered above. Take the model. Leave the cinematography.

### App-switching as a model

Bridgeable does NOT adopt the "now you're in this app" model where moving between functions feels like switching contexts. The user is in *Bridgeable*, with various tools-to-hand. The toolbox is one workspace. Switching between Schedule and AR shouldn't feel like switching apps; it should feel like turning to a different tool on the bench.

In implementation: shared chrome (sidebar, top header, command bar) persist across all surfaces. The hub-specific surfaces vary; the tools-to-hand don't. Cmd+K is always the command bar. Cmd+[ and Cmd+] are always Space switching. The interaction language is uniform.

### Modal exclusivity

Dialogs that block until dismissed are an anti-pattern. The platform has very few of them — the Dialog primitive exists for genuinely-blocking confirmations (delete confirms, type-to-confirm modals for destructive actions) but is used sparingly.

Default pattern: tablets, not modals. Floating contextual surfaces, not blocking dialogs. The user can dismiss them, ignore them, or work past them. The exception (true modal) is reserved for actions where misclick has irreversible consequences.

### Tab-forest navigation

Bridgeable does NOT use a sidebar tree of nested tabs to navigate. The Sidebar's nav items are a fallback channel ("Nav as fallback" — [`PLATFORM_PRODUCT_PRINCIPLES.md`](PLATFORM_PRODUCT_PRINCIPLES.md)), not the primary structure. Primary navigation is:

1. **Pulse (arrives)** — Home Space surfaces what's relevant
2. **Command bar (summoned)** — Cmd+K reaches everything
3. **Focus (decided)** — bounded-decision surfaces
4. **Pinned items** — frequently-accessed shortcuts in the Space's sidebar

The Sidebar's vertical nav exists for the user who hasn't yet learned the primary channels (new tenants, infrequent users). It's a baseline, not the destination.

### "Where did I put that quote" cognitive load

A user should never have to remember where they put something. The platform tracks arrangement and presents it back. Examples:

- Pinned items remain in the Space they were pinned to. The user doesn't have to remember "I pinned the proof review queue in my Production Space" — opening the Space surfaces it.
- Layout state in a Focus persists. The user doesn't have to recreate their canvas every time they enter the Focus — the platform restores the last arrangement.
- Recently-touched records float to the top of the command bar's recents. The user doesn't have to type the full name again.
- Affinity signals make heavily-used items more reachable in the command bar over time. The user's behavior compounds.

This is the workshop model's "tools live where you put them" principle implemented in software.

### Transition animations that perform rather than communicate

Layer 3 (Apple Pro) handles this from the craft side. Layer 2 reinforces it from the interaction side: **animations communicate state change; they don't perform**.

Forbidden:
- Spring bounces on click (no physical mass, just decoration)
- Particle effects on materialization (cinematic theater)
- Slow reveals that show the platform "working" before showing the result
- Celebration animations on save (treats the user as a customer to delight, not an operator doing work)
- Skeleton loaders that linger past the actual load completion

Permitted:
- Quick fades on appear/disappear (200–400ms, ease curves from Layer 3)
- Drag lifts during active drag (subtle scale 1.02, shadow intensify level-1 → level-2)
- Crossfades on tier changes (canvas → stack → icon in Focus, asymmetric duration)
- State change indicators (active flag flips on a date box → brass border applies, no celebration)

The discipline: motion conveys *that something happened*. It doesn't perform *for the user*.

---

## The three modes of presence

Focus separates three distinct channels of awareness, each with its own visual/temporal treatment ([`PLATFORM_ARCHITECTURE.md` §5.11](PLATFORM_ARCHITECTURE.md)).

### Persistent state

> *The canvas itself, what's true now.*

The current state of the work — the schedule, the case file, the order, the proof. What the user is editing. What the user is reading.

Visual treatment: rendered in the canvas at full opacity, full readability. The primary visual emphasis. Type, surface, layout — everything serves rendering this layer well.

### Live presence

> *Cursors, highlights, locks, what others are doing now.*

Other users' activity in the same surface. Sarah is editing field X. James is viewing the case. Three other people have the queue open.

Visual treatment: lightweight, peripheral, secondary. Cursors are small. Locks are subtle. Avatars are compact. The presence layer is *visible* but doesn't compete with the persistent-state layer for primary attention.

### Ambient events

> *Activity feed, what's changed elsewhere that affects this.*

Things that happened outside the current surface that are relevant to it. A delivery just got reassigned. The vendor confirmed the order. The proof was approved.

Visual treatment: scoped to a sidebar rail or activity feed, peripheral by default, with `Intelligence Insight` priority being the only auto-emphasized variant. Per-user verbosity setting (verbose / standard / minimal, default standard) controls how much the layer bubbles up ([`PLATFORM_ARCHITECTURE.md` §5.10](PLATFORM_ARCHITECTURE.md)).

### Why three channels matter

Most software jams all three into notifications. Persistent state is in the page. Live presence is in pop-up tooltips ("Sarah is typing"). Ambient events are in toast notifications or a notification dropdown that mixes everything.

That's why notifications are universally hated: they conflate three distinct types of awareness, all interrupted into the same stream, all demanding the same response. A user can't develop a stable mental model of what the platform is telling them, because what the platform is telling them is three different things at once.

Bridgeable separates the three channels by visual register, by location, by interaction model. The user develops a stable read of "what's going on" by knowing which channel surfaces what.

This is the workshop model's "ambient awareness" — Tony in his workshop can see at a glance what's happening with each tool, what others are doing in the building, what's coming in over the comm. All three at once, none of them shouting.

---

## Mobile / tablet translation

The interaction logic is **medium-independent**. Translation per surface:

| Surface | Translation |
|---|---|
| Desktop | Free-form drag, multi-window arrangement, full keyboard (Cmd+K, Cmd+[, etc.) |
| Tablet | Card-rail patterns, swipe-to-foreground, on-screen keyboard for command bar |
| Phone | Stacked summoning, vertical card flow, intelligence-proposed arrangements (less manual arrangement, more automatic surfacing) |

The interaction *feel* is the same: *things I called up, arranged as I like, with persistence and dismissibility*. Implementation differs.

Existing surfaces:
- **Phase A Session 3.7** shipped the three-tier responsive cascade (canvas → stack → icon) for the Focus primitive. The Focus is architecturally mobile-ready in one pass — same widget state, three render presentations. Drag on canvas, scroll-snap stack on tablet, bottom-sheet icon on phone.
- **Mobile bottom-tab navigation** exists as a fallback channel for users on phone. The primary path is still Pulse + command bar; the tab bar is the safety net for users who haven't internalized the workshop model yet.

Aspirational:
- Voice-first phone surface (currently has voice input but isn't optimized for hands-busy phone-as-microphone)
- Tablet card-rail spatial workspace (the multi-tablet arrangement at tablet scale)

---

## Where the model translates to current Bridgeable

Honest about what's shipped vs aspirational. Future sessions building toward this thesis need to know what exists already.

### Shipped (canonical, in production)

- **Command bar as entity portal** — Phase 1 of UI/UX arc shipped the platform layer. Entity resolution via pg_trgm, recency weighting, tenant + permission filtering. Voice + text input. ([CLAUDE.md "Command Bar Platform Layer"](CLAUDE.md))
- **Cmd+K outside Focus pattern** — canonical principle ([`PLATFORM_PRODUCT_PRINCIPLES.md` "Cmd+K outside Focus"](PLATFORM_PRODUCT_PRINCIPLES.md)). Cmd+K is hidden inside Focus; Focus Chat (Phase A Session 7) handles in-Focus information lookup.
- **Floating contextual surfaces from command bar** — peek panels (CLAUDE.md "peek panels"), entity cards in command bar results, command bar's own contextual rendering of search + actions. The mechanism for "tablet floats over current context" exists today.
- **Decision workspaces (Focus)** — the bounded-decision primitive shipped Phase A. Funeral Scheduling Focus is the first vertical-specific implementation (Phase B Sessions 4.x). Triage queue Focuses (Phase 5 of UI/UX arc) absorb bounded-decision processing.
- **Three primitives architecture (Monitor / Act / Decide)** — canonical in [`PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md). Spaces for Monitor, command bar for Act, Focus for Decide.
- **Whole-element drag** — canonical principle ([`PLATFORM_PRODUCT_PRINCIPLES.md` "Drag interactions"](PLATFORM_PRODUCT_PRINCIPLES.md)). PointerSensor activation distance: 8px. No grip handles. Applied to: kanban DeliveryCard, Canvas widgets via WidgetChrome, AncillaryPoolPin items, expanded drawer attached-ancillary items, and any future drag surface.
- **Layout state persistence** — Phase A Session 4 shipped per-user per-focus layout persistence with 3-tier resolve cascade. The "things stay where you put them" rule is implemented for the Focus primitive.
- **Affinity signals** — Phase 8e.1 added behavior-inferred ranking. Items the user engages with surface higher in command bar over time. Pure observation; no explicit config.
- **Surface At Rest vs On Interaction** — canonical principle ([`PLATFORM_PRODUCT_PRINCIPLES.md`](PLATFORM_PRODUCT_PRINCIPLES.md)). Surfaces show their primary purpose at rest; reveal secondary affordances on interaction. Funeral Schedule's empty-driver-lanes-during-drag is the canonical example.
- **Three modes of presence in Focus** — [`PLATFORM_ARCHITECTURE.md` §5.11](PLATFORM_ARCHITECTURE.md). Persistent state, live presence, ambient events as separate channels.
- **Recognition-and-escalation** — [`PLATFORM_ARCHITECTURE.md` §4.5](PLATFORM_ARCHITECTURE.md). Command bar offers Focus escalation when intent is decision-shaped.
- **Chip-driven conversation** — [`PLATFORM_ARCHITECTURE.md` §4.7](PLATFORM_ARCHITECTURE.md). Commitment chips, Shift+Tab walk-back, common-actions surfacing.
- **Interpretation chips + pause sensor** — [`PLATFORM_ARCHITECTURE.md` §4.8](PLATFORM_ARCHITECTURE.md). System-hypothesis chips with confidence thresholds; pause-triggered context surfacing.
- **Inline keyboard disambiguation** — [`PLATFORM_ARCHITECTURE.md` §4.6](PLATFORM_ARCHITECTURE.md). Universal pattern for ambiguous resolution.
- **The Platform Is Honest** — [`PLATFORM_PRODUCT_PRINCIPLES.md`](PLATFORM_PRODUCT_PRINCIPLES.md). "Correct me" affordance on composed surfaces. Anywhere the platform makes decisions, it invites correction.

### Aspirational (the model holds; surface evolution is post-September)

- **Spatial workspace with multi-tablet arrangement.** The full Tony's workshop interaction shape — multiple coexisting tablets, summon-from-anywhere, persistent positioning — is post-September. Today's command bar produces single contextual surfaces; the spatial generalization is a future evolution.
- **Voice-first phone surfaces.** Voice input exists but isn't optimized for the "dispatcher-on-the-phone-with-FH" scenario yet.
- **Tablet card-rail spatial workspace.** Phase A Session 3.7 shipped the three-tier responsive cascade for Focus; broader tablet-as-workshop optimizations are post-September.
- **Cross-tenant ambient events.** Activity feed currently scopes to single-tenant surfaces. Cross-tenant ambient events (FH ←→ Sunnycrest activity surfacing in shared spaces) is part of the cross-tenant arc.
- **Persistent parking lot for command-bar-summoned cards.** Currently single contextual surface dismissed at action complete. Generalizing to "park this card here for now, summon another, come back later" requires the spatial workspace generalization.

**Build to the model. The model holds even when the surface is partial today.**

---

## How to apply this doc

When designing a new interaction surface:

1. **Identify which of the four primary interactions applies** (summon / arrange / park / dismiss). Most interactions are summon-then-arrange-then-dismiss. A few are summon-only (a quick lookup) or arrange-only (positioning an existing object). Park is the most distinctive and most often missed — ask whether the user might want to *set this aside without dismissing*.
2. **Apply Test 2 from the Design Thesis.** *Would this interaction feel correct in Tony's workshop?* Direct manipulation? Summonable? Dismissible? Persistent arrangement? No theater? Quiet, fast, physical-feeling?
3. **Check against the rejection list.** Does this require modal exclusivity? Does it ask the user to remember where they put something? Does it use motion to perform rather than communicate? Does it adopt app-switching feel? Refine before shipping.
4. **Check Layer alignment.** Layer 1 (visual) and Layer 3 (craft) must also pass. The interaction model lives within the visual register and is executed at peak craft.

When in doubt about whether an interaction fits the model:
- Read this doc's "What this rejects" list.
- Compare against the in-production examples (whole-element drag on DeliveryCard, command-bar entity portal, Focus primitive).
- Ask whether removing the interaction would diminish the workshop feel — if no, the interaction is decoration.

---

## Maintenance

This doc evolves carefully. The four primary interactions, the three modes of presence, the chip pattern, the persistence rules, and the rejections are load-bearing. Adding a fifth primary interaction or a fourth mode of presence is a major design decision, not a doc edit.

When new interaction patterns emerge in the codebase:
- If they fit cleanly within summon/arrange/park/dismiss, document them as examples in this doc.
- If they don't fit, the question is: should we extend the model, or should we redesign the surface to fit the model? Default to redesigning the surface. The model is the constitution; surfaces serve the model.

When current-decade software trends (the next "everyone does X now") collide with the model:
- Default to the model. The model is rooted in references outside software (Tony's workshop) and is anti-convergence by construction.
- Document the rejection in this doc's "What this rejects" section so future sessions don't re-litigate.

The interaction model is the most internally distinctive layer of the design thesis. Layer 1 (visual) is what users see first; Layer 3 (craft) is what they feel; Layer 2 (interaction) is what they live in. Build to it.
