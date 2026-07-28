/**
 * TabletFrame — the shared inner shell for park tablets (S-5).
 *
 * WidgetChrome provides the machined-panel wrapper (border + gradient +
 * specular shadow) and the ghosted drag/dismiss chrome. The tablet's own
 * content renders inside via this frame: a header label, a scrollable
 * body, and a footer that carries the ONE chrome primary (send/save/
 * build-out) per the visual spec. `stopPropagation` on interactive
 * content so clicking inputs/buttons doesn't initiate a drag from the
 * drag-from-anywhere wrapper.
 */

import type { ReactNode } from "react"

export function TabletFrame({
  title,
  children,
  footer,
}: {
  title: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div
      className="flex h-full flex-col p-3"
      // Interactive tablet body — don't let clicks/drags on inputs start
      // a WidgetChrome drag. Drag still works from the header/margins.
      onPointerDown={(e) => e.stopPropagation()}
    >
      <header className="mb-2 shrink-0 border-b border-border-subtle pb-2">
        <h3 className="text-body-sm font-medium text-content-strong">
          {title}
        </h3>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      {footer && (
        <footer className="mt-2 shrink-0 border-t border-border-subtle pt-2">
          {footer}
        </footer>
      )}
    </div>
  )
}
