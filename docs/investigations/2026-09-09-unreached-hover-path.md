# The peek hover path has never run

**Date:** 2026-09-09
**Status:** FINDING. Not a build item — nothing is broken.
**Found by:** the session 3 peek bridge becoming its first consumer.

---

## The finding

The peek panel ships two trigger modes. **The hover mode has never
executed in the shipped app.** It landed 2026-04-20 (`86a06450`,
"peek panels — UI/UX Arc Follow-up 4") and has had no consumer since.

Unreached with it: the 200 ms hover debounce, the 80 ms exit grace,
promote-on-pointer-entry, and the `role="tooltip"` panel mode. All of it
is written, reviewed, covered by tests, and correct-looking.

## The enumeration behind it

Claimed from enumeration, not from a miss on a constructed scope.

**Every `openPeek` call site in the app** (6, excluding tests and the
reverted bridge) — every one passes `triggerType: "click"`:

| Call site | triggerType |
|---|---|
| `components/core/CommandBar.tsx:1361` | `"click"` |
| `pages/briefings/BriefingPage.tsx:430` | `"click"` |
| `components/triage/RelatedEntitiesPanel.tsx:139` | `"click"` |
| `components/saved-views/SavedViewBuilderPreview.tsx:260` | `"click"` |
| `lib/runtime-host/buttons/action-dispatch.ts:243` | `"click"` |
| `lib/widget-builder/runtime/atoms/index.tsx:870` | `args.triggerType ?? "click"` |

The last one *can* carry hover, and nothing passes it.

**`PeekTrigger`** — the component built to front both modes — has
**zero usages anywhere in the repository**, tests included. It defaults
`triggerType = "click"` and additionally downgrades hover to click on
coarse pointers.

**Nothing in `frontend/src` passes `"hover"`** outside the reverted
session 3 wiring and its tests.

## Why it surfaced now, and why it never would have otherwise

Session 3 wired the note surface's standing lines as hover peeks — the
first consumer the hover path has ever had. On operator review the peek
opened on cursor travel and then pinned itself on pointer entry.

That behaviour is not a session 3 regression. `promoteToClick()` on
panel mouse-enter is pre-existing and untouched (verified against
`a77b6baa`). It had simply never been reachable.

**There is therefore no live defect on the command bar, briefings, or
triage.** They open click-mode peeks and never enter the hover path.
With the bridge reverted, the path returns to zero consumers.

## What this is an instance of

The recurring question: *what consumes this, and has anyone ever seen
its output?* This is the largest instance found so far — an entire
subsystem rather than a function or a flag.

Things that exist and have never run:

| Thing | Shape |
|---|---|
| The peek **hover path** | never called — no consumer since 2026-04-20 |
| `PeekTrigger` | never mounted — zero usages |
| `peek_inline` | declared in the canonical `WidgetSurface` and one catalog entry, never consumed until session 3 declared and then reverted it |
| `_build_approvals_item` | **different shape** — it IS called (`personal_layer_service.py:299`) but returns `None` always, so its output has never been seen |

The last row is worth separating: unreached code and code whose output
is always empty look identical from the outside — both produce nothing
and both stay green — but they fail differently when something finally
does reach them.

## Not a build item

Nothing is broken and there is nothing to fix until something wants
hover. Recorded so that whoever wants it next knows they are the first,
and inherits the promote-on-entry behaviour as a **decision to make**
rather than a surprise to discover at review.

Two things that specific reader should know:

1. Promote-on-pointer-entry means a transient peek pins itself when the
   cursor merely crosses it. That was ruled wrong for standing lines on
   2026-09-09; it has never been ruled on for any other surface, because
   no other surface has reached it.
2. The 80 ms exit grace at `PeekHost.tsx` is real — an earlier claim in
   this arc that it was missing was itself a false absence, corrected in
   `e9901374`. It exists, it is now named `EXIT_GRACE_MS`, and it has
   never executed.
