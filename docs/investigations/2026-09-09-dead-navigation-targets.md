# Widget navigation targets that point at routes which do not exist

**Date:** 2026-09-09
**Status:** `/dispatch` FIXED. Three others found and deliberately left.

---

## `/dispatch` — never built, not renamed

Established from history, not from the name:

- `git log -S 'path="dispatch"' -- App.tsx` returns **nothing**. A bare
  `dispatch` route has never existed in any revision.
- No `DispatchPage` component has ever been created.
- The closest real route was `delivery/dispatch`, added 2026-03-16
  (`2a57e17c`) and **renamed to `/scheduling`** on 2026-03-20
  (`c83d13f9`), which left the redirect still visible in `App.tsx`.
- The widgets wrote `"/dispatch"` on 2026-04-28/29 (`7327dbe1`,
  `6349ab18`, `9f5b0339`) — **five weeks after that rename**, to a path
  that had never existed at any point.

So it is neither category cleanly: never a route, but a correct live
destination exists today. **That makes it a link correction.**

## Where the links now point, and why

`/dispatch` → **`/dispatch/funeral-schedule`** (`FuneralSchedulePage`).

Evidence for this destination over `/scheduling`:

1. The page's own docstring: *"dispatch Pulse widget for the
   (manufacturing, dispatcher) role"* — exactly the role whose standing
   set carries these widgets.
2. It was renamed from **"Dispatch Monitor"** on 2026-04-23, five days
   *before* the widgets wrote `/dispatch`. The authors were writing a
   link to the thing that had just been renamed out from under them.
3. `today_widget_service` carried the comment *"Dispatch still exists"* —
   the author believed `/dispatch` was live and **distinct from**
   `/scheduling`, which rules out `/scheduling` as their intent. That
   comment has been corrected in place; it was false.

`/scheduling` was the alternative considered. It is the successor to
`delivery/dispatch` and owns an Ancillary Orders panel, which argues for
it on the `scheduling.ancillary-pool` widget specifically. It was
rejected because nothing has called it "dispatch" since the rename, and
because the comment above shows the authors meant a different surface.

### A caveat that is recorded rather than solved

`/dispatch/funeral-schedule` is the **vault line's** dispatch surface.
For a manufacturing tenant *without* vault enabled, it is the least
wrong live destination, not a correct one — Redi-Rock and wastewater
schedules are named-but-unbuilt. Noted in the code at the branch.

## A trap avoided

`backend/app/api/v1.py:524` mounts an API router at `prefix="/dispatch"`.
That is a **backend API path**, unrelated to frontend routing. A blind
replace of `"/dispatch"` across the backend would have broken the API.
The edit was scoped to `services/widgets/` only, and the prefix was
verified untouched afterwards.

## The tests asserted the dead route

**55 literals** across 8 frontend test files and 2 backend test files
asserted `"/dispatch"` as the expected navigation target. They were
green throughout. A test that pins the value a defect produces will
defend that defect — the suite could never have caught this, because it
had been taught the wrong answer.

## Three dead targets remain, deliberately not fixed

Found by the same sweep — every `navigation_target` emitted by
`backend/app/services/widgets/` checked against every route path
declared in any file defining `<Routes>` (App.tsx, TenantRouteTree,
PlatformApp, PortalApp — 413 declared paths):

| Target | Emitted by | Destination exists? |
|---|---|---|
| `/interments` | `today_widget_service` (cemetery vertical) | **No.** `disinterments` exists but is a different concept (exhumation), not a rename |
| `/crematory/schedule` | `today_widget_service` (crematory vertical) | **No page, no route, nothing** |
| `/licensee-transfers/incoming` | `line_status_service`, `vault_schedule_service` | **No page, no route, nothing** |

These differ from `/dispatch` in kind: **there is no destination to
correct the link to.** They are links to pages that were never built, so
the fix is either building those pages or returning `None` — which the
widgets already support and render as "no call to action" rather than a
dead one. Returning `None` is a product behaviour change for two
verticals and was not ruled, so it is left.

Net effect today: the Today widget's primary navigation is dead for the
**cemetery** and **crematory** verticals. Only `funeral_home`
(`/cases`) and the `/dashboard` fallback resolve.

`/dispatch/incoming` appears once, in a `vault_schedule_service`
docstring only. Never emitted — documentation drift, not a live link.

## Recommended, not built

A guard for this class. It must actually be able to fail: extract route
paths from the route trees, extract emitted targets from the widget
services, assert every target resolves. A weaker version — pinning
expected target strings — is what the existing 55 assertions already do,
and it is what let this ship.
