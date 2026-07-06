/**
 * MoC Hierarchy H-1 — the tenant page (the route is the state).
 *
 * Coverage:
 * - the route's :tenantSlug resolves via the lookup, and BOTH reads receive
 *   the tenant_id (the recontextualization is route-driven, no picker);
 * - the merged table renders with activeTenant (the transferred machinery —
 *   its pills/coherence behavior is pinned in TenantView.test.tsx, unchanged);
 * - the fires card fetches company-scoped and renders provenance;
 * - the honest cards-source note for the fall-through case;
 * - the up-link points at the vertical map;
 * - an unknown slug → the missing state, no reads fired with a bogus tenant.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import MoCTenantPage from "./MoCTenantPage"
import * as mocService from "@/bridgeable-admin/services/moc-service"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"

vi.mock("@/bridgeable-admin/services/moc-service", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/bridgeable-admin/services/moc-service")>()
  return {
    ...actual,
    readForContext: vi.fn(),
    readTaskCatalog: vi.fn(),
    listMoCFires: vi.fn(),
    listVocabulary: vi.fn().mockResolvedValue([]),
    listWorkflowTemplateOptions: vi.fn().mockResolvedValue([]),
    listFocusTemplateOptions: vi.fn().mockResolvedValue([]),
    listTriggerEvents: vi.fn().mockResolvedValue([]),
  }
})
vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: { get: vi.fn() },
}))

const TESTCO = { id: "co-1", slug: "testco", name: "Test Vault Co", vertical: "manufacturing" }

const PAGE = {
  id: "p1", scope: "vertical_default" as const, vertical: "manufacturing",
  tenant_id: null, slug: "manufacturing-map", title: "Manufacturing",
  description: null, sections: [],
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/maps/:vertical/:tenantSlug" element={<MoCTenantPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(adminApi.get).mockResolvedValue({ data: [TESTCO] })
  vi.mocked(mocService.readForContext).mockResolvedValue(PAGE)
  vi.mocked(mocService.readTaskCatalog).mockResolvedValue([])
  vi.mocked(mocService.listMoCFires).mockResolvedValue([])
})

describe("MoCTenantPage — route-driven tenant context", () => {
  it("resolves the slug and passes tenant_id to BOTH reads + the fires fetch", async () => {
    renderAt("/maps/manufacturing/testco")
    await waitFor(() =>
      expect(mocService.readForContext).toHaveBeenCalledWith({
        vertical: "manufacturing", tenant_id: "co-1",
      }),
    )
    expect(mocService.readTaskCatalog).toHaveBeenCalledWith({
      vertical: "manufacturing", tenant_id: "co-1",
    })
    expect(mocService.listMoCFires).toHaveBeenCalledWith({ company_id: "co-1", limit: 10 })
    expect((await screen.findByTestId("moc-tenant-title")).textContent).toBe("Test Vault Co")
  })

  it("states the fall-through honestly when the tenant has no page of its own", async () => {
    renderAt("/maps/manufacturing/testco")
    const note = await screen.findByTestId("moc-tenant-cards-source")
    expect(note.textContent).toContain("no map page of its own yet")
  })

  it("states the replacement when the tenant HAS its own page", async () => {
    vi.mocked(mocService.readForContext).mockResolvedValue({
      ...PAGE, scope: "tenant_override", tenant_id: "co-1",
    })
    renderAt("/maps/manufacturing/testco")
    const note = await screen.findByTestId("moc-tenant-cards-source")
    expect(note.textContent).toContain("has its own map page")
  })

  it("renders the fires card with live/dry-run + event provenance", async () => {
    vi.mocked(mocService.listMoCFires).mockResolvedValue([
      { run_id: "r1", task_name: "Witness", moc_task_trigger_id: "t1", company_id: "co-1",
        status: "completed", is_dry_run: false, intended_fire: null,
        started_at: "2026-07-06T12:00:00Z", would_do: [], source: "event",
        event_key: "witness.marker_requested", event_id: "e1" },
      { run_id: "r2", task_name: "Witness", moc_task_trigger_id: "t1", company_id: "co-1",
        status: "completed", is_dry_run: true, intended_fire: null,
        started_at: "2026-07-06T11:00:00Z", would_do: [], source: "schedule",
        event_key: null, event_id: null },
    ])
    renderAt("/maps/manufacturing/testco")
    const card = await screen.findByTestId("moc-tenant-fires")
    expect(card.textContent).toContain("LIVE")
    expect(card.textContent).toContain("Dry-run")
    expect(card.textContent).toContain("event witness.marker_requested")
    expect(card.textContent).toContain("schedule")
  })

  it("the up-link points at the vertical map", async () => {
    renderAt("/maps/manufacturing/testco")
    const up = await screen.findByTestId("moc-tenant-up-link")
    expect(up.getAttribute("href")).toContain("/maps/manufacturing")
  })

  it("an unknown slug shows the missing state and fires NO tenant reads", async () => {
    vi.mocked(adminApi.get).mockResolvedValue({ data: [] })
    renderAt("/maps/manufacturing/ghost")
    await screen.findByTestId("moc-tenant-missing")
    expect(mocService.readForContext).not.toHaveBeenCalled()
    expect(mocService.readTaskCatalog).not.toHaveBeenCalled()
  })
})
