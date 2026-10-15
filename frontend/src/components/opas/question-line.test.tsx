/**
 * One question at a time, in the bar. James 2026-10-15.
 *
 * ⚠️ THE WORDING AND THE ORDER ARE THE SERVER'S, and these tests assert that the bar
 * SHOWS what it is sent rather than deciding anything. A frontend that built the
 * question itself would need its own copy of the call order, and the bar and the
 * pane would then disagree about what is outstanding — which is the defect the
 * header-chip-vs-bar tests were written to catch one layer down.
 */
import { describe, expect, it } from "vitest"

import { placeholderFor } from "./CapturePane"

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
    const asReport = placeholderFor({
      ...BASE,
      missingLabels: ["Service date", "Cemetery", "Cemetery equipment"],
    })
    expect(asReport).toBe("Still need: service date, cemetery, cemetery equipment")

    const asQuestion = placeholderFor({
      ...BASE,
      missingLabels: ["Service date", "Cemetery", "Cemetery equipment"],
      nextQuestion: "What day is the service?",
    })
    expect(asQuestion).toBe("What day is the service?")
  })

  it("shows the ready line when the server says nothing is missing", () => {
    expect(
      placeholderFor({
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
      placeholderFor({ ...BASE, missingLabels: ["Cemetery"], nextQuestion: null }),
    ).toBe("Still need: cemetery")
    expect(
      placeholderFor({ ...BASE, missingLabels: ["Cemetery"] }),
    ).toBe("Still need: cemetery")
  })

  it("does not override the states that are not about missing fields", () => {
    // ⚠️ A PICK STILL WINS. "Which one? 1–2" is a question too, and a more urgent
    // one — the director is mid-answer. Likewise the not-yet-started and in-flight
    // lines, which describe the pane rather than the order.
    expect(
      placeholderFor({
        ...BASE,
        picks: [{ options: [1, 2] }] as never,
        nextQuestion: "Which vault?",
      }),
    ).toContain("Which one?")
    expect(
      placeholderFor({ ...BASE, ready: false, nextQuestion: "Which vault?" }),
    ).toBe("Starting the order…")
    expect(
      placeholderFor({ ...BASE, inFlight: true, nextQuestion: "Which vault?" }),
    ).toBe("Reading what you typed…")
  })
})
