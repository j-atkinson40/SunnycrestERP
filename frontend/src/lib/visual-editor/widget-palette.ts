/**
 * Widget palette taxonomy — sub-arc F-3.
 *
 * Curated category vocabulary for the Focus Builder widget palette.
 * Same shape-discipline as `focus-types.ts` (F-1): a constant list +
 * a slug-to-category mapping + a lookup function with a sensible
 * fallback.
 *
 * Three categories — `ancillaries`, `map`, `information`. Categories
 * are platform-curated; new widgets land in `ancillaries` by default
 * (the catch-all bucket) unless explicitly mapped here.
 */

export const WIDGET_CATEGORIES = ["ancillaries", "map", "information"] as const
export type WidgetCategorySlug = (typeof WIDGET_CATEGORIES)[number]

export const WIDGET_CATEGORY_LABELS: Record<WidgetCategorySlug, string> = {
  ancillaries: "Ancillaries",
  map: "Map",
  information: "Information",
}

/**
 * Slug → category table. Mirrors `CORE_SLUG_TO_FOCUS_TYPE` shape.
 * Widgets not listed fall through to `ancillaries`.
 */
export const WIDGET_SLUG_TO_CATEGORY: Record<string, WidgetCategorySlug> = {
  "day-strip-widget": "information",
  "today-pin-widget": "information",
  "map-placeholder-widget": "map",
}

export function widgetCategoryFor(slug: string): WidgetCategorySlug {
  return WIDGET_SLUG_TO_CATEGORY[slug] ?? "ancillaries"
}

export function widgetCategoryLabel(category: WidgetCategorySlug): string {
  return WIDGET_CATEGORY_LABELS[category] ?? category
}
