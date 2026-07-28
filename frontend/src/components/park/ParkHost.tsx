/**
 * ParkHost — the park layer's mount (S-5).
 *
 * A PEER Act-layer surface mounted at app root, a SIBLING of Focus/
 * command bar — NOT inside the Focus-exclusive tree (mounting there would
 * unmount the command bar). It renders the free-form ParkCanvas when park
 * is active (has tablets AND not suspended behind a Focus), plus a
 * deliberate-exit control and the grace-window relaunch pill.
 *
 * Suspend-and-return is automatic: `isActive` is false while a Focus is
 * open over an arranged park, so the canvas unmounts (tablets hidden) —
 * but the park SESSION state is held in ParkContext, so on Focus close
 * `isActive` flips back true and the tablets re-render intact.
 *
 * The ParkCanvas is wrapped in its own `FocusDndProvider` (the generic
 * DndContext) — independent of the Focus one; park drags never cross into
 * Focus and vice versa.
 */

import { X } from "lucide-react"

import { FocusDndProvider } from "@/components/focus/FocusDndProvider"
import { usePark } from "@/contexts/park-context"

import { ParkCanvas } from "./ParkCanvas"
import { ParkRelaunchPill } from "./ParkRelaunchPill"

export function ParkHost() {
  const { isActive, tablets, exitPark } = usePark()

  return (
    <>
      {isActive && (
        <FocusDndProvider>
          <ParkCanvas />
          {/* Deliberate-exit control — the grace-window entry point.
              Dismissing individual tablets is not exit; this closes the
              whole working set and arms the relaunch pill. */}
          <div
            className="pointer-events-none fixed inset-x-0 top-3 z-[95] flex justify-center"
            data-slot="park-exit-bar"
          >
            <button
              type="button"
              onClick={exitPark}
              data-testid="park-exit"
              className="pointer-events-auto flex items-center gap-1.5 rounded-full border border-border-subtle bg-surface-raised px-3 py-1.5 text-caption text-content-muted shadow-level-1 [background-image:var(--panel-gradient-raised)] hover:text-content-strong focus-ring-accent"
            >
              <X className="size-3" />
              Close working set ({tablets.length})
            </button>
          </div>
        </FocusDndProvider>
      )}
      <ParkRelaunchPill />
    </>
  )
}
