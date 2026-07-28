/**
 * Park tablets (S-5) — the 4th-host re-host proof + the NO-DATA-BEFORE-
 * COMMIT guarantee.
 *
 * (1) RE-HOST: the three tablet surfaces AND the existing S-2
 *     surface.quote-preview all resolve through the SAME getWidgetRenderer
 *     registry — proving the park host is the 4th host (Act-inline /
 *     Focus-core / Focus-pin / park-tablet), no rewrite.
 * (2) NO-DATA-BEFORE-COMMIT: summon the light acts, draft in each, end the
 *     session WITHOUT committing → ZERO writes. The commit fires ONLY at
 *     the tablet's own Send/Save gesture.
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react"
import { useEffect, useRef, type ReactNode } from "react"

// Focus stub (park consumes useFocusOptional).
vi.mock("@/contexts/focus-context", () => ({
  useFocusOptional: () => ({ isOpen: false, open: vi.fn() }),
}))

// Mock the shipped commit service — createNote is THE write park must not
// fire before a gesture.
const createNote = vi.fn().mockResolvedValue({ id: "n1" })
vi.mock("@/services/customer-service", () => ({
  customerService: {
    createNote: (...a: unknown[]) => createNote(...a),
    getCustomers: vi
      .fn()
      .mockResolvedValue({ items: [{ id: "c1", name: "Acme Co" }], total: 1 }),
  },
}))

import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { ParkProvider, usePark } from "@/contexts/park-context"
import { ReplyDmTablet } from "./tablets/ReplyDmTablet"
import { AddNoteTablet } from "./tablets/AddNoteTablet"
import { StartQuoteTablet } from "./tablets/StartQuoteTablet"
// Register the existing S-2 surface so the re-host lookup resolves it.
import "@/components/command-bar-surfaces/QuotePreviewWidget"

beforeEach(() => createNote.mockClear())

describe("Park tablets — 4th-host re-host proof", () => {
  it("the three tablet surfaces resolve through getWidgetRenderer", () => {
    expect(getWidgetRenderer("park.reply-dm")).toBe(ReplyDmTablet)
    expect(getWidgetRenderer("park.add-note")).toBe(AddNoteTablet)
    expect(getWidgetRenderer("park.start-quote")).toBe(StartQuoteTablet)
  })

  it("the existing S-2 surface.quote-preview mounts in park unchanged", () => {
    // The 4th host mounts an EXISTING surface via the SAME registry — the
    // load-bearing "every surface is park-able" claim.
    const R = getWidgetRenderer("surface.quote-preview")
    expect(R).toBeTruthy()
    expect(R.name).not.toBe("MissingWidgetEmptyState")
  })
})

function LightHarness() {
  const { summon, tablets, exitPark } = usePark()
  const seeded = useRef(false)
  useEffect(() => {
    if (seeded.current) return
    seeded.current = true
    summon("reply-dm")
    summon("add-note")
  }, [summon])
  return (
    <div>
      {tablets.map((t) =>
        t.actType === "reply-dm" ? (
          <ReplyDmTablet key={t.tabletId} widgetId={t.tabletId} surface="park" />
        ) : (
          <AddNoteTablet key={t.tabletId} widgetId={t.tabletId} surface="park" />
        ),
      )}
      <button data-testid="do-exit" onClick={exitPark}>
        exit
      </button>
    </div>
  )
}

const wrap = (node: ReactNode) => render(<ParkProvider>{node}</ParkProvider>)

describe("Park — NO DATA BEFORE COMMIT", () => {
  it("drafting in tablets then ending the session writes ZERO rows", async () => {
    wrap(<LightHarness />)
    // Two light tablets summoned + the reply seeds its sender.
    await waitFor(() =>
      expect(screen.getByTestId("park-reply-text")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("park-note-text")).toBeInTheDocument()

    // Draft in each — in-memory only.
    fireEvent.change(screen.getByTestId("park-reply-text"), {
      target: { value: "drafted reply, not sent" },
    })
    fireEvent.change(screen.getByTestId("park-note-text"), {
      target: { value: "drafted note, not saved" },
    })

    // End the session WITHOUT sending/saving.
    act(() => {
      screen.getByTestId("do-exit").click()
    })

    // THE INVARIANT: not one write fired from the un-committed drafts.
    expect(createNote).not.toHaveBeenCalled()
  })

  it("the reply commits ONLY at its Send gesture", async () => {
    wrap(<LightHarness />)
    await waitFor(() =>
      expect(screen.getByTestId("park-reply-text")).toBeInTheDocument(),
    )
    // Set text first, THEN wait for the seeded sender — the button enables
    // only when both are present (senderId from the async seed + text).
    fireEvent.change(screen.getByTestId("park-reply-text"), {
      target: { value: "the reply" },
    })
    await waitFor(() =>
      expect(screen.getByTestId("park-reply-send")).not.toBeDisabled(),
    )
    expect(createNote).not.toHaveBeenCalled() // nothing before the gesture

    fireEvent.click(screen.getByTestId("park-reply-send"))

    await waitFor(() => expect(createNote).toHaveBeenCalledTimes(1))
    expect(createNote).toHaveBeenCalledWith("c1", {
      note_type: "communication",
      content: "the reply",
    })
  })
})
