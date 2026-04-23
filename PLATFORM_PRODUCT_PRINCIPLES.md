# PLATFORM_PRODUCT_PRINCIPLES.md

**Status:** Canonical. Guides all future product design decisions.
**Established:** April 23, 2026 (Phase B planning).
**Scope:** Product thinking and design philosophy. Not technical
architecture — see `PLATFORM_ARCHITECTURE.md` for that. Not visual
treatment — see `DESIGN_LANGUAGE.md` for that. Not quality-floor
criteria — see `PLATFORM_QUALITY_BAR.md` for that.

**Version history:**

| Date       | Change                                                          |
|------------|-----------------------------------------------------------------|
| 2026-04-23 | Initial canonical capture from Phase B planning. Sections 1–11. |
| 2026-04-23 | Added §3 (The Platform Is Honest). Renumbered §3–§10 → §4–§11. |

**Relationship to siblings:**

- `PLATFORM_ARCHITECTURE.md` answers: *how is Bridgeable built?*
- `PLATFORM_QUALITY_BAR.md` answers: *how good does it have to feel?*
- `DESIGN_LANGUAGE.md` answers: *what does it look like?*
- `PLATFORM_PRODUCT_PRINCIPLES.md` answers: ***why was it designed
  this way? what principles resolve disagreements at the fork?***

When a product decision is contested and the three other docs don't
settle it, read here. When the principles here and the three other
docs conflict, the conflict is real — escalate rather than silently
pick.

---

## 1. The Bridgeable Thesis: One Surface, Three Verbs

**The pure expression of Bridgeable is a single canvas that brings
work to the user.** Traditional ERPs force the user to navigate
*to* their work — menus, sub-menus, dashboards, saved filters. The
user carries the burden of knowing where their next decision lives.
Bridgeable inverts this. The work arrives; the user responds. Nav
is fallback, not structure.

Three interaction verbs serve the work. Every surface on the
platform maps to exactly one.

### 1.1 Pulse — the verb that *arrives*

Pulse is the Home Space surface where Intelligence composes what the
user needs to see right now. Composition is driven by:

- **Role.** A dispatcher's Pulse differs from an accountant's.
- **Time of day.** 7am shows overnight anomalies; 4pm shows
  tomorrow's plan.
- **Task state.** Open decisions bubble up; resolved items recede.
- **Behavior.** Patterns the user engages with gain prominence;
  patterns they ignore fade.
- **Anomalies.** Unusual-for-this-company events surface regardless
  of role, because they're what "right now" actually means.

**Opinionated per role. Learns per-user. Compounds per-tenant.**
Starts with decent defaults. Improves rapidly with use. Approaches
bespoke-feel over months.

Pulse is the default landing experience. Most users shouldn't need
to configure it; it should configure itself around them.

### 1.2 Command bar — the verb that's *summoned*

Cmd+K is the power-user verb. Lookup, action, navigation —
consolidated into one input. Entity-aware, action-aware, forgiving
of phrasing.

**Fast response is load-bearing.** A command bar that stutters
breaks the verb — the user starts reaching for menus. Latency is
not a performance concern; it's the primary UX concern for this
surface. Per `PLATFORM_ARCHITECTURE.md §3.15` and the UI/UX arc
Phase 1-7 latency gates, Command Bar query hits p50 < 10ms with
a BLOCKING CI gate at 100ms.

Command bar is the surface for *everything the user can imagine
doing but can't be predicted in advance*. Pulse predicts; Command
bar receives the unpredicted.

### 1.3 Focus — the verb that *decides*

Focus is the bounded-decision surface launched from Pulse or
Command bar. The user enters, decides, exits. State persists;
the user returns to Pulse.

Focus is where real work happens — the editor, the approval queue,
the reconciliation workbench, the quick-edit dialog. Every Focus
has a canonical "done" state. The user isn't trapped; they emerge.

Per `PLATFORM_ARCHITECTURE.md §5`, Focus is the bounded-decision
primitive. The free-form canvas + anchored core + return pill
choreography is its physical expression.

### 1.4 Nav — the verb that's *fallback*

Traditional information architecture — sidebar, sections, pages —
is available when the other verbs fail. Critical during Pulse
learning period, when defaults haven't had time to calibrate.

**Nav is top-tier in its own right.** Fast, predictable, information-
dense. Not a second-class citizen. Dispatchers who prefer nav should
be able to run their full day through it — every route is reachable,
every page respects the quality bar.

Auto-hidden in the mature state (Phase D+); always available via
edge hover or keyboard shortcut. The goal isn't to remove nav but
to make it unnecessary for 90% of daily work.

### 1.5 The revolutionary claim

**A $10M manufacturing operation runs on one screen + command bar.
A $200M operation (20x scale) runs the same way.**

At scale, traditional dashboards fail — no one scans 300 line items.
Pulse's filtering matters more, not less. The three-verb model is
universal across operational complexity. Sunnycrest is the proof-
of-concept; Fort Miller (§11) is the scale test.

---

## 2. Opinionated But Configurable

**The default path is opinionated: Home Space with Pulse is
sufficient for most users.** Custom spaces are available for users
who prefer explicit organization.

The opinion earns trust by calibrating well. The escape hatch
acknowledges that well-calibrated opinions can still miss individual
preferences.

### 2.1 Design discipline

- **Opinionated paths are only sufficient if the opinion is
  well-calibrated to user reality.** A default that routinely
  wrong-foots the user isn't opinionated; it's broken. Fix it or
  scope it.
- **Configurable escape hatches aren't a weakness** — they
  acknowledge that opinions should earn trust, not demand it.
  Users who prefer different organization shouldn't be locked in.
- **Most users won't use the escape hatch.** That's the point. The
  escape hatch exists to preserve agency for the minority; the
  well-calibrated default serves the majority.

### 2.2 The companion principle to §1

Opinionation is what makes "one surface, three verbs" tractable.
Without an opinion, Pulse becomes a user-configured dashboard —
which is just a traditional ERP with a new name. The opinion is
the product.

Configurability is what makes opinionation safe to ship. A platform
that enforces its opinion loses users who feel unheard. The escape
hatch lets the opinion be strong without being coercive.

### 2.3 Cross-reference

See `CLAUDE.md §1a-pre` for the umbrella statement of this principle.
See `SPACES_ARCHITECTURE.md` for the Spaces-layer expression
(seeded defaults + user customization coexist). See §3 (The Platform
Is Honest) for the conversational-correction mechanism — the
companion principle by which opinions stay earning trust.

---

## 3. The Platform Is Honest

**Bridgeable acknowledges its own imperfection.** When the system
composes something on behalf of the user — a Pulse layout, an
Intelligence suggestion, a search result, an auto-decision — the
user has a graceful first-class path to correct it.

Most software pretends to be correct; users silently work around
its wrongness. A "composed" feature that's wrong teaches the user
to ignore it, then to ignore the next composition, then to ignore
the platform. Bridgeable takes a different stance: **every composed
surface carries a visible invitation to correct it**, and the
correction routes through a conversational path that actually
changes behavior.

This is different from a feedback form. Feedback forms say *"we'll
consider this eventually."* Bridgeable says *"tell me what you need
right now, I'll act on it."* Immediate, conversational, structured
as a request with security gates.

### 3.1 The affordance

A subtle icon sits on every composed surface. Hover reveals the
invitation:

> *"Should you be seeing something here that you aren't?"*

Click opens a natural language input field. The user describes
what's missing or wrong. Intelligence parses the intent, proposes
a change, routes through permission gates, applies the change
(immediately if in-scope; after admin approval if sensitive).

The affordance is **visible but unobtrusive** — small, consistently
placed, discoverable on hover. It earns trust by being *always
there* and *always functional*. A "correct me" icon that sometimes
works and sometimes doesn't is worse than none at all.

### 3.2 Worked example

**Dispatcher Pulse, missing a widget:**

1. Dispatcher notices their Pulse doesn't show approved legacies
   awaiting print-shop pickup — they coordinate those but the
   composition doesn't surface them.
2. Clicks the "correct me" icon on their Pulse.
3. Types: *"I need to see all legacies approved here even if
   someone else approved them, because I coordinate with the
   print shop on pickups."*
4. Intelligence extracts:
   - **Intent:** cross-user legacy approvals widget
   - **Scope:** tenant-wide approvals, not just the dispatcher's
   - **Context:** coordination workflow (print-shop handoff)
5. Intelligence proposes: *"Add a 'Legacies ready for pickup'
   widget to your Pulse. Scope: all tenant approvals. This
   requires admin approval since it crosses your user scope."*
6. Dispatcher confirms the proposal.
7. Permission request generated for admin. Admin triages (§7 —
   Permission Requests as Admin Triage). Admin approves.
8. Widget appears on dispatcher's Pulse at next load.

**User experience:** conversational, structured, respectful of
security. No form to fill out; no "we'll get back to you" black
hole; no silent denial.

### 3.3 Universality

The principle extends beyond Pulse to any composed surface:

- **Command bar results.** *"Should Command bar find something
  you aren't seeing?"*
- **Focus pin layout.** *"Should this Focus have a widget it
  doesn't?"*
- **Notification surfacing.** *"Should you be getting notified
  about things you aren't?"*
- **Search results.** *"Should search be finding something you
  aren't seeing?"*
- **Intelligence suggestions.** *"Did this suggestion miss the
  point?"*
- **Auto-decisions (auto-finalize, auto-categorize, auto-match).**
  *"Should this have been decided differently?"*

**Anywhere the platform makes a decision, it invites correction.**
Not "anywhere the user might want to provide feedback" — *anywhere
the platform composes on behalf of the user*. The distinction
matters: feedback is optional volunteer activity; correction is
a first-class user action with an expected outcome.

### 3.4 Design rationale

- **Most software pretends to be correct.** Users work around
  its wrongness — private spreadsheets, shadow workflows,
  one-off macros. The software never improves because it never
  learns it's wrong.
- **Bridgeable admits uncertainty as a design stance.** Genuine
  humility, visible to the user. The platform says: "I made
  a guess; tell me if I'm wrong."
- **Calibration happens through conversation, not complaint
  forms.** Users describe their reality; Intelligence translates
  to structured changes; the system applies them. No product
  manager in the loop.
- **User trust compounds when the system visibly improves based
  on user input.** Week 2 trust is higher than week 1 because
  the user's week-1 correction visibly landed.
- **Cold-start problem softens.** Users correct wrong defaults
  immediately rather than waiting 6 weeks for observation-based
  learning (§9) to notice the mismatch.

### 3.5 Relationship to other principles

- **§2 (Opinionated but Configurable)** establishes that
  Bridgeable ships opinions, not blank slates. §3 is the
  mechanism by which those opinions **earn ongoing trust** —
  the opinion's authority depends on its correctability. An
  opinion that can't be corrected is a mandate; Bridgeable
  ships opinions, not mandates.
- **§7 (Permission Requests as Admin Triage)** handles the
  security-gate portion of §3 corrections. When a user's
  correction implies sensitive scope, the admin triage queue
  catches it. Same pattern, reused.
- **§9 (The Learning Loop)** is observation-based and slow
  (weeks-to-months timescale). §3 is conversation-based and
  fast (minutes). Both are calibration mechanisms; they work
  together. Observation-based learning inherits from
  conversation-based corrections (explicit user corrections
  are strong signal, not decaying).

### 3.6 Boundaries — what §3 is NOT

- **Not a feature request form.** Feature requests go through
  product. Corrections are *"make THIS composed surface right
  for me"* — scoped to existing primitives and existing data.
- **Not a permission bypass.** Sensitive-scope corrections
  route through admin triage (§7). Non-sensitive corrections
  apply freely. The security boundary is preserved.
- **Not a substitute for good defaults.** If corrections flood
  in for the same issue, the default is broken. Fix the default;
  don't rely on per-user corrections to paper over it.
- **Not always conversational.** Obvious corrections (dismiss
  a widget, pin a new one, rename a Space) don't need NL
  parsing — they're direct manipulation. §3 is the *path for
  the corrections direct manipulation can't express*.

### 3.7 Implementation note

A universal "correct me" primitive attachable to any composed
surface. Pairs with the admin approval Focus (§7) for scope
changes requiring permission review. Intelligence pipeline:
capture NL → parse intent → map to platform primitive change →
scope-check → propose to user → route to admin if sensitive →
apply. Telemetry: correction-accept rate, time-to-apply,
admin-approval rate. High-volume corrections for the same
composition target flag the underlying default as a likely
miss.

Part of Phase D infrastructure (per `PLATFORM_ARCHITECTURE.md`
Phase D scope). Post-arc polish will bring the primitive to
parity across every composed surface.

---

## 4. Data Density Over Decoration

**Professional operational users scan-and-act at speed across many
items.** Information density compounds over volume. A dispatcher
scanning 20 deliveries benefits from icon patterns over text
labels; an AR clerk scanning 50 invoices benefits from column
alignment over visual flourish.

### 4.1 Principles

- **Primary text carries the fields the user acts on for the
  current decision.** Funeral home name, cemetery + city, service
  time + ETA, vault type — a dispatcher's decision anchors here.
  Not icons, not color.
- **Status icons with tooltips carry scannable indicators.**
  Hole-dug, notes, chat activity, cemetery section — fields the
  user checks but doesn't anchor on. Icon + tooltip lets the eye
  skim; hover reveals detail when needed.
- **Hover reveals full detail when needed.** The card is compact
  by default; the full story is one gesture away.
- **Avoid decorative color-coding that doesn't inform decision.**
  Service-type tints removed from Dispatch Monitor cards (Phase
  3.1) because equipment context — a text field — is the primary
  cue, not service type.
- **Cards compact but readable, icons distinguishable.** ~100–120
  px vertical for dense-scan surfaces; 150+ px for review
  surfaces where absolute readability outranks density.

### 4.2 The anti-pattern

Generic kanban and SaaS tools optimize for "looks clean" at the
cost of density. Generous padding, centered single-field cards,
color-first communication. This is appropriate for low-volume
surfaces (5–10 items) and inappropriate for operational surfaces
(20–200 items).

**Professional operational users need density.** Bridgeable's
target user isn't a knowledge worker reviewing 8 Jira tickets;
it's a dispatcher processing 40 deliveries, an AR clerk working
75 invoices, a plant manager scanning 150 production records.

### 4.3 Universality

This principle applies broadly: any surface where the user scans
many items at speed. Phase B Session 1 applied it to Dispatch
Monitor. Future surfaces that inherit it:

- Driver route overview
- AR aging workbench
- Production board
- Safety training tracker
- Compliance deadline calendar
- Inventory reconciliation
- Anomaly-triage queues platform-wide

### 4.4 The comparison standard

James' Airtable setup at Sunnycrest is the dispatch-density
benchmark. It's the only prior tool that got it right. When
designing operational surfaces, compare against Airtable — not
against Jira, Asana, or Trello. Those three optimize for clarity
at low volume. Airtable optimizes for density at scale.

---

## 5. Business Function Triage: Universal vs Vertical

**Not all business functions require equal design investment.**
Some are universal — well-defined patterns across every vertical.
Others are vertical-specific — the design shape is different for
a vault manufacturer than for a funeral home than for a cemetery.

### 5.1 Universal functions

Strong defaults. Patterns known. Pulse ships with decent day-1
composition; learning refines individual preferences within the
pattern.

- **Accounting.** AR, AP, GL, reconciliation, close cycles, tax
  prep, 1099 prep, month-end, year-end. Pattern known across
  verticals. Workflow Arc Phase 8b–8f migration work refined this.
- **Compliance.** Regulatory deadlines, certifications, licensing,
  OSHA tracking, audit readiness. Per-vertical citations differ;
  framework is universal.
- **HR & Payroll.** Employee lifecycle (hire, onboard, review,
  terminate), payroll rhythms (biweekly, semi-monthly, monthly),
  benefits administration, PTO tracking. Largely universal.
- **CRM / Sales.** Pipeline, opportunities, renewals, customer
  communication, quote-to-order. Pattern stable across verticals.
- **Quality / Safety programs.** OSHA, incident reporting, toolbox
  talks, training certifications. Per-industry hazard specifics
  differ; program structure is universal.

### 5.2 Vertical-specific functions

Hand-designed per vertical. Pulse composition is vertical-specific.
Learning refines per-company operational patterns within the
vertical's shape.

- **Manufacturing operations.** Production scheduling, quality
  inspections, equipment maintenance, inventory reconciliation,
  casting cycles. Funeral-vault manufacturing differs from
  wastewater-precast differs from Redi-Rock.
- **Logistics & scheduling variants.** Funeral dispatch (this is
  Phase B work), Redi-Rock dispatch (contractor delivery),
  wastewater dispatch (pump trucks + tank delivery), crematory
  custody. Each vertical has a different dispatch shape.
- **Smart Plant operations.** Camera-forklift coordination, yard
  management, pour schedules, concrete batching. Vault-specific
  today; expands with hardware.
- **Vertical-specific workflows.** Arrangement conference (FH),
  personalization compositor (FH), cemetery coordination (FH
  + cemetery), plot reservation (cemetery), disinterment
  authorization (FH + cemetery + manufacturer cross-tenant).

### 5.3 Design implication

**Don't treat every business function as requiring novel design
thinking.** Universal patterns are known — apply them. Vertical
specifics are where design energy goes — that's where Bridgeable
wins against horizontal ERPs that apply identical patterns
everywhere.

Triage new work against this table:

| Question                              | Universal         | Vertical-specific            |
| ------------------------------------- | ----------------- | ---------------------------- |
| Has this pattern been solved before?  | Yes               | Sometimes                    |
| Do other verticals do it identically? | Yes               | No                           |
| Does design energy earn differentiation? | Low             | High                         |
| Start with                            | Known pattern     | Observational research       |
| Pulse composition                     | Role-shared       | (vertical, role)-specific    |

### 5.4 Cross-reference

The HOME_PULSE_COMPOSITIONS dict (Phase B Session 1 backend) already
encodes this triage — compositions are keyed on `(vertical,
role_slug)`, and the universal functions (Accounting, Compliance,
HR, CRM) inherit role-level components while vertical-specific
components layer on top.

---

## 6. Onboarding as First Calibration

**The Pulse engine needs decent day-1 composition for every new
user.** Pure observation-based learning has a cold-start problem —
first weeks feel generic while Pulse calibrates. A dispatcher
on day 1 shouldn't wait 6 weeks for Pulse to figure out they care
about tomorrow's schedule.

### 6.1 The solution

**Onboarding IS the first calibration.** When a user is first
assigned a role (or during first login), they describe their
responsibilities through two surfaces:

**(1) Selectable cards for universal business functions.** Multi-
select against the Universal list from §5.1 — Accounting,
Compliance, Ownership, HR, Sales, Safety, etc. Each card maps to
Pulse composition components. The user picks what applies; Pulse
composes accordingly.

**(2) Natural language field for operational specifics.** Free-text
describing what the user does, tracks, is responsible for. "I
schedule deliveries for tomorrow, handle the weekend cemetery
on-call rotation, and confirm hole-dug status with the cemetery
superintendents." This is vertical-specific signal that cards
can't capture.

Intelligence parses the NL description, extracts responsibilities,
maps them to Pulse composition components. The user reviews the
proposed composition *before* confirming. Nothing is applied
silently.

### 6.2 Day 1 vs Month 3 vs Year 1

**Day 1:** Pulse is calibrated to stated intent, not generic
defaults. Feels like someone read the user's job description.

**Month 3:** Observation-based learning has refined individual
preferences. Pulse knows what the user actually opens vs what
they said they'd open. Feels like it knows this specific user.

**Year 1:** Per-tenant patterns have compounded. Pulse knows how
this company operates — specific vendors, specific anomaly
profiles, specific seasonal rhythms. Feels bespoke to the company.

**Value compounds over tenure.** This is the moat. A competitor
shipping cold Pulse can't catch up to a Bridgeable instance with
a year of calibration.

### 6.3 Scaling property

**Fort Miller's 200 employees each calibrate themselves via
onboarding.** Bridgeable doesn't need to understand Fort Miller's
org chart. Users describe their own jobs; the system composes
accordingly. Admin approves permission requests (§7) but doesn't
manually configure each employee's workspace.

This is the scaling claim in one line: *per-user self-calibration
is the only org-chart-scaling onboarding model that works at 200+
employees.*

### 6.4 What onboarding does NOT do

- **Does not replace admin approval for sensitive permissions.**
  See §7.
- **Does not lock the user in.** Observation-based learning (§9)
  continues to refine; explicit corrections (§3) let the user
  speak up any time; users can update onboarding intent whenever
  their role shifts.
- **Does not treat the NL description as authoritative.** It's
  input to an opinionated composition engine that applies it,
  not a direct specification the engine parrots back.

---

## 7. Permission Requests as Admin Triage

**Sensitive areas require admin approval.** Accounting, HR,
financial data, cross-tenant access — user-described
responsibilities generate *permission requests*, not automatic
grants.

### 7.1 The flow

1. User onboarding (§6) lists responsibilities including
   "review accounts receivable weekly."
2. Intelligence extracts "invoice.approve + customer.view" as the
   permission scope implied.
3. Instead of granting those permissions, Bridgeable creates a
   **permission request** — "User Jane stated: 'review accounts
   receivable weekly'. Proposed scope: invoice.approve,
   customer.view. Review?"
4. The request surfaces on the admin's Pulse as a triage queue
   item. Admin opens the approval Focus.
5. Admin chooses: **Approve outright** (accept proposed scope),
   **Refine and approve** (adjust before granting), **Deny**
   (reject, optionally with reason).

### 7.2 Admin affordances

- **Batch operations for common patterns.** Five new hires in the
  same role → approve all with the standard scope in one gesture.
- **User intent is preserved as context.** The admin sees what the
  user said they'd do, not just the flat permission delta. Informs
  the decision.
- **Denial is a first-class outcome.** Rejection with reason
  closes the loop respectfully; the user sees the rejection and
  can adjust intent.

### 7.3 Security boundary preserved

Admin scrutiny is not bypassed by onboarding. The user's stated
intent *speeds the admin's triage* — it doesn't replace the
decision. Auto-approval is never the path for sensitive
permissions.

### 7.4 What flows freely

Non-sensitive configuration applies without admin triage:

- Pulse composition components (that don't imply sensitive data
  access)
- Saved views scoped to the user
- Space pins and preferences
- Command bar customizations
- Onboarding NL description itself
- Conversational corrections (§3) that stay within the user's
  existing scope

Only permission-implicating requests route to the admin queue.

### 7.5 Reuse across the platform

This is a **reusable admin-triage primitive**, not a permission-
specific feature. Three surfaces route through the same
approve/refine/deny pattern:

- Permission requests generated from onboarding (§6) and
  templates (§8).
- Scope-expanding corrections from §3 (Platform Is Honest) —
  when a user's correction implies cross-user or cross-tenant
  data, the admin queue catches it.
- Accounting agent jobs — per `CLAUDE.md §3 Agent Actions with
  Human Review`, the same approve/refine/deny shape governs
  month-end close, collections, and other accounting agents.

A future surface generating admin-gated requests inherits the
pattern without re-designing it.

---

## 8. User Configuration Templates

**User configurations are serializable and composable.** Admins
can snapshot, distribute, and re-apply the shape of a user's
workspace.

### 8.1 Admin capabilities

- **Snapshot any user's configuration as a template.** Captures:
  Pulse composition, permission set, preferences, saved views,
  command bar customizations, onboarding NL. One template =
  one user's full workspace shape at a point in time.
- **Apply templates to new or existing users.** Bootstrap a new
  hire with a senior-employee's workspace shape; copy a departing
  employee's shape to their backup.
- **Use cases:** hiring, promotion, cross-training, backup
  coverage, disaster-recovery staffing.

### 8.2 Composition model

**Role defaults + template layer + per-user personalization.** All
three merge at render time.

- Role defaults give every user in a role a baseline.
- The template layer applies shared shape on top.
- Per-user personalization from §6 onboarding, §9 observation-
  based learning, and §3 conversational corrections refines
  further.

Templates don't lock the user in. Personalization continues to
refine from the template starting point.

### 8.3 Security boundary

**Permission grants always route through admin approval even when
applying templates.** Applying a senior-accountant template to a
new hire doesn't auto-grant the senior's permissions. The
template's *permission requests* surface on the admin's queue;
the admin approves/refines/denies as usual (§7).

Non-sensitive configuration (Pulse composition, preferences,
views, command customizations) applies freely as part of the
template.

### 8.4 The competitive onboarding claim

**New hire self-describes (§6). Relevant template applied.
Permission requests generated. Admin triages daily → new hires
productive from day 1.**

Scales to 50+ hires/month without breaking admin workflow.

This is the Fort Miller onboarding story in one paragraph. The
claim isn't "Bridgeable has templates" — every ERP has templates.
The claim is "Bridgeable templates compose cleanly with per-user
self-description and admin triage, so a 200-person operation can
onboard 50 hires/month without the admin becoming a bottleneck."

---

## 9. The Learning Loop

**Pulse starts with defaults, improves with use.** The learning
loop is the slow, observation-based mechanism by which decent
day-1 becomes bespoke-feeling over months. It works alongside §3
(Platform Is Honest), which is the fast, conversation-based
correction mechanism — the two compose.

### 9.1 Loop shape

1. **Observe behavior.** What surfaces does the user engage with?
   What do they ignore? What do they search for frequently via
   command bar? What do they dismiss from Pulse without acting
   on?
2. **Infer intent.** When observation diverges from stated role
   (§6) or current composition, flag for possible update.
   Observation is authoritative over stated intent — users know
   what they do, not always what they *say* they do.
3. **Propose adjustments.** "I notice you check overdue invoices
   every morning. Want me to surface them higher?" The proposal
   is specific, actionable, and rejectable.
4. **Learn from response.** Acceptance tunes the model toward
   this pattern. Rejection tunes it away. Ignored proposals
   decay in confidence.
5. **Respect attention.** Don't reshuffle Pulse while the user is
   mid-task. Propose during natural pauses (morning open, after
   completion, on navigation to an adjacent surface).
6. **Never impose.** Always offer. Always respect dismissal. The
   user is in charge; Pulse suggests.

### 9.2 Discipline

- **Pulse that nags loses trust.** Too-frequent proposals, over-
  confident suggestions, surprise reshuffles — each erodes the
  opinion's authority. The user stops trusting the default.
- **Pulse that quietly tunes itself based on user reality gains
  trust.** Calibration that the user feels but doesn't notice is
  the ideal state.
- **Observe-and-offer is the primary learning mechanism.**
  Observe always. Offer rarely. Explain the reasoning when
  offering.

### 9.3 What NOT to learn from

- **Single-instance behavior.** One skipped widget doesn't mean
  the widget is wrong; could be a one-off day.
- **Explicit user customization.** If the user pinned something,
  they want it there. Don't unlearn pinning.
- **Explicit §3 corrections.** Conversational corrections from
  §3 are strong signal, not decaying — they reflect stated user
  intent. Observation should *reinforce* the correction, not
  override it.
- **Behavior during onboarding period.** First two weeks are
  too noisy; user is still figuring things out.
- **Data the user flagged as private or sensitive.** Respect the
  boundary.

### 9.4 Time horizon

| Tenure    | Pulse character                                           |
| --------- | --------------------------------------------------------- |
| Day 1     | Decent defaults + onboarding calibration (§6)             |
| Week 1    | Confidence builds on onboarding intent + §3 corrections   |
| Month 1   | First observation-based calibration proposals arrive      |
| Month 3   | Calibrated to specific user                               |
| Month 6   | Per-tenant anomaly profiles emerge                        |
| Year 1    | Feels bespoke to the company                              |
| Year 2+   | Compounding moat — competitors can't catch up cold        |

**Value compounds over tenure. This is the product's moat.**

---

## 10. Scheduling-Related Operational Semantics

Product-layer definitions that resolve ambiguity in scheduling
contexts. These are domain-semantics, not UI choices.

### 10.1 ETA — delivery scheduling context

**ETA is the funeral director's estimated family-arrival time at
the cemetery after the church service.** It's the downstream
anchor the dispatcher uses for *scheduling capacity planning* —
"can this driver take another delivery after the 11am graveside?"

**ETA is NOT the driver's setup target.** The driver aims to be
ready BEFORE the service-start time. A 11:00 church service
with ETA 12:00 means: driver sets up at the cemetery by ~11:15
so equipment is placed before the family arrives at 12:00.

This distinction matters for Intelligence scheduling features.
If Pulse or Focus surface "next available slot," the algorithm
uses ETA as the free-for-next-job boundary, not service-start.
If Pulse surfaces "driver setup deadline," it uses service-start-
minus-margin, not ETA.

**Reading pattern on Dispatch Monitor cards** (Phase 3.1 spec):
"11:00 Church · ETA 12:00". Service time first (anchor — when
service starts). ETA second (when driver free for next dispatch).
Matches the dispatcher mental model: *"church at 11, graveside
by 12, driver free at 12 for the next job."*

### 10.2 Draft vs Finalized schedule states

**Dispatcher plans schedule throughout the day.** Manual
finalization or auto-finalization at 1pm tenant-local locks the
schedule for TOMORROW. Drivers see the last-finalized state as
their authoritative plan.

**Late orders received post-finalization revert the schedule to
draft.** The dispatcher sees the revert; drivers continue to see
the previously-finalized state until re-finalization. Prevents
drivers reacting to in-flux plans.

**Past-date drafts are anomalies.** A day in the past that's
still in draft state indicates the dispatcher forgot to finalize;
Pulse surfaces this as an anomaly widget, not auto-resolved.
Auto-finalize targets TOMORROW only — never today, never past,
never two-days-out.

**Hole-dug status is three-state non-nullable.** `unknown` (default
— dispatcher hasn't confirmed), `yes` (confirmed dug), `no`
(confirmed not dug, flag for follow-up). Pre-Phase-3.1 null state
was dropped — every delivery has a hole-dug state; the question
is whether confirmation happened. Migration `r50_dispatch_hole_
dug_default` backfilled.

### 10.3 Why this lives here

These aren't UI decisions — they're operational semantics that
every surface touching dispatch must respect. Dispatch Monitor,
driver portal, auto-finalize scheduler, Pulse scheduling widgets,
Focus quick-edit dialog — all must render ETA and schedule state
consistently. Documenting here prevents drift across surfaces.

---

## 11. The Fort Miller Scaling Principle

**Sunnycrest ($10M revenue) is the proof-of-concept.** Single
facility, ~20 employees, one dispatcher, one admin. The platform
shape is complete; the scale claim is untested.

**Fort Miller (~$200M revenue, ~200 employees, 20x scale) is the
scale test.** Multiple facilities, multiple dispatchers, multiple
admins, hierarchical reporting, HR onboarding at volume, payroll
cycles, compliance across jurisdictions, cross-facility inventory.

### 11.1 The scale claim

**The three-verb model (§1) is universal across operational
complexity.** What makes Bridgeable work for Sunnycrest makes it
*more* valuable at Fort Miller scale, not less.

At scale, traditional dashboards fail:

- No one scans 300 delivery line items.
- No one tracks 50 concurrent compliance deadlines on a calendar.
- No one reconciles 1,200 monthly invoices by visual inspection.
- No one maintains 200 per-employee dashboards.

**Pulse's filtering matters more at scale, not less.** The dispatcher
at a 10-driver facility can get by with a spreadsheet; the dispatcher
at a 50-driver facility across 4 facilities cannot. The Pulse
opinion — "here is what you need to act on right now" — becomes
load-bearing as volume grows.

### 11.2 Scaling advantages of the architecture

- **Per-user onboarding (§6) calibrates each employee.** No
  company-wide configuration burden on the admin. 200 employees
  each self-describe; the system composes.
- **§3 corrections let each employee fine-tune their own
  surface.** 200 employees × per-user corrections doesn't break
  anything — each correction is scoped to that user's Pulse
  (with admin triage for sensitive scope). The admin doesn't
  field 200 help tickets; the platform fields them.
- **Templates (§8) handle hiring velocity.** 50 hires/month is
  not a breaking event; it's a daily triage workflow for the
  admin.
- **Intelligence-driven Pulse surfaces anomalies without manual
  dashboards.** The admin doesn't build dashboards for 200
  employees; Pulse generates them.
- **Command bar replaces menu-traversal.** Speed compounds over
  many users. A 2-second-per-action saving across 200 employees
  is 400 second-saves per day = 6.6 minutes × $50/hr = $275/day
  = $71,500/year. At scale, latency has linear ROI.
- **Per-tenant learning compounds.** Fort Miller's year-2 Pulse
  knows Fort Miller's patterns — specific vendors, seasonal
  rhythms, anomaly profiles. A competitor shipping cold Pulse
  can't catch up inside a year.

### 11.3 Why Fort Miller is specifically the right test

Fort Miller shares a vertical with Sunnycrest (precast concrete,
vault-adjacent) — so the vertical-specific design from §5.2
transfers. What doesn't transfer is scale. Fort Miller therefore
tests *the scale claim in isolation* — same vertical, same
workflows, 20x size.

If Bridgeable works for both, the thesis holds: the three-verb
model scales. If it works for Sunnycrest but not Fort Miller,
the architecture needs a different shape for scale, and that's
a deep lesson.

### 11.4 Demo strategy

**Sunnycrest demonstrates intimate scale.** The full Pulse →
Focus → done loop, dispatcher personally known to the platform,
immediate daily value.

**Fort Miller framing demonstrates the scaling claim.** "What
you're seeing at Sunnycrest runs the same way at 20x. Here's the
onboarding workflow for 50 hires/month. Here's the admin triage
for permission requests. Here's the Pulse composition for a
plant manager overseeing 4 facilities."

**Both matter for September.** Sunnycrest is the *this works*
argument. Fort Miller is the *this scales* argument. A Wilbert
licensee attending the September meeting is picking between
"horizontal ERP that almost fits" and "Bridgeable that fits at
scale." Fort Miller framing is load-bearing.

### 11.5 Post-September

Fort Miller isn't just a demo device — it's the next deployment
target. Post-September rollout plan uses Fort Miller as the
first multi-facility, large-employee-count validation. What
works at Fort Miller generalizes to the Wilbert licensee
network's largest operators.

---

## Appendix: Document Maintenance

This document is canonical. When a product decision is made that
contradicts these principles, update the document first — don't
silently drift. Amendments should:

- Reference the conversation or session that produced the change
- Note the date
- Explain what changed and why
- Keep deprecated principle text visible (struck-through or in
  a "History" section) so future readers understand the arc

New principles added post-April-2026 go at the end of the section
they logically belong in, with a date stamp. New top-level
sections get a version-history note in the header table at the
top of this document.

When in doubt: **read here first. Reference `PLATFORM_ARCHITECTURE
.md` for how; reference `PLATFORM_QUALITY_BAR.md` for how-good;
reference `DESIGN_LANGUAGE.md` for what-looks-like; reference this
for why.**
