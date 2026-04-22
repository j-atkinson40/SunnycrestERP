/**
 * EditCanvasCore — stub renderer for Focus `editCanvas` mode.
 *
 * Phase A Session 2 stub. Renders a faux toolbar above a ~600px-wide
 * centered canvas placeholder — visually a document/composition
 * surface. The mode is what Quote Building Focus + Proof Revision
 * Focus (Phase B–E) will use.
 *
 * Real canvas behavior (rich editing, save/discard, zoom) lands with
 * the first real edit-canvas Focus.
 */

import { Bold, Italic, Underline, Image } from "lucide-react"

import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


export function EditCanvasCore({ config }: CoreProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="editCanvas" title={config.displayName} />

      <div className="flex flex-1 flex-col items-center gap-3 overflow-auto rounded-md border border-border-subtle bg-surface-sunken/40 p-6">
        <div className="flex w-full max-w-[600px] items-center gap-1 rounded-md border border-border-subtle bg-surface-elevated px-2 py-1">
          <button
            type="button"
            disabled
            aria-label="Bold (placeholder)"
            className="flex h-8 w-8 items-center justify-center rounded text-content-muted"
          >
            <Bold className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled
            aria-label="Italic (placeholder)"
            className="flex h-8 w-8 items-center justify-center rounded text-content-muted"
          >
            <Italic className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled
            aria-label="Underline (placeholder)"
            className="flex h-8 w-8 items-center justify-center rounded text-content-muted"
          >
            <Underline className="h-4 w-4" />
          </button>
          <span className="mx-1 h-5 w-px bg-border-subtle" />
          <button
            type="button"
            disabled
            aria-label="Insert image (placeholder)"
            className="flex h-8 w-8 items-center justify-center rounded text-content-muted"
          >
            <Image className="h-4 w-4" />
          </button>
        </div>

        <div className="flex min-h-[320px] w-full max-w-[600px] flex-1 flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-6">
          <p className="text-body text-content-muted">
            Canvas placeholder
          </p>
          <p className="text-body-sm text-content-subtle">
            Edit-canvas content renders here. Real editing lands when
            Quote Building Focus (Phase B) or Proof Revision Focus
            (Phase E) ships.
          </p>
        </div>
      </div>

      <EscToDismissHint />
    </div>
  )
}
