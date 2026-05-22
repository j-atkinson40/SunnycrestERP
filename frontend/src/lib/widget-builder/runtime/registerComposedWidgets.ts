/**
 * registerComposedWidgets — WB-3 visual-editor metadata registry
 * bridge.
 *
 * Composed widget definitions (rows in the platform-wide
 * `widget_definitions` table with `composition_blob` populated) live
 * server-side, NOT in `class-registrations.ts` like hand-coded widgets.
 * For Focus Builder palette + placement to discover composed widgets,
 * each definition needs a corresponding entry in the in-memory
 * visual-editor metadata registry (the singleton consumed by
 * `getByType("widget")` + `getByName("widget", slug)`).
 *
 * Flow:
 *   1. App boot calls `registerComposedWidgetsFromApi()` (fire-and-forget;
 *      logs warning on failure + continues — hand-coded widgets stay
 *      registered regardless).
 *   2. Helper GETs `/api/v1/widgets/composed-definitions`.
 *   3. For each row, calls `registerComposedWidgetMeta()` which
 *      registers the metadata via `registerComponent` AND wraps a
 *      `ComposedWidget`-bound component that the Focus Builder
 *      palette + PlacedWidgetCore consume to render the composed
 *      widget end-to-end.
 *
 * Phase 1: at-boot only; reload required to pick up server-side
 * changes. Future phases may stream updates or invalidate per
 * widget id.
 *
 * Module-scoped guard prevents double-registration on hot reload
 * (the registry's own re-register safety covers metadata drift but
 * we still don't want to re-fetch the API on every HMR cycle).
 */

import { type ComponentType, createElement } from "react"

import apiClient from "@/lib/api-client"
import { registerComponent } from "@/lib/visual-editor/registry/register"
import type { ComponentKind } from "@/lib/visual-editor/registry/types"

import type {
  CompositionBlob,
  VariantId,
} from "../types/composition-blob"

import { ComposedWidget } from "./ComposedWidget"


export interface ComposedWidgetDefinitionDTO {
  widget_id: string
  title: string
  description: string | null
  icon: string | null
  category: string | null
  composition_blob: unknown
  composition_version: number | null
  tier_scope: "platform" | "vertical" | null
  supported_surfaces: string[]
  default_size: string
  supported_sizes: string[]
}


let _fetchAttempted = false


/** Register a single composed widget definition's metadata in the
 *  visual-editor registry. Exported for tests + future ad-hoc use. */
/** WB-8 Lock 6b — resolve the effective variantId for bridge consumers.
 *  Resolution chain:
 *    1. `composition_blob.default_variant_id` (Lock 6a-stored default)
 *    2. `composition_blob.variants[0]?.variant_id` (first declared)
 *    3. `undefined` (the "all atoms" unfiltered render path)
 *
 *  Exported for tests + future ad-hoc resolution callers. */
export function resolveEffectiveVariantId(
  blob: CompositionBlob | unknown,
): VariantId | string | undefined {
  if (blob === null || typeof blob !== "object") return undefined
  const b = blob as Partial<CompositionBlob>
  if (typeof b.default_variant_id === "string" && b.default_variant_id) {
    return b.default_variant_id
  }
  const first = Array.isArray(b.variants) ? b.variants[0] : undefined
  if (first && typeof first.variant_id === "string") {
    return first.variant_id
  }
  return undefined
}


export function registerComposedWidgetMeta(
  defn: ComposedWidgetDefinitionDTO,
): void {
  const slug = defn.widget_id
  // WB-8 — pre-compute the bridge's effective variantId so the
  // Component wrapper falls into the resolution chain at registration
  // time. Allows future consumer overrides to pass variantId via
  // props (currently the Focus Builder palette + PlacedWidgetCore
  // call this with zero props; future Page Builder will pass
  // variantId derived from the rendering surface — Lock 6d).
  const resolvedDefaultVariant = resolveEffectiveVariantId(
    defn.composition_blob,
  ) as VariantId | undefined
  // The Component handed to registerComponent is the renderer that
  // Focus Builder palette + PlacedWidgetCore will call. It wraps
  // ComposedWidget with the definition's composition_blob.
  const Component: ComponentType<{ variantId?: VariantId }> = (props) =>
    createElement(ComposedWidget, {
      widgetDefinition: {
        widget_id: slug,
        composition_blob: defn.composition_blob,
      },
      variantId: props.variantId ?? resolvedDefaultVariant,
    })
  Component.displayName = `ComposedWidgetBound(${slug})`

  registerComponent({
    type: "widget" as ComponentKind,
    name: slug,
    displayName: defn.title || slug,
    description: defn.description ?? undefined,
    category: defn.category ?? "composed",
    // Composed widgets ship cross-vertical by default. WB-4+ may
    // expose a verticals authoring control; today, "all" keeps
    // them discoverable in every Focus Builder palette.
    verticals: ["all"],
    userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
    consumedTokens: [],
    canvasPlaceable: true,
    canvasMetadata: {
      minDimensions: { columns: 2, rows: 2 },
      defaultDimensions: { columns: 4, rows: 3 },
      freeFormDefaultDimensions: { width: 320, height: 180 },
      freeFormMinDimensions: { width: 120, height: 64 },
      resizable: true,
    },
    configurableProps: {},
    schemaVersion: 1,
    componentVersion: defn.composition_version ?? 1,
    // Forward-compat: store composition metadata in extensions so
    // future tooling can introspect without a registry-type change.
    extensions: {
      composition_blob: defn.composition_blob,
      composition_version: defn.composition_version,
      tier_scope: defn.tier_scope,
      composed: true,
    },
  })(Component)
}


/** Boot adapter — fetches composed widget definitions + registers
 *  each. Fire-and-forget; logs warning on failure. Idempotent (a
 *  second call is a no-op).
 *
 *  Returns the number of definitions registered (0 on failure).
 *  Tests await the promise; the App.tsx side-effect call ignores it.
 */
export async function registerComposedWidgetsFromApi(): Promise<number> {
  if (_fetchAttempted) return 0
  _fetchAttempted = true
  try {
    const response = await apiClient.get<ComposedWidgetDefinitionDTO[]>(
      "/widgets/composed-definitions",
    )
    const rows = response.data ?? []
    for (const row of rows) {
      try {
        registerComposedWidgetMeta(row)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(
          `[registerComposedWidgets] registration failed for widget_id=${row.widget_id}:`,
          err,
        )
      }
    }
    return rows.length
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn(
      "[registerComposedWidgets] fetch failed; composed widgets unavailable in palette this session:",
      err,
    )
    return 0
  }
}


/** WB-4a — refresh after Publish.
 *
 *  The Widget Builder shell calls this after a successful Publish so
 *  the operator's newly-published composed widget surfaces in Focus
 *  Builder palette + other consumers WITHOUT a page reload. Unlike
 *  `registerComposedWidgetsFromApi` (which is gated by the module-
 *  scoped boot guard), this helper forces a fresh fetch + re-registers
 *  every row. Idempotent: registerComponent silently overwrites an
 *  existing registration at the same (type, name) key.
 *
 *  Returns the number of definitions registered (0 on failure). Logs
 *  + swallows fetch errors so the calling Publish flow never fails on
 *  registry-refresh issues — the publish itself already landed.
 */
export async function refreshComposedWidgets(): Promise<number> {
  try {
    const response = await apiClient.get<ComposedWidgetDefinitionDTO[]>(
      "/widgets/composed-definitions",
    )
    const rows = response.data ?? []
    for (const row of rows) {
      try {
        registerComposedWidgetMeta(row)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(
          `[refreshComposedWidgets] registration failed for widget_id=${row.widget_id}:`,
          err,
        )
      }
    }
    // After a refresh, the boot guard is moot — mark fetched.
    _fetchAttempted = true
    return rows.length
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn(
      "[refreshComposedWidgets] refresh failed; palette will show stale state until next reload:",
      err,
    )
    return 0
  }
}


/** Test helper — reset the module-scoped guard so a fresh fetch can
 *  run. Not exported from the public barrel; tests import directly. */
export function _resetForTests(): void {
  _fetchAttempted = false
}
