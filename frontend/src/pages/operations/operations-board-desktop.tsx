// Operations Board — Desktop view (widget dashboard).
// Renders when effectiveDevice = 'desktop'. Mobile view is unchanged.
//
// Phase II Batch 1a refresh — migrated hardcoded Tailwind to DL tokens.
// Page title + date subtitle + refresh button chrome + edit-mode banner
// + customize button now use DESIGN_LANGUAGE tokens. Widget chrome picks
// up the DL palette via WidgetWrapper.tsx (refreshed in same batch).
// Amber-50 edit-mode banner migrates to Alert primitive variant.

import { useState, useMemo } from "react"
import { Settings, Check, RefreshCw, RotateCcw } from "lucide-react"
import { useDashboard } from "@/components/widgets/useDashboard"
import WidgetGrid from "@/components/widgets/WidgetGrid"
import WidgetPicker from "@/components/widgets/WidgetPicker"
import { OPS_BOARD_WIDGETS } from "@/components/widgets/ops-board"

function formatDate(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  })
}

function timeAgo(date: Date | null): string {
  if (!date) return "never"
  const mins = Math.floor((Date.now() - date.getTime()) / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins} min ago`
  return `${Math.floor(mins / 60)}h ago`
}

export default function OperationsBoardDesktop() {
  const dashboard = useDashboard("ops_board")
  const [pickerOpen, setPickerOpen] = useState(false)

  const currentWidgetIds = useMemo(
    () => dashboard.layout.filter((w) => w.enabled).map((w) => w.widget_id),
    [dashboard.layout]
  )

  function handleToggleEdit() {
    if (dashboard.editMode) {
      dashboard.setEditMode(false)
      setPickerOpen(false)
    } else {
      dashboard.setEditMode(true)
      setPickerOpen(true)
    }
  }

  if (dashboard.isLoading) {
    return (
      <div className="p-6 space-y-4 animate-pulse">
        <div className="h-8 w-48 bg-surface-sunken rounded-sm" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 bg-surface-sunken rounded-md" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Operations Board
          </h1>
          <p className="text-body-sm text-content-muted">{formatDate()}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Last updated */}
          <span className="text-caption text-content-subtle">
            Updated {timeAgo(dashboard.lastSaved)}
          </span>

          {/* Refresh all */}
          <button
            onClick={dashboard.reload}
            className="flex items-center gap-1.5 rounded-sm border border-border-subtle px-3 py-1.5 text-body-sm text-content-base hover:bg-brass-subtle transition-colors duration-quick ease-settle focus-ring-brass"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh all
          </button>

          {/* Customize / Done */}
          <button
            onClick={handleToggleEdit}
            className={`flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-body-sm font-medium transition-colors duration-quick ease-settle focus-ring-brass ${
              dashboard.editMode
                ? "bg-status-warning text-content-on-brass hover:bg-status-warning/90"
                : "bg-brass text-content-on-brass hover:bg-brass-hover"
            }`}
          >
            {dashboard.editMode ? (
              <>
                <Check className="h-3.5 w-3.5" />
                Done customizing
              </>
            ) : (
              <>
                <Settings className="h-3.5 w-3.5" />
                Customize
              </>
            )}
          </button>
        </div>
      </div>

      {/* Edit mode indicator */}
      {dashboard.editMode && (
        <div className="flex items-center justify-between rounded-md bg-status-warning-muted border border-status-warning/30 px-4 py-2">
          <p className="text-body-sm text-status-warning">
            Edit mode — drag widgets to reorder, use the panel to add or remove.
          </p>
          <button
            onClick={dashboard.resetLayout}
            className="flex items-center gap-1 text-caption text-status-warning hover:text-status-warning/80 focus-ring-brass rounded-sm"
          >
            <RotateCcw className="h-3 w-3" />
            Reset to default
          </button>
        </div>
      )}

      {/* Saving indicator */}
      {dashboard.isSaving && (
        <div className="text-caption text-content-subtle text-right">Saving...</div>
      )}

      {/* Widget grid */}
      <div className={pickerOpen ? "mr-80" : ""}>
        <WidgetGrid
          widgets={dashboard.layout}
          componentMap={OPS_BOARD_WIDGETS}
          editMode={dashboard.editMode}
          onReorder={dashboard.reorderWidgets}
          onRemove={dashboard.removeWidget}
          onSizeChange={dashboard.resizeWidget}
        />
      </div>

      {/* Widget picker panel */}
      {pickerOpen && (
        <WidgetPicker
          available={dashboard.available}
          currentWidgetIds={currentWidgetIds}
          onAdd={(id) => dashboard.addWidget(id)}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  )
}
