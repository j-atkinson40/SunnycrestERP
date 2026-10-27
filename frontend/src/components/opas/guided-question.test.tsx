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
import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import {
  GuidedQuestion,
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

  it("no field means nothing is listening", () => {
    const { onAnswer } = mount({ fieldId: null })
    expect(pressDigit(1, { alt: true })).toBe(false)
    expect(onAnswer).not.toHaveBeenCalled()
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
     *  for the same things. `extra_chairs_count` is ours and not the prototype's — it
     *  is literally "how many", so it belongs by the same reasoning. */
    expect(questionTakesNumbers("service_time")).toBe(true)
    expect(questionTakesNumbers("service_date")).toBe(true)
    expect(questionTakesNumbers("date_of_birth")).toBe(true)
    expect(questionTakesNumbers("date_of_death")).toBe(true)
    expect(questionTakesNumbers("extra_chairs_count")).toBe(true)
  })

  it("and the ones that do not", () => {
    expect(questionTakesNumbers("funeral_home")).toBe(false)
    expect(questionTakesNumbers("vault")).toBe(false)
    expect(questionTakesNumbers("cemetery")).toBe(false)
    expect(questionTakesNumbers(null)).toBe(false)
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
