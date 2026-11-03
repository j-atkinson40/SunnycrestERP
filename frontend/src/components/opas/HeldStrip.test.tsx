/**
 * The "Not placed yet" strip: three ways out of a chip, and what each one sends.
 *
 * ⚠️ THE GESTURES ARE DRIVEN WITH REAL POINTER EVENTS, not by calling the handlers.
 * The click/drag split is decided by DISTANCE inside one `pointerdown`, so a test that
 * invoked `onPlace` directly would assert the plumbing and never the fork — and the
 * fork is the whole design. jsdom has no layout, so `elementFromPoint` is stubbed;
 * everything else is the real listener chain.
 */
import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { HELD_HINT, HELD_LABEL, HeldStrip } from "./HeldStrip"
import type { HeldWord } from "@/services/opas-capture-service"

const held = (over: Partial<HeldWord> = {}): HeldWord =>
  ({ id: "h1", word: "green pastures", origin: "typed", ...over }) as HeldWord

function setup(over: Partial<Parameters<typeof HeldStrip>[0]> = {}) {
  const onPlace = vi.fn()
  const onDrop = vi.fn()
  const onEdit = vi.fn()
  render(
    <HeldStrip
      held={[held()]}
      onPlace={onPlace}
      onDrop={onDrop}
      onEdit={onEdit}
      {...over}
    />,
  )
  return { onPlace, onDrop, onEdit }
}

/** A row the pointer can be over, carrying the two attributes a drop reads. */
function row(fieldId: string): HTMLElement {
  const el = document.createElement("button")
  el.setAttribute("data-fields", fieldId)
  el.setAttribute("data-drop-field", fieldId)
  document.body.appendChild(el)
  return el
}

function overPoint(el: Element | null) {
  document.elementFromPoint = () => el as Element
}

afterEach(() => {
  document.body.removeAttribute("data-opas-dragging")
  document.querySelectorAll("[data-testid='opas-held-ghost']").forEach((n) => n.remove())
})

describe("the strip itself", () => {
  it("shows the label, the word and the hint", () => {
    setup()
    expect(screen.getByTestId("capture-held")).toBeInTheDocument()
    expect(screen.getByText(HELD_LABEL)).toBeInTheDocument()
    expect(screen.getByText("green pastures")).toBeInTheDocument()
    expect(screen.getByText(HELD_HINT)).toBeInTheDocument()
  })

  it("renders NOTHING with no held words", () => {
    /** ⚠️ AN EMPTY DASHED BOX WOULD READ AS A PROBLEM. "Not placed yet" with no words
     *  under it says something went wrong; the strip existing at all is the signal. */
    setup({ held: [] })
    expect(screen.queryByTestId("capture-held")).not.toBeInTheDocument()
  })

  it("shows the DIRECTOR'S text, not a normalised form", () => {
    setup({ held: [held({ word: "montecello" })] })
    expect(screen.getByText("montecello")).toBeInTheDocument()
  })
})

describe("× drops the word", () => {
  it("sends the chip's id", async () => {
    const user = userEvent.setup()
    const { onDrop, onPlace, onEdit } = setup()
    await user.click(screen.getByTestId("capture-held-drop-h1"))
    expect(onDrop).toHaveBeenCalledWith("h1")
    expect(onPlace).not.toHaveBeenCalled()
    expect(onEdit).not.toHaveBeenCalled()
  })

  it("names the word for a screen reader", () => {
    /** The × is the only destructive control here and it has no text of its own. */
    setup()
    expect(screen.getByLabelText("Drop green pastures")).toBeInTheDocument()
  })
})

describe("a click opens the inline edit", () => {
  it("a press that does not move opens the box with the word in it", () => {
    setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    expect(screen.getByTestId("capture-held-edit")).toHaveValue("green pastures")
  })

  it("Enter commits a CHANGED word", async () => {
    const user = userEvent.setup()
    const { onEdit } = setup({ held: [held({ word: "montecello" })] })
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    const box = screen.getByTestId("capture-held-edit")
    await user.clear(box)
    await user.type(box, "monticello{Enter}")
    expect(onEdit).toHaveBeenCalledWith("h1", "monticello")
  })

  it("an UNCHANGED edit sends nothing", () => {
    /** ⚠️ CLICKING A CHIP TO LOOK AT IT IS THE COMMON CASE. A PATCH per glance re-runs
     *  extraction, which can move the order's rows under the director for no reason. */
    const { onEdit } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    fireEvent.blur(screen.getByTestId("capture-held-edit"))
    expect(onEdit).not.toHaveBeenCalled()
  })

  it("an EMPTIED edit drops the chip instead of keeping a blank one", async () => {
    /** The prototype's `if(text)h.text=text;else S.held=S.held.filter(…)`. A blank chip
     *  would be undraggable and uneditable — a dead slot in the strip. */
    const user = userEvent.setup()
    const { onEdit, onDrop } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    const box = screen.getByTestId("capture-held-edit")
    await user.clear(box)
    await user.type(box, "{Enter}")
    expect(onDrop).toHaveBeenCalledWith("h1")
    expect(onEdit).not.toHaveBeenCalled()
  })

  it("Escape abandons the edit and sends nothing", () => {
    const { onEdit, onDrop } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    fireEvent.keyDown(screen.getByTestId("capture-held-edit"), { key: "Escape" })
    expect(screen.queryByTestId("capture-held-edit")).not.toBeInTheDocument()
    expect(onEdit).not.toHaveBeenCalled()
    expect(onDrop).not.toHaveBeenCalled()
  })
})

describe("a drag files the word", () => {
  it("drops onto the row under the pointer", () => {
    const { onPlace, onEdit } = setup()
    const target = row("cemetery")
    try {
      const chip = screen.getByTestId("capture-held-word-h1")
      fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
      overPoint(target)
      fireEvent.pointerMove(window, { clientX: 300, clientY: 400 })
      fireEvent.pointerUp(window, { clientX: 300, clientY: 400 })
      expect(onPlace).toHaveBeenCalledWith("h1", "cemetery")
      // ⚠️ AND NOT THE EDIT. One gesture, two outcomes — a drag that also opened the
      // edit box would leave a text field over the strip after every drop.
      expect(onEdit).not.toHaveBeenCalled()
    } finally {
      target.remove()
    }
  })

  it("carries a GHOST while dragging, and removes it on release", () => {
    const { onPlace } = setup()
    const target = row("cemetery")
    try {
      const chip = screen.getByTestId("capture-held-word-h1")
      fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
      overPoint(target)
      fireEvent.pointerMove(window, { clientX: 300, clientY: 400 })
      const ghost = screen.getByTestId("opas-held-ghost")
      expect(ghost).toHaveTextContent("green pastures")
      // ⚠️ AND THE ROWS DASH WHILE IT IS IN THE AIR, which is how a director who has
      // never dragged a chip learns the rows are targets at all.
      expect(document.body).toHaveAttribute("data-opas-dragging", "true")
      expect(target).toHaveAttribute("data-drop-over", "true")

      fireEvent.pointerUp(window, { clientX: 300, clientY: 400 })
      expect(screen.queryByTestId("opas-held-ghost")).not.toBeInTheDocument()
      expect(document.body).not.toHaveAttribute("data-opas-dragging")
      expect(target).not.toHaveAttribute("data-drop-over")
      expect(onPlace).toHaveBeenCalled()
    } finally {
      target.remove()
    }
  })

  it("a drag released over NOTHING places nothing, and leaves no ghost", () => {
    /** ⚠️ THE MISSED DROP, AND IT MUST NOT FALL BACK TO THE EDIT EITHER. A director who
     *  thinks better of a drag and lets go over empty space has cancelled it. */
    const { onPlace, onEdit } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    overPoint(null)
    fireEvent.pointerMove(window, { clientX: 300, clientY: 400 })
    fireEvent.pointerUp(window, { clientX: 300, clientY: 400 })
    expect(onPlace).not.toHaveBeenCalled()
    expect(onEdit).not.toHaveBeenCalled()
    expect(screen.queryByTestId("opas-held-ghost")).not.toBeInTheDocument()
  })

  it("pointerCANCEL places nothing and cleans up", () => {
    /** The browser cancels a pointer when a system gesture takes over — a notification,
     *  a scroll handoff on iOS. Treating that as a drop would file the word wherever
     *  the finger happened to be. */
    const { onPlace } = setup()
    const target = row("cemetery")
    try {
      const chip = screen.getByTestId("capture-held-word-h1")
      fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
      overPoint(target)
      fireEvent.pointerMove(window, { clientX: 300, clientY: 400 })
      fireEvent.pointerCancel(window, { clientX: 300, clientY: 400 })
      expect(onPlace).not.toHaveBeenCalled()
      expect(screen.queryByTestId("opas-held-ghost")).not.toBeInTheDocument()
      expect(document.body).not.toHaveAttribute("data-opas-dragging")
    } finally {
      target.remove()
    }
  })

  it("a SHORT drag is still a click", () => {
    /** The threshold, through the real gesture rather than through `isADrag`. */
    const { onPlace } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(window, { clientX: 102, clientY: 101 })
    fireEvent.pointerUp(window, { clientX: 102, clientY: 101 })
    expect(onPlace).not.toHaveBeenCalled()
    expect(screen.getByTestId("capture-held-edit")).toBeInTheDocument()
  })

  it("does not drag while BUSY", () => {
    /** A request is already in flight; a second gesture would race it. */
    const { onPlace } = setup({ busy: true })
    const target = row("cemetery")
    try {
      const chip = screen.getByTestId("capture-held-word-h1")
      fireEvent.pointerDown(chip, { button: 0, clientX: 100, clientY: 100 })
      overPoint(target)
      fireEvent.pointerMove(window, { clientX: 300, clientY: 400 })
      fireEvent.pointerUp(window, { clientX: 300, clientY: 400 })
      expect(onPlace).not.toHaveBeenCalled()
    } finally {
      target.remove()
    }
  })

  it("ignores a RIGHT-button press", () => {
    /** ⚠️ IT ASSERTS THE EDIT BOX IS ABSENT, AND THE FIRST VERSION DID NOT — it checked
     *  only that `onPlace` and `onEdit` were not called, which stayed green with the
     *  button check deleted. A right-click that starts tracking ends as a zero-distance
     *  release, which opens the INLINE EDIT, and opening it calls neither callback. So
     *  the assertion that catches this is the one about the box, not the ones about the
     *  handlers. Found by the break matrix. */
    const { onPlace, onEdit } = setup()
    const chip = screen.getByTestId("capture-held-word-h1")
    fireEvent.pointerDown(chip, { button: 2, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(window, { clientX: 100, clientY: 100 })
    expect(screen.queryByTestId("capture-held-edit")).not.toBeInTheDocument()
    expect(onPlace).not.toHaveBeenCalled()
    expect(onEdit).not.toHaveBeenCalled()
  })
})

describe("two chips", () => {
  it("each has its own id, its own × and its own edit", async () => {
    /** ⚠️ THE SAME WORD TWICE IS TWO CHIPS, which is why the chip is keyed on its id
     *  and not on its text — "smith" typed twice is two unplaced words, and dropping
     *  one must not drop the other. */
    const user = userEvent.setup()
    const { onDrop } = setup({
      held: [held({ id: "h1", word: "smith" }), held({ id: "h2", word: "smith" })],
    })
    expect(screen.getByTestId("capture-held-chip-h1")).toBeInTheDocument()
    expect(screen.getByTestId("capture-held-chip-h2")).toBeInTheDocument()
    await user.click(screen.getByTestId("capture-held-drop-h2"))
    expect(onDrop).toHaveBeenCalledWith("h2")
    expect(onDrop).toHaveBeenCalledTimes(1)
  })
})
