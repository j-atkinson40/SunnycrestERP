/**
 * One question at a time, in Opas's one voice. James 2026-10-15, moved 2026-10-20.
 *
 * ⚠️ THE WORDING AND THE ORDER ARE THE SERVER'S, and these tests assert that the bar
 * SHOWS what it is sent rather than deciding anything. A frontend that built the
 * question itself would need its own copy of the call order, and the bar and the
 * pane would then disagree about what is outstanding — which is the defect the
 * header-chip-vs-bar tests were written to catch one layer down.
 *
 * ⚠️ RE-POINTED FROM `placeholderFor` TO `captureVoice` ON 2026-10-20, BY RULING:
 * "capture's question moves into the reply line above the bar and stays visible while
 * typing; the placeholder goes back to a plain prompt. One voice everywhere."
 *
 * ⚠️ AND THE MOVE IS A BUG FIX. These four tests passed from the day they were written
 * and the thing they assert was never on screen: the bar rendered the string as a
 * textarea `placeholder`, which shows only when the field is EMPTY, while
 * `placeholderFor` returned the question only when the text was NON-empty. The two
 * conditions are mutually exclusive. See `the question nobody could see` at the end of
 * this file, which pins the four strings that were unreachable.
 */
import { describe, expect, it } from "vitest"

import { ENTRY_PLACEHOLDER, captureVoice } from "./CapturePane"

const BASE = {
  ready: true,
  inFlight: false,
  text: "order for riverside",
  picks: [] as never[],
  missing: 3,
  reviewing: false,
}

describe("the question line", () => {
  it("shows the server's question instead of listing every gap", () => {
    // ⚠️ THE OLD SENTENCE IS THE CONTRAST. Three gaps at once is a report; the
    // dispatch asks for a conversation.
    const asReport = captureVoice({
      ...BASE,
      missingLabels: ["Service date", "Cemetery", "Cemetery equipment"],
    })
    expect(asReport).toBe("Still need: service date, cemetery, cemetery equipment")

    const asQuestion = captureVoice({
      ...BASE,
      missingLabels: ["Service date", "Cemetery", "Cemetery equipment"],
      nextQuestion: "What day is the service?",
    })
    expect(asQuestion).toBe("What day is the service?")
  })

  it("shows the ready line when the server says nothing is missing", () => {
    expect(
      captureVoice({
        ...BASE,
        missing: 0,
        nextQuestion: "Ready. Press Enter to review.",
      }),
    ).toBe("Ready. Press Enter to review.")
  })

  it("falls back to the old sentence when an older server sends no question", () => {
    // ⚠️ THE 2026-10-12 BLANK-PANE DEFECT WAS A KEY AN OLDER SERVER OMITTED. A
    // deploy where the bundle leads the API must degrade, not blank.
    expect(
      captureVoice({ ...BASE, missingLabels: ["Cemetery"], nextQuestion: null }),
    ).toBe("Still need: cemetery")
    expect(
      captureVoice({ ...BASE, missingLabels: ["Cemetery"] }),
    ).toBe("Still need: cemetery")
  })

  it("does not override the states that are not about missing fields", () => {
    // ⚠️ A PICK STILL WINS. "Which one? 1–2" is a question too, and a more urgent
    // one — the director is mid-answer. Likewise the not-yet-started and in-flight
    // lines, which describe the pane rather than the order.
    expect(
      captureVoice({
        ...BASE,
        picks: [{ options: [1, 2] }] as never,
        nextQuestion: "Which vault?",
      }),
    ).toContain("Which one?")
    expect(
      captureVoice({ ...BASE, ready: false, nextQuestion: "Which vault?" }),
    ).toBe("Starting the order…")
    expect(
      captureVoice({ ...BASE, inFlight: true, nextQuestion: "Which vault?" }),
    ).toBe("Reading what you typed…")
  })
})

describe("⚠️ the question nobody could see", () => {
  const BASE2 = {
    ready: true, inFlight: false, picks: [] as never[], reviewing: false,
  }

  it("the prompt left the voice, and is now the bar's own", () => {
    // ⚠️ THE BRANCH THAT CAUSED IT, DELETED. `placeholderFor` opened with
    //     if (args.text.trim() === "") return "Say what the director said"
    // which stood in front of every question below it for the ONLY state in which a
    // textarea renders its placeholder. The prompt is now a constant on the bar and
    // this function answers one question: what does Opas say about this order.
    expect(ENTRY_PLACEHOLDER).toBe("Say what the director said")
    expect(captureVoice({ ...BASE2, text: "", missing: 1, missingLabels: ["Cemetery"] }))
      .toBe("Still need: cemetery")
    expect(captureVoice({ ...BASE2, text: "", missing: 0, nextQuestion: "What day is the service?" }))
      .toBe("What day is the service?")
  })

  it("every question state is reachable with an EMPTY bar, which is where it will be read", () => {
    // ⚠️ THE FOUR THAT WERE UNREACHABLE, each asserted at `text: ""` — the state the
    // old function answered with a prompt instead. Measured 2026-10-20: these four of
    // nine return values could not appear on screen under the old arrangement.
    expect(captureVoice({ ...BASE2, text: "", missing: 2, nextQuestion: "Which cemetery?" }))
      .toBe("Which cemetery?")
    expect(captureVoice({ ...BASE2, text: "", missing: 1, missingLabels: ["Service date"] }))
      .toBe("Still need: service date")
    expect(captureVoice({ ...BASE2, text: "", missing: 3, missingLabels: [] }))
      .toBe("3 still needed — keep typing")
    expect(captureVoice({ ...BASE2, text: "", missing: 0 }))
      .toBe("Nothing needed — say “that’s it”")
  })

  it("and the same string comes back once the bar HAS text — the voice does not change under typing", () => {
    // ⚠️ "STAYS VISIBLE WHILE TYPING" NEEDS BOTH ENDS TO AGREE. A function that said one
    // thing with an empty bar and another with text would make the question flicker on
    // the first keystroke, which is the defect in a different costume.
    for (const text of ["", "o", "order for hopkins"]) {
      expect(captureVoice({ ...BASE2, text, missing: 2, nextQuestion: "Which cemetery?" }))
        .toBe("Which cemetery?")
    }
  })
})
