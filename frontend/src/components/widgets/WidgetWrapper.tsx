// WidgetWrapper — standard chrome around every widget

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
    <div className="flex flex-col rounded-lg border border-gray-200 bg-white shadow-sm h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-2 min-h-[40px]">
        {editMode && (
          <div
            className="cursor-grab text-gray-400 hover:text-gray-600 shrink-0"
            {...(dragHandleProps || {})}
          >
            <GripVertical className="h-4 w-4" />
          </div>
        )}

        {icon && <span className="shrink-0 text-gray-500">{icon}</span>}
        <h3 className="text-sm font-semibold text-gray-800 truncate flex-1">{title}</h3>

        {/* Refresh */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
          </button>
        )}

        {/* Overflow menu */}
        <div className="relative shrink-0" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-40 rounded-md border bg-white py-1 shadow-lg">
              {/* Size options */}
              {supportedSizes && supportedSizes.length > 1 && onSizeChange && (
                <>
                  <div className="px-3 py-1 text-[10px] font-semibold text-gray-400 uppercase">
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
                        className="rounded border px-1.5 py-0.5 text-[11px] font-mono text-gray-600 hover:bg-gray-100"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <div className="border-t border-gray-100 my-1" />
                </>
              )}

              {/* Remove (edit mode only) */}
              {editMode && onRemove && (
                <button
                  onClick={() => {
                    onRemove()
                    setMenuOpen(false)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
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
            className="shrink-0 text-gray-400 hover:text-red-500 transition-colors"
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
          <div className="flex flex-col items-center justify-center gap-2 py-4 text-center text-sm text-gray-500">
            <p className="text-red-500">{error}</p>
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="text-xs text-blue-600 hover:underline"
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
