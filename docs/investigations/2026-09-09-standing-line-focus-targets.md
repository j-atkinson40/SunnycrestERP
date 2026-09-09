# What Focus does each standing line open?

**Date:** 2026-09-09
**Status:** ENUMERATION. Measure-before-building for the session 3 redraft.
**Scope:** the four standing targets. `ar_summary` excluded — no renderer,
queued as its own build.

---

## Answer per target

The four possible answers, and which applies:

| Target | Standing label | Where it navigates today | Answer |
|---|---|---|---|
| `today` | Deliveries / Workload | `/dispatch`, or `/cases` · `/interments` · `/crematory/schedule` by vertical | **No Focus at all** |
| `vault_schedule` | Schedule | `/dispatch` or `/dispatch/incoming` | **No Focus at all** |
| `line_status` | Production | `/dispatch` or `/licensee-transfers/incoming` | **No Focus at all** |
| `scheduling.ancillary-pool` | Ancillary pool | `/dispatch` | **Exists, but may not match what the line means** — see below |

**Three of four are "none at all".** No widget produces a `?focus=` URL
anywhere; every navigation target is a page route. Verified: zero
`focus=` strings in the backend widget services.

**The fourth is the mismatch case.** `funeral-scheduling` is a real
registered Focus (kanban, with a `coreComponent`), and `AncillaryPoolPin`
lives inside its subtree (`components/dispatch/scheduling-focus/`,
`contexts/scheduling-focus-context.tsx`). But the standing entry sits
under `("manufacturing", "dispatcher")`, and that Focus is the funeral
vertical's scheduling board. Nothing gates Focus registration by
vertical — so it would open, and open onto the wrong board's shape.
Whether that is the right target is a design question, not a build one.

### The full Focus registry, for reference

12 registered. Two have a real `coreComponent`: `funeral-scheduling`
(kanban) and the quote Focus (editCanvas). Five are real via `queueId` +
`TriageQueueCore` — `decision-triage`, `books-review`, `month-end-close`,
`expense-categorization`, `cash-receipts`. Five are `test-*` stubs seeded
for the dev test page.

None of them corresponds to `today`, `vault_schedule`, or `line_status`.

---

## Read-only in the Focus layer

**It does not exist.** Zero matches for `readOnly` / `read_only` /
`canEdit` / `viewOnly` across `components/focus/`, `contexts/
focus-context.tsx`, and `contexts/focus-registry.ts`.

`FocusConfig` declares exactly: `id`, `mode`, `displayName`,
`defaultLayout`, `coreComponent`, `compositionFocusType`, `queueId`.
There is no non-editing mode to opt into.

So "read-only without edit permission" is **a build against the Focus
layer**, not a per-Focus flag, and it is the same size regardless of
which targets get Focuses. Worth separating from the per-target work:
permission-to-edit already exists as a concept; a Focus that *renders*
non-editing does not.

---

## Does a Focus take a scope parameter?

Half. `FocusOpenOptions` declares:

```ts
export interface FocusOpenOptions {
  /** Optional scope parameters passed to the Focus core. Reserved
   *  for later sessions — Session 1 stores but does not consume. */
  params?: Record<string, unknown>;
}
```

Two problems, both verified by reading the implementation rather than
the comment:

1. **Nothing consumes it.** `params` is stored on `FocusState` and
   round-tripped by `ReturnPill` (`ReturnPill.tsx:87`). No Focus core
   reads it.
2. **It does not survive the URL.** `open()` writes params to a ref and
   sets only `?focus=<id>` (`focus-context.tsx:352-364`). The module
   docstring states the URL is *"the source of truth after initial
   mount"* — so a refresh, deep link, or back-navigation drops the
   scope while keeping the Focus open.

This matters exactly as flagged: a standing line means **today's**
schedule. An unscoped Focus lands the user somewhere they must then
filter — the same two-steps-to-one-thing problem that killed the peek.
Passing scope is currently possible and inert; making it real means
consuming it in the core **and** getting it into the URL.

---

## A live defect found on the way: `/dispatch` is not a route

Every one of the four widgets uses `/dispatch` as its primary or
fallback navigation target. **There is no `/dispatch` route.**

Enumerated across every file defining `<Routes>` — `App.tsx`,
`TenantRouteTree.tsx`, `PlatformApp.tsx`, `PortalApp.tsx` — the only
matches are `dispatch/funeral-schedule` (a distinct path) and
`delivery/dispatch` (a redirect to `/scheduling`). No bare `dispatch`
path exists anywhere.

Both catch-alls that could receive it render `NotFound`: the
root-domain branch (`App.tsx:522`) and the tenant branch
(`App.tsx:1987`). The only `HomePage` catch-all is impersonation-only.

Reference count: **15 lines** in `backend/app` and **9 lines** in
`frontend/src` excluding tests (lines matched, not occurrences).

So today, clicking through from any of these four widgets lands on a
404. That is independent of this arc and of the peek-versus-Focus
ruling — it is broken now.

---

## Correction: the localhost 404

I attributed the review 404 to `/note` needing an authenticated
session. That was a guess and it was wrong. The app is **tenant-slug
routed**: `App.tsx:513` branches on `slug`, and without one the
root-domain branch serves only `/`, `/register-company`,
`/platform-admin`, then `NotFound`. `http://localhost:5173/note` has no
slug, so it could only ever 404. The URL I supplied was malformed, not
the route.

---

## Sizing

- **Read-only mode**: one build against the Focus layer. Nothing exists.
- **Scope**: one build, two halves — consume `params` in the core, and
  persist it in the URL.
- **Three targets** need a Focus that does not exist in any form.
- **One target** has a candidate Focus whose fit is a design question.
- **`/dispatch`**: a separate defect, fixable independently and probably
  worth fixing regardless of what the standing set does.

The measure-before-building conclusion: the redraft is not "wire four
standing lines to four Focuses." Three of the four Focuses do not exist,
and the two cross-cutting capabilities the ruling depends on — read-only
rendering and scoped opening — are absent and declared-but-inert
respectively.
