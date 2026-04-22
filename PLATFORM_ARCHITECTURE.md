## Bridgeable Platform Architecture 

Status: Discussion / specification, captured during the aesthetics arc (April 2026). Build sequencing TBD when the aesthetics arc completes. 

Purpose: This document consolidates the platform architecture work developed across multiple desktop sessions during the aesthetics arc. It describes the three core primitives (Spaces, Command Bar, Focus), their supporting systems, the cross-cutting principles that govern them, and the underlying thesis the whole platform is built around. 

Companion docs: Sits alongside `CLAUDE.md` (build standards + session log), 

`BRIDGEABLE_MASTER.md` (master planning reference), `FEATURE_SESSIONS.md` , and 

`FUNERAL_HOME_VERTICAL.md` . Where this doc and the existing docs disagree, this doc reflects the more recent thinking and supersedes. 

## Table of Contents 

1. Core Thesis 

2. The Three Primitives: Monitor, Act, Decide 

3. Spaces (Monitor) 

4. Command Bar (Act) 

5. Focus (Decide) 

6. Cross-Cutting Principles 

7. Cross-Location and Cross-Tenant 

8. Open Questions and Future Considerations 

## 1. Core Thesis 

Bridgeable is software-as-new-employee-coaching. Assume users are new, distracted, and partial-experts at best — design every primitive to provide what an experienced coworker would. 

- Spaces = the experienced coworker pointing across the room: “you’ve got three things on your plate today, here’s the rough state of each.” Work surfaces itself; the user doesn’t have to find it. 

- Command Bar = the experienced coworker saying “you don’t need to remember where that button is, just tell me what you need.” Natural language replaces tribal knowledge of menus. 

- Focus = the experienced coworker pulling up a chair next to you, spreading the relevant materials across the table, saying “okay, this is what we’re deciding, here’s everything we need, what do you think?” The platform becomes the second person at the table. 

The bounded-decision discipline (Section 5) matters because good coaching shows up for the decision then steps back. A coach who never leaves becomes overbearing and is eventually ignored. 

The test for any feature: would a good coach do this? A good coach surfaces what’s important without overwhelming, doesn’t quiz you constantly, doesn’t punish you for not knowing, brings expertise to the moment then steps back, knows when to interrupt and when to stay quiet. 

This thesis differentiates Bridgeable from competitors — Passare, Osiris, Gather, CRaKN, FDMS, SRS, and equivalents in other verticals — who treat users as competent operators with extra steps. Their software has data entry and dashboards. Bridgeable has a coach. 

For the September Wilbert demo specifically: most licensees are second- or thirdgeneration owners watching veteran staff age out, struggling to onboard younger workers without decades of tribal knowledge. The pitch isn’t “better software for funeral homes” — it’s “software that holds its hand around your newer staff so you can hire and train more easily.” Every feature is a coaching feature. 

## 2. The Three Primitives: Monitor, Act, Decide 

The platform is built on three distinct primitives, each mapping to a verb the user does, each with its own architectural shape: 

|Verb|Primitive|What it does|Shape|
|---|---|---|---|
|Monitor|Spaces (with<br>composed Pulse<br>surfaces)|Surface ongoing work and<br>state proactively|Persistent context<br>the user lives in|
|||Execute discrete actions and|Ephemeral, single-|
|||||



|||||
|---|---|---|---|
|Act|Command Bar|access entities|action surface|
|Decide|Focus|Make bounded decisions with<br>everything needed laid out|Transient, decision-<br>bounded surface|



Tagline (marketing): _Monitor. Act. Decide._ — three verbs, each a true differentiator backed by a distinct primitive. 

Marketing page structure: section per verb with vertical-specific example, fourth section ties them together. Body copy introduces “Focus” as the _how_ of Decide. Internal product language uses “Focus” as the noun for the primitive (“open a focus on the proof review”, “I’m in the scheduling focus”, “Sarah joined the focus”). 

Critical category claim: competitors have data entry and dashboards but no dedicated decision surface. Focus is the gap nobody else fills. 

The three-primitive decomposition is non-negotiable. Each primitive has a specific shape, and the discipline of keeping them distinct is what makes the architecture cohere. The most common failure mode is letting one primitive drift into another’s job — letting Focus become a dashboard, letting Command Bar become a Focus, letting Spaces become a list of disconnected pages. Each primitive section below includes the discipline that prevents drift. 

Naming: Earlier work in this cluster used “decision workspace” or “focused workspace” for the Decide primitive. The canonical name is Focus. “Workspace” is too overloaded in SaaS (Slack, Notion, Google all use it) to carry the architectural weight. Focus does triple duty: noun (a focus), verb (to focus), experience (being in focus). 

## 3. Spaces (Monitor) 

A Space is a persistent context the user lives in: a domain like Funeral Direction, Production, Business, Schedule, or a cross-tenant relationship like “Sunnycrest ↔ Hopkins”. Spaces hold navigation structure and a composed Monitor surface. They are where users _return_ ; they are not where users _focus into_ . 

## 3.1 The Monitor Reframe 

Dashboard-list-in-nav is the wrong primitive. A list of dashboards in nav is a folder structure — a filing system. Filing systems make sense when you’re looking for something you already know exists and roughly where it is. They fail at almost everything else: discovering what’s relevant right now, surfacing what’s changed, combining views across 

domains, adapting to your role and time of day. 

Most SaaS defaults to dashboard-lists because it’s the easy build. Bridgeable rejects this. Each Space has one composed Monitor surface (the Pulse / Home), not a sidebar list of destinations. 

## 3.2 What Monitor Should Actually Do 

If Monitor is the experienced coworker who walks in and says “here’s what’s going on right now that you should know about,” it needs to do five things: 

1. Surface what’s actionable now — your work, your decisions waiting, your urgent items 

2. Show ambient state — the rhythm of the business, what’s normal, what’s flowing 

3. Highlight what’s changed or unusual — anomalies, deviations, fresh information 

4. Provide go-deeper paths — drill into anything on the surface 

5. Adapt to context — role, time, current workload, recent activity, what you usually look at 

A static dashboard list does maybe 30% of #4 and nothing else. 

## 3.3 The Pulse Surface (per Space) 

When a user enters a Space, they land on its Pulse — a composed surface that draws from several layers: 

- Personal layer (top) — your work, your decisions waiting, your @mentions, things assigned to you, focuses you have pending. _“What does this person need to do now?”_ 

- Operational layer (middle) — the rhythm of this space’s domain right now (today’s services, today’s pours, current inventory, active customers — whatever the canonical “ambient state” is). _“What’s happening?”_ 

- Anomaly / Insight layer (interleaved) — Intelligence-detected unusual patterns, items trending toward deadlines, conflicts emerging, opportunities. _“What should I know?”_ 

- Activity layer (sidebar or rail) — recent changes scoped to this space. _“What’s been happening?”_ 

Composition is dynamic. Time of day matters (morning briefing vs end-of-day summary). Day of week matters. Role matters. User behavior matters (if you always check inventory first, that floats up). 

## 3.4 Components of the Monitor Surface 

The Pulse assembles from a set of pluggable components. Same composition machinery serves all of them: 

- Live data widgets — schedule view, inventory levels, queue depths, financial scoreboards 

- Saved views — user-curated filtered Vault views (e.g., “high-value customers due for follow-up”) 

- Anomaly cards — Intelligence-surfaced “this is unusual” items 

- Pending decisions — items waiting for user action with one-click “Open in Focus” affordance 

- Activity stream — recent changes scoped to this space 

- Briefing card — Intelligence-generated summary of what changed since last visit 

- Action shortcuts — common tasks for this space 

- People presence — who else is currently active in this space 

Critically: saved views are components on the Pulse, not separate destinations. The user shouldn’t have to remember “is that thing a dashboard or a saved view or a report?” It’s all one composed surface. 

## 3.5 Editability 

The Pulse is editable — users can rearrange components, hide ones they don’t care about, add saved views, resize. But defaults are role-driven and intelligence-driven, not blankslate. New employees don’t customize their workspace before they know what they need. The platform proposes a sensible composition; the user adjusts over time, often via observe-and-offer (Section 6.1) rather than explicit settings. 

## 3.6 Cross-Space Overview 

Some users — owners, regional managers, anyone with cross-functional scope — need to see across spaces. A top-level Overview composes across all spaces the user has access to, surfacing the most actionable items from each. For most users the Overview isn’t where they live; for leadership it’s the daily landing. 

This shares real estate with the Spaces Overview (Section 3.7) — worth deciding whether they’re the same surface or siblings. 

## 3.7 Spaces Management 

New-space creation: popover handles all settings inline (name, icon, color, default landing 

page, starter nav items). No link out to a settings page. Mirrors the lightweight-creation principle of `event_create_v1` . 

Spaces Overview (“peek”) page: Arc-inspired side-by-side columns of each Space’s nav structure. Drag-and-drop elements between Spaces. Multi-select for bulk operations. Inline add-element using the same configurator as in-space edit (shared edit surface — Vault-asfoundation principle). Templates rail for stamping new spaces from saved configurations. Cross-space element search. Worth being more ambitious than Arc here because Bridgeable’s nav items are richer than browser tabs (pages, saved views, action buttons, agent shortcuts, dashboards). 

## 3.8 Per-Space Color 

Curated palette only (8–12 swatches, all warm-family, all contrast-validated for both light and dark modes). Single semantic token `--space-accent` replaces brass _only_ in spacescoped affordances: 

The active NavDot 

The selected nav-item edge indicator 

The focus ring on inputs within the space 

Optionally a 2px page chrome border 

Brass remains the platform-wide primary action color (Approve All buttons, command bar edge, etc.) — primary action shouldn’t shift meaning between spaces. 

Preferred subtler execution: rather than tinting UI elements, shift `surface-base` by 2–3% chroma toward the space color. This is a peripheral “the light changed” signal, not a “UI is colored” signal. Combined with the colored NavDot and a colored accent stripe on the active nav item, that’s enough to know which space you’re in without anything looking different. 

Constraint: curated palette is non-negotiable. Same logic as the funeral home brandextraction constraint — preventing tenants from picking neon colors protects platform tone the same way it protects their website’s tone. 

## 3.9 The Schedule Space (worked example) 

The existing Scheduling Board is the canonical case for the Monitor reframe. It’s currently structured as a single dashboard. Under the new model: 

Schedule is a Space whose Pulse composes: 

_Personal layer:_ services I’m assigned to today, decisions I have waiting on schedule 

items 

- _Operational layer:_ the unified live schedule across all product lines (calendar/timeline component as centerpiece), filterable inline by domain (vault delivery / Redi-Rock / wastewater / staff / equipment) 

- _Anomaly layer:_ “you have 3 services Tuesday but only 2 directors available,” “delivery to St. Mary’s might hit traffic” 

_Activity layer:_ recent reschedules, new orders that hit the calendar, completions 

Old “Today’s Operations” / “This Week” / “By Product Line” dashboards become _views or filter modes within the unified schedule component_ , not separate destinations. The user switches lens (today / week / month / by product / by staff) inline. 

Quick-edit on the dashboard, real scheduling in Focus. Drag-to-move a slot by 30 minutes? Do it on the Pulse. Reschedule a service that affects three other deliveries and a staffing assignment? The system offers “this affects 4 other items — open in Focus to handle it properly.” The platform doesn’t _force_ the focus — it makes the smart path obvious. 

Don’t kill the existing Scheduling Board. Re-cast it. What’s currently called “Scheduling Board” becomes a component of the Schedule Pulse. Rename it — “Today’s Schedule,” “This Week,” “Operations” — names that signal “this is what’s happening” not “this is where you make it happen.” 

## 3.10 The Dashboard-with-Quick-Edit + Focus-for-Real-Decisions Pattern 

This pattern generalizes beyond scheduling. It’s the standard way operational domains surface in Bridgeable: 

- Inventory — dashboard for current stock with quick-adjust, Focus for rebalancing decisions 

- Compliance — dashboard for status with quick “mark complete,” Focus for resolving an issue 

- PO management — dashboard for outstanding POs with quick approve, Focus for review of complex POs 

- Casework — dashboard for active cases, Focus for arrangement conferences and case decisions 

Quick-edit constraints: allowed for trivial single-item changes (drag-to-move within constraints, single-field edits, mark complete, simple swaps). Blocked for anything that creates a conflict, anything affecting items not currently visible, multi-step changes, anything that would benefit from contextual info the dashboard can’t show. When blocked, 

gentle in-place message offers escalation: “This change affects 3 other items. Open in Focus to see them?” 

The dashboard makes easy things easy and hard things visibly easier in the focus. 

## 4. Command Bar (Act) 

The Command Bar is the platform’s universal Act surface. Invoked with Cmd+K from anywhere. Single-user, ephemeral, lightweight. Used to execute actions, invoke entities, ask questions, and (when the request is decision-shaped) escalate to a Focus. 

The Command Bar is _not_ a Focus and is not allowed to drift into one. Sections 4.4 and 4.5 specify the discipline that prevents this. 

## 4.1 What the Command Bar Does 

Four distinct things in one surface: 

1. Action invocation — “Schedule delivery Tuesday for Hopkins” → action with floating supporting context (calendar, inventory) 

2. Entity invocation — “Hopkins” → entity surfaces with action affordances and relational pivots 

3. Question answering — “How many vaults shipped last month?” → answer with reference-for-answer surface (chart) 

4. Recognition-and-escalation — when a request is decision-shaped, offer to open a Focus instead 

All four obey the same Act-shape discipline. 

## 4.2 Command Bar as Universal Entity Portal 

Type a name. The system recognizes the entity type and assembles relevant contextual surfaces. 

For a customer name: 

Contact card with click-to-call (RingCentral when enabled), text, email, note 

## Recent / open orders panel 

Financial standing panel (if user has permission) 

## Related records as needed 

Each entity type has its own card composition. Permission-respecting via the Vault view model — surfaces the user has permission to see appear, others quietly omit. 

## Generalizes to every entity in the platform: 

- _Customer / family_ → contact, orders, financials, communications, lifetime value, related families 

- _Case_ → status, family contacts, scheduled events, completion checklist, activity, assigned director 

- _Order_ → status, line items, delivery info, related case/customer, payment, production status 

- _Product (vault)_ → inventory, recent orders, production schedule, pricing history, supplier 

- _Cemetery_ → contact, recent interments, current orders, drive time, gate hours, requirements 

- _Staff member_ → contact, availability, schedule, activity, role 

- _Equipment / asset_ → status, location, schedule, maintenance, current operator 

- _Vendor / supplier_ → contact, recent POs, terms, payment history 

- _Invoice / PO_ → status, related entities, payment, line items 

Action affordances and relational pivots. Each entity card has clickable actions (call, text, email, note, “create new order,” “open profile”) AND clickable pivots to related entities. Click an order on the customer’s card → the order’s own entity surfaces appear. Click the cemetery on the order’s card → cemetery surfaces. The user navigates _through entities and their relationships_ without ever navigating through pages. 

This is genuinely different from search-based command bars (Linear, Raycast). Those navigate to entities. Bridgeable’s invokes them into your current context — _the customer doesn’t have to open in a page_ . Everything comes to you, around your current work, and dismisses cleanly when you’re done. 

## 4.3 Floating Contextual Surfaces (for actions and answers) 

Three purposes, all consistent with Act: 

1. Capture confirmation — what’s been parsed (existing overlay does this). Shows the user the system understood without making them re-type or scroll back. 

2. Disambiguation / safety — context that helps the user not make a mistake on the action they’re committed to. Calendar showing Tuesday’s bookings before scheduling a 

delivery for Tuesday. Customer’s recent order pattern when quoting. Inventory level when ordering. _Guardrails for the action in flight._ 

3. Reference for the answer — when the user asked a question, the supporting data backing up the answer (a small chart, a brief table). Interactive but consumed-notdeliberated-with. 

All three stay on the Act side because they support a _single action or query that’s already in flight_ , not an open-ended decision. 

## Visual treatment: 

Float near the command bar (below or beside), not centered on screen 

- Same elevation as the command bar (level 3, brass border) — visually a _family_ with the command bar 

Maximum 2–3 surfaces visible 

- No drag handle, no resize, no persistent affordances — as ephemeral as the command bar overlay 

- Interactive but not editable (user can drill or expand, can’t modify the surfaces themselves) 

## 4.4 The Discipline That Keeps Command Bar from Drifting into Focus 

Six rules. Violating any of them means the surface should be a Focus instead: 

1. Time-bounded by the action, not by the user. Surfaces appear because of what the user is doing right now, disappear when the action completes. The user doesn’t dismiss them — the action does. 

2. No persistent state across invocations. Closing and reopening starts fresh. The user isn’t “returning to” anything. 

3. Lightweight, not full-screen. Floats over the page. Page underneath stays interactive. No blur, no push-back. 

4. One action at a time. Processing one thing the user said. Need to do something else? Invoke again or finish the current thing. 

5. No collaboration. Single-user. No cursors, no chat, no presence. 

6. No “open” state. You don’t “open a calendar” — the calendar appears because you mentioned a date. 

If any of these breaks, the right primitive is Focus. 

## 4.5 Recognition-and-Escalation 

The Command Bar’s Intelligence layer detects when a request is decision-shaped and offers to route it to a Focus. Signals: 

Request is open-ended (“figure out,” “plan,” “decide,” “review”) 

- Request has no specific entity to act on 

- Request references multiple items (“schedule next week’s deliveries”) 

- Request implies comparison or weighing (“what’s the best option for…”) 

User is taking long to refine the request — multiple back-and-forths 

When detected: _“This sounds like more than one action — want me to open a Focus on it?”_ One-click escalation. The Command Bar steps back; the user moves to the right primitive. 

This pattern self-enforces the boundary. The Command Bar can let Intelligence be as forgiving as it wants — anything that gets too big naturally escalates. Users learn the difference between actions and decisions through the platform’s gentle routing. 

## 4.6 Inline Keyboard Disambiguation (universal pattern) 

When Intelligence isn’t sure which option the user meant — “John Smith” matches three records — surface candidates as keyboard-numbered cards in the same surface: 

`1. John Smith (family) — Hopkins FH case, pre-need 2024` 

`2. John Smith (family) — Hopkins FH case, at-need 2026-04-12` 

`3. John Smith (vendor) — Smith Concrete Supply, Cameron NY` 

Three short rows, type pill + just enough disambiguating fields to instantly pick 

Keyboard shortcuts (1-9, or arrow + Enter) 

Total interaction time: ~800ms typing-to-acting 

Intelligence picks WHICH fields to show as differentiators, based on what would help the user choose. Same data-shape inference principle as Focus pin suggestions and activity feed filtering. 

Always include the escape hatch: “Don’t see what you’re looking for? [Add new family] [Add new vendor] [Refine search]”. Critical for at-need cases — every new family starts with a name the system has never seen. 

The pattern is universal. Same component, same keyboard handling, same escape hatch, deployed everywhere ambiguity exists: command bar entity portal, action confirmations, 

Focus pin choices, anywhere Intelligence isn’t sure. 

Why this matters: Intelligence-driven recognition will never be perfect. A platform that pretends Intelligence is perfect will fail catastrophically on edge cases (especially in funeral homes where wrong-family is a disaster). A platform with clean inline disambiguation can let Intelligence be as good as it can be, knowing the worst case is a 1-second pick from a card list. That trust is what lets users invoke the command bar with casual queries instead of careful precise ones. 

## 4.7 Chip-Driven Conversation (the multi-step pattern) 

When the user commits to an entity or parameter, the typed text collapses into a chip on the left of the input, freeing the input for the next thing. 

User types “John Smith” → picks family from disambiguation 

- `[John Smith]` chip appears on left, input clears 

User types “schedule delivery” 

- `[John Smith] [schedule delivery]` chips, input clears 

User types “Tuesday 10am” 

- `[John Smith] [schedule delivery] [Tuesday 10am]` chips 

- Confirmation surface appears with all parameters + safety context (calendar, inventory) 

User hits Enter to confirm 

Chip-ify on commitment, never on time. Triggers: picking a disambiguation option, accepting an autocomplete (Tab on single match), Enter on unambiguous match. While the user is still typing, no transformation. Time-based clearing is always wrong because it removes user agency over what’s still working text. 

Shift+Tab walks back into chips. Chip slides back into input as editable text, cursor at end. Walks one chip at a time, most recent first. Tab moves forward. The user navigates the chip stack like a stack of completed thoughts. 

Visual transition: chip “unpacks” into text in ~150–200ms, brief enough not to feel ceremonial. Same motion played in reverse on chip-ification. 

Edge case — mid-typing Shift+Tab: the current input text becomes its own chip-inprogress (dashed border or muted color), pushed right of existing chips. Shift+Tab then walks into the previous committed chip. Nothing is lost. 

After chip creation, when input is empty: show common actions for the entity below the 

input — “Common actions: Call · Text · Email · Note · New Order · Open Profile” with keyboard shortcuts. Suggestions disappear the moment user starts typing. Serves new users (discoverability) without slowing power users. 

The cumulative pattern is conversational with memory. The chips visibly hold what’s been established so far. Same as a good chat: the assistant doesn’t ask you to repeat yourself. 

## 4.8 Real-Time Interpretation (interpretation chips + pause sensor) 

NL command bars are typically _intent-opaque until they execute_ — the user types a sentence, hits enter, and either the system did the right thing or the wrong thing. That’s a quiet anxiety in every NL interface. Bridgeable’s command bar makes the system’s interpretation visible _while_ the user is typing, so the user can catch misinterpretations early and never be surprised by the result. 

Two mechanisms work together: interpretation chips (show what the system thinks) and the pause sensor (show it at the right moment). 

## 4.8.1 Interpretation Chips 

Different from commitment chips (Section 4.7). Commitment chips are solid because the user committed to something specific. Interpretation chips are lighter — outlined, dotted, or muted — because they show the _system’s hypothesis_ about what the user is doing, not something the user has confirmed. 

|Chip type|Trigger|Visual|Behavior|
|---|---|---|---|
|Commitment<br>chip|User commits to an<br>entity, action, or<br>parameter|Solid fill,<br>brass border|Persists until user shift-tabs<br>back|
|Interpretation<br>chip|System forms a<br>confident hypothesis<br>about intent|Outlined /<br>muted /<br>dotted border|Updates as interpretation<br>changes; can be dismissed or<br>corrected|



Example flow. User types: `Ferguson Funeral Home Sacred Heart Cemetery Full Equipment` 

Early in typing ( `Ferguson Funeral Home` ) the system has multiple candidate interpretations — lookup, order entry, quote, scheduling. Confidence is too low to commit to a chip. 

By `Ferguson Funeral Home Sacred Heart Cemetery` , the system has stronger signal (two entities commonly co-occurring in order/delivery contexts). Hypothesis firming but still 

## uncertain. 

By `Full Equipment` (product/service language), the system is confident: this is an order. Interpretation chip appears: `[Order]` — outlined, muted, at the top of the input or as the leftmost chip in the stack with distinct treatment so it reads as _frame_ not as a parameter. 

Confidence threshold, not time. The chip appears when the system’s confidence crosses ~70%+ — when flipping to a different interpretation would require the user to actively contradict what they’ve typed. Below that threshold, no chip. Short queries may never show one until they’re nearly complete; longer queries show it earlier. Either is honest. 

## Correction paths. 

- _Click the chip_ → dropdown of alternative interpretations the system considered ( `[Order] | [Delivery Schedule] | [Quote] | [Search]` ). User picks the right one; system re-parses typed input against corrected intent. 

- _Keyboard shortcut_ (e.g., Cmd+I for “inspect interpretation”) — same result, no mouse. 

- _Type a contradicting phrase_ — “actually this is just a delivery for an existing order” — system updates the chip. 

## Visual treatment ideas (to prototype): 

- Small icon + concise one-word label (document icon + “Order”) rather than raw text 

- Evolves with commitments: `[Order]` → `[Order: Ferguson]` as entities are committed, so the frame becomes more specific 

- Animated firming: brief pulse/fade-in when the chip first appears (“I just figured this out”), then settles quietly. Reinforces that this is the system understanding in motion, not a static label. 

Position probably _above_ the input or as leftmost chip with clearly distinct visual treatment — it’s the frame for the whole session, not a parameter in the sequence. 

## 4.8.2 Pause Sensor (when contextual surfaces appear) 

The chip pattern needs a companion: when does the _full contextual information_ (entity cards, order panels, calendar, inventory checks) appear? Not on every keystroke (flicker), not only on Enter (too late). The answer: when the user pauses. 

The user’s typing rhythm contains intent information that text alone doesn’t. Typing “Ferguson Funeral Home” and immediately continuing = mid-sentence, don’t interrupt. Typing “Ferguson Funeral Home” and stopping = unit of thought completed, user is checking or thinking about what’s next. Most NL interfaces ignore this signal; Bridgeable’s 

uses it. 

Threshold. ~500–700ms between keystrokes. Below ~400ms catches normal mid-typing rhythm pauses (flicker). Above ~1000ms feels unresponsive. The sweet spot is around half a second past last keystroke. 

Adaptive per user. The platform learns each user’s typing rhythm over time via the observe-and-offer infrastructure (Section 6.1). Fast typists have shorter natural pauses; slower typists have longer ones. The threshold tunes behaviorally over a week of use — no setting required. 

## What counts as a pause-trigger: 

- Time elapsed since last keystroke (primary signal) 

- Cursor position change without typing (user clicked elsewhere or arrow-key navigated — they’re inspecting, not composing) 

End-of-word space + brief pause (softer signal — completed a unit) 

Behavior on pause. Pause threshold crosses → contextual surfaces fade in (~200ms). Entity cards appear for entities mentioned. Interpretation chip, if present, stays visible. Confirmation surfaces appear if the system has enough to propose an action. 

Behavior on resume. User starts typing again → surfaces fade out (~200ms). System goes back to listening mode. Interpretation chip may update as more input arrives. 

Minimum visibility duration. Once surfaces appear, they have ~1 second minimum visibility before resumed typing can dismiss them. Without this, pause-then-immediatelyresume produces a flicker (surfaces appear and instantly vanish). With the minimum, the visual rhythm stays smooth — system keeps parsing the new typing in the background, UI just doesn’t flash. 

Fade, not snap. All transitions use `ease-settle` (200ms). Surfaces don’t pop in or disappear — they arrive and leave gracefully. Matches the design language’s restraint principle and keeps the interaction rhythm continuous rather than stuttering. 

## 4.8.3 How Chips and Pause Work Together 

The interpretation chip and pause-triggered surfaces are two halves of one design pattern: _making the system’s interpretation visible at the right moment._ 

- _Interpretation chip_ — continuous signal while typing. “I think this is an order.” Persistent quiet indicator. 

_Pause-triggered surfaces_ — punctuation. “You paused; here’s what I have so far.” 

Heavier contextual info appears. 

They compose cleanly. The chip can appear mid-typing when confidence crosses threshold (doesn’t wait for pause). The surfaces wait for the pause because they require user attention. Together they implement the coaching rhythm: _a good coach watches you work, doesn’t interrupt mid-thought, waits for the natural pause and offers “here’s what I think you mean — does that look right?”_ 

Without these mechanisms, the system feels like a know-it-all interrupting constantly. With them, the system feels like a coach who’s listening. Most NL interfaces are pause-blind; Bridgeable’s command bar that _waits for you to think_ is a polish detail that changes the whole feel of the interaction. 

## 4.9 Why This Is Competitively Significant 

Most operational software requires navigation to entities (open customers page, search, click, see record, navigate to orders tab, navigate back, click email, etc.) — each step a tax. Most multi-step actions require forms — slow, rigid, hostile to natural language. 

Bridgeable’s command bar collapses all of that into one surface. _Type to find. Act in place. Speak parameters in any order. Walk back to refine._ The competitive frame: competitors make you go find information; Bridgeable brings information to you, in floating context, wherever you are. 

For the September Wilbert demo: this is showable in 30 seconds. Director invokes command bar, types “Hopkins,” picks the family from disambiguation (chip slides left), types “schedule delivery,” types “Tuesday 10am,” confirms. ~8 seconds for a complete multiparameter action. 

## 5. Focus (Decide) 

A Focus is the platform’s bounded-decision primitive — a full-screen overlay where a specific decision happens with everything needed laid out. The third leg of Monitor / Act / Decide. 

## 5.1 The Primitive 

Full-screen overlay 

- Backdrop blurred + slightly darkened + scaled ~2–3% (push-back effect) 

- Anchored core decision surface at the center — can’t be moved, can’t be lost 

- Free-form canvas around the core for pins, widgets, and contextual panels — drag, 

resize, snaps to 8px grid 

Soft maximum on visible widgets; overflow lives in a side rail 

Click backdrop to dismiss; reverse animation returns to underlying page 

Not a page (which is part of nav structure). Not a modal (which interrupts). Not a panel (which docks). A new primitive: temporary, goal-bounded, decision-focused surface. 

## 5.2 Core Modes 

The anchored core takes different modes based on the workflow’s shape: 

|Workflow|Core mode|
|---|---|
|Personalization request<br>processing|Triage queue (superhuman-style rapid processing with<br>shortcuts)|
|PO review|Triage queue|
|Funeral scheduling|Kanban board (drag-and-drop spatial arrangement)|
|Disinterment scheduling|Kanban / calendar|
|Quote building|Edit canvas|
|Proof revision|Edit canvas|
|Arrangement conference|Single-record (case file + live completion panel)|
|Proof review|Single-record (proof image + edit/approve tools)|
|Inventory rebalancing|Multi-location matrix|



Triage is one mode, not the primitive itself. The earlier conflation of “triage” and “the workspace primitive” is wrong. Triage specifically means the superhuman-style queueprocessing pattern (keyboard shortcuts, swipes, blast through). Other modes are not triage. All share the same enclosing primitive (the Focus). 

## 5.3 What Focus Absorbs 

These workflows should be Focuses, not pages: 

Funeral scheduling (Kanban core) 

Arrangement conference (case file core) 

Quote building (edit canvas core) 

PO review (triage queue core) 

Disinterment scheduling (Kanban / calendar core) 

- Personalization request processing (triage queue core) 

Proof review / revision (edit canvas core) 

Inventory rebalancing across locations (matrix core) 

Pattern: decision-heavy + context-hungry + bounded-by-specific-decision → Focus. 

## 5.4 Pins (contextual surfaces around the core) 

Three tiers: 

1. System-suggested pins (Intelligence) — “you have items with location fields, want a map?” Inferred from data shape across the items in scope, not hardcoded per-Focus type. Cross-vertical: the same data-shape inference works for funeral cemeteries, wastewater install sites, Redi-Rock job locations. 

2. Saved pins — user/admin defined per Focus type. Persist across sessions. 

3. Ephemeral pins — pinned by the user for a single session. 

Pins are parameterized. Static pins (always-same query) or context-aware pins (query parameters bound from Focus scope at render time). Examples of context-aware pins for funeral scheduling: 

- _Cemeteries with orders today_ — Vault view filtered by `cemetery_id IN (cemeteries on the canvas)` . Updates as Focus contents change. 

- _Drive-time matrix_ — computed widget taking the same cemetery set as input, calling a maps API. 

- _Staff availability_ — Vault view filtered by `date = currently-being-scheduled date AND role IN (...)` . 

_Equipment / vehicle availability_ — same pattern, scoped to the date. 

Pins are Vault views or parameterized widgets. No new infrastructure. 

## 5.5 Selection-as-Query 

Multi-select on the core surface (shift+click) drives contextual widgets and actions. Singleselect shows item detail; multi-select shows cross-item relationships. 

## Examples: 

- Select 2 funerals → route + drive time, conflict indicator if time gap < drive time 

- Select 3+ funerals → optimized route (TSP-style), total drive time, suggested ordering 

- Select 2 orders to same cemetery → “consolidate?” with one-click merge 

- Select an order + a staff schedule entry → conflict check 

- Select multiple POs → combined supplier view, total spend, delivery date overlap 

- Select multiple personalization requests → “share vault model — batch approve?” 

Intelligence infers which widgets apply from shared data shape across the selection — same mechanism as system-suggested pins. Cross-vertical: a wastewater installer selecting 3 install jobs gets the same map+route widget for the same reason. 

Selection-context widgets replace standing pins inline while selection is active, revert on deselect. Selection doesn’t persist across Focus exits. 

## 5.6 Exit and Re-Entry 

Click backdrop to dismiss → returns to underlying page with reverse animation. 

Return-pill appears bottom-center: label (“Funeral Scheduling Focus · 3 items”) + backarrow + 15-second countdown bar (brass at low opacity along the bottom edge of the pill). 

- Hover pauses countdown. Resume on mouse-leave from where it stopped. 

- State change re-arms the pill. If the Focus state changes during countdown (new item enters, item gets claimed by someone else, Intelligence alert fires), pill re-appears full 15 seconds with subtle change indicator (space accent color pulse or small dot). 

- Only the most recent exit gets a pill. Older Focuses accessible via Cmd+K history. Otherwise pills stack and the whole point of restraint dies. 

- Triage state preserved server-side after dismissal — the Focus isn’t gone, just the fast-return path expires. 

After dismissal, paths back to a Focus: 

- Cmd+K → “open funeral scheduling focus” (universal escape hatch) 

- The Focus’s normal entry point (wherever it lives in the Space’s nav or Pulse) 

- Recent / pending Focuses section, Spaces Overview 

5.7 Layout State 

Three-tier persistence: 

1. Tenant default — admin-set baseline composition for this Focus type 

2. Per-user override — saved automatically when user rearranges 

3. Per-session ephemeral — resets on Focus exit 

Same three-tier pattern as pins. 

Smart positioning engine (shared cross-vertical) places new widgets in open regions, prefers edges over center, places near relevant content. Worth solving once well. 

Widget chrome (drag handle, resize corner, dismiss X) ghosted by default, appears on hover or touch. Restraint principle: affordances visible when needed, invisible when not. 

Touch / iPad uses preset zones (left rail, right rail, bottom strip) instead of true free-form. “Tidy up” button auto-arranges if someone makes a mess. 

## 5.8 Live Presence and Collaboration 

Cursors: per-user colored cursors with name pill. Soft cap ~4 visible; rest in avatar stack. Idle cursors fade after 30s. Off-screen users get edge indicator pointing toward them. 

## Highlights and locks: 

- _Ephemeral highlights_ — click, hover, selection get a brief colored pulse (~800ms) in the user’s color 

- _Persistent edit locks_ — dragging a card puts a colored border on it, others can’t grab until release 

- _Detail panels_ — opening a detail outlines it in user’s color so others see what they’re looking at 

Selection-context widgets are personal-scoped (route maps, conflict checks, etc. that appear when _you_ shift-select aren’t visible to others). One-click “share with room” promotes them to shared. 

Async catch-up summary. When a user joins a Focus that others have been working in, show a brief Intelligence-generated summary at top: _“Mike moved 3 services, commented on 2 cards, flagged a staff conflict.”_ Glanceable, dismissable. Eliminates “wait what did you do” friction. 

Infrastructure: real-time transport (websockets) + presence service. Cursor-level presence is a different volume than the existing SSE used for Call Intelligence. Strong argument for Liveblocks/Yjs integration (~2 weeks) over building from scratch (~6 months) — matches 

integrate-now-make-native-later framework. 

Permissions: plug into existing Vault view permission model. Not bespoke. 

## 5.9 Inline Chat 

- Docked rail right-side, collapsible, unread badge on icon when collapsed, pop-out to floating 

- Scope is the Focus (not a general channel) — chat is persistent with the Focus’s history 

- Anchored comments (the killer feature): shift+click an item on the canvas, hit 

- “comment” — message in chat shows `[on Johnson service]` and the card gets a small comment count badge. Click the badge to scroll chat to relevant messages. Turns chat into structured decision history rather than ephemeral talk. 

- @mentions while in-Focus = subtle ping, not a notification (the person is already here) 

## 5.10 Activity Feed (the COD killfeed pattern) 

Top-right of the Focus, fixed to viewport. Ambient awareness of events _outside_ the Focus that affect _this_ decision. 

## Scope: 

- Events outside the Focus that touch records currently in scope (new order for current date, cemetery closure for cemetery on canvas, staff callout, pinned widget data change) 

- Intelligence insights (“5 services today cluster around 2 cemeteries — want to see route?”) 

## Not: 

- Other users’ actions inside the Focus (cursors and highlights handle that — no doublesignal) 

- General notifications unrelated to this Focus 

- Out-of-scope events 

Filter is context-aware per Focus type via Intelligence — same data-shape inference as pin suggestions. 

## Behavior: 

- Items slide in from right with `ease-settle` , push older down 

Max 4–5 visible, older fade 

- Auto-dismiss ~8s for routine items, ~20s for higher-signal (cancellations, conflicts) 

- Hover pauses all dismissals 

Click an item → scroll canvas to affected record + briefly highlight 

## Item taxonomy: 

- _Addition_ (+) — new records entering scope; subtle positive accent 

- _Removal_ (−) — cancellations, deletions; subtle warning accent 

- _Change_ (refresh) — status updates, reschedules; neutral 

- _Conflict / Alert_ (warning) — `status-warning` or `status-error` , longer dismiss 

- _Intelligence Insight_ (brass + sparkle) — no auto-dismiss until acknowledged 

## Restraint dial (cry-wolf is the biggest risk): 

- Per-user verbosity setting (verbose / standard / minimal, default standard) 

- Admin-level event-type filtering per Focus 

- Per-hover “mute this type for this session” option 

Future consideration: platform-level urgent activity channel for cross-Focus critical events that should pull users back to an exited Focus via re-armed return pill. 

## 5.11 Three Channels of Awareness 

Focus separates three distinct channels, each with its own visual/temporal treatment: 

1. Persistent state — the canvas itself, what’s true now 

2. Live presence — cursors, highlights, locks, what others are doing now 

3. Ambient events — activity feed, what’s changed elsewhere that affects this 

Three time horizons, three channels. Most software jams all three into notifications, which is why notifications are universally hated. Worth featuring on the marketing page as a Monitor differentiator (the channels span Monitor and Decide). 

## 5.12 Access and Invitations 

## Two-axis access model: 

_Role-scoped Focuses_ — default audience via the Space/nav (e.g., funeral scheduling for 

all directors). Most Focuses use this. 

- _Invited Focuses_ — granted access to a specific Focus instance (e.g., inventory rebalancing for owners only). Have an explicit owner. 

Triage access extends the existing Vault view permission model. Not bespoke. 

## Invitation flavors: 

1. _Permanent_ — ongoing access until revoked. Audit-logged. 

2. _Session-scoped_ — ends when the user closes the Focus. 

3. _Time-bounded_ — expires at a specified date/duration. 

4. _Decision-bounded_ — ends when a specific work unit in the Focus resolves. Most Bridgeable-feeling because it auto-revokes on completion (solves the security footgun of forgotten temp access). 

View-only flavor for audit and stakeholder cases — see canvas, activity, history, but can’t drag, can’t action, can’t comment (or comments go to a separate “observer” thread). 

Invitation flow via command bar natural language (“invite Sarah until Friday”). Not a separate permissions UI. Owner-only invites by default; grant-invite-power available. 

## 5.13 Guest UX 

When an invited user enters a Focus they didn’t have role-scoped access to: 

- Clear guest indication — distinct cursor treatment, chat avatar with guest badge, topcenter “here until X resolves” affordance 

- Scoped item access — only the items that caused them to be invited, not the full canvas 

- Async catch-up summary especially important for guests joining mid-context 

- Graceful exit — when access ends, notification + pill-style summary of what was decided 

Discovery: “Focuses” section in Cmd+K grouped role-scoped vs. invited; subtle indicator in hub when invited Focuses have pending attention; visible in the Spaces Overview. 

## 5.14 The Bounded-Decision Discipline (anti-pattern guard) 

Every Focus must be bounded by a specific nameable decision. If you can’t name the decision the Focus is for, it’s not a Focus — it’s a dashboard with delusions, and it belongs in a Space. 

## Tests: 

- “What decision does this close out?” 

- “When does the user exit?” 

If the answer is “when they’re done looking around,” the wrong primitive was chosen. 

Why this matters: without this discipline, Focuses drift into being persistent dashboards wrapped in a blurred overlay, which would collapse the architectural distinction between Spaces and Focuses. The primitive loses its meaning. Hold the line. 

Test in context: cross-tenant personalization. A first attempt at this designed a “persistent shared triage between FH and manufacturer” — which was actually a dashboard, not a Focus. The corrected decomposition (Section 7.3) puts persistent collaboration in a shared Space with shared dashboards, and reserves Focuses for specific decisions (proof review, proof revision, timing conflict resolution). 

## 5.15 Implementation Foundation 

Phase A Session 1 (April 2026). Documented here to prevent future sessions from rebuilding primitive Dialog functionality. 

The Focus primitive is implemented atop `@base-ui/react/dialog` (`Dialog.Root` / `Dialog.Portal` / `Dialog.Backdrop` / `Dialog.Popup`). Focus IS an opinionated, scoped use of Dialog — full-screen, decision-bounded, with an anchored core and a free-form canvas for pins. The Dialog primitive provides: focus trap, ESC handling, `role="dialog"`, portal rendering, controlled-open/onOpenChange state plumbing, backdrop-click dismiss. Custom chrome layered on top: heavier backdrop blur (12px vs Dialog's 4px) to signal push-back per §5.2; larger anchored core with `shadow-level-3`; free-form canvas and pin system (Sessions 3 + 5–6); return pill (Session 4 adds the 15s countdown); Focus Chat (Session 7). 

This choice was made after verifying that `framer-motion` is not a dependency of the codebase (the Aesthetic Arc's overlay family — Dialog, Popover, DropdownMenu, Tooltip, SlideOver, Select, PeekHost — all use base-ui primitives with `data-open:animate-in` / `data-closed:animate-out` Tailwind utility classes driven by `--duration-arrive` / `--duration-settle` / `--ease-settle` / `--ease-gentle` tokens). Adopting `framer-motion` for Focus only would have introduced a parallel animation pipeline. Building on Dialog keeps Focus inside the overlay family aesthetically and inherits every accessibility affordance the family already ships. 

Push-back scale on the underlying app (§5.2 signal) **ships in Session 2**. The scope risk identified in Session 1 (CSS `transform: scale` creates a containing block for `position: fixed` descendants on Safari + some Chromium builds) is resolved by applying the transform to the `<main>` element inside AppLayout — which has no fixed-positioned descendants. DotNav and ModeToggle live in the sibling `<Sidebar>` and `<header>` elements, which are NOT descendants of `<main>`, so the transform's containing-block effect cannot reach them. Attribute-driven (`main[data-focus-pushback="true"]`) keyed on `useFocus().isOpen`. Transition matches Focus enter/exit timing (`--duration-arrive` / `--ease-settle`). Reduced-motion users inherit the instant transition per the global `prefers-reduced-motion` retrofit in base.css. CSS rule lives in `frontend/src/styles/base.css`. Verified in Chromium during Session 2 build; sidebar + header remain viewport-anchored while main content scales to 0.98.

Command Bar and Focus are mutually exclusive surfaces. Command Bar is hidden while a Focus is open (both its render and its `Cmd+K` keyboard shortcut are gated on `useFocus().isOpen`). This is bounded-decision discipline in implementation: Act and Decide are distinct primitives with distinct shapes, and mixing them inside one screen breaks the boundary. Information-lookup needs inside a Focus are answered by Focus Chat (Session 7), a scoped Q&A surface specific to the active Focus — not by escaping to the Command Bar. 

## 6. Cross-Cutting Principles 

## 6.1 Observe-and-Offer (the truest “opinionated but configurable”) 

The platform watches user behavior, detects when behavior contradicts current configuration, and proactively proposes a configuration change. 

Loop: detect → propose → accept / decline → learn. 

## Examples: 

- _Monitor:_ “I notice you check the cemetery contact list every Monday morning. Want me to surface it in your Pulse?” 

- _Command bar:_ “You’ve typed ‘show today’s services’ three days in a row. Want a quickaction button for it?” 

- _Pins in Focus:_ “You always pin the family preferences widget when reviewing proofs. Want me to make it a saved pin for proof review focuses?” 

- _Notifications:_ “You’ve muted three notifications about purchase orders this week. Want me to lower their priority?” 

- _Saved views:_ “You’ve manually filtered the case list by ‘high-value’ four times this week. Want me to save that as a view?” 

## Design principles: 

_Quiet, not nagging._ Small, dismissible suggestion. Not a modal, not an interruption. 

- _Right time, not constant._ Suggest after a clear pattern (3–5 instances over a reasonable time window). Premature suggestions annoy; well-timed feel insightful. 

- _Respect “no thanks” properly._ If user dismisses, don’t ask again for that thing for a long time (months). 

- _Frame as a question, not an action._ “Want me to add this?” not “I added this for you.” User remains in control. Auto-adding things behind the user’s back is what makes platforms feel creepy. 

_Show what changed._ When the user accepts, show where it landed. 

Reverse pattern for pruning: notice when configured things aren’t being used and offer to remove them. _“You haven’t looked at the staff utilization widget in 3 weeks. Want me to remove it from your Pulse?”_ Keeps configuration from accreting clutter as roles change. 

Infrastructure: behavioral analytics on user interactions with the platform itself (not just business analytics on data). Privacy/trust consideration — settings entry: “Bridgeable learns from how you use the platform to make it better. Here’s what it’s noticed about you. You can pause this.” Same model as the Memories panel in Claude.ai. 

Lives in the Bridgeable Intelligence backbone. Detect-pattern-and-suggest is a generic capability called from many places: Monitor composition, command bar suggestions, pin suggestions, notification tuning. Not reimplemented per feature. 

## 6.2 Intelligence with Graceful Failure 

Intelligence-driven recognition will never be perfect. The honest design move: make Intelligence’s failure modes graceful and fast. 

When Intelligence isn’t sure, the platform asks — fast, gracefully, with enough information to decide. This is what builds trust. Users can invoke Intelligence with casual queries instead of careful precise ones, knowing the worst case is a 1-second pick from a card list — not “the system did the wrong thing.” 

Same principle applies across: 

- _Command bar disambiguation_ — keyboard-numbered candidate cards (Section 4.6) 

- _Interpretation chips + pause sensor_ — system’s in-flight hypothesis made visible while user is typing; corrected early, not after submission (Section 4.8) 

- _Focus pin suggestions_ — multiple options when Intelligence isn’t sure which pin is relevant 

- _Monitor anomaly surfacing_ — softer signal when uncertain, dismissable 

- _Action parsing_ — inline ask for clarification with options 

_Observe-and-offer_ — propose, don’t impose 

## Two expressions of the same principle: 

- _Uncertainty expression_ — when Intelligence isn’t sure, show candidates and let the user pick (disambiguation cards, anomaly softer-signal, clarification options). 

- _Real-time expression_ — when Intelligence has a confident hypothesis but the user hasn’t confirmed, show the hypothesis in-flight and let the user correct before it matters (interpretation chips, pause-triggered surfaces). 

The thread running through it all: Intelligence proposes, the user disposes. Always. That’s what makes Intelligence useful rather than obnoxious. 

## 6.3 Architectural Tests (compounding) 

Three tests at different altitudes, each a usable filter for any feature decision: 

1. Vault-as-foundation — does this respect the data architecture, or create reconciliation burden? (data-architecture altitude) 

2. Bounded-decision — does this Focus close out a specific decision, or is it secretly a dashboard? (primitive-boundary altitude) 

3. New-employee-coaching — would a good coach do this for someone new? (userexperience altitude) 

A feature passing all three is probably right. A feature failing any of them is probably wrong. 

## 6.4 Each Primitive Has Supporting Context — But the Shape Tells You Which Primitive Owns It 

The Intelligence engine, the Vault data, and the basic concept of “context surfaces around a primary surface” are shared across all three primitives. What differs is composition rules and persistence rules: 

|Primitive|Context shape|Persistence|Bounding|
|---|---|---|---|
|Spaces /<br>Monitor|Composed by<br>Intelligence into the<br>Pulse surface|Persistent, customized over time<br>via observe-and-offer|The<br>Space’s<br>domain|
||Floats around the action|Ephemeral, action-bound,|The single|



|||||
|---|---|---|---|
|Command<br>Bar / Act|surface|vanishes on completion|action in<br>flight|
|Focus /<br>Decide|Arranged on free-form<br>canvas around the core|Decision-bounded, persists per-<br>user/per-tenant with smart<br>defaults|The named<br>decision|



Same Intelligence, same Vault, three different shapes governed by what each primitive is for. Holding these distinctions is what keeps the architecture from collapsing. 

## 7. Cross-Location and Cross-Tenant 

## 7.1 Cross-Location (multi-location tenants) 

Unifying frame: load balancing. Cross-location work is almost always about balancing something across the tenant’s locations — inventory, capacity, staffing, compliance burden, assets. That’s the unifying mental model. 

Architecture: lives in a leadership-scoped Space with dashboards showing cross-location state. Decision Focuses launched from those dashboards for specific moves (rebalance, reassignment). 

- Dashboards = persistent visibility (Monitor) 

- Focuses = bounded decisions (Decide) 

## Examples: 

- _Inventory rebalancing_ — dashboard shows imbalance, Focus opens for specific transfer decisions with transfer cost math, route maps, truck schedules 

- _Production load balancing_ — dashboard shows queue depths across plants, Focus opens to drag jobs between plant queues 

- _Cross-location staffing_ — dashboard shows availability gaps, Focus opens for shift coverage decisions 

- _Cross-location compliance_ — dashboard shows status across locations, Focus opens for resolving specific compliance gaps 

- _Asset/equipment deployment_ — dashboard shows asset calendar across locations, Focus opens for reassignment 

Typically uses invited access (leadership, regional managers), not role-scoped daily ops. 

Vault views aggregate across **`location_id`** within tenant boundary. Plug into existing permission model. 

## For September Wilbert demo specifically: multi-location compliance dashboard + 

network inventory sharing as network-effect pitches for the licensee audience — _“the more of you on Bridgeable, the more valuable Bridgeable becomes.”_ 

## 7.2 Cross-Tenant 

Bridgeable already has a three-way cross-tenant relationship in the FH ↔ manufacturer ↔ cemetery model ( `fh_02_cross_tenant` migration). This is proof-of-concept latent in the existing data model. 

Architecture: shared cross-tenant Space with shared dashboards (persistent collaboration context) + decision Focuses launched from dashboards (bounded decisions). Not one mega-Focus. 

## High-value cross-tenant workflows: 

- _Delivery coordination_ — currently happens via phone + Excel between FH, manufacturer, cemetery. Genuinely novel as a shared Focus. 

- _Network inventory sharing_ — Wilbert licensees back each other up with inventory. Currently informal; could formalize on Bridgeable. Strong network-effect pitch. 

- _Compliance benchmarking_ — anonymized aggregates across the network (“your plant is at 94% completion, network average 87%, top quartile”). 

- _Multi-party disinterments_ — currently painful specifically because cross-tenant. Highvalue to solve. 

- _Personalization_ — see Section 7.3 (canonical worked example). 

Decision-bounded invitations are a natural fit — auto-expire on completion, no permanent cross-tenant accounts needed. 

Consent / data sovereignty model is a trust primitive. What does each tenant see about each other? A manufacturer seeing an FH’s case file is privacy violation. An FH seeing a manufacturer’s internal production schedule is competitive leakage. The shared dashboards/Focuses only show what all parties have consented to share for the purpose of this coordination. This is the differentiator from “just build APIs between systems.” 

## 7.3 Cross-Tenant Personalization (canonical worked example) 

This is the prototypical cross-tenant case and the cleanest test of the shared-Space + dashboards + Focuses decomposition. 

Shared Space: “Sunnycrest ↔ Hopkins” (framed appropriately per side — “Manufacturing Partners” on FH side, “Customers” on manufacturer side; same underlying shared Space). One Space per FH ↔ manufacturer relationship. 

## Shared dashboards within the Space: 

- Active personalization items by proof status (awaiting proof, awaiting FH review, awaiting family review, approved, in production, shipped) 

- Timing pipeline (when each item ships, against service date) 

- Historical proofs and decisions 

Relationship-level notes (“this family always wants block letters”) 

## Decision Focuses launched from dashboards: 

- _Proof review Focus_ — core: the proof image. Pinned: engraving rules, original order details, past proofs for this family if repeat customer, service date and timing context. Decision-bounded: approve, request revision, escalate. Closes when decision made. 

- _Proof revision Focus_ (manufacturer side) — core: edit canvas. Pinned: original proof, FH’s change request, engraving rules, prior revisions. Decision-bounded: submit new proof version. Closes when sent. 

- _Timing conflict Focus_ — core: production schedule. Pinned: service date, FH’s urgency, alternate scheduling options. Decision-bounded: commit to a new delivery date. Closes when resolved. 

Family stays outside the Focus entirely. Family interacts via the proof approval portal (link, email with approve/reject buttons) which updates the shared Space automatically. Keeps the professional collaboration surface clean while the family-facing layer stays simple. 

## Items flow through the dashboard; decisions happen in Focuses. Automation drives 

items into the dashboard (new order with personalization → automatic item creation, status transitions as events happen). The Focuses are entered from the dashboard for specific decisions, dismissed when the decision is made. 

For September Wilbert demo: personalization is an ideal second workflow to show after funeral scheduling — exercises cross-tenant Focuses, visually compelling (proofs are images, iteration is visible), solves a real acknowledged pain point, and the Sunnycrest + Hopkins demo seed already exists. 

## 8. Open Questions and Future Considerations 

These are decisions deferred or topics flagged for future workshopping. 

## 8.1 Build Sequencing for September 

Single-tenant Focus primitive is plausible for September demo. Cross-location is doable if the data model already supports multi-location. Cross-tenant Focuses are almost certainly post-September, but a _mocked preview_ of cross-tenant delivery coordination as part of the vision pitch could be powerful in the Wilbert room. 

When the aesthetics arc completes, sequencing conversation should cover: which Focus(es) ship for September? Which Monitor surfaces are reframed for September vs. later? Live collaboration is probably post-September (cursors etc. don’t need to land for the Wilbert demo). 

## 8.2 Naming of the Pulse Surface 

“Pulse” is the working name for each Space’s primary Monitor surface. Alternatives: “Live View” (descriptive but flat), “Home” (clear but generic), “The Surface” (too abstract). Decide before building. 

## 8.3 Spaces Overview vs. Cross-Space Overview 

Two distinct uses currently described as overlapping: 

- _Spaces Overview (“peek”)_ — the management/edit surface for nav structures across spaces (Section 3.7) 

_Cross-Space Overview_ — the leadership Pulse composing across spaces (Section 3.6) 

May share real estate. May be siblings. Worth deciding. 

## 8.4 Monitor’s Default Landing per Space 

Each Space’s Pulse should be role-defaulted (Funeral Direction → director-shaped composition; Production → plant manager-shaped). Configurable per-user with sensible role defaults. Specifics TBD per Space. 

## 8.5 Action Suggestions in Empty Command Bar 

When the input is empty (after an entity chip is created), should common actions for the entity show below as keyboard-shortcut-numbered options? Lean: yes, with restraint. Suggestions disappear the moment the user starts typing. Serves new users without slowing power users. 

## 8.6 Platform-Level Urgent Activity Channel 

Future consideration: critical cross-Focus events that should pull exited-Focus users back via re-armed return pill. Not the per-Focus activity feed (Section 5.10) — a higher-priority cross-context channel. 

## 8.7 Behavioral Analytics Privacy Surface 

Observe-and-offer (Section 6.1) requires behavioral analytics on the user’s interactions with the platform itself. Privacy/trust requires a transparent settings panel: “Bridgeable learns from how you use the platform. Here’s what it’s noticed. You can pause this.” Same model as the Memories panel in Claude.ai. Worth specifying when the behavioral analytics infrastructure is built. 

## 8.8 Naming Sweep Opportunity 

Several internal-doc-only references in earlier discussions still use older terminology: “decision workspace” / “focused workspace” / “triage” (when meaning the primitive vs. when meaning the queue-processing mode). This document uses the canonical names throughout. Older session notes and CLAUDE.md may have stale language to clean up when convenient. 

_End of document. Open issues, unresolved decisions, and future workshopping topics are tracked in Section 8. This document supersedes earlier post-aesthetics-arc memory entries and discussion notes from the desktop sessions of April 2026._ 

