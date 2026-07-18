/**
 * The Map Home campaign — the suggestions rail's restraint pins.
 *
 *  * THE WHY-LINE IS LOAD-BEARING — every card renders its honest reason.
 *  * DISMISSAL RESPECTED — one X: recorded as `dismissed`, card gone,
 *    no resurrection (the backend rule skips dismissed keys; pinned there).
 *  * EMPTY-HONEST — no cards, no rail (nothing stretched).
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { SuggestionsRail } from "./SuggestionsRail"
import * as svc from "@/services/moc-map-service"

vi.mock("@/services/moc-map-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/services/moc-map-service")
  return { ...actual, getSuggestions: vi.fn(), recordEngagement: vi.fn() }
})

const CARDS = [
  {
    id: "onboarding:welcome-map", rule: "onboarding" as const,
    title: "Welcome to your Bridgeable Map",
    why: "Get set up — you haven't walked this yet.",
    ponder_key: "onboarding:welcome-map",
  },
  {
    id: "area:manufacturing:Accounting", rule: "role_area" as const,
    title: "How Accounting thinks",
    why: "You work in Accounting — see how it thinks.",
    ponder_key: "area:manufacturing:Accounting",
  },
]

describe("SuggestionsRail", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders each card WITH its why-line (load-bearing)", async () => {
    vi.mocked(svc.getSuggestions).mockResolvedValue(structuredClone(CARDS))
    render(<MemoryRouter><SuggestionsRail onOpen={() => {}} /></MemoryRouter>)
    await waitFor(() => screen.getByTestId("map-suggestions-rail"))
    expect(screen.getByTestId("map-suggestion-why-onboarding").textContent)
      .toContain("you haven't walked this yet")
    expect(screen.getByTestId("map-suggestion-why-role_area").textContent)
      .toContain("You work in Accounting")
  })

  it("dismissal records + removes the card", async () => {
    vi.mocked(svc.getSuggestions).mockResolvedValue(structuredClone(CARDS))
    render(<MemoryRouter><SuggestionsRail onOpen={() => {}} /></MemoryRouter>)
    await waitFor(() => screen.getByTestId("map-suggestion-onboarding"))
    fireEvent.click(screen.getByTestId("map-suggestion-dismiss-onboarding"))
    expect(svc.recordEngagement).toHaveBeenCalledWith(
      "onboarding:welcome-map", "dismissed",
    )
    expect(screen.queryByTestId("map-suggestion-onboarding")).toBeNull()
  })

  it("clicking a card opens its ponder", async () => {
    vi.mocked(svc.getSuggestions).mockResolvedValue(structuredClone(CARDS))
    const onOpen = vi.fn()
    render(<MemoryRouter><SuggestionsRail onOpen={onOpen} /></MemoryRouter>)
    await waitFor(() => screen.getByTestId("map-suggestion-role_area"))
    fireEvent.click(screen.getByTestId("map-suggestion-role_area"))
    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({ ponder_key: "area:manufacturing:Accounting" }),
    )
  })

  it("EMPTY-HONEST — no cards, no rail at all", async () => {
    vi.mocked(svc.getSuggestions).mockResolvedValue([])
    render(<MemoryRouter><SuggestionsRail onOpen={() => {}} /></MemoryRouter>)
    await new Promise((r) => setTimeout(r, 10))
    expect(screen.queryByTestId("map-suggestions-rail")).toBeNull()
  })
})
