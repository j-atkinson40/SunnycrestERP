/**
 * PulseSurface empty slot filter + console.warn discipline —
 * Phase W-4a Step 6 Commit 4.
 *
 * Per DESIGN_LANGUAGE.md §13.4.3 agency-dictated error surface canon:
 * Pulse is platform-composed; widget pieces whose renderer resolves
 * to a fallback (MissingWidgetEmptyState / MockSavedViewWidget) are
 * silently filtered + emit a debounced console.warn for observability.
 *
 * Test classes per the Commit 4 spec:
 *   • TestEmptySlotFilter — filter behavior at PulseLayer rendering
 *     site + at PulseSurface measurement walk (consistent semantics
 *     across both consumers via shared `isItemRenderable` predicate)
 *   • TestConsoleWarnDiscipline — canonical warn message + per-key
 *     debounce semantics
 *   • TestRenderabilityHelper — `isItemRenderable` per-kind contract
 *
 * jsdom limitations: actual DOM mounting of PulseLayer requires
 * mocking the widget renderer registry. Tests use a synthesized
 * widget renderer registry via the test-only `_resetWidgetRenderer-
 * RegistryForTests` + `registerWidgetRenderer` exports.
 */

import { render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { computeLayerRowCount } from "@/components/spaces/utils/layer-row-count"
import { isItemRenderable } from "@/components/spaces/utils/renderability"
import {
  _resetWidgetRendererRegistryForTests,
  getWidgetRenderer,
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"
import { MissingWidgetEmptyState } from "@/components/focus/canvas/MissingWidgetEmptyState"
import { MockSavedViewWidget } from "@/components/focus/canvas/MockSavedViewWidget"
import {
  _resetPulseLayerWarnDebounceForTests,
  PulseLayer,
} from "@/components/spaces/PulseLayer"
import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  TimeOfDaySignal,
} from "@/types/pulse"


// ── Fixtures ────────────────────────────────────────────────────────


function makeWidgetItem(
  overrides: Partial<LayerItem> = {},
): LayerItem {
  return {
    item_id: "widget:test",
    kind: "widget",
    component_key: "test_widget",
    variant_id: "brief",
    cols: 2,
    rows: 1,
    priority: 50,
    payload: {},
    dismissed: false,
    ...overrides,
  }
}


function makeStreamItem(
  overrides: Partial<LayerItem> = {},
): LayerItem {
  return {
    item_id: "stream:test",
    kind: "stream",
    component_key: "test_stream",
    variant_id: "brief",
    cols: 6,
    rows: 2,
    priority: 95,
    payload: {},
    ...overrides,
  }
}


function MockWidgetRenderer(
  props: WidgetRendererProps,
): React.ReactElement {
  return (
    <div
      data-testid="mock-real-widget"
      data-widget-id={props.widgetId}
    >
      mock {props.widgetId}
    </div>
  )
}


// ── Setup ───────────────────────────────────────────────────────────


let warnSpy: ReturnType<typeof vi.spyOn>


beforeEach(() => {
  _resetWidgetRendererRegistryForTests()
  _resetPulseLayerWarnDebounceForTests()
  warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {})
})


afterEach(() => {
  warnSpy.mockRestore()
})


// ── TestRenderabilityHelper ──────────────────────────────────────────


describe("TestRenderabilityHelper", () => {
  it("stream pieces are always renderable (separate dispatch path)", () => {
    const stream = makeStreamItem({ component_key: "any_stream_key" })
    expect(isItemRenderable(stream)).toBe(true)
  })

  it("widget pieces with registered renderers are renderable", () => {
    registerWidgetRenderer("registered_widget", MockWidgetRenderer)
    const item = makeWidgetItem({ component_key: "registered_widget" })
    expect(isItemRenderable(item)).toBe(true)
  })

  it("widget pieces with no registration resolve to MissingWidgetEmptyState (not renderable)", () => {
    const item = makeWidgetItem({ component_key: "never_registered" })
    expect(getWidgetRenderer("never_registered")).toBe(
      MissingWidgetEmptyState,
    )
    expect(isItemRenderable(item)).toBe(false)
  })

  it("widget pieces with undefined component_key resolve to MockSavedViewWidget (not renderable)", () => {
    const item = makeWidgetItem({
      component_key: undefined as unknown as string,
    })
    // Defensive — undefined component_key path returns MockSavedViewWidget.
    expect(getWidgetRenderer(undefined)).toBe(MockSavedViewWidget)
    expect(isItemRenderable(item)).toBe(false)
  })
})


// ── TestEmptySlotFilter ──────────────────────────────────────────────


describe("TestEmptySlotFilter — measurement walk", () => {
  it("computeLayerRowCount counts only renderable items when predicate provided", () => {
    registerWidgetRenderer("registered_widget", MockWidgetRenderer)
    const items: LayerItem[] = [
      makeWidgetItem({
        item_id: "1",
        component_key: "registered_widget",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "2",
        component_key: "unregistered_widget",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "3",
        component_key: "registered_widget",
        cols: 2,
        rows: 1,
      }),
    ]
    // Without predicate: counts all 3 → 1 row at 6 cols (3 × 2-col fits)
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(1)
    // With predicate: counts 2 (the two registered) → still 1 row
    expect(computeLayerRowCount(items, new Set(), 6, isItemRenderable)).toBe(
      1,
    )
  })

  it("filters all items when none registered → 0 rows", () => {
    const items: LayerItem[] = [
      makeWidgetItem({
        item_id: "1",
        component_key: "unregistered_a",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "2",
        component_key: "unregistered_b",
        cols: 2,
        rows: 1,
      }),
    ]
    expect(computeLayerRowCount(items, new Set(), 6, isItemRenderable)).toBe(
      0,
    )
  })

  it("dismissed AND unrenderable filters compose", () => {
    registerWidgetRenderer("registered_widget", MockWidgetRenderer)
    const items: LayerItem[] = [
      makeWidgetItem({
        item_id: "keep",
        component_key: "registered_widget",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "dismissed",
        component_key: "registered_widget",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "unrenderable",
        component_key: "unregistered_widget",
        cols: 2,
        rows: 1,
      }),
    ]
    expect(
      computeLayerRowCount(
        items,
        new Set(["dismissed"]),
        6,
        isItemRenderable,
      ),
    ).toBe(1) // only "keep" survives both filters
  })

  it("stream items are never filtered (always renderable per renderability helper)", () => {
    const items: LayerItem[] = [
      makeStreamItem({ item_id: "s1", cols: 6, rows: 2 }),
      makeWidgetItem({
        item_id: "w1",
        component_key: "unregistered",
        cols: 2,
        rows: 1,
      }),
    ]
    // Stream takes full row 0+1; widget filtered → 2 rows total
    expect(computeLayerRowCount(items, new Set(), 6, isItemRenderable)).toBe(
      2,
    )
  })

  it("backward-compat: predicate omitted → no filter applied (Commit 2 contract)", () => {
    const items: LayerItem[] = [
      makeWidgetItem({
        item_id: "1",
        component_key: "unregistered",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "2",
        component_key: "also_unregistered",
        cols: 2,
        rows: 1,
      }),
    ]
    // Without predicate, all items count regardless of renderer.
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(1)
  })
})


// ── TestEmptySlotFilter — PulseLayer rendering ───────────────────────


describe("TestEmptySlotFilter — PulseLayer rendering", () => {
  function renderLayer(items: LayerItem[]): ReturnType<typeof render> {
    const layer: LayerContent = {
      layer: "personal",
      items,
      advisory: null,
    }
    const intelligenceStreams: IntelligenceStream[] = []
    const timeOfDay: TimeOfDaySignal = "morning"
    return render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={intelligenceStreams}
          timeOfDay={timeOfDay}
          workAreas={["Production Scheduling"]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
  }

  it("PulseLayer DOES NOT render unrenderable widgets (silent filter per §13.4.3)", () => {
    registerWidgetRenderer("real_widget", MockWidgetRenderer)
    const { container } = renderLayer([
      makeWidgetItem({
        item_id: "real",
        component_key: "real_widget",
      }),
      makeWidgetItem({
        item_id: "fake",
        component_key: "unregistered_key",
      }),
    ])
    const realPiece = container.querySelector(
      '[data-component-key="real_widget"]',
    )
    const fakePiece = container.querySelector(
      '[data-component-key="unregistered_key"]',
    )
    expect(realPiece).not.toBeNull()
    // Per §13.4.3 platform-composed surface canon, unrenderable
    // pieces are silently filtered. The DOM should NOT contain the
    // unregistered piece.
    expect(fakePiece).toBeNull()
  })

  it("PulseLayer NEVER renders MissingWidgetEmptyState in Pulse (it's the user-composed-surface fallback)", () => {
    const { container } = renderLayer([
      makeWidgetItem({
        item_id: "fake",
        component_key: "unregistered_key",
      }),
    ])
    // §13.4.3: MissingWidgetEmptyState is reserved for user-composed
    // surfaces (PinnedSection, Custom Spaces). Pulse silently filters
    // instead. The component key shouldn't appear anywhere in the
    // rendered output.
    expect(container.textContent).not.toContain("Widget unavailable")
    expect(container.textContent).not.toContain("No renderer registered")
  })

  it("layer becomes empty after filter → renders advisory if present", () => {
    const layer: LayerContent = {
      layer: "anomaly",
      items: [
        makeWidgetItem({
          item_id: "fake",
          component_key: "unregistered",
        }),
      ],
      advisory: "All clear",
    }
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay={"morning" as TimeOfDaySignal}
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    // Filter dropped all items → empty layer with advisory
    const emptySection = container.querySelector(
      '[data-slot="pulse-layer"][data-empty="true"]',
    )
    expect(emptySection).not.toBeNull()
    expect(container.textContent).toContain("All clear")
  })

  it("layer becomes empty after filter + no advisory → renders nothing", () => {
    const layer: LayerContent = {
      layer: "personal",
      items: [
        makeWidgetItem({
          item_id: "fake",
          component_key: "unregistered",
        }),
      ],
      advisory: null,
    }
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay={"morning" as TimeOfDaySignal}
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    // Empty layer + no advisory → suppressed entirely
    expect(container.querySelector('[data-slot="pulse-layer"]')).toBeNull()
  })

  it("data-row-count attribute reflects filtered count (not raw count)", () => {
    registerWidgetRenderer("real", MockWidgetRenderer)
    const { container } = renderLayer([
      makeWidgetItem({
        item_id: "1",
        component_key: "real",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "2",
        component_key: "unregistered",
        cols: 2,
        rows: 1,
      }),
      makeWidgetItem({
        item_id: "3",
        component_key: "real",
        cols: 2,
        rows: 1,
      }),
    ])
    const section = container.querySelector(
      '[data-slot="pulse-layer"]',
    ) as HTMLElement | null
    expect(section).not.toBeNull()
    // 2 renderable widgets at 2-col each → 1 row at 6 cols
    expect(section!.getAttribute("data-row-count")).toBe("1")
  })
})


// ── TestConsoleWarnDiscipline ────────────────────────────────────────


describe("TestConsoleWarnDiscipline", () => {
  function renderLayer(
    layerName: LayerContent["layer"],
    items: LayerItem[],
  ): void {
    const layer: LayerContent = {
      layer: layerName,
      items,
      advisory: null,
    }
    render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay={"morning" as TimeOfDaySignal}
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
  }

  it("emits canonical console.warn message with required fields", () => {
    renderLayer("personal", [
      makeWidgetItem({
        item_id: "fake",
        component_key: "unregistered_widget",
      }),
    ])
    expect(warnSpy).toHaveBeenCalledOnce()
    const [message, payload] = warnSpy.mock.calls[0]
    expect(message).toBe(
      "[pulse] missing widget renderer; skipping piece",
    )
    expect(payload).toMatchObject({
      component_key: "unregistered_widget",
      layer: "personal",
      item_id: "fake",
      kind: "widget",
    })
    // Hint field references canon section + CI parity test path.
    expect((payload as { hint?: string }).hint).toContain("§13.4.3")
    expect((payload as { hint?: string }).hint).toContain(
      "widget-renderer-parity",
    )
  })

  it("debounces same widget_id in same layer across re-renders (one warn per session)", () => {
    const items: LayerItem[] = [
      makeWidgetItem({
        item_id: "fake",
        component_key: "unregistered_widget",
      }),
    ]
    // Three render passes — each would attempt to warn without dedupe.
    renderLayer("personal", items)
    renderLayer("personal", items)
    renderLayer("personal", items)
    expect(warnSpy).toHaveBeenCalledOnce()
  })

  it("warns separately for different widget_ids in same layer", () => {
    renderLayer("personal", [
      makeWidgetItem({
        item_id: "a",
        component_key: "unregistered_a",
      }),
      makeWidgetItem({
        item_id: "b",
        component_key: "unregistered_b",
      }),
    ])
    expect(warnSpy).toHaveBeenCalledTimes(2)
  })

  it("warns separately for same widget_id in different layers (per layer:key debounce)", () => {
    renderLayer("personal", [
      makeWidgetItem({
        item_id: "a",
        component_key: "shared_unregistered",
      }),
    ])
    renderLayer("operational", [
      makeWidgetItem({
        item_id: "b",
        component_key: "shared_unregistered",
      }),
    ])
    // Different layer:key tuples → 2 separate warns
    expect(warnSpy).toHaveBeenCalledTimes(2)
  })

  it("does NOT warn for renderable widgets (registered renderer)", () => {
    registerWidgetRenderer("real", MockWidgetRenderer)
    renderLayer("personal", [
      makeWidgetItem({ item_id: "ok", component_key: "real" }),
    ])
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it("does NOT warn for stream pieces (always renderable)", () => {
    renderLayer("anomaly", [
      makeStreamItem({
        item_id: "s1",
        component_key: "any_stream_key",
      }),
    ])
    expect(warnSpy).not.toHaveBeenCalled()
  })
})


// ── TestSessionB1PersonalLayerDeferral ───────────────────────────────


describe("TestSessionB1PersonalLayerDeferral", () => {
  // Phase W-4a Cleanup Session B.1 (2026-05-04): backend
  // personal_layer_service.py defers _build_tasks_item +
  // _build_approvals_item to return None always pending Phase W-4b
  // migration to operational_layer_service. Per §3.26.7.5 canonical-
  // quality discipline. Frontend contract: personal layer arrives
  // with items=[] + canonical advisory; PulseLayer renders advisory-
  // only; no empty Pattern 2 card; no console.warn fires (because no
  // unrenderable items reach the filter).

  it("personal layer with items=[] + advisory renders advisory only — no piece chrome", () => {
    const layer: LayerContent = {
      layer: "personal",
      items: [],
      advisory: "Nothing addressed to you right now.",
    }
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay={"morning" as TimeOfDaySignal}
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    // Layer renders empty-state advisory.
    const emptySection = container.querySelector(
      '[data-slot="pulse-layer"][data-empty="true"]',
    )
    expect(emptySection).not.toBeNull()
    expect(container.textContent).toContain(
      "Nothing addressed to you right now.",
    )
    // CRITICAL: no piece chrome anywhere (the pre-Session-B.1 drift
    // rendered an empty Pattern 2 card here).
    const pieces = container.querySelectorAll('[data-slot="pulse-piece"]')
    expect(pieces.length).toBe(0)
    // No console.warn fires — there are no items to filter.
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it("backend deferral closes the approvals_waiting + tasks_assigned drift surfaced by Commit 4", () => {
    // Pre-Session-B.1 contract (now retired): backend emitted
    // kind="stream" LayerItems for tasks_assigned and approvals_waiting
    // but composition_engine had no matching IntelligenceStream
    // registration → PulsePiece's stream-render path returned null →
    // empty Pattern 2 card visible. This test simulates the
    // post-Session-B.1 contract: backend emits items=[].
    const layer: LayerContent = {
      layer: "personal",
      items: [],
      advisory: "Nothing addressed to you right now.",
    }
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay={"morning" as TimeOfDaySignal}
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    // Critical regression guard: no piece carrying the deferred
    // component_keys leaks into the rendered DOM under any path.
    expect(
      container.querySelector('[data-component-key="approvals_waiting"]'),
    ).toBeNull()
    expect(
      container.querySelector('[data-component-key="tasks_assigned"]'),
    ).toBeNull()
    // No warns for these component_keys either (backend doesn't emit
    // them; frontend has no LayerItem to filter).
    const warnsForDeferredKeys = warnSpy.mock.calls.filter(
      (args: unknown[]) => {
        const payload = args[1] as { component_key?: string } | undefined
        return (
          payload?.component_key === "approvals_waiting" ||
          payload?.component_key === "tasks_assigned"
        )
      },
    )
    expect(warnsForDeferredKeys.length).toBe(0)
  })
})
