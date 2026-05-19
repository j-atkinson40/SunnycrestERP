/**
 * WidgetPalette — reusable categorized palette primitive (sub-arc F-3).
 *
 * Consumer-opaque, same discipline as VerticalGroupedTree. The palette
 * knows nothing about widgets, focus types, or registry shapes — it
 * renders a list of categories, each with a list of items. Items are
 * draggable via @dnd-kit's `useDraggable`; the consumer wires the
 * surrounding `<DndContext>` and `onDragEnd` handler.
 *
 * Contract:
 *   - `categories`: top-level groups with item arrays.
 *   - Each `PaletteItem` is a draggable affordance with `id`, `label`,
 *     optional `description`, optional `iconName`.
 *   - The drag `active.id` IS the PaletteItem `id` (consumer's
 *     responsibility to namespace e.g. `palette-widget:<slug>`).
 *   - Empty category renders an explicit empty state ("No items").
 *   - Empty palette (zero categories) renders an empty-state hint.
 *
 * Future Page Builder / Document Builder palette consumers can reuse
 * this primitive with their own category + item shapes.
 */
import { useDraggable } from "@dnd-kit/core"
import {
  CalendarDays,
  Map as MapIcon,
  Pin,
  Square,
  type LucideIcon,
} from "lucide-react"

export interface PaletteItem {
  id: string
  label: string
  description?: string
  iconName?: string
}

export interface PaletteCategory {
  id: string
  label: string
  items: PaletteItem[]
}

export interface WidgetPaletteProps {
  categories: PaletteCategory[]
  /** Visual disabled state — when true, items render but cannot drag. */
  disabled?: boolean
  /** Hint shown when no categories exist. */
  emptyHint?: string
}

const ICON_MAP: Record<string, LucideIcon> = {
  "calendar-days": CalendarDays,
  map: MapIcon,
  pin: Pin,
  square: Square,
}

function PaletteItemRow({
  item,
  disabled,
}: {
  item: PaletteItem
  disabled: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: item.id,
    disabled,
  })
  const Icon = item.iconName ? ICON_MAP[item.iconName] ?? Square : Square
  return (
    <div
      ref={setNodeRef}
      data-testid="widget-palette-item"
      data-item-id={item.id}
      data-dragging={isDragging ? "true" : "false"}
      {...attributes}
      {...listeners}
      role="button"
      aria-disabled={disabled ? "true" : undefined}
      style={{
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "grab",
      }}
      className="flex items-start gap-2 rounded-md border border-[color:var(--border-subtle)] bg-surface-base px-2 py-1.5 text-[12px] transition-colors hover:bg-surface-elevated focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)]"
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--content-muted)]" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span
          className="truncate text-[color:var(--content-strong)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          {item.label}
        </span>
        {item.description && (
          <span
            className="truncate text-[11px] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            {item.description}
          </span>
        )}
      </div>
    </div>
  )
}

export function WidgetPalette(props: WidgetPaletteProps) {
  const { categories, disabled = false, emptyHint } = props

  if (categories.length === 0) {
    return (
      <div
        data-testid="widget-palette-empty"
        className="px-3 py-2 text-[11px] text-content-muted"
        style={{ fontFamily: "var(--font-plex-mono)" }}
      >
        {emptyHint ?? "No widgets available."}
      </div>
    )
  }

  return (
    <div
      data-testid="widget-palette"
      data-disabled={disabled ? "true" : "false"}
      className="flex flex-col gap-2 px-3 py-2"
    >
      {categories.map((cat) => (
        <section
          key={cat.id}
          data-testid="widget-palette-category"
          data-category-id={cat.id}
        >
          <header
            className="mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            {cat.label}
          </header>
          <div className="flex flex-col gap-1">
            {cat.items.length === 0 ? (
              <div
                data-testid="widget-palette-category-empty"
                className="rounded border border-dashed border-[color:var(--border-subtle)] px-2 py-1 text-[11px] text-content-muted"
              >
                No items
              </div>
            ) : (
              cat.items.map((item) => (
                <PaletteItemRow
                  key={item.id}
                  item={item}
                  disabled={disabled}
                />
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  )
}

export default WidgetPalette
