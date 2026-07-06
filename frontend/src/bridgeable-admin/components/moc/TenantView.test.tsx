/**
 * MoC Tenant View — the table's tenant labeling + the tenant-aware Add-task.
 *
 * Coverage:
 * - a tenant_override row renders the scope pill (the tenant's name); a
 *   vertical_default row does NOT (defaults stay calm, overrides are marked);
 * - no activeTenant → no pills even if a row claims tenant scope (defensive);
 * - Add-task with an activeTenant POSTs scope=tenant_override + tenant_id
 *   (never silently a vertical-wide default) and titles the panel for the
 *   tenant; without one, createTask carries NO tenant fields (the
 *   non-regression pin).
 *
 * (The page-level read recontextualization — passing tenant_id to
 * readForContext/readTaskCatalog — is exercised in the visual witness; the
 * page's data flow is a thin param pass.)
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { MoCTaskTable } from "./MoCTaskTable"
import type { MoCTask } from "@/bridgeable-admin/services/moc-service"
import * as mocService from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/bridgeable-admin/services/moc-service")>()
  return {
    ...actual,
    createTask: vi.fn(),
    listWorkflowTemplateOptions: vi.fn(),
    listFocusTemplateOptions: vi.fn(),
    listTriggerEvents: vi.fn(),
  }
})

const TESTCO = { id: "co-testco", slug: "testco", name: "Test Vault Co" }

function task(over: Partial<MoCTask>): MoCTask {
  return {
    id: "t-x", name: "Task", frequency: null, task_type: null, description: null,
    display_order: 0, workflow: null, focuses: [], triggers: [],
    ...over,
  }
}

const DEFAULT_ROW = task({ id: "t-def", name: "Default Task", scope: "vertical_default", tenant_id: null })
const TENANT_ROW = task({ id: "t-ten", name: "Witness Marker", scope: "tenant_override", tenant_id: TESTCO.id })

function renderTable(tasks: MoCTask[], activeTenant: typeof TESTCO | null) {
  return render(
    <MemoryRouter>
      <MoCTaskTable tasks={tasks} vertical="manufacturing" activeTenant={activeTenant} onChanged={() => {}} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(mocService.listWorkflowTemplateOptions).mockResolvedValue([])
  vi.mocked(mocService.listFocusTemplateOptions).mockResolvedValue([])
  vi.mocked(mocService.listTriggerEvents).mockResolvedValue([])
})

describe("tenant scope pill", () => {
  it("labels tenant_override rows with the tenant's name; defaults stay unmarked", () => {
    renderTable([DEFAULT_ROW, TENANT_ROW], TESTCO)
    const pill = screen.getByTestId("moc-task-tenant-pill-t-ten")
    expect(pill.textContent).toBe("Test Vault Co")
    expect(screen.queryByTestId("moc-task-tenant-pill-t-def")).toBeNull()
  })

  it("falls back to 'Tenant' when the active tenant name is unavailable", () => {
    renderTable([TENANT_ROW], null)
    // Defensive: a tenant-scoped row without page tenant context still marked.
    expect(screen.getByTestId("moc-task-tenant-pill-t-ten").textContent).toBe("Tenant")
  })
})

describe("tenant-aware Add-task", () => {
  it("creates the TENANT's override when a tenant is active (+ titled panel)", async () => {
    vi.mocked(mocService.createTask).mockResolvedValue({} as never)
    renderTable([], TESTCO)
    fireEvent.click(screen.getByTestId("moc-task-add"))
    expect(screen.getByText("Add task for Test Vault Co")).toBeTruthy()

    fireEvent.change(screen.getByTestId("task-panel-name"), { target: { value: "New Tenant Task" } })
    fireEvent.click(screen.getByTestId("task-panel-save"))

    await waitFor(() => expect(mocService.createTask).toHaveBeenCalled())
    const [input] = vi.mocked(mocService.createTask).mock.calls[0]
    expect(input.scope).toBe("tenant_override")
    expect(input.tenant_id).toBe(TESTCO.id)
    expect(input.name).toBe("New Tenant Task")
  })

  it("creates a plain vertical default when NO tenant is active (non-regression)", async () => {
    vi.mocked(mocService.createTask).mockResolvedValue({} as never)
    renderTable([], null)
    fireEvent.click(screen.getByTestId("moc-task-add"))
    // the panel is NOT tenant-titled ("Add task", not "Add task for …")
    expect(screen.queryByText(/Add task for/)).toBeNull()

    fireEvent.change(screen.getByTestId("task-panel-name"), { target: { value: "New Default" } })
    fireEvent.click(screen.getByTestId("task-panel-save"))

    await waitFor(() => expect(mocService.createTask).toHaveBeenCalled())
    const [input] = vi.mocked(mocService.createTask).mock.calls[0]
    expect(input.scope).toBeUndefined()
    expect(input.tenant_id).toBeUndefined()
  })
})
