// WidgetWrapper — standard chrome around every widget.
//
// Aesthetic Arc Phase II Batch 1a refresh — blast-radius migration.
// Prior: `bg-white border-gray-200 shadow-sm` + `border-gray-100` + `text-gray-{400,500,600,800}`.
// Now: DESIGN_LANGUAGE tokens across the board. A single file flip cascades to
// every widget rendered via WidgetGrid — Operations Board Desktop + Vault
// Overview + any future consumer — without touching widget component code.

import { useState, useEffect, useRef, type ReactNode } from "react"
import { cn } from "@/lib/utils"
import {
  GripVertical,
  RefreshCw,
  MoreHorizontal,
  X,
} from "lucide-react"
import WidgetSkeleton from "./WidgetSkeleton"

interface WidgetWrapperProps {
  widgetId: string
  title: string
  icon?: ReactNode
  size: string
  editMode: boolean
  onRemove?: () => void
  onSizeChange?: (size: string) => void
  supportedSizes?: string[]
  refreshInterval?: number
  children: ReactNode
  isLoading?: boolean
  error?: string | null
  onRefresh?: () => void
  dragHandleProps?: Record<string, unknown>
}

export default function WidgetWrapper({
  title,
  icon,
  editMode,
  onRemove,
  onSizeChange,
  supportedSizes,
  children,
  isLoading,
  error,
  onRefresh,
  dragHandleProps,
}: WidgetWrapperProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [menuOpen])

  return (
    <div className="flex flex-col rounded-md border border-border-subtle bg-surface-elevated shadow-level-1 h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2 min-h-[40px]">
        {editMode && (
          <div
            className="cursor-grab text-content-subtle hover:text-content-muted shrink-0"
            {...(dragHandleProps || {})}
          >
            <GripVertical className="h-4 w-4" />
          </div>
        )}

        {icon && <span className="shrink-0 text-content-muted">{icon}</span>}
        <h3 className="text-body-sm font-semibold text-content-strong truncate flex-1">
          {title}
        </h3>

        {/* Refresh */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="shrink-0 text-content-subtle hover:text-content-muted transition-colors duration-quick ease-settle focus-ring-brass rounded"
            title="Refresh"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
          </button>
        )}

        {/* Overflow menu */}
        <div className="relative shrink-0" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="text-content-subtle hover:text-content-muted transition-colors duration-quick ease-settle focus-ring-brass rounded"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-40 rounded-md border border-border-subtle bg-surface-raised py-1 shadow-level-2">
              {/* Size options */}
              {supportedSizes && supportedSizes.length > 1 && onSizeChange && (
                <>
                  <div className="px-3 py-1 text-micro font-semibold text-content-subtle uppercase tracking-wider">
                    Size
                  </div>
                  <div className="flex gap-1 px-3 pb-1.5">
                    {supportedSizes.map((s) => (
                      <button
                        key={s}
                        onClick={() => {
                          onSizeChange(s)
                          setMenuOpen(false)
                        }}
                        className="rounded-sm border border-border-subtle px-1.5 py-0.5 text-caption font-plex-mono text-content-muted hover:bg-brass-subtle focus-ring-brass"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <div className="border-t border-border-subtle my-1" />
                </>
              )}

              {/* Remove (edit mode only) */}
              {editMode && onRemove && (
                <button
                  onClick={() => {
                    onRemove()
                    setMenuOpen(false)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-body-sm text-status-error hover:bg-status-error-muted focus-ring-brass"
                >
                  <X className="h-3.5 w-3.5" />
                  Remove widget
                </button>
              )}
            </div>
          )}
        </div>

        {/* Edit mode: quick remove button */}
        {editMode && onRemove && (
          <button
            onClick={onRemove}
            className="shrink-0 text-content-subtle hover:text-status-error transition-colors duration-quick ease-settle focus-ring-brass rounded"
            title="Remove widget"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        {isLoading ? (
          <WidgetSkeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center gap-2 py-4 text-center text-body-sm text-content-muted">
            <p className="text-status-error">{error}</p>
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="text-caption text-brass hover:text-brass-hover hover:underline focus-ring-brass rounded"
              >
                Try again
              </button>
            )}
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  )
}
