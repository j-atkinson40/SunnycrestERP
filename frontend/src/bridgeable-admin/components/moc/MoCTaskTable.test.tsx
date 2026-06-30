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
    expect(screen.getByText("Accounting")).toBeTruthy()
    expect(screen.getByText("Funeral Service Operations")).toBeTruthy()
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
    renderTable([])
    // Panel closed → SlideOver returns null → its name input is absent.
    expect(screen.queryByTestId("task-panel-name")).toBeNull()
    fireEvent.click(screen.getByTestId("moc-task-add"))
    expect(screen.getByTestId("task-panel-name")).toBeTruthy()
  })
})
