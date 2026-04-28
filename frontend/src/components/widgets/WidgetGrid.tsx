// WidgetGrid — universal responsive grid that renders widgets from a layout

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

import WidgetErrorBoundary from "./WidgetErrorBoundary"
import { parseSize, type WidgetLayoutItem, type WidgetComponentMap } from "./types"

interface WidgetGridProps {
  widgets: WidgetLayoutItem[]
  componentMap: WidgetComponentMap
  editMode: boolean
  onReorder: (widgetIds: string[]) => void
  onRemove: (widgetId: string) => void
  onSizeChange: (widgetId: string, size: string) => void
}

function SortableWidget({
  item,
  componentMap,
  editMode,
  onRemove,
  onSizeChange,
}: {
  item: WidgetLayoutItem
  componentMap: WidgetComponentMap
  editMode: boolean
  onRemove: (widgetId: string) => void
  onSizeChange: (widgetId: string, size: string) => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.widget_id, disabled: !editMode })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const { cols, rows } = parseSize(item.size)
  const Component = componentMap[item.widget_id]

  if (!Component) {
    return null
  }

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        gridColumn: `span ${cols}`,
        gridRow: `span ${rows}`,
      }}
      {...attributes}
    >
      <WidgetErrorBoundary widgetId={item.widget_id}>
        <Component
          // WidgetWrapper receives these via internal props.
          // Widget components manage their own WidgetWrapper.
          //
          // Widget Library Phase W-1 (Section 12.3 contract) injects
          // `variant_id` + `surface` alongside the legacy underscore-
          // prefixed framework props. Existing widgets ignore them
          // (loose `WidgetProps` shape); Phase W-3 widgets adopt
          // `WidgetVariantProps` and read them directly. Migration
          // window per Decision 10.
          {...({
            _editMode: editMode,
            _dragHandleProps: listeners,
            _onRemove: () => onRemove(item.widget_id),
            _onSizeChange: (size: string) => onSizeChange(item.widget_id, size),
            _size: item.size,
            _supportedSizes: item.supported_sizes,
            // Phase W-1 unified contract.
            variant_id: item.variant_id,
            surface: "dashboard_grid" as const,
            // Phase W-3b — per-instance widget configuration. Sourced
            // from `WidgetLayoutItem.config` (persisted via dashboard
            // layout API). Widgets that don't declare a config schema
            // ignore this prop. saved_view widget reads
            // `config.view_id` to decide which view to render.
            config: item.config,
          } as Record<string, unknown>)}
        />
      </WidgetErrorBoundary>
    </div>
  )
}

export default function WidgetGrid({
  widgets,
  componentMap,
  editMode,
  onReorder,
  onRemove,
  onSizeChange,
}: WidgetGridProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const enabledWidgets = widgets.filter((w) => w.enabled && componentMap[w.widget_id])

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = enabledWidgets.findIndex((w) => w.widget_id === active.id)
    const newIndex = enabledWidgets.findIndex((w) => w.widget_id === over.id)

    const reordered = arrayMove(enabledWidgets, oldIndex, newIndex)
    onReorder(reordered.map((w) => w.widget_id))
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={enabledWidgets.map((w) => w.widget_id)}
        strategy={rectSortingStrategy}
      >
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gridAutoRows: "minmax(200px, auto)",
          }}
        >
          {enabledWidgets.map((item) => (
            <SortableWidget
              key={item.widget_id}
              item={item}
              componentMap={componentMap}
              editMode={editMode}
              onRemove={onRemove}
              onSizeChange={onSizeChange}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  )
}
