# Call context cards — a seventh triage type, a new surface, or a shared primitive?

**2026-09-22.** Part 0 of the capture-schema dispatch. Read-only; no code written.
Answers the question DECISIONS records as deliberately unruled in
`Call context cards are a second register on the call`.

**This report does not choose.** It reports three options and their costs. STOP.

---

## 1. What a type provides, and what the panel provides around it

`frontend/src/components/triage/TriageContextPanel.tsx` is 143 lines in three parts.

**A type provides a body, and nothing else.** It is one `case` in `PanelBody`
(lines 75–139, 65 lines for all six), receiving `(panel, item, sessionId)` and
returning JSX. `document_preview` is 16 lines; `saved_view` is one line returning
an `EmptyState`. Adding a type is a single-case addition, exactly as the file's
own docstring claims.

**The panel provides everything else:**

- **The rail** (`TriageContextPanel`, lines 25–44, 20 lines) — sorts by
  `display_order`, returns `null` when the list is empty, renders a fixed-width
  `<aside className="space-y-4 lg:w-80">`.
- **The card chrome** (`PanelCard`, lines 46–73, 28 lines) — border, shadow,
  header button, chevron, and the open/closed state.

⚠️ **The open state is per-card local `useState`, seeded from `default_collapsed`
(line 55), and no card knows any other card exists.** That single fact decides most
of what follows.

## 2. Is a type bound to the triage workspace?

**Yes, at three separate points.**

- Every body receives `item: TriageItem` and `sessionId: string` as required props.
- Both wired interactive types call triage session endpoints — `RelatedEntitiesPanel`
  and `AIQuestionPanel` take `sessionId` + `itemId`, and the related-entities endpoint
  is `GET /api/v1/triage/sessions/{id}/items/{item_id}/related`.
- The rail is mounted only when a session exists: `TriageWorkspace.tsx:215` renders it
  behind `session ? ... : null`.

A call is not a triage item and has no triage session. Rendering a type inside the
call overlay means supplying both, or changing the contract every existing type
depends on.

## 3. The five call-card behaviours against the panel as built

| Behaviour | Status | Why |
|---|---|---|
| Click a collapsed card to reopen | **EXISTS** | `PanelCard`'s header button toggles `open` (lines 58–65) |
| Arrival as facts land | **CONTRADICTS** | `panels` is a static config array sorted by `display_order`. Nothing arrives; the set is fixed before render |
| Collapse on arrival of the next | **CONTRADICTS** | Each card's state is independent local `useState`. Coordination is not merely absent — the current model forbids it |
| One-line data summary when collapsed | **NEW** | Collapsed renders `panel.title` (line 63), a static config string. No path from data to the collapsed line exists |
| Hold-open `ASKING` state | **NEW** | No concept of a card refusing to collapse |

**One of five exists. Two contradict. Two are new.**

⚠️ **The mismatch is not about the six types — it is about who owns the open state.**
The panel's collapse model is *operator-driven and independent*: the operator opens and
closes each card, and cards never affect one another. The call cards' model is
*system-driven and coordinated*: arrival order drives collapse, and a card collapses
because a different card arrived. Those are opposite owners. A seventh type does not
reach the disagreement, because the disagreement lives in `PanelCard`, not in `PanelBody`.

This is the same distinction the two canon entries were renamed to preserve: focus
context cards must not displace one another; call context cards collapse when the next
arrives.

## 4. What would configure a type, if the call overlay has no template?

**Panels are configured by the triage queue, not by a focus template.**
`context_panels: TriageContextPanelConfig[]` is a field on `TriageQueueConfig`
(`frontend/src/types/triage.ts:153`), populated per queue in
`backend/app/services/triage/platform_defaults.py`.

The focus-template registry props are a **different layer**, and the dispatch's
premise that they configure the panel does not hold. `showContextPanel`,
`contextPanelLayout` (`right-rail | below | modal`) and `contextPanelWidth`
(240–640px) in `registrations/focus-templates.ts` configure the *shell around* the
rail — whether the Focus renders a right rail at all and how wide. They say nothing
about which panels appear or how they behave. Panel composition is queue-level;
rail geometry is template-level.

**The call overlay has neither.** It has a feature flag, not a template:
`ai_settings.after_call_intelligence_enabled`, surfaced as a single toggle
("Show incoming call popup and live extraction panel",
`call-intelligence-settings.tsx:164`). There is no per-tenant composition of the
call surface today. A seventh type would therefore need a new configuration owner
invented for it — the thing the queue provides for the other six.

⚠️ `ContextPanelConfig` is `ConfigDict(extra="forbid")`
(`backend/app/services/triage/types.py:125`). New per-type fields are a backend schema
change, not an additive JSONB key.

## 5. Blast radius of touching `PanelCard`

Any option that changes the shared card chrome touches shipped code with live
consumers:

- **19 configured panels across 10 queues** in `platform_defaults.py` —
  9 `RELATED_ENTITIES`, 8 `AI_QUESTION`, 1 `DOCUMENT_PREVIEW`, 1 `AI_SUMMARY`.
  (Two further queues ship `context_panels=[]` deliberately.)
- **Playwright specs** covering the surface: `triage-phase-5.spec.ts`,
  `ai-question-panel.spec.ts`, `workflow-arc-phase-8b.spec.ts`.

CLAUDE.md's *Characterization before extraction* applies to any option that moves this
code: characterization tests pinning current behaviour first, extract second, fixes in
separate visible commits.

---

## The three options

### Option A — a seventh type

Add `CALL_CONTEXT` to `ContextPanelType`, a case to `PanelBody`, and the per-type
fields to `ContextPanelConfig`.

**Buys:** the body renderer, and one of the five behaviours (click-to-reopen).

**Costs:** the type itself is genuinely small — a case among 65 lines of switch. But
it is the wrong 5%. Arrival, coordinated collapse, data summaries and hold-open all
live in `PanelCard` and the rail, which a type cannot reach, so Option A is really
"add a type *and then* rewrite `PanelCard` anyway" — and rewriting `PanelCard` changes
behaviour for 19 shipped panels across 10 queues. It also requires manufacturing a
`TriageItem` and a `sessionId` for a call that has neither, and inventing a
configuration owner to replace the queue.

**Honest summary:** cheapest to start, and the cheap part is not the part that
matters.

### Option B — a new surface in `components/call/`

Build `CallContextCards` owning an ordered arrival list, coordinated collapse,
data-derived one-line summaries and the hold-open state. No triage coupling.

**Buys:** every line serves a behaviour that was actually specified. No shipped code
is touched, so no characterization burden and no regression surface across the 10
queues. The call overlay already exists (`components/call/CallOverlay.tsx`) with a
card vocabulary of its own — `RingingCard`, `ActiveCallCard`, `ReviewCard`,
`KBPanelCard`, `CustomerContext` — so this lands beside siblings rather than as a
new idea.

**Costs:** re-implements the ~28 lines of card chrome that `PanelCard` already has.
Two card implementations exist afterwards, and a third thing in the codebase is
called a context card (`ops-context-card.tsx` being the existing third).

### Option C — extract a shared primitive

Pull the chrome out of `PanelCard` into a neutral collapsible-card primitive that
both the triage rail and the call overlay compose, with **collapse policy injected** —
independent for triage, arrival-coordinated for calls.

**Buys:** one card implementation. The policy difference becomes explicit and named
rather than implicit in two separate files, which is the thing most likely to be
misread later given the two surfaces already share a word.

**Costs:** highest up-front, and the only option that touches shipped triage code
with 19 live panels and three Playwright specs. Requires the full characterization
discipline before the move. Risks paying extraction cost for a second consumer whose
requirements are still partly unbuilt — the hold-open `ASKING` state has no
implementation anywhere to generalize from yet.

---

## STOP

Reported, not chosen. The build's size follows from this ruling: Option A and C
change shipped triage behaviour and carry characterization work; Option B does not
touch it.

**Method note.** The six types were verified twice by different means rather than
inherited from the dispatch: the frontend `switch` in `PanelBody` and the backend
`ContextPanelType` enum independently list the same six. The dispatch's premise that
focus-template props configure the panel was checked and does not hold — see §4.
