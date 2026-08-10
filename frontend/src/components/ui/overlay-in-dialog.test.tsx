/**
 * Overlays opened from INSIDE a Dialog must portal into the dialog's popup.
 *
 * THE BUG THIS PINS. Phase A 4.2.6 lifted Dialog onto `--z-modal` (105) and
 * left the dropdown family on a literal `z-50`. A popover opened from inside a
 * dialog therefore rendered BEHIND it — trigger live, list populated, painting
 * under the modal's own scrim. It reads as a greyed-out control, which is why
 * three rounds of source reading found nothing: every line was consistent with
 * a control that works, because it does.
 *
 * WHY THIS IS A CONTAINER TEST AND NOT A Z-INDEX TEST. Fixing by number would
 * make every popover outrank every modal platform-wide, and the number would
 * have to stay right in every future combination. Portalling is right by
 * construction — shared stacking context — so the thing worth pinning is the
 * portal TARGET, not a value.
 *
 * A rendering-layer bug is invisible to source reading; jsdom has no layout, so
 * it cannot see the stacking order either. What it CAN see is containment, and
 * containment is what makes the stacking order correct.
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { Dialog, DialogContent, DialogTitle } from "./dialog"
import { Popover, PopoverContent, PopoverTrigger } from "./popover"

function PopoverInsideDialog() {
  return (
    <Dialog open>
      <DialogContent>
        <DialogTitle>Edit account</DialogTitle>
        <Popover>
          <PopoverTrigger data-testid="trigger">Open</PopoverTrigger>
          <PopoverContent>
            <div data-testid="panel">1030 JANDHA LLC - CASH CHECKING</div>
          </PopoverContent>
        </Popover>
      </DialogContent>
    </Dialog>
  )
}

function PopoverAlone() {
  return (
    <Popover>
      <PopoverTrigger data-testid="trigger">Open</PopoverTrigger>
      <PopoverContent>
        <div data-testid="panel">1030 JANDHA LLC - CASH CHECKING</div>
      </PopoverContent>
    </Popover>
  )
}

describe("overlays inside a Dialog", () => {
  it("portals the popover INTO the dialog popup, not to the body", async () => {
    const user = userEvent.setup()
    render(<PopoverInsideDialog />)

    await user.click(screen.getByTestId("trigger"))

    const panel = await screen.findByTestId("panel")
    const dialogPopup = document.querySelector('[data-slot="dialog-content"]')

    expect(dialogPopup).not.toBeNull()
    // Containment IS the fix: sharing the dialog's stacking context is what
    // puts the popover above it, without claiming a global layer.
    expect(dialogPopup!.contains(panel)).toBe(true)
  })

  it("still portals to the body when there is no dialog above it", async () => {
    const user = userEvent.setup()
    render(<PopoverAlone />)

    await user.click(screen.getByTestId("trigger"))

    const panel = await screen.findByTestId("panel")
    // The negative case matters as much as the positive: the container is
    // `null` outside a dialog, so the primitive's default body portal must be
    // untouched. A fix that always portalled somewhere new would pass the test
    // above and silently change every popover on the platform.
    expect(document.querySelector('[data-slot="dialog-content"]')).toBeNull()
    expect(document.body.contains(panel)).toBe(true)
  })
})
