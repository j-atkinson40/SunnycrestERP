# Command Bar × Spatial Workspace — Phase 1 Findings
2026-07-22 · READ-ONLY · repo @ fedbc27b (working tree clean of code changes) · no push

## JOB 1 — WHAT'S ACTUALLY BUILT (ground truth from code, not docs)

### Backend — `backend/app/services/command_bar/` (real, 2,228 LOC)
| Module | LOC | What it actually does today |
|---|---|---|
| `intent.py` | 305 | Rule-based classifier (no AI): navigate / search / create / action / empty; record-number regex, exact-alias, create-verb + `detect_create_with_nl()` (Phase 4 NL-creation detector) |
| `registry.py` | 558 | `ActionRegistryEntry` singleton + seed; permission/module/extension gates; create actions incl. `crossVerticalCreateActions` equivalents |
| `resolver.py` | 359 | pg_trgm fuzzy entity resolution across 7 entity types (fh_case, sales_order, invoice, contact, product, document, task), single UNION ALL, recency weighting, tenant isolation |
| `retrieval.py` | 760 | Orchestrator; owns `QueryResponse`/`ResultItem` contract; Phase-3 pin boost (1.25×), Phase-8e.1 starter-template boost (1.10×) + affinity boost (1.0–1.40×) |
| `saved_views_resolver.py` | 173 | Saved-view results (Phase 2) |

`POST /api/v1/command-bar/query` confirmed live (`backend/app/api/routes/command_bar.py:97`). BLOCKING latency gate exists (`test_command_bar_latency.py`).

### Frontend
- `src/components/core/CommandBar.tsx` — **1,392 LOC**. Renders a ranked RESULT LIST with type ranking `WORKFLOW > ANSWER > ACTION > RECORD > ASK > VIEW > NAV`. Voice input via `useVoiceInput` (voiceMode prop). NL-creation is a **mode swap** (`NLCreationMode` replaces the results list; components at `src/components/nl-creation/`). Peek-eye icons on RECORD/VIEW tiles (Peek follow-up 4). "Ask AI" escalation row.
- `src/core/commandBarQueryAdapter.ts` (138 LOC) — interface-only backend→frontend adapter, as documented.
- **DOC/CODE DRIFT #1**: CLAUDE.md refers to "frontend `actionRegistry.ts`"; the real file is `src/services/actions/registry.ts` (+ `manufacturing.ts`, `funeral_home.ts`, `types.ts`). Name drift only; the registry exists.
- **DOC/CODE DRIFT #2 (the big one for this arc)**: §4.2–4.3's *entity portal* and *floating contextual surfaces* are **SPEC-ONLY. Nothing in the codebase renders a floating entity card / calendar / chart beside the palette.** Greps for entity-portal / contextual-surface components: zero hits. What exists instead of §4.3 surfaces: the in-palette NL overlay, inline ANSWER rows, and the separately-routed Peek system.
- Also spec-only: §4.7 chip-driven conversation (zero "chip" occurrences in CommandBar.tsx), §4.8 interpretation chips + pause sensor, §4.5 recognition-and-escalation (no Focus-escalation code path in CommandBar.tsx — the only "escalate" is the Ask-AI row).

### Phase reality check (v1→Polish)
All seven phases left real code: v1 platform layer ✓ (above), Saved Views ✓ (`saved_views_resolver` + seeds), Spaces ✓ (boosts + DotNav), NL Creation ✓ (`nl-creation/` FE + `nl_creation/` BE), Triage ✓ (task type in resolver), Briefings ✓, Polish ✓. CLAUDE.md's claims for these are accurate; the aspirational §4.x surfaces are the gap.

### Floating / draggable / park inventory (everything spatial that exists)
| Thing | Where | Real behavior |
|---|---|---|
| **Focus free-form canvas** | `src/components/focus/canvas/` — `Canvas.tsx`, `WidgetChrome.tsx`, `geometry.ts`, `widget-renderers.ts`, `FocusDndProvider.tsx` | THE shipped draggable-window system: @dnd-kit drag from anywhere on widget body, 8-zone resize, anchor+offset state `{anchor, offsetX, offsetY, width, height}`, transform-based positioning, z-bump while active, pointer-events tier contract |
| **Three-tier responsive cascade** | `StackRail.tsx`, `StackExpandedOverlay.tsx`, `IconButton.tsx`, `BottomSheet.tsx`, `useViewportTier` | canvas (≥1000×700) / stack (280px right rail, scroll-snap) / icon (bottom-sheet grid); widget state tier-independent; **the shipped answer to "what happens to draggable windows on mobile"** |
| **Layout persistence** | `focus_sessions` (per-user per-focus, 3-tier resolve cascade) | Arrangements persist ONLY inside Focus |
| **AncillaryPoolPin** | scheduling Focus | The canonical "tablet" per INTERACTION_MODEL — pool/park state for triage items |
| **Peek system** | `PeekHost`, `PeekTrigger`, `peek-context` | Hover-summon/click-pin single floating panel; session cache; NOT draggable |
| Kanban drag | `DeliveryCard`, `SchedulingKanbanCore` | Lane drag, not windows |
| **Parking lot / window manager / multi-window layer** | — | **DOES NOT EXIST.** No react-rnd/react-draggable/window-manager anywhere; only @dnd-kit inside Focus + dispatch. Zero "parked/parking" code |

## JOB 2 — WHAT THE CANON SPECIFIES (quotes)

### PLATFORM_ARCHITECTURE §4.3 — visual treatment of Act surfaces
> "Float near the command bar (below or beside), not centered on screen … Maximum 2–3 surfaces visible … **No drag handle, no resize, no persistent affordances — as ephemeral as the command bar overlay** … Interactive but not editable"
(Note: "level 3, brass border" — pre-pivot language; visual spec now answers to chrome/steel.)

### §4.4 — the six anti-drift rules (verbatim, abridged to operative clauses)
> 1. "**Time-bounded by the action, not by the user.** … The user doesn't dismiss them — the action does."
> 2. "**No persistent state across invocations.** Closing and reopening starts fresh. The user isn't 'returning to' anything."
> 3. "Lightweight, not full-screen. … Page underneath stays interactive."
> 4. "One action at a time."
> 5. "No collaboration."
> 6. "**No 'open' state. You don't 'open a calendar' — the calendar appears because you mentioned a date.**"
> "If any of these breaks, the right primitive is Focus."

### §4.5 — escalation
> "When detected: 'This sounds like more than one action — want me to open a Focus on it?' One-click escalation."

### §5.1 — where draggable windows canonically live
> "Free-form canvas around the core for pins, widgets, and contextual panels — **drag, resize, snaps to 8px grid** … Soft maximum on visible widgets; overflow lives in a side rail"
§5.7: three-tier layout persistence (tenant default → per-user → per-session); "Touch / iPad uses preset zones (left rail, right rail, bottom strip) instead of true free-form."
§5.14 bounded-decision tests: "What decision does this close out?" / "When does the user exit?" — "If the answer is 'when they're done looking around,' the wrong primitive was chosen."

### PLATFORM_INTERACTION_MODEL — Park (the crux)
> "**Park** — *Set objects aside without dismissing them; they remain available.* … Parked objects are *available* without being *active*. They sit in the workspace's periphery (or in an explicit parking lot) until the user calls them back."
> Implementation status (April 2026): "**Existing**: … AncillaryPoolPin … Pinned items in a Space … return pill on a closed Focus."
> "**Aspirational: spatial parking lot for command-bar-summoned cards.** Tony's workshop model would let the user say 'actually, hold on this one for a moment' and have the card slide to a parking position. **Bridgeable has the architecture for this (the command bar with a parking surface) but the spatial workspace with multi-tablet arrangement is post-September.** The four-verb model still holds; the implementation surface evolves."

### Tablets + aspirational evolution
> "The full Tony's workshop model — multiple coexisting tablets, drag-positionable, summonable from anywhere — is **post-September**. … The architectural bones are in place … **Build to the model; the model holds even when the surface is a single-tablet implementation today.**"

### Spatial layer vs Focus + the escalation thresholds
> "The spatial layer is **on top of the current Page/Space**. Lightweight. Dismissible. Non-exclusive." vs Focus = "deliberate 'I'm now working through this specific decision' mode."
> Escalation: "**Pin count crosses ~3** … you're really setting up a workspace." / "Time-bounded by user, not by action → it's a Focus."

### Persistence rules — how park reconciles with §4.4 rule 2
> "**Command bar state** [doesn't persist]. Closing and reopening the command bar starts fresh … Within an invocation, the chip stack persists; across invocations, fresh start."
> Peek precedent: "Click-pinned peeks persist **within a session** but not across navigation away."
> "The discipline: **persistence aligns with the user's mental model of the object.**"
**Reconciliation as written**: §4.4-2 governs the *command bar's own state*, not objects it has summoned. A summoned-then-parked tablet is a distinct object whose persistence follows ITS mental model — canon's precedents cap that at *session-scoped* (peek pins) or route durable placement to Space pins / Focus layouts. Nothing in canon sanctions a cross-session floating-window desktop.

### Mobile / tablet translation (verbatim table)
> Desktop: "Free-form drag, multi-window arrangement, full keyboard" · Tablet: "Card-rail patterns, swipe-to-foreground" · Phone: "**Stacked summoning, vertical card flow, intelligence-proposed arrangements (less manual arrangement, more automatic surfacing)**"
> "The interaction *feel* is the same … Implementation differs." Shipped reference: the Focus canvas→stack→icon cascade with tier-independent widget state.
**Answer to the mobile question: draggable windows are desktop-tier only, by design; canon prescribes card-rail (tablet) and stacked/auto-arranged flow (phone), and the tier cascade is the shipped mechanism to reuse.**

## JOB 3 — COLLISION MAP + TYPE B CALL

| Figma element | Canon verdict |
|---|---|
| Command palette | ✅ Built (Act). Matches §4.1 |
| "Open Calendar" as a command | ❌ Verbatim collision with **§4.4 rule 6** ("You don't 'open a calendar'"). Sanctioned grammars: intent-shaped summon ("schedule Tuesday" → calendar appears as guardrail, §4.3-2) or entity/view summon ("show today's deliveries" → routes to view). An app-launcher grammar imports the app-switching model the canon explicitly rejects |
| A draggable, resizable floating window | ❌ On the Act surface (§4.3: "no drag handle, no resize"). ✅ Inside Focus (§5.1: drag/resize/8px grid — fully built). ⚠️ In the ambient spatial layer: sanctioned as the *aspirational* multi-tablet workshop (post-September), machinery exists (WidgetChrome et al.) but no ambient host layer is built |
| Multiple coexisting windows (Calendar + People + Notes) | ⚠️ = the "multiple coexisting tablets" aspirational model. Bounded by "max 2–3 surfaces" on Act and the ">~3 pins → you're in Focus territory" escalation rule |
| Persistent multi-window workspace (macOS desktop) | ❌ as drawn. Cross-invocation persistence on the command bar violates §4.4-2; cross-session floating arrangement has no canon home — durable placement is Space pins (Monitor) or Focus layout state (Decide). Session-scoped parking is the sanctioned ceiling |
| Mobile version of the above | ❌ direct translation; ✅ canon-prescribed: tablet card-rail / phone stacked+auto-arranged, via the shipped tier cascade |

**Does "park" already provide a sanctioned home?** Yes-with-a-ceiling. The parking-lot-for-command-bar-cards is *named in canon as the aspirational evolution of an existing verb* — not a new primitive; it's the interaction model's ambient spatial layer riding the existing tablet machinery (WidgetChrome drag/resize, tier cascade, peek/widget composition reuse). But canon caps it: session-scoped persistence, ~3-object escalation to Focus, summon grammar stays intent-shaped, and it must not become "where work lives" (Monitor owns ambient awareness; Decide owns bounded work).

**THE TYPE B CALL (James decides; framing per the three options):**
- **(a) Decision-bounded → Focus.** If the drawn windows exist to work through something nameable ("plan the week"), this is a Focus re-skin + wiring the UNBUILT §4.5 escalation. Cheapest; everything exists.
- **(b) Ambient utility → the park layer.** If the intent is "keep the calendar/People card handy while I work," canon already sanctions exactly this as the post-September spatial parking lot: a session-scoped ambient tablet layer above the page, summoned via intent (not "open"), escalating to Focus past ~3 tablets, translating to rail/stack on touch. Requires NO new primitive — but does require James to ratify the constraint set (session-only persistence + observe-and-offer promotion to Space pins; the summon grammar; the escalation threshold).
- **(c) New spatial primitive.** Only forced if the requirement is a *cross-session, per-Space persistent window desktop* — that genuinely exceeds park's ceiling and collides with §4.4-2 + the persistence discipline, and would be an architecture decision against Monitor/Act/Decide.

Investigator's read (not a decision): the Figma as described is **(b) with two grammar amendments** — summon stays intent-shaped, persistence stays session-scoped — falling back to (a) for any window that is actually a decision. The genuinely new build is the ambient host layer + park verb UI; the windows themselves are the existing tablet/widget machinery. Separately, note that the *specced-but-unbuilt* §4.2/4.3/4.5/4.7/4.8 backlog (entity portal, contextual surfaces, escalation, chips, pause sensor) is the connective tissue the Figma concept assumes — any arc plan should sequence those before or with the spatial layer.

— Read-only confirmed: no code, schema, or doc changes; no push. —
