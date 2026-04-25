# Platform Product Principles

Bridgeable's product design philosophy. This document captures the
thinking behind how the platform works, not how it's built. All
design decisions should trace back to these principles. Technical
architecture lives in `PLATFORM_ARCHITECTURE.md`; product principles
live here.

**Status:** Canonical. Load-bearing for all future product design
decisions.
**Established:** April 23, 2026 (Phase B planning).

**Relationship to siblings:**

- `PLATFORM_DESIGN_THESIS.md` answers: ***what is Bridgeable, at the
  level of design identity?*** The three-layer synthesis (Range
  Rover / Tony Stark / Apple Pro). Top-level design canon.
- `DESIGN_LANGUAGE.md` §0 answers: *what does it look like?* (Layer 1)
- `PLATFORM_INTERACTION_MODEL.md` answers: *how does it behave?*
  (Layer 2)
- `PLATFORM_QUALITY_BAR.md` answers: *how good does it have to feel?*
  (Layer 3)
- `PLATFORM_ARCHITECTURE.md` answers: *how is Bridgeable built?*
- `PLATFORM_PRODUCT_PRINCIPLES.md` answers: ***why was it designed
  this way? what principles resolve disagreements at the fork?***

When a product decision is contested and the others don't
settle it, read here.

**Version history:**

| Date       | Change                                                             |
|------------|--------------------------------------------------------------------|
| 2026-04-23 | Initial canonical capture from Phase B planning.                   |
| 2026-04-23 | Added "The Platform Is Honest" section.                            |
| 2026-04-23 | Restructured per expanded user spec — added "Software as New-Employee Coaching", renamed scheduling section to "Domain-Specific Operational Semantics", resequenced. |
| 2026-04-24 | Added three sections: "Dashboards as Universal Primitive," "Everything Composable is a Widget," "Surface At Rest vs On Interaction." Captures the primitive-layer unification (Pulse + custom Spaces are both dashboards; saved views + system widgets + smart widgets are all widgets) and canonicalizes the drag-reveal behavioral pattern from Funeral Schedule 3.3.1. |
| 2026-04-25 | Added cross-references to the three-layer design thesis canon: `PLATFORM_DESIGN_THESIS.md` (synthesis), `DESIGN_LANGUAGE.md` §0 (Layer 1 — Range Rover visual values), `PLATFORM_INTERACTION_MODEL.md` (Layer 2 — Tony Stark / Jarvis behavior), `PLATFORM_QUALITY_BAR.md` (Layer 3 — Apple Pro era execution). Articulations of interaction model already in this doc (whole-element drag, Cmd+K-outside-Focus, Surface-At-Rest-vs-On-Interaction, The-Platform-Is-Honest) cross-link into the new Interaction Model doc which articulates the broader Layer 2 model they instantiate. |
| 2026-04-25 (PM) | Added "Widget Content Sizing" principle after "Surface At Rest vs On Interaction." Canvas widgets size to their contents by default — width is layout-constrained, height is content-driven. Empty internal space is decorative chrome and rejected per Section 0 Restraint TP3. New widgets declare `height: "auto"` with optional `maxHeight` cap. AncillaryPoolPin (Aesthetic Arc Session 1.5) is the reference implementation. Existing fixed-height widgets are tech debt to revisit per natural-touch refactor. |
| 2026-04-25 (PM, late) | Renamed + expanded "Widget Content Sizing" → "Widget Compactness" (Aesthetic Arc Session 1.6). Principle now covers BOTH dimensions + boundary affordances: width sizes to content (text wraps, no ellipsis truncation as default); chrome aligns within surface's effective extent (kanban-level Finalize button aligns to kanban content right edge, not focus-core right edge); applies to non-widget surfaces too via `w-fit max-w-full mx-auto`. Pin item titles now wrap via `line-clamp-2`; SchedulingKanbanCore wraps the whole kanban + header in a content-width centered container so Finalize aligns with rightmost lane. References + exceptions documented. |

---

## The Bridgeable Thesis: One Surface, Three Verbs

The pure expression of Bridgeable is a single canvas that brings
work to the user. Nav is fallback, not structure. Three interaction
verbs serve the work:

**Pulse (arrives)** — Home Space surface where Intelligence composes
what the user needs to see right now, based on role, time of day,
task state, behavior, anomalies. Opinionated per role; learns
per-user; compounds per-tenant. Starts with decent defaults; improves
rapidly with use; approaches bespoke-feel over months.

**Command bar (summoned)** — Cmd+K verb for lookup, action,
navigation. Power-user path for anyone who learns the patterns.
Entity-aware, action-aware, forgiving. Fast response is load-bearing
— command bar that stutters breaks the verb.

**Focus (decided)** — Bounded-decision surfaces launched from Pulse
or Command bar. Enter, decide, exit. State persists; user returns
to Pulse.

**Nav (fallback)** — Traditional IA available when other verbs fail.
Critical during Pulse learning period for every new tenant. Top-tier
in its own right — fast, predictable, information-dense. Auto-hidden
in mature state (Phase D+); always available via edge hover or
shortcut.

**The revolutionary claim:** A $10M manufacturing operation runs on
one screen + command bar. A $200M operation (20x scale) runs the
same way. At scale, traditional dashboards fail — no one scans 300
items. Pulse's filtering matters more, not less. The three-verb
model is universal across operational complexity.

---

## Opinionated but Configurable

Default path is opinionated: Home Space with Pulse is sufficient for
most users. Custom spaces available for users who prefer explicit
organization. The opinion earns trust by calibrating well; the
escape hatch acknowledges that well-calibrated opinions can still
miss individual preferences.

Design discipline: opinionated paths are only sufficient if the
opinion is well-calibrated to user reality. Configurable escape
hatches aren't a weakness — they acknowledge that opinions should
earn trust. Users who prefer different organization shouldn't be
locked in.

---

## Dashboards as Universal Primitive

A dashboard composes widgets into a Tetris-like layout. Dashboards
are the primary surface of every Space.

Two composition modes:

- **Pulse (Intelligence-composed):** Home Space dashboard. Bridgeable
  composes based on role, time, task state, behavior, anomalies.
- **User-composed:** Custom Space dashboards. User drags widgets
  from catalog, arranges via Tetris layout.

Same visual language, same widget library, same layout engine, same
interactions. Only difference is composition authority — Intelligence
vs user.

Templates extend naturally: admin snapshots user's custom dashboard
composition, applies to other users. Same template mechanism as user
configuration templates.

"Correct me" invitation works on both — user can refine either
composition mode, routing through appropriate permission gates.

---

## Everything Composable is a Widget

A widget is any composable unit that renders on a dashboard. Three
types:

- **System widgets:** built-in platform widgets with purpose-built
  backends (Funeral Schedule, AR Outstanding, Production Queue, etc.)
- **Saved views:** user-created widgets that filter/configure
  existing entity data. User filters a list, saves configuration
  as named widget, appears in catalog.
- **Smart widgets:** hybrid where user picks category and
  Intelligence picks content (*"show production anomalies here"*)

All three render identically on dashboards. All three are in the
widget catalog. Only composition authority differs.

This unifies what would otherwise be separate primitives. Users
learn widgets once; saved views aren't a separate concept to
understand. Permission model applies uniformly. Templates include
saved-view widgets naturally. Cross-tenant sharing uses same
mechanism.

---

## Data Density Over Decoration

Professional operational users scan-and-act at speed across many
items. Information density compounds over volume.

Principles:

- Primary text: fields the user acts on for current decision
- Status icons with tooltips: scannable indicators (hole-dug, notes,
  chat, section, family, etc.)
- Hover reveals full detail when needed
- Avoid decorative color-coding that doesn't inform decisions
- Cards compact but readable, icons distinguishable at scan speed

Generic kanban/SaaS tools optimize for "looks clean" at cost of
density. Professional operational users need density. Dispatcher
scanning 20 deliveries or AR scanning 50 invoices benefits from
icon patterns over text labels.

This principle applies broadly: any surface where users scan many
items at speed.

---

## Surface At Rest vs On Interaction

Surfaces show their primary purpose at rest; reveal secondary
affordances on interaction.

**Example:** Funeral Schedule at rest shows only drivers with
assignments (the scheduled state). During drag, empty drivers slide
in as drop targets (the "could be changed" state). When drag ends,
they collapse back if unused.

This is the inverse of generic convention (show all options always,
let user filter). Bridgeable's discipline: canvas is for seeing what
IS; interaction is for exploring what COULD BE.

Applied broadly:

- Pulse shows what matters now; interaction reveals configuration.
- Command bar shows no results at rest; reveals candidates on typing.
- Focus shows decision surface; reveals tools on interaction.

Design discipline: if a surface requires showing "everything always"
to be useful, the primitive is wrong. Good surfaces surface their
primary purpose; interactions reveal what's contextually needed.

---

## Widget Compactness

> **Surfaces — widgets, the kanban core, any container that holds
> content — size to their contents in both dimensions. Empty
> internal space is decorative chrome and rejected per Section 0
> Restraint.**

A surface that reserves space (vertical OR horizontal) for content
it doesn't have is the same anti-pattern as a card with a
placeholder beneath the title — it claims real estate without
earning it. The user reads "this surface is bigger than what's in
it," registers the gap as decoration, and the platform's restraint
discipline (Section 0 Restraint Translation Principle 3 — *if you
can remove an element and the user doesn't notice, the element was
decorative — remove it*) is broken at the surface chrome level.

**The principle expands across two dimensions and one boundary
rule.** Width, height, and chrome alignment all answer to the same
discipline.

### Height: content-driven by default

Default height for any new widget is `"auto"`. Height is a function
of what's currently in the widget: a pool with one item is short; a
pool with ten items is taller. Height-by-design is the wrong answer
to *how-tall-should-this-be* unless the design exists for a specific
content reason.

**Bounded growth via maxHeight.** Widgets with potentially unbounded
content (lists, queues, history feeds, search results) declare a
`maxHeight` cap. Above the cap, the widget body scrolls. At-rest
height matches actual content; growth halts at the cap. The cap is
a visual ceiling, not a default reservation.

### Width: content-fitting, no truncation default

**Width sizes to display content cleanly without truncation.**
Either text fits on a single line at the current width, OR text
wraps to multiple lines naturally. **Ellipsis truncation
(`text-overflow: ellipsis`) is a failure mode** — either the widget
is too narrow (widen) or the content is too long for the layout
(wrap, or rethink what to display).

The historical default `truncate` Tailwind utility is a holdover
from desktop-app-list patterns where row height is fixed and text
must conform. In Bridgeable widgets, height is content-driven (see
above) — a row's text wrapping to two lines is fine; the widget
grows to accommodate. Use `line-clamp-2` (or 3) as a graceful
overflow cap when truly necessary; default to natural wrap.

**Width may still be fixed by layout constraint.** Right-rail
anchor bands, kanban lane uniformity for visual scanning, 8px-grid
alignment — these are legitimate reasons to set a fixed width.
What's NOT legitimate: a fixed width that's narrower than the
expected content + truncates as a result. If the layout demands a
specific width AND the content doesn't fit, the answer is wrap
(content-driven height absorbs the wrap), not ellipsis.

**Where width is content-driven.** The kanban container itself
sizes to lane content + gaps (not to the focus core's full inner
width). The header chrome above the kanban aligns within that
content-driven width, not to the inner-core's right edge. This
keeps everything contained within the visible work surface.

### Boundary affordances: chrome aligns to content extent

**Chrome elements (action buttons, navigation, headers) align
within the surface's effective horizontal extent. Nothing floats
beyond what it logically belongs to.**

- An action button inside a kanban column header aligns to that
  column's left/right edges, not to the focus core's edges.
- An action button in a kanban-level header (Finalize, Add Lane,
  Reset) aligns to the kanban container's right edge, not to the
  focus core's right edge. If the kanban is content-width and
  centered, the header chrome is content-width and centered.
- A widget's count chip / filter button / sort dropdown aligns to
  the widget's content extent, not to a chrome wrapper that
  exceeds it.

The British register (Section 0) reinforces this: surfaces don't
announce themselves with chrome. A button floating to the right of
"empty space within the surface" reads as the platform claiming
more visual real estate than the work earns. Pulling chrome inside
content extent says: this surface is exactly as wide as its work.

### Implementation contract

| Field | Meaning |
|---|---|
| `width: number` | Fixed pixel width. Always required. Justified by layout constraint (rail anchor, column uniformity); never to truncate content. |
| `height: number \| "auto"` | Fixed pixel height OR content-driven. `"auto"` is preferred for new widgets. |
| `maxHeight?: number` | Optional cap when `height === "auto"`. Above this, the widget body scrolls (`overflow-y: auto`). |

`WidgetChrome` honors the contract: when `height === "auto"`, the
chrome's inline height is omitted, content drives intrinsic height,
and `max-height` + `overflow-y: auto` cap growth if `maxHeight` is
set. Vertical resize zones are filtered out (no n/s/corner handles)
because height isn't user-tunable in content mode.

**For width-driven widgets within the canvas widget framework**:
`width` remains a fixed pixel value (rail anchor or layout
constraint). Inside the widget, content uses natural wrap +
optional `line-clamp` for graceful overflow. Don't apply
`truncate` as a default.

**For non-widget surfaces** (the kanban core, hub dashboards, any
content container outside the canvas widget framework): use
`w-fit max-w-full mx-auto` (or equivalent) so the container
natural-sizes to content and centers within the available space.
Header chrome aligns within that container's width via standard
flex layout (`justify-between` etc.).

### Reference implementations

- **`AncillaryPoolPin`** (`frontend/src/components/dispatch/
  scheduling-focus/register.ts`) — `height: "auto", maxHeight: 480`.
  Empty state ~120px; one pool item ~150px; growing past 10 items
  hits the cap and scrolls. Item title text wraps via
  `line-clamp-2` (Aesthetic Arc Session 1.6) — no truncation
  default.
- **`SchedulingKanbanCore`** kanban container (`SchedulingKanbanCore
  .tsx`) — wrapped in `w-fit max-w-full mx-auto` (Aesthetic Arc
  Session 1.6) so the surface natural-sizes to lane content + gaps,
  and centers within the focus-core inner area. Header sits within
  that same content width, so the Finalize action button's right
  edge aligns to the rightmost kanban lane's right edge — chrome
  contained within the work surface, not floating in empty space.

### Going forward

- New widgets declare `height: "auto"` by default.
- New widgets and content surfaces let text wrap; reach for
  `truncate` only when the layout genuinely cannot accommodate any
  wrap (rare).
- New non-widget surfaces use `w-fit max-w-full mx-auto` (or
  equivalent) to size to content + center.
- Existing widgets with fixed heights, default-truncated text, or
  full-width chrome are tech debt to be revisited per natural-touch
  refactor.
- A surface that fundamentally needs to fill available space (e.g.,
  the focus core itself, the App's main scroll area) should justify
  the fill in the registration / mounting comment — the principle's
  exceptions exist but must be argued.

### How this principle pairs

- **Surface At Rest vs On Interaction** (above) — surfaces show
  their primary purpose at rest, sized to that purpose. A widget
  with empty internal padding has its rest state saying "I'm a
  budget for content I might have" — wrong; the rest state should
  say "this is what I have right now."
- **Section 0 Restraint Translation Principle 3** — *if you can
  remove an element and the user doesn't notice, the element was
  decorative — remove it.* Empty horizontal space inside a surface
  passes that test (the user doesn't notice it shrinking when
  removed); empty vertical space passes the same test.
- **Section 0 British register** — *the thing is good; you'll see
  if you look closely; we're not going to point at it.* Surfaces
  don't announce themselves with oversized chrome. A button at
  the inner-core right edge floating in empty space announces. A
  button at the rightmost-lane right edge aligned with the work
  it controls doesn't announce.
- **PLATFORM_INTERACTION_MODEL "Tablets are the materialization
  unit"** — tablets are individually present, sized to themselves,
  not enclosing other content as containers. Compactness expresses
  this in the rest-state geometry.

---

## Business Function Triage: Universal vs Vertical

Not all business functions require equal design investment. Some
are universal (well-defined patterns across verticals); some are
vertical-specific (hand-designed per vertical).

**Universal (strong defaults, patterns known):**

- Accounting (AR, AP, GL, reconciliation, close cycles, tax prep)
- Compliance (regulatory deadlines, certifications, licensing)
- HR & Payroll (employee lifecycle, payroll rhythms)
- CRM / Sales (pipeline, opportunities, renewals)
- Quality/safety programs (OSHA, incident reporting)

For these, Pulse can ship strong defaults without learning. The
learning loop handles individual user preferences within universal
functions. Integration with existing tools (Check for payroll,
accounting systems) does the heavy lifting.

**Vertical-specific (hand-designed per vertical):**

- Manufacturing operations (production, quality, equipment,
  inventory)
- Logistics / scheduling variants (funeral dispatch, Redi-Rock
  dispatch, wastewater)
- Smart Plant operations (camera-forklift, yard, pour schedules)
- Vertical-specific workflows (arrangement conference,
  personalization, cemetery coordination)

For these, Pulse composition is vertical-specific. Learning refines
per-company operational patterns. Design energy goes here, not into
reinventing accounting.

Design implication: don't treat every business function as requiring
novel design thinking. Universal patterns are known. Vertical
specifics are where design energy goes.

---

## Onboarding as First Calibration

Pulse engine needs decent day-1 composition for every new user.
Pure observation-based learning has cold-start problem — first weeks
feel generic while Pulse calibrates.

Solution: onboarding IS the first calibration. When a user is first
assigned a role (or during first login), they describe
responsibilities via:

1. **Selectable cards for universal business functions**
   (Accounting, Compliance, Ownership, HR, Sales, etc.) —
   multi-select. Each card maps to Pulse composition components.

2. **Natural language field** for operational specifics. Free-text
   describing what the user does, tracks, is responsible for.
   Example: *"I schedule funerals, approve personalization, send
   invoices and statements, and give safety meetings once a month."*

Intelligence parses NL description, extracts responsibilities, maps
to Pulse composition components. User reviews proposed composition
before confirming.

Day-1 Pulse is calibrated to stated intent, not generic defaults.
Observation-based learning refines from there.

Scales beautifully: Fort Miller's 200 employees each calibrate
themselves via onboarding. Bridgeable doesn't need to understand
company org charts. Users describe their own jobs; system composes
accordingly.

Per-user personalization stored as override layer on top of
`(vertical, role)` defaults in `HOME_PULSE_COMPOSITIONS`. Both merge
at render time.

---

## Permission Requests as Admin Triage

Sensitive areas (Accounting, HR, financial data, cross-tenant
access) require admin approval. User-described responsibilities
generate permission requests, not automatic grants.

Permission requests surface on admin's Pulse as triage queue. Admin
opens approval Focus:

- **Approve outright** (accept proposed scope)
- **Refine and approve** (adjust scope before granting). Example:
  user requested accounting access because they send invoices.
  Admin refines: *"AR only, no AP, no GL access, no bank
  reconciliation."* Single click approves refined scope.
- **Deny** (reject, optionally with reason)

Batch operations for common patterns. Admin scrutiny preserved for
security; user intent remains valuable context for admin decisions.

This is a canonical triage queue use case — bounded decision
(approve/refine/deny), multiple items to process, need for context
on each, batch approval possible.

---

## User Configuration Templates

User configurations are serializable and composable. Admin
capabilities:

- Snapshot any user's configuration as template (Pulse composition,
  permissions, preferences, saved views, command customizations,
  onboarding NL description)
- Apply templates to new or existing users
- Use templates for hiring, promotion, cross-training, backup
  coverage

Two distinct use cases:

- **Exact duplicate**: New hire replacing departing employee. Apply
  exact same configuration. *"Hire Dave, Dave replaces Sarah who
  left, Dave gets Sarah's configuration."*
- **Template starter**: New hire in similar role but distinct.
  *"We have three dispatchers with similar but not identical setups.
  New dispatcher gets 'dispatcher template' as starting point, then
  onboards with their own NL description to personalize."*

Template composition layering: role defaults + template layer +
per-user personalization. All merge at render time.

**Security boundary:** permission grants always route through admin
approval even when applying templates. Non-sensitive configuration
(Pulse, preferences, views) applies freely.

Enables competitive onboarding advantage: new hire self-describes,
relevant template applied, permission requests generated, admin
triages daily → new hires productive from day 1. Scales to 50+
hires/month without breaking admin workflow.

---

## The Learning Loop

Pulse starts with defaults, improves with use. The learning system:

- **Observes behavior** — what surfaces the user engages with, what
  they ignore, what they search for frequently
- **Infers intent** — when observation diverges from stated role,
  flag for possible update
- **Proposes adjustments** — *"I notice you check X often, want me
  to surface it more prominently?"*
- **Learns from response** — acceptance/rejection refines model
- **Respects attention** — doesn't reshuffle during active
  engagement, propose during natural pauses
- **Never imposes** — always offers, respects dismissal

Discipline: Pulse that nags loses trust. Pulse that quietly tunes
itself based on user reality gains trust. Observe-and-offer is the
primary learning mechanism.

Time horizon: Day 1 is "decent defaults + onboarding calibration."
Month 3 is "calibrated to specific user." Year 1 is "feels bespoke
to the company." Value compounds over tenure.

---

## The Platform Is Honest

Bridgeable acknowledges its own imperfection. When the system
composes something on behalf of users (Pulse layout, Intelligence
suggestions, search results, auto-decisions), the user has a
graceful first-class path to correct it.

**Visual affordance:** subtle icon on composed surfaces. Hover
reveals invitation: *"Should you be seeing something here that you
aren't?"* Click opens natural language input. User describes what's
missing or wrong. Intelligence parses intent, proposes change,
routes through appropriate permission gates, applies to composition.

**Example:** Dispatcher notices missing widget. Clicks icon. Types
*"I need to see all legacies approved here even if someone else
approved them because I coordinate with the print shop on pickups."*
System extracts intent (cross-user legacy approvals widget,
coordination context), proposes the change, requests admin approval
for cross-user scope, applies once approved.

**Different from feedback forms:** feedback forms say *"we'll
consider this eventually."* Honest platform says *"tell me what you
need, I'll act on it."* Immediate, conversational, structured as
request with security gates.

**Principle extends beyond Pulse** to any composed surface:

- Command bar results (*"should Command bar find something you
  aren't seeing?"*)
- Focus pin layout (*"should this Focus have a widget it doesn't?"*)
- Notification surfacing (*"should you be getting notified about
  things you aren't?"*)
- Search results (*"should search be finding something you aren't
  seeing?"*)

Anywhere the platform makes decisions, it invites correction.

**Design rationale:**

- Most software pretends to be correct; users work around its
  wrongness
- Bridgeable admits uncertainty as a design stance — genuine
  humility
- Calibration happens through conversation, not complaint forms
- User trust compounds when the system visibly improves based on
  user input
- Cold-start problem softens: users correct wrong defaults
  immediately rather than waiting for observation-based learning

Implementation: universal "correct me" primitive attachable to any
composed surface. Paired with admin approval Focus for scope
changes requiring permission review. Part of Phase D infrastructure.

---

## Software as New-Employee Coaching

Bridgeable's user model assumes new, distracted, or partial-expert
users. Not expert operators who memorized the platform.

Three verbs mapped to coaching patterns:

- **Spaces/Pulse** — coworker pointing across the room, surfacing
  what you need
- **Command bar** — *"just tell me what you need"* with no
  navigation tax
- **Focus** — coworker pulling up a chair, spreading materials,
  walking through the decision

Bounded-decision discipline matters: good coaching shows up when
needed, then steps back. Test: *"would a good coach do this?"* —
applied to every primitive, every affordance.

This differentiates from competitors that treat users as competent
operators who should know the system. Bridgeable treats users as
people with work to do who deserve help. Expert users still benefit
(command bar for speed); non-expert users aren't penalized.

---

## Drag interactions: whole-element drag, no handles

**Drag handles are an anti-pattern on Bridgeable.** Every
draggable surface supports whole-element drag activated by the
PointerSensor activation constraint (`distance: 8`). Quick click
fires the click handler if one is registered; press-and-move past
8px activates drag. The two gestures are unambiguous because the
8px threshold cleanly separates them.

Why no handles
──────────────
- Explicit grip icons (⋮⋮) clutter UI and add visual noise to a
  surface that should read as content-first.
- Handles fragment the interaction model — users learn "this part
  drags, this part clicks" instead of the simpler "press and hold
  to grab anything."
- The activation-constraint pattern is universal across our drag
  surfaces, so a user who learns it once on kanban cards
  immediately understands it on pin items, drawer items, canvas
  widgets, future surfaces.

Pattern applies platform-wide
─────────────────────────────
- Kanban DeliveryCard / AncillaryCard (Phase 4.2.4)
- Canvas widgets via WidgetChrome (Phase A Session 3.5)
- AncillaryPoolPin items (Phase 4.3b.3.2)
- Expanded drawer attached-ancillary items (Phase 4.3b.4)
- Future drag-aware widgets (drive-time matrix, staff
  availability, pre-dig Intelligence pin)
- Any element with `useDraggable` from the platform's elevated
  DndContext (FocusDndProvider)

Implementation contract
───────────────────────
- `useDraggable({ id })` listeners spread onto the element's
  outermost interactive wrapper, NOT a separate handle child
- `cursor-grab` + `active:cursor-grabbing` on the same wrapper —
  the cursor IS the affordance
- If the element also has a click handler, both compose cleanly:
  click fires on release within 8px; drag fires on release after
  >8px movement; @dnd-kit suppresses `click` after a completed
  drag
- Drag-state visual feedback (subtle scale 1.02-1.04, shadow
  intensification, opacity dim) goes on the wrapper, not on a
  handle

Reference implementations that codify the pattern: `DeliveryCard
.tsx` (whole-card drag with QuickEdit on click), `WidgetChrome.tsx`
(whole-widget drag with resize zones via cursor change), and
`AncillaryPoolPin.tsx` PoolItem (whole-row drag with subhead +
headline as the draggable content).

Decorative cursor changes (grab → grabbing) are correct; decorative
icons are not. When in doubt, ask: "would I expect to see a grip
icon on the equivalent surface in Apple Notes, Apple Reminders, or
Linear?" The answer is virtually always no.

---

## Cmd+K outside Focus: defer to Focus Chat when target resolution is ambiguous

The command bar (Cmd+K) is hidden inside Focus per primitive
design (PA §5.15: Act and Decide are distinct primitives;
information-lookup or in-Focus actions are answered by Focus
Chat — Phase A Session 7 — not by escaping to the command bar).

That leaves Cmd+K available outside Focus — on hub dashboards,
on per-page surfaces, on the Pulse home view. For actions that
need a TARGET delivery / case / record, target resolution outside
Focus is harder than inside:

- Outside Focus there's no "currently-selected item" concept on
  most surfaces. NL extraction has to identify the target by
  family name or some other shorthand the user types.
- Inside Focus, the open Focus IS the context. Focus Chat
  inherits target unambiguously.

When QuickEdit (or an equivalent direct-edit affordance) already
serves the use case efficiently, **defer NL-disambiguated Cmd+K
alternatives to Focus Chat where target is unambiguous from
context.** Don't build a Cmd+K NL flow that competes with a 2-3
click QuickEdit path on the same surface — the QuickEdit path
typically wins because it's faster, has better failure modes
(visible form vs. silent NL parse miss), and doesn't require
target disambiguation.

Pattern surfaced during Phase 4.3b.1 investigation when
considering "assign Dave as helper to DiNardo" via Cmd+K. Target
resolution outside Focus required NL parsing of family + date;
QuickEditDialog already supports the helper field with a
deterministic dropdown. Cmd+K helper assignment deferred to Focus
Chat (Phase A Session 7) where the open Focus's selected item
provides the target without parsing.

**Test for any new Cmd+K action:**
1. Inside Focus → not applicable (Cmd+K is hidden; this is Focus
   Chat territory).
2. Outside Focus → does the user already have a faster
   deterministic path (QuickEdit, single-click button, hover-
   reveal)? If yes, defer.
3. If no faster path exists, the action is a candidate for Cmd+K
   — but design the disambiguation prompt explicitly (chip-driven
   conversation, candidate cards) rather than hoping NL extracts
   correctly.

The principle isn't "Cmd+K is bad outside Focus." It's "Cmd+K
isn't a general-purpose escape valve for any side-effect that
needs a target — the target-resolution UX deserves explicit
design every time."

---

## Domain-Specific Operational Semantics

Terminology matters when it reflects operational reality. These
semantics inform Intelligence features and user-facing surface
design.

**ETA (delivery scheduling context):** Funeral director's estimated
family-arrival time at cemetery after church service. Used for
scheduling capacity planning (can driver take another delivery
today) — NOT driver setup target. Driver aims for service start
time to be ready early; stands by for family arrival at ETA.
Distinction matters for Intelligence scheduling features: driver
availability window includes ETA + buffer, not just service time.

**Draft vs Finalized schedule states:** Dispatcher plans schedule
throughout the day, manually or auto-finalizes at 1pm for tomorrow.
Late orders received post-finalization revert schedule to draft.
Drivers see last-finalized state until re-finalized. Past-date
drafts are anomalies surfaced via Pulse widgets, not auto-resolved.

**Hole-dug status:** Three-state (unknown/yes/no). Affects pre-dig
coordination — dispatcher sends driver with extra vault base if
tomorrow's route passes near a day-after cemetery with hole already
dug. Current workflow is phone calls to cemeteries + sticky notes;
cross-tenant cemetery integration (future) automates this.

**Ancillary orders:** Smaller resale items (urns, cremation trays)
that ride alongside primary deliveries. Three states (Phase B
Session 4 Phase 4.3 / r56–r57):

- **Pool** — `attached_to_delivery_id IS NULL` AND
  `primary_assignee_id IS NULL` AND `requested_date IS NULL`.
  Waiting for pairing. Lives in the Scheduling Focus pool pin.
- **Paired** — `attached_to_delivery_id` set. Rides geographically
  with a primary kanban delivery. Driver + date inherit from
  parent at attach time. Shows as `+N ancillary` badge on the
  parent's Monitor card; click expands in Focus.
- **Standalone** — `attached_to_delivery_id IS NULL` AND
  `primary_assignee_id` set AND `requested_date` set.
  Independent stop on a driver's day, e.g., slow-day driver
  covering an ancillary-only drop-off, or office staff covering
  when drivers unavailable. Renders as a small `AncillaryCard`
  in driver lanes alongside primary `DeliveryCard`s.

Detach defaults to **standalone** (single-path detach: driver +
date preserved, only the parent FK clears). Return-to-pool is a
separate explicit action. The four canonical transitions are
implemented in `app/services/ancillary_service.py`:
`attach_ancillary`, `detach_ancillary`,
`assign_ancillary_standalone`, `return_ancillary_to_pool`.

---

## Fort Miller Scaling Principle

Sunnycrest ($10M) is proof-of-concept. Fort Miller (~$200M, 20x
scale) is the scale test for the thesis.

**Claim:** the three-verb model is universal across operational
complexity. At scale, traditional dashboards fail (can't scan 300
items); Pulse's filtering matters more, not less.

**Scaling advantages of Bridgeable architecture:**

- Per-user onboarding calibrates each employee; no company-wide
  configuration burden on admin
- Templates handle hiring velocity (50+ hires/month practical)
- Intelligence-driven Pulse surfaces anomalies without requiring
  manual dashboards
- Command bar replaces menu-traversal — speed compounds over many
  users
- Permission requests as triage fits admin workflow even at scale

**Demo strategy implication:** Sunnycrest demonstrates intimate
scale. Fort Miller framing demonstrates the scaling claim. Both
matter for September.

The revolutionary claim depends on the scaling holding. If a
200-person operation can run on the same one-screen model that
works for an 8-person operation, Bridgeable has a genuine
competitive position vs traditional enterprise software.

---

## Appendix: Document Maintenance

This document is canonical. When a product decision is made that
contradicts these principles, update the document first — don't
silently drift. Amendments should:

- Reference the conversation or session that produced the change
- Note the date in the version history table
- Explain what changed and why
- Keep deprecated principle text visible (struck-through or in a
  "History" section) so future readers understand the arc

New principles added post-April-2026 go at the end of the section
they logically belong in, with a date stamp. New top-level sections
get a version-history note in the header table.

When in doubt: **read here first.** Reference the three-layer design
thesis canon for design identity:

- `PLATFORM_DESIGN_THESIS.md` — the synthesis (top-level design
  identity). When a question crosses Layer 1/2/3, this resolves it.
- `DESIGN_LANGUAGE.md` §0 — Layer 1 (visual values).
  *What does it look like?*
- `PLATFORM_INTERACTION_MODEL.md` — Layer 2 (interaction behavior).
  *How does it behave?*
- `PLATFORM_QUALITY_BAR.md` — Layer 3 (execution standard).
  *How good does it have to feel?*

Reference `PLATFORM_ARCHITECTURE.md` for *how is it built*; reference
this doc for *why was it designed this way*.
