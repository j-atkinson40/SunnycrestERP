/**
 * The guided question: ⌥ and the number, a bare digit, a click — and the layout.
 *
 * ⚠️ THE KEYBOARD TESTS DISPATCH REAL `KeyboardEvent`S WITH `code` AND `key` SET
 * SEPARATELY, because that separation is the defect this component can have and no
 * other kind of test can see. On macOS ⌥1 produces `key: "¡"` and `code: "Digit1"`.
 * A handler testing `/^[1-9]$/` against `key` is silently dead under the one modifier
 * the ruling requires — and `userEvent.keyboard("{Alt>}1{/Alt}")` sets `key: "1"`,
 * so it would pass against the broken version. The fixtures below set `key` to the
 * macOS character on purpose.
 *
 * ⚠️ AND EVERY ABSENCE ASSERTION HAS A POSITIVE CONTROL BESIDE IT. "onAnswer was not
 * called" cannot tell "the rule correctly refused" from "the listener is not attached
 * at all" — the exact pair `capture-live` already records for ⌘-digits. So each refusal
 * test is followed by a press that MUST land.
 */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import {
  BAR_INSET,
  GuidedQuestion,
  paneBottomPx,
  questionTakesNumbers,
  type GuidedQuestionProps,
} from "./GuidedQuestion"

const PILLS = [
  { value: "hopkins", label: "Hopkins Funeral Home", sub: "Skaneateles" },
  { value: "riverside", label: "Riverside Memorial Chapel", sub: "Auburn" },
  { value: "brown", label: "Brown & Sons", sub: "Auburn" },
]

/**
 * ⚠️ TYPED AS THE COMPONENT'S OWN PROPS, NOT CAST TO `never`, AND CI IS WHY. My first
 * version spread `props as never`, which `tsc -b` rejects — "Spread types may only be
 * created from object types" — and which `tsc --noEmit` never reached, because the gate
 * builds the test projects and that command does not. The cast was there to let `over`
 * be a loose bag; `Partial<GuidedQuestionProps>` does the same job and keeps the
 * fixtures honest, so a test passing a prop the component does not have fails here
 * rather than agreeing with my reading of it.
 */
function mount(over: Partial<GuidedQuestionProps> = {}) {
  const onAnswer = vi.fn()
  const props: GuidedQuestionProps = {
    question: "Which funeral home?",
    hint: "Type a name or pick one.",
    fieldId: "funeral_home",
    pills: PILLS,
    barHeight: 46,
    barWidth: "600px",
    stacked: false,
    barIsEmpty: true,
    questionTakesNumbers: false,
    onAnswer,
    ...over,
  }
  render(<GuidedQuestion {...props} />)
  return { onAnswer }
}

/**
 * `mount`, but able to re-render with new props.
 *
 * ⚠️ A SEPARATE HELPER RATHER THAN CHANGING `mount`'s RETURN, because `mount` is used
 * by thirty-odd tests above and widening what it returns is the kind of edit that
 * reads as harmless and makes every one of them a little less legible.
 */
function renderWithRerender(over: Partial<GuidedQuestionProps> = {}) {
  const onAnswer = vi.fn()
  const base: GuidedQuestionProps = {
    question: "Which funeral home?",
    hint: "Type a name or pick one.",
    fieldId: "funeral_home",
    pills: PILLS,
    barHeight: 46,
    barWidth: "600px",
    stacked: false,
    barIsEmpty: true,
    questionTakesNumbers: false,
    onAnswer,
    ...over,
  }
  const view = render(<GuidedQuestion {...base} />)
  return {
    onAnswer,
    rerender: (next: Partial<GuidedQuestionProps>) =>
      view.rerender(<GuidedQuestion {...base} {...next} />),
  }
}

/**
 * Dispatch a digit keypress the way a browser would, and report whether anything
 * claimed it.
 *
 * ⚠️ `code` IS ALWAYS `DigitN` AND `key` IS WHAT THE MODIFIER MAKES OF IT. That is the
 * whole point of this helper: with `alt: true` the key really is "¡" on a Mac.
 */
function pressDigit(n: number, opts: { alt?: boolean; meta?: boolean } = {}): boolean {
  const MAC_ALT_DIGITS = ["¡", "™", "£", "¢", "∞", "§", "¶", "•", "ª"]
  const e = new KeyboardEvent("keydown", {
    code: `Digit${n}`,
    key: opts.alt ? MAC_ALT_DIGITS[n - 1] : String(n),
    altKey: opts.alt ?? false,
    metaKey: opts.meta ?? false,
    bubbles: true,
    cancelable: true,
  })
  document.dispatchEvent(e)
  return e.defaultPrevented
}

describe("what it shows", () => {
  it("the question, the hint, and ⌥ with the number on every pill", () => {
    mount()
    expect(screen.getByTestId("opas-guided-question").textContent).toBe(
      "Which funeral home?",
    )
    expect(screen.getByTestId("opas-guided-hint").textContent).toBe(
      "Type a name or pick one.",
    )
    for (const n of [1, 2, 3]) {
      // ⚠️ ⌥ AND NOT ⌘, BY RULING. "Chrome keeps ⌘1–8 for switching tabs, so ⌘ would
      // only ever work in a desktop app" (James, 2026-10-27). The prototype renders ⌘;
      // this is the one place the divergence is visible, so it is asserted.
      expect(screen.getByTestId(`opas-guided-pill-key-${n}`).textContent).toBe(`⌥${n}`)
    }
    expect(screen.queryByText("⌘1")).toBeNull()
  })

  it("the sub beside each answer, which is what tells two answers apart", () => {
    mount()
    expect(screen.getByTestId("opas-guided-pill-sub-1").textContent).toBe("Skaneateles")
    expect(screen.getByTestId("opas-guided-pill-sub-2").textContent).toBe("Auburn")
  })

  it("no pills row at all when there are no answers to offer", () => {
    /** ⚠️ THE PROTOTYPE'S `.chips:empty{display:none}`. An empty glass strip above the
     *  bar on every free-text question reads as a row that failed to load — and
     *  `deceased_name`, the dates and `grave_location` are all free-text, so this is
     *  the common case rather than an edge one. */
    mount({ pills: [] })
    expect(screen.queryByTestId("opas-guided-pills")).toBeNull()
    // and the question is still there — the pane is not conditional on the pills
    expect(screen.getByTestId("opas-guided-question")).toBeTruthy()
  })

  it("nothing at all when there is no question", () => {
    mount({ question: null })
    expect(screen.queryByTestId("opas-guided-pane")).toBeNull()
    expect(screen.queryByTestId("opas-guided-pills")).toBeNull()
  })

  it("no hint element when the server sent no hint", () => {
    mount({ hint: null })
    expect(screen.queryByTestId("opas-guided-hint")).toBeNull()
  })

  it("the Cremation chip only once the vault has settled the kind", () => {
    mount()
    expect(screen.queryByTestId("opas-cremation-chip")).toBeNull()
    mount({ cremation: "Cremation" })
    expect(screen.getByTestId("opas-cremation-chip").textContent).toBe("Cremation")
  })

  it("does NOT carry the cleared note — that belongs in the pane footer", () => {
    /**
     * ⚠️ MOVED 2026-10-27, AND THE DISPATCH IS WHY. I first rendered the note here,
     * beside the question, reasoning that the capture pane can be tucked. But clause 4
     * says "in one line in the PANE FOOTER", and the note explains why a ROW emptied —
     * the rows are in the pane, so a sentence about rows the reader cannot see is
     * worse than one tucked along with them.
     *
     * ⚠️ ASSERTED AS AN ABSENCE so the capability cannot drift back and leave the
     * sentence on screen twice, in two places, saying the same thing.
     */
    mount()
    expect(screen.queryByTestId("opas-cleared-note")).toBeNull()
  })
})

describe("the layout the dispatch ruled", () => {
  it("sits to the LEFT of the bar when wide, bottom-aligned with it", () => {
    mount({ stacked: false })
    const pane = screen.getByTestId("opas-guided-pane")
    expect(pane.getAttribute("data-stacked")).toBe("false")
    // ⚠️ THE OFFSET IS THE BAR'S OWN INSET PLUS ITS WIDTH PLUS THE PROTOTYPE'S 16px
    // COLUMN GAP, which is what "to the LEFT of the bar" is in a fixed layout:
    //
    //     24  the bar's `right`
    //  + 600  the bar's width
    //  +  16  `.dock{gap:12px 16px}` — the column gap
    //  = 640
    //
    // ⚠️ ASSERTED AS THE FOLDED SUM BECAUSE THE BROWSER FOLDS IT, and the folded form
    // is the stronger assertion: `toContain("600px")` would have passed on a `calc`
    // that dropped the gap entirely. Found by the test failing on `calc(640px)`.
    expect(pane.style.right).toBe("calc(640px)")
    // bottom-aligned with the bar means the SAME `bottom`, so the two baselines agree
    expect(pane.style.bottom).toBe("24px")
    expect(screen.getByTestId("opas-guided-pills").style.width).toBe("600px")
  })

  it("stacks ABOVE the pills when narrow, which is the prototype's own order", () => {
    /** `@media (max-width:960px){.dock{grid-template-areas:"pane" "side" "chips" "bar"}}`
     *  — pane, Opas pane, pills, bar. So when stacked the Opas pane is above the pills
     *  and therefore above the bar by more than the pills row alone. */
    mount({ stacked: true })
    const pane = screen.getByTestId("opas-guided-pane")
    expect(pane.getAttribute("data-stacked")).toBe("true")
    expect(pane.style.right).toBe("24px")
    const paneBottom = parseInt(pane.style.bottom, 10)
    const pillsBottom = parseInt(screen.getByTestId("opas-guided-pills").style.bottom, 10)
    expect(paneBottom).toBeGreaterThan(pillsBottom)
  })

  it("the pills sit directly above the bar, at the bar's own width", () => {
    mount()
    const pills = screen.getByTestId("opas-guided-pills")
    // bar bottom 24 + bar height 46 + the prototype's 12px row gap
    expect(pills.style.bottom).toBe("82px")
    expect(pills.style.width).toBe("600px")
  })
})

describe("the three ways to answer", () => {
  it("a click answers with the pill's VALUE, not its label", async () => {
    const user = userEvent.setup()
    const { onAnswer } = mount()
    await user.click(screen.getByTestId("opas-guided-pill-2"))
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "riverside")
  })

  it("⌥2 answers the second pill — with the macOS character in `key`", () => {
    /** ⚠️ THIS IS THE TEST THAT CATCHES THE `key`-VERSUS-`code` DEFECT. With ⌥ held,
     *  macOS puts "™" in `key`; a handler matching `/^[1-9]$/` against `key` never
     *  fires and the whole ruling is silently dead on the only platform the office
     *  uses. */
    const { onAnswer } = mount()
    expect(pressDigit(2, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "riverside")
  })

  it("⌥ works even mid-phrase, when a bare digit would not", () => {
    const { onAnswer } = mount({ barIsEmpty: false })
    expect(pressDigit(1, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "hopkins")
  })

  it("a bare digit answers when the bar is empty", () => {
    const { onAnswer } = mount({ barIsEmpty: true })
    expect(pressDigit(3)).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "brown")
  })
})

describe("when a digit must be left alone", () => {
  it("a bare digit mid-phrase is part of what is being typed", () => {
    /** ⚠️ "monticello 28" NAMES A SIZE. Consuming that 8 would both answer the wrong
     *  question and eat a character — the prototype's own rule, `bareOK` at line 707. */
    const { onAnswer } = mount({ barIsEmpty: false })
    expect(pressDigit(1)).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
    // ⚠️ THE POSITIVE CONTROL. Without it, "not called" is satisfied by a listener
    // that is not attached — which is indistinguishable from the rule working.
    expect(pressDigit(1, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "hopkins")
  })

  it("a bare digit is left alone while the question itself takes numbers", () => {
    /** ⚠️ "What time?" — a bare "1" is the start of "1pm", not a pick. */
    const { onAnswer } = mount({
      fieldId: "service_time",
      questionTakesNumbers: true,
      barIsEmpty: true,
    })
    expect(pressDigit(1)).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
    expect(pressDigit(1, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("service_time", "hopkins")
  })

  it("a digit past the pill count is not claimed, so the key stays free", () => {
    const { onAnswer } = mount()
    expect(pressDigit(7, { alt: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
    expect(pressDigit(3, { alt: true })).toBe(true)
  })

  it("⌘ is not ours — Chrome keeps it, and claiming it would fight the browser", () => {
    /** ⚠️ THE OTHER HALF OF THE RULING. ⌥ is ours precisely BECAUSE ⌘1-8 belongs to
     *  tab switching; a handler that claimed both would break the thing the ruling was
     *  made to avoid. */
    const { onAnswer } = mount()
    expect(pressDigit(1, { meta: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
    expect(pressDigit(1, { alt: true })).toBe(true)
  })

  it("no field still listens, because the ready state's only pill is an ACTION", () => {
    /**
     * ⚠️ THIS ASSERTED THE OPPOSITE UNTIL 2026-10-27, AND IT WAS RIGHT THEN. With only
     * answer pills, a null field means nothing can be answered and the listener should
     * stand down. Clause 3 of the fixes introduces a pill that is NOT an answer —
     * "When everything needed is answered, Opas says 'That's everything.' with a
     * Review pill (⌥1) and Enter" — and in that state `question_field_id` is null.
     *
     * So guarding on the field made ⌥1 dead at exactly the moment the office wants it.
     * The listener now attaches whenever there are pills, and the field is used only
     * by the answer branch.
     */
    const onAnswer = vi.fn()
    const onAct = vi.fn()
    render(
      <GuidedQuestion
        question="That’s everything."
        hint="Press Enter to review, or click any line to change it."
        fieldId={null}
        pills={[{ value: "review", label: "Review", sub: "Enter", act: "review" }]}
        barHeight={46}
        barWidth="600px"
        stacked={false}
        barIsEmpty
        questionTakesNumbers={false}
        onAnswer={onAnswer}
        onAct={onAct}
      />,
    )
    expect(pressDigit(1, { alt: true })).toBe(true)
    expect(onAct).toHaveBeenCalledWith("review")
    // ⚠️ AND IT IS NOT ROUTED AS AN ANSWER. Through `onAnswer` it would try to store
    // "review" into a field — and with a null field there is no field to store it in.
    expect(onAnswer).not.toHaveBeenCalled()
  })

  it("an action pill does not try to answer a field, even when one is being asked", () => {
    /** ⚠️ THE MIXED STATE, WHICH IS THE COMMON ONE ONCE THE ORDER IS REVIEWABLE: an
     *  optional question still being asked, its answers in the row, and Review at the
     *  end. Routing by position rather than by `act` would store "review" into
     *  `cemetery_equipment`. */
    const onAnswer = vi.fn()
    const onAct = vi.fn()
    render(
      <GuidedQuestion
        question="What cremation setup?"
        hint={null}
        fieldId="cemetery_equipment"
        pills={[
          { value: "tent_only", label: "Tent Only" },
          { value: "review", label: "Review", sub: "Enter", act: "review" },
        ]}
        barHeight={46}
        barWidth="600px"
        stacked={false}
        barIsEmpty
        questionTakesNumbers={false}
        onAnswer={onAnswer}
        onAct={onAct}
      />,
    )
    expect(pressDigit(2, { alt: true })).toBe(true)
    expect(onAct).toHaveBeenCalledWith("review")
    expect(onAnswer).not.toHaveBeenCalled()
    // ⚠️ AND THE ANSWER PILL BESIDE IT STILL ANSWERS — the control for the above.
    expect(pressDigit(1, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("cemetery_equipment", "tent_only")
  })

  it("the listener is removed when the question goes", () => {
    /** ⚠️ A LISTENER THAT OUTLIVES ITS QUESTION ANSWERS THE NEXT ONE WITH THE LAST
     *  one's options. Asserted by unmounting rather than by reading the cleanup. */
    const onAnswer = vi.fn()
    const { unmount } = render(
      <GuidedQuestion
        question="Which funeral home?"
        hint={null}
        fieldId="funeral_home"
        pills={PILLS}
        barHeight={46}
        barWidth="600px"
        stacked={false}
        barIsEmpty
        questionTakesNumbers={false}
        onAnswer={onAnswer}
      />,
    )
    expect(pressDigit(1, { alt: true })).toBe(true)
    onAnswer.mockClear()
    unmount()
    expect(pressDigit(1, { alt: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
  })
})

describe("which questions take numbers", () => {
  it("the four the prototype names, plus ours", () => {
    /** ⚠️ THE PROTOTYPE'S LIST IS `['time','dates','day']`; these are this schema's ids
     *  for the same things. The chair counts are ours and not the prototype's — they
     *  are literally "how many", so they belong by the same reasoning.
     *
     *  ⚠️ THIS TEST ASSERTED `extra_chairs_count` UNTIL 2026-10-30 AND WAS GREEN ON A
     *  FIELD THAT NO LONGER EXISTED. Rulings A/B' split it into two, thirteen backend
     *  declarations failed on the rename, and this one passed throughout — because
     *  `questionTakesNumbers` is a membership check over a hand-written list, so the
     *  test and the list agreed with each other about a name the schema had dropped.
     *  Two halves of one constructed name cannot cross-check each other. */
    expect(questionTakesNumbers("service_time")).toBe(true)
    expect(questionTakesNumbers("service_date")).toBe(true)
    expect(questionTakesNumbers("date_of_birth")).toBe(true)
    expect(questionTakesNumbers("date_of_death")).toBe(true)
    expect(questionTakesNumbers("chairs_total")).toBe(true)
    expect(questionTakesNumbers("chairs_extra")).toBe(true)
  })

  it("and the ones that do not", () => {
    expect(questionTakesNumbers("funeral_home")).toBe(false)
    expect(questionTakesNumbers("vault")).toBe(false)
    expect(questionTakesNumbers("cemetery")).toBe(false)
    expect(questionTakesNumbers(null)).toBe(false)
    /** ⚠️ THE RETIRED NAME, PINNED AS A NEGATIVE. Without this the rename above could
     *  be undone by re-adding the old id beside the new ones and everything would stay
     *  green while a dead field sat in a live list again. */
    expect(questionTakesNumbers("extra_chairs_count")).toBe(false)
  })
})

describe("more answers than there are keys", () => {
  it("caps at nine, because there is no ⌥0", () => {
    /** ⚠️ THE SERVER CAPS AT FOUR; THIS IS INDEPENDENCE FROM THAT NUMBER, not a second
     *  opinion about it. A tenth pill would be unreachable by keyboard and would carry
     *  a label naming a key that does nothing — the same reasoning the pane's old
     *  numbered list used when it dropped the number past nine. */
    mount({
      pills: Array.from({ length: 12 }, (_, i) => ({
        value: `v${i}`,
        label: `Option ${i}`,
      })),
    })
    expect(screen.getByTestId("opas-guided-pill-9")).toBeTruthy()
    expect(screen.queryByTestId("opas-guided-pill-10")).toBeNull()
  })
})

describe("the pane does not swallow the pointer", () => {
  it("the question pane is inert and the pills are not", () => {
    /** ⚠️ THE PANE SITS OVER THE PAGE AND MUST NOT EAT CLICKS MEANT FOR IT. The pills
     *  are buttons and must. Same contract as the reply line, which is
     *  `pointerEvents: none` with its options row set back to `auto`. */
    mount()
    expect(screen.getByTestId("opas-guided-pane").style.pointerEvents).toBe("none")
    const pills = screen.getByTestId("opas-guided-pills")
    expect(pills.style.pointerEvents).not.toBe("none")
    // and a click on a pill really does reach it
    fireEvent.click(screen.getByTestId("opas-guided-pill-1"))
  })
})

describe("it reports the room it takes, so nothing overlaps", () => {
  /**
   * ⚠️ THE DEFECT THIS IS FOR IS WHAT JAMES SAW: "The pills sit on top of the order
   * pane. They cover 'Complete order' and the text under it." The capture pane was
   * anchored at `bottom: 24 + barH` — the bar's top edge — and the pills sit 12px
   * above that edge, so the pills were drawn over the pane's footer.
   *
   * ⚠️ MEASURED, NOT COMPUTED, BECAUSE THE ROW WRAPS. Four pills at 1920px are one
   * row; the same four at 1280px can be two, and a hard-coded 44px would put the pane
   * back on top of the second row.
   *
   * ⚠️ `offsetHeight` IS STUBBED BECAUSE JSDOM DOES NO LAYOUT — every element reports
   * 0, so without this the reported height would be 0 in every case and the test would
   * pass against a component that never measured anything. Stating it because a
   * stubbed measurement is weaker evidence than a real one, which is why the dispatch
   * also asks for screenshots: this pins the ARITHMETIC, the screenshots pin the
   * RENDER.
   */
  function stubHeights(pills: number, pane: number) {
    const proto = HTMLElement.prototype
    const original = Object.getOwnPropertyDescriptor(proto, "offsetHeight")
    Object.defineProperty(proto, "offsetHeight", {
      configurable: true,
      get(this: HTMLElement) {
        const id = this.getAttribute("data-testid")
        if (id === "opas-guided-pills") return pills
        if (id === "opas-guided-pane") return pane
        return 0
      },
    })
    return () => {
      if (original !== undefined) Object.defineProperty(proto, "offsetHeight", original)
      else Reflect.deleteProperty(proto, "offsetHeight")
    }
  }

  it("the pills' height plus the gap, when wide", () => {
    const restore = stubHeights(44, 120)
    try {
      const onHeightAbove = vi.fn()
      mount({ onHeightAbove, stacked: false })
      // 12 (bar -> pills) + 44 (the pills row) + 12 (pills -> pane) = 68. The Opas
      // pane is in the column LEFT of the bar when wide and takes no room above it.
      //
      // ⚠️ TWO GAPS, AND MY FIRST VERSION HAD ONE — 56, which put the pane's bottom
      // exactly on the pills' top. Touching is not clear, with a shadow and a border
      // in play, and the prototype's `.dock{gap:12px}` is between EVERY row.
      expect(onHeightAbove).toHaveBeenCalledWith(68)
    } finally {
      restore()
    }
  })

  it("the pills AND the Opas pane, when stacked", () => {
    const restore = stubHeights(44, 120)
    try {
      const onHeightAbove = vi.fn()
      mount({ onHeightAbove, stacked: true })
      // 12 + 44 + 12 (the pills with a gap each side) + 120 + 12 (the Opas pane and
      // the gap above it) = 200. Below 960px the pane is above the pills, so the room
      // needed above the bar is both.
      expect(onHeightAbove).toHaveBeenCalledWith(200)
    } finally {
      restore()
    }
  })

  it("two rows of pills take twice the room — the wrapping case", () => {
    const restore = stubHeights(88, 120)
    try {
      const onHeightAbove = vi.fn()
      mount({ onHeightAbove, stacked: false })
      // ⚠️ THE CASE A CONSTANT WOULD GET WRONG. Same pills, narrower window, two
      // rows: 12 + 88 + 12 = 112.
      expect(onHeightAbove).toHaveBeenCalledWith(112)
    } finally {
      restore()
    }
  })

  it("zero when there are no pills, so the pane keeps touching the bar", () => {
    /** ⚠️ ZERO IS LOAD-BEARING. The pane touching the bar with no pills was asked for
     *  last round — "`bottom: 96` was a guess against a ~46px bar and left it
     *  floating" — so reserving room for a row that is not rendered would undo it. */
    const restore = stubHeights(0, 120)
    try {
      const onHeightAbove = vi.fn()
      mount({ onHeightAbove, pills: [], stacked: false })
      expect(onHeightAbove).toHaveBeenCalledWith(0)
    } finally {
      restore()
    }
  })

  it("reports zero on the way out", () => {
    /** ⚠️ WITHOUT THIS THE PANE KEEPS THE ROOM RESERVED for a pills row that is no
     *  longer rendered, leaving a gap above the bar for the rest of the session. */
    const restore = stubHeights(44, 120)
    try {
      const onHeightAbove = vi.fn()
      const { unmount } = render(
        <GuidedQuestion
          question="Which funeral home?"
          hint={null}
          fieldId="funeral_home"
          pills={PILLS}
          barHeight={46}
          barWidth="600px"
          stacked={false}
          barIsEmpty
          questionTakesNumbers={false}
          onAnswer={vi.fn()}
          onHeightAbove={onHeightAbove}
        />,
      )
      onHeightAbove.mockClear()
      unmount()
      expect(onHeightAbove).toHaveBeenCalledWith(0)
    } finally {
      restore()
    }
  })
})

describe("nothing overlaps, at 1280 and at 1920", () => {
  /**
   * James's fixes, clause 1: "The pills row takes its own space: pane, then pills,
   * then bar, with nothing overlapping at any width. Screenshot at 1280 and 1920 to
   * prove it."
   *
   * ⚠️ I COULD NOT TAKE THE SCREENSHOTS — the Chrome extension is not connected in
   * this environment, so there is no browser to drive. Stated plainly rather than
   * skipped: this test proves the ARITHMETIC at both widths and NOT the render, and
   * those are different things. A CSS rule I have not thought of could still overlap
   * two boxes whose numbers clear each other.
   *
   * ⚠️ WHAT IT DOES PROVE IS THE THING THAT WAS WRONG. The pane was anchored at
   * `bottom: 24 + barH` — the bar's top edge — while the pills sit above that edge, so
   * the two rectangles genuinely intersected. That is an arithmetic fact and this is
   * where it is now checked, at both widths, with the pills wrapping at the narrow one.
   */
  const BAR_H = 46

  /** The three boxes as `bottom` / `height` pairs, measured up from the viewport floor.
   *
   * ⚠️ THE PANE'S ANCHOR COMES FROM `paneBottomPx`, THE FUNCTION THE HOST CALLS, not
   * from a copy of its arithmetic. My first version wrote `BAR_INSET + BAR_H +
   * guidedAbove` here — a check derived from the implementation, which would have
   * stayed green if the host's anchor changed. Importing it is what makes this test
   * watch the thing that ships.
   */
  function boxes(viewportWidth: number, pillsHeight: number, guidedAbove: number) {
    const barWidth = Math.min(600, viewportWidth - 48)
    return {
      barWidth,
      bar: { bottom: BAR_INSET, height: BAR_H },
      pills: { bottom: BAR_INSET + BAR_H + 12, height: pillsHeight },
      pane: { bottom: paneBottomPx(BAR_H, guidedAbove), height: 300 },
    }
  }

  function overlaps(
    a: { bottom: number; height: number },
    b: { bottom: number; height: number },
  ) {
    return a.bottom < b.bottom + b.height && b.bottom < a.bottom + a.height
  }

  it("at 1920 — four pills on one row", () => {
    // one row of pills: 12 + 44 + 12
    const { bar, pills, pane, barWidth } = boxes(1920, 44, 68)
    expect(barWidth).toBe(600)
    expect(overlaps(pills, bar)).toBe(false)
    expect(overlaps(pane, pills)).toBe(false)
    expect(overlaps(pane, bar)).toBe(false)
    // ⚠️ AND THE ORDER IS PANE, PILLS, BAR going up the screen, which is the clause's
    // own words. Asserting the order as well as the absence of overlap, because three
    // boxes can clear each other in the wrong sequence.
    expect(bar.bottom).toBeLessThan(pills.bottom)
    expect(pills.bottom).toBeLessThan(pane.bottom)
  })

  it("at 1280 — the same pills wrap to two rows", () => {
    // ⚠️ THE WRAPPING CASE IS THE ONE A CONSTANT GETS WRONG, and 1280 is where James
    // asked for it. Two rows: 12 + 88 + 12.
    const { bar, pills, pane, barWidth } = boxes(1280, 88, 112)
    expect(barWidth).toBe(600)
    expect(overlaps(pills, bar)).toBe(false)
    expect(overlaps(pane, pills)).toBe(false)
    expect(bar.bottom).toBeLessThan(pills.bottom)
    expect(pills.bottom).toBeLessThan(pane.bottom)
  })

  it("⚠️ THE OLD ANCHOR OVERLAPPED — the positive control for all of the above", () => {
    /**
     * ⚠️ WITHOUT THIS THE TESTS ABOVE PROVE NOTHING. "These boxes do not overlap" is
     * satisfied by arithmetic that could never overlap; the question is whether the
     * check can see the defect that was there. `bottom: 24 + barH` with no room for
     * the pills is exactly what shipped, and it must come out as an overlap.
     */
    const { pills, pane } = boxes(1920, 44, 0)
    expect(pane.bottom).toBe(BAR_INSET + BAR_H)
    expect(overlaps(pane, pills)).toBe(true)
  })

  it("at 640 — stacked, and the Opas pane is in the column too", () => {
    /** Below the prototype's 960px breakpoint the Opas pane moves above the pills, so
     *  the room above the bar is both: 12 + 44 + 12 + 120 + 12 = 200. */
    const { bar, pills, pane } = boxes(640, 44, 200)
    expect(overlaps(pane, pills)).toBe(false)
    expect(overlaps(pills, bar)).toBe(false)
    // and the bar narrows with the viewport
    expect(boxes(640, 44, 200).barWidth).toBe(640 - 48)
  })
})

// ── JAMES'S RULING OF 2026-10-28: THE PICK SHORTCUT IS A PER-USER SETTING ─────────
//
// "A preference on the user: pick modifier = Option (default) | Control | Command.
//  Pill labels show the chosen key (⌥1 / ⌃1 / ⌘1). Read the key by e.code, as now."
//
// ⚠️ EVERY TEST BELOW BUILDS ITS OWN `KeyboardEvent` RATHER THAN USING
// `userEvent.keyboard`. `userEvent.keyboard("{Control>}1{/Control}")` sets `key: "1"`,
// so it would pass against a handler that read `e.key` — and on a Mac ⌥1 really is "¡".
// The helper above exists for that reason and these extend it.

/** Dispatch a digit with an arbitrary modifier, the way a browser would. */
function pressDigitWith(
  n: number,
  mods: { alt?: boolean; ctrl?: boolean; meta?: boolean; shift?: boolean } = {},
): boolean {
  const MAC_ALT_DIGITS = ["¡", "™", "£", "¢", "∞", "§", "¶", "•", "ª"]
  const e = new KeyboardEvent("keydown", {
    code: `Digit${n}`,
    key: mods.alt ? MAC_ALT_DIGITS[n - 1] : String(n),
    altKey: mods.alt ?? false,
    ctrlKey: mods.ctrl ?? false,
    metaKey: mods.meta ?? false,
    shiftKey: mods.shift ?? false,
    bubbles: true,
    cancelable: true,
  })
  // ⚠️ `act` BECAUSE THESE KEYSTROKES CHANGE REACT STATE. The digit helper above does
  // not need it — it only calls a mock — but the highlight is `useState`, so without
  // `act` the state updates and the DOM this test reads has not re-rendered yet. The
  // symptom is `data-highlighted` reading null while the component is correct.
  act(() => {
    document.dispatchEvent(e)
  })
  return e.defaultPrevented
}

function pressKey(key: string, mods: { shift?: boolean; alt?: boolean } = {}): boolean {
  const e = new KeyboardEvent("keydown", {
    key,
    code: key.startsWith("Arrow") ? key : undefined,
    shiftKey: mods.shift ?? false,
    altKey: mods.alt ?? false,
    bubbles: true,
    cancelable: true,
  })
  act(() => {
    document.dispatchEvent(e)
  })
  return e.defaultPrevented
}

describe("the pick modifier is a per-user setting", () => {
  it("labels every pill with the chosen glyph, not a hard-coded ⌥", () => {
    mount({ pickModifier: "control", pickModifierGlyph: "⌃" })
    for (const n of [1, 2, 3]) {
      expect(screen.getByTestId(`opas-guided-pill-key-${n}`).textContent).toBe(`⌃${n}`)
    }
    // ⚠️ THE CONTROL: the old glyph must be GONE, not merely joined. A label reading
    // "⌥1 ⌃1" would satisfy a `toContain` and instruct two different keys.
    expect(screen.queryByText("⌥1")).toBeNull()
  })

  it("falls back to this file's table when the server sent no glyph", () => {
    // ⚠️ THE WINDOW BEFORE THE PREFERENCE READ LANDS IS A REAL STATE, and the pills
    // must be labelled correctly in it rather than blank or wrong.
    mount({ pickModifier: "command" })
    expect(screen.getByTestId("opas-guided-pill-key-1").textContent).toBe("⌘1")
  })

  // ⚠️ `barIsEmpty: false` ON EVERY CHORD TEST, AND A BREAK TEST IS WHY. With the bar
  // EMPTY a plain digit picks, so these tests passed with the chord hard-coded back to
  // ⌥ — the bare-digit path was answering and the modifier preference was untested.
  // CLAUDE.md §11 shape 6: a check passing for a reason unrelated to what it claims.
  // Mid-phrase, the chord is the ONLY route in, so it is the only thing under test.
  const MIDPHRASE = { barIsEmpty: false } as const

  it("Control picks when Control is the preference", () => {
    const { onAnswer } = mount({ ...MIDPHRASE, pickModifier: "control" })
    expect(pressDigitWith(2, { ctrl: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "riverside")
  })

  it("⌥ does NOT pick when Control is the preference", () => {
    // ⚠️ THE HALF THAT MAKES THE SETTING REAL. Without this, a handler that accepted
    // any modifier would pass the test above and the preference would be decoration.
    const { onAnswer } = mount({ ...MIDPHRASE, pickModifier: "control" })
    expect(pressDigitWith(2, { alt: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
  })

  it("Command picks when Command is the preference, and ⌥ does not", () => {
    const { onAnswer } = mount({ ...MIDPHRASE, pickModifier: "command" })
    expect(pressDigitWith(1, { meta: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "hopkins")
    onAnswer.mockClear()
    expect(pressDigitWith(1, { alt: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
  })

  it("Option still picks by default, which is the 2026-10-27 ruling", () => {
    const { onAnswer } = mount(MIDPHRASE)
    expect(pressDigitWith(3, { alt: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "brown")
  })

  it("Control does NOT pick when Option is the preference", () => {
    // ⚠️ THE OTHER DIRECTION, because a handler that accepted ctrl unconditionally
    // would pass every test above.
    const { onAnswer } = mount({ ...MIDPHRASE, pickModifier: "option" })
    expect(pressDigitWith(1, { ctrl: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
  })

  it("Shift never picks, whatever the preference", () => {
    for (const m of ["option", "control", "command"] as const) {
      const { onAnswer } = mount({ barIsEmpty: false, pickModifier: m })
      expect(pressDigitWith(1, { alt: m === "option", ctrl: m === "control",
                                 meta: m === "command", shift: true })).toBe(false)
      expect(onAnswer).not.toHaveBeenCalled()
      cleanup()
    }
  })

  it("a plain digit still picks while the bar is empty — clause 2, unchanged", () => {
    const { onAnswer } = mount({ pickModifier: "control", barIsEmpty: true })
    expect(pressDigitWith(1)).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "hopkins")
  })

  it("a plain digit does NOT pick while the question takes numbers — unchanged", () => {
    const { onAnswer } = mount({
      pickModifier: "control", barIsEmpty: true, questionTakesNumbers: true,
    })
    expect(pressDigitWith(1)).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
    // ⚠️ AND THE CHORD STILL WORKS THERE, which is the point of having one.
    expect(pressDigitWith(1, { ctrl: true })).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "hopkins")
  })
})

describe("the arrow highlight — clause 3", () => {
  function highlighted(): number | null {
    for (const n of [1, 2, 3, 4, 5, 6, 7, 8, 9]) {
      const el = screen.queryByTestId(`opas-guided-pill-${n}`)
      if (el?.getAttribute("data-highlighted") === "true") return n
    }
    return null
  }

  it("starts with NOTHING highlighted, and Enter is not claimed", () => {
    // ⚠️ THE MOST IMPORTANT TEST IN THIS BLOCK. If a fresh question highlighted pill 1,
    // Enter — which the bar uses to finish the order — would silently answer instead.
    mount({ barIsEmpty: true })
    expect(highlighted()).toBeNull()
    expect(pressKey("Enter")).toBe(false)
  })

  it("→ moves the highlight forward and ← moves it back", () => {
    mount({ barIsEmpty: true })
    expect(pressKey("ArrowRight")).toBe(true)
    expect(highlighted()).toBe(1)
    pressKey("ArrowRight")
    expect(highlighted()).toBe(2)
    pressKey("ArrowLeft")
    expect(highlighted()).toBe(1)
  })

  it("↓ and ↑ do the same as → and ←", () => {
    mount({ barIsEmpty: true })
    pressKey("ArrowDown")
    expect(highlighted()).toBe(1)
    pressKey("ArrowDown")
    expect(highlighted()).toBe(2)
    pressKey("ArrowUp")
    expect(highlighted()).toBe(1)
  })

  it("clamps at both ends rather than wrapping", () => {
    // ⚠️ WRAPPING WOULD MEAN → AT THE LAST PILL LANDS ON THE FIRST, so somebody
    // holding → to reach the end cycles past it forever.
    mount({ barIsEmpty: true })
    for (let i = 0; i < 8; i += 1) pressKey("ArrowRight")
    expect(highlighted()).toBe(3)
    for (let i = 0; i < 8; i += 1) pressKey("ArrowLeft")
    expect(highlighted()).toBe(1)
  })

  it("Enter picks the highlighted pill", () => {
    const { onAnswer } = mount({ barIsEmpty: true })
    pressKey("ArrowRight")
    pressKey("ArrowRight")
    expect(pressKey("Enter")).toBe(true)
    expect(onAnswer).toHaveBeenCalledWith("funeral_home", "riverside")
  })

  it("typing clears the highlight, and Enter goes back to submitting text", () => {
    const { onAnswer } = mount({ barIsEmpty: true })
    pressKey("ArrowRight")
    expect(highlighted()).toBe(1)
    // one printable character
    pressKey("h")
    expect(highlighted()).toBeNull()
    // ⚠️ AND ENTER IS NO LONGER CLAIMED, which is the half that matters: the bar's own
    // Enter finishes the order, and intercepting it here would break that.
    expect(pressKey("Enter")).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
  })

  it("the arrows do nothing while the bar holds text", () => {
    // ⚠️ ← AND → ARE HOW YOU MOVE THE CARET. Stealing them mid-phrase makes the bar
    // uneditable, which is a worse defect than the feature is a benefit.
    mount({ barIsEmpty: false })
    expect(pressKey("ArrowRight")).toBe(false)
    expect(highlighted()).toBeNull()
  })

  it("a modified arrow is left alone", () => {
    // ⚠️ ⌥← AND ⇧← ARE WORD-WISE AND SELECTING MOVEMENTS. Claiming them would break
    // text editing in a textarea that is usually holding a sentence.
    mount({ barIsEmpty: true })
    expect(pressKey("ArrowRight", { shift: true })).toBe(false)
    expect(pressKey("ArrowRight", { alt: true })).toBe(false)
    expect(highlighted()).toBeNull()
  })

  it("the highlight resets when the question changes", () => {
    // ⚠️ INDEX 2 OF FOUR CEMETERIES IS NOT INDEX 2 OF THREE EQUIPMENT PACKAGES. A
    // highlight carried across questions points at a pill that may not exist.
    const { rerender } = renderWithRerender({ barIsEmpty: true })
    pressKey("ArrowRight")
    pressKey("ArrowRight")
    expect(highlighted()).toBe(2)
    rerender({ barIsEmpty: true, fieldId: "cemetery", pills: [
      { value: "St. Mary's", label: "St. Mary's" },
    ] })
    expect(highlighted()).toBeNull()
  })
})
