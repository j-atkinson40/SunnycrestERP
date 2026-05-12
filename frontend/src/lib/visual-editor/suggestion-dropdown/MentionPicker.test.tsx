/**
 * Arc 4b.2b — MentionPicker component tests.
 *
 * Covers:
 *   - Renders entity-type tabs (4-subset: case/order/contact/product)
 *   - Active tab attribute discriminates by data-active
 *   - Fetches mention candidates via document-mentions-service
 *   - Renders results with display_name + entity_type badge + preview
 *   - Empty state copy varies by query / loading / error
 *   - Click tab fires onSwitchEntityType
 *   - Click candidate fires onSelectCandidate with full candidate
 *   - Renders nothing when pickerState.open === false
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { useRef } from "react"
import { fireEvent, render, waitFor } from "@testing-library/react"

import { MentionPicker } from "./MentionPicker"
import type { MentionPickerState } from "./useMentionPicker"


// Mock the document-mentions-service so we control resolveMention.
const resolveMentionMock = vi.fn()
vi.mock("@/bridgeable-admin/services/document-mentions-service", async () => {
  const actual = await vi.importActual<
    typeof import("@/bridgeable-admin/services/document-mentions-service")
  >("@/bridgeable-admin/services/document-mentions-service")
  return {
    ...actual,
    resolveMention: (...args: unknown[]) => resolveMentionMock(...args),
  }
})


function MountHarness({
  state,
  onSelectCandidate = vi.fn(),
  onCancelKeepText = vi.fn(),
  onCancelEraseText = vi.fn(),
  onSwitchEntityType = vi.fn(),
}: {
  state: MentionPickerState
  onSelectCandidate?: (c: { entity_type: string; entity_id: string }) => void
  onCancelKeepText?: () => void
  onCancelEraseText?: () => void
  onSwitchEntityType?: (next: "case" | "order" | "contact" | "product") => void
}) {
  const fieldRef = useRef<HTMLTextAreaElement | null>(null)
  return (
    <div>
      <textarea ref={fieldRef} defaultValue="@" data-testid="field" />
      <MentionPicker
        pickerState={state}
        fieldRef={fieldRef}
        onSelectCandidate={(c) => onSelectCandidate(c)}
        onCancelKeepText={onCancelKeepText}
        onCancelEraseText={onCancelEraseText}
        onSwitchEntityType={onSwitchEntityType}
        debounceMs={0}
      />
    </div>
  )
}


beforeEach(() => {
  resolveMentionMock.mockReset()
  resolveMentionMock.mockResolvedValue({ results: [], total: 0 })
})


describe("MentionPicker — closed state", () => {
  it("renders nothing when pickerState.open === false", () => {
    const { queryByTestId } = render(
      <MountHarness
        state={{ open: false, triggerPosition: -1, query: "", entityType: "case" }}
      />,
    )
    expect(queryByTestId("documents-mention-picker")).toBeNull()
  })
})


describe("MentionPicker — entity-type tabs", () => {
  it("renders all 4 canonical entity-type tabs", () => {
    const { getByTestId } = render(
      <MountHarness
        state={{ open: true, triggerPosition: 0, query: "", entityType: "case" }}
      />,
    )
    expect(getByTestId("documents-mention-picker-tab-case")).toBeTruthy()
    expect(getByTestId("documents-mention-picker-tab-order")).toBeTruthy()
    expect(getByTestId("documents-mention-picker-tab-contact")).toBeTruthy()
    expect(getByTestId("documents-mention-picker-tab-product")).toBeTruthy()
  })

  it("marks the active tab via data-active=true", () => {
    const { getByTestId } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "",
          entityType: "order",
        }}
      />,
    )
    expect(
      getByTestId("documents-mention-picker-tab-order").getAttribute(
        "data-active",
      ),
    ).toBe("true")
    expect(
      getByTestId("documents-mention-picker-tab-case").getAttribute(
        "data-active",
      ),
    ).toBe("false")
  })

  it("clicking a tab fires onSwitchEntityType", () => {
    const onSwitch = vi.fn()
    const { getByTestId } = render(
      <MountHarness
        state={{ open: true, triggerPosition: 0, query: "", entityType: "case" }}
        onSwitchEntityType={onSwitch}
      />,
    )
    fireEvent.mouseDown(getByTestId("documents-mention-picker-tab-contact"))
    expect(onSwitch).toHaveBeenCalledWith("contact")
  })
})


describe("MentionPicker — fetch + render results", () => {
  it("calls resolveMention with correct entity_type + query", async () => {
    resolveMentionMock.mockResolvedValueOnce({
      results: [
        {
          entity_type: "case",
          entity_id: "FC-2026-0001",
          display_name: "John Michael Smith",
          preview_snippet: "Hopkins FH · 2026-01-15",
        },
      ],
      total: 1,
    })
    render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "Hop",
          entityType: "case",
        }}
      />,
    )
    await waitFor(() => {
      expect(resolveMentionMock).toHaveBeenCalledWith({
        entity_type: "case",
        query: "Hop",
        limit: 10,
      })
    })
  })

  it("renders result row with display_name + entity_type badge", async () => {
    resolveMentionMock.mockResolvedValueOnce({
      results: [
        {
          entity_type: "case",
          entity_id: "FC-1",
          display_name: "Hopkins Family Case",
          preview_snippet: "Funeral home pickup pending",
        },
      ],
      total: 1,
    })
    const { getByTestId, findByTestId } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "Hop",
          entityType: "case",
        }}
      />,
    )
    const row = await findByTestId("documents-mention-picker-row-FC-1")
    expect(row.textContent).toContain("Hopkins Family Case")
    const badge = getByTestId("documents-mention-picker-row-FC-1-type")
    expect(badge.textContent).toBe("case")
  })

  it("clicking a row fires onSelectCandidate with the candidate", async () => {
    resolveMentionMock.mockResolvedValueOnce({
      results: [
        {
          entity_type: "order",
          entity_id: "SO-42",
          display_name: "Vault Order 42",
          preview_snippet: null,
        },
      ],
      total: 1,
    })
    const onSelect = vi.fn()
    const { findByTestId } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "Vault",
          entityType: "order",
        }}
        onSelectCandidate={onSelect}
      />,
    )
    const row = await findByTestId("documents-mention-picker-row-SO-42")
    fireEvent.mouseDown(row)
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        entity_type: "order",
        entity_id: "SO-42",
        display_name: "Vault Order 42",
      }),
    )
  })
})


describe("MentionPicker — empty / loading / error states", () => {
  it("renders 'Start typing' empty state when query is empty", async () => {
    resolveMentionMock.mockResolvedValueOnce({ results: [], total: 0 })
    const { findByText } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "",
          entityType: "case",
        }}
      />,
    )
    // Wait for the resolved (non-loading) empty-state copy.
    const empty = await findByText(/start typing/i)
    expect(empty).toBeTruthy()
  })

  it("renders 'No <entities> match' when results empty + query non-empty", async () => {
    resolveMentionMock.mockResolvedValueOnce({ results: [], total: 0 })
    const { findByText } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "xyzzz",
          entityType: "contact",
        }}
      />,
    )
    const empty = await findByText(/xyzzz/)
    expect(empty).toBeTruthy()
  })

  it("renders error state when resolveMention rejects", async () => {
    resolveMentionMock.mockRejectedValueOnce(new Error("network failure"))
    const { findByText } = render(
      <MountHarness
        state={{
          open: true,
          triggerPosition: 0,
          query: "X",
          entityType: "product",
        }}
      />,
    )
    const empty = await findByText(/network failure/i)
    expect(empty).toBeTruthy()
  })
})
