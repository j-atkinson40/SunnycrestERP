/**
 * registerComposedWidgets — WB-3 visual-editor metadata registry bridge tests.
 *
 * Closes WB-2 Surprise 3: composed widgets discoverable in Focus Builder
 * palette + placeable via PlacedWidgetCore's getByName lookup.
 */

import { describe, it, expect, beforeEach, vi } from "vitest"
import { render } from "@testing-library/react"

import { getByName, getByType } from "@/lib/visual-editor/registry"

import {
  _resetForTests,
  registerComposedWidgetMeta,
  registerComposedWidgetsFromApi,
  type ComposedWidgetDefinitionDTO,
} from "./registerComposedWidgets"

// Mock apiClient before importing tests.
vi.mock("@/lib/api-client", () => ({
  default: {
    get: vi.fn(),
  },
}))


function _mkDto(
  overrides: Partial<ComposedWidgetDefinitionDTO> = {},
): ComposedWidgetDefinitionDTO {
  return {
    widget_id: "composed.test-cases",
    title: "Open cases",
    description: "Composed widget that lists open cases",
    icon: null,
    category: "information",
    composition_blob: {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "text_label",
          config: {},
        },
      },
      variants: [],
      bindings_catalog: {},
    },
    composition_version: 1,
    tier_scope: "platform",
    supported_surfaces: ["focus_canvas"],
    default_size: "2x2",
    supported_sizes: ["2x2"],
    ...overrides,
  }
}


describe("registerComposedWidgetMeta — direct registration", () => {
  beforeEach(() => {
    _resetForTests()
  })

  it("registers a composed widget in the visual-editor registry", () => {
    const dto = _mkDto({ widget_id: "composed.direct-1" })
    registerComposedWidgetMeta(dto)
    const entry = getByName("widget", "composed.direct-1")
    expect(entry).not.toBeUndefined()
    expect(entry?.metadata.displayName).toBe("Open cases")
    expect(entry?.metadata.category).toBe("information")
  })

  it("stores composition metadata in extensions for forward-compat introspection", () => {
    const dto = _mkDto({
      widget_id: "composed.direct-2",
      composition_version: 3,
      tier_scope: "vertical",
    })
    registerComposedWidgetMeta(dto)
    const entry = getByName("widget", "composed.direct-2")
    expect(entry?.metadata.extensions?.composition_version).toBe(3)
    expect(entry?.metadata.extensions?.tier_scope).toBe("vertical")
    expect(entry?.metadata.extensions?.composed).toBe(true)
  })

  it("getByType('widget') surfaces composed widgets", () => {
    registerComposedWidgetMeta(
      _mkDto({ widget_id: "composed.appears-in-palette" }),
    )
    const all = getByType("widget").map((e) => e.metadata.name)
    expect(all).toContain("composed.appears-in-palette")
  })

  it("registered component renders ComposedWidget when called", () => {
    registerComposedWidgetMeta(
      _mkDto({ widget_id: "composed.render-check" }),
    )
    const entry = getByName("widget", "composed.render-check")
    expect(entry).not.toBeUndefined()
    const Component = entry!.component as React.ComponentType<unknown>
    const { container } = render(<Component />)
    expect(container.querySelector("[data-composed-widget-root]")).not.toBeNull()
  })
})


describe("registerComposedWidgetsFromApi — boot adapter", () => {
  beforeEach(async () => {
    _resetForTests()
    const apiClient = (await import("@/lib/api-client")).default
    ;(apiClient.get as unknown as ReturnType<typeof vi.fn>).mockReset()
  })

  it("fetches definitions + registers each", async () => {
    const apiClient = (await import("@/lib/api-client")).default
    ;(apiClient.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        _mkDto({ widget_id: "composed.boot-1" }),
        _mkDto({ widget_id: "composed.boot-2", title: "Two" }),
      ],
    })
    const count = await registerComposedWidgetsFromApi()
    expect(count).toBe(2)
    expect(getByName("widget", "composed.boot-1")).not.toBeUndefined()
    expect(getByName("widget", "composed.boot-2")?.metadata.displayName).toBe(
      "Two",
    )
  })

  it("logs warning + returns 0 on fetch failure (graceful degradation)", async () => {
    const apiClient = (await import("@/lib/api-client")).default
    ;(apiClient.get as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network down"),
    )
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {})
    const count = await registerComposedWidgetsFromApi()
    expect(count).toBe(0)
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it("is idempotent (second call is a no-op)", async () => {
    const apiClient = (await import("@/lib/api-client")).default
    const getMock = apiClient.get as unknown as ReturnType<typeof vi.fn>
    getMock.mockResolvedValue({ data: [_mkDto({ widget_id: "composed.idem" })] })
    await registerComposedWidgetsFromApi()
    await registerComposedWidgetsFromApi()
    expect(getMock).toHaveBeenCalledTimes(1)
  })
})
