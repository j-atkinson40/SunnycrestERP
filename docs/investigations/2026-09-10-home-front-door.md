# The front door — what assumes `/home` is Pulse, and two STOPs

**Date:** 2026-09-10 · **HEAD:** `0b157e5f` · **Read-only — no application source changed.**

Session 5 of the note arc opened with step 3's enumeration front-loaded, because a
miss there is a broken front door rather than a caught reference. The enumeration
completed. **Two of the dispatch's five STOP lines fire**, and they bracket the
session: one before step 1, one before step 3.

Nothing was inherited from the 2026-09-04 salvage investigation or from the
dispatch. Every figure below was re-derived at this HEAD.

---

## 0. Headline

**STOP line 3 fires on two of three prompts.** `collections_outstanding` and
`expense_posting_map` have no owner determinable from anything that exists.
`tasks_due_today` does. Owner/backup routing cannot ship for two thirds of the
prompt surface without inventing an ownership model, which is a decision.

**STOP line 1 fires on canon, not on code.** Two canonical documents assert Pulse
as live — **BRIDGEABLE_MASTER.md at 289 mentions and PLATFORM_PRODUCT_PRINCIPLES.md
at 29** — with **no supersession markers**, outside the dispatch's rewrite scope,
and write-restricted to this session by CLAUDE.md's documentation permissions.
Moving `/home` falsifies BRIDGEABLE_MASTER §3.26.1.1 by name.

Step 2 depends on step 1's data. Steps 4 and 5 sit behind step 3. **The buildable
remainder of the session is this document.**

---

## 1. Step 3 — the `/home` enumeration, re-derived

Method: `grep -rn` over `frontend/src` + `backend/app` for `"/home"` in every
quoting form, `*.ts` / `*.tsx` / `*.py`, **unbounded** — no `head`, no `-m`.

**34 occurrences across 14 files.** The salvage investigation reported **six files**.

### 1.1 The six the salvage doc named — all still true

| Site | What it does |
|---|---|
| `components/root-redirect.tsx:43` | `<Navigate to="/home" replace />` |
| `pages/home/HomePage.tsx:26` | `return <PulseSurface />` — the mount |
| `App.tsx:616` | `<Route path="home" element={<HomePage />} />` |
| `lib/runtime-host/page-contexts.ts:37` | `{ pattern: "/home", …, label: "Home Pulse" }` |
| `lib/runtime-host/TenantRouteTree.tsx:43-45` | comment only |
| `lib/visual-editor/registry/registrations/buttons.ts:209` | `actionConfig: { route: "/home" }` |

### 1.2 Three the salvage doc missed — one of them functional

| Site | Status |
|---|---|
| **`backend/app/services/spaces/registry.py:739`** | **FUNCTIONAL.** The Home system space carries `default_home_route="/home"`, seeded **for every active user regardless of role or permission**. Its 12-line comment block quotes BRIDGEABLE_MASTER §3.26.1.1 and justifies `pins=[]` on the grounds that "Pulse is intelligence-composed, not user-curated" — a rationale the note's *configured* standing set does not inherit. |
| `backend/app/services/operator_profile_service.py:18` | Docstring. |
| `bridgeable-admin/pages/runtime-editor/RuntimeEditorShell.tsx:98` | Comment. |

Plus five test files (`root-redirect.test.tsx`, `TenantRouteTree.test.tsx`,
`action-dispatch.test.ts`, `RegisteredButton.test.tsx`, `studio-routes.test.ts`).

### 1.3 ⚠️ The finding the literal grep does NOT surface

**`HomePage` mounts in three places, not one.**

```
App.tsx:616    <Route path="home"  element={<HomePage />} />   ← tenant route
App.tsx:1981   <Route index        element={<HomePage />} />   ← runtime editor root
App.tsx:1982   <Route path="*"     element={<HomePage />} />   ← runtime editor catch-all
```

The salvage doc's framing — *"`HomePage` is a 24-line wrapper whose entire body is
the Pulse mount. Pointing `/home` at the note surface is a one-line change in one
file"* — is **true about the line count and wrong about the blast radius.** The
same one-line body swap silently repoints the **runtime editor's root and
catch-all surface** (the R-1.6.9 invariant) from Pulse to the note.

`TenantRouteTree.test.tsx:140,155` asserts `elementTypeName(...) === "HomePage"`.
That stays green through a body swap, because the element type is still
`HomePage`. **The guard watches the mount and not the surface** — green without
contact, and it is the check that would otherwise catch this.

The fix is not difficult (mount the note at the tenant route directly, leave
`HomePage` to the runtime editor, or parameterise it). It is simply not the
one-line change it was reported as, and it is not a decision I should take alone.

### 1.4 Where the note lives today

`App.tsx:619` — `<Route path="note" element={<NotePage />} />`, three lines below
`/home`. Backend at `v1.py:428`, prefix `/note`. The Pulse backend router is
mounted at `v1.py:454`, prefix `/pulse`.

---

## 2. ⚠️ STOP line 1 — canon that assumes `/home` is Pulse and cannot be moved here

The dispatch scopes canon rewrites to **CLAUDE.md §1a** and **PLATFORM_ARCHITECTURE
§3**. Those are the two documents carrying supersession markers. Measured across
the canon registry:

| Document | Pulse mentions | Marker? | In dispatch scope? |
|---|---|---|---|
| BRIDGEABLE_MASTER.md | **289** | **none** | **no** |
| PLATFORM_ARCHITECTURE.md | 35 | §3, §8.2, §8.4 | yes |
| PLATFORM_PRODUCT_PRINCIPLES.md | **29** | **none** | **no** |
| CLAUDE.md | 11 | §1a | yes |
| PLATFORM_INTERACTION_MODEL.md | 5 | none | no |
| PLATFORM_DESIGN_THESIS.md | 1 | none | no |
| SPACES_ARCHITECTURE.md | 0 | — | — |

**BRIDGEABLE_MASTER §3.26.1.1 names the exact thing being changed:**

> "Authenticated tenant users land on Home Space (rendering Pulse at `/home`) on
> app open… The frontend's `RootRedirect` component honors this canon."
> — line 4074, labelled **"This is explicit canon, not implicit assumption."**

and at line 4099: *"The Pulse exists only in the Home Space. It is the platform's
primary Monitor surface and Bridgeable's most distinctive product feature."*

**PLATFORM_PRODUCT_PRINCIPLES** carries Pulse as **one of the three verbs** in the
one-surface-three-verbs thesis (lines 51, 62, 64, 82, 137) — the thesis CLAUDE.md's
own canon table names as the tiebreaker for contested product decisions.

### Why this is a STOP and not a note

The dispatch's own justification for the markers is that **"canon must not describe
a surface that is absent from code in either direction."** Rewriting §1a and §3
while leaving 318 unmarked Pulse assertions standing in two documents produces
exactly that defect, at roughly seven times the volume of the two documents being
repaired — and in the document the read order sends new sessions to for strategy.

CLAUDE.md's documentation-write permissions forbid this session writing
BRIDGEABLE_MASTER.md or PLATFORM_PRODUCT_PRINCIPLES.md. So the condition is not
"harder than expected"; it is **out of scope and out of permission**, which is the
STOP's literal wording: *anything that assumes `/home` is Pulse which cannot be
moved in this session.*

**This is a scope decision, not a technical one, and it is cheap to make.** Marking
is not rewriting — the two documents could take supersession markers under the same
rule §1a and §3 took them under, which is a smaller act than the rewrites already
authorised. That is James's call, not mine.

---

## 3. ⚠️ STOP line 3 — owner undeterminable for two of three prompts

Five fragments are registered; **three are `kind="prompt"`** and therefore the
population owner/backup routing and holder-scoped resolution lines apply to.

| Prompt | `subject_kind` | Owner determinable? |
|---|---|---|
| `tasks_due_today` | `user_day` | **Yes** — `task_details.assignee_user_id`, and `TaskRoutingRule` already resolves an assignee per `task_type_key` (`direct_user` / `round_robin`). |
| `collections_outstanding` | `customer` | **No.** |
| `expense_posting_map` | `expense_category` | **No.** |

### The absence is from enumeration, not from a keyword search

`Customer` has **67 mapped columns**. Enumerated in full, it carries exactly three
FKs to `users.id`: `created_by`, `modified_by`, `classification_reviewed_by`. All
three are audit columns. **There is no account owner, rep, collector, or assignee.**

⚠️ Worth recording: a keyword grep for `user|owner|rep|assign|manager` over the same
file returned nothing and would have produced this same conclusion **by luck** — it
missed all three real `users.id` FKs, because none of their names contains any of
those words. The conclusion was right and the method was wrong. Enumerating the
columns is what makes the absence claim worth anything.

`expense_posting_map`'s subject is an expense **category** — a string discriminator,
not an entity, and not a thing anything can own.

### Why this is a STOP

Shipping owner/backup for `tasks_due_today` alone and leaving the other two
unowned is a decision about what an unowned prompt does — does it route to every
permission-holder as today, does it acquire a configured owner, does the audience
predicate become the owner-of-last-resort? Each answer implies a different data
model, and the dispatch reserves it: *any prompt whose owner cannot be determined
from what exists.*

The ruling that avatars communicate **capability** rather than activity is
load-bearing here. An avatar row on a prompt nobody owns says something specific
and currently untrue.

---

## 4. Corrections to the salvage investigation

Carried forward per the dispatch's instruction not to inherit it.

1. **"Six files assume `/home`" → 14 files, 34 occurrences.** The three non-test
   additions are §1.2; one (`spaces/registry.py`) is functional.
2. **"A one-line change in one file" understates the blast radius** — §1.3. Three
   mounts, one of them the runtime editor's catch-all.
3. **`pulse-widget` zero-row measurement was dev-only and remains so.** Not
   re-measured here; production is read-only and step 4 is blocked upstream.
4. **Confirmed, not corrected:** `types/fragments.ts` imports `IntelligenceStream`
   from `@/types/pulse` and has **zero importers** — its only externally-referenced
   export name, `TargetSurface`, resolves to the unrelated widget-surface type of
   the same name. It is a compile-time assertion that the two payload shapes agree
   (`PAYLOAD_SHAPES_AGREE`). Deleting `types/pulse.ts` in step 4 breaks it. The
   rename must land somewhere before the delete, which is the ordering the
   dispatch's own sequencing rule predicts.

---

## 5. What is unblocked

Nothing in steps 1–5 as scoped. Step 1 is blocked by §3, step 2 depends on step 1,
step 3 is blocked by §2, steps 4–5 sit behind step 3.

The badge ruling (dispatch §3) is *decidable* without either STOP — canon already
supplies it at DECISIONS 2026-09-04: *"a count is a fact you read, a badge is a
demand."* It was not implemented here because it is a step-3 deliverable and
shipping header chrome alone, with the front door unmoved, is a change without its
reason attached.

---

## 6. Method notes

- The `/home` grep was unbounded. No `head`, no `-m`, no pipe that could truncate
  a completeness claim.
- The `Customer` ownership absence is from a full column enumeration (§3), not from
  a keyword match, and the keyword match is recorded as the near-miss it was.
- Pulse mention counts are `grep -c -i "pulse"` — **matching lines, not
  occurrences**. A line mentioning Pulse twice counts once, so 289 and 29 are lower
  bounds on mentions and exact counts of lines.
- Marker absence in BRIDGEABLE_MASTER / PRODUCT_PRINCIPLES is from
  `grep -n -i "supersed"` returning no Pulse-related hit, not from reading the
  whole document.
- `HomePage`'s three mounts were found by enumerating references to the symbol, not
  by searching for the route string — the literal `/home` grep does not reach
  `App.tsx:1981-1982`.
