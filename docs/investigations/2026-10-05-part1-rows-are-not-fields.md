# Part 1, measured first: the capture rows are not the template's fields

**Read-only. 2026-10-05.** The check the dispatch asked for before fixing the
shape — *"check screen 1's rows against the template"* — and it says Part 1 as
scoped cannot produce the design.

## ⚠️ The cited file is not reachable; a different revision of it is in the repo

| | size | md5 |
|---|---|---|
| dispatch cites | 984,337 | `8ee8e117d9f4564f18a4ab580b9666ca` |
| **in the repo** at `docs/prototypes/2026-09-call-to-print.html` | 1,072,184 | `56e1e24c3a4a873e1ef6d45fc58ba18e` |

Nothing of 984,337 bytes exists anywhere reachable (searched `~/Downloads`,
`~/Desktop`, `~/Documents`, `/tmp`, the scratchpad and the repo with `find -L`,
after a control confirming those directories are readable). **I did not create
`docs/design/`** — committing a file I was only told about is the thing an
executor must refuse.

But the repo copy reproduces **every marker measured on the other revision**:

```
cap.done ×4   cap.needed ×4   unconfig ×0   "Not mentioned yet" ×2
sf.late ×2    "1 — CALL over the note" ×1   "2 — CALL SUMMARY in the overlay" ×1
"Approve &amp; Create" ×1
```

Same design, different revision. **Everything below is measured from the
1,072,184-byte repo copy and is labelled as such** — not silently substituted for
the file the dispatch named.

## Three states, confirmed verbatim

```css
.cap .v        { color: var(--fg-4); font-style: italic }      /* default */
.cap.done      { border-color: rgba(63,156,99,.3); background: rgba(63,156,99,.05) }
.cap.done .v   { color: var(--fg); font-style: normal }
.cap.needed    { border-color: rgba(224,168,74,.55); animation: needpulse 1.9s ease-in-out infinite }
.cap.needed .k { color: #e0a84a }
```

Default value text is literally `"Not mentioned yet"`; `flagNeeded()` replaces it
with literally `"Still needed"`. No fourth state — `unconfig` has zero hits.

⚠️ **`needed` is raised PER FIELD BY A SIGNAL IN THE TRANSCRIPT, not by a mode.**
`LINES[3]` carries `flag:8`, so when the caller says *"That should be everything"*
while row 8 is unfilled, `flagNeeded(8)` fires on that row alone. Nothing marks
the other unfilled rows. So "amber after the user signals done" is a **per-row
decision about which gap to surface**, and who makes it is an open question the
design does not answer — the server cannot see the signal today.

## ⚠️ THE FINDING: nine display rows, twelve template fields

Screen 1's `FIELDS`, verbatim:

```js
{k:'Funeral Home',       v:'Wilbert Funeral Home'},
{k:'Contact',            v:'Tom Harding'},
{k:'Deceased Name',      v:'John Smith'},
{k:'Dates',              v:'Mar 14, 1948 — Sep 14, 2026'},
{k:'Service',            v:"St. Mary's · Thu 10:00 AM"},
{k:'Cemetery',           v:'Forest Lawn · Thu 11:30 AM'},
{k:'Vault / Product',    v:'Wilbert Bronze'},
{k:'Personalization',    v:'Legacy print · American Flag'},
{k:'Cemetery Equipment', v:'Full setup · lowering device, tent, chairs'}
```

Against the twelve-field `sales_order` template:

| screen 1 row | template field(s) |
|---|---|
| Funeral Home | `funeral_home` |
| **Contact** | ⚠️ **no template field** |
| Deceased Name | `deceased_name` |
| **Dates** | ⚠️ **no template field** — birth and death dates |
| **Service** | `service_location` **+ a service time the template does not have** |
| **Cemetery** | `cemetery` **+ `burial_time`** — composed |
| Vault / Product | `vault` (and `vault_size`?) |
| **Personalization** | ⚠️ **all three personalization questions in ONE row** |
| **Cemetery Equipment** | ⚠️ **no template field** |

So the counts "N captured / N needed" are over **nine rows**, not twelve fields —
`cneed` is literally `FIELDS.length - done`.

**Four distinct mismatches, not one:**

1. **Composition inside a row** — `Cemetery` carries cemetery *and* burial time.
2. **Collapse** — three template fields become one `Personalization` row.
3. **Rows with no template field** — `Contact`, `Dates`, `Cemetery Equipment`.
4. **Template fields with no row** — `vault_size`, `grave_location`,
   `burial_date` appear nowhere as their own row.

## What this means for the dispatch

Part 1 was scoped as *"the template gains a display label and an order per
field"*. **That produces twelve rows where the design has nine**, and no amount of
labelling fixes it, because the mismatch is structural rather than cosmetic.

⚠️ **Part 1 and Part 2 are one mechanism.** Composition was supposed to be Part
2's concern, but screen 1 is already composed — so the display-row layer is
needed to render the *capture* display, not only the summary. Building Part 1 as
scoped would ship a shape that then has to be replaced, which is the outcome the
prototype was consulted to prevent.

**I have not built anything.** Three options, and the choice is James's because it
is a product question about what a template declares:

- **(a) One layer.** The template declares ordered DISPLAY ROWS, each composed
  from zero or more fields; both screens render rows. Largest change, matches both
  screens, and makes Part 2 mostly already done.
- **(b) Two layers.** Fields keep labels and order; a separate row spec composes
  them per surface. More machinery, allows the two screens to differ.
- **(c) Part 1 for the four rows that are 1:1** (`Funeral Home`,
  `Deceased Name`, `Vault / Product`, and `Service` degraded to location only),
  composition deferred. Ships something, renders a different display from the
  approved one.

Also unresolved and not mine to settle: `Contact`, `Dates` and
`Cemetery Equipment` are rows in the approved design with **no capture field
behind them** — the same question `service_location` raised, three more times.

## Method

Markers grepped with both controls (a string that must be present, one that must
be absent). Row definitions read from the JS that builds `#caps`, not inferred
from CSS. Template read live via `template_for(SALES_ORDER)`. Every figure here is
from the 1,072,184-byte repo revision.
