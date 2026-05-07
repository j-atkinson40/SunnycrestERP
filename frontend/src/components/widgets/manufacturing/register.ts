/**
 * Phase W-3d manufacturing per-line widget registration.
 *
 * Side-effect module — importing this file registers the W-3d
 * manufacturing per-line widgets with the canvas widget renderer
 * registry so Canvas / PinnedSection / Stack / BottomSheet / etc.
 * surfaces dispatch them correctly via `getWidgetRenderer(widget_id)`.
 *
 * Mirrors the established Phase W-3a/W-3b pattern at
 * `foundation/register.ts` — same side-effect-on-import shape so each
 * widget cluster owns its registration without coupling to the
 * framework.
 *
 * Imported once at app bootstrap (see App.tsx) alongside the
 * foundation register.
 */

import type { ComponentType } from "react"

import {
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"

// R-1.6.12: wrapped versions of vault_schedule + line_status (carry
// data-component-name boundary div from `registerComponent` HOC).
// urn_catalog_status is not yet in the visual-editor metadata
// registry — stays unwrapped until promoted.
//
// Cast through `unknown` is required because the wrapped components
// preserve their original prop type (e.g. `VaultScheduleWidgetProps`
// declares a wider `surface` literal that includes "dashboard_grid"
// + an optional `widgetId`). React's `ComponentType` exposes
// `defaultProps` which is invariant on prop type, so structural
// assignment fails despite contravariant function-arg compatibility.
// Same runtime contract as pre-R-1.6.12 — the widget accepts the
// narrower `WidgetRendererProps` at runtime.
import {
  LineStatusWidget as LineStatusWidgetWrapped,
  VaultScheduleWidget as VaultScheduleWidgetWrapped,
} from "@/lib/visual-editor/registry/registrations/widgets"

import { UrnCatalogStatusWidget } from "./UrnCatalogStatusWidget"

const VaultScheduleWidget =
  VaultScheduleWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const LineStatusWidget =
  LineStatusWidgetWrapped as unknown as ComponentType<WidgetRendererProps>


// `vault_schedule` widget — Phase W-3d manufacturing per-line
// workspace-core canonical reference. Per DESIGN_LANGUAGE.md §12.6:
// renders the SAME data the scheduling Focus kanban core consumes
// with a deliberately abridged interactive surface. Mode-aware:
// production reads Delivery rows, purchase reads LicenseeTransfer
// incoming rows, hybrid composes both. 5-axis filter:
// `required_vertical=["manufacturing"]`, `required_product_line=["vault"]`.
// Cards enrich Delivery rows with SalesOrder context (deceased,
// customer, line items) at render time — Delivery is the canonical
// scheduling entity per the SalesOrder-vs-Delivery investigation.
registerWidgetRenderer("vault_schedule", VaultScheduleWidget)


// `line_status` widget — Phase W-3d cross-line health aggregator.
// Multi-line builder pattern (mirrors today widget): vault metrics
// real today; redi_rock / wastewater / urn_sales placeholders
// activate when each per-line aggregator ships. 5-axis filter:
// `required_vertical=["manufacturing"]`, `required_product_line=["*"]`
// (renders for whichever lines are active per tenant). Brief +
// Detail variants — NO Glance because line status is operational
// health that doesn't compress to count-only.
registerWidgetRenderer("line_status", LineStatusWidget)


// `urn_catalog_status` widget — Phase W-3d extension-gated widget.
// **First widget in the catalog exercising the `required_extension`
// axis end-to-end** — visible only to tenants with the `urn_sales`
// extension activated. 5-axis filter:
// `required_vertical=["manufacturing"]`, `required_product_line=["urn_sales"]`,
// `required_extension="urn_sales"`. Glance + Brief variants —
// catalog management lives at /urns/catalog (the page); the widget
// surfaces health (SKU counts, low-stock, recent orders).
registerWidgetRenderer("urn_catalog_status", UrnCatalogStatusWidget)
