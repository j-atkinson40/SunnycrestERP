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

- `PLATFORM_ARCHITECTURE.md` answers: *how is Bridgeable built?*
- `PLATFORM_QUALITY_BAR.md` answers: *how good does it have to feel?*
- `DESIGN_LANGUAGE.md` answers: *what does it look like?*
- `PLATFORM_PRODUCT_PRINCIPLES.md` answers: ***why was it designed
  this way? what principles resolve disagreements at the fork?***

When a product decision is contested and the three other docs don't
settle it, read here.

**Version history:**

| Date       | Change                                                             |
|------------|--------------------------------------------------------------------|
| 2026-04-23 | Initial canonical capture from Phase B planning.                   |
| 2026-04-23 | Added "The Platform Is Honest" section.                            |
| 2026-04-23 | Restructured per expanded user spec — added "Software as New-Employee Coaching", renamed scheduling section to "Domain-Specific Operational Semantics", resequenced. |

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
piggy-backed on primary deliveries going geographically adjacent.
Waiting-for-pairing pool lives in Scheduling Focus; paired
ancillaries show as badge+icon on Monitor card.

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

When in doubt: **read here first. Reference `PLATFORM_ARCHITECTURE
.md` for how; reference `PLATFORM_QUALITY_BAR.md` for how-good;
reference `DESIGN_LANGUAGE.md` for what-looks-like; reference this
for why.**
