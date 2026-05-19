/**
 * FocusBuilderPalette — Focus-specific consumer of WidgetPalette primitive.
 *
 * Sub-arc F-3. Reads the component registry for `kind: "widget"` AND
 * `canvasPlaceable: true` entries; groups them by `widget-palette.ts`
 * category vocabulary; renders via the consumer-opaque WidgetPalette
 * primitive.
 *
 * Item id format: `palette-widget:<slug>`. Drop handlers strip the
 * prefix to recover the widget slug.
 */
import * as React from "react"

import {
  getByType,
  isCanvasPlaceable,
} from "@/lib/visual-editor/registry"
import {
  WIDGET_CATEGORIES,
  widgetCategoryFor,
  widgetCategoryLabel,
  type WidgetCategorySlug,
} from "@/lib/visual-editor/widget-palette"

import {
  WidgetPalette,
  type PaletteCategory,
  type PaletteItem,
} from "../builder-primitives/WidgetPalette"

const SLUG_TO_ICON: Record<string, string> = {
  "day-strip-widget": "calendar-days",
  "today-pin-widget": "pin",
  "map-placeholder-widget": "map",
}

export const PALETTE_ITEM_PREFIX = "palette-widget:"

export function paletteItemIdToSlug(itemId: string): string | null {
  if (!itemId.startsWith(PALETTE_ITEM_PREFIX)) return null
  return itemId.slice(PALETTE_ITEM_PREFIX.length)
}

export interface FocusBuilderPaletteProps {
  /** Disabled when the active subject is a core (cores have no widgets). */
  disabled?: boolean
}

export function FocusBuilderPalette(props: FocusBuilderPaletteProps) {
  const { disabled = false } = props

  const categories = React.useMemo<PaletteCategory[]>(() => {
    const entries = getByType("widget").filter(isCanvasPlaceable)
    const buckets = new Map<WidgetCategorySlug, PaletteItem[]>()
    for (const cat of WIDGET_CATEGORIES) buckets.set(cat, [])
    for (const e of entries) {
      const slug = e.metadata.name
      const cat = widgetCategoryFor(slug)
      const item: PaletteItem = {
        id: `${PALETTE_ITEM_PREFIX}${slug}`,
        label: e.metadata.displayName ?? slug,
        description: e.metadata.description,
        iconName: SLUG_TO_ICON[slug],
      }
      buckets.get(cat)!.push(item)
    }
    return WIDGET_CATEGORIES.map((cat) => ({
      id: cat,
      label: widgetCategoryLabel(cat),
      items: buckets.get(cat) ?? [],
    })).filter((c) => c.items.length > 0)
  }, [])

  return (
    <WidgetPalette
      categories={categories}
      disabled={disabled}
      emptyHint="No widgets registered. Add via component registry."
    />
  )
}

export default FocusBuilderPalette
