import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

// Debounce → identity so the search effect fires without timer juggling.
vi.mock("@/hooks/useDebouncedValue", () => ({ useDebouncedValue: (v: unknown) => v }))

const { mockSearch } = vi.hoisted(() => ({ mockSearch: vi.fn() }))
vi.mock("@/services/reconciliation-flag-service", () => ({ searchFlagRecipients: mockSearch }))

import { FlagDestinationPicker } from "./FlagDestinationPicker"

afterEach(cleanup)

describe("FlagDestinationPicker — destinations state their return condition", () => {
  it("shows three destinations, each with its return condition (not bare names)", () => {
    render(<FlagDestinationPicker open onClose={() => {}} onFlag={() => {}} />)
    expect(screen.getByText("Ask someone")).toBeInTheDocument()
    expect(screen.getByText("Returns when they complete the task")).toBeInTheDocument()
    expect(screen.getByText("Hold for documentation")).toBeInTheDocument()
    expect(screen.getByText("Returns when a document is attached")).toBeInTheDocument()
    expect(screen.getByText("Accept as a reconciling item")).toBeInTheDocument()
    expect(screen.getByText(/amount posts as a reconciling difference/)).toBeInTheDocument()
  })

  it("hold_for_documentation flags immediately and closes", () => {
    const onFlag = vi.fn()
    const onClose = vi.fn()
    render(<FlagDestinationPicker open onClose={onClose} onFlag={onFlag} />)
    fireEvent.click(screen.getByText("Hold for documentation"))
    expect(onFlag).toHaveBeenCalledWith({ destination: "hold_for_documentation" })
    expect(onClose).toHaveBeenCalled()
  })

  it("accept_reconciling (terminal) flags immediately", () => {
    const onFlag = vi.fn()
    render(<FlagDestinationPicker open onClose={() => {}} onFlag={onFlag} />)
    fireEvent.click(screen.getByText("Accept as a reconciling item"))
    expect(onFlag).toHaveBeenCalledWith({ destination: "accept_reconciling" })
  })
})

describe("FlagDestinationPicker — recipient search (async, caller-owned seam)", () => {
  it("ask someone → search → pick a recipient → flags with recipient_user_id; shows waiting count", async () => {
    mockSearch.mockResolvedValue([
      { id: "u1", name: "Dana R", email: "dana@x", waiting_count: 14 },
      { id: "u2", name: "Sam T", email: "sam@x", waiting_count: 0 },
    ])
    const onFlag = vi.fn()
    render(<FlagDestinationPicker open onClose={() => {}} onFlag={onFlag} />)
    fireEvent.click(screen.getByText("Ask someone"))
    fireEvent.change(screen.getByLabelText("Recipient search"), { target: { value: "da" } })

    expect(await screen.findByText("Dana R")).toBeInTheDocument()
    expect(screen.getByText("14 already waiting")).toBeInTheDocument()
    // Sam has 0 waiting → no badge
    expect(screen.queryByText("0 already waiting")).not.toBeInTheDocument()

    fireEvent.click(screen.getByText("Dana R"))
    expect(onFlag).toHaveBeenCalledWith({ destination: "ask_someone", recipient_user_id: "u1" })
    expect(mockSearch).toHaveBeenCalled()  // the caller drove the fetch
  })

  it("empty results show keep-typing (caller-owned empty state)", async () => {
    mockSearch.mockResolvedValue([])
    render(<FlagDestinationPicker open onClose={() => {}} onFlag={() => {}} />)
    fireEvent.click(screen.getByText("Ask someone"))
    expect(await screen.findByText(/keep typing/i)).toBeInTheDocument()
  })
})
