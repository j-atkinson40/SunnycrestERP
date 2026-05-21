/**
 * AtomPalette — left-rail atom catalog for the WB-4a Widget Builder.
 *
 * Two sections per Area 3 lock:
 *   - Content & Visual: text_label, value_display, icon, status_badge,
 *     divider, image
 *   - Container & Interactive: conditional_container, repeater_atom,
 *     button
 *
 * Each tile is a @dnd-kit `useDraggable` source. The page-level
 * DndContext (PointerSensor + KeyboardSensor per Q-40) routes
 * onDragEnd → drop target on the canvas. The tile carries its
 * atom_type in the `data` payload; the canvas reads it to construct
 * the appropriate AtomNode default.
 *
 * Visual: Lucide icon + atom name only (Area 3 lock — restraint).
 *
 * Test ids:
 *   - data-testid="widget-builder-atom-palette" on the rail root.
 *   - data-testid="widget-builder-atom-tile-{atom_type}" on each tile.
 *   - data-testid="widget-builder-atom-section-{content|container}".
 */
import { useDraggable } from "@dnd-kit/core"
import type { LucideIcon } from "lucide-react"
import {
  Box,
  Hash,
  Image as ImageIcon,
  List,
  Minus,
  MousePointer,
  Star,
  Tag,
  Type,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type { AtomType } from "@/lib/widget-builder/types/composition-blob"
import { ATOM_TYPE_LABELS } from "@/lib/widget-builder/types/composition-blob"


/** Palette entry per atom — narrow shape for testing. */
export interface AtomPaletteEntry {
  atom_type: AtomType
  label: string
  icon: LucideIcon
}


/** Suggested Lucide icon mapping per build prompt. Refine if better
 *  fit surfaces in operator-facing work (WB-4b inspector polish). */
export const ATOM_ICON_MAP: Record<AtomType, LucideIcon> = {
  text_label: Type,
  value_display: Hash,
  icon: Star,
  status_badge: Tag,
  divider: Minus,
  image: ImageIcon,
  button: MousePointer,
  conditional_container: Box,
  repeater_atom: List,
}


/** Two-section catalog per Area 3 lock. */
export const ATOM_SECTIONS: Array<{
  key: "content" | "container"
  title: string
  atom_types: AtomType[]
}> = [
  {
    key: "content",
    title: "Content & Visual",
    atom_types: [
      "text_label",
      "value_display",
      "icon",
      "status_badge",
      "divider",
      "image",
    ],
  },
  {
    key: "container",
    title: "Container & Interactive",
    atom_types: ["conditional_container", "repeater_atom", "button"],
  },
]


/** Per-atom draggable tile. */
function AtomTile({ atom_type }: { atom_type: AtomType }) {
  const Icon = ATOM_ICON_MAP[atom_type]
  const label = ATOM_TYPE_LABELS[atom_type]
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-atom:${atom_type}`,
    data: { source: "palette", atom_type },
  })
  return (
    <button
      ref={setNodeRef}
      type="button"
      data-testid={`widget-builder-atom-tile-${atom_type}`}
      data-atom-type={atom_type}
      data-dragging={isDragging ? "true" : "false"}
      aria-label={`Drag ${label} atom onto the canvas`}
      className={cn(
        "flex w-full items-center gap-2 rounded-md border border-border-subtle",
        "bg-surface-raised px-3 py-2 text-left text-body-sm text-content-base",
        "hover:bg-surface-elevated hover:border-border-base",
        "active:cursor-grabbing cursor-grab",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
        isDragging && "opacity-50",
      )}
      {...listeners}
      {...attributes}
    >
      <Icon size={16} className="text-content-muted shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  )
}


export function AtomPalette() {
  return (
    <aside
      data-testid="widget-builder-atom-palette"
      className="flex h-full w-60 flex-col gap-4 border-r border-border-subtle bg-surface-sunken p-3"
    >
      <div className="text-caption font-medium uppercase tracking-wide text-content-muted">
        Atoms
      </div>
      {ATOM_SECTIONS.map((section) => (
        <section
          key={section.key}
          data-testid={`widget-builder-atom-section-${section.key}`}
          className="flex flex-col gap-2"
        >
          <div className="text-caption font-medium text-content-muted">
            {section.title}
          </div>
          <div className="flex flex-col gap-1.5">
            {section.atom_types.map((atom_type) => (
              <AtomTile key={atom_type} atom_type={atom_type} />
            ))}
          </div>
        </section>
      ))}
    </aside>
  )
}
