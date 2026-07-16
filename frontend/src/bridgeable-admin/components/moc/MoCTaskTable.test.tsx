/**
 * MoC-2c — Tasks table (read) + MoC-2b — hybrid editing.
 *
 * Read coverage: rows + descriptive cells render; the orphan-tolerant
 * DELIBERATE empty state (em-dash, not blank) when a reference is absent;
 * populated deep-link pills when present; and the KEYSTONE — a focus pill's href
 * is byte-identical to the canonical mocDeepLink → adminPath the cards use.
 *
 * Edit coverage (2b): the Frequency quick-pick reads the vocabulary + PATCHes on
 * select; +Add-value POSTs then selects; a rejected PATCH surfaces the server's
 * reason AND reverts (the cell keeps the old value — no silent swallow); the row
 * delete affordance DELETEs; the Add-task button opens the panel.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, within, waitFor, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import { MoCTaskTable } from "./MoCTaskTable"
import type { MoCTask } from "@/bridgeable-admin/services/moc-service"
import * as mocService from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/bridgeable-admin/services/moc-service")>()
  return {
    ...actual,
    listVocabulary: vi.fn(),
    addVocabularyValue: vi.fn(),
    patchTask: vi.fn(),
    deleteTask: vi.fn(),
    createTask: vi.fn(),
    listWorkflowTemplateOptions: vi.fn(),
    listFocusTemplateOptions: vi.fn(),
    listTriggerEvents: vi.fn(),
    addTaskTrigger: vi.fn(),
    deleteTrigger: vi.fn(),
  }
})

function artifact(over: Partial<MoCTask["focuses"][number]> = {}) {
  return {
    exists: true,
    available: true,
    label: "Artifact",
    routing: {},
    artifact_id: "art-1",
    ...over,
  }
}

const POPULATED: MoCTask = {
  id: "t-pop",
  name: "Funeral Home Billing",
  icon: "receipt",
  frequency: "End of Month",
  task_type: "Accounting",
  description: "End of month billing.",
  display_order: 0,
  workflow: artifact({
    label: "Invoice and Statement Run",
    artifact_id: "wf-1",
    routing: { workflow_type: "invoice_statement", scope: "vertical_default" },
  }),
  focuses: [
    artifact({ label: "Decision Triage", artifact_id: "foc-1", routing: { template_slug: "decision-triage", scope: "vertical_default" } }),
    artifact({ label: "Legacy Generation", artifact_id: "foc-2", routing: { template_slug: "legacy-gen", scope: "vertical_default" } }),
  ],
}

const EMPTY: MoCTask = {
  id: "t-empty",
  name: "New Legacy Order",
  icon: "sparkles",
  frequency: "On demand",
  task_type: "Funeral Service Operations",
  description: "Creates a legacy proof.",
  display_order: 1,
  workflow: null, // absent reference (option-3 not seeded)
  focuses: [],
}

function renderTable(tasks: MoCTask[], onChanged: () => void = () => {}) {
  return render(
    <MemoryRouter>
      <MoCTaskTable
        tasks={tasks}
        vertical="manufacturing"
        onChanged={onChanged}
        data-testid="moc-task-table"
      />
    </MemoryRouter>,
  )
}

describe("MoCTaskTable — read", () => {
  it("renders a row per task with descriptive cells + the Type pill", () => {
    renderTable([POPULATED, EMPTY])
    expect(screen.getByTestId("moc-task-row-t-pop")).toBeTruthy()
    expect(screen.getByTestId("moc-task-row-t-empty")).toBeTruthy()
    expect(screen.getByText("End of Month")).toBeTruthy()
    // "Accounting" now also appears in the Set-1 group tab — assert the
    // row's Type pill specifically (>=2 = pill + tab both present).
    expect(screen.getAllByText("Accounting").length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText("Funeral Service Operations").length).toBeGreaterThanOrEqual(2)
  })

  it("renders the DELIBERATE empty state (em-dash) for absent workflow + focuses", () => {
    renderTable([EMPTY])
    const wf = screen.getByTestId("moc-task-workflow-t-empty")
    const foc = screen.getByTestId("moc-task-focuses-t-empty")
    // Not blank — a deliberate muted em-dash, and NOT a link.
    expect(wf.textContent).toBe("—")
    expect(foc.textContent).toBe("—")
    expect(within(wf).queryByRole("link")).toBeNull()
    expect(within(foc).queryByRole("link")).toBeNull()
  })

  it("renders populated workflow + focus pills as deep-links", () => {
    renderTable([POPULATED])
    const wf = within(screen.getByTestId("moc-task-workflow-t-pop")).getByRole("link")
    expect(wf.getAttribute("href")).toContain("workflow_type=invoice_statement")
    const foc = within(screen.getByTestId("moc-task-focuses-t-pop"))
    expect(foc.getByRole("link", { name: /Decision Triage/ })).toBeTruthy()
    expect(foc.getByRole("link", { name: /Legacy Generation/ })).toBeTruthy()
  })

  it("KEYSTONE: a focus pill's href is the canonical mocDeepLink (same as the cards)", () => {
    renderTable([POPULATED])
    const link = within(screen.getByTestId("moc-task-focuses-t-pop")).getByRole(
      "link",
      { name: /Decision Triage/ },
    )
    const expected = adminPath(
      mocDeepLink({
        builder: "focuses",
        artifact_id: "foc-1",
        routing: { template_slug: "decision-triage", scope: "vertical_default" },
      }) as string,
    )
    expect(link.getAttribute("href")).toBe(expected)
  })
})

describe("MoCTaskTable — edit (2b)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(mocService.listVocabulary).mockResolvedValue([
      { id: "v1", kind: "frequency", value: "End of Month", scope: "platform_default", vertical: null, display_order: 0, is_active: true },
      { id: "v2", kind: "frequency", value: "Weekly", scope: "platform_default", vertical: null, display_order: 1, is_active: true },
    ])
  })

  it("the Frequency quick-pick reads the vocabulary and PATCHes on select", async () => {
    vi.mocked(mocService.patchTask).mockResolvedValue({} as never)
    const onChanged = vi.fn()
    renderTable([POPULATED], onChanged)

    const cell = within(screen.getByTestId("moc-task-row-t-pop")).getByTestId("vocab-cell-frequency")
    fireEvent.click(cell)
    // Menu reads the vocabulary list.
    await waitFor(() => expect(screen.getByTestId("vocab-menu-frequency")).toBeTruthy())
    expect(mocService.listVocabulary).toHaveBeenCalledWith({ kind: "frequency", vertical: "manufacturing" })

    fireEvent.click(await screen.findByText("Weekly"))
    await waitFor(() =>
      expect(mocService.patchTask).toHaveBeenCalledWith("t-pop", { frequency: "Weekly" }),
    )
    expect(onChanged).toHaveBeenCalled()
  })

  it("+Add value POSTs the new value then selects it", async () => {
    vi.mocked(mocService.addVocabularyValue).mockResolvedValue(
      { id: "v9", kind: "frequency", value: "Quarterly", scope: "platform_default", vertical: null, display_order: 9, is_active: true },
    )
    vi.mocked(mocService.patchTask).mockResolvedValue({} as never)
    renderTable([POPULATED])

    fireEvent.click(within(screen.getByTestId("moc-task-row-t-pop")).getByTestId("vocab-cell-frequency"))
    fireEvent.click(await screen.findByTestId("vocab-add-frequency"))
    const input = screen.getByTestId("vocab-add-input-frequency")
    fireEvent.change(input, { target: { value: "Quarterly" } })
    fireEvent.keyDown(input, { key: "Enter" })

    await waitFor(() =>
      expect(mocService.addVocabularyValue).toHaveBeenCalledWith({ kind: "frequency", value: "Quarterly" }),
    )
    await waitFor(() =>
      expect(mocService.patchTask).toHaveBeenCalledWith("t-pop", { frequency: "Quarterly" }),
    )
  })

  it("a rejected PATCH surfaces the server's reason AND reverts the cell", async () => {
    vi.mocked(mocService.patchTask).mockRejectedValue({
      response: { data: { detail: "frequency 'Weekly' is not a valid value for manufacturing" } },
    })
    renderTable([POPULATED])

    fireEvent.click(within(screen.getByTestId("moc-task-row-t-pop")).getByTestId("vocab-cell-frequency"))
    fireEvent.click(await screen.findByText("Weekly"))

    // Error surfaces (not swallowed)…
    const err = await screen.findByTestId("moc-task-error")
    expect(err.textContent).toContain("not a valid value")
    // …and the cell reverts: still shows the original value (no refetch happened).
    expect(within(screen.getByTestId("moc-task-row-t-pop")).getByText("End of Month")).toBeTruthy()
  })

  it("the row delete affordance DELETEs after confirm", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    vi.mocked(mocService.deleteTask).mockResolvedValue(undefined)
    const onChanged = vi.fn()
    renderTable([POPULATED], onChanged)

    fireEvent.click(screen.getByTestId("moc-task-delete-t-pop"))
    await waitFor(() => expect(mocService.deleteTask).toHaveBeenCalledWith("t-pop"))
    expect(onChanged).toHaveBeenCalled()
  })

  it("the Add-task button opens the create panel", () => {
    vi.mocked(mocService.listWorkflowTemplateOptions).mockResolvedValue([])
    vi.mocked(mocService.listFocusTemplateOptions).mockResolvedValue([])
    vi.mocked(mocService.listTriggerEvents).mockResolvedValue([])
    renderTable([])
    // Panel closed → SlideOver returns null → its name input is absent.
    expect(screen.queryByTestId("task-panel-name")).toBeNull()
    fireEvent.click(screen.getByTestId("moc-task-add"))
    expect(screen.getByTestId("task-panel-name")).toBeTruthy()
  })
})

const ORDER_EVENT: mocService.MoCTriggerEvent = {
  id: "ev-1",
  event_key: "order.created",
  label: "Order created",
  entity: "sales_order",
  filterable_fields: [
    { field: "order_type", type: "enum", values: ["funeral", "retail", "wholesale"] },
    { field: "status", type: "string" },
  ],
}

describe("MoCTaskTable — triggers + derived frequency (T-1b)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(mocService.listWorkflowTemplateOptions).mockResolvedValue([])
    vi.mocked(mocService.listFocusTemplateOptions).mockResolvedValue([])
    vi.mocked(mocService.listTriggerEvents).mockResolvedValue([ORDER_EVENT])
  })

  it("renders trigger chips per kind, with the backend summary", () => {
    const withTriggers: MoCTask = {
      ...EMPTY,
      id: "t-trig",
      triggers: [
        { id: "tr1", kind: "schedule", config: {}, display_order: 0, summary: "Monthly · 1st" },
        { id: "tr2", kind: "event", config: {}, display_order: 1, summary: "order.created: funeral" },
        { id: "tr3", kind: "manual", config: {}, display_order: 2, summary: "Manual" },
      ],
    }
    renderTable([withTriggers])
    const cell = screen.getByTestId("moc-task-triggers-t-trig")
    expect(within(cell).getByTestId("trigger-chip-schedule")).toBeTruthy()
    expect(within(cell).getByTestId("trigger-chip-event")).toBeTruthy()
    expect(within(cell).getByTestId("trigger-chip-manual")).toBeTruthy()
    expect(cell.textContent).toContain("Monthly · 1st")
    expect(cell.textContent).toContain("order.created: funeral")
  })

  it("the triggers cell is a deliberate em-dash when a task has none", () => {
    renderTable([{ ...EMPTY, id: "t-none", triggers: [] }])
    expect(screen.getByTestId("moc-task-triggers-t-none").textContent).toBe("—")
  })

  it("shows the DERIVED frequency when a schedule-trigger exists (manual pick suppressed)", () => {
    const derived: MoCTask = { ...POPULATED, id: "t-deriv", derived_frequency: "End of Month · 6:00 PM" }
    renderTable([derived])
    const cell = screen.getByTestId("moc-task-frequency-t-deriv")
    expect(within(cell).getByTestId("moc-task-frequency-derived-t-deriv")).toBeTruthy()
    expect(cell.textContent).toContain("End of Month · 6:00 PM")
    // The manual quick-pick is NOT rendered in the derived case.
    expect(within(cell).queryByTestId("vocab-cell-frequency")).toBeNull()
  })

  it("keeps the manual frequency quick-pick when there is NO schedule-trigger (coexist)", () => {
    renderTable([{ ...POPULATED, id: "t-manual", derived_frequency: null }])
    const cell = screen.getByTestId("moc-task-frequency-t-manual")
    expect(within(cell).getByTestId("vocab-cell-frequency")).toBeTruthy()
    expect(within(cell).queryByTestId("moc-task-frequency-derived-t-manual")).toBeNull()
  })

  it("the panel's kind-switched form builds a STRUCTURED list-of-one event condition", async () => {
    vi.mocked(mocService.addTaskTrigger).mockResolvedValue(
      { id: "new", kind: "event", config: {}, display_order: 0, summary: "order.created: funeral" },
    )
    renderTable([POPULATED])
    // Open the panel (edit), open the trigger editor.
    fireEvent.click(screen.getByTestId("moc-task-edit-t-pop"))
    fireEvent.click(await screen.findByTestId("trigger-add-open"))
    // Pick EVENT kind → event → the condition builder reads filterable_fields.
    fireEvent.click(screen.getByTestId("trigger-kind-event"))
    fireEvent.change(await screen.findByTestId("event-select"), { target: { value: "order.created" } })
    fireEvent.change(await screen.findByTestId("condition-field"), { target: { value: "order_type" } })
    fireEvent.change(await screen.findByTestId("condition-value"), { target: { value: "funeral" } })
    fireEvent.click(screen.getByTestId("trigger-editor-add"))

    await waitFor(() => expect(mocService.addTaskTrigger).toHaveBeenCalled())
    const [, payload] = vi.mocked(mocService.addTaskTrigger).mock.calls[0]
    expect(payload.kind).toBe("event")
    const conditions = (payload.config as { conditions: unknown }).conditions
    expect(Array.isArray(conditions)).toBe(true) // a LIST, not a string
    expect(conditions).toEqual([{ field: "order_type", operator: "==", value: "funeral" }])
  })

  it("a rejected trigger write surfaces the validator's reason (no swallow)", async () => {
    vi.mocked(mocService.addTaskTrigger).mockRejectedValue({
      response: { data: { detail: "condition field 'bogus' is not exposed by event 'order.created'" } },
    })
    renderTable([POPULATED])
    fireEvent.click(screen.getByTestId("moc-task-edit-t-pop"))
    fireEvent.click(await screen.findByTestId("trigger-add-open"))
    fireEvent.click(screen.getByTestId("trigger-kind-manual")) // simplest valid kind to submit
    fireEvent.click(screen.getByTestId("trigger-editor-add"))
    const err = await screen.findByTestId("trigger-editor-error")
    expect(err.textContent).toContain("not exposed by event")
  })
})
