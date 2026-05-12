/**
 * Arc 3b — Shared BlockKindPicker (Q-CROSS-2 canon).
 *
 * Extracted from DocumentsEditorPage.tsx so both the standalone
 * editor at `/visual-editor/documents` AND the inspector's
 * Documents tab consume the same component. Single source of truth.
 *
 * Pattern parallels Phase 2b NodeConfigForm extraction precedent:
 * shared authoring components live in one place; consumers import.
 *
 * Presentational + self-contained: takes `blockKinds`, `onPick`,
 * `onCancel`. Modal-style overlay; click backdrop or Cancel
 * dismisses. Each kind shows display_name + accepts_children badge
 * + description.
 */
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { BlockKindMetadata } from "@/bridgeable-admin/services/document-blocks-service"


export interface BlockKindPickerProps {
  blockKinds: BlockKindMetadata[]
  onPick: (kind: string) => void
  onCancel: () => void
}


export function BlockKindPicker({
  blockKinds,
  onPick,
  onCancel,
}: BlockKindPickerProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onCancel}
      data-testid="documents-block-picker-modal"
    >
      <div
        className="w-[480px] max-h-[80vh] overflow-y-auto rounded-md border border-border-subtle bg-surface-elevated p-4 shadow-level-2"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="text-h4 font-plex-serif text-content-strong">
            Add a block
          </div>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        <div className="grid gap-2">
          {blockKinds.map((k) => (
            <button
              key={k.kind}
              type="button"
              onClick={() => onPick(k.kind)}
              className="rounded-sm border border-border-subtle bg-surface-base p-3 text-left hover:bg-accent-subtle/30"
              data-testid={`documents-block-picker-${k.kind}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-body-sm font-medium text-content-strong">
                  {k.display_name}
                </span>
                {k.accepts_children && (
                  <Badge variant="outline">wraps children</Badge>
                )}
              </div>
              <div className="mt-1 text-caption text-content-muted">
                {k.description}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
