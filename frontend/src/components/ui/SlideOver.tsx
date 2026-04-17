// SlideOver — platform primitive for right-edge panels.
// Stacks correctly (multiple slide-overs can be open, each above the previous).
// Mobile: full-screen. Escape closes. Click backdrop closes unless disabled.

import { useEffect, type ReactNode } from "react"
import { X } from "lucide-react"

export type SlideOverWidth = "sm" | "md" | "lg" | "xl"

interface Props {
  isOpen: boolean
  onClose: () => void
  title: string
  width?: SlideOverWidth
  children: ReactNode
  showBackdrop?: boolean
  closeOnBackdropClick?: boolean
  footer?: ReactNode
  /** z-index offset for stacked slide-overs (default 60). Each nested one should add 10. */
  zIndex?: number
}

const WIDTHS: Record<SlideOverWidth, string> = {
  sm: "max-w-[400px]",
  md: "max-w-[600px]",
  lg: "max-w-[800px]",
  xl: "max-w-[1000px]",
}

export function SlideOver({
  isOpen,
  onClose,
  title,
  width = "md",
  children,
  showBackdrop = true,
  closeOnBackdropClick = true,
  footer,
  zIndex = 60,
}: Props) {
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 pointer-events-none" style={{ zIndex }}>
      {showBackdrop && (
        <div
          className="absolute inset-0 bg-black/30 transition-opacity duration-300 pointer-events-auto"
          onClick={closeOnBackdropClick ? onClose : undefined}
        />
      )}

      <div
        className={`absolute right-0 top-0 h-full w-full ${WIDTHS[width]} bg-white shadow-2xl pointer-events-auto flex flex-col transition-transform duration-300 ease-out`}
        style={{ transform: "translateX(0)" }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="slide-over-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 flex-shrink-0">
          <h2 id="slide-over-title" className="text-base font-semibold text-slate-900">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-slate-200 px-5 py-3 flex-shrink-0 bg-slate-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export default SlideOver
