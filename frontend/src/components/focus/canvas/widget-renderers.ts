/**
 * Widget renderer registry — Phase B Session 4.3b.3.
 *
 * Pre-4.3b.3 each canvas dispatch site (Canvas, BottomSheet, StackRail,
 * StackExpandedOverlay) hardcoded `<MockSavedViewWidget />` for every
 * widget. There was no widget-type discriminator — `WidgetState` only
 * carried `position`. Phase 4.3b.3 ships the first non-placeholder
 * widget (AncillaryPoolPin) which means the framework needs to
 * dispatch by `widgetType`.
 *
 * Pattern
 * ───────
 * Canvas-side primitives (Canvas, BottomSheet, StackRail,
 * StackExpandedOverlay) call `getWidgetRenderer(widgetType)` and
 * render the resulting component. Default fallback when widgetType
 * is undefined or unknown is `MockSavedViewWidget` — preserves
 * back-compat for layouts that predate the typed-widget system.
 *
 * Per-feature widgets register themselves via side-effect imports
 * at app boot. Example:
 *
 *   // frontend/src/components/dispatch/scheduling-focus/register.ts
 *   import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
 *   import { AncillaryPoolPin } from "./AncillaryPoolPin"
 *   registerWidgetRenderer("funeral-scheduling.ancillary-pool", AncillaryPoolPin)
 *
 * Same side-effect-on-import pattern that `register.ts` already uses
 * for `registerFocus` — the file is imported once at App bootstrap so
 * the registrations land before any Focus mounts.
 *
 * Why a Map, not a static object literal
 * ──────────────────────────────────────
 * A static literal would force every widget to live in this file,
 * which couples the canvas framework to feature-specific imports
 * (Canvas → AncillaryPoolPin → SchedulingFocusContext → ... is a
 * cross-feature dependency the canvas primitive should not have). A
 * mutable registry with `register*` lets feature modules attach
 * themselves to the framework in their own bootstrap, preserving
 * one-directional dependency flow (feature imports framework,
 * framework doesn't import feature).
 *
 * What this registry does NOT do
 * ──────────────────────────────
 * - **Does not pass per-widget data props.** Widgets that need
 *   contextual data (like AncillaryPoolPin reading pool ancillaries)
 *   subscribe to a feature-owned React context. The registry's
 *   `WidgetRendererProps` carries identity (`widgetId`) only — data
 *   piping per widget would centralize feature concerns into the
 *   framework. Future shared per-widget config (e.g. saved view id
 *   for a Phase A Session 5 saved-view pin) would land here as
 *   additional optional props on `WidgetRendererProps`, not as a
 *   widget-by-widget data dispatch.
 */

import type { ComponentType } from "react"

import { MockSavedViewWidget } from "./MockSavedViewWidget"


export interface WidgetRendererProps {
  /** Stable widget id from `WidgetState`. Useful for telemetry +
   *  per-widget local state keys. */
  widgetId: string
}


const REGISTRY = new Map<string, ComponentType<WidgetRendererProps>>()

// Default registration. MockSavedViewWidget covers any widget without
// an explicit `widgetType` (back-compat for layouts that predate
// the typed-widget system) plus the test fixtures used by
// `Canvas.test.tsx` + canvas-cousin tests.
REGISTRY.set("mock-saved-view", MockSavedViewWidget)


/** Register a widget component under `widgetType`. Idempotent — a
 *  re-registration overwrites the previous mapping (useful for hot-
 *  reload + tests that swap implementations). Called by feature
 *  modules at app boot via side-effect imports.
 *
 *  The `widgetType` string convention: dot-namespaced by feature,
 *  e.g. `"funeral-scheduling.ancillary-pool"`. Avoids accidental
 *  collisions across features. */
export function registerWidgetRenderer(
  widgetType: string,
  component: ComponentType<WidgetRendererProps>,
): void {
  REGISTRY.set(widgetType, component)
}


/** Resolve a widget renderer for the given `widgetType`. Returns
 *  `MockSavedViewWidget` when `widgetType` is undefined (legacy
 *  layouts) OR when the type is registered but missing (defensive —
 *  e.g. the registering module failed to load).
 *
 *  Callers (Canvas, BottomSheet, StackRail, StackExpandedOverlay)
 *  invoke this once per render and pass `widgetId` to the resulting
 *  component. */
export function getWidgetRenderer(
  widgetType: string | undefined,
): ComponentType<WidgetRendererProps> {
  if (widgetType === undefined) return MockSavedViewWidget
  return REGISTRY.get(widgetType) ?? MockSavedViewWidget
}


/** Test-only helper. Resets the registry to its default state
 *  (just `mock-saved-view`). Used by tests that register and
 *  unregister widgets to isolate from each other. NOT for production
 *  use — production registers once at app bootstrap and never
 *  unregisters. */
export function _resetWidgetRendererRegistryForTests(): void {
  REGISTRY.clear()
  REGISTRY.set("mock-saved-view", MockSavedViewWidget)
}
