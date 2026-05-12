/**
 * runtime-writers — dashboard_layout writer tests (Arc 1).
 *
 * Arc 1 lifts dashboard_layout from a `throw` stub to a real writer
 * that POSTs through `dashboardLayoutsService`. These tests cover
 * the write path: vertical-default scope, page_context resolution,
 * update-existing vs create-new branching, and error guards.
 *
 * The pre-existing token / component_prop / component_class writers
 * have their behavior covered by edit-mode-context.test.tsx's
 * `commitDraft routing` suite via injected `writers` props. This
 * file focuses on dashboard_layout-specific paths because Arc 1
 * adds substantive new logic there.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"

import { dashboardLayoutsService } from "@/bridgeable-admin/services/dashboard-layouts-service"

import { makeDashboardLayoutWriter } from "./runtime-writers"
import type { RuntimeOverride } from "./edit-mode-context"


vi.mock("@/bridgeable-admin/services/dashboard-layouts-service", () => ({
  dashboardLayoutsService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}))


const layoutFixture = [
  {
    widget_id: "today",
    enabled: true,
    position: 1,
    size: "md",
  },
  {
    widget_id: "anomalies",
    enabled: true,
    position: 2,
    size: "lg",
  },
]


function makeOverride(partial: Partial<RuntimeOverride> = {}): RuntimeOverride {
  return {
    type: "dashboard_layout",
    target: "home",
    prop: "layout_config",
    value: layoutFixture,
    ...partial,
  }
}


function makeCtx(overrides: { vertical?: string | null } = {}) {
  // Honor explicit null in overrides (don't fold null into the fallback).
  const vertical =
    "vertical" in overrides ? overrides.vertical ?? null : "manufacturing"
  return {
    vertical,
    tenantId: "tenant-test",
    impersonatedUserId: "user-impersonated",
    themeMode: "light" as const,
  }
}


describe("makeDashboardLayoutWriter", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("creates a new layout row when no active row exists", async () => {
    vi.mocked(dashboardLayoutsService.list).mockResolvedValue([])
    vi.mocked(dashboardLayoutsService.create).mockResolvedValue({
      id: "new-layout-id",
      scope: "vertical_default",
      vertical: "manufacturing",
      tenant_id: null,
      page_context: "home",
      layout_config: layoutFixture,
      version: 1,
      is_active: true,
      created_at: "2026-05-12T00:00:00Z",
      updated_at: "2026-05-12T00:00:00Z",
    })

    const writer = makeDashboardLayoutWriter(makeCtx())
    await writer(
      {} as never,
      makeOverride(),
    )

    expect(dashboardLayoutsService.list).toHaveBeenCalledWith({
      scope: "vertical_default",
      vertical: "manufacturing",
      page_context: "home",
    })
    expect(dashboardLayoutsService.create).toHaveBeenCalledWith({
      scope: "vertical_default",
      vertical: "manufacturing",
      page_context: "home",
      layout_config: layoutFixture,
    })
    expect(dashboardLayoutsService.update).not.toHaveBeenCalled()
  })

  it("updates the active layout row when one exists", async () => {
    vi.mocked(dashboardLayoutsService.list).mockResolvedValue([
      {
        id: "existing-layout-id",
        scope: "vertical_default",
        vertical: "manufacturing",
        tenant_id: null,
        page_context: "home",
        layout_config: [],
        version: 2,
        is_active: true,
        created_at: "2026-05-01T00:00:00Z",
        updated_at: "2026-05-08T00:00:00Z",
      },
    ])
    vi.mocked(dashboardLayoutsService.update).mockResolvedValue({
      id: "existing-layout-id",
      scope: "vertical_default",
      vertical: "manufacturing",
      tenant_id: null,
      page_context: "home",
      layout_config: layoutFixture,
      version: 3,
      is_active: true,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-12T00:00:00Z",
    })

    const writer = makeDashboardLayoutWriter(makeCtx())
    await writer(
      {} as never,
      makeOverride(),
    )

    expect(dashboardLayoutsService.update).toHaveBeenCalledWith(
      "existing-layout-id",
      { layout_config: layoutFixture },
    )
    expect(dashboardLayoutsService.create).not.toHaveBeenCalled()
  })

  it("creates new when only inactive rows exist (latest-active-wins)", async () => {
    // Defensive: list returns history with no active row (rare; can
    // happen mid-deploy or after manual deactivation).
    vi.mocked(dashboardLayoutsService.list).mockResolvedValue([
      {
        id: "inactive-old-id",
        scope: "vertical_default",
        vertical: "manufacturing",
        tenant_id: null,
        page_context: "home",
        layout_config: [],
        version: 1,
        is_active: false,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ])

    const writer = makeDashboardLayoutWriter(makeCtx())
    await writer(
      {} as never,
      makeOverride(),
    )

    expect(dashboardLayoutsService.create).toHaveBeenCalled()
    expect(dashboardLayoutsService.update).not.toHaveBeenCalled()
  })

  it("throws when vertical is missing", async () => {
    const writer = makeDashboardLayoutWriter(makeCtx({ vertical: null }))
    await expect(
      writer(
        {} as never,
        makeOverride(),
      ),
    ).rejects.toThrow(/vertical missing/)
  })

  it("throws when prop is not 'layout_config'", async () => {
    const writer = makeDashboardLayoutWriter(makeCtx())
    await expect(
      writer(
        {} as never,
        makeOverride({ prop: "unsupported_prop" }),
      ),
    ).rejects.toThrow(/only 'layout_config' prop supported/)
  })

  it("throws when target (page_context) is empty", async () => {
    const writer = makeDashboardLayoutWriter(makeCtx())
    await expect(
      writer(
        {} as never,
        makeOverride({ target: "" }),
      ),
    ).rejects.toThrow(/target \(page_context\) missing/)
  })

  it("forwards page_context filter to the list call (per-context lookup)", async () => {
    vi.mocked(dashboardLayoutsService.list).mockResolvedValue([])
    const writer = makeDashboardLayoutWriter(makeCtx())
    await writer(
      {} as never,
      makeOverride({ target: "ops_board" }),
    )

    expect(dashboardLayoutsService.list).toHaveBeenCalledWith({
      scope: "vertical_default",
      vertical: "manufacturing",
      page_context: "ops_board",
    })
    expect(dashboardLayoutsService.create).toHaveBeenCalledWith(
      expect.objectContaining({ page_context: "ops_board" }),
    )
  })
})
