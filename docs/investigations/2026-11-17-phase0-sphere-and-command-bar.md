# Phase 0 — the sphere, the command bar, and the missing upload path

Read-only. Nothing was built. 2026-11-17.

---

## 1. The blocking gap, demonstrated in code

`WeeklyPayrollCore.tsx:273` passes the upload card its week from the Focus:

    weekNumber={focus.week_number}
    weekEndDate={focus.week_end_date}

`focus` comes from `getWeekFocus(weekId)`, which needs a `weekId`, which exists
only once a `PayrollWeek` row exists, which `POST /weeks/upload` creates. **The
upload card lives inside the surface that the upload has to create.** With zero
weeks there is no Focus, so no card, so no upload. The note has nothing to say
and `payroll-home.tsx` renders its "No payroll weeks yet" state with
deliberately no link — correct, and a dead end.

### What already exists for the week calendar

    hours_validation.WEEK_START_WEEKDAY = 6     "Payentry's payroll week. Sunday through Saturday."
    service.CHECK_DATE_OFFSET = timedelta(days=5)   check_date = week_end + 5
    hours_validation:82  back = (any_day.weekday() - WEEK_START_WEEKDAY) % 7

Sunday–Saturday and check-date +5 are **already named once** and read by the
model, the importer and the tests. A "current week from today" helper does not
exist, and **the Wednesday Payentry cutoff appears nowhere in `app/`** — it is
new, and it is the only part of the calendar rule that is not already settled.

---

## 2. The sphere — far more exists than the dispatch assumes, and it disagrees

`components/opas/OpasHost.tsx` is ~3,090 lines: sphere, veil, command line,
glass panes, capture, guided questions, pane drag. `contexts/opas-context.tsx`
coordinates mutual exclusion with the command bar and the Focus, proven by
`opas-gate.test.tsx` over the three conflicting pairs.

**Gate:** `useAuth().isAdmin`, the existing role check, no new flag mechanism.
App.tsx:520 says so in a comment; OpasHost's header says
*"ADMIN-ONLY, via the EXISTING role check. No new flag mechanism."*

### ⚠️ Two prototypes, and the built sphere follows the OTHER one

    docs/prototypes/2026-10-01-opas-overlay.html    93,177 B  md5 a52a1e95153bd5c686b88d0acffc31e6
      -> this is what OpasHost was measured from, per its own header

    ~/Downloads/payroll-prototype-reference.html   132,110 B  md5 e98a51c61a4aa8ad7637f90c4854bc81
      -> what THIS dispatch cites. NOT IN THE REPOSITORY.

Canon (CLAUDE.md §11, "a dispatch may only cite sources the executor can
reach") wants the bytes committed with their digest before they authorise a
build. It is reachable here and is read in place below, but it should land in
`docs/prototypes/` as part of the build PR.

### Measured comparison

| | payroll prototype (cited) | built today (`OpasHost:3054`) |
|---|---|---|
| size | 56px | 56px ✓ |
| ball | `radial-gradient(circle at 36% 30%,#3c3c3c 0,#181818 42%,#060606 78%)` | **identical** ✓ |
| shadow | `0 18px 36px rgba(0,0,0,.75), 0 4px 10px rgba(0,0,0,.6)` | first half ✓, second replaced by a glow ring |
| layers | 6 spans: halo, ball, tint, inner, spec, rim | **none** — one element, background only |
| position | `absolute`, JS-placed, initial `{side:'right', y:.72}`, gutter 16 | `fixed; right:24; bottom:24` |
| drag | 5px threshold, snaps to nearer horizontal edge, keeps y fraction | **none** |
| states | `quiet` (no rule → **halo opacity 0**), `suggest #8aa4bd`, `working #d6d6d6`, `needs #cc7452`, `done #86ad73` | **two**: session `#d6d6d6`, else `#8aa4bd` |
| idle | **no glow** | ⚠️ **glows steel** |
| specular | tracks pointer, returns to 34/28 after 2200ms, respects reduced-motion | none |
| hover hint | 350ms, opposite side | none |

So the dispatch's sphere spec is accurate against the prototype it cites, and
**the built sphere is a partial implementation of a different one**. Reusable:
the ball gradient, the size, the open-on-click wiring, the mutual-exclusion
gate. Not present: drag/snap, the four-state glow model, the quiet state, the
layered construction.

### ⚠️ ⌘K was deliberately NOT bound, by a prior ruling

OpasHost's header, verbatim:

> **NOT BUILT, DELIBERATELY:** the prototype binds Cmd/Ctrl+K to toggle itself.
> This app binds Cmd+K to the command bar, and taking it would change existing
> command-bar behaviour. The sphere click is the entrance. Logged in STATE as
> James's call after the walk.

The dispatch asks for *"Clicking it or ⌘K opens the command bar."* That is a
reversal of a recorded decision, not an omission. Flagged per §12
Spec-Override Discipline — **it needs James's word, not my interpretation.**
Note the two readings differ: if Susan's shell has no platform command bar at
all, ⌘K is free and there is no conflict; if she can reach both, the binding
has to be decided.

---

## 3. The command bar — the area hole is already named in canon

There are two command surfaces:

    core/CommandBar.tsx          the platform bar, Cmd+K, hits POST /command-bar/query
    OpasHost's own command line  testid `opas-command-line`, inside the overlay

### ⚠️ `/command-bar/query` is COMMON but NOT COMPOSED

`areas.py:186` lists `("POST", "/command-bar/query")` in **`COMMON_ROUTES`** —
every signed-in user may reach it and **the area guard steps aside**. It is not
in `COMPOSED_ROUTES`, whose only member is `GET /note/today`.

And `services/command_bar/` contains **no mention of `area` or
`limited_to_areas` at all** — grepped, zero hits. The resolver searches 8 entity
types (fh_case, sales_order, invoice, contact, company_entity, product,
document, task) with no area predicate.

**So a payroll-limited user can call it today and get orders, invoices,
contacts, products and documents back.** That is the 2026-11-06 six-hubs
incident in a different surface: reachable, unfiltered, and nothing refuses it.

This is not a new discovery — canon already records it. `COMPOSED_SURFACES`,
the ordered plan of what must become composed, has `command-bar` as **#2**:

> *"Opas. The stated primary entrance; Sue's Opas should know payroll and
> nothing else. **Must resolve per RESULT.**"*

"Per result" is the hard part and the reason this cannot be a router tag: one
response mixes entity types, so the filter belongs on each row, not on the
route.

---

## 4. Plan, for James's go — NOT started

**A. Backend, first, because the area hole is live today.**
1. Make `/command-bar/query` a composed surface: filter per RESULT by the
   caller's areas, add it to `COMPOSED_ROUTES` with its reason, and remove it
   from `COMMON_ROUTES` so the two lists cannot both claim it.
2. Tests assert **content, not status** — a payroll-limited caller's results
   contain her payroll rows and contain no order, invoice, contact or product
   row. Break test: delete the filter, the content assertions redden.
3. A payroll week helper: current week from today (Sun–Sat), `check_date =
   week_end + 5`, and the Wednesday cutoff as a **new** named constant beside
   the two that already exist.
4. The five typed intents, server-composed: this week's Focus, past weeks,
   union dues for a week, timecard for a person, union member for a person.
   Typed matching only, no model calls.

**B. The upload path (the blocking gap).**
5. The note's payroll fragment and the Payroll page always show the current
   week, hours or not: *"Week 46 (Nov 8–14): no hours yet · Upload Employee
   Hours"*. Opening it opens the Focus **for a week that may not exist yet**;
   the upload creates the row. This is the real change — the Focus must accept
   a week descriptor, not only a week id.
6. Walk-through from sign-in with **zero weeks**, uploading a real Employee
   Hours file unmocked, reading the week back from the server.

**C. The shell, payroll-limited users only; admin keeps today's shell.**
7. No sidebar; minimal top bar (company, name, sign out); home is the note.
8. The sphere to the cited prototype: layered construction, drag with 5px
   threshold and edge snap, four glow states plus a genuinely quiet idle.
9. Needs-you glow when the current week has unanswered findings, or no hours
   after Monday.

**Open questions I will not answer by choosing:**
- **⌘K** — reversing a recorded decision (§2 above).
- **Which command surface Susan gets** — the platform bar, Opas's own line, or
  one replacing the other. The dispatch says "the command bar"; two exist.
- **Admin's shell** stays as-is, so two shells coexist. For how long, and is
  the split by area-limitation or by role?

**Sequencing note.** A2 before A1 in practice: write the content-asserting
tests against today's behaviour first so they fail for the right reason, then
filter. Characterization before extraction.
