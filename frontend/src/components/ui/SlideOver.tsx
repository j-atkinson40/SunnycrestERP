// SlideOver — platform primitive for right-edge panels.
// Stacks correctly (multiple slide-overs can be open, each above the previous).
// Mobile: full-screen. Escape closes. Click backdrop closes unless disabled.
//
// Aesthetic Arc Session 2 refresh — brought onto DESIGN_LANGUAGE tokens:
//   - bg-surface-raised (level-2 raised — slide-overs sit above page
//     content, same level family as modals and dropdowns)
//   - shadow-level-3 (floating — slide-overs are the most-prominent
//     overlay on their screen; §6 "Floating: command bar, toasts,
//     tooltips" — slide-overs inherit this floating treatment)
//   - border-border-subtle on header/footer separators
//   - bg-surface-base on footer (sunken feel against raised body,
//     matching Card + Dialog footer convention)
//   - text-content-strong title, text-content-muted close icon
//   - ghost button treatment for the close — brass focus ring inherits
//   - bg-black/40 backdrop per DESIGN_LANGUAGE §9 canonical form
//   - duration-arrive ease-settle motion per §6 "Side panel opening"

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
          className="absolute inset-0 bg-black/40 transition-opacity duration-arrive ease-settle pointer-events-auto"
          onClick={closeOnBackdropClick ? onClose : undefined}
        />
      )}

      <div
        className={`absolute right-0 top-0 h-full w-full ${WIDTHS[width]} bg-surface-raised shadow-level-3 pointer-events-auto flex flex-col transition-transform duration-arrive ease-settle font-plex-sans text-content-base`}
        style={{ transform: "translateX(0)" }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="slide-over-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-3 flex-shrink-0">
          <h2
            id="slide-over-title"
            className="text-h4 font-medium text-content-strong"
          >
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-content-muted hover:text-content-strong hover:bg-brass-subtle focus-ring-brass transition-colors duration-quick ease-settle"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-border-subtle px-5 py-3 flex-shrink-0 bg-surface-base">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export default SlideOver
