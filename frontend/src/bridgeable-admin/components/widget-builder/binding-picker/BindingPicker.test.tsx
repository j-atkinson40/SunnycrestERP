/**
 * BindingPicker tests — composed inspector control.
 *
 * Mocks the saved-views service so the hook returns deterministic
 * data. Covers the full operator-as-platform-builder authoring flow.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { BindingPicker } from "./BindingPicker"
import type { SavedView, EntityTypeMetadata } from "@/types/saved-views"

vi.mock("@/services/saved-views-service", () => ({
  listSavedViews: vi.fn(),
  listEntityTypes: vi.fn(),
  executeSavedView: vi.fn(),
}))


function mkView(id: string, title: string, mode: "list" | "chart" | "stat" = "list", entityType: "invoice" | "fh_case" = "invoice"): SavedView {
  return {
    id,
    company_id: "co1",
    title,
    description: null,
    created_by: null,
    created_at: "2026-05-21T00:00:00Z",
    updated_at: "2026-05-21T00:00:00Z",
    config: {
      query: { entity_type: entityType, filters: [], sort: [] },
      presentation: { mode },
      permissions: { owner_user_id: "u1", visibility: "private" },
    },
  } as SavedView
}


const ENTITY_TYPES: EntityTypeMetadata[] = [
  {
    entity_type: "invoice",
    display_name: "Invoice",
    icon: "file",
    navigate_url_template: "/i/{id}",
    available_fields: [
      { field_name: "total", display_name: "Total", field_type: "currency" },
      { field_name: "status", display_name: "Status", field_type: "enum" },
    ],
    default_sort: [],
    default_columns: [],
  },
]


async function mockServices(views: SavedView[]) {
  const svc = await import("@/services/saved-views-service")
  vi.mocked(svc.listSavedViews).mockResolvedValue(views)
  vi.mocked(svc.listEntityTypes).mockResolvedValue(ENTITY_TYPES)
  vi.mocked(svc.executeSavedView).mockResolvedValue({
    total_count: 0,
    rows: [],
    groups: null,
    aggregations: null,
    permission_mode: "full",
    masked_fields: [],
  })
}


describe("BindingPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders loading state initially", async () => {
    await mockServices([])
    render(
      <BindingPicker
        atomType="value_display"
        bindingRef={null}
        onChange={() => {}}
        bindingId="b1"
      />,
    )
    expect(screen.getByTestId("binding-picker-loading")).toBeInTheDocument()
  })

  it("renders saved-view + field-path + iteration-mode pickers after load", async () => {
    await mockServices([mkView("v1", "Outstanding invoices")])
    render(
      <BindingPicker
        atomType="value_display"
        bindingRef={null}
        onChange={() => {}}
        bindingId="b1"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("binding-picker")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("binding-picker-saved-view")).toBeInTheDocument()
    expect(screen.getByTestId("binding-picker-field-path")).toBeInTheDocument()
    expect(
      screen.getByTestId("binding-picker-iteration-mode"),
    ).toBeInTheDocument()
  })

  it("calls onChange when saved view selected (sets binding_type='field_path')", async () => {
    await mockServices([mkView("v1", "Outstanding invoices")])
    const onChange = vi.fn()
    render(
      <BindingPicker
        atomType="value_display"
        bindingRef={null}
        onChange={onChange}
        bindingId="b-test"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("binding-picker")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("binding-picker-saved-view"))
    fireEvent.click(screen.getByTestId("binding-picker-saved-view-option-v1"))
    expect(onChange).toHaveBeenCalledTimes(1)
    const next = onChange.mock.calls[0][0]
    expect(next.binding_id).toBe("b-test")
    expect(next.binding_type).toBe("field_path")
    expect(next.saved_view_id).toBe("v1")
    expect(next.iteration_mode).toBe("single_record") // list view + value_display
  })

  it("locks iteration_mode to per_row for repeater_atom (shape-filtered picker)", async () => {
    await mockServices([
      mkView("v1", "List view", "list"),
      mkView("v2", "Chart view", "chart"),
    ])
    render(
      <BindingPicker
        atomType="repeater_atom"
        bindingRef={null}
        onChange={() => {}}
        bindingId="b-rep"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("binding-picker")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("binding-picker-saved-view"))
    // List view available; chart view filtered out by shape. The dropdown
    // options render on a later async tick than the open click, so assert
    // via waitFor (a bare synchronous getByTestId here is a latent race
    // that full-suite worker load can lose — same anti-pattern as the
    // Tier2TemplatesEditor.test:602 fix).
    //
    // ⚠️ THAT FIX WAS THE RIGHT SHAPE AND THE WRONG MAGNITUDE. The waitFor
    // above was added and still timed out: CI run 37125242228 failed here with
    //
    //   TestingLibraryElementError: Unable to find an element by:
    //     [data-testid="binding-picker-saved-view-option-v1"]
    //
    // and a DOM dump showing the trigger still closed (aria-expanded="false").
    // waitFor's DEFAULT window is 1000 ms; CI measured this test at 1062 ms,
    // and CI runs the suite ~6x slower than a dev machine (276.8 s against
    // ~44 s). The popover's open did not finish inside the default window.
    //
    // ⚠️ THIS IS AN EXPERIMENT, NOT A FIX DECLARED DONE. The failure rate is
    // 2 in 8 pushes, so ONE green CI run is the most likely outcome whether or
    // not this worked. It is evidenced only by several consecutive clean
    // pushes. If it fails again unchanged, the hypothesis was wrong and the
    // live suspect becomes the click never processing at all —
    // aria-expanded="false" is consistent with both, and only the first is
    // helped by more time.
    //
    // ⚠️ AND IT CANNOT BE REPRODUCED LOCALLY, WHICH IS THE EXPECTED RESULT AND
    // NOT A REASON TO DOUBT IT. Five full local suite runs were green; this
    // machine is never slow enough to close the window. A failure mode that
    // cannot manifest locally reads exactly like a flake that will not
    // reproduce, and the two call for opposite responses.
    await waitFor(
      () =>
        expect(
          screen.getByTestId("binding-picker-saved-view-option-v1"),
        ).toBeInTheDocument(),
      { timeout: 5_000 },
    )
    expect(
      screen.queryByTestId("binding-picker-saved-view-option-v2"),
    ).toBeNull()
  })

  it("displays auto-inferred iteration_mode read-only for repeater_atom", async () => {
    await mockServices([mkView("v1", "List view", "list")])
    render(
      <BindingPicker
        atomType="repeater_atom"
        bindingRef={{
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "v1",
          field_path: "id",
          iteration_mode: "per_row",
        }}
        onChange={() => {}}
        bindingId="b1"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("binding-picker")).toBeInTheDocument(),
    )
    const itm = screen.getByTestId("binding-picker-iteration-mode")
    expect(itm).toHaveTextContent("per row")
    expect(itm).toHaveTextContent("auto")
  })

  it("preserves field_path when switching between views of the same entity type", async () => {
    await mockServices([
      mkView("v1", "Invoices A", "list", "invoice"),
      mkView("v2", "Invoices B", "list", "invoice"),
    ])
    const onChange = vi.fn()
    render(
      <BindingPicker
        atomType="value_display"
        bindingRef={{
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "v1",
          field_path: "total",
          iteration_mode: "single_record",
        }}
        onChange={onChange}
        bindingId="b1"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTestId("binding-picker")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("binding-picker-saved-view"))
    fireEvent.click(screen.getByTestId("binding-picker-saved-view-option-v2"))
    expect(onChange).toHaveBeenCalledTimes(1)
    const next = onChange.mock.calls[0][0]
    expect(next.field_path).toBe("total") // preserved
  })
})
