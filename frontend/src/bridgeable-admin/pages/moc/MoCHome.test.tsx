/**
 * MoCHome — THE PLATFORM MoC (H-2; was the Phase 1.2 select-a-vertical pane).
 *
 * Re-homed pins: the two-pane structure + the §18 surface island TRANSFER
 * (unchanged claims); the "select a vertical" prompt pin RETIRED with the
 * empty pane (the platform map fills it). New pins: the login landing renders
 * the platform map — verticals as cards (live → linked, unbuilt → deliberate
 * coming-room), and the FIRST-RENDER DISCIPLINE's deliberate-room copy (the
 * platform task table's "lives here" text, the fires card's "lands here"
 * text, the not-authored state) — room, never a no-data shrug.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import MoCHome from "./MoCHome"
import * as mocService from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/bridgeable-admin/services/moc-service")>()
  return {
    ...actual,
    listPages: vi.fn().mockResolvedValue([]),
    readForContext: vi.fn(),
    readTaskCatalog: vi.fn(),
    listMoCFires: vi.fn(),
    createTask: vi.fn(),
    listVocabulary: vi.fn().mockResolvedValue([]),
    listWorkflowTemplateOptions: vi.fn().mockResolvedValue([]),
    listFocusTemplateOptions: vi.fn().mockResolvedValue([]),
    listTriggerEvents: vi.fn().mockResolvedValue([]),
  }
})
vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: { get: vi.fn() },
}))

import { adminApi } from "@/bridgeable-admin/lib/admin-api"

const PLATFORM_PAGE = {
  id: "pp1", scope: "platform_default" as const, vertical: null, tenant_id: null,
  slug: "platform-map", title: "Bridgeable",
  description: "The platform, whole.", sections: [],
}

beforeEach(() => {
  vi.mocked(mocService.readForContext).mockResolvedValue(PLATFORM_PAGE)
  vi.mocked(mocService.readTaskCatalog).mockResolvedValue([])
  vi.mocked(mocService.listMoCFires).mockResolvedValue([])
  vi.mocked(adminApi.get).mockImplementation((url: string) => {
    if (url.includes("/moc/")) {
      // the seeded-verticals list — manufacturing has a map, the others don't
      return Promise.resolve({ data: [{ vertical: "manufacturing" }] })
    }
    return Promise.resolve({ data: { items: [], total: 7 } })
  })
})
afterEach(() => vi.clearAllMocks())

function renderHome() {
  return render(
    <MemoryRouter>
      <MoCHome />
    </MemoryRouter>,
  )
}

describe("MoCHome — the platform MoC (H-2)", () => {
  it("renders the two-pane: the Verticals rail beside the content area", async () => {
    renderHome()
    expect(await screen.findByTestId("moc-verticals-rail")).toBeInTheDocument()
    expect(screen.getByTestId("moc-home-content")).toBeInTheDocument()
  })

  it("applies the §18 surface (contrast fix) on the home root", () => {
    renderHome()
    expect(screen.getByTestId("moc-home").className).toContain("bg-surface-base")
  })

  it("the landing IS the platform map: title + reads at platform scope", async () => {
    renderHome()
    expect((await screen.findByTestId("moc-platform-title")).textContent).toBe("Bridgeable")
    expect(mocService.readForContext).toHaveBeenCalledWith({})
    expect(mocService.readTaskCatalog).toHaveBeenCalledWith({ scope: "platform_default" })
  })

  it("verticals as cards: live links down, unbuilt reads as deliberate coming-room", async () => {
    renderHome()
    // waitFor: the card renders as coming-room until the seeded-slugs fetch
    // resolves and flips manufacturing to a link.
    await waitFor(() =>
      expect(
        screen.getByTestId("moc-platform-vertical-manufacturing").getAttribute("href"),
      ).toContain("/maps/manufacturing"),
    )
    const fh = screen.getByTestId("moc-platform-vertical-funeral_home")
    expect(fh.getAttribute("href")).toBeNull()               // not a broken link
    expect(fh.textContent).toContain("Map coming")           // deliberate room
  })

  it("FIRST-RENDER DISCIPLINE: empty states are deliberate room, never a shrug", async () => {
    renderHome()
    // the platform task table's room
    const room = await screen.findByTestId("moc-platform-tasks-room")
    expect(room.textContent).toContain("Platform-wide tasks live here")
    // the fires card's room
    const fires = screen.getByTestId("moc-platform-fires")
    expect(fires.textContent).toContain("Platform activity lands here")
  })

  it("the not-authored state is deliberate (names the seed), not an error", async () => {
    vi.mocked(mocService.readForContext).mockRejectedValue({ response: { status: 404 } })
    renderHome()
    const note = await screen.findByTestId("moc-platform-not-authored")
    expect(note.textContent).toContain("seed_moc_platform")
    // and no error banner anywhere on the landing
    expect(screen.queryByText(/couldn't load/i)).toBeNull()
  })

  it("Add-task from the platform page authors platform scope (the coherence guard)", async () => {
    vi.mocked(mocService.createTask).mockResolvedValue({} as never)
    renderHome()
    const addBtn = await screen.findByTestId("moc-task-add")
    addBtn.click()
    expect(await screen.findByText("Add platform task")).toBeInTheDocument()
  })
})
