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
 *
 * CLICK-TO-ADD MODE (additive — Workflow Builder palette, 2026-05-29):
 *   - When `onItemClick` is provided, items are CLICK-to-add (button
 *     semantics: onClick + Enter/Space, `cursor: pointer`) and drag is
 *     disabled (useDraggable is still called for hook-rule stability but
 *     its listeners/attributes are NOT spread). When ABSENT, items keep
 *     the existing drag behavior verbatim (Focus Builder path unchanged).
 *   - `PaletteItem.iconComponent` (a Lucide component) takes precedence
 *     over the `iconName` string-map when present; the string-map path is
 *     untouched.
 *   - `PaletteItem.testId` overrides the default `widget-palette-item`
 *     testid (so consumers can namespace their items).
 */
import type { KeyboardEvent as ReactKeyboardEvent } from "react"
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
  /** Additive: a Lucide icon component, preferred over `iconName`. */
  iconComponent?: LucideIcon
  /** Additive: override the default `widget-palette-item` testid. */
  testId?: string
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
  /**
   * Additive: when provided, items become CLICK-to-add (drag disabled),
   * invoked with the PaletteItem `id`. When absent, items stay draggable
   * (the original Focus Builder behavior, unchanged).
   */
  onItemClick?: (id: string) => void
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
  onItemClick,
}: {
  item: PaletteItem
  disabled: boolean
  onItemClick?: (id: string) => void
}) {
  const clickMode = !!onItemClick
  // Hook-rule: useDraggable is always called. In click-mode it's disabled
  // and its listeners/attributes are NOT spread → no drag affordance.
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: item.id,
    disabled: disabled || clickMode,
  })
  const Icon =
    item.iconComponent ??
    (item.iconName ? ICON_MAP[item.iconName] ?? Square : Square)
  // Interactive props are mutually exclusive:
  //  - DRAG mode (onItemClick absent): spread dnd-kit `attributes`
  //    (which includes `tabIndex: 0` + role for the KeyboardSensor) +
  //    `listeners`. This branch is byte-identical to the pre-extension
  //    behavior — DO NOT add explicit tabIndex/onClick here, they would
  //    clobber dnd-kit's attributes and break keyboard-drag activation.
  //  - CLICK mode (onItemClick present): button semantics (onClick +
  //    Enter/Space), focusable, NO drag listeners.
  const interactive = clickMode
    ? {
        role: "button" as const,
        tabIndex: disabled ? undefined : 0,
        onClick: disabled ? undefined : () => onItemClick?.(item.id),
        onKeyDown: disabled
          ? undefined
          : (ev: ReactKeyboardEvent) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault()
                onItemClick?.(item.id)
              }
            },
      }
    : { ...attributes, ...listeners, role: "button" as const }
  return (
    <div
      ref={setNodeRef}
      data-testid={item.testId ?? "widget-palette-item"}
      data-item-id={item.id}
      data-dragging={isDragging ? "true" : "false"}
      aria-disabled={disabled ? "true" : undefined}
      {...interactive}
      style={{
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : clickMode ? "pointer" : "grab",
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
  const { categories, disabled = false, emptyHint, onItemClick } = props

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
                  onItemClick={onItemClick}
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
