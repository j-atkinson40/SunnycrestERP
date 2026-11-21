# Focus contrast — measured on all 13 registered Focuses, 2026-11-21

**This is a STOP, not a build.** The fix as specified reverses a canon
calibration surface and a second part of it would require editing
DESIGN_LANGUAGE. CLAUDE.md: *"If a build prompt seems to require edits to a
canon document, STOP and surface that."* The measurements are here so the
decision can be made on numbers.

## What was measured, and how

Every registered Focus was opened for real in a browser, signed in, and each
**text element inside the Focus core** was photographed on its own. Within one
element's box the darkest pixel is its glyphs and the lightest is the surface
directly behind them — which is the comparison AA is defined over.

⚠️ **TWO EARLIER VERSIONS OF THIS MEASUREMENT WERE WRONG, THE SAME WAY TWICE.**
Recorded because the numbers would have been believed:

| attempt | what it measured | why it was wrong |
|---|---|---|
| full viewport | the whole frame | included the **dimmed note behind** the Focus, whose text is *supposed* to be unreadable. Reported the backdrop working as designed as a defect, and put a Focus already measured at 14.49:1 below AA. |
| clipped to the core, scanned rows | each row's darkest and lightest pixel | at the card's **rounded corners** the darkest pixel is the backdrop outside it. Every row returned 4.53 — the card edge, not the text. |
| **per text element** | one element's glyphs vs its own background | names the failing string, which is checkable by eye |

The third names the text, so each number can be confirmed against the
screenshot. Harness: `frontend/tests/local/focus-contrast.spec.ts`.

## The numbers — 13 of 13 below AA

AA for body text is **4.5:1**.

| Focus | mode | worst | the text that fails |
|---|---|---|---|
| test-kanban | kanban | **1.13** | "Core mode · kanban" |
| books-review | triageQueue | **1.49** | "Nothing pending right now." |
| cash-receipts | triageQueue | **1.49** | "Nothing pending right now." |
| decision-triage | triageQueue | **1.49** | "Nothing pending right now." |
| expense-categorization | triageQueue | **1.49** | "Nothing pending right now." |
| month-end-close | triageQueue | **1.49** | "Nothing pending right now." |
| funeral-scheduling | kanban | **1.55** | "Unassigned" |
| test-triage-queue | triageQueue | **1.93** | "queueId" |
| weekly-payroll | singleRecord | **1.94** | "Cutoff is assumed, not confirmed." |
| test-matrix | matrix | **2.00** | "Plant A" |
| union-form | singleRecord | **2.94** | "Union remittance · R-115" |
| test-edit-canvas | editCanvas | **3.30** | "Edit-canvas content renders here…" |
| test-single-record | singleRecord | **3.55** | "Single-record stub" |

⚠️ **THE REGISTRY HOLDS 13 FOCUSES, NOT 5.** Five is the number of *modes*.
Two carry a bespoke `coreComponent` (`weekly-payroll`, `union-form`); the other
eleven fall through to the mode-generic renderers.

## There are TWO causes, and only one of them is the shell

### 1. Cores with no surface of their own

Eleven of the thirteen render directly onto `Dialog.Backdrop`'s
`bg-black/40 backdrop-blur-md`. `union-form` is the exception — it paints
`bg-surface-base`, added 2026-11-20 — and it is the only Focus whose body text
clears AA comfortably (its line labels measure 16.08:1).

### 2. `--content-subtle` fails AA on the lightest surface in the system

This one is **not about the Focus at all**, and would survive any shell fix:

| token | value | renders | on `--surface-base` | AA |
|---|---|---|---|---|
| `--content-base` | `oklch(0.22 0.004 260)` | (14,15,17) | **16.08** | pass |
| `--content-muted` | `oklch(0.52 0.006 258)` | (103,105,108) | **4.62** | pass, barely |
| `--content-subtle` | `oklch(0.63 0.006 258)` | (135,137,141) | **2.94** | **fail** |

`--content-subtle` cannot reach 4.5:1 against any surface the platform has.
Every eyebrow, every caption and every hint using it is below AA **platform
wide**, not only inside a Focus. The union form's worst element is exactly
this: its "UNION REMITTANCE · R-115" eyebrow.

## Why this is a STOP

**The shell's transparency is canon, and deliberate.**
`PLATFORM_QUALITY_BAR.md:249` lists it as an **at-bar calibration surface**:

> *Scheduling Focus core after Phase 4.4.2 container removal — content floats
> directly on dimmed-blurred backdrop. No container chrome. Each child element
> provides its own visual weight. "Focus is a mode, not a modal."*

`Focus.tsx` carries the same ruling in a comment, citing the spec it came from.
So "the shared shell paints the Focus surface itself" reverses a canon
calibration surface and changes the look of the funeral-scheduling kanban,
which that same page names as at-bar.

**And fixing `--content-subtle` means editing DESIGN_LANGUAGE.** tokens.css and
DESIGN_LANGUAGE §3 are declared mirrors that must change in the same commit,
and CLAUDE.md forbids this session from writing DESIGN_LANGUAGE.md.

## Three routes, with what each costs

**A — the shell paints the surface** (as instructed). Fixes cause 1 for all
thirteen at once. Reverses the 4.4.2 calibration surface; the kanban's cards
would sit on a panel rather than floating. Does **not** fix cause 2: the
union form's eyebrow stays at 2.94.

**B — each core paints its own surface.** This is what 4.4.2 already requires
of children ("each child element provides its own visual weight"), so it
reverses nothing and the at-bar scheduling Focus keeps its look. Proven by
`union-form`, whose body text is 16.08:1. Costs: eleven cores to touch, and
the ones that are stubs may not be worth touching. Also does not fix cause 2.

**C — A or B, plus darkening `--content-subtle`.** The only route that gets
every Focus fully to AA. Needs an Opus session for the DESIGN_LANGUAGE change,
and it moves every eyebrow and caption on the platform, not just in Focuses.

My reading, stated as a recommendation and not acted on: **B for the two
payroll cores Susan will see, plus C's token change raised separately**, since
cause 2 is platform-wide and a Focus PR is the wrong place to settle it.

## Evidence

`frontend/tests/local/shots/contrast/<focus>.png` — the whole core.
`frontend/tests/local/shots/contrast/<focus>/NN.png` — each text element.
`labels.json` per Focus maps each probe to the string it photographed.
